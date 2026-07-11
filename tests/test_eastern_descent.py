import pytest
from unittest.mock import patch, MagicMock
from src.npc._eastern_descent import NomadCamper, NomadScout, NomadTrader

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
    with patch("src.npc._eastern_descent.moves.NpcIdle", side_effect=RuntimeError("boom")):
        npc = NomadCamper()
    assert npc.known_moves == []

def test_nomad_scout_known_moves_exception_falls_back_to_empty_list():
    with patch("src.npc._eastern_descent.moves.NpcIdle", side_effect=RuntimeError("boom")):
        npc = NomadScout()
    assert npc.known_moves == []

def test_nomad_trader_known_moves_exception_falls_back_to_empty_list():
    with patch("src.npc._eastern_descent.moves.NpcIdle", side_effect=RuntimeError("boom")):
        npc = NomadTrader()
    assert npc.known_moves == []
