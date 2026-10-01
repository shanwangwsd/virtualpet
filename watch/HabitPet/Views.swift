import SwiftUI
import WatchKit

struct LoginView: View {
    @EnvironmentObject var store: AppStore
    @AppStorage("serverURL") private var server = "https://your-server.example"
    @State private var username = ""
    @State private var password = ""
    @State private var register = false
    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                Text("HabitPet").font(.title3.bold())
                Text("Your habits. Their little world.").font(.caption2).foregroundStyle(.secondary)
                TextField("Server HTTPS URL",text:$server).textInputAutocapitalization(.never)
                TextField("Username",text:$username).textInputAutocapitalization(.never)
                SecureField("Password",text:$password)
                Toggle("Create account",isOn:$register)
                Button(register ? "Get started" : "Sign in") { Task { await store.login(url:server,username:username,password:password,register:register) } }.disabled(store.busy)
                if let message=store.statusMessage { Text(message).font(.caption2).foregroundStyle(.orange) }
            }.padding()
        }
    }
}

struct HomeView: View {
    @EnvironmentObject var store: AppStore
    @State private var confirmDiscard = false
    var body: some View {
        NavigationStack {
            ScrollView {
                TimelineView(.periodic(from:.now,by:60)) { timeline in
                VStack(spacing:12) {
                    if let snapshot=store.projected(at:timeline.date) {
                        HStack { Text(snapshot.pet.name).font(.headline); Spacer(); Text("Lv.\(snapshot.pet.level)").foregroundStyle(.mint) }
                        PetAvatar(species:snapshot.pet.appearance.species,state:PetRules.imageState(snapshot.pet,action:store.actionVisual),name:snapshot.pet.name).frame(height:120)
                        Text("\(snapshot.pet.currentAgeDays(at:timeline.date)) days old").font(.caption2).foregroundStyle(.secondary)
                        NavigationLink("My pet") { PetDetailsView(pet: snapshot.pet) }
                        meter("Fullness",value:snapshot.pet.hunger,color:.orange)
                        meter("Water",value:snapshot.pet.hydration,color:.cyan)
                        meter("Fitness",value:snapshot.pet.fitnessValue,color:.green)
                        meter("Energy",value:snapshot.pet.energy,color:.purple)
                        meter("Mood",value:snapshot.pet.mood,color:.pink)
                        HStack {
                            NavigationLink("Food") { InventoryView(category:"food") }
                            NavigationLink("Toys") { InventoryView(category:"toy") }
                        }
                        if !(snapshot.pendingRewards ?? []).isEmpty { NavigationLink("Choose reward (\(snapshot.pendingRewards!.count))") { RewardsView() } }
                        Text(store.careMessage ?? snapshot.message.message).font(.caption).multilineTextAlignment(.center)
                        if snapshot.pet.state=="dead" {
                            Text("This generation's history is saved.").font(.caption)
                            Button("New pet") { Task { await store.action("rebirth") } }.disabled(store.local.pending.contains { $0.kind=="rebirth" })
                        } else {

                            Button("Drink") { Task { await store.action("water") } }.disabled(snapshot.pet.hydration>=100)
                        }
                        if snapshot.pet.state != "dead" { Button(snapshot.pet.restAt == nil ? "Rest" : "Wake up") { Task { await store.action(snapshot.pet.restAt == nil ? "rest" : "wake") } } }
                        if store.isOfflineEstimate { Text("\(store.local.pending.count) pending · Estimated stats").font(.caption2).foregroundStyle(.orange) }
                        if store.blocked {
                            Text("The first action has a conflict. Later actions are waiting.").font(.caption2)
                            Button("Discard first action",role:.destructive) { confirmDiscard=true }
                        }
                        NavigationLink("Schedule") { ScheduleView() }
                        NavigationLink("Habits") { HabitsView() }
                        NavigationLink("Activity & Health") { HealthView() }
                        NavigationLink("Settings") { SettingsView() }
                    } else { Text("Getting ready for today...") }
                    Button("Sync") { Task { await store.refresh() } }.disabled(store.syncing)
                    if store.syncing { Label("Syncing", systemImage: "arrow.triangle.2.circlepath").font(.caption2) }
                    if store.busy { ProgressView() }
                    if let message=store.statusMessage { Text(message).font(.caption2).foregroundStyle(.secondary) }
                }.padding(.horizontal,8)
                }
            }
            .task { await store.refresh() }
            .confirmationDialog("Discard this action without its reward? Later actions may need review.",isPresented:$confirmDiscard) {
                Button("Discard action",role:.destructive) { Task { await store.discardFirst() } }
            }
        }
    }
    func meter(_ title:String,value:Int,color:Color) -> some View {
        HStack { Text(title).font(.caption2).frame(width:48, alignment:.leading); ProgressView(value:Double(max(0,min(100,value))),total:100).tint(color); Text("\(value)").font(.caption2.monospacedDigit()).frame(width:24) }
    }
}

struct HabitsView: View {
    @EnvironmentObject var store: AppStore
    var body: some View {
        List {
            if store.local.focus != nil { NavigationLink("Current focus") { FocusView() } }
            ForEach(store.display?.habits ?? []) { habit in
                NavigationLink { HabitDetailView(habitID:habit.id) } label: {
                    VStack(alignment:.leading) {
                        Text(habit.name)
                        Text(habit.completed ? "Done" : "\(habit.progress)/\(habit.target)").font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
            NavigationLink("New habit") { NewHabitView() }
        }.navigationTitle("Habits").disabled(store.busy)
    }
}
struct HabitDetailView: View {
    @EnvironmentObject var store: AppStore
    let habitID:Int
    @State private var showRewards=false
    @State private var showFocus=false
    var body:some View {
        ScrollView {
            VStack(spacing:12) {
                if let habit=store.display?.habits.first(where: { $0.id==habitID }) {
                    Text(habit.name).font(.headline)
                    Text("\(habit.progress) / \(habit.target) \(habit.unit)")
                    if habit.completed {
                        Label("Done",systemImage:"checkmark.circle.fill").foregroundStyle(.mint)
                        NavigationLink("Choose reward") { RewardsView(habitID:habitID) }
                    } else {
                        Button("Complete & choose reward") {
                            Task { if await store.action("complete",payload:["habit_id":habitID]) { showRewards=true } }
                        }
                        Button("Start focus") {
                            Task { await store.startFocus(habit); showFocus=store.local.focus?.habitID==habitID }
                        }.disabled(store.local.focus != nil)
                    }
                } else { Text("Habit unavailable.") }
                if let message=store.statusMessage { Text(message).font(.caption2) }
            }.padding(.horizontal,8)
        }.disabled(store.busy)
        .navigationDestination(isPresented:$showRewards) { RewardsView(habitID:habitID) }
        .navigationDestination(isPresented:$showFocus) { FocusView() }
    }
}
struct NewHabitView: View {
    @EnvironmentObject var store:AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var name=""
    @State private var target=30
    @State private var category="study"
    var body:some View {
        Form {
            TextField("Habit name",text:$name)
            Stepper("\(target) minutes",value:$target,in:5...180,step:5)
            Picker("Category",selection:$category) { Text("Study").tag("study"); Text("Reading").tag("reading"); Text("Work").tag("work"); Text("Exercise").tag("exercise") }
            Text("Choose Food or Toy after completion.").font(.caption2)
            Button("Save") { Task { if await store.createHabit(name:name,target:target,category:category) { dismiss() } } }.disabled(name.trimmingCharacters(in:.whitespaces).isEmpty || store.busy)
            if let message=store.statusMessage { Text(message).font(.caption2) }
        }
    }
}
struct FocusView:View {
    @EnvironmentObject var store:AppStore
    @State private var showRewards=false
    @State private var rewardHabitID:Int?
    var body:some View {
        VStack(spacing:10) {
            Text("Focus with \(store.display?.pet.name ?? "your pet")").font(.headline)
            if let timer=store.local.focus {
                TimelineView(.periodic(from:.now,by:1)) { timeline in
                    let remaining=Int(timer.remaining(at:timeline.date))
                    Text(String(format:"%02d:%02d",remaining/60,remaining%60)).font(.system(size:34,design:.rounded).monospacedDigit())
                    if remaining==0 { Button("Finish & choose reward") {
                        Task { rewardHabitID=timer.habitID; if await store.finishFocus() { showRewards=true } }
                    } }
                }
                Button(timer.runningSince == nil ? "Resume" : "Pause") { Task { await store.toggleFocus() } }
                Button("Cancel",role:.destructive) { store.cancelFocus() }
            } else { Text("Choose a habit to get started.").font(.caption) }
        }.disabled(store.busy)
        .navigationDestination(isPresented:$showRewards) { RewardsView(habitID:rewardHabitID) }
    }
}
struct HealthView:View {
    @EnvironmentObject var store:AppStore
    func change(_ delta:Int?) -> String {
        guard let delta else { return "No available data · No penalty" }
        return "Estimate: \(delta >= 0 ? "+" : "")\(delta) Fitness"
    }
    var body:some View {
        ScrollView { VStack(alignment:.leading,spacing:12) {
            Text("Activity & Health").font(.headline)
            if let snapshot=store.display {
                Text("Fitness \(snapshot.pet.fitnessValue) / 100 · \(snapshot.pet.fitnessStatus?.capitalized ?? "Normal")").font(.caption)
                Divider()
                Text("Today's steps").font(.headline)
                Text(store.currentStepPreview.map { "\($0) steps" } ?? "No available data")
                Text(change(store.currentStepPreview.map(FitnessRules.steps))).font(.caption2).foregroundStyle(.mint)
                Text("Local preview. Steps settle after the day ends when synced.").font(.caption2).foregroundStyle(.secondary)
                Divider()
                Text("Latest main sleep").font(.headline)
                if let minutes=store.healthPreview?.sleepMinutes ?? snapshot.health.sleepMinutes {
                    Text("\(minutes/60)h \(minutes%60)m")
                    Text(store.healthPreview?.sleepMinutes != nil ? store.healthPreview!.date : snapshot.health.sleepDate ?? "").font(.caption2)
                } else { Text("No available sleep data") }
                Text(change(store.currentSleepPreview.map(FitnessRules.sleep))).font(.caption2).foregroundStyle(.mint)
                if snapshot.health.sleepSettledToday == true { Text("Settled today.").font(.caption2) }
                NavigationLink("Details") {
                    VStack(alignment:.leading,spacing:12) {
                    Text("Sleep window: 6 PM–noon. Missing data has no penalty.").font(.caption2)
                    Text("Steps settled: \(snapshot.health.lastStepSettlementDate ?? "Not yet")").font(.caption2)
                    Text("Sleep settled: \(snapshot.health.lastSleepSettlementDate ?? "Not yet")").font(.caption2)
                    Text(snapshot.health.fitnessTimezone ?? snapshot.timezone).font(.caption2)
                    }.padding().navigationTitle("Health details")
                }
            }
            Button(store.healthConnected ? "Sync Health" : "Connect Health") { Task { await store.syncHealth() } }.disabled(store.busy || store.syncing)
            if store.syncing { Text("Syncing…").font(.caption2) }
            if let message=store.statusMessage { Text(message).font(.caption2).foregroundStyle(.orange) }
        }.padding(.horizontal,8) }
        .task {
            while !Task.isCancelled {
                if store.healthConnected { await store.refresh() }
                do { try await Task.sleep(nanoseconds:30_000_000_000) } catch { break }
            }
        }
    }
}
struct SettingsView:View {
    @EnvironmentObject private var schedules: ScheduleStore
    @EnvironmentObject var store:AppStore
    @State private var deleteAccount=false
    @State private var confirmLogout=false
    var body:some View {
        Form {
            if let profile=store.profile {
                Toggle("Share health with AI",isOn:Binding(get:{store.profile?.aiHealthConsent ?? false},set:{ value in var p=profile;p.aiHealthConsent=value;Task { await store.saveProfile(p) }}))
            }
            NavigationLink("Connection") {
                VStack(alignment:.leading,spacing:12) {
                if let profile=store.profile { Text(profile.timezone).font(.caption2) }
                if let address=store.api.credentials?.baseURL { Text(address).font(.caption2) }
                }.padding().navigationTitle("Connection")
            }
            Button("Enable remote reminders") {
                Task {
                    do { try await NotificationService.authorize(); WKApplication.shared().registerForRemoteNotifications() }
                    catch { store.notice="Notifications are off. Enable them in Watch settings." }
                }
            }
            Button("Turn off local notifications") { schedules.disableAll(); NotificationService.clear() }
                .disabled(schedules.busy)
            Button("Sign out") { confirmLogout=true }
            Button("Delete account",role:.destructive) { deleteAccount=true }
            if let message=store.statusMessage { Text(message).font(.caption2) }
        }.task { await store.loadProfile() }.disabled(store.busy)
        .confirmationDialog("Signing out removes local data and unsynced actions.",isPresented:$confirmLogout) { Button("Sign out",role:.destructive) { Task { await store.logout() } } }
        .confirmationDialog("Permanently delete your account, pets, and health summaries? This cannot be undone.",isPresented:$deleteAccount) { Button("Delete permanently",role:.destructive) { Task { await store.logout(deleteAccount:true) } } }
    }
}
