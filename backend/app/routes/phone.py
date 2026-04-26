import hashlib
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.anticheat import audio_challenge, hash_verify, light_consistency, splice_detect
from app.scoring.underwriting import score_phone_signal
from app.services.audio import extract_mono_wav, transcribe
from app.services.video_frames import extract_keyframes
from app.vision.phone_signal_extract import extract_signal

router = APIRouter(prefix="/verify", tags=["verify"])

# Persisted recordings live here. Mounted at /uploads/ in main.py.
# Cleanup is your job — these accumulate.
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


@router.post("/phone")
async def verify_phone(
    video: UploadFile = File(...),
    challenge_code: str | None = Form(default=None),
    client_hash: str | None = Form(default=None),
    gps_lat: str | None = Form(default=None),
    gps_lon: str | None = Form(default=None),
    captured_at: str | None = Form(default=None),
    keyframe_count: int = Form(default=4),
) -> dict:
    if video.content_type and not video.content_type.startswith("video/"):
        raise HTTPException(400, f"expected video/*, got {video.content_type}")

    suffix = os.path.splitext(video.filename or "")[1] or ".mp4"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix=f"capture_{uuid.uuid4().hex}_")
    persisted_url: str | None = None
    try:
        h = hashlib.sha256()
        with os.fdopen(fd, "wb") as f:
            while chunk := await video.read(1024 * 1024):
                f.write(chunk)
                h.update(chunk)

        # Persist the upload under its content hash so duplicate uploads coalesce.
        digest = h.hexdigest()
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        persisted_name = f"{ts}_{digest[:16]}{suffix}"
        persisted_path = UPLOADS_DIR / persisted_name
        if not persisted_path.exists():
            shutil.copyfile(tmp_path, persisted_path)
        persisted_url = f"/uploads/{persisted_name}"

        lat = _parse_float(gps_lat)
        lon = _parse_float(gps_lon)
        when = _parse_iso(captured_at)

        keyframes = extract_keyframes(tmp_path, count=keyframe_count)

        # Audio challenge: extract → transcribe → match against the displayed code.
        wav_path = extract_mono_wav(tmp_path)
        transcript = transcribe(wav_path) if wav_path else ""
        if wav_path:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

        anticheat_results = [
            hash_verify.verify(tmp_path, client_hash),
            splice_detect.check(keyframes),
            light_consistency.check(keyframes, lat, lon, when),
            audio_challenge.check(transcript, challenge_code),
        ]

        signal = extract_signal(keyframes)
        anticheat_results.append({
            "check": "physical_phone_visible",
            "passed": bool(signal.get("physical_phone_visible")),
            "reason": signal.get("extraction_notes", ""),
        })

        score = score_phone_signal(signal, anticheat_results)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return {
        "challenge_code": challenge_code,
        "keyframe_count": len(keyframes),
        "video_url": persisted_url,
        "signal": signal,
        "anticheat": anticheat_results,
        "underwriting": score,
    }
