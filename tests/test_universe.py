import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytest
import types
import io
import tempfile
import shutil
from pathlib import Path
import functions

# TODO: Need to restructure project and imports, otherwise we'll eventually
# run into problems with the way $PYTHONPATH is set and imports are performed.
from universe import Universe, tile_exists


class DummyItem:
    def __init__(self, name, value):
        self.name = name
        self.value = value


class DummyMerchant:
    def __init__(self, inventory):
        self.inventory = inventory


@pytest.fixture(autouse=True)
def dummy_modules(monkeypatch):
    # Create dummy modules for deserialization (without 'src.' prefix as per universe.py implementation)
    dummy_items = types.ModuleType('items')
    dummy_items.DummyItem = DummyItem
    sys.modules['items'] = dummy_items
    dummy_npc = types.ModuleType('npc')
    dummy_npc.DummyMerchant = DummyMerchant
    sys.modules['npc'] = dummy_npc
    yield
    # Cleanup
    del sys.modules['items']
    del sys.modules['npc']


def test_recursive_deserialize_inventory():
    # Simulate a merchant with a nested inventory of items
    payload = {
        '__class__': 'DummyMerchant',
        '__module__': 'npc',
        'props': {
            'inventory': [
                {
                    '__class__': 'DummyItem',
                    '__module__': 'items',
                    'props': {'name': 'Sword', 'value': 100}
                },
                {
                    '__class__': 'DummyItem',
                    '__module__': 'items',
                    'props': {'name': 'Shield', 'value': 150}
                }
            ]
        }
    }
    universe = Universe()
    merchant = universe._deserialize_saved_instance(payload)
    assert isinstance(merchant, DummyMerchant)
    assert isinstance(merchant.inventory, list)
    for item in merchant.inventory:
        assert isinstance(item, DummyItem)
        assert hasattr(item, 'name')
        assert hasattr(item, 'value')


@pytest.mark.parametrize(
    "setting, expected_hidden, expected_hfactor",
    [("", False, 0), ("garbage", False, 0), ("h+0", True, 0), ("h+123", True, 123)],
)
def test_parse_hidden(setting: str, expected_hidden: bool, expected_hfactor: int):
    hidden, hfactor = Universe.parse_hidden(setting)

    assert hidden == expected_hidden
    assert hfactor == expected_hfactor


def test_tile_exists():
    test_map = {(1, 2): 'tileA', (3, 4): 'tileB'}
    assert tile_exists(test_map, 1, 2) == 'tileA'
    assert tile_exists(test_map, 3, 4) == 'tileB'
    assert tile_exists(test_map, 0, 0) is None


def test_universe_init():
    u = Universe()
    assert u.game_tick == 0
    assert u.maps == []
    assert u.starting_position == (0, 0)
    assert u.starting_map_default is None
    assert isinstance(u.story, dict)
    assert u.locked_chests == []


def test_json_maps_root_candidates(tmp_path, monkeypatch):
    # Create dummy directories
    maps_dir = tmp_path / 'resources' / 'maps'
    maps_dir.mkdir(parents=True)
    utils_maps_dir = tmp_path / 'utils' / 'src' / 'resources' / 'maps'
    utils_maps_dir.mkdir(parents=True)
    monkeypatch.setattr('universe.RESOURCES_DIR', tmp_path / 'resources')
    u = Universe()
    # Patch _json_maps_root_candidates to only return our test dirs
    u._json_maps_root_candidates = lambda: [maps_dir, utils_maps_dir]
    candidates = u._json_maps_root_candidates()
    assert any(str(maps_dir) == str(c) for c in candidates)
    assert any(str(utils_maps_dir) == str(c) for c in candidates)


def test_load_all_json_maps(monkeypatch, tmp_path):
    # Setup dummy map file
    maps_dir = tmp_path / 'resources' / 'maps'
    maps_dir.mkdir(parents=True)
    dummy_map = maps_dir / 'testmap.json'
    dummy_map.write_text('{"(0,0)": {"title": "DummyTile", "description": "desc"}}')
    monkeypatch.setattr('universe.RESOURCES_DIR', tmp_path / 'resources')
    u = Universe()
    # Patch _json_maps_root_candidates to only return our test dir
    u._json_maps_root_candidates = lambda: [maps_dir]
    # Patch _load_single_json_map to count calls
    called = []
    def fake_load_single_json_map(player, jf):
        called.append(jf)
    u._load_single_json_map = fake_load_single_json_map
    count = u._load_all_json_maps(player=None)
    assert count == 1
    assert called[0].name == 'testmap.json'


def test_deserialize_saved_instance_edge_cases():
    u = Universe()
    # Empty dict
    assert u._deserialize_saved_instance({}) is None
    # Missing __class__
    assert u._deserialize_saved_instance({'__module__': 'items', 'props': {}}) is None
    # Builtins
    payload = {'__class__': 'int', '__module__': 'builtins', 'props': {'x': 5}}
    assert u._deserialize_saved_instance(payload) is not None
    # Nested dicts/lists
    payload = {
        '__class__': 'DummyMerchant',
        '__module__': 'npc',
        'props': {
            'inventory': [
                {
                    '__class__': 'DummyItem',
                    '__module__': 'items',
                    'props': {'name': 'Sword', 'value': 100}
                },
                {'foo': 'bar'}
            ],
            'meta': {'subitem': {
                '__class__': 'DummyItem',
                '__module__': 'items',
                'props': {'name': 'Potion', 'value': 10}
            }}
        }
    }
    merchant = u._deserialize_saved_instance(payload)
    assert isinstance(merchant, DummyMerchant)
    assert isinstance(merchant.inventory[0], DummyItem)
    assert merchant.inventory[1] == {'foo': 'bar'}
    assert isinstance(merchant.meta['subitem'], DummyItem)


def test_load_single_json_map(monkeypatch, tmp_path):
    # Setup dummy tile class
    class DummyTile:
        def __init__(self, universe, this_map, x, y, description=None):
            self.x = x
            self.y = y
            self.description = description
            self.block_exit = []
            self.symbol = None
            self.events_here = []
            self.items_here = []
            self.npcs_here = []
            self.objects_here = []
    monkeypatch.setattr(functions, 'seek_class', lambda title, mod: DummyTile)
    # Create dummy map JSON
    map_json = tmp_path / 'testmap.json'
    map_json.write_text('{"(1,2)": {"title": "DummyTile", "description": "desc", "block_exit": ["N"], "symbol": "#", "events": [], "items": [], "npcs": [], "objects": []}}')
    u = Universe()
    u._load_single_json_map(player=None, json_path=map_json)
    assert u.maps[-1]['name'] == 'testmap'
    tile = u.maps[-1][(1,2)]
    assert isinstance(tile, DummyTile)
    assert tile.x == 1 and tile.y == 2
    assert tile.description == 'desc'
    assert tile.block_exit == ['N']
    assert tile.symbol == '#'
    assert tile.events_here == []
    assert tile.items_here == []
    assert tile.npcs_here == []
    assert tile.objects_here == []


def test_load_tiles(monkeypatch, tmp_path):
    # Setup dummy tile class
    class DummyTile:
        def __init__(self, universe, this_map, x, y):
            self.x = x
            self.y = y
    monkeypatch.setattr(functions, 'seek_class', lambda name, mod: DummyTile)
    # Create dummy txt file
    txt_path = tmp_path / 'testmap.txt'
    txt_path.write_text('DummyTile\t\n\n')
    monkeypatch.setattr('universe.RESOURCES_DIR', tmp_path)
    u = Universe()
    u.load_tiles(player=None, mapname='testmap')
    assert u.maps[-1]['name'] == 'testmap'
    assert isinstance(u.maps[-1][(0,0)], DummyTile)
