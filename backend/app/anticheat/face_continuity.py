def check(face_timeline: list[dict]) -> dict:
    """Verify the front camera saw the operator's face for most of the scan.

    Expects 1-Hz samples with shape {t: float, present: bool}. A genuine
    walk-through has the operator looking at (or near) the device most of
    the time. Long absences imply a propped phone or a relayed video.
    """
    if not face_timeline:
        return {"check": "face_continuity", "passed": None, "reason": "no face timeline samples"}

    total = len(face_timeline)
    present = sum(1 for s in face_timeline if s.get("present"))
    ratio = present / total

    if total < 5:
        return {
            "check": "face_continuity",
            "passed": None,
            "reason": f"only {total} samples — scan too short to assess",
            "ratio": round(ratio, 2),
        }

    threshold = 0.5
    return {
        "check": "face_continuity",
        "passed": ratio >= threshold,
        "reason": f"face anchor present in {ratio*100:.0f}% of samples (threshold {int(threshold*100)}%)",
        "ratio": round(ratio, 2),
    }
