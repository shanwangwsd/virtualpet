import XCTest
@testable import HabitPetCore

@MainActor final class AccountExitTests: XCTestCase {
    func testOfflineSignOutClearsLocalSessionEvenIfServerCannotBeReached() async throws {
        var locallySignedIn = true
        let result = try await AccountExit.run(deleteAccount: false, remote: {
            XCTAssertFalse(locallySignedIn)
            throw URLError(.notConnectedToInternet)
        }, clearLocal: { locallySignedIn = false })
        XCTAssertFalse(locallySignedIn)
        XCTAssertFalse(result)
    }
    func testFailedDeletionKeepsSessionSoUserCanRetry() async {
        var locallySignedIn = true
        do {
            _ = try await AccountExit.run(deleteAccount: true, remote: { throw URLError(.timedOut) }, clearLocal: { locallySignedIn = false })
            XCTFail("Deletion must report failure")
        } catch {
            XCTAssertTrue(locallySignedIn)
            XCTAssertEqual((error as? URLError)?.code, .timedOut)
        }
    }
    func testConfirmedDeletionClearsSessionOnlyAfterServerSuccess() async throws {
        var serverDeleted = false
        var locallySignedIn = true
        _ = try await AccountExit.run(deleteAccount: true, remote: { serverDeleted = true }, clearLocal: {
            XCTAssertTrue(serverDeleted)
            locallySignedIn = false
        })
        XCTAssertFalse(locallySignedIn)
    }
    func testNetworkErrorsAreActionableAndDoNotIncludeCredentials() {
        let text = RequestFailure.message(URLError(.cannotConnectToHost), server: "http://user:secret@192.168.1.5:8000")
        XCTAssertTrue(text.contains("192.168.1.5"))
        XCTAssertFalse(text.contains("secret"))
        XCTAssertTrue(RequestFailure.message(URLError(.timedOut), server: nil).contains("timed out"))
        XCTAssertTrue(RequestFailure.message(URLError(.appTransportSecurityRequiresSecureConnection), server: nil).contains("HTTPS"))
    }
}
