import os
import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules resolve.
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import random
import pytest

from src.npc import CaveBat


class FakeRoom:
    def __init__(self):
        self.spawned = []
        self.objects = []
        self.npcs_here = []
        self.universe = None
        self.description = "A damp cavern"

    def spawn_item(self, item_type, amt=1, hidden=False, hfactor=0, merchandise=False):
        # Create an instance of the requested item class from the items module
        import items as items_module
        cls = getattr(items_module, item_type, None)
        if cls is None:
            return None
        try:
            # Try a common constructor signature
            item = cls()
        except TypeError:
            # Fallback for classes that need args (Gold, etc.)
            try:
                item = cls(amt=amt)
            except Exception:
                item = cls()
        # Record spawn for assertions
        self.spawned.append(item)
        return item


class DummyPlayer:
    def __init__(self):
        self.combat_list = []
        self.combat_proximity = {}
        self.combat_list_allies = []


def test_cave_bat_basic_attributes():
    bat = CaveBat()
    # Name and basic stats
    assert bat.name.startswith("Cave Bat")
    assert bat.maxhp == 8
    assert bat.hp == bat.maxhp
    assert bat.damage == 18
    assert bat.awareness == 14
    assert bat.speed == 40
    assert bat.aggro is True
    assert bat.exp_award == 4
    # Flavor resistances
    assert pytest.approx(bat.resistance_base.get("light", 1.0), rel=1e-3) == 0.8
    assert pytest.approx(bat.resistance_base.get("earth", 1.0), rel=1e-3) == 1.1


def test_cave_bat_moves_include_attack_and_bite():
    bat = CaveBat()
    # known_moves contains move instances; ensure expected move class names present
    move_names = [m.__class__.__name__ for m in bat.known_moves]
    assert "NpcAttack" in move_names or any("Attack" in n for n in move_names)
    assert "BatBite" in move_names


def test_combat_engage_adds_to_player_and_allies(monkeypatch):
    bat = CaveBat()
    p = DummyPlayer()
    # Add an ally with combat_proximity mapping to be updated
    class Ally:
        def __init__(self):
            self.combat_proximity = {}

    ally = Ally()
    p.combat_list_allies.append(ally)

    # Make uniform deterministic so proximity is exact
    monkeypatch.setattr('random.uniform', lambda a, b: 1.0)
    bat.combat_engage(p)
    assert bat in p.combat_list
    assert p.combat_proximity.get(bat) == int(bat.default_proximity * 1.0)
    # Ally should also have been assigned a proximity entry
    assert bat in ally.combat_proximity
    assert ally.combat_proximity[bat] == int(bat.default_proximity * 1.0)
    assert bat.in_combat is True


def test_roll_loot_spawns_item_and_announces(monkeypatch, capsys):
    bat = CaveBat()
    room = FakeRoom()
    bat.current_room = room

    # Make deterministic: don't shuffle, and return a low roll so first candidate wins
    monkeypatch.setattr('random.shuffle', lambda x: None)
    monkeypatch.setattr('random.randint', lambda a, b: 0)

    # Call roll_loot - should spawn at least one item into the room via spawn_item
    bat.roll_loot()
    # Ensure spawn_item was called and an item was returned
    assert len(room.spawned) >= 1
    # The roll_loot function prints a drop message when successful; check stdout contains 'dropped'
    captured = capsys.readouterr()
    assert 'dropped' in captured.out


def test_die_triggers_before_death_and_explosion_message(capsys):
    bat = CaveBat()
    # Force no current_room so roll_loot prints an ERR and die still prints explosion message
    bat.current_room = None
    bat.hp = 0
    bat.die()
    out = capsys.readouterr().out
    # before_death will call roll_loot which prints an ERR line when current_room is None
    assert 'ERR' in out or 'exploded into fragments of light' in out
