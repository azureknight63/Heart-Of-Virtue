"""Behavioural tests for the eastern-descent NPCs (src/npc/_eastern_descent.py).

Every ``talk``/``pet`` test here used to be ``@patch("builtins.print")`` plus
``assert mock_print.called``. That proved almost nothing: it could not tell one
NPC's dialogue from another's, could not catch a line vanishing from the pool,
and was one refactor away from being permanently vacuous — the engine narrates
through ``src.narration`` (see CLAUDE.md, "Terminal-mode removal"), which only
echoes to ``print`` when no capture is active, so any caller that installs a
narration sink would have silently emptied these assertions.

They now capture the narration sink and assert the emitted text is a line from
the NPC's own declared pool.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from src.narration import capture_narration
from src.npc._eastern_descent import Anvil, NomadCamper, NomadScout, NomadTrader


def _player_with_story(story=None):
    """Lightweight player stand-in exposing player.universe.story as a real
    dict, since Anvil's first-encounter tracking does story.get()/[] = on it
    (a bare MagicMock's mocked __eq__ would make every call look like a
    'first encounter').
    """
    return SimpleNamespace(universe=SimpleNamespace(story=story if story is not None else {}))


def _narrated(callable_, *args, **kwargs):
    """Run ``callable_`` with a narration sink installed; return the texts."""
    with capture_narration() as messages:
        callable_(*args, **kwargs)
    return [m["text"] for m in messages]


# ---------------------------------------------------------------------------
# The three nomads: identical shape, so parametrized over the real classes.
# ---------------------------------------------------------------------------

NOMADS = [
    (NomadCamper, "Nomad", "he"),
    (NomadScout, "Nomad Scout", "he"),
    (NomadTrader, "Nomad Trader", "she"),
]


@pytest.mark.parametrize("cls,expected_name,pronoun", NOMADS)
def test_nomad_properties(cls, expected_name, pronoun):
    npc = cls()
    assert npc.name == expected_name
    assert "talk" in npc.keywords
    assert npc.pronouns["personal"] == pronoun
    assert len(npc.known_moves) > 0


@pytest.mark.parametrize("cls,expected_name,pronoun", NOMADS)
def test_nomad_talk_narrates_a_line_from_its_own_pool(cls, expected_name, pronoun):
    npc = cls()
    texts = _narrated(npc.talk, MagicMock())

    assert len(texts) == 1
    assert texts[0] in cls._TALK_LINES
    # The pool must be a real pool -- a single hardcoded line would make the
    # random.choice above meaningless.
    assert len(cls._TALK_LINES) > 1


@pytest.mark.parametrize("cls,expected_name,pronoun", NOMADS)
def test_nomad_talk_pools_do_not_overlap(cls, expected_name, pronoun):
    """Each nomad speaks with its own voice; a copy-paste of another's pool
    would make the three ``talk`` tests above interchangeable."""
    others = [other for other, _, _ in NOMADS if other is not cls]
    for other in others:
        assert not set(cls._TALK_LINES) & set(other._TALK_LINES)


@pytest.mark.parametrize("cls,expected_name,pronoun", NOMADS)
def test_nomad_known_moves_exception_falls_back_to_empty_list(
        cls, expected_name, pronoun):
    with patch("src.npc._base.moves.NpcIdle", side_effect=RuntimeError("boom")):
        npc = cls()
    assert npc.known_moves == []


# ---------------------------------------------------------------------------
# Anvil — the non-combatant dog, with first-encounter gating.
# ---------------------------------------------------------------------------

def test_anvil_properties():
    npc = Anvil()
    assert npc.name == "Anvil"
    assert npc.keywords == ["talk", "pet"]
    assert npc.pronouns["personal"] == "he"
    assert len(npc.known_moves) > 0
    assert npc.friend is True
    assert npc.aggro is False
    assert npc.damage == 0


def test_anvil_cannot_enter_combat():
    npc = Anvil()
    assert npc.can_enter_combat() is False
    player = MagicMock()
    npc.combat_engage(player)
    assert npc.in_combat is False


@pytest.mark.parametrize("verb,pool_attr", [("talk", "_TALK_LINES"),
                                            ("pet", "_PET_LINES")])
def test_anvil_narrates_its_own_pool_after_the_first_encounter(verb, pool_attr):
    npc = Anvil()
    # Pre-mark as already encountered so this exercises the normal ambient
    # flavor-line path (the first-encounter path is covered separately below).
    player = _player_with_story({"anvil_conversation_ready": "1"})

    texts = _narrated(getattr(npc, verb), player)

    assert len(texts) == 1
    assert texts[0] in getattr(Anvil, pool_attr)


def test_anvil_talk_and_pet_draw_from_different_pools():
    assert not set(Anvil._TALK_LINES) & set(Anvil._PET_LINES)


@pytest.mark.parametrize("verb", ["talk", "pet"])
def test_anvil_first_encounter_is_silent_and_sets_ready_flag(verb):
    """The first talk()/pet() call defers to AnvilIntroEvent (src/story/ch03.py)
    instead of narrating a flavor line, so it must emit nothing itself."""
    npc = Anvil()
    player = _player_with_story()

    texts = _narrated(getattr(npc, verb), player)

    assert texts == []
    assert player.universe.story["anvil_conversation_ready"] == "1"


def test_anvil_talk_after_first_encounter_narrates_normally():
    npc = Anvil()
    player = _player_with_story()

    first = _narrated(npc.talk, player)   # first call: silent, sets the flag
    second = _narrated(npc.talk, player)  # second: flag set, normal flavor line

    assert first == []
    assert len(second) == 1
    assert second[0] in Anvil._TALK_LINES


def test_anvil_first_encounter_with_no_player_still_narrates():
    """No player/story context (e.g. a direct call with no player) can't track
    'first encounter' state, so it must fail open to the normal flavor line
    rather than going silently unresponsive."""
    npc = Anvil()
    assert npc._first_encounter(None) is False
    assert len(_narrated(npc.talk, None)) == 1


def test_anvil_known_moves_exception_falls_back_to_empty_list():
    with patch("src.npc._base.moves.NpcIdle", side_effect=RuntimeError("boom")):
        npc = Anvil()
    assert npc.known_moves == []
