from pathlib import Path

import cv2

# BGR (OpenCV convention).
GOOD = (60, 200, 60)   # green for safety equipment
BAD = (60, 60, 220)    # red for hazards

SEVERITY_COLOR = {
    "low":    (60, 180, 220),    # amber
    "medium": (40, 110, 230),    # orange-red
    "high":   (40, 40, 230),     # deep red
}


def _denormalize(bbox: list, w: int, h: int) -> tuple[int, int, int, int] | None:
    if not bbox or len(bbox) != 4:
        return None
    x, y, bw, bh = bbox
    # Heuristic: if values look like 0..1, treat as normalized. Otherwise pixels.
    if max(abs(x), abs(y), abs(bw), abs(bh)) <= 1.5:
        x1 = int(max(0, min(1, x)) * w)
        y1 = int(max(0, min(1, y)) * h)
        x2 = int(max(0, min(1, x + bw)) * w)
        y2 = int(max(0, min(1, y + bh)) * h)
    else:
        x1, y1 = int(x), int(y)
        x2, y2 = int(x + bw), int(y + bh)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _draw(img, color, label: str, box: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 4)
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    bar_y1 = max(0, y1 - th - 12)
    cv2.rectangle(img, (x1, bar_y1), (x1 + tw + 10, y1), color, -1)
    cv2.putText(img, label, (x1 + 5, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)


def annotate(scan_dir: Path, hazards: dict) -> list[str]:
    """Render bounding boxes from `hazards` onto the keyframes saved under `scan_dir`.

    Returns a list of `/uploads/<scan_dir>/<file>` URL paths (one per frame that
    received any annotation). Frames without annotations are NOT returned — the
    UI uses this list directly so unannotated frames stay hidden.
    """
    by_frame: dict[int, list[tuple]] = {}

    for item in hazards.get("fire_extinguishers", []) or []:
        idx = item.get("frame_index")
        if idx is None:
            continue
        by_frame.setdefault(int(idx), []).append((GOOD, "extinguisher", item.get("bbox")))

    for item in hazards.get("exit_signs", []) or []:
        idx = item.get("frame_index")
        if idx is None:
            continue
        by_frame.setdefault(int(idx), []).append((GOOD, "exit", item.get("bbox")))

    for item in hazards.get("slip_trip_hazards", []) or []:
        idx = item.get("frame_index")
        if idx is None:
            continue
        sev = (item.get("severity") or "medium").lower()
        color = SEVERITY_COLOR.get(sev, BAD)
        # Truncate description so the label bar doesn't run off the frame.
        desc = (item.get("description") or "hazard").strip()
        label = desc if len(desc) <= 36 else desc[:33] + "…"
        by_frame.setdefault(int(idx), []).append((color, label, item.get("bbox")))

    annotated_urls: list[str] = []
    for idx in sorted(by_frame.keys()):
        src = scan_dir / f"kf_{idx:02d}.jpg"
        if not src.exists():
            continue
        img = cv2.imread(str(src))
        if img is None:
            continue
        h, w = img.shape[:2]
        for color, label, bbox in by_frame[idx]:
            box = _denormalize(bbox, w, h)
            if box is None:
                continue
            _draw(img, color, label, box)
        dst = scan_dir / f"kf_{idx:02d}_annotated.jpg"
        if cv2.imwrite(str(dst), img):
            annotated_urls.append(f"/uploads/{scan_dir.name}/{dst.name}")

    return annotated_urls
