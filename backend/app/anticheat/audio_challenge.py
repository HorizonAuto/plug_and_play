import re

# When users speak a 4-character alphanumeric code aloud, Whisper transcribes
# the spoken digits and NATO-phonetic letters as words. Map the words back
# to characters before doing a substring match against the expected code.
_WORD_TO_CHAR: dict[str, str] = {
    "ZERO": "0", "OH": "0", "O": "0",
    "ONE": "1", "TWO": "2", "TO": "2", "TOO": "2",
    "THREE": "3", "FOUR": "4", "FOR": "4",
    "FIVE": "5", "SIX": "6", "SEVEN": "7",
    "EIGHT": "8", "ATE": "8", "NINE": "9",
    # NATO phonetic alphabet — common when reading codes aloud.
    "ALPHA": "A", "BRAVO": "B", "CHARLIE": "C", "DELTA": "D",
    "ECHO": "E", "FOXTROT": "F", "GOLF": "G", "HOTEL": "H",
    "INDIA": "I", "JULIET": "J", "JULIETT": "J", "KILO": "K",
    "LIMA": "L", "MIKE": "M", "NOVEMBER": "N", "OSCAR": "O",
    "PAPA": "P", "QUEBEC": "Q", "ROMEO": "R", "SIERRA": "S",
    "TANGO": "T", "UNIFORM": "U", "VICTOR": "V", "WHISKEY": "W",
    "WHISKY": "W", "XRAY": "X", "X-RAY": "X", "YANKEE": "Y", "ZULU": "Z",
    # Letters spelled phonetically when said as themselves.
    "BEE": "B", "SEE": "C", "GEE": "G", "JAY": "J",
    "KAY": "K", "EM": "M", "EN": "N", "PEE": "P", "QUE": "Q", "CUE": "Q",
    "ARE": "R", "ESS": "S", "TEE": "T", "YOU": "U", "DOUBLEYOU": "W",
    "EX": "X", "WHY": "Y", "ZEE": "Z",
}

_TOKEN_RE = re.compile(r"[A-Za-z0-9'-]+")


def _normalize(text: str) -> str:
    """Squash a transcript to a stream of letters/digits the user *plausibly* said."""
    out: list[str] = []
    for tok in _TOKEN_RE.findall(text.upper()):
        tok = tok.replace("-", "").replace("'", "")
        if tok in _WORD_TO_CHAR:
            out.append(_WORD_TO_CHAR[tok])
        elif tok.isalnum():
            out.append(tok)
    return "".join(out)


def _is_subsequence(target: str, source: str) -> bool:
    """True iff every char of `target` appears in `source` in order (with arbitrary
    intervening characters). Whisper mangles single phonetic letters often enough
    ('Quebec' → 'quib-back', 'Mike' → 'mic') that strict substring match is too
    harsh; subsequence still requires the correct chars in the correct order."""
    si = 0
    for c in target:
        while si < len(source) and source[si] != c:
            si += 1
        if si >= len(source):
            return False
        si += 1
    return True


def check(transcript: str, expected_code: str | None) -> dict:
    if not expected_code:
        return {"check": "audio_challenge", "passed": None, "reason": "no challenge code provided"}
    if not transcript:
        return {
            "check": "audio_challenge",
            "passed": False,
            "reason": "no speech detected on the audio track — challenge code not spoken",
            "transcript": "",
        }

    normalized = _normalize(transcript)
    target = expected_code.upper().replace(" ", "")
    matched = _is_subsequence(target, normalized)

    return {
        "check": "audio_challenge",
        "passed": matched,
        "reason": (
            f"heard \"{transcript[:120].strip()}\" → \"{normalized}\"; "
            + ("contains " if matched else "missing ")
            + f"expected code {target} in order"
        ),
        "transcript": transcript.strip(),
        "normalized": normalized,
    }
