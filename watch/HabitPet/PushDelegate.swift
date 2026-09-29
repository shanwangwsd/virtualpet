import Foundation
import WatchKit

final class PushDelegate: NSObject, WKApplicationDelegate {
    func didRegisterForRemoteNotifications(withDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format:"%02x",$0) }.joined()
        Task { @MainActor in
            let api=APIClient()
            guard api.credentials != nil else { return }
            do {
                try await api.empty("api/devices/",method:"POST",body:JSONSerialization.data(withJSONObject:["token":token]))
                UserDefaults.standard.set(token,forKey:"apnsToken")
            } catch { UserDefaults.standard.set("推送注册失败，请稍后重试",forKey:"apnsStatus") }
        }
    }
    func didFailToRegisterForRemoteNotificationsWithError(_ error: Error) {
        UserDefaults.standard.set(error.localizedDescription,forKey:"apnsStatus")
    }
}
