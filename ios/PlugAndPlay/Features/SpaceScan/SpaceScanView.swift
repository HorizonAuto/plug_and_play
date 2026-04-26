import ARKit
import SwiftUI

struct SpaceScanView: View {
    @StateObject private var vm = SpaceScanViewModel()

    var body: some View {
        ZStack {
            ARPreview(session: vm.scanner.session)
                .ignoresSafeArea()

            VStack {
                topBar
                    .padding(.horizontal)
                    .padding(.top, 8)
                Spacer()
                controlBar
                    .padding(.horizontal)
                    .padding(.bottom, 24)
            }
        }
        .onAppear { vm.prepare() }
        .sheet(isPresented: bindingFinished) {
            if case .finished(let response) = vm.phase {
                SpaceResultView(response: response, onDone: { vm.reset() })
            }
        }
        .alert("Scan failed", isPresented: bindingFailed, actions: {
            Button("OK") { vm.reset() }
        }, message: {
            if case .failed(let msg) = vm.phase { Text(msg) }
        })
    }

    private var topBar: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Space scan").font(.subheadline.bold())
            Text("Walk through the room — sweep the camera over every wall and exit so the LiDAR mesh fills in.")
                .font(.caption)
            HStack(spacing: 12) {
                Label("\(vm.scanner.keyframeCount) keyframes", systemImage: "photo.stack")
                Label("\(vm.scanner.meshFaceCount) mesh faces", systemImage: "cube")
            }
            .font(.caption2)
            .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private var controlBar: some View {
        HStack {
            switch vm.phase {
            case .idle:
                Spacer()
                Button(action: vm.start) {
                    Circle().fill(.green)
                        .frame(width: 76, height: 76)
                        .overlay(
                            Image(systemName: "play.fill")
                                .font(.title)
                                .foregroundStyle(.white)
                        )
                        .overlay(Circle().stroke(.white, lineWidth: 4).padding(2))
                }
                Spacer()
            case .scanning:
                Spacer()
                Button(action: vm.stop) {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(.red)
                        .frame(width: 36, height: 36)
                        .padding(20)
                        .background(Circle().stroke(.white, lineWidth: 4))
                }
                Spacer()
            case .uploading:
                ProgressView()
                Text("Analyzing scan…").font(.callout)
            case .finished, .failed:
                EmptyView()
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private var bindingFinished: Binding<Bool> {
        Binding(
            get: { if case .finished = vm.phase { true } else { false } },
            set: { _ in }
        )
    }

    private var bindingFailed: Binding<Bool> {
        Binding(
            get: { if case .failed = vm.phase { true } else { false } },
            set: { _ in }
        )
    }
}

private struct ARPreview: UIViewRepresentable {
    let session: ARSession

    func makeUIView(context: Context) -> ARSCNView {
        let view = ARSCNView(frame: .zero)
        view.session = session
        view.automaticallyUpdatesLighting = true
        view.debugOptions = [.showFeaturePoints]
        return view
    }

    func updateUIView(_ uiView: ARSCNView, context: Context) {}
}

struct SpaceResultView: View {
    let response: SpaceVerifyResponse
    let onDone: () -> Void

    var body: some View {
        NavigationStack {
            List {
                Section("Underwriting") {
                    HStack {
                        Text("Score")
                        Spacer()
                        Text("\(response.underwriting.score) / 100")
                            .font(.title3.bold())
                            .foregroundStyle(scoreColor)
                    }
                    ForEach(response.underwriting.notes, id: \.self) { note in
                        Text(note).font(.caption).foregroundStyle(.secondary)
                    }
                }

                Section("Hazard report") {
                    LabeledContent("Fire extinguishers", value: "\(response.hazards.fireExtinguishers.count)")
                    LabeledContent("Exit signs", value: "\(response.hazards.exitSigns.count)")
                    LabeledContent("Exits unobstructed", value: response.hazards.exitsUnobstructed ? "Yes" : "No")
                    LabeledContent("Lighting", value: response.hazards.lightingAdequacy)
                    LabeledContent("Clutter (0-1)", value: String(format: "%.2f", response.hazards.clutterScore))
                    LabeledContent("Estimated area", value: String(format: "%.0f m²", response.hazards.estimatedFloorAreaSqm))
                    if !response.hazards.summary.isEmpty {
                        Text(response.hazards.summary).font(.caption).foregroundStyle(.secondary)
                    }
                }

                if !response.hazards.slipTripHazards.isEmpty {
                    Section("Slip / trip hazards") {
                        ForEach(response.hazards.slipTripHazards) { hz in
                            VStack(alignment: .leading, spacing: 2) {
                                HStack {
                                    Text(hz.description).font(.subheadline)
                                    Spacer()
                                    if let sev = hz.severity {
                                        Text(sev.uppercased())
                                            .font(.caption2.bold())
                                            .padding(.horizontal, 6).padding(.vertical, 2)
                                            .background(severityColor(sev).opacity(0.2), in: Capsule())
                                            .foregroundStyle(severityColor(sev))
                                    }
                                }
                                Text("frame \(hz.frameIndex)").font(.caption2).foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                if let urls = response.annotatedKeyframeUrls, !urls.isEmpty {
                    Section("Annotated keyframes") {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 10) {
                                ForEach(urls, id: \.self) { path in
                                    annotatedThumbnail(path: path)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                        .listRowInsets(EdgeInsets())
                        .padding(.horizontal, 16)
                        Text("Green = safety equipment Claude identified · red = hazards. Boxes are AI-estimated; trust the *frame*, double-check the *position*.")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Anti-cheat") {
                    ForEach(response.anticheat) { result in
                        antiCheatRow(result)
                    }
                }

                Section("Capture") {
                    LabeledContent("Duration", value: String(format: "%.1fs", response.durationSeconds))
                    LabeledContent("Keyframes analyzed", value: "\(response.keyframeCount)")
                }
            }
            .navigationTitle("Scan result")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done", action: onDone)
                }
            }
        }
    }

    private func antiCheatRow(_ result: AntiCheatResult) -> some View {
        let icon: String
        let color: Color
        switch result.passed {
        case .some(true):  icon = "checkmark.seal.fill";       color = .green
        case .some(false): icon = "xmark.seal.fill";            color = .red
        case nil:          icon = "questionmark.circle.fill";   color = .secondary
        }
        return VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: icon).foregroundStyle(color)
                Text(displayName(result.check)).font(.subheadline.weight(.medium))
            }
            Text(result.reason).font(.caption).foregroundStyle(.secondary)
        }
    }

    private func displayName(_ check: String) -> String {
        switch check {
        case "face_continuity":   return "Operator face visible (front cam)"
        case "mesh_coverage":     return "LiDAR coverage"
        default:                  return check.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    private func severityColor(_ s: String) -> Color {
        switch s.lowercased() {
        case "high":   return .red
        case "medium": return .orange
        case "low":    return .yellow
        default:       return .secondary
        }
    }

    private var backendBaseURL: String {
        UserDefaults.standard.string(forKey: "backendBaseURL") ?? "http://localhost:8000"
    }

    private static let thumbWidth: CGFloat = 340
    private static let thumbHeight: CGFloat = 460

    @ViewBuilder
    private func annotatedThumbnail(path: String) -> some View {
        let absolute = URL(string: backendBaseURL.trimmingCharacters(in: .init(charactersIn: "/")) + path)
        AnnotatedThumbnailView(url: absolute, width: Self.thumbWidth, height: Self.thumbHeight)
    }

    private var scoreColor: Color {
        switch response.underwriting.score {
        case 80...:    return .green
        case 60..<80:  return .yellow
        default:       return .red
        }
    }
}

/// AsyncImage replacement: explicit URLSession load with retry + diagnostic
/// failure state. AsyncImage on newer iOS sometimes silently fails on first
/// load over flaky tunnels; this gives us the actual error string on screen.
private struct AnnotatedThumbnailView: View {
    let url: URL?
    let width: CGFloat
    let height: CGFloat

    @State private var image: UIImage?
    @State private var error: String?
    @State private var attempt: Int = 0

    var body: some View {
        let frame = RoundedRectangle(cornerRadius: 14)
        Group {
            if let image {
                Image(uiImage: image).resizable().scaledToFit()
                    .frame(width: width, height: height)
                    .background(Color.black, in: frame)
                    .clipShape(frame)
            } else if let error {
                VStack(spacing: 8) {
                    Image(systemName: "photo.badge.exclamationmark")
                        .font(.title)
                        .foregroundStyle(.secondary)
                    Text(error)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .lineLimit(4)
                    if let url {
                        Text(url.absoluteString)
                            .font(.caption2.monospaced())
                            .foregroundStyle(.tertiary)
                            .lineLimit(3)
                            .truncationMode(.middle)
                    }
                    Text("Tap to retry")
                        .font(.caption2.bold())
                        .foregroundStyle(.blue)
                }
                .padding(12)
                .frame(width: width, height: height)
                .background(.gray.opacity(0.15), in: frame)
                .onTapGesture { attempt += 1 }
            } else {
                ProgressView()
                    .frame(width: width, height: height)
                    .background(.gray.opacity(0.15), in: frame)
            }
        }
        .task(id: "\(url?.absoluteString ?? "")|\(attempt)") {
            await load()
        }
    }

    private func load() async {
        guard let url else {
            error = "URL is nil"
            return
        }
        image = nil
        error = nil
        do {
            var req = URLRequest(url: url)
            req.timeoutInterval = 20
            req.cachePolicy = .reloadIgnoringLocalCacheData
            let (data, response) = try await URLSession.shared.data(for: req)
            guard let http = response as? HTTPURLResponse else {
                error = "non-HTTP response"
                return
            }
            guard (200..<300).contains(http.statusCode) else {
                error = "HTTP \(http.statusCode)"
                return
            }
            guard let ui = UIImage(data: data) else {
                error = "decoded \(data.count) bytes but not a valid image (content-type \(http.value(forHTTPHeaderField: "Content-Type") ?? "?"))"
                return
            }
            image = ui
        } catch {
            self.error = error.localizedDescription
        }
    }
}
