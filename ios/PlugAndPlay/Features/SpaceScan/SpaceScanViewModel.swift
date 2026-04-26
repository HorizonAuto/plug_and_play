import Foundation

@MainActor
final class SpaceScanViewModel: ObservableObject {
    enum Phase {
        case idle
        case scanning
        case uploading
        case finished(SpaceVerifyResponse)
        case failed(String)
    }

    @Published var phase: Phase = .idle
    let scanner = ARSpaceScanner()
    private var artifacts: SpaceScanArtifacts?

    /// Brings up the AR camera preview as soon as the view appears.
    /// On non-Pro devices this fails fast and surfaces the error so the user
    /// understands why the screen is black, instead of just showing a blank feed.
    func prepare() {
        do {
            try scanner.startPreview()
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    func start() {
        do {
            try scanner.startRecording()
            phase = .scanning
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    func stop() {
        Task {
            do {
                let bundle = try scanner.stopRecording()
                artifacts = bundle
                phase = .uploading

                async let location = LocationService.shared.fetchOnce()
                let loc = await location

                let request = SpaceVerifyRequest(
                    keyframes: bundle.keyframes,
                    faceTimeline: bundle.faceTimeline,
                    meshSummary: bundle.meshSummary,
                    durationSeconds: bundle.durationSeconds,
                    location: loc,
                    capturedAt: Date()
                )
                let response = try await BackendClient.shared.verifySpace(request)
                phase = .finished(response)
            } catch {
                phase = .failed(error.localizedDescription)
            }
        }
    }

    func reset() {
        if let bundle = artifacts { scanner.cleanup(bundle) }
        artifacts = nil
        phase = .idle
    }
}
