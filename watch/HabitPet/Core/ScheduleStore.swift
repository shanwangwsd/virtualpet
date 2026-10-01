import Combine
import UserNotifications

@MainActor final class ScheduleStore: ObservableObject {
    @Published private(set) var reminders: [DailyReminder] = []
    @Published private(set) var busy = false
    @Published private(set) var storageReadable = true
    @Published var notice = ""
    @Published private(set) var appearance = PetAppearance()
    private let appearanceKey = "schedulePetAppearance.v1"
    private var needsAppearanceRefresh = false
    private let key = "dailySchedule.v1"
    private let notifications: ReminderNotifications
    private let defaults: UserDefaults
    private var revision = 0

    init(defaults: UserDefaults = .standard, notifications: ReminderNotifications? = nil) {
        self.defaults = defaults
        self.notifications = notifications ?? SystemReminderNotifications()
        if let saved = defaults.data(forKey: appearanceKey), let identity = try? JSONDecoder().decode(PetAppearance.self, from: saved) { appearance = identity }
        guard let data = defaults.data(forKey: key) else { return }
        do {
            let saved = try JSONDecoder().decode([DailyReminder].self, from: data)
            reminders = try saved.reduce([]) { try DailySchedule.upserting($1, into: $0) }
        } catch {
            storageReadable = false
            notice = ScheduleError.unreadableStorage.localizedDescription
        }
    }
    private func persist(_ values: [DailyReminder], data: Data) {
        defaults.set(data, forKey: key)
        reminders = values
    }
    func save(_ reminder: DailyReminder) async -> Bool {
        guard !busy, storageReadable else { return false }
        busy = true; defer { finishWork() }
        let operationRevision = revision
        do {
            let next = try DailySchedule.upserting(reminder, into: reminders)
            let data = try JSONEncoder().encode(next)
            if reminder.enabled {
                guard try await notifications.authorize() else { throw ScheduleError.permissionDenied }
                guard revision == operationRevision else { return false }
                // The stable identifier replaces any previous request for this reminder.
                try await notifications.add(reminder.notificationRequest(appearance: appearance))
            } else { cancel([reminder.notificationID]) }
            guard revision == operationRevision else {
                cancel([reminder.notificationID]); return false
            }
            persist(next, data: data)
            notice = !reminder.enabled ? "Reminder is off." : reminder.speechSource=="fallback" ? "Saved with local voice. Re-save online for AI voice." : "Saved. \(appearance.name) will remind you every day."
            return true
        } catch { show(error); return false }
    }
    func delete(_ reminder: DailyReminder) {
        guard !busy, storageReadable else { return }
        do {
            let next = reminders.filter { $0.id != reminder.id }
            let data = try JSONEncoder().encode(next)
            cancel([reminder.notificationID])
            persist(next, data: data)
            notice = "Reminder deleted."
        } catch { show(error) }
    }
    func disableAll() {
        guard !busy, storageReadable else { return }
        do {
            let next = reminders.map { item -> DailyReminder in var off = item; off.enabled = false; return off }
            let data = try JSONEncoder().encode(next)
            cancel(reminders.map(\.notificationID))
            persist(next, data: data)
            notice = "All schedule reminders are off."
        } catch { show(error) }
    }
    func updateAppearance(_ value: PetAppearance) async {
        guard appearance != value else { return }
        appearance = value
        defaults.set(try? JSONEncoder().encode(value), forKey: appearanceKey)
        needsAppearanceRefresh = true
        if !busy { await restore() }
    }
    private func finishWork() {
        busy = false
        if needsAppearanceRefresh, storageReadable {
            Task { await self.restore() }
        }
    }
    func restore() async {
        guard !busy, storageReadable else { return }
        needsAppearanceRefresh = false
        busy = true; defer { finishWork() }
        let operationRevision = revision
        let pending = await notifications.pendingIDs()
        guard revision == operationRevision else { return }
        cancel(DailySchedule.cancellations(reminders: reminders, pending: pending))
        let allowed = await notifications.authorized()
        guard revision == operationRevision else { return }
        guard allowed else {
            if reminders.contains(where: \.enabled) { notice = ScheduleError.permissionDenied.localizedDescription }
            return
        }
        do {
            for reminder in reminders where reminder.enabled {
                guard revision == operationRevision else { return }
                try await notifications.add(reminder.notificationRequest(appearance: appearance))
                guard revision == operationRevision else { cancel([reminder.notificationID]); return }
            }
            notice = ""
        } catch { show(error) }
    }
    func clear() {
        revision += 1
        cancel(reminders.map(\.notificationID))
        // Include any orphaned requests when resetting unreadable saved data.
        Task {
            let ids = await notifications.pendingIDs()
            cancel(DailySchedule.cancellations(reminders: reminders, pending: ids))
        }
        defaults.removeObject(forKey: key)
        defaults.removeObject(forKey: appearanceKey)
        appearance = PetAppearance(); needsAppearanceRefresh = false
        reminders = []; storageReadable = true; notice = ""
    }
    private func cancel(_ ids: [String]) {
        notifications.cancel(ids)
    }
    private func show(_ error: Error) {
        notice = (error as? ScheduleError)?.localizedDescription ?? "Could not save your reminders. Please try again."
    }
}


// The operating-system boundary is injectable so permission and delivery failures
// can be exercised without showing real notifications in the test runner.
@MainActor protocol ReminderNotifications {
    func authorize() async throws -> Bool
    func authorized() async -> Bool
    func add(_ request: UNNotificationRequest) async throws
    func pendingIDs() async -> [String]
    func cancel(_ ids: [String])
}

@MainActor private final class SystemReminderNotifications: ReminderNotifications {
    private let center = UNUserNotificationCenter.current()
    func authorize() async throws -> Bool {
        try await center.requestAuthorization(options: [.alert, .sound])
    }
    func authorized() async -> Bool {
        let status = await center.notificationSettings().authorizationStatus
        return status == .authorized || status == .provisional
    }
    func add(_ request: UNNotificationRequest) async throws { try await center.add(request) }
    func pendingIDs() async -> [String] { await center.pendingNotificationRequests().map(\.identifier) }
    func cancel(_ ids: [String]) {
        center.removePendingNotificationRequests(withIdentifiers: ids)
        center.removeDeliveredNotifications(withIdentifiers: ids)
    }
}
