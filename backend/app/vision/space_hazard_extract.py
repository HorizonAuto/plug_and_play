import base64
import json

from app.vision.claude_client import DEFAULT_MODEL, get_client, image_block

DETECTION_ITEM = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "frame_index": {"type": "integer", "description": "0-based index into the keyframe array."},
        "bbox": {
            "type": "array",
            "items": {"type": "number"},
            "description": "Normalized [x, y, width, height] in 0.0-1.0 range, with origin at top-left. Tight box around the object.",
        },
        "confidence": {"type": "number", "description": "0.0-1.0 self-rated confidence in this identification."},
    },
    "required": ["frame_index", "bbox", "confidence"],
}

HAZARD_DETECTION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "frame_index": {"type": "integer"},
        "bbox": {
            "type": "array",
            "items": {"type": "number"},
            "description": "Normalized [x, y, width, height] in 0.0-1.0 range, top-left origin.",
        },
        "description": {"type": "string", "description": "One short sentence describing the specific hazard."},
        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["frame_index", "bbox", "description", "severity"],
}

HAZARD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "fire_extinguishers": {"type": "array", "items": DETECTION_ITEM},
        "exit_signs": {"type": "array", "items": DETECTION_ITEM},
        "exits_unobstructed": {"type": "boolean"},
        "slip_trip_hazards": {"type": "array", "items": HAZARD_DETECTION},
        "clutter_score": {"type": "number", "description": "0.0 (pristine) to 1.0 (severely overcrowded)."},
        "lighting_adequacy": {"type": "string", "enum": ["adequate", "marginal", "inadequate", "unknown"]},
        "estimated_floor_area_sqm": {"type": "number", "description": "Non-negative; 0 if not estimable."},
        "summary": {"type": "string"},
    },
    "required": [
        "fire_extinguishers",
        "exit_signs",
        "exits_unobstructed",
        "slip_trip_hazards",
        "clutter_score",
        "lighting_adequacy",
        "estimated_floor_area_sqm",
        "summary",
    ],
}


SYSTEM_PROMPT = """You are a commercial-property hazard inspector reviewing keyframes from a continuous LiDAR-equipped walk-through of a small business space (storefront, office, restaurant, gym, salon, etc.). Your goal is to produce an underwriting-grade hazard report that an annotator can render on top of the keyframes.

You will be given an ordered set of keyframes sampled from one continuous walk-through. Treat them as one tour - do not assume they are independent rooms unless the visual evidence makes that clear.

For every detection (extinguisher, exit sign, hazard) you MUST return:
- frame_index: the 0-based index of the keyframe where the item is most clearly visible (use that single index even if it appears in multiple frames; pick the clearest).
- bbox: [x, y, width, height] in normalized 0.0-1.0 coordinates with origin at the top-left of the keyframe. The box should tightly enclose the object. Do not extend beyond [0, 1]. If you can only roughly localize the object, still return a box - just make it cover the plausible region.
- confidence (for safety items): 0.0-1.0 reflecting how sure you are the object is what you think it is.
- severity (for hazards): "low" / "medium" / "high".

Output fields:
- fire_extinguishers: array of detections (one entry per distinct extinguisher you can localize). Don't double-count the same extinguisher seen from multiple angles.
- exit_signs: array of detections (illuminated or printed EXIT signs).
- exits_unobstructed: true if every visible exit/door appears clear of obstacles. If no exit is visible, set true and mention that in summary.
- slip_trip_hazards: array of hazard detections. Examples: loose cables crossing walkways, wet/oil spills, uneven flooring, raised thresholds without warning markings, rugs with curled edges, boxes/inventory in walking paths.
- clutter_score: 0.0 = pristine; 1.0 = severe overcrowding/hoarding. Most healthy small businesses are 0.1-0.4.
- lighting_adequacy: "adequate" if you can clearly see the space, "marginal" if some areas are visibly dim, "inadequate" if large portions are hard to make out, "unknown" if the keyframes don't show enough.
- estimated_floor_area_sqm: rough order-of-magnitude estimate of total walked area in square meters. Small storefront ~30, office floor ~80-150, small gym ~150-300. 0 if not estimable.
- summary: 2-3 short sentences summarizing the type of space and the overall risk picture.

Be conservative. If you cannot localize an item with even a rough bounding box, omit it from the array rather than fabricating one. Underwriting decisions get made off this output.

Respond with the JSON object only - no commentary."""


def extract_hazards(keyframe_jpegs_b64: list[str]) -> dict:
    if not keyframe_jpegs_b64:
        return {
            "fire_extinguishers": [],
            "exit_signs": [],
            "exits_unobstructed": True,
            "slip_trip_hazards": [],
            "clutter_score": 0.0,
            "lighting_adequacy": "unknown",
            "estimated_floor_area_sqm": 0.0,
            "summary": "No keyframes captured.",
        }

    client = get_client()
    user_content: list[dict] = [image_block(b64) for b64 in keyframe_jpegs_b64]
    user_content.append({
        "type": "text",
        "text": (
            f"The {len(keyframe_jpegs_b64)} keyframes above were sampled in order from one "
            "continuous walk-through. Produce the hazard report. Remember: every detection "
            "needs a frame_index AND a normalized bbox so we can draw it on the right keyframe."
        ),
    })

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4096,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": HAZARD_SCHEMA,
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
