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
                PetAvatar(hungry:false,dead:false).frame(height:80)
                Text("HabitPet").font(.title3.bold())
                Text("你的好习惯，TA的小日子").font(.caption2).foregroundStyle(.secondary)
                TextField("服务器 HTTPS 地址",text:$server).textInputAutocapitalization(.never)
                TextField("用户名",text:$username).textInputAutocapitalization(.never)
                SecureField("密码",text:$password)
                Toggle("创建新账号",isOn:$register)
                Button(register ? "开始陪伴" : "登录") { Task { await store.login(url:server,username:username,password:password,register:register) } }.disabled(store.busy)
                Text(store.notice).font(.caption2).foregroundStyle(.orange)
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
                VStack(spacing:12) {
                    if let snapshot=store.display {
                        HStack { Text(snapshot.pet.name).font(.headline); Spacer(); Text("Lv.\(snapshot.pet.level)").foregroundStyle(.mint) }
                        PetAvatar(hungry:snapshot.pet.hunger<40,dead:snapshot.pet.state=="dead",emotion:(store.reply ?? snapshot.message).emotion).frame(height:100)
                        Text("第 \(snapshot.pet.generation) 代 · \(snapshot.pet.evolution)").font(.caption2).foregroundStyle(.secondary)
                        meter("饱腹",value:snapshot.pet.hunger,color:.orange)
                        meter("饮水",value:snapshot.pet.hydration,color:.cyan)
                        meter("精力",value:snapshot.pet.energy,color:.yellow)
                        meter("心情",value:snapshot.pet.mood,color:.pink)
                        Text("❤️ \(snapshot.pet.bond)  ·  🍖 \(snapshot.inventory.food)  ·  🪙 \(snapshot.inventory.coin)").font(.caption2)
                        Text((store.reply ?? snapshot.message).message).font(.caption).multilineTextAlignment(.center)
                        if snapshot.pet.state=="dead" {
                            Text("这一代的回忆已经保存。").font(.caption)
                            Button("迎接新一代") { Task { await store.action("rebirth") } }
                        } else {
                            Button("🍖 喂食") { Task { await store.action("feed") } }.disabled(snapshot.inventory.food<1 || snapshot.pet.hunger>=100)
                            HStack {
                                Button("💧 喝水") { Task { await store.action("water") } }
                                Button("✨ 互动") { Task { await store.action("play") } }
                            }
                        }
                        Text("最近同步：\(snapshot.serverTime, style: .relative)前").font(.caption2).foregroundStyle(.secondary)
                        if store.isOfflineEstimate { Text("待同步 \(store.local.pending.count) 项 · 数值为临时预览").font(.caption2).foregroundStyle(.orange) }
                        if store.blocked {
                            Text("首个操作有冲突，后续操作尚未提交。").font(.caption2)
                            Button("放弃首个操作",role:.destructive) { confirmDiscard=true }
                        }
                        NavigationLink("📚 今日习惯") { HabitsView() }
                        NavigationLink("🚶 活动与健康") { HealthView() }
                        NavigationLink("💬 和 Mochi 聊聊") { ChatView() }
                        NavigationLink("📖 日记与记忆") { JournalView() }
                        NavigationLink("⚙️ 设置") { SettingsView() }
                    } else { Text("正在准备今天的陪伴…") }
                    Button("刷新 / 重试同步") { Task { await store.refresh() } }
                    if store.busy { ProgressView() }
                    Text(store.notice).font(.caption2).foregroundStyle(.secondary)
                }.padding(.horizontal,8)
            }.disabled(store.busy)
            .task { if store.local.snapshot == nil { await store.refresh() } }
            .confirmationDialog("放弃后不会获得此操作的奖励；后续操作可能需要重新检查。",isPresented:$confirmDiscard) {
                Button("确认放弃",role:.destructive) { Task { await store.discardFirst() } }
            }
        }
    }
    func meter(_ title:String,value:Int,color:Color) -> some View {
        HStack { Text(title).font(.caption2).frame(width:28); ProgressView(value:Double(value),total:100).tint(color); Text("\(value)").font(.caption2.monospacedDigit()).frame(width:24) }
    }
}

struct PetAvatar: View {
    let hungry: Bool
    let dead: Bool
    var emotion: String = "happy"
    @State private var float = false
    var body: some View {
        ZStack {
            Ellipse().fill(.mint.opacity(0.12)).frame(width:90,height:15).offset(y:43)
            ZStack {
                RoundedRectangle(cornerRadius:42).fill(LinearGradient(colors:dead ? [.gray,.gray.opacity(0.5)] : [.mint.opacity(0.95),.teal],startPoint:.topLeading,endPoint:.bottomTrailing)).frame(width:93,height:83)
                HStack(spacing:25) { eye; eye }.offset(y:-5)
                Capsule().fill(.black.opacity(0.7)).frame(width:hungry ? 14:22,height:hungry ? 9:4).offset(y:15)
                HStack(spacing:44) { Circle().fill(.pink.opacity(0.55)); Circle().fill(.pink.opacity(0.55)) }.frame(width:66,height:11).offset(y:8)
                Text(dead ? "✦" : emotion == "sleepy" ? "💤" : emotion == "excited" ? "✨" : "🌱").offset(y:-44)
            }.offset(y:float && !dead ? -4:3)
        }.onAppear { withAnimation(.easeInOut(duration:1.7).repeatForever(autoreverses:true)) { float=true } }
        .accessibilityLabel(dead ? "宠物已离世" : hungry ? "饥饿的 Mochi" : "开心的 Mochi")
    }
    var eye: some View { Capsule().fill(.black.opacity(0.8)).frame(width:dead ? 12:6,height:(dead || emotion == "sleepy") ? 3:10) }
}

struct HabitsView: View {
    @EnvironmentObject var store: AppStore
    var body: some View {
        List {
            if store.local.focus != nil { NavigationLink("⏱ 当前专注") { FocusView() } }
            ForEach(store.display?.habits ?? []) { habit in
                NavigationLink {
                    VStack(spacing:12) {
                        Text(habit.name).font(.headline)
                        Text("\(habit.progress) / \(habit.target) \(habit.unit)")
                        if habit.completed { Label("今日已完成",systemImage:"checkmark.circle.fill").foregroundStyle(.mint) }
                        else {
                            Button("开始专注") { Task { await store.startFocus(habit) } }.disabled(store.local.focus != nil)
                            NavigationLink("查看计时器") { FocusView() }
                            Button("手动确认完成") { Task { await store.action("complete",payload:["habit_id":habit.id]) } }
                        }
                    }
                } label: { VStack(alignment:.leading) { Text(habit.name); Text(habit.completed ? "✓ 完成" : "\(habit.progress)/\(habit.target)").font(.caption2).foregroundStyle(.secondary) } }
            }
            NavigationLink("＋ 创建习惯") { NewHabitView() }
        }.navigationTitle("今日习惯").disabled(store.busy)
    }
}
struct NewHabitView: View {
    @EnvironmentObject var store:AppStore
    @State private var name=""
    @State private var target=30
    @State private var category="study"
    var body:some View {
        Form {
            TextField("习惯名称",text:$name)
            Stepper("\(target) 分钟",value:$target,in:5...180,step:5)
            Picker("类别",selection:$category) { Text("学习").tag("study"); Text("阅读").tag("reading"); Text("工作").tag("work"); Text("运动").tag("exercise") }
            Text("完成奖励：食物 ×1").font(.caption2)
            Button("保存") { Task { await store.createHabit(name:name,target:target,category:category) } }.disabled(name.trimmingCharacters(in:.whitespaces).isEmpty || store.busy)
            Text(store.notice).font(.caption2)
        }
    }
}
struct FocusView:View {
    @EnvironmentObject var store:AppStore
    var body:some View {
        VStack(spacing:10) {
            Text("和 Mochi 一起专注").font(.headline)
            if let timer=store.local.focus {
                TimelineView(.periodic(from:.now,by:1)) { timeline in
                    let remaining=Int(timer.remaining(at:timeline.date))
                    Text(String(format:"%02d:%02d",remaining/60,remaining%60)).font(.system(size:34,design:.rounded).monospacedDigit())
                    if remaining==0 { Button("确认完成并领奖") { Task { await store.finishFocus() } } }
                }
                Button(timer.runningSince == nil ? "继续" : "暂停") { Task { await store.toggleFocus() } }
                Button("取消",role:.destructive) { store.cancelFocus() }
            } else { Text("从习惯列表选择一项开始。").font(.caption) }
        }.disabled(store.busy)
    }
}
struct HealthView:View {
    @EnvironmentObject var store:AppStore
    var body:some View {
        ScrollView { VStack(spacing:12) {
            Text("一起照顾自己").font(.headline)
            if store.display?.health.stepsObservedAt != nil { Text("步数：\(store.display?.health.steps ?? 0)") }
            else { Text("步数：暂无可读数据") }
            if let minutes=store.display?.health.sleepMinutes { Text("睡眠：\(minutes/60) 小时 \(minutes%60) 分钟") }
            else { Text("睡眠：暂无数据") }
            Text("睡眠采用昨天中午至今天中午的窗口，不作医学判断。").font(.caption2).foregroundStyle(.secondary)
            Button("授权并同步健康摘要") { Task { await store.syncHealth() } }
            Button("开始遛宠物") { Task { if await store.syncHealth() { await store.action("walk_start") } } }
            Button("同步步数并完成散步") { Task { if await store.syncHealth() { await store.action("walk_finish") } } }
            ForEach(store.display?.sessions ?? []) { session in
                Button("取消未结束的 \(session.kind)",role:.destructive) { Task { await store.cancelSession(session.id) } }
            }
            Text("散步至少新增 1000 步；每日奖励一次。").font(.caption2)
            Text(store.notice).font(.caption2)
        }}.disabled(store.busy)
    }
}
struct ChatView:View {
    @EnvironmentObject var store:AppStore
    @State private var text=""
    var body:some View {
        ScrollView { VStack(spacing:12) {
            TextField("对 Mochi 说…",text:$text)
            Button("发送") { Task { await store.chat(text) } }.disabled(text.isEmpty || store.busy)
            if let reply=store.reply {
                Text(reply.message).font(.body)
                Text(reply.source == "live" ? "AI 回复" : reply.source == "demo" ? "演示模式 · 未调用模型" : "离线规则回复").font(.caption2).foregroundStyle(.secondary)
                if reply.suggestedAction == "feed" { Button("喂食") { Task { await store.action("feed") } } }
                if reply.suggestedAction == "water" { Button("喝水打卡") { Task { await store.action("water") } } }
                if reply.suggestedAction == "habits" { NavigationLink("查看习惯") { HabitsView() } }
            }
            Text("开启长期记忆后，可说“记住：我喜欢晚饭后学习”。").font(.caption2)
            Text(store.notice).font(.caption2)
        }}
    }
}
struct JournalView:View {
    @EnvironmentObject var store:AppStore
    var body:some View {
        List {
            Button("生成今天的日记") { Task { await store.generateDiary() } }
            Section("日记") { ForEach(store.diaries) { diary in VStack(alignment:.leading) { Text(diary.date).font(.caption2); Text(diary.response.message) } } }
            Section("长期记忆") { ForEach(store.memories) { memory in VStack(alignment:.leading) { Text(memory.content); Button("删除",role:.destructive) { Task { await store.deleteMemory(memory.id) } } } } }
            Section("提醒") { ForEach(store.reminders) { reminder in Text(reminder.response.message) } }
        }.task { await store.loadExtras() }.disabled(store.busy)
    }
}
struct SettingsView:View {
    @EnvironmentObject var store:AppStore
    @State private var deleteAccount=false
    @State private var confirmLogout=false
    var body:some View {
        Form {
            if let profile=store.profile {
                Toggle("允许 AI 使用健康摘要",isOn:Binding(get:{store.profile?.aiHealthConsent ?? false},set:{ value in var p=profile;p.aiHealthConsent=value;Task { await store.saveProfile(p) }}))
                Toggle("长期记忆",isOn:Binding(get:{store.profile?.memoryEnabled ?? false},set:{ value in var p=profile;p.memoryEnabled=value;Task { await store.saveProfile(p) }}))
                Picker("性格",selection:Binding(get:{store.profile?.personality ?? "playful"},set:{value in var p=profile;p.personality=value;Task { await store.saveProfile(p) }})) {
                    Text("俏皮").tag("playful");Text("温柔").tag("gentle");Text("傲娇").tag("tsundere");Text("活力").tag("energetic");Text("安静").tag("calm")
                }
                Text("服务器时区：\(profile.timezone)").font(.caption2)
            }
            Button("授权通知，每天 19 点提醒") { Task { do { try await NotificationService.authorize();try await NotificationService.daily(hour:19) } catch { store.notice=error.localizedDescription } } }
            Button("注册远程提醒（需服务器配置）") {
                WKApplication.shared().registerForRemoteNotifications()
            }
            Button("关闭本地通知") { NotificationService.clear() }
            Text("日记和记忆可包含个人信息；关闭记忆不会删除已有内容，请在记忆页面删除。").font(.caption2)
            Button("退出登录") { confirmLogout=true }
            Button("删除账号及所有云端数据",role:.destructive) { deleteAccount=true }
            Text(store.notice).font(.caption2)
        }.task { await store.loadExtras() }.disabled(store.busy)
        .confirmationDialog("退出会清除本地数据及未同步操作。",isPresented:$confirmLogout) { Button("确认退出",role:.destructive) { Task { await store.logout() } } }
        .confirmationDialog("永久删除账号、宠物、健康摘要和记忆，无法撤销。",isPresented:$deleteAccount) { Button("永久删除",role:.destructive) { Task { await store.logout(deleteAccount:true) } } }
    }
}
