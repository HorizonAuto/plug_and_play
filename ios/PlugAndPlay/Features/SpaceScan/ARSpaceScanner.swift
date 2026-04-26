import ARKit
import CoreImage
import Foundation
import UIKit

struct SpaceScanArtifacts {
    let keyframes: [URL]                 // JPEG paths in temp dir
    let faceTimeline: [FacePresence]     // 1 Hz sample of face-anchor presence
    let meshSummary: MeshSummary
    let durationSeconds: Double
}

struct FacePresence: Encodable {
    let t: Double
    let present: Bool
}

struct MeshSummary: Encodable {
    let totalFaces: Int            // triangle count across all anchors
    let estimatedAreaSquareMeters: Double
    let anchorCount: Int
}

enum SpaceScanError: LocalizedError {
    case unsupportedDevice(String)
    case sessionStartFailed(String)
    case alreadyRunning
    case notRunning

    var errorDescription: String? {
        switch self {
        case .unsupportedDevice(let s): return "device unsupported: \(s)"
        case .sessionStartFailed(let s): return "AR session failed: \(s)"
        case .alreadyRunning: return "already scanning"
        case .notRunning: return "not currently scanning"
        }
    }
}

@MainActor
final class ARSpaceScanner: NSObject, ObservableObject {
    let session = ARSession()
    @Published private(set) var isPreviewing: Bool = false
    @Published private(set) var isRecording: Bool = false
    @Published private(set) var keyframeCount: Int = 0
    @Published private(set) var meshFaceCount: Int = 0

    private var keyframeURLs: [URL] = []
    private var faceTimeline: [FacePresence] = []
    private var startedAt: Date?
    private var lastKeyframeAt: Date?
    private var lastFaceSampleAt: Date?
    private var lastMeshSampleAt: Date = .distantPast
    private let ciContext = CIContext()

    override init() {
        super.init()
        session.delegate = self
    }

    /// Starts the AR session so the camera feed renders. Safe to call repeatedly.
    /// Does NOT begin capturing artifacts — call `startRecording()` for that.
    func startPreview() throws {
        guard !isPreviewing else { return }
        guard ARWorldTrackingConfiguration.isSupported else {
            throw SpaceScanError.unsupportedDevice("ARWorldTrackingConfiguration not supported")
        }
        guard ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh) else {
            throw SpaceScanError.unsupportedDevice("LiDAR mesh reconstruction requires an iPhone Pro")
        }

        let config = ARWorldTrackingConfiguration()
        config.sceneReconstruction = .mesh
        config.frameSemantics.insert(.sceneDepth)
        config.environmentTexturing = .none
        config.planeDetection = []
        if ARWorldTrackingConfiguration.supportsUserFaceTracking {
            config.userFaceTrackingEnabled = true
        }

        session.run(config, options: [.resetTracking, .removeExistingAnchors])
        isPreviewing = true
    }

    func pausePreview() {
        guard isPreviewing else { return }
        session.pause()
        isPreviewing = false
    }

    func startRecording() throws {
        guard isPreviewing else { throw SpaceScanError.notRunning }
        guard !isRecording else { throw SpaceScanError.alreadyRunning }
        keyframeURLs.removeAll()
        faceTimeline.removeAll()
        startedAt = Date()
        lastKeyframeAt = nil
        lastFaceSampleAt = nil
        keyframeCount = 0
        // Don't reset meshFaceCount — the LiDAR mesh accrues across the AR
        // session and we want the user to see it climbing through the preview.
        isRecording = true
    }

    func stopRecording() throws -> SpaceScanArtifacts {
        guard isRecording else { throw SpaceScanError.notRunning }
        isRecording = false
        // Leave the AR session running so the preview stays live for the next scan.

        let duration = startedAt.map { Date().timeIntervalSince($0) } ?? 0

        var totalFaces = 0
        var anchorCount = 0
        var areaSqM: Double = 0
        for anchor in session.currentFrame?.anchors ?? [] {
            guard let mesh = anchor as? ARMeshAnchor else { continue }
            anchorCount += 1
            let geom = mesh.geometry
            let faces = geom.faces.count
            totalFaces += faces
            // Each ARMeshAnchor is roughly cubic; approximate covered area as
            // half the bounding box surface (most of an indoor scene is one-sided).
            let extent = mesh.transform.columns.0
            let scale = max(0.5, simd_length(SIMD3<Float>(extent.x, extent.y, extent.z)))
            areaSqM += Double(scale * scale * 0.5)
        }
        meshFaceCount = totalFaces

        return SpaceScanArtifacts(
            keyframes: keyframeURLs,
            faceTimeline: faceTimeline,
            meshSummary: MeshSummary(
                totalFaces: totalFaces,
                estimatedAreaSquareMeters: areaSqM,
                anchorCount: anchorCount
            ),
            durationSeconds: duration
        )
    }

    func cleanup(_ artifacts: SpaceScanArtifacts) {
        for url in artifacts.keyframes {
            try? FileManager.default.removeItem(at: url)
        }
    }

    // MARK: - keyframe sampling (called from ARSessionDelegate)

    fileprivate func sampleIfNeeded(_ frame: ARFrame) {
        let now = Date()

        // Live mesh polygon count — updated during preview AND recording so the
        // user can see the LiDAR fill in before they commit. Throttled to ~2 Hz.
        if now.timeIntervalSince(lastMeshSampleAt) >= 0.5 {
            lastMeshSampleAt = now
            var faces = 0
            for anchor in frame.anchors {
                if let mesh = anchor as? ARMeshAnchor { faces += mesh.geometry.faces.count }
            }
            if faces != meshFaceCount { meshFaceCount = faces }
        }

        guard isRecording else { return }

        if lastKeyframeAt == nil || now.timeIntervalSince(lastKeyframeAt!) >= 1.0 {
            lastKeyframeAt = now
            saveKeyframe(from: frame.capturedImage)
        }
        if lastFaceSampleAt == nil || now.timeIntervalSince(lastFaceSampleAt!) >= 1.0 {
            lastFaceSampleAt = now
            let t = startedAt.map { now.timeIntervalSince($0) } ?? 0
            let present = frame.anchors.contains { $0 is ARFaceAnchor }
            faceTimeline.append(FacePresence(t: t, present: present))
        }
    }

    private func saveKeyframe(from pixelBuffer: CVPixelBuffer) {
        let ci = CIImage(cvPixelBuffer: pixelBuffer)
        // Rotate to portrait; ARKit gives the buffer in landscape-right orientation.
        let oriented = ci.oriented(.right)
        guard let cg = ciContext.createCGImage(oriented, from: oriented.extent) else { return }
        let ui = UIImage(cgImage: cg)
        guard let jpeg = ui.jpegData(compressionQuality: 0.7) else { return }

        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("scan-\(UUID().uuidString).jpg")
        do {
            try jpeg.write(to: url)
            keyframeURLs.append(url)
            keyframeCount = keyframeURLs.count
        } catch {
            // best effort; drop the keyframe
        }
    }
}

extension ARSpaceScanner: ARSessionDelegate {
    nonisolated func session(_ session: ARSession, didUpdate frame: ARFrame) {
        Task { @MainActor in
            self.sampleIfNeeded(frame)
        }
    }
}
