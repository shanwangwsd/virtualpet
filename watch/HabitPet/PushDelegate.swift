import Foundation
import WatchKit
import UserNotifications

final class PushDelegate: NSObject, WKApplicationDelegate, UNUserNotificationCenterDelegate {
    func applicationDidFinishLaunching() {
        UNUserNotificationCenter.current().delegate = self
    }
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }
    func didRegisterForRemoteNotifications(withDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format:"%02x",$0) }.joined()
        Task { @MainActor in
            let api=APIClient()
            guard api.credentials != nil else { return }
            do {
                try await api.empty("api/devices/",method:"POST",body:JSONSerialization.data(withJSONObject:["token":token]))
                UserDefaults.standard.set(token,forKey:"apnsToken")
            } catch { UserDefaults.standard.set("Remote notification registration failed. Please try again.",forKey:"apnsStatus") }
        }
    }
    func didFailToRegisterForRemoteNotificationsWithError(_ error: Error) {
        UserDefaults.standard.set("Remote notification registration failed. Please try again.",forKey:"apnsStatus")
    }
}
