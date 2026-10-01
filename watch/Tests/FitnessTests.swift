import XCTest
@testable import HabitPetCore

final class FitnessTests: XCTestCase {
    func testThresholdPreviews() {
        XCTAssertEqual([0,499,500,999,1000,4999,5000].map(FitnessRules.steps), [-10,-10,0,0,10,10,30])
        XCTAssertEqual([0,299,300,479,480].map(FitnessRules.sleep), [-10,-10,0,0,10])
    }
    func testNaturalDayAndSleepWindowAcrossDST() throws {
        let calendar = FitnessCalendar.calendar("America/New_York")
        let date = try XCTUnwrap(FitnessCalendar.date("2026-03-08", calendar: calendar))
        let steps = FitnessCalendar.stepWindow(date, calendar: calendar)
        XCTAssertEqual(steps.end.timeIntervalSince(steps.start), 23*3600)
        let sleep = FitnessCalendar.sleepWindow(date, calendar: calendar)
        XCTAssertEqual(calendar.component(.hour, from: sleep.start), 18)
        XCTAssertEqual(calendar.component(.hour, from: sleep.end), 12)
        XCTAssertEqual(sleep.end.timeIntervalSince(sleep.start), 17*3600)
    }
    func testBackfillStartsAtEarliestCursorAndIncludesTodaysPreview() throws {
        let cal=FitnessCalendar.calendar("UTC")
        let now=try XCTUnwrap(FitnessCalendar.date("2026-10-30", calendar: cal))
        let batch=try FitnessCalendar.batch(start: "2026-10-01", lastSteps: "2026-10-03", lastSleep: "2026-10-02", timezone: "UTC", now: now)
        XCTAssertTrue(batch.hasMore)
        XCTAssertEqual(batch.days.count, 15)
        XCTAssertEqual(FitnessCalendar.key(batch.days[0], calendar: cal), "2026-10-03")
        XCTAssertEqual(FitnessCalendar.key(batch.days.last!, calendar: cal), "2026-10-30")
    }
    func testMissingSamplesAreEncodedAsNullNotOmittedOrZero() throws {
        let input=HealthDayInput(date:"2026-10-01",steps:nil,sleepMinutes:nil)
        let object=try JSONSerialization.jsonObject(with: Wire.encoder().encode(input)) as! [String:Any]
        XCTAssertTrue(object["steps"] is NSNull)
        XCTAssertTrue(object["sleep_minutes"] is NSNull)
    }
}
