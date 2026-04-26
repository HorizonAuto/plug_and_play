import os
from functools import lru_cache

from anthropic import Anthropic

DEFAULT_MODEL = "claude-sonnet-4-6"
FALLBACK_MODEL = "claude-opus-4-7"


@lru_cache(maxsize=1)
def get_client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return Anthropic(api_key=api_key)


def image_block(jpeg_base64: str) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": jpeg_base64,
        },
    }
