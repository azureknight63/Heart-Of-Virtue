import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from src.npc._eastern_descent import Anvil, NomadCamper, NomadScout, NomadTrader


def _player_with_story(story=None):
    """Lightweight player stand-in exposing player.universe.story as a real
    dict, since Anvil's first-encounter tracking does story.get()/[] = on it
    (a bare MagicMock's mocked __eq__ would make every call look like a
    'first encounter').
    """
    return SimpleNamespace(universe=SimpleNamespace(story=story if story is not None else {}))

def test_nomad_camper_properties():
    npc = NomadCamper()
    assert npc.name == "Nomad"
    assert "talk" in npc.keywords
    assert npc.pronouns["personal"] == "he"
    assert len(npc.known_moves) > 0

@patch("builtins.print")
def test_nomad_camper_talk(mock_print):
    npc = NomadCamper()
    player = MagicMock()
    npc.talk(player)
    assert mock_print.called

def test_nomad_scout_properties():
    npc = NomadScout()
    assert npc.name == "Nomad Scout"
    assert "talk" in npc.keywords
    assert npc.pronouns["personal"] == "he"
    assert len(npc.known_moves) > 0

@patch("builtins.print")
def test_nomad_scout_talk(mock_print):
    npc = NomadScout()
    player = MagicMock()
    npc.talk(player)
    assert mock_print.called

def test_nomad_trader_properties():
    npc = NomadTrader()
    assert npc.name == "Nomad Trader"
    assert "talk" in npc.keywords
    assert npc.pronouns["personal"] == "she"
    assert len(npc.known_moves) > 0

@patch("builtins.print")
def test_nomad_trader_talk(mock_print):
    npc = NomadTrader()
    player = MagicMock()
    npc.talk(player)
    assert mock_print.called

def test_nomad_camper_known_moves_exception_falls_back_to_empty_list():
    with patch("src.npc._base.moves.NpcIdle", side_effect=RuntimeError("boom")):
        npc = NomadCamper()
    assert npc.known_moves == []

def test_nomad_scout_known_moves_exception_falls_back_to_empty_list():
    with patch("src.npc._base.moves.NpcIdle", side_effect=RuntimeError("boom")):
        npc = NomadScout()
    assert npc.known_moves == []

def test_nomad_trader_known_moves_exception_falls_back_to_empty_list():
    with patch("src.npc._base.moves.NpcIdle", side_effect=RuntimeError("boom")):
        npc = NomadTrader()
    assert npc.known_moves == []


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


@patch("builtins.print")
def test_anvil_talk(mock_print):
    npc = Anvil()
    # Pre-mark as already encountered so this exercises the normal ambient
    # flavor-line path (the first-encounter path is covered separately below).
    player = _player_with_story({"anvil_conversation_ready": "1"})
    npc.talk(player)
    assert mock_print.called


@patch("builtins.print")
def test_anvil_pet(mock_print):
    npc = Anvil()
    npc.pet()
    assert mock_print.called


@patch("builtins.print")
def test_anvil_first_talk_is_silent_and_sets_ready_flag(mock_print):
    """The first talk()/pet() call defers to AnvilIntroEvent (src/story/ch03.py)
    instead of narrating a flavor line, so it must not print anything itself."""
    npc = Anvil()
    player = _player_with_story()
    npc.talk(player)
    assert not mock_print.called
    assert player.universe.story["anvil_conversation_ready"] == "1"


@patch("builtins.print")
def test_anvil_talk_after_first_encounter_narrates_normally(mock_print):
    npc = Anvil()
    player = _player_with_story()
    npc.talk(player)  # first call: silent, sets the flag
    mock_print.reset_mock()
    npc.talk(player)  # second call: flag already set, normal flavor line
    assert mock_print.called


@patch("builtins.print")
def test_anvil_first_pet_is_silent_and_sets_ready_flag(mock_print):
    npc = Anvil()
    player = _player_with_story()
    npc.pet(player)
    assert not mock_print.called
    assert player.universe.story["anvil_conversation_ready"] == "1"


def test_anvil_first_encounter_with_no_player_still_narrates():
    """No player/story context (e.g. a direct call with no player) can't track
    'first encounter' state, so it must fail open to the normal flavor line
    rather than going silently unresponsive."""
    npc = Anvil()
    assert npc._first_encounter(None) is False


def test_anvil_known_moves_exception_falls_back_to_empty_list():
    with patch("src.npc._base.moves.NpcIdle", side_effect=RuntimeError("boom")):
        npc = Anvil()
    assert npc.known_moves == []
