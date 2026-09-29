import XCTest
@testable import HabitPetCore
final class CoreTests: XCTestCase {
    let start = Date(timeIntervalSince1970: 0)
    func testFocusSurvivesSuspensionAndPause() {
        var timer = FocusTimer(habitID: 1, goalSeconds: 1800, now: start)
        XCTAssertEqual(timer.remaining(at: start.addingTimeInterval(600)), 1200)
        timer.pause(at: start.addingTimeInterval(600))
        XCTAssertEqual(timer.remaining(at: start.addingTimeInterval(900)), 1200)
        timer.resume(at: start.addingTimeInterval(900))
        XCTAssertEqual(timer.remaining(at: start.addingTimeInterval(2100)), 0)
    }
    func testOverlappingSleepExcludesDuplicateTimeAndClipsWindow() {
        let samples = [SleepInterval(start: start.addingTimeInterval(-100), end: start.addingTimeInterval(3600)), SleepInterval(start: start.addingTimeInterval(1800), end: start.addingTimeInterval(7200))]
        XCTAssertEqual(SleepMath.minutes(samples, from: start, to: start.addingTimeInterval(6000)), 100)
    }
    func testOfflineCompletionThenFeedingAndRepeatedCompletion() {
        let pet = Pet(name:"Mochi",generation:1,hunger:70,hydration:70,energy:70,mood:50,bond:10,xp:0,level:1,state:"healthy",evolution:"baby",updatedAt:start)
        let habit = Habit(id:1,name:"Japanese",category:"study",target:30,unit:"minutes",rewardType:"food",rewardAmount:1,progress:0,completed:false)
        let snapshot = Snapshot(serverTime:start,date:"2026-01-01",timezone:"Asia/Tokyo",pet:pet,inventory:Inventory(food:0,coin:0),habits:[habit],health:HealthSummary(steps:0,sleepMinutes:nil,stepReward:0),waterCount:0,message:PetMessage(emotion:"calm",message:"Hi",suggestedAction:"none",urgency:"low",source:"rule"))
        let actions = [PendingAction(kind:"complete",generation:1,payload:["habit_id":1]), PendingAction(kind:"complete",generation:1,payload:["habit_id":1]),PendingAction(kind:"feed",generation:1)]
        let projected = Projection.apply(actions,to:snapshot)
        XCTAssertEqual(projected.inventory.food,0)
        XCTAssertEqual(projected.pet.hunger,100)
        XCTAssertEqual(projected.pet.xp,5)
        XCTAssertTrue(projected.habits[0].completed)
    }
    func testWireActionRoundTripPreservesIDForRetry() throws {
        let action=PendingAction(kind:"water",generation:1,now:start)
        let encoded=try Wire.encoder().encode(action)
        let decoded=try Wire.decoder().decode(PendingAction.self,from:encoded)
        XCTAssertEqual(action,decoded)
    }
}
