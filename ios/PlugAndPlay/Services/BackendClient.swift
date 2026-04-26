import Foundation

enum BackendError: LocalizedError {
    case badResponse(Int, String)
    case decoding(Error)
    case transport(Error)

    var errorDescription: String? {
        switch self {
        case .badResponse(let code, let body): return "server returned \(code): \(body.prefix(200))"
        case .decoding(let e): return "could not decode response: \(e.localizedDescription)"
        case .transport(let e): return "network error: \(e.localizedDescription)"
        }
    }
}

struct SpaceVerifyRequest {
    let keyframes: [URL]
    let faceTimeline: [FacePresence]
    let meshSummary: MeshSummary
    let durationSeconds: Double
    let location: LocationFix?
    let capturedAt: Date
}

actor BackendClient {
    static let shared = BackendClient()

    /// Override at runtime via `UserDefaults.standard.set("https://...", forKey: "backendBaseURL")`.
    private var baseURL: URL {
        if let s = UserDefaults.standard.string(forKey: "backendBaseURL"), let u = URL(string: s) {
            return u
        }
        return URL(string: "http://localhost:8000")!
    }

    func verifySpace(_ request: SpaceVerifyRequest) async throws -> SpaceVerifyResponse {
        if DemoFixtures.isOn {
            try? await Task.sleep(for: .seconds(2))
            return try DemoFixtures.spaceResponse()
        }
        let url = baseURL.appendingPathComponent("verify/space")
        let boundary = "Boundary-\(UUID().uuidString)"

        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 180

        var body = Data()
        body.appendField(name: "duration_seconds", value: String(request.durationSeconds), boundary: boundary)
        body.appendField(
            name: "captured_at",
            value: ISO8601DateFormatter.iso8601Fractional.string(from: request.capturedAt),
            boundary: boundary
        )
        if let loc = request.location {
            body.appendField(name: "gps_lat", value: String(loc.latitude), boundary: boundary)
            body.appendField(name: "gps_lon", value: String(loc.longitude), boundary: boundary)
        }

        let encoder = JSONEncoder()
        let faceJSON = try encoder.encode(request.faceTimeline)
        body.appendFile(name: "face_timeline", filename: "face.json",
                        mimeType: "application/json", data: faceJSON, boundary: boundary)

        let meshJSON = try encoder.encode(request.meshSummary)
        body.appendFile(name: "mesh_summary", filename: "mesh.json",
                        mimeType: "application/json", data: meshJSON, boundary: boundary)

        for (idx, kfURL) in request.keyframes.enumerated() {
            let data = try Data(contentsOf: kfURL)
            body.appendFile(
                name: "keyframes",
                filename: "kf_\(idx).jpg",
                mimeType: "image/jpeg",
                data: data,
                boundary: boundary
            )
        }
        body.append("--\(boundary)--\r\n")
        req.httpBody = body

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await URLSession.shared.data(for: req)
        } catch {
            throw BackendError.transport(error)
        }
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            let code = (response as? HTTPURLResponse)?.statusCode ?? -1
            let bodyText = String(data: data, encoding: .utf8) ?? ""
            throw BackendError.badResponse(code, bodyText)
        }
        do {
            return try JSONDecoder().decode(SpaceVerifyResponse.self, from: data)
        } catch {
            throw BackendError.decoding(error)
        }
    }
}

private extension ISO8601DateFormatter {
    static let iso8601Fractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
}

private extension Data {
    mutating func append(_ s: String) {
        if let d = s.data(using: .utf8) { append(d) }
    }

    mutating func appendField(name: String, value: String, boundary: String) {
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
        append("\(value)\r\n")
    }

    mutating func appendFile(name: String, filename: String, mimeType: String, data: Data, boundary: String) {
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"\(name)\"; filename=\"\(filename)\"\r\n")
        append("Content-Type: \(mimeType)\r\n\r\n")
        append(data)
        append("\r\n")
    }
}
