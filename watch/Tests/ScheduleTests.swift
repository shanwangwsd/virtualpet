import XCTest
import UserNotifications
@testable import HabitPetCore

final class ScheduleTests: XCTestCase {
    func testDailyRequestUsesWallClockAndPetMessage() throws {
        let reminder = DailyReminder(title: "Read a book", hour: 21, minute: 15)
        let request = try reminder.notificationRequest()
        let trigger = try XCTUnwrap(request.trigger as? UNCalendarNotificationTrigger)
        XCTAssertTrue(trigger.repeats)
        XCTAssertEqual(trigger.dateComponents.hour, 21)
        XCTAssertEqual(trigger.dateComponents.minute, 15)
        XCTAssertNil(trigger.dateComponents.timeZone)
        XCTAssertNil(trigger.dateComponents.day)
        XCTAssertTrue(request.content.body.contains("Read a book"))
        XCTAssertEqual(request.content.categoryIdentifier, DailyReminder.category)
    }
    func testEditingReplacesSameNotificationAfterRelaunch() throws {
        let original = DailyReminder(title: "Read", hour: 9, minute: 0)
        var reminders = try DailySchedule.upserting(original, into: [])
        var edited = try JSONDecoder().decode([DailyReminder].self, from: JSONEncoder().encode(reminders))[0]
        edited.hour = 20
        edited.title = "Study"
        reminders = try DailySchedule.upserting(edited, into: reminders)
        XCTAssertEqual(reminders.count, 1)
        XCTAssertEqual(try reminders[0].notificationRequest().identifier, original.notificationID)
        XCTAssertEqual(reminders[0].hour, 20)
        XCTAssertEqual(reminders[0].title, "Study")
    }
    func testDisableAndDeleteCancelOnlyScheduleNotifications() {
        let active = DailyReminder(title: "Read", hour: 8, minute: 0)
        var disabled = DailyReminder(title: "Walk", hour: 9, minute: 0)
        disabled.enabled = false
        let deleted = DailyReminder(title: "Study", hour: 10, minute: 0)
        let pending = [active.notificationID, disabled.notificationID, deleted.notificationID, "focus", "daily"]
        XCTAssertEqual(Set(DailySchedule.cancellations(reminders: [active, disabled], pending: pending)), Set([disabled.notificationID, deleted.notificationID]))
    }
    func testInvalidInputCannotBecomeScheduledNotification() {
        for reminder in [DailyReminder(title: "  \n", hour: 9, minute: 0), DailyReminder(title: "Read", hour: 24, minute: 0), DailyReminder(title: "Read", hour: 9, minute: 60)] {
            XCTAssertThrowsError(try reminder.notificationRequest())
            XCTAssertThrowsError(try DailySchedule.upserting(reminder, into: []))
        }
    }
    func testSeparateRemindersAtSameTimeAreKeptAndTitlesTrimmed() throws {
        let first = DailyReminder(title: "Read", hour: 9, minute: 0)
        let second = DailyReminder(title: "  Drink water  ", hour: 9, minute: 0)
        let reminders = try DailySchedule.upserting(second, into: [first])
        XCTAssertEqual(reminders.count, 2)
        XCTAssertEqual(reminders.first(where: { $0.id == second.id })?.title, "Drink water")
        XCTAssertNotEqual(first.notificationID, second.notificationID)
    }
    func testLimitAllowsEditingButRejectsAdditionalReminder() throws {
        let full = (0..<DailySchedule.limit).map { DailyReminder(title: "Task \($0)", hour: 9, minute: 0) }
        XCTAssertThrowsError(try DailySchedule.upserting(DailyReminder(title: "Extra", hour: 10, minute: 0), into: full))
        var edited = full[0]; edited.minute = 30
        XCTAssertEqual(try DailySchedule.upserting(edited, into: full).count, full.count)
    }
}

@MainActor final class ScheduleStoreTests: XCTestCase {
    var defaults: UserDefaults!
    var suite: String!
    override func setUp() async throws {
        suite = "HabitPetTests.\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suite)
    }
    override func tearDown() async throws { defaults.removePersistentDomain(forName: suite) }

    func testSavedChangesSurviveRelaunchAndDisableCancelsDelivery() async {
        let notifications = TestReminderNotifications()
        let store = ScheduleStore(defaults: defaults, notifications: notifications)
        var reminder = DailyReminder(title: "Read", hour: 9, minute: 0)
        let saved = await store.save(reminder)
        XCTAssertTrue(saved)
        reminder.hour = 20
        _ = await store.save(reminder)
        XCTAssertEqual(notifications.pending.count, 1)
        let reloaded = ScheduleStore(defaults: defaults, notifications: notifications)
        XCTAssertEqual(reloaded.reminders.first?.hour, 20)
        reminder.enabled = false
        _ = await reloaded.save(reminder)
        XCTAssertTrue(notifications.pending.isEmpty)
        XCTAssertEqual(ScheduleStore(defaults: defaults, notifications: notifications).reminders.first?.enabled, false)
    }
    func testDeniedPermissionAndAddFailureKeepPreviousSavedSchedule() async {
        let notifications = TestReminderNotifications()
        let store = ScheduleStore(defaults: defaults, notifications: notifications)
        var reminder = DailyReminder(title: "Read", hour: 9, minute: 0)
        _ = await store.save(reminder)
        reminder.hour = 15
        notifications.allowed = false
        let denied = await store.save(reminder)
        XCTAssertFalse(denied)
        XCTAssertEqual(store.reminders.first?.hour, 9)
        notifications.allowed = true; notifications.failAdd = true
        let failed = await store.save(reminder)
        XCTAssertFalse(failed)
        XCTAssertEqual(ScheduleStore(defaults: defaults, notifications: notifications).reminders.first?.hour, 9)
    }
    func testDeleteAndDisableAllStayOffAfterRestore() async {
        let notifications = TestReminderNotifications()
        let store = ScheduleStore(defaults: defaults, notifications: notifications)
        let first = DailyReminder(title: "Read", hour: 9, minute: 0)
        let second = DailyReminder(title: "Walk", hour: 10, minute: 0)
        _ = await store.save(first); _ = await store.save(second)
        store.delete(first); store.disableAll()
        let reloaded = ScheduleStore(defaults: defaults, notifications: notifications)
        await reloaded.restore()
        XCTAssertEqual(reloaded.reminders.map(\.id), [second.id])
        XCTAssertFalse(reloaded.reminders[0].enabled)
        XCTAssertTrue(notifications.pending.isEmpty)
    }
    func testClearDuringSaveDoesNotResurrectOldAccountReminder() async {
        let notifications = TestReminderNotifications()
        let store = ScheduleStore(defaults: defaults, notifications: notifications)
        notifications.onAdd = { store.clear() }
        let saved = await store.save(DailyReminder(title: "Read", hour: 9, minute: 0))
        XCTAssertFalse(saved)
        XCTAssertTrue(store.reminders.isEmpty)
        XCTAssertTrue(notifications.pending.isEmpty)
        XCTAssertTrue(ScheduleStore(defaults: defaults, notifications: notifications).reminders.isEmpty)
    }
}

@MainActor private final class TestReminderNotifications: ReminderNotifications {
    var allowed = true
    var failAdd = false
    var pending: [String: UNNotificationRequest] = [:]
    var onAdd: (() -> Void)?
    func authorize() async throws -> Bool { allowed }
    func authorized() async -> Bool { allowed }
    func add(_ request: UNNotificationRequest) async throws {
        if failAdd { throw NSError(domain: "test-scheduler", code: 1) }
        onAdd?()
        pending[request.identifier] = request
    }
    func pendingIDs() async -> [String] { Array(pending.keys) }
    func cancel(_ ids: [String]) { for id in ids { pending.removeValue(forKey: id) } }
}


extension ScheduleStoreTests {
    func testChangingPetUpdatesExistingReminderAndPersistsAppearance() async throws {
        let notifications = TestReminderNotifications()
        let store = ScheduleStore(defaults: defaults, notifications: notifications)
        let reminder = DailyReminder(title: "Read", hour: 20, minute: 0)
        _ = await store.save(reminder)
        await store.updateAppearance(PetAppearance(name: "Clover", species: "rabbit"))
        XCTAssertEqual(notifications.pending.count, 1)
        XCTAssertEqual(notifications.pending[reminder.notificationID]?.content.userInfo["petName"] as? String, "Clover")
        XCTAssertEqual(notifications.pending[reminder.notificationID]?.content.userInfo["petSpecies"] as? String, "rabbit")
        let loaded = ScheduleStore(defaults: defaults, notifications: notifications)
        XCTAssertEqual(loaded.appearance, PetAppearance(name: "Clover", species: "rabbit"))
        store.clear()
        XCTAssertEqual(store.appearance, PetAppearance())
    }
}
