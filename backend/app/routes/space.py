import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.anticheat import face_continuity, mesh_coverage
from app.services.annotate_frames import annotate as annotate_frames
from app.vision.space_hazard_extract import extract_hazards

# Anthropic rejects very large requests (413). 60 frames at 1024 px long-edge
# JPEG-75 lands around ~9 MB base64 — safely under the per-request limit while
# still giving Claude dense temporal coverage. Annotation uses the originals.
MAX_FRAMES_TO_CLAUDE = 60
CLAUDE_LONG_EDGE_PX = 1024

router = APIRouter(prefix="/verify", tags=["verify"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        normalized = s.replace("Z", "+00:00") if s.endswith("Z") else s
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _parse_float(s: str | None) -> float | None:
    if s is None or s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


async def _read_json(upload: UploadFile) -> Any:
    raw = await upload.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(400, f"could not parse {upload.filename}: {e}")


def _score_space(hazards: dict, anticheat: list[dict]) -> dict:
    base = 100
    notes: list[str] = []

    for r in anticheat:
        if r.get("passed") is False:
            penalty = {"face_continuity": 25, "mesh_coverage": 20}.get(r["check"], 15)
            base -= penalty
            notes.append(f"FAIL {r['check']}: {r.get('reason', '')} (-{penalty})")
        elif r.get("passed") is None:
            notes.append(f"SKIP {r['check']}: {r.get('reason', '')}")

    if not hazards.get("exits_unobstructed", True):
        base -= 20
        notes.append("blocked exits (-20)")

    extinguishers = len(hazards.get("fire_extinguishers", []) or [])
    if extinguishers == 0:
        base -= 10
        notes.append("no fire extinguisher visible (-10)")

    clutter = float(hazards.get("clutter_score", 0.0))
    if clutter > 0.6:
        base -= 15
        notes.append(f"high clutter score {clutter:.2f} (-15)")

    slip_hazards = hazards.get("slip_trip_hazards", []) or []
    if slip_hazards:
        sev_weight = {"low": 3, "medium": 6, "high": 10}
        penalty = min(25, sum(sev_weight.get((h.get("severity") or "medium").lower(), 6) for h in slip_hazards))
        base -= penalty
        notes.append(f"{len(slip_hazards)} slip/trip hazard(s) (-{penalty})")

    if hazards.get("lighting_adequacy") == "inadequate":
        base -= 10
        notes.append("inadequate lighting (-10)")

    return {"score": max(0, min(100, base)), "notes": notes}


@router.post("/space")
async def verify_space(
    face_timeline: UploadFile = File(...),
    mesh_summary: UploadFile = File(...),
    keyframes: list[UploadFile] = File(...),
    duration_seconds: str | None = Form(default=None),
    captured_at: str | None = Form(default=None),
    gps_lat: str | None = Form(default=None),
    gps_lon: str | None = Form(default=None),
) -> dict:
    if not keyframes:
        raise HTTPException(400, "no keyframes uploaded")

    face_samples = await _read_json(face_timeline)
    if not isinstance(face_samples, list):
        raise HTTPException(400, "face_timeline must be a JSON array")

    mesh = await _read_json(mesh_summary)
    if not isinstance(mesh, dict):
        raise HTTPException(400, "mesh_summary must be a JSON object")

    # Persist keyframes under a per-scan directory so the user can audit
    # exactly what Claude was given. Naming: scan_<timestamp>_<digest>/kf_NN.jpg
    scan_id_hasher = hashlib.sha256()
    raw_frames: list[bytes] = []
    for kf in keyframes:
        raw = await kf.read()
        if raw:
            raw_frames.append(raw)
            scan_id_hasher.update(raw)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    scan_dir_name = f"scan_{ts}_{scan_id_hasher.hexdigest()[:12]}"
    scan_dir = UPLOADS_DIR / scan_dir_name
    scan_dir.mkdir(exist_ok=True)
    keyframe_urls: list[str] = []
    for idx, raw in enumerate(raw_frames):
        path = scan_dir / f"kf_{idx:02d}.jpg"
        path.write_bytes(raw)
        keyframe_urls.append(f"/uploads/{scan_dir_name}/{path.name}")

    # Pick a small, evenly-spaced subset for Claude. Track the mapping so we
    # can rewrite frame_index in the response back to the original positions.
    n_orig = len(raw_frames)
    if n_orig <= MAX_FRAMES_TO_CLAUDE:
        selected_orig_indices = list(range(n_orig))
    else:
        step = (n_orig - 1) / (MAX_FRAMES_TO_CLAUDE - 1)
        selected_orig_indices = [int(round(i * step)) for i in range(MAX_FRAMES_TO_CLAUDE)]

    keyframe_b64: list[str] = []
    for orig_idx in selected_orig_indices:
        arr = np.frombuffer(raw_frames[orig_idx], dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]
        long_side = max(h, w)
        if long_side > CLAUDE_LONG_EDGE_PX:
            scale = CLAUDE_LONG_EDGE_PX / long_side
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if ok:
            keyframe_b64.append(base64.b64encode(buf.tobytes()).decode("ascii"))

    anticheat_results = [
        face_continuity.check(face_samples),
        mesh_coverage.check(mesh),
    ]

    hazards = extract_hazards(keyframe_b64)

    # Claude sees a subset; rewrite each detection's frame_index back to the
    # original position so annotate_frames finds the right kf_NN.jpg on disk.
    for key in ("fire_extinguishers", "exit_signs", "slip_trip_hazards"):
        for item in hazards.get(key) or []:
            sub = int(item.get("frame_index", 0))
            if 0 <= sub < len(selected_orig_indices):
                item["frame_index"] = selected_orig_indices[sub]

    annotated_urls = annotate_frames(scan_dir, hazards)
    score = _score_space(hazards, anticheat_results)

    return {
        "duration_seconds": _parse_float(duration_seconds) or 0.0,
        "keyframe_count": len(keyframe_b64),
        "captured_at": captured_at,
        "gps": {"lat": _parse_float(gps_lat), "lon": _parse_float(gps_lon)},
        "hazards": hazards,
        "anticheat": anticheat_results,
        "underwriting": score,
        "scan_id": scan_dir_name,
        "keyframe_urls": keyframe_urls,
        "annotated_keyframe_urls": annotated_urls,
    }
