import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import unittest
from unittest.mock import patch
import tkinter as tk
from map_generator import MapEditor, TileEditorWindow, TagListFrame, refresh_tags  # added refresh_tags import
import tempfile
import json


class MockItem:
    """Mock item class for testing"""
    def __init__(self, name="Test Item", count=1, value=10):
        self.name = name
        self.count = count
        self.value = value

    def __repr__(self):
        return f"MockItem(name='{self.name}', count={self.count}, value={self.value})"


class MockEvent:
    """Mock event class for testing"""
    def __init__(self, name="Test Event", repeat=False, priority=1):
        self.name = name
        self.repeat = repeat
        self.priority = priority

    def __repr__(self):
        return f"MockEvent(name='{self.name}', repeat={self.repeat}, priority={self.priority})"


class TestMapGenerator(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures before each test method."""
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            # Patch last map detection to avoid unintended auto-load of stray json files
            with patch('map_generator._get_last_map_file', return_value=None):
                self.map_editor = MapEditor(self.root)
            self.has_display = True
        except tk.TclError:
            self.has_display = False
            self.skipTest("No display available for GUI tests")

    def tearDown(self):
        if hasattr(self, 'root'):
            try:
                self.root.quit()
                self.root.destroy()
            except Exception:
                pass

    def test_map_editor_initialization(self):
        if not self.has_display:
            self.skipTest("No display available")
        self.assertIsNotNone(self.map_editor)
        self.assertEqual(self.map_editor.tile_size, 50)
        self.assertEqual(self.map_editor.map_data, {})
        self.assertIsNone(self.map_editor.selected_tile)
        self.assertFalse(self.map_editor.is_adding_tile)

    def test_add_tile(self):
        if not self.has_display:
            self.skipTest("No display available")
        self.map_editor.add_tile(1, 1)
        self.assertIn((1, 1), self.map_editor.map_data)
        tile = self.map_editor.map_data[(1, 1)]
        self.assertEqual(tile["id"], "tile_1_1")
        self.assertEqual(tile["title"], "tile_1_1")
        self.assertIn("description", tile)

    def test_remove_selected_tile(self):
        if not self.has_display:
            self.skipTest("No display available")
        self.map_editor.add_tile(1, 1)
        self.map_editor.selected_tiles = {(1, 1)}
        self.map_editor.remove_selected_tile()
        self.assertNotIn((1, 1), self.map_editor.map_data)

    def test_create_new_map(self):
        if not self.has_display:
            self.skipTest("No display available")
        self.map_editor.add_tile(1, 1)
        self.map_editor.selected_tile = (1, 1)
        self.map_editor.create_new_map()
        self.assertEqual(self.map_editor.map_data, {})
        self.assertIsNone(self.map_editor.selected_tile)
        self.assertIsNone(self.map_editor.current_map_filepath)

    def test_auto_connect_exits(self):
        if not self.has_display:
            self.skipTest("No display available")
        self.map_editor.add_tile(0, 0)
        self.map_editor.add_tile(1, 0)
        self.map_editor.auto_connect_exits()
        tile1 = self.map_editor.map_data[(0, 0)]
        tile2 = self.map_editor.map_data[(1, 0)]
        self.assertIn("east", tile1["exits"])
        self.assertIn("west", tile2["exits"])

    @patch('tkinter.filedialog.asksaveasfilename')
    def test_save_map(self, mock_save_dialog):
        if not self.has_display:
            self.skipTest("No display available")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            tmp_path = tmp.name
        mock_save_dialog.return_value = tmp_path
        self.map_editor.add_tile(0, 0)
        self.map_editor.map_data[(0, 0)]["items"] = [MockItem("TestItem")]
        self.map_editor.save_map()
        self.assertTrue(os.path.exists(tmp_path))
        with open(tmp_path, 'r') as f:
            saved_data = json.load(f)
        self.assertIn("(0, 0)", saved_data)
        os.unlink(tmp_path)

    @patch('tkinter.filedialog.askopenfilename')
    def test_load_map(self, mock_open_dialog):
        if not self.has_display:
            self.skipTest("No display available")
        test_data = {
            "(0, 0)": {
                "id": "tile_0_0",
                "title": "Test Room",
                "description": "A test room",
                "exits": ["north"],
                "events": [],
                "items": [],
                "npcs": [],
                "objects": []
            }
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            json.dump(test_data, tmp)
            tmp_path = tmp.name
        mock_open_dialog.return_value = tmp_path
        self.map_editor.load_map()
        self.assertIn((0, 0), self.map_editor.map_data)
        tile = self.map_editor.map_data[(0, 0)]
        self.assertEqual(tile["title"], "Test Room")
        os.unlink(tmp_path)


class TestTileEditorWindow(unittest.TestCase):

    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            self.has_display = True
            self.map_data = {
                (0, 0): {
                    "id": "tile_0_0",
                    "title": "Test Room",
                    "description": "A test room",
                    "exits": ["south"],
                    "events": [MockEvent("TestEvent")],
                    "items": [MockItem("TestItem")],
                    "npcs": [],
                    "objects": [],
                    "block_exit": [],
                    "symbol": "T"
                },
                (0, 1): {
                    "id": "tile_0_1",
                    "title": "Adjacent Room",
                    "description": "Adjacent room",
                    "exits": ["north"],
                    "events": [],
                    "items": [],
                    "npcs": [],
                    "objects": []
                }
            }
            self.callback_called = False
            def mock_callback():
                self.callback_called = True
            self.tile_editor = TileEditorWindow(self.root, self.map_data, (0, 0), mock_callback)
        except tk.TclError:
            self.has_display = False
            self.skipTest("No display available for GUI tests")

    def tearDown(self):
        if hasattr(self, 'tile_editor'):
            try:
                self.tile_editor.window.quit()
                self.tile_editor.window.destroy()
            except Exception:
                pass
        if hasattr(self, 'root'):
            try:
                self.root.quit()
                self.root.destroy()
            except Exception:
                pass

    def test_tile_editor_initialization(self):
        if not self.has_display:
            self.skipTest("No display available")
        self.assertIsNotNone(self.tile_editor)
        self.assertEqual(self.tile_editor.pos, (0, 0))
        self.assertEqual(self.tile_editor.tile_data, self.map_data[(0, 0)])
        self.assertIn("south", self.tile_editor.valid_directions)

    def test_save_and_close(self):
        if not self.has_display:
            self.skipTest("No display available")
        # Capture original exits and blocked exits for regression verification
        original_exits = list(self.tile_editor.tile_data.get("exits", []))
        original_blocked = list(self.tile_editor.tile_data.get("block_exit", []))
        self.assertIn("south", original_exits)  # precondition
        self.tile_editor.title_entry.delete(0, tk.END)
        self.tile_editor.title_entry.insert(0, "Modified Title")
        self.tile_editor.description_text.delete("1.0", tk.END)
        self.tile_editor.description_text.insert("1.0", "Modified description")
        # Do NOT touch exits listbox to simulate the bug scenario
        self.tile_editor.save_and_close()
        self.assertEqual(self.tile_editor.tile_data["title"], "Modified Title")
        self.assertEqual(self.tile_editor.tile_data["description"], "Modified description")
        # Regression checks: exits and blocked exits unchanged
        self.assertEqual(self.tile_editor.tile_data.get("exits", []), original_exits)
        self.assertEqual(self.tile_editor.tile_data.get("block_exit", []), original_blocked)
        self.assertTrue(self.callback_called)

    def test_refresh_tags(self):
        if not self.has_display:
            self.skipTest("No display available")
        # Frames are attached to the Toplevel window (dialog), not directly on TileEditorWindow
        events_frame = getattr(self.tile_editor.window, 'events_frame')
        items_frame = getattr(self.tile_editor.window, 'items_frame')
        refresh_tags(self.tile_editor.tile_data['events'], events_frame)
        events = events_frame.get_all()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], MockEvent)
        refresh_tags(self.tile_editor.tile_data['items'], items_frame)
        items = items_frame.get_all()
        self.assertEqual(len(items), 1)
        self.assertIsInstance(items[0], MockItem)

    def test_exit_and_blocked_selection_independence(self):
        if not self.has_display:
            self.skipTest("No display available")
        # Add a second adjacent tile east to provide another direction
        self.map_data[(1,0)] = {
            "id": "tile_1_0","title": "East","description": "East room","exits": ["west"],
            "events": [],"items": [],"npcs": [],"objects": []
        }
        # Rebuild editor to refresh valid directions
        try:
            self.tile_editor.window.destroy()
        except Exception:
            pass
        self.tile_editor = TileEditorWindow(self.root, self.map_data, (0,0), lambda: None)
        # Select one exit (south) and one blocked (east) and ensure independence
        # Find indices
        def index_of(lb, value):
            for i in range(lb.size()):
                if lb.get(i) == value:
                    return i
            return None
        south_i = index_of(self.tile_editor.exits_listbox, 'south')
        east_i = index_of(self.tile_editor.directions_listbox, 'east')
        self.assertIsNotNone(south_i)
        self.assertIsNotNone(east_i)
        # Select south in exits
        self.tile_editor.exits_listbox.selection_set(south_i)
        # Select east in blocked
        self.tile_editor.directions_listbox.selection_set(east_i)
        # Ensure both selections persist
        self.assertIn('south', [self.tile_editor.exits_listbox.get(i) for i in self.tile_editor.exits_listbox.curselection()])
        self.assertIn('east', [self.tile_editor.directions_listbox.get(i) for i in self.tile_editor.directions_listbox.curselection()])


class TestTagListFrame(unittest.TestCase):

    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            self.has_display = True
            # Create a TagListFrame with default behavior
            self.tag_frame = TagListFrame(self.root)
            self.backing_list = []
        except tk.TclError:
            self.has_display = False
            self.skipTest("No display available for GUI tests")

    def tearDown(self):
        if hasattr(self, 'root'):
            try:
                self.root.quit()
                self.root.destroy()
            except Exception:
                pass

    def test_add_and_remove_tag(self):
        if not self.has_display:
            self.skipTest("No display available")
        test_item = MockItem("Test")
        # Simulate list management (refresh_tags normally handles linking list -> tags)
        self.backing_list.append(test_item)
        self.tag_frame.add_tag(test_item, self.backing_list, "Test Item")
        tags = self.tag_frame.get_all()
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], test_item)
        # Remove via frame (will also call remove_element which updates backing list)
        self.tag_frame.remove(test_item, self.backing_list)
        tags = self.tag_frame.get_all()
        self.assertEqual(len(tags), 0)
        self.assertNotIn(test_item, self.backing_list)  # ensure underlying list updated

    def test_clear_tags(self):
        if not self.has_display:
            self.skipTest("No display available")
        i1 = MockItem("Test1")
        i2 = MockItem("Test2")
        self.backing_list.extend([i1, i2])
        self.tag_frame.add_tag(i1, self.backing_list, "Item 1")
        self.tag_frame.add_tag(i2, self.backing_list, "Item 2")
        self.assertEqual(len(self.tag_frame.get_all()), 2)
        self.tag_frame.clear()
        self.assertEqual(len(self.tag_frame.get_all()), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
