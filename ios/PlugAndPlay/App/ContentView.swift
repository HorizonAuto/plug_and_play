import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            SpaceScanView()
                .tabItem { Label("Space", systemImage: "cube.transparent") }

            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}

#Preview {
    ContentView()
}
