import subprocess
import tempfile
from functools import lru_cache

import imageio_ffmpeg


def extract_mono_wav(video_path: str) -> str:
    """Pull the audio track out of an mp4/webm and return a 16 kHz mono WAV path
    suitable for Whisper. Returns empty string if the source has no audio."""
    fd, out_path = tempfile.mkstemp(suffix=".wav", prefix="audio_")
    import os
    os.close(fd)

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.run(
        [ff, "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000",
         "-f", "wav", "-loglevel", "error", out_path],
        capture_output=True,
    )
    if proc.returncode != 0:
        try:
            os.unlink(out_path)
        except OSError:
            pass
        return ""
    if os.path.getsize(out_path) < 1024:  # essentially silent / empty
        try:
            os.unlink(out_path)
        except OSError:
            pass
        return ""
    return out_path


@lru_cache(maxsize=1)
def get_whisper():
    # tiny.en: ~75 MB, English-only, fast on CPU. Plenty for short alphanumeric codes.
    from faster_whisper import WhisperModel
    return WhisperModel("tiny.en", device="cpu", compute_type="int8")


def transcribe(wav_path: str) -> str:
    if not wav_path:
        return ""
    model = get_whisper()
    segments, _ = model.transcribe(wav_path, beam_size=5, vad_filter=True)
    return " ".join(seg.text for seg in segments).strip()
