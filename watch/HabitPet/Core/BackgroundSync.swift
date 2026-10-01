import Foundation

/// Runs one ordered flush at a time without making a local interaction wait
/// for the server. The caller keeps its durable queue when a flush fails.
@MainActor final class BackgroundSync {
    private(set) var running = false
    private var task: Task<Void, Never>?
    @discardableResult
    func start(_ operation: @escaping () async throws -> Void, finished: @escaping (Error?) -> Void) -> Bool {
        guard !running else { return false }
        running = true
        task = Task {
            var failure: Error?
            do { try Task.checkCancellation(); try await operation(); try Task.checkCancellation() } catch { failure = error }
            running = false
            task = nil
            finished(failure)
        }
        return true
    }
    func waitUntilFinished() async { await task?.value }
    func cancelAndWait() async {
        let current = task
        current?.cancel()
        await current?.value
    }
}
