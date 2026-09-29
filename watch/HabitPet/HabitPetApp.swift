import SwiftUI
import WatchKit

@main struct HabitPetApp: App {
    @WKApplicationDelegateAdaptor(PushDelegate.self) var pushDelegate
    @StateObject private var store = AppStore()
    @Environment(\.scenePhase) private var scenePhase
    var body: some Scene {
        WindowGroup {
            Group {
                if store.authenticated { HomeView() } else { LoginView() }
            }
            .environmentObject(store)
            .tint(.mint)
            .onChange(of: scenePhase) { phase in
                if phase == .active && store.authenticated { Task { await store.refresh() } }
            }
        }
    }
}
