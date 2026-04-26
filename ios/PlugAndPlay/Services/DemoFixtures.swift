import Foundation

enum DemoFixtures {
    static var isOn: Bool {
        UserDefaults.standard.bool(forKey: "demoMode")
    }

    static let spaceJSON: String = """
    {
      "duration_seconds": 47.2,
      "keyframe_count": 18,
      "captured_at": null,
      "gps": {"lat": null, "lon": null},
      "hazards": {
        "fire_extinguishers": [
          {"frame_index": 4, "bbox": [0.62, 0.30, 0.09, 0.22], "confidence": 0.92}
        ],
        "exit_signs": [
          {"frame_index": 2, "bbox": [0.40, 0.05, 0.18, 0.08], "confidence": 0.88},
          {"frame_index": 11, "bbox": [0.74, 0.10, 0.16, 0.07], "confidence": 0.81}
        ],
        "exits_unobstructed": true,
        "slip_trip_hazards": [
          {"frame_index": 6, "description": "Loose extension cord crossing main walkway near the front counter.", "bbox": [0.20, 0.62, 0.55, 0.10], "severity": "medium"}
        ],
        "clutter_score": 0.32,
        "lighting_adequacy": "adequate",
        "estimated_floor_area_sqm": 87,
        "summary": "Small storefront, ~87 m². One fire extinguisher and two exit signs visible. Front and rear exits clear. One slip hazard from a loose extension cord at frame 6 — minor remediation."
      },
      "anticheat": [
        {"check": "face_continuity", "passed": true, "reason": "face anchor present in 87% of samples (threshold 50%)"},
        {"check": "mesh_coverage", "passed": true, "reason": "12,847 mesh triangles across 9 anchors (adequate)"}
      ],
      "underwriting": {
        "score": 80,
        "notes": ["1 slip/trip hazard(s) (-5)"]
      }
    }
    """

    static func spaceResponse() throws -> SpaceVerifyResponse {
        try JSONDecoder().decode(SpaceVerifyResponse.self, from: Data(spaceJSON.utf8))
    }
}
