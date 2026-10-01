import Foundation
import UserNotifications

struct DailyReminder: Codable, Equatable, Identifiable {
    static let category = "PET_SCHEDULE"
    static let prefix = "schedule."
    var id = UUID()
    var title: String
    var hour: Int
    var minute: Int
    var enabled = true
    var generatedSpeech: String? = nil
    var generatedForTitle: String? = nil
    var voicePersonality: String? = nil
    var generatedForPersonality: String? = nil
    var speechSource: String? = nil

    var notificationID: String { Self.prefix + id.uuidString }
    var timeLabel: String { String(format: "%02d:%02d", hour, minute) }
    var message: String {
        if generatedForTitle==title.trimmingCharacters(in:.whitespacesAndNewlines),
           generatedForPersonality==voicePersonality, let generatedSpeech, !generatedSpeech.isEmpty { return generatedSpeech }
        switch voicePersonality {
        case "tsundere": return "Hmph! Time for \(title). Show me what you've got!"
        case "gentle": return "Time for \(title). One little step; I'm here with you."
        case "energetic": return "Let's go! It's time for \(title). You've got this!"
        case "calm": return "Time for \(title). Settle in and begin."
        default: return "Hey! Time for \(title). I'll keep you company!"
        }
    }

    func validated() throws -> Self {
        var value = self
        value.title = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.title.isEmpty, value.title.count <= 80 else { throw ScheduleError.invalidTitle }
        guard (0..<24).contains(hour), (0..<60).contains(minute) else { throw ScheduleError.invalidTime }
        return value
    }

    func notificationRequest(appearance: PetAppearance = PetAppearance()) throws -> UNNotificationRequest {
        let value = try validated()
        let content = UNMutableNotificationContent()
        content.title = "\(appearance.name)'s reminder"
        content.body = value.message
        content.categoryIdentifier = Self.category
        content.sound = .default
        content.userInfo = ["reminderID": id.uuidString, "task": value.title, "petName": appearance.name, "petSpecies": appearance.species]
        // No fixed date or zone: repeat at the device's local wall-clock time.
        let trigger = UNCalendarNotificationTrigger(dateMatching: DateComponents(hour: hour, minute: minute), repeats: true)
        return UNNotificationRequest(identifier: notificationID, content: content, trigger: trigger)
    }
}

enum ScheduleError: LocalizedError {
    case invalidTitle, invalidTime, limitReached, permissionDenied, unreadableStorage
    var errorDescription: String? {
        switch self {
        case .invalidTitle: return "Enter a reminder of 1–80 characters."
        case .invalidTime: return "Choose a valid hour and minute."
        case .limitReached: return "You can save up to 30 reminders. Remove one to add another."
        case .permissionDenied: return "Notifications are off. Enable HabitPet notifications in Settings, then try again."
        case .unreadableStorage: return "Saved reminders could not be read. Reset them to create a new schedule."
        }
    }
}

enum DailySchedule {
    // Leave room for focus, daily, and other system notification requests.
    static let limit = 30
    static func upserting(_ reminder: DailyReminder, into reminders: [DailyReminder]) throws -> [DailyReminder] {
        let value = try reminder.validated()
        var result = reminders
        if let index = result.firstIndex(where: { $0.id == value.id }) { result[index] = value }
        else {
            guard result.count < limit else { throw ScheduleError.limitReached }
            result.append(value)
        }
        return result.sorted {
            if $0.hour != $1.hour { return $0.hour < $1.hour }
            if $0.minute != $1.minute { return $0.minute < $1.minute }
            return $0.id.uuidString < $1.id.uuidString
        }
    }
    static func cancellations(reminders: [DailyReminder], pending: [String]) -> [String] {
        let active = Set(reminders.filter(\.enabled).map(\.notificationID))
        return pending.filter { $0.hasPrefix(DailyReminder.prefix) && !active.contains($0) }
    }
}

struct ScheduleSpeechReply: Decodable {
    let message: String
    let source: String
    let personality: String
}
