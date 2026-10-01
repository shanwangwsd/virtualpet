import XCTest
@testable import HabitPetCore
final class UnifiedTests: XCTestCase {
    func testDecayAndVisuals() {
        let t = Date(timeIntervalSince1970: 0)
        var p = Pet(name:"P",generation:1,hunger:10,hydration:20,energy:70,mood:70,bond:0,xp:0,level:1,state:"healthy",evolution:"baby",updatedAt:t)
        PetRules.advance(&p,to:t.addingTimeInterval(18000))
        XCTAssertEqual(p.hunger,0); XCTAssertEqual(p.hydration,0); XCTAssertEqual(p.fitnessValue,50)
        XCTAssertEqual(p.visualState,"angry")
        PetRules.advance(&p,to:t.addingTimeInterval(36000))
        XCTAssertEqual(p.fitnessValue,20)
        PetRules.advance(&p,to:t.addingTimeInterval(54000))
        XCTAssertEqual(p.visualState,"dead")
        XCTAssertEqual(p.diedAt,t.addingTimeInterval(54000))
    }
    func testCatalogHasCustomArtForEveryPetAndNoDuplicateItems() throws {
        let url = URL(fileURLWithPath:#filePath).deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("HabitPet/Assets/catalog.json")
        let catalog = try JSONDecoder().decode(PetCatalog.self,from:Data(contentsOf:url))
        XCTAssertEqual(Set(catalog.pets.map(\.id)),["potato","cat"])
        for pet in catalog.pets {
            for state in ["normal","happy","sad","angry","sick","dead","eat","drink"] { XCTAssertNotNil(pet.states[state]) }
        }
        XCTAssertEqual(Set(catalog.items.map(\.id)).count,catalog.items.count)
    }
}

extension UnifiedTests {
    func testSickAndDeadOverrideRestAndNewActionOverridesOldState() {
        var pet=Pet(name:"P",generation:1,hunger:70,hydration:70,energy:70,mood:70,bond:0,xp:0,level:1,state:"healthy",evolution:"baby",updatedAt:.now)
        pet.restAt = .now
        pet.fitness=10
        XCTAssertEqual(PetRules.imageState(pet,action:nil),"sick")
        XCTAssertEqual(PetRules.imageState(pet,action:"eat"),"eat")
        pet.state="dead"
        XCTAssertEqual(PetRules.imageState(pet,action:"eat"),"dead")
    }
}

extension UnifiedTests {
    private func actionSnapshot() -> Snapshot {
        let pet=Pet(name:"P",generation:1,hunger:70,hydration:100,energy:70,mood:70,bond:0,xp:0,level:1,state:"healthy",evolution:"baby",updatedAt:.now)
        return Snapshot(serverTime:.now,date:"2026-10-01",timezone:"UTC",pet:pet,inventory:Inventory(food:0,coin:0),habits:[],health:HealthSummary(steps:0,sleepMinutes:nil,stepReward:0),waterCount:0,message:PetMessage(emotion:"happy",message:"Hi",suggestedAction:"none",urgency:"low",source:"rule"))
    }
    func testRepeatedRewardAndRebirthDoNotEnterQueue() {
        var state=actionSnapshot()
        state.pendingRewards=[PendingReward(id:1,name:"Read",date:"2026-10-01")]
        let claim=PendingAction(kind:"claim_reward",generation:1,payload:["reward_id":1,"category":0])
        XCTAssertNil(PetRules.actionError("claim_reward",payload:claim.payload,snapshot:state,pending:[]))
        XCTAssertNotNil(PetRules.actionError("claim_reward",payload:claim.payload,snapshot:state,pending:[claim]))
        state.pet.state="dead"
        XCTAssertNil(PetRules.actionError("rebirth",payload:[:],snapshot:state,pending:[]))
        XCTAssertNotNil(PetRules.actionError("rebirth",payload:[:],snapshot:state,pending:[PendingAction(kind:"rebirth",generation:1)]))
    }
    func testFullWaterAndUnavailableStockAreRejectedLocally() {
        let state=actionSnapshot()
        XCTAssertNotNil(PetRules.actionError("water",payload:[:],snapshot:state,pending:[]))
        XCTAssertNotNil(PetRules.actionError("use_item",payload:["item_id":3],snapshot:state,pending:[]))
    }
}

extension UnifiedTests {
    func testRewardFlowTracksCompletionAndFiltersByHabitID() {
        let complete=PendingAction(kind:"complete",generation:1,payload:["habit_id":7])
        XCTAssertTrue(RewardFlow.waiting([complete],habitID:7))
        XCTAssertFalse(RewardFlow.waiting([complete],habitID:8))
        let rewards=[PendingReward(id:1,name:"Same name",date:"2026-10-01",habitId:7),PendingReward(id:2,name:"Same name",date:"2026-10-01",habitId:8)]
        XCTAssertEqual(RewardFlow.choices(rewards,habitID:7).map(\.id),[1])
        XCTAssertEqual(RewardFlow.choices(rewards,habitID:nil).count,2)
    }
}

extension UnifiedTests {
    func testGeneratedScheduleSpeechPersistsAndInvalidatesWhenTaskChanges() throws {
        var reminder=DailyReminder(title:"Study Japanese",hour:19,minute:0)
        reminder.generatedSpeech="Hmph! Japanese time!"
        reminder.generatedForTitle="Study Japanese"
        reminder.speechSource="live"
        let restored=try JSONDecoder().decode(DailyReminder.self,from:JSONEncoder().encode(reminder))
        XCTAssertEqual(try restored.notificationRequest().content.body,"Hmph! Japanese time!")
        reminder.title="Read"
        XCTAssertTrue(reminder.message.contains("Read"))
        XCTAssertFalse(reminder.message.contains("Japanese"))
    }
}

extension UnifiedTests {
    func testRetiredPlayCannotIncreaseMoodOrEnterQueue() {
        let state=actionSnapshot()
        XCTAssertNotNil(PetRules.actionError("play",payload:[:],snapshot:state,pending:[]))
        let projected=Projection.apply([PendingAction(kind:"play",generation:1)],to:state)
        XCTAssertEqual(projected.pet.mood,state.pet.mood)
        XCTAssertEqual(projected.pet.xp,state.pet.xp)
    }
}


extension UnifiedTests {
    func testWakeShowsCurrentConditionRatherThanPlayOrRest() {
        var pet=actionSnapshot().pet
        pet.restAt = .now
        XCTAssertEqual(PetRules.imageState(pet,action:"wake"),"happy")
        pet.mood=20
        XCTAssertEqual(PetRules.imageState(pet,action:"wake"),"sad")
        pet.fitness=10
        XCTAssertEqual(PetRules.imageState(pet,action:"wake"),"sick")
        pet.state="dead"
        XCTAssertEqual(PetRules.imageState(pet,action:"wake"),"dead")
    }
}


extension UnifiedTests {
    func testFitnessZeroAndOvershootAreFatalAndClamped() {
        for initial in [30,20,0,-10] {
            var pet=actionSnapshot().pet
            let start=pet.updatedAt
            pet.hunger=0; pet.fitness=initial
            PetRules.advance(&pet,to:start.addingTimeInterval(18000))
            XCTAssertEqual(pet.fitness,0)
            XCTAssertEqual(pet.state,"dead")
            XCTAssertEqual(pet.diedAt,initial <= 0 ? start : start.addingTimeInterval(18000))
        }
    }
}
