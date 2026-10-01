import Foundation

struct CatalogPet: Codable, Identifiable { let id: String; let name: String; let states: [String:String] }
struct CatalogItem: Codable, Identifiable { let id: Int; let key: String; let name: String; let category: String; let effect: Int; let asset: String }
struct PetCatalog: Codable {
    let pets: [CatalogPet]
    let items: [CatalogItem]
    static let shared: PetCatalog = {
        guard let url=Bundle.main.url(forResource:"catalog",withExtension:"json",subdirectory:"Assets"),
              let data=try? Data(contentsOf:url), let value=try? JSONDecoder().decode(PetCatalog.self,from:data) else { return PetCatalog(pets:[],items:[]) }
        return value
    }()
    func asset(species:String,state:String) -> String? { pets.first { $0.id==species }?.states[state] }
}
struct StockItem: Codable, Equatable, Identifiable {
    let id: Int
    let key: String
    let name: String
    let category: String
    let effect: Int
    let asset: String
    var quantity: Int
}
struct PendingReward: Codable, Equatable, Identifiable { let id: Int; let name: String; let date: String; var habitId: Int? = nil }
enum RewardFlow {
    static func choices(_ rewards:[PendingReward], habitID:Int?) -> [PendingReward] {
        guard let habitID else { return rewards }
        return rewards.filter { $0.habitId==habitID || $0.habitId==nil }
    }
    static func waiting(_ pending:[PendingAction], habitID:Int?) -> Bool {
        pending.contains { ["complete","focus_finish"].contains($0.kind) && (habitID==nil || $0.payload["habit_id"]==habitID) }
    }
}

enum PetRules {
    static func actionError(_ kind:String, payload:[String:Int], snapshot:Snapshot, pending:[PendingAction]) -> String? {
        if kind == "play" { return "Use a Toy to improve Mood." }
        let pet=snapshot.pet
        if pending.contains(where: { $0.generation==pet.generation && $0.kind=="rebirth" }) { return "Starting your new pet…" }
        if kind=="rebirth" { return pet.state=="dead" ? nil : "Your pet is still here." }
        if pet.state=="dead" { return "Start a new pet first." }
        if kind=="water" && pet.hydration>=100 { return "Water is full." }
        if kind=="claim_reward" {
            guard let id=payload["reward_id"], snapshot.pendingRewards?.contains(where: { $0.id==id })==true,
                  !pending.contains(where: { $0.kind==kind && $0.payload["reward_id"]==id }) else { return "Reward already selected." }
        }
        if kind=="use_item" {
            guard let item=snapshot.inventory.items?.first(where: { $0.id==payload["item_id"] && $0.quantity>0 }) else { return "Item unavailable." }
            if item.category=="food" ? pet.hunger>=100 : pet.mood>=100 { return "Already full." }
        }
        if kind=="complete", let id=payload["habit_id"], snapshot.habits.first(where: { $0.id==id })?.completed==true { return "Already completed." }
        return nil
    }
    static func imageState(_ pet:Pet, action:String?) -> String {
        if pet.state == "dead" { return "dead" }
        if action == "wake" { return pet.visualState }
        if let action { return action }
        if pet.visualState == "sick" { return "sick" }
        return pet.restAt != nil ? "rest" : pet.visualState
    }
    static func advance(_ pet: inout Pet, to now: Date) {
        pet.fitness=pet.fitnessValue
        guard pet.state != "dead", now >= pet.updatedAt else { return }
        pet.lastDecayAt = pet.lastDecayAt ?? pet.updatedAt
        if pet.hunger > 0 { pet.criticalSince=nil }
        else if pet.criticalSince == nil { pet.criticalSince=pet.updatedAt }
        if pet.hydration > 0 { pet.waterZeroSince=nil }
        else if pet.waterZeroSince == nil { pet.waterZeroSince=pet.updatedAt }
        while true {
            let decay=pet.lastDecayAt!.addingTimeInterval(18000)
            let deadline=[pet.criticalSince,pet.waterZeroSince].compactMap { $0?.addingTimeInterval(172800) }.min()
            let rest=pet.restAt?.addingTimeInterval(1800)
            let event=[decay,deadline,rest].compactMap { $0 }.min()!
            if pet.fitnessValue <= 0 || (deadline != nil && deadline! <= min(event,now)) {
                pet.state="dead"; pet.diedAt=pet.fitnessValue <= 0 ? pet.updatedAt : deadline; pet.restAt=nil; return
            }
            if event > now { break }
            pet.updatedAt=event
            if rest == event { pet.energy=min(100,pet.energy+10); pet.restAt=pet.energy < 100 ? event : nil }
            if decay == event {
                if pet.hunger == 0 || pet.hydration == 0 { pet.fitness=max(0,pet.fitnessValue-30) }
                pet.hunger=max(0,pet.hunger-10); pet.hydration=max(0,pet.hydration-20)
                pet.energy=max(0,pet.energy-5); pet.mood=max(0,pet.mood-5); pet.lastDecayAt=event
                if pet.hunger == 0 && pet.criticalSince == nil { pet.criticalSince=event }
                if pet.hydration == 0 && pet.waterZeroSince == nil { pet.waterZeroSince=event }
            }
            if pet.fitnessValue <= 0 { pet.state="dead"; pet.diedAt=event; pet.restAt=nil; return }
        }
        pet.updatedAt=now
        pet.state=min(pet.hunger,pet.hydration)==0 ? "critical" : pet.hunger<40 ? "hungry" : "healthy"
    }
}
extension Pet {
    var visualState: String {
        if state == "dead" { return "dead" }
        if fitnessValue < 20 { return "sick" }
        if min(hunger,hydration)==0 { return "angry" }
        if min(hunger,hydration,energy)<30 || mood<40 || (sleepDeprivedUntil.map { updatedAt < $0 } ?? false) { return "sad" }
        return mood>=70 && min(hunger,hydration,energy)>=40 ? "happy" : "normal"
    }
}
