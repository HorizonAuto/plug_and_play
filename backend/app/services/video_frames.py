import base64
from dataclasses import dataclass

import cv2
import imageio_ffmpeg as iio_ff
import numpy as np


@dataclass
class Keyframe:
    timestamp_seconds: float
    frame_index: int
    jpeg_base64: str


def _count_and_meta(path: str) -> tuple[int, float, int, int]:
    """Walk every frame once just to count. Cheap-ish; avoids decode buffering."""
    reader = iio_ff.read_frames(path)
    meta = next(reader)
    fps = float(meta.get("fps") or 30.0)
    width, height = meta.get("size", (0, 0))
    total = sum(1 for _ in reader)
    return total, fps, int(width), int(height)


def extract_keyframes(video_path: str, count: int = 4, jpeg_quality: int = 80) -> list[Keyframe]:
    total, fps, width, height = _count_and_meta(video_path)
    if total <= 0 or width <= 0 or height <= 0:
        raise ValueError("video has no decodable frames")

    sample_count = min(count, total)
    indices = set(int(i) for i in np.linspace(0, total - 1, sample_count, dtype=int).tolist())

    reader = iio_ff.read_frames(video_path)
    next(reader)  # skip metadata frame

    keyframes: list[Keyframe] = []
    for i, raw in enumerate(reader):
        if i not in indices:
            continue
        try:
            arr = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
        except ValueError:
            continue
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
        if not ok:
            continue
        keyframes.append(
            Keyframe(
                timestamp_seconds=i / fps,
                frame_index=i,
                jpeg_base64=base64.b64encode(buf.tobytes()).decode("ascii"),
            )
        )
        if len(keyframes) == sample_count:
            break

    if not keyframes:
        raise ValueError("could not decode any frames from video")
    return keyframes
