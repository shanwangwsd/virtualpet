import Foundation
import SwiftUI
import CryptoKit

struct LocalState: Codable {
    var snapshot: Snapshot?
    var pending: [PendingAction] = []
    var focus: FocusTimer?
}
struct UserProfile: Codable {
    var timezone: String
    var personality: String
    var sleepTarget: Int
    var aiHealthConsent: Bool
    var quietStart: Int
    var quietEnd: Int
}

@MainActor final class AppStore: ObservableObject {
    @Published var local = LocalState()
    @Published var authenticated = false
    @Published var busy = false
    @Published var notice = ""
    @Published var blocked = false
    @Published var profile: UserProfile?
    @Published var syncing = false
    @Published var careMessage: String?
    @Published var actionVisual: String?
    private var visualTask: Task<Void,Never>?
    private var speechTask: Task<Void,Never>?
    private var latestCareID: UUID?
    private var lastSpeechAt: Date = .distantPast
    @Published var healthPreview: HealthDayInput?
    private var sessionRevision = 0
    private let backgroundSync = BackgroundSync()
    let api = APIClient()
    private let health = HealthKitService()
    var display: Snapshot? { local.snapshot.map { Projection.apply(local.pending, to: $0, now: Date()) } }
    var statusMessage: String? {
        ["", "Up to date", "Saved on this Watch. Syncing in the background."].contains(notice) ? nil : notice
    }
    func projected(at date:Date) -> Snapshot? { local.snapshot.map { Projection.apply(local.pending,to:$0,now:date) } }
    var isOfflineEstimate: Bool { !local.pending.isEmpty }
    init() {
        authenticated = api.credentials != nil
        load()
        if healthConnected { observeHealth() }
    }
    private var cacheURL: URL? {
        guard let credentials = api.credentials else { return nil }
        let id = SHA256.hash(data: Data((credentials.baseURL + "|" + credentials.username).utf8)).map { String(format: "%02x", $0) }.joined()
        return FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first?.appendingPathComponent("\(id).json")
    }
    private func load() {
        guard let url = cacheURL, FileManager.default.fileExists(atPath: url.path) else { return }
        do {
            local = try Wire.decoder().decode(LocalState.self, from: Data(contentsOf: url))
            let count=local.pending.count
            local.pending.removeAll { ["walk_start", "walk_finish", "play"].contains($0.kind) }
            if count != local.pending.count { try save(); notice="Retired actions were removed from the sync queue." }
        }
        catch { notice = "Could not read local data. Connect and refresh." }
    }
    private func save() throws {
        guard let url = cacheURL else { throw APIError(status: 401, detail: "Please sign in again.") }
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Wire.encoder().encode(local).write(to: url, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
    }
    func perform(_ operation: () async throws -> Void) async {
        guard !busy else { return }
        guard !syncing else { notice = "Sync is finishing. Please try again shortly."; return }
        busy = true; defer { busy = false }
        do { try await operation() }
        catch let error as APIError {
            notice = error.localizedDescription
            if error.status == 401 { authenticated = false }
        }
        catch { notice = RequestFailure.message(error, server: api.credentials?.baseURL) }
    }
    func login(url: String, username: String, password: String, register: Bool) async {
        await perform {
            sessionRevision += 1
            try await api.login(baseURL: url, username: username, password: password, register: register)
            local = LocalState(); load(); authenticated = true
            startSync()
        }
    }
    func refresh() async {
        guard !busy else { return }
        startSync()
    }
    private func startSync() {
        guard authenticated, !backgroundSync.running else { return }
        syncing = true
        backgroundSync.start({ await self.refreshHealthPreview(); try Task.checkCancellation(); try await self.flush() }, finished: { error in
            self.syncing = false
            if let error { self.reportSyncFailure(error) }
            else if !self.local.pending.isEmpty { self.startSync() }
        })
    }
    private func reportSyncFailure(_ error: Error) {
        if let error = error as? APIError {
            notice = error.localizedDescription
            if error.status == 401 { authenticated = false }
        } else if error is DecodingError {
            notice = "The server reply could not be read. Update the backend and retry sync. Your actions are saved."
        } else if let error = error as? URLError {
            let host = api.credentials.flatMap { URL(string: $0.baseURL)?.host } ?? "your server"
            let reason = error.code == .timedOut ? "Server timed out" : "Cannot connect to the server"
            notice = "\(reason) (\(host)). Actions are saved on this Watch. Check the server address and connection, then retry."
        } else {
            notice = "Could not sync. Your actions are saved on this Watch. Please retry."
        }
    }
    private func flush() async throws {
        blocked = false
        var speechAction: PendingAction?
        var healthFailed=false
        while let first = local.pending.first {
            do {
                let result: Snapshot = try await api.request("api/actions/", method: "POST", body: Wire.encoder().encode(first))
                local.snapshot = result
                local.pending.removeFirst()
                try save()
                if first.id == latestCareID { speechAction=first }
            } catch let error as APIError {
                blocked = error.status != 401 && error.status != 429 && error.status < 500
                throw error
            }
        }
        // Drain saved actions before settling all elapsed time or asking AI for context.
        if healthConnected, local.snapshot != nil {
            do { try await synchronizeFitness() } catch is CancellationError { throw CancellationError() } catch { healthFailed=true }
        }
        local.snapshot = try await api.request("api/today/")
        try save()
        if let speechAction, local.pending.isEmpty { requestSpeech(for:speechAction) }
        notice = healthFailed ? "Care synced. Health data could not sync; retry Activity & Health." : "Up to date"
    }
    @discardableResult func action(_ kind: String, payload: [String:Int] = [:]) async -> Bool {
        guard !busy, authenticated, let snapshot = display else { return false }
        guard !blocked else { notice = "Resolve the sync conflict first."; return false }
        if let error=PetRules.actionError(kind,payload:payload,snapshot:snapshot,pending:local.pending) {
            notice=error; return false
        }
        let item = PendingAction(kind: kind, generation: snapshot.pet.generation, payload: payload)
        local.pending.append(item)
        do { try save() }
        catch { local.pending.removeLast(); notice = "Could not save this action. Please try again."; return false }
        if ["water","use_item","rest","wake"].contains(kind) {
            latestCareID=item.id
            speechTask?.cancel()
            let food=kind=="use_item" && snapshot.inventory.items?.first(where: { $0.id==payload["item_id"] })?.category=="food"
            actionVisual=kind=="water" ? "drink" : food ? "eat" : kind=="rest" ? "rest" : kind=="wake" ? "wake" : "play"
            careMessage=nil
            visualTask?.cancel()
            visualTask=Task { [weak self] in
                do { try await Task.sleep(nanoseconds:4_000_000_000) } catch { return }
                self?.actionVisual=nil
            }
        } else { latestCareID=nil; speechTask?.cancel(); careMessage=nil; actionVisual=nil }
        notice = "Saved on this Watch. Syncing in the background."
        startSync()
        return true
    }
    func dismissCareAnimation() {
        visualTask?.cancel()
        actionVisual=nil
    }
    func prepareScheduleSpeech(_ reminder:DailyReminder) async -> DailyReminder? {
        let revision=sessionRevision
        await backgroundSync.waitUntilFinished()
        guard authenticated, !Task.isCancelled, revision==sessionRevision else { return nil }
        var prepared=reminder
        prepared.voicePersonality=local.snapshot?.personality ?? "playful"
        prepared.generatedSpeech=nil; prepared.generatedForTitle=nil; prepared.speechSource="fallback"
        // Never let optional speech advance a pet past unconfirmed saved care.
        if !local.pending.isEmpty { return prepared }
        await perform {
            let body=try JSONSerialization.data(withJSONObject:["title":reminder.title,"hour":reminder.hour,"minute":reminder.minute])
            let reply:ScheduleSpeechReply=try await api.request("api/schedule/speech/",method:"POST",body:body)
            prepared.generatedSpeech=reply.message
            prepared.generatedForTitle=reminder.title.trimmingCharacters(in:.whitespacesAndNewlines)
            prepared.voicePersonality=reply.personality; prepared.generatedForPersonality=reply.personality
            prepared.speechSource=reply.source
        }
        guard authenticated, revision==sessionRevision, !Task.isCancelled else { return nil }
        return prepared
    }
    func discardFirst() async {
        await perform {
            guard !local.pending.isEmpty else { return }
            local.pending.removeFirst(); try save(); blocked = false
            try await flush()
        }
    }
    func createHabit(name: String, target: Int, category: String) async -> Bool {
        var created=false
        await perform {
            let body: [String:Any] = ["name":name,"target":target,"category":category,"unit":"minutes","reward_type":"food","reward_amount":1]
            try await api.empty("api/habits/",method:"POST",body:JSONSerialization.data(withJSONObject:body))
            created=true
            try await flush()
        }
        return created
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
        catch { notice = RequestFailure.message(error, server: api.credentials?.baseURL) }
    }
    func toggleFocus() async {
        guard var timer = local.focus else { return }
        if timer.runningSince == nil { timer.resume(at:Date()) } else { timer.pause(at:Date()) }
        local.focus = timer
        do {
            try save()
            if timer.runningSince != nil { try await NotificationService.focus(seconds:timer.remaining(at:Date())) }
            else { NotificationService.cancelFocus() }
        } catch { notice = RequestFailure.message(error, server: api.credentials?.baseURL) }
    }
    func cancelFocus() {
        local.focus = nil; NotificationService.cancelFocus()
        do { try save() } catch { notice = RequestFailure.message(error, server: api.credentials?.baseURL) }
    }
    func finishFocus() async -> Bool {
        guard let timer=local.focus,timer.remaining(at:Date())<=0 else { return false }
        // The persisted complete operation is the authoritative, idempotent reward request.
        let queued = await action("complete",payload:["habit_id":timer.habitID])
        if queued && !blocked { cancelFocus() }
        return queued
    }
    var healthConnected: Bool { UserDefaults.standard.bool(forKey: "healthAccessRequested") }
    private func observeHealth() {
        health.observeChanges { [weak self] in
            Task { @MainActor in
                guard let self, self.authenticated, self.healthConnected else { return }
                await self.refresh()
            }
        }
    }
    var currentStepPreview: Int? {
        if let preview=healthPreview { return preview.steps }
        guard let health=local.snapshot?.health, health.stepsObservedAt != nil else { return nil }
        return health.steps
    }
    var currentSleepPreview: Int? {
        if let preview=healthPreview { return preview.sleepMinutes }
        return local.snapshot?.health.sleepPreviewMinutes
    }
    private func refreshHealthPreview() async {
        guard healthConnected, authenticated else { return }
        let revision=sessionRevision
        let zone=local.snapshot?.health.fitnessTimezone ?? local.snapshot?.timezone ?? TimeZone.current.identifier
        let now=Date()
        let calendar=FitnessCalendar.calendar(zone)
        let day=calendar.startOfDay(for:now)
        do {
            let result=try await health.readBatch(FitnessBatch(days:[day],hasMore:false),timezone:zone,now:now)
            guard !Task.isCancelled, revision == sessionRevision else { return }
            healthPreview=result.first
        } catch {
            guard !Task.isCancelled, revision == sessionRevision else { return }
            healthPreview=HealthDayInput(date:FitnessCalendar.key(day,calendar:calendar),steps:nil,sleepMinutes:nil)
        }
    }
    private func synchronizeFitness() async throws {
        while let snapshot = local.snapshot, let start=snapshot.health.fitnessStartedOn, snapshot.pet.state != "dead" {
            try Task.checkCancellation()
            let zone=snapshot.health.fitnessTimezone ?? snapshot.timezone
            let now=Date()
            let batch=try FitnessCalendar.batch(start:start,lastSteps:snapshot.health.lastStepSettlementDate,lastSleep:snapshot.health.lastSleepSettlementDate,timezone:zone,now:now)
            guard !batch.days.isEmpty else { return }
            let readings=try await health.readBatch(batch,timezone:zone,now:now)
            try Task.checkCancellation()
            let upload=HealthUpload(generation:snapshot.pet.generation,observedAt:now,days:readings)
            let updated: Snapshot=try await api.request("api/health/sync/",method:"POST",body:Wire.encoder().encode(upload))
            local.snapshot=updated; try save()
            if !batch.hasMore { return }
            if updated.health.lastStepSettlementDate == snapshot.health.lastStepSettlementDate && updated.health.lastSleepSettlementDate == snapshot.health.lastSleepSettlementDate {
                return // Unfinished/unknown windows are never guessed just to advance a cursor.
            }
        }
    }
    func syncHealth() async {
        guard !busy else { return }
        busy=true
        do {
            try await health.authorize()
            UserDefaults.standard.set(true,forKey:"healthAccessRequested")
            observeHealth()
            notice="Health connected. Checking Fitness records."
        } catch {
            notice=(error as? APIError)?.localizedDescription ?? RequestFailure.message(error,server:api.credentials?.baseURL)
        }
        busy=false
        if healthConnected { startSync() }
    }
    func cancelSession(_ id: Int) async {
        await perform {
            try await api.empty("api/sessions/\(id)/", method:"DELETE")
            try await flush()
        }
    }
    func savePetDetails(generation:Int,name:String,species:String,personality:String) async -> Bool {
        guard local.pending.isEmpty else { notice="Sync saved actions before editing your pet."; startSync(); return false }
        var saved=false
        await perform {
            let body:[String:Any]=["generation":generation,"name":name,"species":species,"personality":personality]
            local.snapshot=try await api.request("api/pet/",method:"PATCH",body:JSONSerialization.data(withJSONObject:body))
            speechTask?.cancel(); latestCareID=nil
            try save(); careMessage=nil; notice="Pet details saved."; saved=true
        }
        return saved
    }
    private func requestSpeech(for action:PendingAction) {
        guard Date().timeIntervalSince(lastSpeechAt)>=15 else { return }
        lastSpeechAt=Date()
        let revision=sessionRevision
        speechTask=Task { [weak self] in
            guard let self else { return }
            do {
                let reply=try await api.careReaction(actionID:action.id)
                guard !Task.isCancelled, revision==sessionRevision, latestCareID==action.id,
                      display?.pet.generation==action.generation, display?.pet.state != "dead" else { return }
                careMessage=reply.message
            } catch { /* Local personality response remains available. */ }
        }
    }
    func loadProfile() async {
        await backgroundSync.waitUntilFinished()
        guard !Task.isCancelled, authenticated else { return }
        await perform { profile = try await api.request("api/profile/") }
    }
    func saveProfile(_ value: UserProfile) async {
        speechTask?.cancel(); careMessage=nil; latestCareID=nil
        await perform {
            profile = try await api.request("api/profile/",method:"PATCH",body:Wire.encoder().encode(value))
            local.snapshot?.personality=profile?.personality
            try save()
        }
    }
    private func clearLocalSession() throws {
        if let url = cacheURL, FileManager.default.fileExists(atPath: url.path) { try FileManager.default.removeItem(at: url) }
        try KeychainStore.clearChecked(); sessionRevision += 1; api.credentials = nil; local = LocalState(); authenticated = false
        visualTask?.cancel(); speechTask?.cancel(); actionVisual=nil; latestCareID=nil
        careMessage = nil; healthPreview = nil; profile = nil; blocked = false
        UserDefaults.standard.removeObject(forKey: "apnsToken")
        UserDefaults.standard.removeObject(forKey: "healthAccessRequested")
        NotificationService.clear()
    }
    func logout(deleteAccount: Bool = false) async {
        guard !busy else { return }
        busy = true
        await backgroundSync.cancelAndWait()
        syncing = false
        let credentials = api.credentials
        let token = UserDefaults.standard.string(forKey: "apnsToken")
        var exitRevision = sessionRevision
        do {
            let confirmed = try await AccountExit.run(deleteAccount: deleteAccount, remote: {
                if deleteAccount { try await self.api.empty("api/account/", method: "DELETE") }
                else if let credentials { try await self.api.revokeSession(credentials, deviceToken: token) }
            }, clearLocal: {
                try self.clearLocalSession()
                exitRevision = self.sessionRevision
                self.notice = deleteAccount ? "Account deleted." : "Signed out on this Watch."
                // Allow the sign-in screen while best-effort remote revocation finishes.
                self.busy = false
            })
            if !authenticated && exitRevision == sessionRevision { notice = deleteAccount ? "Account deleted." : confirmed ? "Signed out." : "Signed out on this Watch. Server sign-out could not be confirmed." }
        } catch {
            busy = false
            let detail = (error as? APIError)?.localizedDescription ?? RequestFailure.message(error, server: credentials?.baseURL)
            notice = deleteAccount ? "Account deletion was not confirmed. " + detail : detail
        }
        if deleteAccount { busy = false }
    }
}
