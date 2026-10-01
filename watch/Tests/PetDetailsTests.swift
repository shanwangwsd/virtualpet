import XCTest
@testable import HabitPetCore

final class PetDetailsTests: XCTestCase {
    private func pet() -> Pet {
        Pet(name: "Mochi", generation: 1, hunger: 70, hydration: 70, energy: 70, mood: 70, bond: 10, xp: 135, level: 2, state: "healthy", evolution: "baby", updatedAt: Date(timeIntervalSince1970: 0))
    }
    func testAgeUsesFullDaysAndStopsAtDeath() {
        var value = pet()
        value.initialAgeDays = 7
        value.bornAt = Date(timeIntervalSince1970: 0)
        XCTAssertEqual(value.currentAgeDays(at: Date(timeIntervalSince1970: 172799)), 1)
        XCTAssertEqual(value.currentAgeDays(at: Date(timeIntervalSince1970: 172800)), 2)
        value.diedAt = Date(timeIntervalSince1970: 86400)
        XCTAssertEqual(value.currentAgeDays(at: Date(timeIntervalSince1970: 999999)), 1)
        XCTAssertEqual(value.xpIntoLevel, 35)
        XCTAssertEqual(value.xpUntilNextLevel, 65)
    }
    func testExistingPetCacheStillDecodesAndDefaultsToCat() throws {
        let data = try Wire.encoder().encode(pet())
        let decoded = try Wire.decoder().decode(Pet.self, from: data)
        XCTAssertEqual(decoded.appearance.species, "cat")
        XCTAssertEqual(decoded.genderLabel, "Unspecified")
        XCTAssertEqual(decoded.currentAgeDays(at: Date()), 0)
        XCTAssertFalse(decoded.detailsConfigured ?? false)
    }
    func testNotificationIncludesSelectedPetWithoutChangingReminderIdentity() throws {
        let reminder = DailyReminder(title: "Read", hour: 20, minute: 0)
        let request = try reminder.notificationRequest(appearance: PetAppearance(name: "Clover", species: "potato"))
        XCTAssertEqual(request.identifier, reminder.notificationID)
        XCTAssertEqual(request.content.userInfo["petName"] as? String, "Clover")
        XCTAssertEqual(request.content.userInfo["petSpecies"] as? String, "potato")
        XCTAssertTrue(request.content.title.contains("Clover"))
    }
}
