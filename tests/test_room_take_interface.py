"""Test suite for RoomTakeInterface

This file ensures the test environment can import project modules by adding the
`src` directory to sys.path before importing `src.interface`.
"""
import os
import sys
# Ensure the project's `src` package can import modules that use top-level imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import pytest

from src.interface import RoomTakeInterface


class DummyItem:
    def __init__(self, name, weight=0, count=None, announce=''):
        self.name = name
        self.weight = weight
        if count is not None:
            self.count = count
        self.announce = announce
        self.owner = None

    def __repr__(self):
        return f"<Item {self.name} x{getattr(self, 'count', 1)}>"


class DummyRoom:
    def __init__(self, items=None, nickname='room'):
        self.items_here = items or []
        self.nickname = nickname

    def refresh_description(self):
        pass

    def process_events(self):
        pass


class DummyPlayer:
    def __init__(self, name='Jean', weight_tolerance=100):
        self.name = name
        self.weight_tolerance = weight_tolerance
        self.inventory = []
        self.weight_current = 0
        self.current_room = None

    def refresh_weight(self):
        self.weight_current = sum(getattr(i, 'weight', 0) * getattr(i, 'count', 1) for i in self.inventory)

    def _take_item(self, item, index=None):
        # Mirror RoomTakeInterface._take_item semantics used by tests
        if hasattr(item, 'weight'):
            item_weight = item.weight * getattr(item, 'count', 1)
            if item_weight > (self.weight_tolerance - self.weight_current):
                return False
        self.inventory.append(item)
        if index is not None:
            # remove by index from current_room
            self.current_room.items_here.pop(index)
        else:
            self.current_room.items_here.remove(item)
        item.owner = self
        self.refresh_weight()
        return True


@pytest.fixture
def player():
    p = DummyPlayer()
    return p


@pytest.fixture
def simple_room():
    return DummyRoom()


def test_take_single_item_by_interactive_selection(monkeypatch, player, simple_room, capsys):
    # Room with one item
    item = DummyItem('Sword', weight=5)
    simple_room.items_here.append(item)
    player.current_room = simple_room

    ri = RoomTakeInterface(player, room=simple_room)

    # Simulate user selecting index 0 then exit
    inputs = iter(['0', 'x'])
    monkeypatch.setattr('builtins.input', lambda prompt='': next(inputs))

    ri.run()

    # Assert item moved to player
    assert item in player.inventory
    assert item.owner == player
    assert item not in simple_room.items_here


def test_take_all_noninteractive_with_phrase_all(player, simple_room):
    # Room with multiple items
    items = [DummyItem('Arrow', weight=1, count=10), DummyItem('Gem', weight=2)]
    simple_room.items_here.extend(items)
    player.current_room = simple_room

    ri = RoomTakeInterface(player, room=simple_room)

    # Non-interactive call with phrase 'all'
    ri.run(phrase='all')

    # Player should have taken items that fit
    assert any(i.name == 'Arrow' for i in player.inventory)


def test_take_specific_item_by_phrase(player, simple_room, capsys):
    item = DummyItem('Lantern', weight=3, announce='brass')
    simple_room.items_here.append(item)
    player.current_room = simple_room

    ri = RoomTakeInterface(player, room=simple_room)

    # Non-interactive take specific
    ri.run(phrase='lantern')

    assert item in player.inventory
    # Item owner should be the player (interfaces must not be recorded as owners)
    assert item.owner == player


def test_weight_limit_prevents_taking(player, simple_room, capsys, monkeypatch):
    # Player with low tolerance
    player.weight_tolerance = 2
    heavy = DummyItem('Anvil', weight=5)
    simple_room.items_here.append(heavy)
    player.current_room = simple_room

    ri = RoomTakeInterface(player, room=simple_room)

    # Non-interactive specific attempt
    ri.run(phrase='anvil')

    # Anvil should remain in the room
    assert heavy in simple_room.items_here
    assert heavy not in player.inventory


def test_run_handles_empty_room(player, simple_room, capsys):
    # Ensure empty room prints message and returns
    player.current_room = simple_room
    ri = RoomTakeInterface(player, room=simple_room)
    ri.run()
    captured = capsys.readouterr()
    assert "There doesn't seem to be anything here for Jean to take." in captured.out


def test_take_all_with_weight_constraints(player, simple_room, capsys):
    # Player can only carry limited weight; ensure partial take in _take_all
    player.weight_tolerance = 5
    # Items: one heavy (weight 4) and one light stack (weight 1 each * 10)
    heavy = DummyItem('Rock', weight=4)
    arrows = DummyItem('Arrow', weight=1, count=10)
    simple_room.items_here.extend([heavy, arrows])
    player.current_room = simple_room

    ri = RoomTakeInterface(player, room=simple_room)

    # Call _take_all_items directly to test internal logic
    ri._take_all_items()

    # Player should at least take the heavy rock (fits) and possibly arrows up to capacity
    assert any(i.name == 'Rock' for i in player.inventory)
    # total weight should not exceed tolerance
    total_weight = sum(getattr(i, 'weight', 0) * getattr(i, 'count', 1) for i in player.inventory)
    assert total_weight <= player.weight_tolerance
