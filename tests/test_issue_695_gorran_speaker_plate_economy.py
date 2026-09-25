"""Issue #695: a Gorran-shaped narration line ("A low, subsonic vibration
rolled through the gravel underfoot as Gorran shifted his weight...") was
plated on ``say(..., "Gorran", ...)`` in ``src/story/ch03.py``'s
``IronAndOathIntroEvent`` -- third-person environmental narration, not
speech, wearing Gorran's speaker plate. The other Gorran physical/sound
reactions in the same file (~489, ~653) are correctly ``print_slow()``
narration instead.

This is a class of defect, not a one-off typo: `docs/lore/story/ch02-ch03-
transition.md` ("Gorran's Language Stage During This Transition") is explicit
that at this point in the story Gorran "deploys [words] with extreme economy"
and "the two-word moment ... is the ceiling, not the average" -- so any
``say()`` call plating him with a full descriptive sentence is a narration
misattributed to dialogue, independent of which specific sentence it is.
Guarded generically (AST scan across every story module, word-count ceiling)
rather than by pinning the fixed string, per the triage brief's request for a
test that "guards a class of defect."
"""

import ast
from pathlib import Path

STORY_DIR = Path(__file__).resolve().parent.parent / "src" / "story"

#: Generous ceiling for a Gorran spoken line at this stage of his language
#: arc. The two lines shipped today ("Mmmmm... Go-rra-nnnnnn...", "Stop.")
#: are both one token; the offender this guards against was 19 words of
#: environmental narration. Not zero-margin-tight on purpose -- a short,
#: stage-appropriate utterance ("It remembers.") must still pass.
_MAX_GORRAN_SPOKEN_WORDS = 6


def _say_calls_for_speaker(tree, speaker):
    """``(lineno, narrated text)`` for every ``say(text, speaker, ...)`` call
    in ``tree`` whose speaker argument is the literal string ``speaker``.

    Reads only the positional/keyword shape every shipped ``say()`` call
    uses (text, speaker, mood, ...); a call that doesn't match this shape is
    skipped rather than guessed at.
    """
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "say" or len(node.args) < 2:
            continue
        text_node, speaker_node = node.args[0], node.args[1]
        if not (isinstance(speaker_node, ast.Constant) and speaker_node.value == speaker):
            continue
        if isinstance(text_node, ast.Constant) and isinstance(text_node.value, str):
            found.append((node.lineno, text_node.value))
    return found


def _gorran_spoken_lines():
    found = []
    for path in sorted(STORY_DIR.glob("ch0*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, text in _say_calls_for_speaker(tree, "Gorran"):
            found.append((f"{path.name}:{lineno}", text))
    return found


def test_population_is_non_empty():
    """The population must actually contain shipped Gorran dialogue, or the
    guard below is checking nothing."""
    assert len(_gorran_spoken_lines()) >= 1


def test_gorran_spoken_lines_stay_within_his_language_stage_economy():
    offenders = [
        (where, text) for where, text in _gorran_spoken_lines()
        if len(text.split()) > _MAX_GORRAN_SPOKEN_WORDS
    ]
    assert offenders == [], (
        "a say() call plates Gorran with a full sentence, which his language "
        "stage in ch02-ch03-transition.md forbids -- likely narration "
        "misattributed to his speaker plate: " + repr(offenders)
    )
