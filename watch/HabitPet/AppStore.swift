import Foundation
import SwiftUI
import CryptoKit

struct LocalState: Codable {
    var snapshot: Snapshot?
    var pending: [PendingAction] = []
    var focus: FocusTimer?
}
struct PetMemory: Decodable, Identifiable { let id: Int; let content: String; let category: String }
struct PetDiary: Decodable, Identifiable { let id: Int; let date: String; let response: PetMessage }
struct ReminderItem: Decodable, Identifiable { let id: Int; let response: PetMessage }
struct UserProfile: Codable {
    var timezone: String
    var personality: String
    var sleepTarget: Int
    var aiHealthConsent: Bool
    var memoryEnabled: Bool
    var quietStart: Int
    var quietEnd: Int
}

@MainActor final class AppStore: ObservableObject {
    @Published var local = LocalState()
    @Published var authenticated = false
    @Published var busy = false
    @Published var notice = ""
    @Published var blocked = false
    @Published var reply: PetMessage?
    @Published var memories: [PetMemory] = []
    @Published var diaries: [PetDiary] = []
    @Published var profile: UserProfile?
    @Published var reminders: [ReminderItem] = []
    let api = APIClient()
    private let health = HealthKitService()
    var display: Snapshot? { local.snapshot.map { Projection.apply(local.pending, to: $0, now: Date()) } }
    var isOfflineEstimate: Bool { !local.pending.isEmpty }
    init() {
        authenticated = api.credentials != nil
        load()
    }
    private var cacheURL: URL? {
        guard let credentials = api.credentials else { return nil }
        let id = SHA256.hash(data: Data((credentials.baseURL + "|" + credentials.username).utf8)).map { String(format: "%02x", $0) }.joined()
        return FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first?.appendingPathComponent("\(id).json")
    }
    private func load() {
        guard let url = cacheURL, FileManager.default.fileExists(atPath: url.path) else { return }
        do { local = try Wire.decoder().decode(LocalState.self, from: Data(contentsOf: url)) }
        catch { notice = "本地数据读取失败，请联网刷新。" }
    }
    private func save() throws {
        guard let url = cacheURL else { throw APIError(status: 401, detail: "请重新登录") }
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Wire.encoder().encode(local).write(to: url, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
    }
    func perform(_ operation: () async throws -> Void) async {
        guard !busy else { return }
        busy = true; defer { busy = false }
        do { try await operation() }
        catch let error as APIError {
            notice = error.localizedDescription
            if error.status == 401 { authenticated = false }
        }
        catch { notice = error.localizedDescription }
    }
    func login(url: String, username: String, password: String, register: Bool) async {
        await perform {
            try await api.login(baseURL: url, username: username, password: password, register: register)
            local = LocalState(); load(); authenticated = true
            try await flush()
        }
    }
    func refresh() async {
        await perform { try await flush() }
    }
    private func flush() async throws {
        blocked = false
        while let first = local.pending.first {
            do {
                let result: Snapshot = try await api.request("api/actions/", method: "POST", body: Wire.encoder().encode(first))
                local.snapshot = result
                local.pending.removeFirst()
                try save()
            } catch let error as APIError {
                blocked = error.status != 401 && error.status != 429 && error.status < 500
                throw error
            }
        }
        local.snapshot = try await api.request("api/today/")
        try save(); notice = "已同步"
    }
    @discardableResult func action(_ kind: String, payload: [String:Int] = [:]) async -> Bool {
        var didQueue = false
        await perform {
            guard let snapshot = display else { return }
            if blocked { throw APIError(status:409,detail:"请先处理同步冲突") }
            if kind == "feed" && (snapshot.inventory.food < 1 || snapshot.pet.hunger >= 100) {
                throw APIError(status:409,detail:"没有食物，或宠物已经吃饱")
            }
            let item = PendingAction(kind: kind, generation: snapshot.pet.generation, payload: payload)
            local.pending.append(item)
            do { try save() } catch { local.pending.removeLast(); throw error }
            didQueue = true
            do { try await flush() }
            catch let error as URLError {
                notice = "已保存到本机，联网后确认（\(error.code.rawValue)）"
            }
        }
        return didQueue
    }
    func discardFirst() async {
        await perform {
            guard !local.pending.isEmpty else { return }
            local.pending.removeFirst(); try save(); blocked = false
            try await flush()
        }
    }
    func createHabit(name: String, target: Int, category: String) async {
        await perform {
            let body: [String:Any] = ["name":name,"target":target,"category":category,"unit":"minutes","reward_type":"food","reward_amount":1]
            try await api.empty("api/habits/",method:"POST",body:JSONSerialization.data(withJSONObject:body))
            try await flush()
        }
    }
    func deleteHabit(_ id: Int) async {
        await perform {
            try await api.empty("api/habits/\(id)/",method:"DELETE")
            try await flush()
        }
    }
    func startFocus(_ habit: Habit) async {
        guard !busy, local.focus == nil else { return }
        local.focus = FocusTimer(habitID:habit.id,goalSeconds:Double(max(0,habit.target-habit.progress))*60)
        do { try save(); try await NotificationService.focus(seconds:local.focus!.remaining(at:Date())) }
        catch { notice = error.localizedDescription }
    }
    func toggleFocus() async {
        guard var timer = local.focus else { return }
        if timer.runningSince == nil { timer.resume(at:Date()) } else { timer.pause(at:Date()) }
        local.focus = timer
        do {
            try save()
            if timer.runningSince != nil { try await NotificationService.focus(seconds:timer.remaining(at:Date())) }
            else { NotificationService.cancelFocus() }
        } catch { notice = error.localizedDescription }
    }
    func cancelFocus() {
        local.focus = nil; NotificationService.cancelFocus()
        do { try save() } catch { notice = error.localizedDescription }
    }
    func finishFocus() async {
        guard let timer=local.focus,timer.remaining(at:Date())<=0 else { return }
        // The persisted complete operation is the authoritative, idempotent reward request.
        let queued = await action("complete",payload:["habit_id":timer.habitID])
        if queued && !blocked { cancelFocus() }
    }
    @discardableResult func syncHealth() async -> Bool {
        var synced = false
        await perform {
            try await health.authorize()
            let summary=try await health.summary(timezone:local.snapshot?.timezone ?? TimeZone.current.identifier)
            guard summary.steps != nil || summary.sleep != nil else { notice="暂无可读取的健康数据；这不表示你没有活动或睡眠。"; return }
            let body:[String:Any] = ["steps": summary.steps as Any? ?? NSNull(),"sleep_minutes":summary.sleep as Any? ?? NSNull(),"observed_at":ISO8601DateFormatter().string(from:Date())]
            local.snapshot = try await api.request("api/health/sync/",method:"POST",body:JSONSerialization.data(withJSONObject:body))
            try save(); notice="健康摘要已同步"; synced = summary.steps != nil
        }
        return synced
    }
    func cancelSession(_ id: Int) async {
        await perform {
            try await api.empty("api/sessions/\(id)/", method:"DELETE")
            try await flush()
        }
    }
    func chat(_ text: String) async {
        await perform { reply = try await api.request("api/pet/chat/",method:"POST",body:JSONSerialization.data(withJSONObject:["message":text])) }
    }
    func loadExtras() async {
        await perform {
            profile = try await api.request("api/profile/")
            memories = try await api.request("api/memories/")
            diaries = try await api.request("api/diary/")
            reminders = try await api.request("api/reminders/")
        }
    }
    func saveProfile(_ value: UserProfile) async {
        await perform { profile = try await api.request("api/profile/",method:"PATCH",body:Wire.encoder().encode(value)) }
    }
    func deleteMemory(_ id:Int) async {
        await perform { try await api.empty("api/memories/\(id)/",method:"DELETE"); memories.removeAll { $0.id==id } }
    }
    func generateDiary() async {
        await perform {
            let diary: PetDiary = try await api.request("api/diary/",method:"POST",body:Data("{}".utf8))
            diaries.removeAll { $0.id==diary.id }; diaries.insert(diary,at:0)
        }
    }
    func logout(deleteAccount: Bool = false) async {
        await perform {
            if let token=UserDefaults.standard.string(forKey:"apnsToken") {
                try await api.empty("api/devices/",method:"DELETE",body:JSONSerialization.data(withJSONObject:["token":token]))
                UserDefaults.standard.removeObject(forKey:"apnsToken")
            }
            if deleteAccount { try await api.empty("api/account/",method:"DELETE") }
            else if let refresh=api.credentials?.refresh {
                try await api.empty("api/auth/logout/",method:"POST",body:JSONSerialization.data(withJSONObject:["refresh":refresh]))
            }
            if let url=cacheURL { try? FileManager.default.removeItem(at:url) }
            KeychainStore.clear(); api.credentials=nil; local=LocalState(); authenticated=false
            reply=nil; memories=[]; diaries=[]; profile=nil; reminders=[]; NotificationService.clear()
        }
    }
}
