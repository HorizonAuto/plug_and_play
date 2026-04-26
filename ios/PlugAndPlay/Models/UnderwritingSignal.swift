import Foundation

struct AntiCheatResult: Decodable, Identifiable {
    let check: String
    let passed: Bool?
    let reason: String

    var id: String { check }
}

struct UnderwritingScore: Decodable {
    let score: Int
    let notes: [String]
}
