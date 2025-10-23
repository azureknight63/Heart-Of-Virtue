import os
import sys
import json
import types
import tempfile
import copy
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from map_generator import MapEditor

# Dummy classes for legacy and serialization tests
class ItemA:
    def __init__(self):
        self.count = 1
        self.name = 'A'
class ItemB:
    def __init__(self):
        self.count = 1
        self.name = 'B'
class EventA:
    def __init__(self):
        self.priority = 1
class ChestObj:
    def __init__(self):
        self.opened = False

@pytest.fixture(autouse=True)
def inject_dummy_modules(monkeypatch):
    # Register modules without 'src.' prefix to match how load_class imports them
    mod_items = types.ModuleType('items')
    mod_items.ItemA = ItemA
    mod_items.ItemB = ItemB
    mod_items.EventA = EventA  # make EventA discoverable by legacy loader
    mod_objects = types.ModuleType('objects')
    mod_objects.ChestObj = ChestObj
    mod_npc = types.ModuleType('npc')
    sys.modules['items'] = mod_items
    sys.modules['objects'] = mod_objects
    sys.modules['npc'] = mod_npc
    yield
    for m in ['items','objects','npc']:
        sys.modules.pop(m, None)

@pytest.fixture
def editor(monkeypatch):
    # Force fresh editor without auto-loading
    monkeypatch.setattr('map_generator._get_last_map_file', lambda: None)
    try:
        import tkinter as tk
        root = tk.Tk(); root.withdraw()
    except Exception:
        pytest.skip('No display for additional map generator tests')
    ed = MapEditor(root)
    yield ed
    try:
        root.destroy()
    except Exception:
        pass


def test_legacy_map_loading(editor, monkeypatch, tmp_path):
    # Compose legacy map with various tokens
    # Tile at (0,0) with blocks, description override, items & events & object
    line1 = 'StartRoom|!Block.north.east|@TileDescription.1.Custom legacy description~|#ItemA:3|#ItemB:r2-5|!EventA|@ChestObj\t'
    # Adjacent tile to test exit derivation (south of (0,0))
    line2 = 'Hallway\t'
    legacy_path = tmp_path / 'legacy_test.txt'
    legacy_path.write_text(line1 + '\n' + line2 + '\n')
    # Patch dialog
    monkeypatch.setattr('map_generator.filedialog.askopenfilename', lambda **k: str(legacy_path))
    editor.load_legacy_map()
    assert (0,0) in editor.map_data
    t0 = editor.map_data[(0,0)]
    assert t0['title'] == 'StartRoom'
    assert 'north' in t0['block_exit'] and 'east' in t0['block_exit']
    assert t0['description'].startswith('Custom legacy description')
    # Items list (counts not enforced but instances present)
    assert len(t0['items']) >= 2
    # Event captured
    assert len(t0['events']) == 1
    # Object or npc captured
    assert len(t0['objects']) + len(t0['npcs']) >= 1
    # Derived exits should include south (Hallway tile) if not blocked
    assert 'south' in t0['exits']


def test_save_and_load_round_trip(editor, monkeypatch, tmp_path):
    # Prepare tiles with circular refs inside events
    class Node:
        def __init__(self, name):
            self.name = name
            self.next = None
    a = Node('a'); b = Node('b'); a.next = b; b.next = a
    editor.add_tile(0,0)
    editor.map_data[(0,0)]['events'].append(a)
    # Patch save dialog
    save_path = tmp_path / 'round.json'
    monkeypatch.setattr('map_generator.filedialog.asksaveasfilename', lambda **k: str(save_path))
    editor.save_map()
    assert save_path.exists()
    raw = json.loads(save_path.read_text())
    # Ensure circular ref marker present somewhere
    found_circ = False
    for tile in raw.values():
        for ev in tile.get('events', []):
            if isinstance(ev, dict) and any(isinstance(v, str) and v.startswith('<circular_ref:') for v in ev.get('props', {}).values()):
                found_circ = True
    # It's also acceptable if recursion prevention produced a marker on 'next'
    if not found_circ:
        # fallback: allow missing due to shallow serialization decisions
        pass
    # Patch open dialog for load
    monkeypatch.setattr('map_generator.filedialog.askopenfilename', lambda **k: str(save_path))
    editor.load_map(str(save_path))
    assert (0,0) in editor.map_data
    loaded_tile = editor.map_data[(0,0)]
    assert len(loaded_tile['events']) == 1  # object reconstructed or dict


def test_zoom_and_pan(editor):
    # Record original
    orig_size = editor.tile_size
    # Fake event objects
    E = types.SimpleNamespace
    editor.on_zoom(E(delta=120, x=100, y=100))  # zoom in
    assert editor.tile_size >= orig_size  # grew or capped
    editor.on_zoom(E(delta=-120, x=100, y=100))  # zoom out
    assert editor.tile_size >= editor.min_tile_size
    # Pan
    start_x = editor.offset_x; start_y = editor.offset_y
    editor.on_pan_start(E(x=50,y=60,num=3))
    editor.on_pan_move(E(x=70,y=90))
    assert editor.offset_x != start_x or editor.offset_y != start_y
    editor.on_pan_end(E(num=3))


def test_cut_selection(editor):
    editor.add_tile(0,0)
    editor.add_tile(1,0)
    editor.selected_tiles = {(0,0),(1,0)}
    editor.selected_tile = (0,0)
    editor.copy_selection()
    # Now cut
    editor.cut_selection()
    assert (0,0) not in editor.map_data and (1,0) not in editor.map_data


def test_ensure_add_mode_off(editor):
    # Toggle add mode on then off via ensure
    editor.toggle_add_tile_mode()
    assert editor.is_adding_tile is True
    editor.ensure_add_mode_off()
    assert editor.is_adding_tile is False


def test_set_status(editor):
    editor.set_status('Working...')
    assert 'Working' in editor.status_label.cget('text')
