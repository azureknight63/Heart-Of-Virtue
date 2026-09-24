"""Guard the authored ``fallback_replies`` pool on every shipped persona.

Issue #628: when the LLM cannot produce a mid-conversation turn, the NPC
answers from its persona's ``fallback_replies`` (``_get_fallback_npc_line``
in ``src/npc/_chat_llm.py``). These lines are a *response* to whatever Jean
just said, so they must never ask a question -- a degraded turn that answers
"Tell me more" with a question is the defect this pool replaced -- and, being
authored lines that bypass the model QC, they must not contain a phrase the
persona itself says this character never uses.

Prohibited phrases are matched the way the runtime matches them
(``_prohibited_patterns``: escaped, case-insensitive, substring).
"""

import json
from pathlib import Path

import pytest

_PERSONA_DIR = Path(__file__).resolve().parent.parent / "ai" / "npc" / "human"


def _personas():
    """Every persona file -- a file with a ``character_name``.

    ``world_facts.json`` shares the directory and is not a persona.
    """
    found = []
    for path in sorted(_PERSONA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "character_name" in data:
            found.append(pytest.param(data, id=path.stem))
    return found


_PERSONAS = _personas()


def test_the_persona_glob_finds_the_shipped_personas():
    """A moved directory must fail loudly, not parametrize to zero cases."""
    assert len(_PERSONAS) >= 5


@pytest.mark.parametrize("persona", _PERSONAS)
def test_persona_has_fallback_replies(persona):
    replies = persona.get("fallback_replies")
    assert isinstance(replies, list) and replies
    assert all(isinstance(line, str) and line.strip() for line in replies)
    assert len(set(replies)) == len(replies), "duplicate fallback reply"


@pytest.mark.parametrize("persona", _PERSONAS)
def test_fallback_replies_are_not_questions(persona):
    for line in persona.get("fallback_replies", []):
        assert not line.rstrip().endswith("?"), line
        # A quoted question inside narration ("She says, 'Where?'") is still
        # a question put to Jean.
        assert "?" not in line, line


@pytest.mark.parametrize("persona", _PERSONAS)
def test_fallback_replies_avoid_prohibited_phrases(persona):
    prohibited = [p.lower() for p in persona.get("prohibited_phrases", [])]
    for line in persona.get("fallback_replies", []):
        hits = [p for p in prohibited if p in line.lower()]
        assert not hits, f"{line!r} contains prohibited {hits}"


@pytest.mark.parametrize("persona", _PERSONAS)
def test_fallback_replies_are_not_openers_or_closers(persona):
    """The pool must be distinct from the starters and the closing lines --
    reusing either is the bug (a first-contact opener, or a false goodbye)."""
    starters = {
        line
        for lines in persona.get("conversation_starters_by_chapter", {}).values()
        for line in lines
    }
    closing = set(persona.get("closing_lines_when_exhausted", []))
    for line in persona.get("fallback_replies", []):
        assert line not in starters, line
        assert line not in closing, line
