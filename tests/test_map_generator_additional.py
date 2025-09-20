import os
import sys
import copy
import pytest

# Ensure paths for utils and src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from map_generator import MapEditor, parse_type_hint, get_class_hierarchy
import importlib
import types
from typing import Optional, List, Union


@pytest.fixture
def map_editor(monkeypatch):
    # Patch last map detection to avoid loading stray files
    monkeypatch.setattr('map_generator._get_last_map_file', lambda: None)
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip('No display available for additional MapEditor tests')
    editor = MapEditor(root)
    yield editor
    try:
        root.destroy()
    except Exception:
        pass


def test_normalize_min_padding_shifts(map_editor):
    # Create a map with a tile far from origin forcing shift
    map_editor.map_data = {
        (10, 10): {"id": "tile_10_10", "title": "tile_10_10", "description": "", "exits": [], "events": [], "items": [], "npcs": [], "objects": []},
        (11, 10): {"id": "tile_11_10", "title": "tile_11_10", "description": "", "exits": [], "events": [], "items": [], "npcs": [], "objects": []},
    }
    map_editor.selected_tile = (10, 10)
    map_editor.selected_tiles = {(10, 10), (11, 10)}
    map_editor.selection_anchor = (10, 10)
    map_editor._normalize_min_padding()
    # Tiles should shift so min coord is now 2
    assert (2, 2) in map_editor.map_data
    assert (3, 2) in map_editor.map_data
    t = map_editor.map_data[(2, 2)]
    assert t['id'] == 'tile_2_2'
    assert t['title'] == 'tile_2_2'  # auto updated
    assert map_editor.selected_tile == (2, 2)
    assert (3, 2) in map_editor.selected_tiles


def test_copy_paste_pattern(map_editor):
    # Add tiles via public API to ensure exits etc unaffected
    map_editor.add_tile(0, 0)
    map_editor.add_tile(1, 0)
    map_editor.selected_tiles = {(0, 0), (1, 0)}
    map_editor.selected_tile = (0, 0)
    map_editor.copy_selection()
    assert 'tiles' in map_editor.clipboard
    assert map_editor.clipboard['w'] == 2
    # Paste at new anchor
    map_editor.selected_tiles = {(3, 0)}
    map_editor.selected_tile = (3, 0)
    map_editor.paste_clipboard()
    assert (3, 0) in map_editor.map_data
    assert (4, 0) in map_editor.map_data
    # Confirm ids/titles updated
    assert map_editor.map_data[(3, 0)]['id'] == 'tile_3_0'
    assert map_editor.map_data[(4, 0)]['id'] == 'tile_4_0'


def test_copy_empty_and_delete_paste(map_editor):
    # Ensure map has something to delete
    map_editor.add_tile(0, 0)
    # Select empty tile -> copy placeholder
    map_editor.selected_tiles = {(5, 5)}
    map_editor.selected_tile = (5, 5)
    map_editor.copy_selection()
    assert map_editor.clipboard.get('empty') is True
    # Select existing tile and paste empty -> deletes
    map_editor.selected_tiles = {(0, 0)}
    map_editor.selected_tile = (0, 0)
    map_editor.paste_clipboard()
    assert (0, 0) not in map_editor.map_data


def test_single_tile_multi_paste(map_editor):
    # Single tile clipboard replicated across multi-selection
    map_editor.add_tile(0, 0)
    map_editor.selected_tiles = {(0, 0)}
    map_editor.selected_tile = (0, 0)
    map_editor.copy_selection()
    # Reduce clipboard to single tile explicitly
    assert len(map_editor.clipboard['tiles']) == 1
    # Multi-target selection
    targets = {(2, 2), (3, 2), (4, 2)}
    map_editor.selected_tiles = targets
    map_editor.selected_tile = (2, 2)
    map_editor.paste_clipboard()
    for t in targets:
        assert t in map_editor.map_data
        assert map_editor.map_data[t]['id'] == f'tile_{t[0]}_{t[1]}'


def test_auto_connect_exits_diagonals(map_editor):
    map_editor.add_tile(0, 0)
    map_editor.add_tile(1, 1)  # diagonal
    map_editor.auto_connect_exits()
    assert 'southeast' in map_editor.map_data[(0, 0)]['exits']
    assert 'northwest' in map_editor.map_data[(1, 1)]['exits']


# ---------- Non-GUI helper tests (no Tk needed) ----------
class BaseA: ...
class SubA(BaseA): ...


def test_parse_type_hint_basic():
    cls, is_list, is_opt = parse_type_hint(BaseA)
    assert cls is BaseA and not is_list and not is_opt


def test_parse_type_hint_list_optional():
    cls, is_list, is_opt = parse_type_hint(List[SubA])
    assert cls is SubA and is_list and not is_opt
    cls2, is_list2, is_opt2 = parse_type_hint(Optional[SubA])
    assert cls2 is SubA and not is_list2 and is_opt2
    cls3, is_list3, is_opt3 = parse_type_hint(Union[SubA, None])
    assert cls3 is SubA and not is_list3 and is_opt3


def test_parse_type_hint_string_forward():
    # Provide a dummy module and class to resolve by name
    dummy_mod = types.ModuleType('src.events')
    class ForwardClass: ...
    dummy_mod.ForwardClass = ForwardClass
    sys.modules['src.events'] = dummy_mod
    try:
        cls, is_list, is_opt = parse_type_hint('ForwardClass')
        assert cls is ForwardClass
    finally:
        del sys.modules['src.events']


def test_get_class_hierarchy(monkeypatch):
    # Create dummy modules with subclasses
    mod_items = types.ModuleType('src.items')
    class ItemBase: ...
    class ItemSub(ItemBase): ...
    mod_items.ItemBase = ItemBase
    mod_items.ItemSub = ItemSub
    sys.modules['src.items'] = mod_items
    try:
        h = get_class_hierarchy(ItemBase)
        assert 'ItemBase' in h and 'ItemSub' in h
        assert h['ItemSub'] is ItemSub
    finally:
        del sys.modules['src.items']

