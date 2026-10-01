import Foundation

@MainActor enum AccountExit {
    /// False means local sign-out succeeded but remote revocation was unavailable.
    static func run(deleteAccount: Bool, remote: () async throws -> Void, clearLocal: () throws -> Void) async throws -> Bool {
        if deleteAccount {
            try await remote()
            try clearLocal()
            return true
        }
        try clearLocal()
        do { try await remote(); return true } catch { return false }
    }
}

enum RequestFailure {
    static func message(_ error: Error, server: String?) -> String {
        let host = server.flatMap { URL(string: $0)?.host } ?? "your server"
        if let e = error as? URLError {
            switch e.code {
            case .timedOut: return "The server timed out (\(host)). Check its connection and try again."
            case .notConnectedToInternet: return "This Watch is offline. Connect to Wi-Fi or your iPhone and retry."
            case .cannotConnectToHost, .cannotFindHost, .dnsLookupFailed, .networkConnectionLost:
                return "Cannot reach the server (\(host)). Check the server address and that the backend is running."
            case .appTransportSecurityRequiresSecureConnection: return "This connection requires HTTPS. Check your server address."
            case .secureConnectionFailed, .serverCertificateUntrusted: return "The server's HTTPS connection could not be verified. Check its certificate."
            case .cancelled: return "Request cancelled."
            default: return "Connection failed (\(e.code.rawValue)). Check the server address and retry."
            }
        }
        if error is DecodingError { return "The server reply could not be read. Update the backend and retry." }
        let e = error as NSError
        if e.domain == NSCocoaErrorDomain { return "Could not save local data. Check available storage and retry." }
        if e.domain == NSOSStatusErrorDomain { return "Could not update secure sign-in storage (\(e.code)). Unlock this Watch and retry." }
        return "The request failed (\(e.code)). Please retry."
    }
}
