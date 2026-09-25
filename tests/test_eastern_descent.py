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
from src.story.ch03 import IronAndOathIntroEvent

_IRON_AND_OATH_GATE = IronAndOathIntroEvent.GATE_KEY


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
    """The first talk()/pet() call *after Jean has met Kaelen & Vespera*
    defers to AnvilIntroEvent (src/story/ch03.py) instead of narrating a
    flavor line, so it must emit nothing itself. ``iron_and_oath_intro_done``
    is AnvilIntroEvent's own precondition (both gates on the same tile
    (4, 3), Iron & Oath's intro firing on tile entry) -- it must already be
    set for this "first encounter" to be the real one (issue #695)."""
    npc = Anvil()
    player = _player_with_story({_IRON_AND_OATH_GATE: "1"})

    texts = _narrated(getattr(npc, verb), player)

    assert texts == []
    assert player.universe.story["anvil_conversation_ready"] == "1"


@pytest.mark.parametrize("verb,pool_attr", [("talk", "_TALK_LINES"),
                                            ("pet", "_PET_LINES")])
def test_anvil_first_encounter_before_iron_and_oath_intro_narrates_normally(
        verb, pool_attr):
    """Issue #695: petting/talking to Anvil before Jean has met Kaelen &
    Vespera used to burn the one-shot ``CONVERSATION_READY_FLAG`` for
    nothing -- AnvilIntroEvent's own ``check_conditions`` also requires
    ``iron_and_oath_intro_done``, so the "first encounter" narrated nothing
    (deferring to a conversation that could never fire) and the API's
    generic ''Jean successfully completes the 'pet' action.'' fallback
    reached the player instead of an Anvil line. It must fall open to the
    ambient flavor line and leave the ready flag unset, so a later
    talk()/pet() call -- once Jean HAS met them -- is still the genuine first
    encounter that hands off to AnvilIntroEvent.
    """
    npc = Anvil()
    player = _player_with_story()  # iron_and_oath_intro_done unset

    texts = _narrated(getattr(npc, verb), player)

    assert len(texts) == 1
    assert texts[0] in getattr(Anvil, pool_attr)
    assert "anvil_conversation_ready" not in player.universe.story


def test_anvil_talk_after_first_encounter_narrates_normally():
    npc = Anvil()
    player = _player_with_story({_IRON_AND_OATH_GATE: "1"})

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


def test_anvil_first_encounter_follows_the_iron_and_oath_gate_key(monkeypatch):
    """Scrub of #695: Anvil gated its first encounter on a literal copy of
    ``IronAndOathIntroEvent.GATE_KEY``. Renaming that key would leave Anvil
    waiting on a gate nothing ever sets -- its intro silently dead. The gate
    must be read from the event that owns it."""
    from src.story.ch03 import IronAndOathIntroEvent

    monkeypatch.setattr(IronAndOathIntroEvent, "GATE_KEY", "iron_and_oath_renamed")
    anvil = Anvil()
    player = _player_with_story({"iron_and_oath_renamed": "1"})

    assert anvil._first_encounter(player) is True


# ---------------------------------------------------------------------------
# Issue #718: through the API, the first pet hands off to AnvilIntro -- and
# the generic "successfully completes" line must not ride along with it.
# ---------------------------------------------------------------------------

_GENERIC_FALLBACK = "successfully completes"


def _anvil_world(with_intro=True):
    """A real world: Anvil on the tile, AnvilIntroEvent armed beside him, and
    Iron & Oath's intro done so the first pet is the first encounter."""
    from src.events import set_story_gate
    from src.story.ch03 import AnvilIntroEvent
    from tests._gs_fixtures import live_world

    player, game_map = live_world()
    tile = game_map[(0, 0)]
    anvil = Anvil()
    anvil.current_room = tile
    tile.npcs_here.append(anvil)
    if with_intro:
        tile.events_here.append(AnvilIntroEvent(player, tile))
    set_story_gate(player, _IRON_AND_OATH_GATE)
    return player, anvil


def _interact(player, target, action):
    from src.api.services.game_service import GameService
    from src.combatant import wire_handle

    return GameService().interact_with_target(
        player, wire_handle(target), action, session_data={}
    )


def test_a_pet_that_starts_anvil_intro_carries_no_generic_fallback():
    player, anvil = _anvil_world()
    result = _interact(player, anvil, "pet")

    assert result["success"] is True, result
    names = [e.get("name") for e in result["events_triggered"]]
    assert "AnvilIntro" in names, "premise: the pet must start AnvilIntro"
    assert _GENERIC_FALLBACK not in result["message"], result["message"]


def test_an_action_with_no_narration_and_no_event_still_gets_its_fallback():
    """Negative control: the fallback exists for exactly this -- a first
    encounter swallowed its own line and nothing picked it up (no intro on
    the tile), so without it the player would see nothing at all."""
    player, anvil = _anvil_world(with_intro=False)
    result = _interact(player, anvil, "pet")

    assert result["events_triggered"] == [], "premise: nothing fired"
    assert _GENERIC_FALLBACK in result["message"], result["message"]
