import SwiftUI
import WatchKit

@main struct HabitPetApp: App {
    @WKApplicationDelegateAdaptor(PushDelegate.self) var pushDelegate
    @StateObject private var store = AppStore()
    @StateObject private var schedules = ScheduleStore()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            Group {
                if store.authenticated { HomeView() } else { LoginView() }
            }
            .environmentObject(store)
            .environmentObject(schedules)
            .overlay {
                if store.authenticated, let action=store.actionVisual, let pet=store.display?.pet, pet.state != "dead" {
                    CareActionOverlay(pet:pet,action:action).environmentObject(store)
                }
            }
            .task(id: store.local.snapshot?.pet.appearance) {
                if store.authenticated, let appearance = store.local.snapshot?.pet.appearance {
                    await schedules.updateAppearance(appearance)
                }
            }
            .task { if store.authenticated { await schedules.restore() } }
            .onChange(of: store.authenticated) { _, authenticated in
                if !authenticated { schedules.clear() }
            }
            .environment(\.locale, Locale(identifier: "en"))
            .tint(.mint)
            .onChange(of: scenePhase) { _, phase in
                if phase == .active && store.authenticated {
                    Task {
                        await store.refresh()
                        if store.authenticated {
                            await schedules.restore()
                        }
                    }
                }
            }
        }
        WKNotificationScene(
            controller: ScheduleNotificationController.self,
            category: DailyReminder.category
        )
    }
}
