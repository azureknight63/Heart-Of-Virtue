"""Coverage for the portrait emotion vocabulary owned by ``src/narration.py``.

``narration.EMOTIONS`` is the owner. Two files must spell the same set and
cannot import it, because neither runs Python:

* ``frontend/src/utils/portraits.js`` (``EMOTIONS``) — the browser copy every
  React surface normalizes against.
* ``tools/portrait_splitter.html`` (``emotionState``) — a standalone,
  dependency-free browser tool (no build step, so it cannot import the JS copy
  either) that decides which expressions can be cut out of a portrait sheet in
  the first place.

Both are unavoidable duplicates, so both are made *detectable* here: the tests
below parse the array literal straight out of each source file and compare it
to ``narration.EMOTIONS`` as a set. Nothing in this module hand-lists the
vocabulary — a restated list cannot fail when the vocabulary changes, which is
the only failure these tests exist to catch.

The vocabulary already drifted once: the list had 6 entries while portrait art
on disk shipped 8 expressions, so ``concerned``/``curious`` were silently
coerced to ``neutral`` by both ``_norm_emotion`` and its JS counterpart. The
art-vs-vocabulary half of that guard lives on the JS side, where the portrait
directory can actually be scanned (``frontend/src/utils/portraits.test.js``,
"every expression found on disk is part of the known EMOTIONS vocabulary");
it reaches the backend through the sync test below.
"""

import re
from pathlib import Path

import src.narration as narration

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_PORTRAITS_JS = REPO_ROOT / "frontend" / "src" / "utils" / "portraits.js"
PORTRAIT_SPLITTER_HTML = REPO_ROOT / "tools" / "portrait_splitter.html"


def _js_string_array(path, binding):
    """Extract a flat ``<binding> = ['a', 'b']`` literal without a JS runtime.

    Deliberately crude: it matches up to the first ``]``, so it only supports
    the flat, single-bracket list both sources are documented to keep. If a
    source ever grows past that shape this raises rather than silently
    returning a short list that would make the comparison vacuously pass.
    """
    text = path.read_text(encoding="utf-8")
    # The lookbehind keeps ``EMOTIONS`` from matching inside a longer name
    # such as ``TONE_EMOTIONS``, which would silently read the wrong list.
    match = re.search(rf"(?<![A-Za-z0-9_]){binding}\s*=\s*\[([^\]]*)\]", text)
    assert match, f"could not find the {binding} array literal in {path.name}"
    names = [
        tok.strip().strip("'\"") for tok in match.group(1).split(",") if tok.strip()
    ]
    assert names, f"parsed an empty {binding} array out of {path.name}"
    assert all(
        re.fullmatch(r"[a-z]+", name) for name in names
    ), f"{binding} in {path.name} did not parse as bare emotion names: {names}"
    return names


def test_emotions_is_a_well_formed_vocabulary():
    """Shape assertion over the real tuple — no hand-copied list to drift.

    Restating the eight names here would only assert that a literal equals
    itself. What is actually worth pinning is the shape ``_norm_emotion`` and
    the portrait path convention depend on: unique, non-empty, lowercase
    slug-safe names, with the normalization fallback among them.
    """
    emotions = narration.EMOTIONS

    assert isinstance(emotions, tuple), "EMOTIONS must stay immutable"
    assert len(emotions) >= 2
    assert len(set(emotions)) == len(emotions), f"duplicate emotion: {emotions}"
    for emotion in emotions:
        assert isinstance(emotion, str) and emotion
        # `_norm_emotion` lowercases + strips before the membership test, so an
        # entry that is not already in that form could never be matched; the
        # name is also a portrait filename, hence the slug-safe charset.
        assert emotion == emotion.strip().lower()
        assert re.fullmatch(
            r"[a-z]+", emotion
        ), f"not a portrait-safe name: {emotion!r}"

    # The fallback must itself be a member, or every unknown value normalizes
    # to something the vocabulary rejects.
    assert narration._norm_emotion("definitely-not-an-emotion") in emotions


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
    assert set(narration.EMOTIONS) == set(
        _js_string_array(FRONTEND_PORTRAITS_JS, "EMOTIONS")
    )


def test_portrait_splitter_tool_offers_exactly_the_known_vocabulary():
    """Drift guard for the tool that decides what portrait art can exist.

    ``tools/portrait_splitter.html`` cuts a sheet into one PNG per emotion and
    names the files from its own ``emotionState`` list. An emotion missing
    there can never be cut; an extra one there produces ``<slug>/<name>.png``
    that ``normalizeEmotion`` coerces to ``neutral``, so the art is quietly
    unreachable. Either way nothing fails today — hence parsing the literal
    out of the HTML, unglamorous as that is.

    Order is exempt on purpose: the tool's order is sheet grid-slot layout
    (drag-reorderable in the UI), not vocabulary.
    """
    assert set(narration.EMOTIONS) == set(
        _js_string_array(PORTRAIT_SPLITTER_HTML, "emotionState")
    )


def test_say_normalizes_new_emotions_in_the_capture_buffer():
    with narration.capture_narration() as messages:
        narration.say("A flicker of doubt crosses her face.", speaker="liss", emotion="concerned")
        narration.say("What is that?", speaker="jean", emotion="curious")

    assert messages[0]["speaker"] == "liss"
    assert messages[0]["emotion"] == "concerned"
    assert messages[1]["speaker"] == "jean"
    assert messages[1]["emotion"] == "curious"
