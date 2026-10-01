import XCTest
@testable import HabitPetCore

@MainActor final class BackgroundSyncTests: XCTestCase {
    func testSlowNetworkRunsWithoutBlockingCallerAndStartsOnlyOneFlush() async {
        let sync = BackgroundSync()
        var release: CheckedContinuation<Void, Never>?
        let started = expectation(description: "request started")
        let finished = expectation(description: "request finished")
        XCTAssertTrue(sync.start({
            await withCheckedContinuation { release = $0; started.fulfill() }
        }, finished: { error in XCTAssertNil(error); finished.fulfill() }))
        await fulfillment(of: [started], timeout: 1)
        XCTAssertTrue(sync.running)
        XCTAssertFalse(sync.start({ XCTFail("duplicate flush") }, finished: { _ in }))
        // The caller is still able to run while the network has not responded.
        release?.resume()
        await fulfillment(of: [finished], timeout: 1)
        XCTAssertFalse(sync.running)
    }
    func testFailureReleasesSyncAndAllowsRetry() async {
        let sync = BackgroundSync()
        let failed = expectation(description: "failure returned")
        sync.start({ throw URLError(.timedOut) }, finished: { error in
            XCTAssertEqual((error as? URLError)?.code, .timedOut)
            failed.fulfill()
        })
        await fulfillment(of: [failed], timeout: 1)
        XCTAssertFalse(sync.running)
        let retried = expectation(description: "retry completed")
        XCTAssertTrue(sync.start({}, finished: { error in XCTAssertNil(error); retried.fulfill() }))
        await fulfillment(of: [retried], timeout: 1)
    }
}
