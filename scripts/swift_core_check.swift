import Foundation
@main struct CoreCheck {
    static func main() throws {
        var failures = 0
        func check(_ condition: Bool, _ name: String) {
            if !condition { failures += 1; print("FAIL: \(name)") } else { print("PASS: \(name)") }
        }
        let start=Date(timeIntervalSince1970:0)
        var timer=FocusTimer(habitID:1,goalSeconds:1800,now:start)
        check(timer.remaining(at:start.addingTimeInterval(600)) == 1200,"timer survives suspension")
        timer.pause(at:start.addingTimeInterval(600))
        check(timer.remaining(at:start.addingTimeInterval(900)) == 1200,"pause freezes elapsed")
        timer.resume(at:start.addingTimeInterval(900))
        check(timer.remaining(at:start.addingTimeInterval(2100)) == 0,"resume completes")
        let intervals=[SleepInterval(start:start.addingTimeInterval(-100),end:start.addingTimeInterval(3600)),SleepInterval(start:start.addingTimeInterval(1800),end:start.addingTimeInterval(7200))]
        check(SleepMath.minutes(intervals,from:start,to:start.addingTimeInterval(6000)) == 100,"overlapping sleep clipped and merged")
        let pet=Pet(name:"Mochi",generation:1,hunger:70,hydration:70,energy:70,mood:50,bond:10,xp:0,level:1,state:"healthy",evolution:"baby",updatedAt:start)
        let habit=Habit(id:1,name:"Japanese",category:"study",target:30,unit:"minutes",rewardType:"food",rewardAmount:1,progress:0,completed:false)
        let snapshot=Snapshot(serverTime:start,date:"2026-01-01",timezone:"Asia/Tokyo",pet:pet,inventory:Inventory(food:0,coin:0),habits:[habit],health:HealthSummary(steps:0,sleepMinutes:nil,stepReward:0),waterCount:0,message:PetMessage(emotion:"calm",message:"Hi",suggestedAction:"none",urgency:"low",source:"rule"))
        let actions=[PendingAction(kind:"complete",generation:1,payload:["habit_id":1],now:start),PendingAction(kind:"complete",generation:1,payload:["habit_id":1],now:start),PendingAction(kind:"feed",generation:1,now:start)]
        let projected=Projection.apply(actions,to:snapshot)
        check(projected.inventory.food == 0 && projected.pet.hunger == 100 && projected.pet.xp == 5 && projected.habits[0].completed,"offline completion/feed deduplicates rewards")
        let decoded=try Wire.decoder().decode(PendingAction.self,from:Wire.encoder().encode(actions[0]))
        check(decoded==actions[0],"durable action ID and payload round trip")
        do {
            let saved=FocusTimer(habitID:7,goalSeconds:300,now:start)
            let restored=try Wire.decoder().decode(FocusTimer.self,from:Wire.encoder().encode(saved))
            check(restored==saved,"focus persists across app restarts")
        } catch { check(false,"focus persists across app restarts: \(error)") }
        let decayed=Projection.apply([],to:snapshot,now:start.addingTimeInterval(8*3600))
        check(decayed.pet.hunger==60 && decayed.pet.hydration==60,"offline state advances elapsed time")
        if failures>0 { exit(1) }
    }
}
