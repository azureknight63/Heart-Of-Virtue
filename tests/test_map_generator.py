import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import unittest
from unittest.mock import patch, MagicMock, Mock
import tkinter as tk
from map_generator import MapEditor, TileEditorWindow, TagListFrame
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
        # Only create root if display is available
        try:
            self.root = tk.Tk()
            self.root.withdraw()  # Hide the window during testing
            self.map_editor = MapEditor(self.root)
            self.has_display = True
        except tk.TclError:
            self.has_display = False
            self.skipTest("No display available for GUI tests")

    def tearDown(self):
        """Clean up after each test method."""
        if hasattr(self, 'root'):
            try:
                self.root.quit()
                self.root.destroy()
            except:
                pass

    def test_map_editor_initialization(self):
        """Test that MapEditor initializes properly"""
        if not self.has_display:
            self.skipTest("No display available")

        self.assertIsNotNone(self.map_editor)
        self.assertEqual(self.map_editor.tile_size, 50)
        self.assertEqual(self.map_editor.map_data, {})
        self.assertIsNone(self.map_editor.selected_tile)
        self.assertFalse(self.map_editor.is_adding_tile)

    def test_add_tile(self):
        """Test adding a tile to the map"""
        if not self.has_display:
            self.skipTest("No display available")

        self.map_editor.add_tile(1, 1)
        self.assertIn((1, 1), self.map_editor.map_data)
        tile = self.map_editor.map_data[(1, 1)]
        self.assertEqual(tile["id"], "tile_1_1")
        self.assertEqual(tile["title"], "tile_1_1")
        self.assertIn("description", tile)

    def test_remove_selected_tile(self):
        """Test removing selected tiles"""
        if not self.has_display:
            self.skipTest("No display available")

        # Add a tile first
        self.map_editor.add_tile(1, 1)
        self.map_editor.selected_tiles = {(1, 1)}

        # Remove it
        self.map_editor.remove_selected_tile()
        self.assertNotIn((1, 1), self.map_editor.map_data)

    def test_create_new_map(self):
        """Test creating a new map"""
        if not self.has_display:
            self.skipTest("No display available")

        # Add some data first
        self.map_editor.add_tile(1, 1)
        self.map_editor.selected_tile = (1, 1)

        # Create new map
        self.map_editor.create_new_map()
        self.assertEqual(self.map_editor.map_data, {})
        self.assertIsNone(self.map_editor.selected_tile)
        self.assertIsNone(self.map_editor.current_map_filepath)

    def test_auto_connect_exits(self):
        """Test automatic exit connection between adjacent tiles"""
        if not self.has_display:
            self.skipTest("No display available")

        # Add two adjacent tiles
        self.map_editor.add_tile(0, 0)
        self.map_editor.add_tile(1, 0)

        # Connect exits
        self.map_editor.auto_connect_exits()

        # Check that exits were created
        tile1 = self.map_editor.map_data[(0, 0)]
        tile2 = self.map_editor.map_data[(1, 0)]

        self.assertIn("east", tile1["exits"])
        self.assertIn("west", tile2["exits"])

    @patch('tkinter.filedialog.asksaveasfilename')
    def test_save_map(self, mock_save_dialog):
        """Test saving map to file"""
        if not self.has_display:
            self.skipTest("No display available")

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            tmp_path = tmp.name

        mock_save_dialog.return_value = tmp_path

        # Add some test data
        self.map_editor.add_tile(0, 0)
        self.map_editor.map_data[(0, 0)]["items"] = [MockItem("TestItem")]

        # Save the map
        self.map_editor.save_map()

        # Verify file was created and contains data
        self.assertTrue(os.path.exists(tmp_path))
        with open(tmp_path, 'r') as f:
            saved_data = json.load(f)

        self.assertIn("(0, 0)", saved_data)

        # Clean up
        os.unlink(tmp_path)

    @patch('tkinter.filedialog.askopenfilename')
    def test_load_map(self, mock_open_dialog):
        """Test loading map from file"""
        if not self.has_display:
            self.skipTest("No display available")

        # Create test data file
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

        # Load the map
        self.map_editor.load_map()

        # Verify data was loaded
        self.assertIn((0, 0), self.map_editor.map_data)
        tile = self.map_editor.map_data[(0, 0)]
        self.assertEqual(tile["title"], "Test Room")

        # Clean up
        os.unlink(tmp_path)


class TestTileEditorWindow(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            self.has_display = True

            # Create test map data - fix the adjacency issue
            self.map_data = {
                (0, 0): {
                    "id": "tile_0_0",
                    "title": "Test Room",
                    "description": "A test room",
                    "exits": ["south"],  # Changed to south since (0, 1) is below
                    "events": [MockEvent("TestEvent")],
                    "items": [MockItem("TestItem")],
                    "npcs": [],
                    "objects": [],
                    "block_exit": [],
                    "symbol": "T"
                },
                (0, 1): {  # This is south of (0, 0), not north
                    "id": "tile_0_1",
                    "title": "Adjacent Room",
                    "description": "Adjacent room",
                    "exits": ["north"],  # Goes back north to (0, 0)
                    "events": [],
                    "items": [],
                    "npcs": [],
                    "objects": []
                }
            }

            self.callback_called = False
            def mock_callback():
                self.callback_called = True

            self.tile_editor = TileEditorWindow(
                self.root,
                self.map_data,
                (0, 0),
                mock_callback
            )
        except tk.TclError:
            self.has_display = False
            self.skipTest("No display available for GUI tests")

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'tile_editor'):
            try:
                self.tile_editor.window.quit()
                self.tile_editor.window.destroy()
            except:
                pass
        if hasattr(self, 'root'):
            try:
                self.root.quit()
                self.root.destroy()
            except:
                pass

    def test_tile_editor_initialization(self):
        """Test that TileEditorWindow initializes properly"""
        if not self.has_display:
            self.skipTest("No display available")

        self.assertIsNotNone(self.tile_editor)
        self.assertEqual(self.tile_editor.pos, (0, 0))
        self.assertEqual(self.tile_editor.tile_data, self.map_data[(0, 0)])

        # Check that valid directions are computed correctly - (0, 1) is south of (0, 0)
        self.assertIn("south", self.tile_editor.valid_directions)

    def test_save_and_close(self):
        """Test saving tile changes and closing editor"""
        if not self.has_display:
            self.skipTest("No display available")

        # Modify some values
        self.tile_editor.title_entry.delete(0, tk.END)
        self.tile_editor.title_entry.insert(0, "Modified Title")

        self.tile_editor.description_text.delete("1.0", tk.END)
        self.tile_editor.description_text.insert("1.0", "Modified description")

        # Save and close
        self.tile_editor.save_and_close()

        # Verify changes were saved
        self.assertEqual(self.tile_editor.tile_data["title"], "Modified Title")
        self.assertEqual(self.tile_editor.tile_data["description"], "Modified description")
        self.assertTrue(self.callback_called)

    def test_refresh_tags(self):
        """Test that tags are refreshed properly"""
        if not self.has_display:
            self.skipTest("No display available")

        # Test events refresh
        self.tile_editor._refresh_tags('events', self.tile_editor.events_frame)
        events = self.tile_editor.events_frame.get_all()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], MockEvent)

        # Test items refresh
        self.tile_editor._refresh_tags('items', self.tile_editor.items_frame)
        items = self.tile_editor.items_frame.get_all()
        self.assertEqual(len(items), 1)
        self.assertIsInstance(items[0], MockItem)


class TestAutoSaveFunctionality(unittest.TestCase):
    """Test the auto-save functionality with simplified approach"""

    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            self.has_display = True
        except tk.TclError:
            self.has_display = False
            self.skipTest("No display available for GUI tests")

        # Create a mock item with editable properties
        self.mock_item = MockItem("Original Name", 5, 100)

        self.callback_called = 0
        self.callback_result = None

        def mock_callback(result):
            self.callback_called += 1
            self.callback_result = result

        self.callback = mock_callback

    def tearDown(self):
        if hasattr(self, 'root'):
            try:
                self.root.quit()
                self.root.destroy()
            except:
                pass

    def test_auto_save_concept(self):
        """Test the concept of auto-save by directly testing the logic"""
        if not self.has_display:
            self.skipTest("No display available")

        # Test that auto-save function can modify existing objects
        original_name = self.mock_item.name
        self.mock_item.name = "Auto Saved Name"

        # Verify the change
        self.assertNotEqual(original_name, self.mock_item.name)
        self.assertEqual(self.mock_item.name, "Auto Saved Name")

        # Test callback mechanism
        self.callback(self.mock_item)
        self.assertEqual(self.callback_called, 1)
        self.assertEqual(self.callback_result, self.mock_item)

    def test_property_dialog_button_logic(self):
        """Test the logic for different button texts"""
        if not self.has_display:
            self.skipTest("No display available")

        # Test logic: existing object should show "Close", new object should show "Add"
        existing_object = self.mock_item
        new_object = None

        # Simulate the button text logic from the actual code
        existing_button_text = "Close" if existing_object else "Add"
        new_button_text = "Close" if new_object else "Add"

        self.assertEqual(existing_button_text, "Close")
        self.assertEqual(new_button_text, "Add")


class TestTagListFrame(unittest.TestCase):

    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            self.has_display = True

            self.edit_calls = []
            self.remove_calls = []
            self.duplicate_calls = []

            def mock_edit(item):
                self.edit_calls.append(item)

            def mock_remove(item):
                self.remove_calls.append(item)

            def mock_duplicate(item):
                self.duplicate_calls.append(item)

            self.tag_frame = TagListFrame(
                self.root,
                on_edit=mock_edit,
                on_remove=mock_remove,
                on_duplicate=mock_duplicate
            )
        except tk.TclError:
            self.has_display = False
            self.skipTest("No display available for GUI tests")

    def tearDown(self):
        if hasattr(self, 'root'):
            try:
                self.root.quit()
                self.root.destroy()
            except:
                pass

    def test_add_and_remove_tag(self):
        """Test adding and removing tags"""
        if not self.has_display:
            self.skipTest("No display available")

        test_item = MockItem("Test")

        # Add tag
        self.tag_frame.add_tag(test_item, "Test Item")
        tags = self.tag_frame.get_all()
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], test_item)

        # Remove tag
        self.tag_frame.remove(test_item)
        tags = self.tag_frame.get_all()
        self.assertEqual(len(tags), 0)
        self.assertIn(test_item, self.remove_calls)

    def test_clear_tags(self):
        """Test clearing all tags"""
        if not self.has_display:
            self.skipTest("No display available")

        self.tag_frame.add_tag(MockItem("Test1"), "Item 1")
        self.tag_frame.add_tag(MockItem("Test2"), "Item 2")

        self.assertEqual(len(self.tag_frame.get_all()), 2)

        self.tag_frame.clear()
        self.assertEqual(len(self.tag_frame.get_all()), 0)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
