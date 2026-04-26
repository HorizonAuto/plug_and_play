import hashlib


# File-level SHA-256 catches post-upload tampering only. A full anti-forgery
# layer needs a per-frame rolling hash bound to the camera capture pipeline,
# so an attacker would have to forge frames in real time. See plan §Feature 1.
def sha256_file(path: str, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def verify(path: str, claimed_hex: str | None) -> dict:
    actual = sha256_file(path)
    if not claimed_hex:
        return {"check": "hash", "passed": None, "reason": "no client hash provided", "actual": actual}
    matched = actual.lower() == claimed_hex.lower()
    return {
        "check": "hash",
        "passed": matched,
        "reason": "matches client hash" if matched else "client hash mismatch",
        "actual": actual,
        "claimed": claimed_hex,
    }
