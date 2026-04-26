import Foundation

struct SpaceVerifyResponse: Decodable {
    let durationSeconds: Double
    let keyframeCount: Int
    let hazards: SpaceHazardReport
    let anticheat: [AntiCheatResult]
    let underwriting: UnderwritingScore
    let annotatedKeyframeUrls: [String]?

    enum CodingKeys: String, CodingKey {
        case durationSeconds = "duration_seconds"
        case keyframeCount = "keyframe_count"
        case hazards
        case anticheat
        case underwriting
        case annotatedKeyframeUrls = "annotated_keyframe_urls"
    }
}

struct SpaceHazardReport: Decodable {
    let fireExtinguishers: [SafetyDetection]
    let exitSigns: [SafetyDetection]
    let exitsUnobstructed: Bool
    let slipTripHazards: [SlipHazard]
    let clutterScore: Double
    let lightingAdequacy: String
    let estimatedFloorAreaSqm: Double
    let summary: String

    enum CodingKeys: String, CodingKey {
        case fireExtinguishers = "fire_extinguishers"
        case exitSigns = "exit_signs"
        case exitsUnobstructed = "exits_unobstructed"
        case slipTripHazards = "slip_trip_hazards"
        case clutterScore = "clutter_score"
        case lightingAdequacy = "lighting_adequacy"
        case estimatedFloorAreaSqm = "estimated_floor_area_sqm"
        case summary
    }
}

struct SafetyDetection: Decodable, Identifiable {
    let frameIndex: Int
    let confidence: Double
    var id: String { "\(frameIndex)-\(confidence)" }

    enum CodingKeys: String, CodingKey {
        case frameIndex = "frame_index"
        case confidence
    }
}

struct SlipHazard: Decodable, Identifiable {
    let frameIndex: Int
    let description: String
    let severity: String?
    var id: String { "\(frameIndex)-\(description)" }

    enum CodingKeys: String, CodingKey {
        case frameIndex = "frame_index"
        case description
        case severity
    }
}
