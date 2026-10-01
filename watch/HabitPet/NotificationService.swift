import Foundation
import UserNotifications

@MainActor enum NotificationService {
    static func authorize() async throws {
        guard try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) else { throw APIError(status:0,detail:"Notifications are off.") }
    }
    static func focus(seconds: TimeInterval) async throws {
        cancelFocus()
        guard seconds > 0 else { return }
        let content = UNMutableNotificationContent(); content.title = "Focus time with Mochi"; content.body = "Your focus session is over. Come back to mark it complete."; content.sound = .default
        let request = UNNotificationRequest(identifier: "focus", content: content, trigger: UNTimeIntervalNotificationTrigger(timeInterval: max(1, seconds), repeats: false))
        try await UNUserNotificationCenter.current().add(request)
    }
    static func cancelFocus() { UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: ["focus"]) }
    static func clear() { UNUserNotificationCenter.current().removeAllPendingNotificationRequests() }
}
