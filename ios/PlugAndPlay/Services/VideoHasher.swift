import CryptoKit
import Foundation

enum VideoHasher {
    /// SHA-256 of the entire captured file. Streamed in 1 MB chunks so large
    /// space-scan clips don't have to fit in memory. See backend hash_verify.py
    /// for the limitation: this catches post-upload tampering only.
    static func sha256(of url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }

        var hasher = SHA256()
        let chunkSize = 1 << 20
        while true {
            let data = try handle.read(upToCount: chunkSize) ?? Data()
            if data.isEmpty { break }
            hasher.update(data: data)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }
}
