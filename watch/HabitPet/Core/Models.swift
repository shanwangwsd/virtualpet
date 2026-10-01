import Foundation

public struct Pet: Codable, Equatable {
    public var name: String
    public var generation: Int
    public var hunger: Int
    public var hydration: Int
    public var energy: Int
    public var mood: Int
    public var bond: Int
    public var xp: Int
    public var level: Int
    public var state: String
    public var evolution: String
    public var updatedAt: Date
    public var criticalSince: Date? = nil
    public var lastDecayAt: Date? = nil
    public var waterZeroSince: Date? = nil
    public var restAt: Date? = nil
    public var sleepDeprivedUntil: Date? = nil
    public var fitness: Int? = nil
    public var fitnessStatus: String? = nil
    var fitnessValue: Int { max(0,min(100,fitness ?? 50)) }
    public var species: String? = nil
    public var gender: String? = nil
    public var initialAgeDays: Int? = nil
    public var ageDays: Int? = nil
    public var bornAt: Date? = nil
    public var diedAt: Date? = nil
    public var detailsConfigured: Bool? = nil
    var appearance: PetAppearance { PetAppearance(name: name, species: species ?? "cat") }
    var genderLabel: String {
        switch gender { case "male": return "Male"; case "female": return "Female"; default: return "Unspecified" }
    }
    func currentAgeDays(at date: Date) -> Int {
        guard let birth = bornAt else { return ageDays ?? 0 }
        return max(0, Int((diedAt ?? date).timeIntervalSince(birth) / 86400))
    }
    var xpIntoLevel: Int { xp % 100 }
    var xpUntilNextLevel: Int { 100 - xpIntoLevel }
}
struct PetAppearance: Codable, Equatable, Hashable {
    var name = "Mochi"
    var species = "cat"
}

public struct Inventory: Codable, Equatable { public var food: Int; public var coin: Int; var items: [StockItem]? = nil }
public struct Habit: Codable, Identifiable, Equatable {
    public var id: Int
    public var name: String
    public var category: String
    public var target: Int
    public var unit: String
    public var rewardType: String
    public var rewardAmount: Int
    public var progress: Int
    public var completed: Bool
}
public struct HealthSummary: Codable, Equatable {
    public var stepsObservedAt: Date? = nil
    public var steps: Int
    public var sleepMinutes: Int?
    public var stepReward: Int
    public var fitnessTimezone: String? = nil
    public var fitnessStartedOn: String? = nil
    public var lastStepSettlementDate: String? = nil
    public var lastSleepSettlementDate: String? = nil
    public var sleepDate: String? = nil
    public var sleepPreviewMinutes: Int? = nil
    public var stepDeltaPreview: Int? = nil
    public var sleepDeltaPreview: Int? = nil
    public var sleepSettledToday: Bool? = nil
}
public struct PetMessage: Codable, Equatable {
    public var emotion: String
    public var message: String
    public var suggestedAction: String
    public var urgency: String
    public var source: String
}
public struct PetSession: Codable, Identifiable, Equatable {
    public var id: Int
    public var kind: String
    public var habitId: Int?
    public var startedAt: Date
    public var startSteps: Int
}
public struct Snapshot: Codable, Equatable {
    public var sessions: [PetSession] = []
    public var serverTime: Date
    public var date: String
    public var timezone: String
    public var pet: Pet
    public var inventory: Inventory
    public var habits: [Habit]
    public var health: HealthSummary
    public var waterCount: Int
    public var careBonusClaimed: Bool? = nil
    public var message: PetMessage
    var pendingRewards: [PendingReward]? = nil
    var personality: String? = nil
}
public struct PendingAction: Codable, Identifiable, Equatable {
    public var id: UUID
    public var kind: String
    public var generation: Int
    public var occurredAt: Date
    public var payload: [String: Int]
    public init(kind: String, generation: Int, payload: [String: Int] = [:], now: Date = Date()) {
        self.id = UUID(); self.kind = kind; self.generation = generation
        self.payload = payload; self.occurredAt = now
    }
}
public struct FocusTimer: Codable, Equatable {
    enum CodingKeys: String, CodingKey { case habitID = "habitId"; case goalSeconds, accumulated, runningSince }
    public var habitID: Int
    public var goalSeconds: TimeInterval
    public var accumulated: TimeInterval = 0
    public var runningSince: Date?
    public init(habitID: Int, goalSeconds: TimeInterval, now: Date = Date()) {
        self.habitID = habitID; self.goalSeconds = goalSeconds; self.runningSince = now
    }
    public func remaining(at date: Date) -> TimeInterval {
        max(0, goalSeconds - accumulated - (runningSince.map { max(0, date.timeIntervalSince($0)) } ?? 0))
    }
    public mutating func pause(at date: Date) {
        if let since = runningSince { accumulated += max(0, date.timeIntervalSince(since)); runningSince = nil }
    }
    public mutating func resume(at date: Date) { if runningSince == nil { runningSince = date } }
}
public enum Projection {
    public static func apply(_ actions: [PendingAction], to snapshot: Snapshot, now: Date? = nil) -> Snapshot {
        var result = snapshot
        for action in actions where action.generation == result.pet.generation {
            if now != nil { PetRules.advance(&result.pet,to:action.occurredAt) }
            if result.pet.state == "dead" { continue }
            switch action.kind {
            case "complete", "progress":
                guard let id=action.payload["habit_id"], let index=result.habits.firstIndex(where: { $0.id==id }), !result.habits[index].completed else { continue }
                result.habits[index].progress = action.kind == "complete" ? result.habits[index].target : min(result.habits[index].target,result.habits[index].progress + max(0,action.payload["amount"] ?? 0))
                if result.habits[index].progress >= result.habits[index].target {
                    result.habits[index].completed=true
                    result.pet.bond=min(100,result.pet.bond+1)
                }
            case "use_item":
                guard let id=action.payload["item_id"], let index=result.inventory.items?.firstIndex(where: { $0.id==id && $0.quantity>0 }), let item=result.inventory.items?[index] else { continue }
                if item.category == "food" {
                    guard result.pet.hunger<100 else { continue }
                    result.pet.hunger=min(100,result.pet.hunger+item.effect)
                    result.pet.criticalSince=nil; result.pet.bond=min(100,result.pet.bond+2); result.pet.xp += 5
                    result.inventory.food=max(0,result.inventory.food-1)
                } else {
                    guard result.pet.mood<100 else { continue }
                    result.pet.mood=min(100,result.pet.mood+item.effect)
                }
                result.inventory.items?[index].quantity -= 1
                result.pet.restAt=nil
            case "water":
                result.waterCount += 1
                result.pet.hydration=min(100,result.pet.hydration+20); result.pet.waterZeroSince=nil; result.pet.restAt=nil
            case "rest":
                if result.pet.restAt == nil { result.pet.restAt=action.occurredAt }
            case "wake": result.pet.restAt=nil
            case "claim_reward": result.pendingRewards?.removeAll { $0.id==action.payload["reward_id"] }
            default: break // Complex server-only rewards remain pending, never fabricated locally.
            }
            result.pet.level=result.pet.xp/100+1
        }
        if let now { PetRules.advance(&result.pet,to:now) }
        return result
    }
}

public struct SleepInterval {
    public var start: Date; public var end: Date
    public init(start: Date, end: Date) { self.start=start; self.end=end }
}
public enum SleepMath {
    public static func minutes(_ intervals: [SleepInterval], from start: Date, to end: Date) -> Int {
        let clipped=intervals.map { SleepInterval(start:max(start,$0.start),end:min(end,$0.end)) }.filter { $0.start<$0.end }.sorted { $0.start<$1.start }
        guard var current=clipped.first else { return 0 }
        var total:TimeInterval=0
        for interval in clipped.dropFirst() {
            if interval.start<=current.end { current.end=max(current.end,interval.end) }
            else { total += current.end.timeIntervalSince(current.start); current=interval }
        }
        total += current.end.timeIntervalSince(current.start)
        return Int(total/60)
    }
}
public enum Wire {
    public static func decoder() -> JSONDecoder {
        let d = JSONDecoder(); d.keyDecodingStrategy = .convertFromSnakeCase
        d.dateDecodingStrategy = .custom { decoder in
            let text = try decoder.singleValueContainer().decode(String.self)
            let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = f.date(from: text) { return date }
            f.formatOptions = [.withInternetDateTime]
            if let date = f.date(from: text) { return date }
            throw DecodingError.dataCorruptedError(in: try decoder.singleValueContainer(), debugDescription: "Invalid ISO date")
        }
        return d
    }
    public static func encoder() -> JSONEncoder {
        let e = JSONEncoder(); e.keyEncodingStrategy = .convertToSnakeCase; e.dateEncodingStrategy = .iso8601
        return e
    }
}
