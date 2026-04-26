import CoreLocation
import Foundation

struct LocationFix: Equatable {
    let latitude: Double
    let longitude: Double
    let timestamp: Date
}

@MainActor
final class LocationService: NSObject {
    static let shared = LocationService()

    private let manager = CLLocationManager()
    private var continuation: CheckedContinuation<LocationFix?, Never>?

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    /// One-shot fix. Returns nil if permission denied, location services off, or no fix in 5s.
    func fetchOnce(timeout: TimeInterval = 5.0) async -> LocationFix? {
        switch manager.authorizationStatus {
        case .notDetermined:
            manager.requestWhenInUseAuthorization()
        case .denied, .restricted:
            return nil
        default:
            break
        }

        if let cached = manager.location, Date().timeIntervalSince(cached.timestamp) < 30 {
            return LocationFix(
                latitude: cached.coordinate.latitude,
                longitude: cached.coordinate.longitude,
                timestamp: cached.timestamp
            )
        }

        return await withTaskGroup(of: LocationFix?.self) { group in
            group.addTask { @MainActor [weak self] in
                guard let self else { return nil }
                return await withCheckedContinuation { (cont: CheckedContinuation<LocationFix?, Never>) in
                    self.continuation = cont
                    self.manager.requestLocation()
                }
            }
            group.addTask {
                try? await Task.sleep(for: .seconds(timeout))
                return nil
            }
            let first = await group.next() ?? nil
            group.cancelAll()
            return first
        }
    }
}

extension LocationService: CLLocationManagerDelegate {
    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        Task { @MainActor in
            guard let loc = locations.last else { return }
            let fix = LocationFix(
                latitude: loc.coordinate.latitude,
                longitude: loc.coordinate.longitude,
                timestamp: loc.timestamp
            )
            self.continuation?.resume(returning: fix)
            self.continuation = nil
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in
            self.continuation?.resume(returning: nil)
            self.continuation = nil
        }
    }
}
