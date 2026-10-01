import SwiftUI
import UserNotifications

struct ScheduleView: View {
    @EnvironmentObject private var schedules: ScheduleStore
    @State private var editing: DailyReminder?
    @State private var reset = false
    var body: some View {
        List {
            Section {
                Text("Let \(schedules.appearance.name) remind you, every day.").font(.caption)
                Text("Choose a time. No timer needed.").font(.caption2).foregroundStyle(.secondary)
                Button("Add reminder", systemImage: "plus") {
                    editing = DailyReminder(title: "", hour: 9, minute: 0)
                }.disabled(schedules.reminders.count >= DailySchedule.limit || !schedules.storageReadable)
            }
            ForEach(schedules.reminders) { reminder in
                VStack(alignment: .leading, spacing: 6) {
                    Button {
                        editing = reminder
                    } label: {
                        VStack(alignment: .leading) {
                            Text(reminder.title).foregroundStyle(.primary)
                            Text("Every day · \(reminder.timeLabel)").font(.caption).foregroundStyle(.mint)
                            Text(reminder.message).font(.caption2).lineLimit(3)
                            Text(reminder.speechSource=="live" ? "AI voice" : "Local voice").font(.caption2).foregroundStyle(.secondary)
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }.buttonStyle(.plain)
                    Toggle("Enabled", isOn: Binding(get: {
                        schedules.reminders.first(where: { $0.id == reminder.id })?.enabled ?? false
                    }, set: { enabled in
                        var updated = reminder; updated.enabled = enabled
                        Task { _ = await schedules.save(updated) }
                    })).font(.caption2)
                }
            }
            if schedules.reminders.isEmpty && schedules.storageReadable {
                Text("No reminders yet. Add your first daily plan.").font(.caption)
            }
            if !schedules.notice.isEmpty { Text(schedules.notice).font(.caption2).foregroundStyle(.orange) }
            if !schedules.storageReadable { Button("Reset saved reminders", role: .destructive) { reset = true } }
            Text("Times follow this Watch's local time. Allow notifications to receive reminders.").font(.caption2).foregroundStyle(.secondary)
        }
        .navigationTitle("Schedule")
        .disabled(schedules.busy)
        .sheet(item: $editing) { reminder in
            ScheduleEditor(reminder: reminder).environmentObject(schedules)
        }
        .confirmationDialog("Delete all saved schedule reminders?", isPresented: $reset) {
            Button("Reset reminders", role: .destructive) { schedules.clear() }
        }
        .task { await schedules.restore() }
    }
}

struct ScheduleEditor: View {
    @EnvironmentObject private var schedules: ScheduleStore
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State var reminder: DailyReminder
    @State private var confirmDelete = false
    @State private var generating = false
    var exists: Bool { schedules.reminders.contains { $0.id == reminder.id } }
    var body: some View {
        NavigationStack {
            Form {
                TextField("What should we do?", text: $reminder.title)
                HStack {
                    Picker("Hour", selection: $reminder.hour) {
                        ForEach(0..<24, id: \.self) { Text(String(format: "%02d", $0)).tag($0) }
                    }
                    Picker("Minute", selection: $reminder.minute) {
                        ForEach(0..<60, id: \.self) { Text(String(format: "%02d", $0)).tag($0) }
                    }
                }.frame(height: 80)
                Text("Every day at \(reminder.timeLabel)").font(.caption)
                Toggle("Enabled", isOn: $reminder.enabled)
                if !reminder.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    PetReminderCard(message: reminder.message, appearance: schedules.appearance)
                }
                if generating { ProgressView("Writing your pet's reminder…") }
                Button("Save reminder") {
                    generating=true
                    Task {
                        defer { generating=false }
                        guard let prepared=await store.prepareScheduleSpeech(reminder) else { return }
                        reminder=prepared
                        if await schedules.save(prepared) { dismiss() }
                    }
                }.disabled(reminder.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                if !schedules.notice.isEmpty { Text(schedules.notice).font(.caption2).foregroundStyle(.orange) }
                if exists { Button("Delete reminder", role: .destructive) { confirmDelete = true } }
                Button("Cancel") { dismiss() }
            }
            .navigationTitle(exists ? "Edit reminder" : "New reminder")
            .disabled(schedules.busy || generating || store.busy)
            .confirmationDialog("Delete this daily reminder?", isPresented: $confirmDelete) {
                Button("Delete reminder", role: .destructive) { schedules.delete(reminder); dismiss() }
            }
        }.environment(\.locale, Locale(identifier: "en"))
        .onAppear { schedules.notice = "" }
    }
}

struct PetReminderCard: View {
    let message: String
    var appearance = PetAppearance()
    var body: some View {
        VStack(spacing: 8) {
            PetAvatar(species: appearance.species, state: "happy", name: appearance.name).frame(height: 120)
            Text(appearance.name).font(.caption.bold()).foregroundStyle(.mint)
            Text(message).font(.caption).multilineTextAlignment(.center)
                .padding(10).frame(maxWidth: .infinity)
                .background(.mint.opacity(0.15), in: RoundedRectangle(cornerRadius: 14))
        }.accessibilityElement(children: .combine)
    }
}

final class ScheduleNotificationController: WKUserNotificationHostingController<PetReminderCard> {
    private var message = "Hey! Time for your daily plan. I'll keep you company!"
    private var appearance = PetAppearance()
    override var body: PetReminderCard { PetReminderCard(message: message, appearance: appearance) }
    override func didReceive(_ notification: UNNotification) {
        let content = notification.request.content
        message = content.body
        appearance = PetAppearance(name: content.userInfo["petName"] as? String ?? "Mochi", species: content.userInfo["petSpecies"] as? String ?? "cat")
    }
}
