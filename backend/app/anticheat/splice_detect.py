import base64

import cv2
import numpy as np

from app.services.video_frames import Keyframe


def _phash(img_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(resized)
    block = dct[:8, :8].copy()
    block[0, 0] = 0  # drop DC component
    median = np.median(block)
    return (block > median).astype(np.uint8).flatten()


def _hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.sum(a != b))


def _decode(kf: Keyframe) -> np.ndarray | None:
    raw = base64.b64decode(kf.jpeg_base64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def check(keyframes: list[Keyframe]) -> dict:
    if len(keyframes) < 2:
        return {
            "check": "splice_detection",
            "passed": None,
            "reason": "need at least 2 keyframes to compare",
        }

    hashes: list[np.ndarray] = []
    for kf in keyframes:
        img = _decode(kf)
        if img is None:
            continue
        hashes.append(_phash(img))

    if len(hashes) < 2:
        return {"check": "splice_detection", "passed": None, "reason": "could not decode keyframes"}

    diffs: list[int] = []
    for i in range(1, len(hashes)):
        diffs.append(_hamming(hashes[i - 1], hashes[i]))

    max_diff = max(diffs)
    mean_diff = float(sum(diffs)) / len(diffs)

    # 64-bit pHash; keyframes are evenly spaced across a several-second clip,
    # so consecutive samples typically diverge 5-25 bits. A diff > 40 between
    # adjacent samples implies a hard cut — likely splice.
    threshold = 40
    spliced = max_diff >= threshold
    return {
        "check": "splice_detection",
        "passed": not spliced,
        "reason": (
            f"max consecutive pHash distance {max_diff} (mean {mean_diff:.1f}) "
            + ("exceeds splice threshold" if spliced else "within continuity range")
        ),
        "max_phash_distance": max_diff,
        "mean_phash_distance": round(mean_diff, 1),
    }
