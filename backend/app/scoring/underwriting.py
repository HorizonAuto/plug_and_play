from typing import Any


def score_phone_signal(
    signal: dict[str, Any],
    anticheat_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base = 100
    notes: list[str] = []

    for result in anticheat_results or []:
        check = result.get("check", "?")
        passed = result.get("passed")
        reason = result.get("reason", "")
        if passed is False:
            penalty = {
                "hash": 30,
                "splice_detection": 30,
                "physical_phone_visible": 35,
                "audio_challenge": 35,
            }.get(check, 20)
            base -= penalty
            notes.append(f"FAIL {check}: {reason} (-{penalty})")
        elif passed is None:
            notes.append(f"SKIP {check}: {reason}")

    confidence = float(signal.get("confidence") or 0.0)
    if confidence < 0.6:
        base -= 20
        notes.append(f"low extraction confidence {confidence:.2f} (-20)")

    platform = signal.get("platform")
    signal_type = signal.get("signal_type")
    value = signal.get("value")

    if platform in {"uber", "lyft"} and signal_type == "driver_rating" and isinstance(value, (int, float)):
        if value >= 4.9:
            base += 5
            notes.append(f"driver rating {value} (>=4.9, +5)")
        elif value < 4.7:
            base -= 10
            notes.append(f"driver rating {value} (<4.7, -10)")
    elif platform == "duolingo" and signal_type == "streak_days" and isinstance(value, (int, float)):
        if value >= 100:
            base += 5
            notes.append(f"duolingo streak {int(value)}d (>=100, +5)")

    return {
        "score": max(0, min(100, base)),
        "notes": notes,
    }
