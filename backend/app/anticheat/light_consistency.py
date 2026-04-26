import base64
from datetime import datetime

import cv2
import numpy as np

from app.anticheat.solar import solar_elevation_degrees
from app.services.video_frames import Keyframe


def _mean_luminance_from_keyframe(kf: Keyframe) -> float:
    raw = base64.b64decode(kf.jpeg_base64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return float("nan")
    return float(img.mean())  # 0..255


def check(
    keyframes: list[Keyframe],
    lat: float | None,
    lon: float | None,
    captured_at: datetime | None,
) -> dict:
    luminances = [_mean_luminance_from_keyframe(kf) for kf in keyframes]
    luminances = [x for x in luminances if not (x != x)]  # drop NaN
    mean_lum = float(sum(luminances) / len(luminances)) if luminances else 0.0

    if lat is None or lon is None or captured_at is None:
        return {
            "check": "light_consistency",
            "passed": None,
            "reason": "no GPS/timestamp provided to cross-check",
            "mean_luminance_0_255": round(mean_lum, 1),
        }

    elevation = solar_elevation_degrees(lat, lon, captured_at)

    # Heuristic thresholds. Indoor lighting at night still produces ~80-150
    # luminance, so we only flag the egregious case: sun well below horizon
    # AND a very bright frame (claiming daylight while the sun is gone), or
    # sun well above horizon AND a very dark frame (claiming midday darkness).
    if elevation < -10 and mean_lum > 200:
        passed = False
        reason = (
            f"sun is {elevation:.1f}° below horizon but frames are bright "
            f"(mean luminance {mean_lum:.0f}/255) — claimed location/time inconsistent"
        )
    elif elevation > 30 and mean_lum < 25:
        passed = False
        reason = (
            f"sun is {elevation:.1f}° above horizon but frames are nearly black "
            f"(mean luminance {mean_lum:.0f}/255) — claimed location/time inconsistent"
        )
    else:
        passed = True
        reason = (
            f"luminance {mean_lum:.0f}/255 plausible for solar elevation {elevation:.1f}°"
        )

    return {
        "check": "light_consistency",
        "passed": passed,
        "reason": reason,
        "mean_luminance_0_255": round(mean_lum, 1),
        "solar_elevation_deg": round(elevation, 2),
    }
