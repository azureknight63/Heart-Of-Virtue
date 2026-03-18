import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import positions
from functions import add_enemies_to_combat
from npc import CaveBat
from player import Player


class DummyAdapter:
    def __init__(self):
        self.calls = []

    def initialize_combat(self, enemies, reinit=False):
        self.calls.append({"enemies": enemies, "reinit": reinit})
        return {"success": True}


def _make_player():
    player = Player()
    player.combat_list = []
    player.combat_list_allies = [player]
    player.combat_proximity = {}
    player.in_combat = True
    return player


def test_add_enemies_to_combat_resets_moves(monkeypatch):
    monkeypatch.setattr(positions, "initialize_combat_positions", lambda **kwargs: None)

    player = _make_player()
    enemy = CaveBat()

    for move in enemy.known_moves:
        move.current_stage = 2
        move.beats_left = 5

    add_enemies_to_combat(player, [enemy])

    assert enemy in player.combat_list
    assert enemy.combat_list == player.combat_list_allies
    assert enemy.combat_list_allies == player.combat_list
    assert enemy.in_combat is True

    for move in enemy.known_moves:
        assert move.current_stage == 0
        assert move.beats_left == 0


def test_add_enemies_to_combat_reinits_adapter(monkeypatch):
    monkeypatch.setattr(positions, "initialize_combat_positions", lambda **kwargs: None)

    player = _make_player()
    player._combat_adapter = DummyAdapter()

    enemy = CaveBat()
    add_enemies_to_combat(player, [enemy])

    assert len(player._combat_adapter.calls) == 1
    call = player._combat_adapter.calls[0]
    assert call["enemies"] == [enemy]
    assert call["reinit"] is True
