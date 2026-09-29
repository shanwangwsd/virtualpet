import Foundation

struct APIError: LocalizedError {
    let status: Int
    let detail: String
    var errorDescription: String? { "\(status)：\(detail)" }
}

@MainActor final class APIClient {
    var credentials: Credentials?
    init() { credentials = KeychainStore.load() }
    func login(baseURL: String, username: String, password: String, register: Bool) async throws {
        guard let url = URL(string: baseURL), url.scheme == "https" || (url.scheme == "http" && Self.localHost(url.host ?? "")), url.host != nil else {
            throw APIError(status: 0, detail: "请输入 HTTPS 地址；本地开发地址可使用 HTTP")
        }
        let normalized = baseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let body = try JSONSerialization.data(withJSONObject: ["username": username, "password": password])
        let data = try await send(base: normalized, path: register ? "api/auth/register/" : "api/auth/login/", method: "POST", body: body, token: nil)
        let tokens = try JSONDecoder().decode(Tokens.self, from: data)
        let value = Credentials(access: tokens.access, refresh: tokens.refresh, username: username, baseURL: normalized)
        try KeychainStore.save(value); credentials = value
    }
    private static func localHost(_ host: String) -> Bool {
        host == "localhost" || host == "127.0.0.1" || host.hasSuffix(".local") || host.hasPrefix("192.168.") || host.hasPrefix("10.")
    }
    func request<T: Decodable>(_ path: String, method: String = "GET", body: Data? = nil) async throws -> T {
        let data = try await authorized(path, method: method, body: body)
        return try Wire.decoder().decode(T.self, from: data)
    }
    func empty(_ path: String, method: String, body: Data? = nil) async throws { _ = try await authorized(path, method: method, body: body) }
    private func authorized(_ path: String, method: String, body: Data?) async throws -> Data {
        guard var value = credentials else { throw APIError(status: 401, detail: "请先登录") }
        do { return try await send(base: value.baseURL, path: path, method: method, body: body, token: value.access) }
        catch let error as APIError where error.status == 401 {
            let refreshBody = try JSONSerialization.data(withJSONObject: ["refresh": value.refresh])
            let data = try await send(base: value.baseURL, path: "api/auth/refresh/", method: "POST", body: refreshBody, token: nil)
            let tokens = try JSONDecoder().decode(Tokens.self, from: data)
            value.access = tokens.access; value.refresh = tokens.refresh
            try KeychainStore.save(value); credentials = value
            return try await send(base: value.baseURL, path: path, method: method, body: body, token: value.access)
        }
    }
    private func send(base: String, path: String, method: String, body: Data?, token: String?) async throws -> Data {
        guard let url = URL(string: base + "/" + path) else { throw URLError(.badURL) }
        var request = URLRequest(url: url); request.httpMethod = method; request.httpBody = body; request.timeoutInterval = 25
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let response = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        guard (200..<300).contains(response.statusCode) else {
            throw APIError(status: response.statusCode, detail: String(data: data, encoding: .utf8).map { String($0.prefix(240)) } ?? "请求失败")
        }
        return data
    }
    private struct Tokens: Decodable { let access: String; let refresh: String }
}
