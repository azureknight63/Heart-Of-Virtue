"""Coverage for the portrait emotion vocabulary in src/narration.py.

The staged-conversation feature has two independent copies of the same
emotion vocabulary: ``narration.EMOTIONS`` (backend) and
``frontend/src/utils/portraits.js`` EMOTIONS (frontend). They previously
drifted — the list only had 6 entries while portrait art on disk shipped
8 expressions (`concerned`/`curious` were silently coerced to `neutral`
by both `_norm_emotion` and its JS counterpart). These tests pin the
current vocabulary and guard against the two copies drifting apart again.
"""

import re
from pathlib import Path

import src.narration as narration

FRONTEND_PORTRAITS_JS = (
    Path(__file__).resolve().parent.parent / "frontend" / "src" / "utils" / "portraits.js"
)


def _frontend_emotions():
    """Extract the EMOTIONS array literal out of portraits.js without a JS runtime."""
    text = FRONTEND_PORTRAITS_JS.read_text(encoding="utf-8")
    match = re.search(r"EMOTIONS\s*=\s*\[([^\]]*)\]", text)
    assert match, "could not find EMOTIONS array in portraits.js"
    return [tok.strip().strip("'\"") for tok in match.group(1).split(",") if tok.strip()]


def test_emotions_include_all_expressions_shipped_as_portrait_art():
    """jean/liss/mara/devet ship concerned+curious art; both must be valid emotions."""
    assert set(narration.EMOTIONS) >= {
        "neutral", "happy", "sad", "angry", "surprised", "skeptical", "concerned", "curious",
    }


def test_norm_emotion_accepts_every_known_emotion():
    for emotion in narration.EMOTIONS:
        assert narration._norm_emotion(emotion) == emotion


def test_norm_emotion_still_defaults_unknown_values_to_neutral():
    assert narration._norm_emotion("furious") == "neutral"
    assert narration._norm_emotion(None) == "neutral"


def test_backend_and_frontend_emotion_vocabularies_stay_in_sync():
    """Drift guard: the two independently-maintained EMOTIONS lists must match.

    This is exactly the class of bug that shipped concerned/curious portrait
    art nobody could ever select — catch it here instead of in the game.
    """
    assert set(narration.EMOTIONS) == set(_frontend_emotions())


def test_say_normalizes_new_emotions_in_the_capture_buffer():
    with narration.capture_narration() as messages:
        narration.say("A flicker of doubt crosses her face.", speaker="liss", emotion="concerned")
        narration.say("What is that?", speaker="jean", emotion="curious")

    assert messages[0]["speaker"] == "liss"
    assert messages[0]["emotion"] == "concerned"
    assert messages[1]["speaker"] == "jean"
    assert messages[1]["emotion"] == "curious"
