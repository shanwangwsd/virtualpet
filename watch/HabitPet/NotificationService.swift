import Foundation
import UserNotifications

@MainActor enum NotificationService {
    static func authorize() async throws {
        _ = try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound])
    }
    static func focus(seconds: TimeInterval) async throws {
        cancelFocus()
        guard seconds > 0 else { return }
        let content = UNMutableNotificationContent(); content.title = "Mochi 学习时间"; content.body = "这段专注结束了，回来确认完成吧。"; content.sound = .default
        let request = UNNotificationRequest(identifier: "focus", content: content, trigger: UNTimeIntervalNotificationTrigger(timeInterval: max(1, seconds), repeats: false))
        try await UNUserNotificationCenter.current().add(request)
    }
    static func cancelFocus() { UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: ["focus"]) }
    static func daily(hour: Int) async throws {
        let content = UNMutableNotificationContent(); content.title = "Mochi 想和你一起进步"; content.body = "有空时，来看看今天的小目标吧。"
        let trigger = UNCalendarNotificationTrigger(dateMatching: DateComponents(hour: hour), repeats: true)
        try await UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: "daily", content: content, trigger: trigger))
    }
    static func clear() { UNUserNotificationCenter.current().removeAllPendingNotificationRequests() }
}
