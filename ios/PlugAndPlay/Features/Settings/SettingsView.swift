import SwiftUI

struct SettingsView: View {
    @AppStorage("backendBaseURL") private var backendBaseURL: String = "http://localhost:8000"
    @AppStorage("demoMode") private var demoMode: Bool = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Backend") {
                    TextField("Base URL", text: $backendBaseURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Text("Use your laptop's LAN IP for on-device demos, e.g. `http://192.168.1.42:8000`.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Section("Demo mode") {
                    Toggle("Skip backend, return canned response", isOn: $demoMode)
                    Text("When on, captures still record locally but the result screens are populated from a fixture. Useful when conference Wi-Fi misbehaves during a demo.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Section("About") {
                    LabeledContent("Build", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?")
                }
            }
            .navigationTitle("Settings")
        }
    }
}

#Preview {
    SettingsView()
}
