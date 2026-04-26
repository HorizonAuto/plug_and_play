import json

from app.services.video_frames import Keyframe
from app.vision.claude_client import DEFAULT_MODEL, get_client, image_block

PHONE_SIGNAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "platform": {
            "type": "string",
            "enum": ["uber", "lyft", "duolingo", "spotify", "oura", "apple_health", "unknown"],
            "description": "Which app/dataset is visible on the captured phone screen.",
        },
        "signal_type": {
            "type": "string",
            "enum": [
                "driver_rating",
                "rider_rating",
                "streak_days",
                "minutes_listened",
                "sleep_score",
                "step_count",
                "unknown",
            ],
            "description": "Which underwriting-relevant metric was extracted.",
        },
        "value": {
            "type": ["number", "string", "null"],
            "description": "The numeric or short string value of the signal (e.g. 4.92, 137, '8h 12m'). Null if unreadable.",
        },
        "confidence": {
            "type": "number",
            "description": "Model confidence the value was correctly read off the screen, between 0.0 and 1.0.",
        },
        "physical_phone_visible": {
            "type": "boolean",
            "description": "True if a physical phone (with bezel/hand/reflection) is clearly visible in frame, indicating a live capture rather than a screen-within-a-screen.",
        },
        "extraction_notes": {
            "type": "string",
            "description": "Short human-readable note: what was visible, what was occluded, why confidence is what it is.",
        },
    },
    "required": [
        "platform",
        "signal_type",
        "value",
        "confidence",
        "physical_phone_visible",
        "extraction_notes",
    ],
}


SYSTEM_PROMPT = """You are an underwriting-signal extraction model for a tamper-proof self-capture insurance product. The user is recording a short live video by pointing one phone's camera at another phone whose screen shows an app (Uber, Lyft, Duolingo, Spotify, Oura, Apple Health). Your job is to read the underwriting-relevant metric off that captured screen and report it as structured data.

You will be given a small ordered set of keyframes from a single continuous video. Treat them as evidence about the same scene at different moments in time.

Per platform, the underwriting-relevant signal is:
- Uber / Lyft: driver_rating (0.00-5.00) if the driver-rating screen is visible; rider_rating if a rider profile is visible.
- Duolingo: streak_days (integer) shown on the streak indicator (flame icon).
- Spotify: minutes_listened (integer minutes) from a Wrapped or stats screen.
- Oura: sleep_score (0-100) from the Readiness or Sleep tab.
- Apple Health: step_count (integer) from the Activity or Steps tab.

Reading rules:
1. Only report a value you can clearly read off the captured phone screen in the frames. Do not infer, guess, or extrapolate. If the value is partially occluded, blurry, cropped, or scrolled past, set value=null and explain in extraction_notes.
2. confidence reflects only how confidently you read the digits/text - not whether the recording is genuine. A perfectly-legible 4.92 is confidence ~0.95+; a grainy partial read is ~0.4-0.6.
3. If the screen does not show one of the supported platforms or none of the supported metrics is visible, set platform=unknown and signal_type=unknown.

Live-capture vs screen-within-a-screen:
A live capture should show a physical phone in the frame: bezel edges, a hand holding it, screen glare, off-axis perspective, or background context (desk, room, the recording device's own reflection). A faked capture often shows a fullscreen recording of an app with no bezel and no surrounding context, or a screen-of-a-screen with visible moiré/scanlines.
- Set physical_phone_visible=true ONLY if at least one of: visible bezel, visible hand/fingers gripping the phone, off-axis perspective with depth cues, or environmental context that proves a separate physical device is being filmed.
- Set physical_phone_visible=false if the frames look like a fullscreen app recording, a screen-of-a-screen with visible scanlines/moiré, or anything that could plausibly be a forwarded screen recording.
- When in doubt, set physical_phone_visible=false. False positives here defeat the entire anti-cheat layer.

extraction_notes should be one or two short sentences in plain English. Mention what platform/screen you saw, what value you read, and what specifically made you set physical_phone_visible the way you did.

Output JSON conforming exactly to the provided schema. Do not include any commentary outside the JSON."""


def extract_signal(keyframes: list[Keyframe]) -> dict:
    client = get_client()

    user_content: list[dict] = []
    for kf in keyframes:
        user_content.append(image_block(kf.jpeg_base64))
    user_content.append(
        {
            "type": "text",
            "text": (
                f"The {len(keyframes)} keyframes above were sampled from a single continuous "
                "video clip captured live. Read the underwriting-relevant signal off the phone "
                "screen in those frames and assess whether a physical phone (not a screen "
                "recording) is visible. Respond with the JSON object only."
            ),
        }
    )

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": PHONE_SIGNAL_SCHEMA,
            }
        },
        messages=[{"role": "user", "content": user_content}],
    )

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise RuntimeError("model returned no text block")

    parsed = json.loads(text)
    parsed["_usage"] = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
        "cache_creation_input_tokens": getattr(
            response.usage, "cache_creation_input_tokens", 0
        ),
    }
    return parsed
