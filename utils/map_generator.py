import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json
import os
import glob
import ast
import inspect
import sys
import copy
import re
import importlib
from typing import Any, Dict, List, Tuple, Optional, cast, get_origin, get_args, Union, Type  # type hinting (removed unused Iterable)
from typing import get_type_hints  # added for resolving postponed annotations

# Ensure the src directory is in sys.path for imports
project_root = os.path.dirname(os.path.dirname(__file__))
src_root = os.path.join(project_root, 'src')
# Ensure both project root (so 'src' package can be imported) and src_root (direct module access) are available
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if src_root not in sys.path:
    sys.path.insert(0, src_root)

from events import Event  # noqa
from src.npc import Merchant


# Added: custom exception to surface rich context about serialization failures
class MapSerializationError(Exception):
    def __init__(self, *, tile: Tuple[int,int] | None = None, category: str | None = None,
                 index: int | None = None, attribute: str | None = None,
                 object_type: str | None = None, object_repr: str | None = None,
                 original: Exception | None = None, note: str | None = None):
        self.tile = tile
        self.category = category
        self.index = index
        self.attribute = attribute
        self.object_type = object_type
        self.object_repr = object_repr
        self.original = original
        self.note = note
        super().__init__(self.__str__())

    def __str__(self):
        parts: List[str] = ["Map save serialization failed"]
        if self.tile is not None:
            parts.append(f"tile={self.tile}")
        if self.category is not None:
            parts.append(f"category={self.category}")
        if self.index is not None:
            parts.append(f"index={self.index}")
        if self.object_type is not None:
            parts.append(f"object_type={self.object_type}")
        if self.attribute is not None:
            parts.append(f"attribute={self.attribute}")
        if self.original is not None:
            parts.append(f"error={type(self.original).__name__}: {self.original}")
        if self.note:
            parts.append(f"note={self.note}")
        if self.object_repr and len(self.object_repr) < 200:
            parts.append(f"object_repr={self.object_repr}")
        return " | ".join(parts)


def parse_type_hint(annotation):
    """
    Parse a type annotation to determine if it's a class type or list of class types.
    Returns tuple: (base_class, is_list, is_optional)
    """
    if annotation is None or annotation is inspect._empty:
        return None, False, False

    # Handle string annotations (forward references)
    if isinstance(annotation, str):
        # Handle list[...] forward reference in string annotations
        stripped = annotation.strip()
        if (stripped.startswith('list[') or stripped.startswith('List[')) and stripped.endswith(']'):
            # extract inner type
            inner = stripped[stripped.index('[')+1:-1].strip("'\"")
            base_cls, _, is_opt = parse_type_hint(inner)
            return base_cls, True, is_opt
        try:
            # Try to resolve the string annotation
            # For forward references like 'Item', we need to look up in the appropriate module
            if annotation.startswith("'") and annotation.endswith("'"):
                annotation = annotation[1:-1]

            # Try to import from src modules
            for module_name in ['items', 'objects', 'npc', 'events']:
                try:
                    module = importlib.import_module(f'src.{module_name}')
                    if hasattr(module, annotation):
                        return getattr(module, annotation), False, False
                except ImportError:
                    continue
        except Exception:
            pass
        return None, False, False

    # Handle typing constructs
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Handle Optional[T] or Union[T, None]
    if origin is Union:
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1:
            # This is Optional[T]
            base_class, is_list, _ = parse_type_hint(non_none_args[0])
            return base_class, is_list, True

    # Handle List[T]
    elif origin is list or origin is List:
        if args:
            base_class, _, is_optional = parse_type_hint(args[0])
            return base_class, True, is_optional

    # Handle direct class references
    elif inspect.isclass(annotation):
        return annotation, False, False

    return None, False, False


def get_class_hierarchy(base_class, module_names=None):
    """
    Get all subclasses of a given base class from specified modules.
    Returns a dictionary mapping class names to class objects.
    """
    if not base_class:
        return {}

    if module_names is None:
        module_names = ['items', 'objects', 'npc', 'events']

    hierarchy = {base_class.__name__: base_class}

    # Add the base class itself

    # Search through specified modules
    for module_name in module_names:
        try:
            module = importlib.import_module(f'src.{module_name}')
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (inspect.isclass(attr) and
                    issubclass(attr, base_class) and
                    attr is not base_class):
                    hierarchy[attr.__name__] = attr
        except ImportError:
            continue

    return hierarchy


def create_hierarchical_selector(parent, base_class, is_list=False, current_values=None, on_change_callback=None):
    """
    Create a hierarchical selector widget for choosing classes.
    Returns a widget that manages selection of class instances.
    """
    container = tk.Frame(parent, bg="#34495e")

    # Get available classes
    class_hierarchy = get_class_hierarchy(base_class)

    if not class_hierarchy:
        tk.Label(container, text=f"No {base_class.__name__} classes found",
                font=("Helvetica", 9, "italic"), bg="#34495e", fg="#f39c12").pack(fill='x')
        return container, lambda: []

    selected_items = []

    if is_list:
        # Multi-selection for list types
        list_frame = tk.Frame(container, bg="#34495e")
        list_frame.pack(fill='both', expand=True, pady=(0, 5))

        # Listbox to show selected items
        listbox_frame = tk.Frame(list_frame, bg="#34495e")
        listbox_frame.pack(fill='both', expand=True)

        selected_listbox = tk.Listbox(listbox_frame, height=8, bg="#2c3e50", fg="white",
                                     selectbackground="#3498db")
        selected_listbox.pack(fill='both', expand=True, side='left')

        # Scrollbar for listbox
        scrollbar = tk.Scrollbar(listbox_frame, orient='vertical', command=selected_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        selected_listbox.config(yscrollcommand=scrollbar.set)

        # Dropdown to add new items
        add_frame = tk.Frame(container, bg="#34495e")
        add_frame.pack(fill='x', pady=(5, 0))

        tk.Label(add_frame, text=f"Add {base_class.__name__}:", bg="#34495e", fg="white").pack(anchor='w')

        class_var = tk.StringVar()
        class_combo = ttk.Combobox(add_frame, textvariable=class_var,
                                  values=list(class_hierarchy.keys()), state='readonly')
        class_combo.pack(fill='x', pady=(2, 5))

        def add_selected():
            class_name = class_var.get()
            if class_name and class_name in class_hierarchy:
                # Create default instance
                cls = class_hierarchy[class_name]
                try:
                    # Try to create with minimal parameters
                    sig = inspect.signature(cls.__init__)
                    kwargs = {}
                    for param in sig.parameters.values():
                        if param.name in ['self', 'player', 'tile']:
                            continue
                        if param.default is not inspect._empty:
                            continue
                        # Add default values for required parameters
                        if param.annotation == str or param.name in ['name', 'description']:
                            kwargs[param.name] = f"Default {class_name}"
                        elif param.annotation == int:
                            kwargs[param.name] = 0
                        elif param.annotation == float:
                            kwargs[param.name] = 0.0
                        elif param.annotation == bool:
                            kwargs[param.name] = False

                    instance = cls(**kwargs)
                    selected_items.append(instance)
                    selected_listbox.insert(tk.END, f"{class_name}: {getattr(instance, 'name', str(instance))}")
                    class_var.set("")

                    if on_change_callback:
                        on_change_callback()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create {class_name}: {str(e)}")

        tk.Button(add_frame, text="Add", command=add_selected, bg="#27ae60", fg="white").pack(fill='x')

        def remove_selected():
            selection = selected_listbox.curselection()
            if selection:
                index = selection[0]
                selected_listbox.delete(index)
                if index < len(selected_items):
                    selected_items.pop(index)
                if on_change_callback:
                    on_change_callback()

        tk.Button(add_frame, text="Remove Selected", command=remove_selected,
                 bg="#e74c3c", fg="white").pack(fill='x', pady=(2, 0))

        # Initialize with current values
        if current_values:
            for item in current_values:
                if item:
                    selected_items.append(item)
                    class_name = item.__class__.__name__
                    selected_listbox.insert(tk.END, f"{class_name}: {getattr(item, 'name', str(item))}")

        def get_values():
            return selected_items.copy()

    else:
        # Single selection for non-list types
        tk.Label(container, text=f"Select {base_class.__name__}:", bg="#34495e", fg="white").pack(anchor='w')

        class_var = tk.StringVar()
        class_combo = ttk.Combobox(container, textvariable=class_var,
                                  values=["None"] + list(class_hierarchy.keys()), state='readonly')
        class_combo.pack(fill='x')

        current_instance = None

        def on_selection_change(event=None):
            nonlocal current_instance
            class_name = class_var.get()
            if class_name == "None" or not class_name:
                current_instance = None
            elif class_name in class_hierarchy:
                cls = class_hierarchy[class_name]
                try:
                    # Try to create with minimal parameters
                    sig = inspect.signature(cls.__init__)
                    kwargs = {}
                    for param in sig.parameters.values():
                        if param.name in ['self', 'player', 'tile']:
                            continue
                        if param.default is not inspect._empty:
                            continue
                        # Add default values for required parameters
                        if param.annotation == str or param.name in ['name', 'description']:
                            kwargs[param.name] = f"Default {class_name}"
                        elif param.annotation == int:
                            kwargs[param.name] = 0
                        elif param.annotation == float:
                            kwargs[param.name] = 0.0
                        elif param.annotation == bool:
                            kwargs[param.name] = False

                    current_instance = cls(**kwargs)

                    if on_change_callback:
                        on_change_callback()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create {class_name}: {str(e)}")
                    current_instance = None

        class_combo.bind('<<ComboboxSelected>>', on_selection_change)

        # Initialize with current value
        if current_values:
            if hasattr(current_values, '__class__'):
                class_var.set(current_values.__class__.__name__)
                current_instance = current_values
            else:
                class_var.set("None")
        else:
            class_var.set("None")

        def get_values():
            return current_instance

    container.pack(fill='x')
    return container, get_values


def create_button(text, command, parent):
    """
    Helper function to create styled buttons.
    Returns the created button so callers can further customize or retain a reference.
    """
    button = tk.Button(
        parent,
        text=text,
        command=command,
        font=("Helvetica", 12, "bold"),
        bg="#3498db",
        fg="white",
        activebackground="#2980b9",
        activeforeground="white",
        relief="raised",
        bd=3,
        pady=5,
        width=20
    )
    button.pack(fill="x", pady=5)
    return button


def create_separator(parent):
    """
    Helper function to create a visual separator.
    """
    separator = tk.Frame(parent, height=2, bg="#5d6d7e")
    separator.pack(fill="x", pady=10)


def _get_last_map_file():
    """
    Returns the path to the most recently modified JSON map file in cwd, or None.
    """
    try:
        files = glob.glob(os.path.join(os.getcwd(), '*.json'))
        if not files:
            return None
        return max(files, key=os.path.getmtime)
    except Exception:
        return None


class MapEditor:
    """
    A simple map editor for a text-based adventure game.
    Uses tkinter for the GUI and json for file handling.
    """

    def __init__(self, root_window):
        """
        Initializes the main application window and components.
        """
        self.root = root_window
        self.root.title("HOV Map Editor")
        self.root.geometry("1400x800")
        self.root.configure(bg="#2c3e50")
        # Track current map filename/path
        self.current_map_filepath = None
        self.map_title_label = None

        self.map_data = {}  # Stores tile data: {(x, y): { ... }}
        self.tile_size = 50
        self.selected_tile = None
        self.is_adding_tile = False
        self.canvas = None  # Will be initialized in create_widgets
        self.status_label = None  # Will be initialized in create_widgets

        # initialize drag data for panning
        self._drag_data = {"x": 0, "y": 0, "dragged": False}
        self.offset_x = 0  # current pan offset in pixels
        self.offset_y = 0
        # zoom limits
        self.min_tile_size = 20
        self.max_tile_size = 200

        # --- New multi-select state ---
        self.selected_tiles = set()  # set[(x,y)]
        self.selection_anchor = None  # anchor for shift-select
        self.clipboard = None  # {'tiles': { (dx,dy): tile_data_copy }, 'w':w, 'h':h} or {'empty':True}
        self.drag_select_mode = False
        self.drag_start_tile = None
        self.drag_current_tile = None
        # Timestamp throttle for delete key status messages
        self._last_delete_block_msg = 0.0

        # Add placeholders for coord label methods created later

        # --- UI Elements ---
        self.create_widgets()
        self.draw_map()
        # Tooltip widget for showing full titles
        self.tooltip = None
        # Attempt to load most recently saved map
        last_map = _get_last_map_file()
        if last_map:
            self.load_map(last_map)
        else:
            self.update_map_label()

    def update_map_label(self):
        """Update the label showing the current map's file name."""
        if not self.map_title_label:
            return
        if self.current_map_filepath:
            name = os.path.basename(self.current_map_filepath)
        else:
            name = "(Unsaved Map)"
        self.map_title_label.config(text=f"Current Map: {name}")

    def create_widgets(self):
        """
        Creates all the GUI widgets for the application.
        """
        # Top label for current map
        self.map_title_label = tk.Label(self.root, text="Current Map: (Unsaved Map)",
                                        bg="#1f2d3a", fg="white", font=("Helvetica", 14, "bold"), pady=6)
        self.map_title_label.pack(side="top", fill="x")
        # Coordinate tooltip label (always visible bottom-right)
        self.coord_label = tk.Label(self.root, text="Tile (0,0)  px(0,0)", bg="#1f2d3a", fg="white", font=("Helvetica", 9))
        self.coord_label.place(relx=1.0, rely=1.0, x=-6, y=-6, anchor='se')
        # Update on any mouse movement inside the root
        self.root.bind('<Motion>', self._update_mouse_coordinates)
        # Also update periodically in case of external offset changes without movement
        self.root.after(200, self._poll_mouse_position)
        # Main Frame for UI controls
        controls_frame = tk.Frame(self.root, bg="#34495e", padx=10, pady=10)
        controls_frame.pack(side="left", fill="y")

        # Map Canvas
        self.canvas = tk.Canvas(self.root, bg="#ecf0f1", width=800, height=800, relief="sunken", bd=2)
        self.canvas.pack(side="right", expand=True, fill="both", padx=10, pady=10)
        # Pan canvas and handle clicks
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        # Right mouse button now used for panning
        self.canvas.bind("<ButtonPress-3>", self.on_pan_start)
        self.canvas.bind("<B3-Motion>", self.on_pan_move)
        self.canvas.bind("<ButtonRelease-3>", self.on_pan_end)
        # Double-click on a tile to edit it directly
        self.canvas.bind("<Double-Button-1>", self.handle_canvas_double_click)
        # Press Enter to edit currently selected tile
        self.root.bind("<Return>", self.handle_enter_key)
        # Zoom with Ctrl + scroll
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom)
        # Shortcut key bindings for selection clipboard operations
        self.root.bind_all('<Control-c>', lambda e: self.copy_selection())
        self.root.bind_all('<Control-C>', lambda e: self.copy_selection())
        self.root.bind_all('<Control-x>', lambda e: self.cut_selection())
        self.root.bind_all('<Control-X>', lambda e: self.cut_selection())
        self.root.bind_all('<Control-v>', lambda e: self.paste_clipboard())
        self.root.bind_all('<Control-V>', lambda e: self.paste_clipboard())
        # Changed: route Delete key through guard handler so it is disabled while editor/property submenus are open.
        self.root.bind_all('<Delete>', self._delete_hotkey_handler)
        # --- Control Buttons ---
        create_button("New Map", lambda: (self.ensure_add_mode_off(), self.create_new_map()), controls_frame)
        create_button("Load Map", lambda: (self.ensure_add_mode_off(), self.load_map()), controls_frame)
        create_button("Load Legacy Map", lambda: (self.ensure_add_mode_off(), self.load_legacy_map()), controls_frame)
        create_button("Save Map", lambda: (self.ensure_add_mode_off(), self.save_map()), controls_frame)
        create_separator(controls_frame)

        # Keep reference to Add Tile button to allow visual toggle
        self.add_tile_button = create_button("Add Tile", self.toggle_add_tile_mode, controls_frame)
        create_button("Remove Tile", lambda: (self.ensure_add_mode_off(), self.remove_selected_tile()), controls_frame)
        create_button("Edit Tile", lambda: (self.ensure_add_mode_off(), self.edit_selected_tile()), controls_frame)
        create_separator(controls_frame)

        create_button("Auto-Connect Exits", lambda: (self.ensure_add_mode_off(), self.auto_connect_exits()), controls_frame)
        create_separator(controls_frame)

        # Status Label
        self.status_label = tk.Label(
            controls_frame,
            text="Ready.",
            bg="#34495e",
            fg="white",
            font=("Helvetica", 10),
            wraplength=200,
            justify="left"
        )
        self.status_label.pack(side="bottom", fill="x", pady=(10, 0))
        # Adjust wraplength dynamically to match panel width
        controls_frame.bind("<Configure>", lambda e: self.status_label.config(wraplength=e.width))
        # Ensure coordinate label is on top of canvas stacking order
        self._raise_coord_label()

    def _raise_coord_label(self):
        """Raise (lift) the coordinate label above the canvas so it is never obscured."""
        if getattr(self, 'coord_label', None):
            try:
                self.coord_label.lift()  # lift above sibling widgets
            except Exception:
                pass

    def handle_canvas_click(self, event):
        """Updated to support modifier-based multi-select and empty tile selection."""
        x = int((event.x - self.offset_x) // self.tile_size)
        y = int((event.y - self.offset_y) // self.tile_size)
        pos = (x,y)
        ctrl = (event.state & 0x0004) != 0
        shift = (event.state & 0x0001) != 0
        if self.is_adding_tile:
            if pos not in self.map_data:
                self.add_tile(x,y)
                self.set_status(f"Added new tile at ({x}, {y}).")
            else:
                self.set_status(f"Tile already exists at ({x}, {y}).")
            return
        # Selection logic
        if shift and self.selection_anchor:
            ax,ay = self.selection_anchor
            minx,maxx = sorted((ax,x))
            miny,maxy = sorted((ay,y))
            region = {(ix,iy) for ix in range(minx,maxx+1) for iy in range(miny,maxy+1)}
            self.selected_tiles.update(region)
        elif ctrl:
            if pos in self.selected_tiles:
                self.selected_tiles.remove(pos)
            else:
                self.selected_tiles.add(pos)
                self.selection_anchor = self.selection_anchor or pos
        else:
            self.selected_tiles = {pos}
            self.selection_anchor = pos
        self.selected_tile = pos if pos in self.map_data else None
        if pos not in self.map_data:
            self._show_empty_coord_tooltip(pos)
        self.draw_map()

    def create_new_map(self):
        """Clears the current map data to start a new map."""
        self.map_data = {}
        self.selected_tile = None
        self.current_map_filepath = None
        self.draw_map()
        self.update_map_label()
        self.set_status("New map created.")

    def add_tile(self, x, y):
        """
        Adds a new tile at the specified coordinates.
        """
        tile_id = f"tile_{x}_{y}"
        self.map_data[(x, y)] = {
            "id": tile_id,
            # Title for display; defaults to tile_id
            "title": tile_id,
            "description": f"A newly created room at ({x}, {y}).",
            "exits": [],
            "events": [],
            "items": [],
            "npcs": [],
            "objects": []
        }
        # Normalize map so there are at most 2 empty rows/cols above/left
        self._normalize_min_padding()
        self.draw_map()

    def _normalize_min_padding(self):
        """Ensure there are at most 2 empty rows above the topmost tile and
        at most 2 empty columns to the left of the leftmost tile.
        Shifts all tiles (and updates their ids) if necessary.
        """
        if not self.map_data:
            return
        min_x = min(pos[0] for pos in self.map_data.keys())
        min_y = min(pos[1] for pos in self.map_data.keys())
        shift_x = max(0, min_x - 2)
        shift_y = max(0, min_y - 2)
        if shift_x == 0 and shift_y == 0:
            return  # nothing to do
        new_map = {}
        for (x, y), tile in self.map_data.items():
            old_id = tile.get('id')
            old_title = tile.get('title')
            nx, ny = x - shift_x, y - shift_y
            tile = dict(tile)  # shallow copy
            new_id = f"tile_{nx}_{ny}"
            tile['id'] = new_id
            # If the title was auto-generated (matched the old id), update it to new id
            if old_title == old_id:
                tile['title'] = new_id
            new_map[(nx, ny)] = tile
        # Update selected tile reference if present
        if self.selected_tile:
            sx, sy = self.selected_tile
            self.selected_tile = (sx - shift_x, sy - shift_y)
        # Update all multi-selected tiles
        if self.selected_tiles:
            self.selected_tiles = {(x - shift_x, y - shift_y) for (x, y) in self.selected_tiles}
            if self.selection_anchor:
                ax, ay = self.selection_anchor
                self.selection_anchor = (ax - shift_x, ay - shift_y)
        self.map_data = new_map

    def remove_selected_tile(self):
        """Removes all selected tiles (supports multi-select)."""
        if not self.selected_tiles:
            self.set_status("No tiles selected to remove.")
            return
        removed = 0
        for p in list(self.selected_tiles):
            if p in self.map_data:
                del self.map_data[p]
                removed += 1
        # Clean exits on remaining tiles
        if removed:
            deltas = {"north":(0,-1),"south":(0,1),"west":(-1,0),"east":(1,0),
                      "northeast":(1,-1),"northwest":(-1,-1),"southeast":(1,1),"southwest":(-1,1)}
            for pos_key, tile in self.map_data.items():
                def neighbor_exists(direction):
                    dx,dy = deltas[direction]
                    return (pos_key[0]+dx, pos_key[1]+dy) in self.map_data
                tile["exits"] = [d for d in tile.get("exits", []) if d in deltas and neighbor_exists(d)]
                tile["block_exit"] = [d for d in tile.get("block_exit", []) if d in deltas and neighbor_exists(d)]
            self._normalize_min_padding()
            self.draw_map()
            self.set_status(f"Removed {removed} tile(s).")
        else:
            self.set_status("No existing tiles in selection to remove.")
        self.selected_tile = None

    def edit_selected_tile(self):
        """
        Opens a new window to edit the properties of the selected tile.
        """
        if self.selected_tile:
            # pass full map and position so editor can filter directions
            TileEditorWindow(self.root, self.map_data, self.selected_tile, self.draw_map)
        else:
            self.set_status("No tile selected to edit.")

    def toggle_add_tile_mode(self):
        """
        Toggles the add tile mode and updates the Add Tile button appearance.
        """
        self.is_adding_tile = not self.is_adding_tile
        if self.is_adding_tile:
            self.set_status("Click on the canvas to add a new tile.")
            self.select_tile(None)
            if hasattr(self, 'add_tile_button') and self.add_tile_button:
                self.add_tile_button.config(relief='sunken', bg='#e67e22', activebackground='#d35400')
        else:
            self.set_status("Add tile mode off.")
            if hasattr(self, 'add_tile_button') and self.add_tile_button:
                self.add_tile_button.config(relief='raised', bg='#3498db', activebackground='#2980b9')

    def auto_connect_exits(self):
        """Automatically creates exits between adjacent tiles (cardinal + diagonal)."""
        # Clear existing exits
        for tile in self.map_data.values():
            tile["exits"] = []
        deltas = {"north":(0,-1),"south":(0,1),"west":(-1,0),"east":(1,0),
                  "northeast":(1,-1),"northwest":(-1,-1),"southeast":(1,1),"southwest":(-1,1)}
        reciprocal = {"north":"south","south":"north","west":"east","east":"west",
                      "northeast":"southwest","northwest":"southeast",
                      "southeast":"northwest","southwest":"northeast"}
        for pos, tile in self.map_data.items():
            x,y = pos
            for direction,(dx,dy) in deltas.items():
                nbr = (x+dx, y+dy)
                if nbr in self.map_data:
                    if direction not in tile["exits"]:
                        tile["exits"].append(direction)
                    rev = reciprocal[direction]
                    if rev not in self.map_data[nbr]["exits"]:
                        self.map_data[nbr]["exits"].append(rev)
        self.draw_map()
        self.set_status("Exits automatically connected.")

    # -------------------- Selection & Clipboard Helpers --------------------
    def _event_to_tile(self, event):
        return (int((event.x - self.offset_x) // self.tile_size), int((event.y - self.offset_y) // self.tile_size))

    def _on_mouse_down(self, event):
        # If in add-tile mode, preserve original click behavior (no marquee drag)
        if self.is_adding_tile:
            self.drag_select_mode = False
            self.handle_canvas_click(event)
            return
        pos = self._event_to_tile(event)
        ctrl = (event.state & 0x0004) != 0
        shift = (event.state & 0x0001) != 0
        # Prepare for potential drag selection (always allow marquee now; modifiers affect behavior on release)
        self.drag_select_mode = True
        self.drag_start_tile = pos
        self.drag_current_tile = pos
        self._drag_started = False  # track whether user actually dragged across tiles
        # Store modifier state for use on mouse up
        self._drag_ctrl = ctrl
        self._drag_shift = shift
        # Record initial pointer for potential future use
        self._drag_data['x'] = event.x
        self._drag_data['y'] = event.y
        self._drag_data['dragged'] = False

    def _on_mouse_drag(self, event):
        # Update current tile during drag and show marquee if movement crosses tile boundary
        if not self.drag_select_mode or self.drag_start_tile is None:
            return
        current = self._event_to_tile(event)
        if current != self.drag_current_tile:
            self.drag_current_tile = current
            self._drag_started = True
            self.draw_map()  # redraw tiles
            # draw selection rectangle overlay
            x0, y0 = self.drag_start_tile
            x1, y1 = self.drag_current_tile
            minx, maxx = sorted((x0, x1))
            miny, maxy = sorted((y0, y1))
            for x in range(minx, maxx + 1):
                for y in range(miny, maxy + 1):
                    rx1 = x * self.tile_size + self.offset_x
                    ry1 = y * self.tile_size + self.offset_y
                    rx2 = rx1 + self.tile_size
                    ry2 = ry1 + self.tile_size
                    self.canvas.create_rectangle(rx1, ry1, rx2, ry2, outline='black', dash=(3, 2))
        self._drag_data['dragged'] = True

    def _on_mouse_up(self, event):
        # Finish marquee or treat as click if no drag started
        if self.drag_select_mode and self.drag_start_tile is not None:
            if self._drag_started and self.drag_current_tile is not None:
                # Marquee selection
                x0, y0 = self.drag_start_tile
                x1, y1 = self.drag_current_tile
                minx, maxx = sorted((x0, x1))
                miny, maxy = sorted((y0, y1))
                new_region = {(x, y) for x in range(minx, maxx + 1) for y in range(miny, maxy + 1)}
                ctrl = self._drag_ctrl
                shift = self._drag_shift
                if ctrl:
                    toggled = set()
                    for p in new_region:
                        if p in self.selected_tiles:
                            self.selected_tiles.remove(p)
                        else:
                            self.selected_tiles.add(p)
                            toggled.add(p)
                    if toggled:
                        self.selection_anchor = next(iter(toggled))
                elif shift:
                    self.selected_tiles.update(new_region)
                    if not self.selection_anchor and new_region:
                        self.selection_anchor = next(iter(new_region))
                else:
                    self.selected_tiles = new_region
                    self.selection_anchor = next(iter(new_region)) if new_region else None
                # Determine primary selected tile (first existing one, else any)
                self.selected_tile = None
                for p in self.selected_tiles:
                    if p in self.map_data:
                        self.selected_tile = p
                        break
                if not self.selected_tile and self.selected_tiles:
                    self.selected_tile = next(iter(self.selected_tiles))
                self.draw_map()
            else:
                # Treat as single click (no tile movement) preserving prior semantics
                self.handle_canvas_click(event)
        # Reset drag state
        self.drag_select_mode = False
        self.drag_start_tile = None
        self.drag_current_tile = None
        # Added helpers for enhanced drag-select logic
        self._drag_started = False
        self._drag_ctrl = False
        self._drag_shift = False
        self._drag_data['dragged'] = False

    def select_tile(self, pos):
        """Override to support multi-select single clicks (clears others unless ctrl/shift)."""
        # When called from legacy code treat as single selection reset
        if pos is None:
            self.selected_tile = None
            self.selected_tiles.clear()
            self.selection_anchor = None
        else:
            self.selected_tile = pos
            self.selected_tiles = {pos}
            self.selection_anchor = pos
            # If selecting empty tile show coords tooltip
            if pos not in self.map_data:
                self._show_empty_coord_tooltip(pos)
        self.draw_map()

    def _show_empty_coord_tooltip(self, pos):
        class _E:  # simple object to mimic event
            def __init__(self, root):
                self.x_root = root.winfo_pointerx()
                self.y_root = root.winfo_pointery()
        self.show_tooltip(_E(self.root), f"Empty ({pos[0]}, {pos[1]})")

    def copy_selection(self):
        if not self.selected_tiles:
            return
        # Single empty tile -> mark empty clipboard
        if len(self.selected_tiles) == 1:
            only = next(iter(self.selected_tiles))
            if only not in self.map_data:
                self.clipboard = {'empty': True}
                self.set_status('Copied empty tile placeholder.')
                return
        # Capture tiles present within selection
        tiles_present = {p: self.map_data[p] for p in self.selected_tiles if p in self.map_data}
        if not tiles_present:
            self.clipboard = {'empty': True}
            self.set_status('Copied empty area (acts as delete on paste).')
            return
        minx = min(p[0] for p in tiles_present)
        miny = min(p[1] for p in tiles_present)
        payload = {}
        for (x,y), tile in tiles_present.items():
            rel = (x - minx, y - miny)
            payload[rel] = copy.deepcopy(tile)
        w = 1 + max(p[0] for p in payload.keys())
        h = 1 + max(p[1] for p in payload.keys())
        self.clipboard = {'tiles': payload, 'w': w, 'h': h}
        self.set_status(f'Copied {len(payload)} tile(s).')

    def cut_selection(self):
        self.copy_selection()
        # Only remove if clipboard not empty placeholder
        if self.clipboard and self.clipboard.get('empty'):
            return  # nothing to cut; treat like copying empty
        removed = 0
        for p in list(self.selected_tiles):
            if p in self.map_data:
                del self.map_data[p]
                removed += 1
        if removed:
            self._normalize_min_padding()
            self.draw_map()
        self.set_status(f'Cut {removed} tile(s).')

    def paste_clipboard(self):
        if not self.clipboard or not self.selected_tiles:
            return
        # Empty clipboard => delete selected existing tiles
        if self.clipboard.get('empty'):
            removed = 0
            for p in list(self.selected_tiles):
                if p in self.map_data:
                    del self.map_data[p]
                    removed += 1
            if removed:
                self._normalize_min_padding()
                self.draw_map()
            self.set_status(f'Deleted {removed} tile(s) via empty paste.')
            return
        payload = self.clipboard.get('tiles', {})
        if not payload:
            return
        # If clipboard has single tile and selection has multiple -> replicate
        if len(payload) == 1 and len(self.selected_tiles) > 1:
            rel_pos, tile_data = next(iter(payload.items()))
            for target in self.selected_tiles:
                self._paste_single_tile(tile_data, target)
            self._normalize_min_padding()
            self.draw_map()
            self.set_status(f'Pasted tile to {len(self.selected_tiles)} positions.')
            return
        # Otherwise paste relative pattern anchored at first selected tile
        anchor = next(iter(sorted(self.selected_tiles)))
        base = min(payload.keys())  # smallest (dx,dy) lexicographically
        count = 0
        for (dx,dy), tile_data in payload.items():
            offsetx = dx - base[0]
            offsety = dy - base[1]
            target = (anchor[0] + offsetx, anchor[1] + offsety)
            self._paste_single_tile(tile_data, target)
            count += 1
        self._normalize_min_padding()
        self.draw_map()
        self.set_status(f'Pasted {count} tile(s).')

    def _paste_single_tile(self, tile_data, target):
        x,y = target
        new_id = f"tile_{x}_{y}"
        tcopy = copy.deepcopy(tile_data)
        old_id = tcopy.get('id')
        old_title = tcopy.get('title')
        tcopy['id'] = new_id
        if old_title == old_id or re.fullmatch(r'tile_\d+_\d+', str(old_title)):
            tcopy['title'] = new_id
        self.map_data[target] = tcopy

    # -------------------- Modified existing methods --------------------
    def draw_map(self):
        """
        Draws all tiles and their exits on the canvas.
        """
        if self.canvas:
            self.canvas.delete("all")
        for pos, tile in self.map_data.items():
            self.draw_tile(pos)
            self.draw_exits(pos, tile)
            self.draw_symbol(pos, tile)
            self.draw_blocked(pos, tile)
            # bring title and counts on top of all other elements
            title_tag = f"title_{pos[0]}_{pos[1]}"
            counts_tag = f"counts_{pos[0]}_{pos[1]}"
            self.canvas.tag_raise(title_tag)
            self.canvas.tag_raise(counts_tag)
        # Draw selection outlines for multi-select (including empty selected cells)
        for p in self.selected_tiles:
            if p not in self.map_data:  # empty cell
                x,y = p
                x1 = x * self.tile_size + self.offset_x
                y1 = y * self.tile_size + self.offset_y
                x2 = x1 + self.tile_size
                y2 = y1 + self.tile_size
                self.canvas.create_rectangle(x1,y1,x2,y2, outline='black', width=2)
                # small coord text inside
                self.canvas.create_text((x1+x2)/2, (y1+y2)/2, text=f"{x},{y}", fill='black', font=("Helvetica",8))
            else:
                # Highlight already handled by tile color; add border for clarity if multi-select
                if len(self.selected_tiles) > 1:
                    x,y = p
                    x1 = x * self.tile_size + self.offset_x
                    y1 = y * self.tile_size + self.offset_y
                    x2 = x1 + self.tile_size
                    y2 = y1 + self.tile_size
                    self.canvas.create_rectangle(x1,y1,x2,y2, outline='yellow', width=2)
        # After drawing, re-raise coord label so it stays visible
        self._raise_coord_label()

    def draw_tile(self, pos):
        """
        Draws a single tile and its ID on the canvas.
        """
        x, y = pos
        x1 = x * self.tile_size + self.offset_x
        y1 = y * self.tile_size + self.offset_y
        x2, y2 = x1 + self.tile_size, y1 + self.tile_size

        color = "#e67e22" if pos == self.selected_tile else "#3498db"
        # draw tile rectangle with tag
        tag = f"tile_{x}_{y}"
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="#2c3e50", tags=(tag,))
        # show exclamation points if there are events
        tile = self.map_data.get(pos, {})
        if tile.get("events"):
            center_y = y1 + self.tile_size / 2
            ex_size = int(self.tile_size * 0.4)
            left_x = x1 + ex_size / 2
            right_x = x2 - ex_size / 2
            self.canvas.create_text(left_x, center_y, text="!", fill="red", font=("Helvetica", ex_size, "bold"))
            self.canvas.create_text(right_x, center_y, text="!", fill="red", font=("Helvetica", ex_size, "bold"))

        # Display truncated title at top
        title = self.map_data.get(pos, {}).get("title", self.map_data[pos]["id"])
        max_chars = max(int(self.tile_size / 6), 1)
        disp = title if len(title) <= max_chars else title[:max_chars-1] + "…"
        title_tag = f"title_{x}_{y}"
        self.canvas.create_text(
            x1 + self.tile_size / 2,
            y1 + 2,
            text=disp,
            fill="white",
            font=("Helvetica", 8, "bold"),
            anchor="n",
            tags=(tag, title_tag)
        )

        # NEW: Bottom-centered overlay label with counts of Items, NPCs, and Objects
        items_cnt = len(tile.get("items", []))
        npcs_cnt = len(tile.get("npcs", []))
        objs_cnt = len(tile.get("objects", []))
        counts_text = f"I:{items_cnt}, N:{npcs_cnt}, O:{objs_cnt}"
        # dynamic font size scaled to tile size with a minimum for readability
        font_size = max(6, int(self.tile_size * 0.08))
        counts_tag = f"counts_{x}_{y}"
        self.canvas.create_text(
            (x1 + x2) / 2,
            y2 - 2,  # slight padding from bottom edge
            text=counts_text,
            fill="white",
            font=("Helvetica", font_size, "bold"),
            anchor="s",  # anchor south so text sits just above given y
            tags=(tag, counts_tag)
        )

        # bind tooltip events to tile area
        self.canvas.tag_bind(tag, "<Enter>", lambda e, t=title: self.show_tooltip(e, t))
        self.canvas.tag_bind(tag, "<Leave>", lambda e: self.hide_tooltip())

    def draw_exits(self, pos, tile):
        """
        Draws lines representing exits from a tile.
        """
        x_center = pos[0] * self.tile_size + self.tile_size / 2 + self.offset_x
        y_center = pos[1] * self.tile_size + self.tile_size / 2 + self.offset_y
        deltas = {"north":(0,-1),"south":(0,1),"west":(-1,0),"east":(1,0),
                  "northeast":(1,-1),"northwest":(-1,-1),"southeast":(1,1),"southwest":(-1,1)}
        reciprocal = {"north":"south","south":"north","west":"east","east":"west",
                      "northeast":"southwest","northwest":"southeast",
                      "southeast":"northwest","southwest":"northeast"}
        for direction in tile.get("exits", []):
            dx, dy = deltas.get(direction, (0,0))
            target_pos = (pos[0] + dx, pos[1] + dy)
            if target_pos in self.map_data:
                x_target = target_pos[0] * self.tile_size + self.tile_size / 2 + self.offset_x
                y_target = target_pos[1] * self.tile_size + self.tile_size / 2 + self.offset_y
                bidir = reciprocal.get(direction) in self.map_data[target_pos].get("exits", [])
                arrow_style = tk.BOTH if bidir else tk.LAST
                self.canvas.create_line(x_center, y_center, x_target, y_target,
                                        arrow=arrow_style, fill="#2c3e50", width=2)

    def save_map(self):
        """
        Saves the current map data to a JSON file.
        Enhanced: Provides detailed diagnostic information (tile, category, index, object type, attribute) if
        serialization fails so the user can quickly locate and fix problematic data.
        """
        try:
            # build serializable structure
            def serialize_instance(inst: Any, seen=None, *, tile_pos=None, category=None, index=None) -> Dict[str, Any] | str:
                if seen is None:
                    seen = set()
                obj_id = id(inst)
                if obj_id in seen:
                    return f"<circular_ref:{type(inst).__name__}>"
                seen.add(obj_id)
                def recursive_serialize(val, *, attr_name=None):
                    try:
                        if inspect.isclass(val):
                            return {"__class_type__": f"{val.__module__}:{val.__name__}"}
                        if isinstance(val, (int, float, str, bool)) or val is None:
                            return val
                        elif isinstance(val, list):
                            out = []
                            for i, subv in enumerate(val):
                                try:
                                    out.append(recursive_serialize(subv, attr_name=f"{attr_name}[{i}]") )
                                except MapSerializationError:
                                    raise
                                except Exception as ex_list:
                                    raise MapSerializationError(tile=tile_pos, category=category, index=index,
                                                                 attribute=f"{attr_name}[{i}]", object_type=type(subv).__name__,
                                                                 object_repr=repr(subv)[:180], original=ex_list)
                            return out
                        elif isinstance(val, tuple):
                            tup_out = []
                            for i, subv in enumerate(val):
                                try:
                                    tup_out.append(recursive_serialize(subv, attr_name=f"{attr_name}({i})") )
                                except MapSerializationError:
                                    raise
                                except Exception as ex_tup:
                                    raise MapSerializationError(tile=tile_pos, category=category, index=index,
                                                                 attribute=f"{attr_name}({i})", object_type=type(subv).__name__,
                                                                 object_repr=repr(subv)[:180], original=ex_tup)
                            return tup_out  # store tuples as lists
                        elif isinstance(val, dict):
                            result_dict = {}
                            for dk, dv in val.items():
                                try:
                                    result_dict[dk] = recursive_serialize(dv, attr_name=f"{attr_name}.{dk}" if attr_name else str(dk))
                                except MapSerializationError:
                                    raise
                                except Exception as ex_dict:
                                    raise MapSerializationError(tile=tile_pos, category=category, index=index,
                                                                 attribute=f"{attr_name}.{dk}" if attr_name else str(dk),
                                                                 object_type=type(dv).__name__, object_repr=repr(dv)[:180], original=ex_dict)
                            return result_dict
                        elif hasattr(val, '__dict__'):
                            return serialize_instance(val, seen, tile_pos=tile_pos, category=category, index=index)
                        else:
                            # Fallback: best-effort stringification
                            return str(val)
                    except MapSerializationError:
                        raise
                    except Exception as ex_other:
                        raise MapSerializationError(tile=tile_pos, category=category, index=index,
                                                     attribute=attr_name, object_type=type(val).__name__,
                                                     object_repr=repr(val)[:180], original=ex_other)
                try:
                    data = {}
                    for kx, vx in vars(inst).items():
                        if kx.startswith('_'):
                            continue
                        try:
                            data[kx] = recursive_serialize(vx, attr_name=kx)
                        except MapSerializationError:
                            raise
                        except Exception as ex_attr:
                            raise MapSerializationError(tile=tile_pos, category=category, index=index,
                                                         attribute=kx, object_type=type(vx).__name__,
                                                         object_repr=repr(vx)[:180], original=ex_attr)
                    # Attempt to include merchant property if accessible
                    if 'merchant' not in data and hasattr(inst, 'merchant'):
                        try:
                            mval = getattr(inst, 'merchant')
                            data['merchant'] = recursive_serialize(mval, attr_name='merchant')
                        except Exception:
                            pass
                except MapSerializationError:
                    raise
                except Exception as ex_unknown:
                    raise MapSerializationError(tile=tile_pos, category=category, index=index,
                                                 attribute='__dict__', object_type=type(inst).__name__,
                                                 object_repr=repr(inst)[:180], original=ex_unknown)
                return {
                    '__class__': inst.__class__.__name__,
                    '__module__': inst.__class__.__module__,
                    'props': data
                }
            serializable_map: Dict[str, Any] = {}
            for k, v in self.map_data.items():
                tile: Dict[str, Any] = dict(v)
                # Serialize each instance collection with granular error handling
                for key in ['events','items','npcs','objects']:
                    inst_list = tile.get(key, [])
                    serialized_instances = []
                    for idx, inst in enumerate(inst_list):
                        try:
                            serialized_instances.append(serialize_instance(inst, tile_pos=k, category=key, index=idx))
                        except MapSerializationError as mse:
                            # Re-raise to outer except so unified handling occurs
                            raise mse
                        except Exception as ex_generic:
                            raise MapSerializationError(tile=k, category=key, index=idx,
                                                        object_type=type(inst).__name__, object_repr=repr(inst)[:180],
                                                        original=ex_generic, note='Generic serialization failure')
                    tile[key] = serialized_instances
                serializable_map[str(k)] = tile

            # Default save directory
            default_dir = os.path.join(os.getcwd(), 'src', 'resources', 'maps')
            os.makedirs(default_dir, exist_ok=True)
            filepath = filedialog.asksaveasfilename(
                initialdir=default_dir,
                defaultextension='.json',
                filetypes=[('JSON files', '*.json')]
            )
            if filepath:
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(serializable_map, f, indent=4)
                except Exception as ex_write:
                    raise MapSerializationError(note='Failed writing JSON to disk', original=ex_write)
                self.current_map_filepath = filepath
                self.update_map_label()
                self.set_status(f"Map saved to {os.path.basename(filepath)}")
        except MapSerializationError as mse:
            detailed = str(mse)
            self.set_status(f"Error saving map: {detailed}")
            try:
                messagebox.showerror('Save Error', detailed)
            except Exception:
                pass
        except Exception as e:
            # Fallback generic error (unexpected)
            self.set_status(f"Error saving map: {type(e).__name__}: {e}")
            try:
                messagebox.showerror('Save Error', f"Unexpected error saving map:\n{type(e).__name__}: {e}")
            except Exception:
                pass

    def load_map(self, filepath=None):
        """
        Loads map data from a JSON file.
        """
        if filepath is None:
            filepath = filedialog.askopenfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )
        if filepath:
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                def deserialize_instance(d):
                    # NEW: restore class objects
                    if isinstance(d, dict) and '__class_type__' in d:
                        spec = d['__class_type__']
                        try:
                            mod_name, cls_name = spec.rsplit(':', 1)
                            if mod_name and cls_name:
                                if not mod_name.startswith('src.') and mod_name != 'builtins':
                                    mod_name = f'src.{mod_name}'
                                module = importlib.import_module(mod_name)
                                return getattr(module, cls_name)
                        except Exception:
                            return spec  # fallback to string spec
                    # Recursively reconstruct any dict with __class__' and '__module__' as an object
                    if isinstance(d, dict):
                        if '__class__' in d and '__module__' in d:
                            cls_name = d.get('__class__')
                            mod_name = d.get('__module__')
                            # Normalize module name for items, moves, etc.
                            if mod_name != 'builtins' and not mod_name.startswith('src.'):
                                mod_name = f'src.{mod_name}'
                            props = d.get('props', {})
                            try:
                                module = importlib.import_module(mod_name)
                                cls = getattr(module, cls_name)
                                try:
                                    param_names = [p.name for p in inspect.signature(cls.__init__).parameters.values() if p.name != 'self']
                                    init_kwargs = {k: deserialize_instance(v) for k, v in props.items() if k in param_names}
                                    inst = cls(**init_kwargs)
                                except Exception:
                                    inst = cls.__new__(cls)
                                    try:
                                        cls.__init__(inst)  # type: ignore
                                    except Exception:
                                        pass
                                # Recursively set all attributes, not just constructor args
                                for k2, v2 in props.items():
                                    setattr(inst, k2, deserialize_instance(v2))
                                return inst
                            except Exception:
                                return d
                        else:
                            # Recursively process all dict values
                            return {k: deserialize_instance(v) for k, v in d.items()}
                    elif isinstance(d, list):
                        return [deserialize_instance(x) for x in d]
                    elif isinstance(d, tuple):
                        return tuple(deserialize_instance(x) for x in d)
                    else:
                        return d
                self.map_data = {}
                for k, tile in data.items():
                    # Skip non-coordinate entries (e.g., 'meta') that cannot be parsed as tuple of ints
                    try:
                        pos = tuple(int(x) for x in k.strip('()').split(','))
                    except ValueError:
                        continue
                    tile_copy: Dict[str, Any] = dict(tile)
                    for key in ['events','items','npcs','objects']:
                        tile_copy[key] = [deserialize_instance(d) for d in tile_copy.get(key, [])]  # type: ignore[assignment]
                    self.map_data[pos] = tile_copy
                self.current_map_filepath = filepath
                self.selected_tile = None
                self.draw_map()
                self.update_map_label()
                self.set_status(f"Map loaded from {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not load map file:\n{e}")
                self.set_status("Error loading map.")

    def load_legacy_map(self, filepath=None):
        """Load a legacy text-based map (.txt) into the editor.
        Format assumptions (best-effort based on sample):
        - File is a tab-delimited grid; each non-empty cell (except 'Boundary') defines a tile.
        - Cell content tokens are separated by '|'. First plain token is base tile name/title.
        - Tokens starting with '!Block.' specify blocked directions separated by '.' after '!Block.'.
        - Tokens starting with '@TileDescription.' then a numeric id then '.' then free text (terminated by optional '~'). Sets tile description.
        - Tokens starting with '#' define items: #ClassName[:count or :rMin-Max]. Count defaults to 1 or min of range.
        - Tokens starting with '@' define objects/NPCs/events by class name after '@'. Additional dotted suffixes ignored except embedded item/event markers (# / !).
        - Tokens starting with '!' (excluding '!Block') treated as events; class name after '!'.
        After parsing all tiles, exits are auto-derived: any cardinal/diagonal neighbor present and not blocked becomes an exit.
        Missing classes or instantiation errors fall back to being skipped silently.
        Additionally, if a tile's title matches a class name inside the src/tilesets package, the description
        passed to that class's super().__init__ call will be copied into the imported tile (unless a legacy
        @TileDescription override was provided).
        """
        if filepath is None:
            filepath = filedialog.askopenfilename(defaultextension=".txt", filetypes=[("Text maps", "*.txt"), ("All files", "*.*")])
        if not filepath:
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            grid = [line.rstrip('\n').split('\t') for line in lines]
            new_map = {}
            deltas = {"north":(0,-1),"south":(0,1),"west":(-1,0),"east":(1,0),
                      "northeast":(1,-1),"northwest":(-1,-1),"southeast":(1,1),"southwest":(-1,1)}

            # --- Build tileset class description lookup once ---
            def _collect_tileset_descriptions():
                desc_map = {}
                tilesets_dir = os.path.join(project_root, 'src', 'tilesets')
                if not os.path.isdir(tilesets_dir):
                    return desc_map
                for fname in os.listdir(tilesets_dir):
                    if not fname.endswith('.py') or fname.startswith('__'):
                        continue
                    fpath = os.path.join(tilesets_dir, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8') as tf:
                            src = tf.read()
                        tree = ast.parse(src)
                        for node in tree.body:
                            if isinstance(node, ast.ClassDef):
                                class_name = node.name
                                # find __init__
                                for sub in node.body:
                                    if isinstance(sub, ast.FunctionDef) and sub.name == '__init__':
                                        # search for super().__init__(..., description="""...""") style call
                                        for inner in ast.walk(cast(ast.AST, sub)):
                                            if isinstance(inner, ast.Call):
                                                # match super().__init__ pattern
                                                func = inner.func
                                                if isinstance(func, ast.Attribute) and func.attr == '__init__' and isinstance(func.value, ast.Call) and isinstance(func.value.func, ast.Name) and func.value.func.id == 'super':
                                                    # collect first (or longest) string literal arg
                                                    string_literals = [a.value for a in inner.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                                                    # also check keywords for 'description='
                                                    for kw in inner.keywords or []:
                                                        if (kw.arg == 'description' and isinstance(kw.value, ast.Constant) and kw.value.value is not None):
                                                            string_literals.append(kw.value.value)
                                                    if string_literals:
                                                        # choose the longest (likely the actual description)
                                                        desc_map[class_name] = max(string_literals, key=len).strip()
                                                        break
                                # end for sub
                    except Exception:
                        continue  # ignore parse issues for a single file
                return desc_map
            tileset_descriptions = _collect_tileset_descriptions()

            # dynamic class loader (unchanged)
            module_cache = {}
            def load_class(class_name):
                if not class_name or not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', class_name):
                    return None
                search_modules = [
                    'src.items', 'src.npc', 'src.objects'
                ]
                # add story modules
                story_dir = os.path.join(project_root, 'src', 'story')
                if os.path.isdir(story_dir):
                    for fn in os.listdir(story_dir):
                        if fn.endswith('.py') and not fn.startswith('__'):
                            mod_path = f"src.story.{fn[:-3]}"
                            if mod_path not in search_modules:
                                search_modules.append(mod_path)
                for mod_name in search_modules:
                    try:
                        if mod_name not in module_cache:
                            module_cache[mod_name] = importlib.import_module(mod_name)
                        mod = module_cache[mod_name]
                        if hasattr(mod, class_name):
                            return getattr(mod, class_name)
                    except Exception:
                        continue
                return None
            # parse grid
            for y, row in enumerate(grid):
                for x, cell in enumerate(row):
                    raw = cell.strip()
                    if not raw or raw == 'Boundary':
                        continue
                    parts = [p for p in raw.split('|') if p]
                    if not parts:
                        continue
                    tile_id = f"tile_{x}_{y}"
                    tile_title = None
                    description = ""
                    exits = []
                    blocked = []
                    events = []
                    items = []
                    npcs = []
                    objects_list = []
                    def ensure_instance(cls):
                        try:
                            return cls()  # attempt default constructor
                        except Exception:
                            try:
                                inst = cls.__new__(cls)
                                try:
                                    cls.__init__(inst)  # type: ignore
                                except Exception:
                                    pass
                                return inst
                            except Exception:
                                return None
                    def add_item(class_name, count_spec=None):
                        cls = load_class(class_name)
                        if not cls:
                            return
                        inst = ensure_instance(cls)
                        if not inst:
                            return
                        if count_spec:
                            if count_spec.startswith('r'):
                                m = re.match(r'r(\d+)-(\d+)', count_spec)
                                if m:
                                    inst.count = int(m.group(1))  # use min
                            else:
                                if count_spec.isdigit():
                                    inst.count = int(count_spec)
                        items.append(inst)
                    def add_event(cls_name):
                        cls = load_class(cls_name)
                        if not cls:
                            return
                        inst = ensure_instance(cls)
                        if inst:
                            events.append(inst)
                    def add_entity(cls_name, collection):
                        cls = load_class(cls_name)
                        if not cls:
                            return
                        inst = ensure_instance(cls)
                        if inst:
                            collection.append(inst)
                    for part in parts:
                        if part.startswith('!Block'):
                            dirs = part.split('.')[1:] if '.' in part else []
                            for d in dirs:
                                if d:
                                    blocked.append(d)
                            continue
                        if part.startswith('@TileDescription'):
                            segs = part.split('.')
                            if len(segs) >= 3:
                                text = '.'.join(segs[2:])
                                if text.endswith('~'):
                                    text = text[:-1]
                                description = text.replace('~', '').strip()
                            continue
                        if part.startswith('#'):
                            body = part[1:]
                            name, count_spec = (body.split(':',1)+[None])[:2]
                            add_item(name, count_spec)
                            continue
                        if part.startswith('@'):
                            subparts = part.split('.')
                            head = subparts[0]
                            cls_name = head[1:]
                            cls = load_class(cls_name)
                            inst = ensure_instance(cls) if cls else None
                            if inst:
                                target = objects_list if any(k in cls_name.lower() for k in ['chest','switch','wall','inscription']) else npcs
                                target.append(inst)
                            for sp in subparts[1:]:
                                if sp.startswith('#'):
                                    ibody = sp[1:]
                                    iname, icount = (ibody.split(':',1)+[None])[:2]
                                    add_item(iname, icount)
                                elif sp.startswith('!') and sp != '!Block':
                                    add_event(sp[1:])
                            continue
                        if part.startswith('!') and part != '!Block':
                            add_event(part[1:])
                            continue
                        if tile_title is None:
                            tile_title = part
                    if tile_title is None:
                        tile_title = tile_id
                    # If no explicit legacy description, pull from tilesets class if available
                    if (not description) and tile_title in tileset_descriptions:
                        description = tileset_descriptions[tile_title]
                    new_map[(x,y)] = {
                        'id': tile_id,
                        'title': tile_title,
                        'description': description if description else f"Legacy imported tile {tile_title}",
                        'exits': exits,
                        'block_exit': blocked,
                        'events': events,
                        'items': items,
                        'npcs': npcs,
                        'objects': objects_list
                    }
            # derive exits
            for pos, tile in new_map.items():
                x, y = pos
                exits = []
                blocked = set(tile.get('block_exit', []))
                for d,(dx,dy) in deltas.items():
                    nbr = (x+dx, y+dy)
                    if nbr in new_map and d not in blocked:
                        exits.append(d)
                tile['exits'] = exits
            self.map_data = new_map
            self.current_map_filepath = filepath
            self.selected_tile = None
            self.draw_map()
            self.update_map_label()
            self.set_status(f"Legacy map loaded: {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load legacy map:\n{e}")
            self.set_status("Error loading legacy map.")

    def set_status(self, message):
        """
        Updates the status bar message.
        """
        self.status_label.config(text=message)

    def ensure_add_mode_off(self):
        """Deactivates add tile mode if currently active."""
        if self.is_adding_tile:
            self.toggle_add_tile_mode()

    def on_pan_start(self, event):
        """Start panning or prepare for click."""
        self._drag_data['x'] = event.x
        self._drag_data['y'] = event.y
        self._drag_data['dragged'] = False

    def on_pan_move(self, event):
        """Handle canvas panning on mouse drag."""
        dx = event.x - self._drag_data['x']
        dy = event.y - self._drag_data['y']
        self._drag_data['x'] = event.x
        self._drag_data['y'] = event.y
        self.offset_x += dx
        self.offset_y += dy
        self._drag_data['dragged'] = True
        self.draw_map()

    def on_pan_end(self, event):
        """End panning; if left click without drag, treat as click."""
        if event.num == 1 and not self._drag_data['dragged']:
            self.handle_canvas_click(event)
        self._drag_data['dragged'] = False

    def on_zoom(self, event):
        """Zoom canvas using Ctrl + mouse wheel."""
        # determine zoom factor
        factor = 1.1 if event.delta > 0 else 0.9
        old_size = self.tile_size
        # compute new tile size with limits
        new_size = int(old_size * factor)
        new_size = max(self.min_tile_size, min(self.max_tile_size, new_size))
        factor = new_size / old_size
        self.tile_size = new_size
        # adjust offsets so zoom centers at cursor
        self.offset_x = event.x - (event.x - self.offset_x) * factor
        self.offset_y = event.y - (event.y - self.offset_y) * factor
        self.draw_map()

    def handle_canvas_double_click(self, event):
        """
        Handles double-clicks on the canvas to open the edit dialog for the clicked tile.
        """
        # adjust for pan offsets
        x = int((event.x - self.offset_x) // self.tile_size)
        y = int((event.y - self.offset_y) // self.tile_size)
        pos = (x, y)
        if pos in self.map_data:
            # ensure add mode is off and select tile before editing
            self.ensure_add_mode_off()
            self.select_tile(pos)
            self.edit_selected_tile()

    def handle_enter_key(self, event=None):
        """
        Handles Enter key to open the edit dialog for the currently selected tile.
        """
        if self.selected_tile:
            # ensure add mode is off before editing
            self.ensure_add_mode_off()
            self.edit_selected_tile()
        else:
            self.set_status("No tile selected to edit.")

    def show_tooltip(self, event, text):
        """Show a small tooltip with full text near the cursor."""
        # destroy existing
        if self.tooltip:
            self.tooltip.destroy()
        # create tooltip window
        tw = tk.Toplevel(self.root)
        tw.wm_overrideredirect(True)
        label = tk.Label(tw, text=text, bg="#ffffe0", fg="black", bd=1, relief="solid", font=("Helvetica", 9))
        label.pack()
        # offset tooltip further from cursor to avoid overlap
        x = event.x_root + 30
        y = event.y_root + 30
        tw.wm_geometry(f"+{x}+{y}")
        self.tooltip = tw

    def hide_tooltip(self):
        """Hide the tooltip if shown."""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
    def draw_symbol(self, pos, tile):
        """Draw the tile's symbol at its center."""
        x = pos[0] * self.tile_size + self.tile_size / 2 + self.offset_x
        y = pos[1] * self.tile_size + self.tile_size / 2 + self.offset_y
        sym = tile.get("symbol", "")
        if sym:
            self.canvas.create_text(x, y, text=sym, fill="black", font=("Helvetica", int(self.tile_size*0.4), "bold"))

    def draw_blocked(self, pos, tile):
        """Draw red X's for blocked directions."""
        x1 = pos[0] * self.tile_size + self.offset_x
        y1 = pos[1] * self.tile_size + self.offset_y
        x2 = x1 + self.tile_size
        y2 = y1 + self.tile_size
        # increase size of blocked-X markers
        half = int(self.tile_size * 0.1)
        coords = {
            "north": ((x1+x2)/2, y1+half),
            "south": ((x1+x2)/2, y2-half),
            "west": (x1+half, (y1+y2)/2),
            "east": (x2-half, (y1+y2)/2),
            "northwest": (x1+half, y1+half),
            "northeast": (x2-half, y1+half),
            "southwest": (x1+half, y2-half),
            "southeast": (x2-half, y2-half),
        }
        for d in tile.get("block_exit", []):
            if d in coords:
                cx, cy = coords[d]
                self.canvas.create_line(cx-half, cy-half, cx+half, cy+half, fill="red", width=2)
                self.canvas.create_line(cx+half, cy-half, cx-half, cy+half, fill="red", width=2)

    # --- Delete hotkey guard helpers ---
    def _collect_toplevel_windows(self):
        """Return list of open editor/property dialogs (Toplevels) excluding root and tooltip windows."""
        tops = []
        try:
            for widget in self.root.winfo_children():
                try:
                    if isinstance(widget, tk.Toplevel) and widget is not self.root and widget.winfo_exists():
                        # Skip overrideredirect tooltips
                        try:
                            if widget.wm_overrideredirect():
                                continue
                        except Exception:
                            pass
                        tops.append(widget)
                except Exception:
                    continue
        except Exception:
            pass
        return tops
    def _is_submenu_open(self) -> bool:
        return len(self._collect_toplevel_windows()) > 0
    def _delete_hotkey_handler(self, event=None):
        import time as _t
        if self._is_submenu_open():
            now = _t.time()
            if now - self._last_delete_block_msg > 1.5:
                self.set_status("Delete disabled: close open editor/property dialogs to delete tiles.")
                self._last_delete_block_msg = now
            return
        self.remove_selected_tile()

    # Coordinate helper methods (restored)
    def _update_mouse_coordinates(self, event=None):
        if not getattr(self, 'coord_label', None) or not self.canvas:
            return
        try:
            px = self.root.winfo_pointerx()
            py = self.root.winfo_pointery()
            cx = self.canvas.winfo_rootx()
            cy = self.canvas.winfo_rooty()
            rel_x = px - cx
            rel_y = py - cy
            if rel_x < 0 or rel_y < 0 or rel_x > self.canvas.winfo_width() or rel_y > self.canvas.winfo_height():
                self.coord_label.config(text=f"Tile (-,-)  px({rel_x},{rel_y})")
                return
            tile_x = int((rel_x - self.offset_x) // self.tile_size)
            tile_y = int((rel_y - self.offset_y) // self.tile_size)
            self.coord_label.config(text=f"Tile ({tile_x},{tile_y})  px({rel_x},{rel_y})")
        except Exception:
            pass

    def _poll_mouse_position(self):
        try:
            self._update_mouse_coordinates()
            self.root.after(300, self._poll_mouse_position)
        except Exception:
            pass
    # --- end helpers ---

def _get_editable_properties(obj) -> List[Tuple[str, str]]:
    props: List[Tuple[str, str]] = []
    try:
        cls = obj.__class__
        sig = inspect.signature(cls.__init__)
        params = [p for p in sig.parameters.values() if p.name != 'self']
        excluded = {'player', 'tile'}
        for p in params:
            if p.name in excluded:
                continue
            try:
                val = getattr(obj, p.name)
            except Exception:
                continue
            try:
                rep = repr(val)
            except Exception:
                rep = str(val)
            if len(rep) > 80:
                rep = rep[:77] + '...'
            props.append((p.name, rep))
    except Exception:
        pass
    return props


class TagListFrame(tk.Frame):
    def __init__(self, parent, allow_duplicate=True, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_edit = edit_element
        self.on_remove = remove_element
        self.on_duplicate = duplicate_element if allow_duplicate else None
        self._tags: List[Tuple[Any, tk.Frame]] = []
        self._tooltip: Optional[tk.Toplevel] = None
        self.topLevelWidget = self.winfo_toplevel()

    def _show_tooltip(self, event, obj):
        self._hide_tooltip()
        header = obj.__class__.__name__ if hasattr(obj, '__class__') else 'Object'
        lines = [header]
        props = _get_editable_properties(obj)
        if props:
            lines.extend(f"{n} = {v}" for n,v in props)
        else:
            lines.append('(No editable properties)')
        text = '\n'.join(lines)
        tw = tk.Toplevel(self.winfo_toplevel())
        tw.wm_overrideredirect(True)
        lbl = tk.Label(tw, text=text, justify='left', bg='#ffffe0', fg='black', bd=1, relief='solid', font=("Helvetica", 9))
        lbl.pack(ipadx=4, ipady=2)
        x = event.x_root + 20
        y = event.y_root + 20
        tw.wm_geometry(f"+{x}+{y}")
        self._tooltip = tw

    def _hide_tooltip(self):
        if self._tooltip is not None:
            try:
                self._tooltip.destroy()
            except Exception:
                pass
            self._tooltip = None

    def _bind_tooltip(self, widget, obj):
        widget.bind('<Enter>', lambda e, o=obj: self._show_tooltip(e, o))
        widget.bind('<Leave>', lambda e: self._hide_tooltip())

    def add_tag(self, identifier, lst: List, text: str):
        tag_frame = tk.Frame(self, bd=1, relief='solid', padx=4, pady=2)
        is_class_object = isinstance(identifier, type)
        # Set background color for class-type tags
        if is_class_object:
            tag_frame.config(bg='#3498db')  # blue background for class-type tags
        tag_label = tk.Label(tag_frame, text=text)
        # Also set label background for class-type tags
        if is_class_object:
            tag_label.config(bg='#3498db', fg='white')
        tag_label.pack(side='left')
        del_btn = tk.Button(tag_frame, text='×', command=lambda: self.remove(identifier, lst), bd=0, padx=2, pady=0)
        del_btn.pack(side='right')
        is_class_object = isinstance(identifier, type)
        if self.on_duplicate and not is_class_object:
            dup_btn = tk.Button(tag_frame, text='⧉', command=lambda: self.on_duplicate(identifier, lst, frame=self), bd=0, padx=2, pady=0)
            dup_btn.pack(side='right')
        tag_frame.pack(side='left', padx=2, pady=2)
        if not is_class_object:
            tag_frame.bind('<Double-Button-1>', lambda e: self.on_edit(self.topLevelWidget, identifier, lst, self))
            tag_label.bind('<Double-Button-1>', lambda e: self.on_edit(self.topLevelWidget, identifier, lst, self))
            self._bind_tooltip(tag_frame, identifier)
            self._bind_tooltip(tag_label, identifier)
        else:
            # Tooltip for class objects
            def _show_cls_tooltip(event, cls_obj=identifier):
                self._hide_tooltip()
                text = f"Class: {cls_obj.__name__}\nModule: {cls_obj.__module__}"
                tw = tk.Toplevel(self.winfo_toplevel())
                tw.wm_overrideredirect(True)
                lbl = tk.Label(tw, text=text, justify='left', bg='#ffffe0', fg='black', bd=1, relief='solid', font=("Helvetica", 9))
                lbl.pack(ipadx=4, ipady=2)
                x = event.x_root + 20
                y = event.y_root + 20
                tw.wm_geometry(f"+{x}+{y}")
                self._tooltip = tw
            for w in (tag_frame, tag_label):
                w.bind('<Enter>', _show_cls_tooltip)
                w.bind('<Leave>', lambda e: self._hide_tooltip())
        self._tags.append((identifier, tag_frame))

    def remove(self, identifier, lst: List):
        self.on_remove(identifier, lst, self)
        for i, (ident, frm) in enumerate(list(self._tags)):
            if ident is identifier:
                try:
                    frm.destroy()
                except Exception:
                    pass
                self._tags.pop(i)
                break
        self._hide_tooltip()

    def clear(self):
        for _, frm in self._tags:
            try:
                frm.destroy()
            except Exception:
                pass
        self._tags.clear()

    def get_all(self) -> List[Any]:
        return [ident for ident, _ in self._tags]


def _get_module_paths_for_class(class_name: str) -> List[str]:
    """
    Returns a list of absolute file paths for all modules in src/ that define the given class or its subclasses.
    """
    this_project_root = os.path.dirname(os.path.dirname(__file__))
    src_dir = os.path.join(this_project_root, 'src')
    result_paths = set()
    # Walk through src/ and subdirectories
    for dirpath, dirnames, filenames in os.walk(src_dir):
        for filename in filenames:
            if filename.endswith('.py') and not filename.startswith('__'):
                file_path = os.path.join(dirpath, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        src = f.read()
                    tree = ast.parse(src)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            # Check if class matches or subclasses the target
                            if node.name == class_name:
                                result_paths.add(file_path)
                            else:
                                # Check bases for subclassing
                                for base in node.bases:
                                    if isinstance(base, ast.Name) and base.id == class_name:
                                        result_paths.add(file_path)
                                    elif isinstance(base, ast.Attribute) and base.attr == class_name:
                                        result_paths.add(file_path)
                except Exception:
                    continue  # Ignore parse errors
    return list(result_paths)

def get_import_path(module_path, this_project_root):
    rel = os.path.relpath(module_path, this_project_root)
    import_mod = rel.replace(os.sep, '.')
    if import_mod.lower().endswith('.py'):
        import_mod = import_mod[:-3]
    if import_mod.startswith('src.'):
        import_mod = import_mod[4:]
    return import_mod

def parse_module_classes(module_path, this_project_root):
    class_info = {}
    if not os.path.isfile(module_path):
        return class_info
    try:
        with open(module_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except Exception as e:
        messagebox.showerror("Error", f"Could not load module {module_path}:\n{e}")
        return None
    import_mod = get_import_path(module_path, this_project_root)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(b.attr)
            info = class_info.setdefault(node.name, {'bases': [], 'children': set(), 'module': import_mod})
            info['bases'] = bases
    return class_info

def build_class_hierarchy(class_info):
    for name, info in class_info.items():
        for base in info['bases']:
            if base in info['children']:
                info['children'].remove(base)
            if base in class_info:
                class_info[base]['children'].add(name)
    return class_info

def filter_classes(class_info, filter_by_class):
    # Filter classes to include the target class and all its subclasses
    allowed_classes = set(class_info.keys())
    if filter_by_class:
        def is_subclass_or_same(cname):
            if cname == filter_by_class:
                return True
            visited = set()
            def check_sub(c):
                if c in visited:
                    return False
                visited.add(c)
                bases = class_info.get(c, {}).get('bases', [])
                for b in bases:
                    if b == filter_by_class:
                        return True
                    if b in class_info and check_sub(b):
                        return True
                return False
            return check_sub(cname)
        allowed_classes = {c for c in class_info if is_subclass_or_same(c)}
    return allowed_classes

class TileEditorWindow:
    """
    A separate window for editing a single tile's properties.
    """

    def __init__(self, parent, map_data, position, on_save_callback):
        """
        Initializes the tile editor window.
        Now receives full map_data and current tile position to filter valid directions.
        """
        self.map_data = map_data
        self.pos = position
        self.tile_data: dict = map_data[position]
        self.on_save_callback = on_save_callback

        # Pre-compute adjacency directions
        self._deltas = {"north":(0,-1),"south":(0,1),"east":(1,0),"west":(-1,0),
                        "northeast":(1,-1),"northwest":(-1,-1),"southeast":(1,1),"southwest":(-1,1)}
        self.valid_directions = [d for d,(dx,dy) in self._deltas.items() if (self.pos[0]+dx, self.pos[1]+dy) in self.map_data]
        # Purge stale exits / block_exit references with missing neighbors
        self.tile_data["exits"] = [d for d in self.tile_data.get("exits", []) if d in self.valid_directions]
        self.tile_data["block_exit"] = [d for d in self.tile_data.get("block_exit", []) if d in self.valid_directions]

        # Track initial state so we only overwrite exits if the user interacts with the listboxes.
        self._initial_exits = list(self.tile_data.get("exits", []))
        self._initial_blocked = list(self.tile_data.get("block_exit", []))
        self._exits_modified = False
        self._blocked_modified = False

        self.window = tk.Toplevel(parent)
        self.window.title(f"Editing Tile: {self.tile_data['id']}")
        self.window.geometry("450x550")
        self.window.configure(bg="#34495e")
        self.window.grab_set()  # Make window modal

        # Pre-declare widget attributes
        self.title_entry = None
        self.description_text = None
        self.exits_listbox = None
        self.symbol_entry = None

        # --- UI Elements ---
        self.create_widgets()

    def create_widgets(self):
        """
        Creates all the GUI widgets for the tile editor, now with a tabbed interface.
        """
        # Main container
        main_frame = tk.Frame(self.window, bg="#34495e", padx=10, pady=10)
        main_frame.pack(fill="both", expand=True)

        # Notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True, pady=(10, 0))

        # --- Properties Tab ---
        props_frame = tk.Frame(notebook, bg="#34495e", padx=10, pady=10)
        notebook.add(props_frame, text="Properties")

        # Title
        tk.Label(props_frame, text="Title:", bg="#34495e", fg="white").pack(anchor="w", pady=(0, 5))
        self.title_entry = tk.Entry(props_frame, width=40, font=("Helvetica", 10))
        self.title_entry.insert(0, self.tile_data.get("title", ""))
        self.title_entry.pack(fill="x", pady=(0, 10))

        # Description
        tk.Label(props_frame, text="Description:", bg="#34495e", fg="white").pack(anchor="w", pady=(0, 5))
        self.description_text = tk.Text(props_frame, height=4, width=40, font=("Helvetica", 10))
        self.description_text.insert(tk.END, self.tile_data.get("description", ""))
        self.description_text.pack(fill="both", expand=True, pady=(0, 10))

        # Symbol
        tk.Label(props_frame, text="Symbol:", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        self.symbol_entry = tk.Entry(props_frame, width=10, font=("Helvetica", 12))
        self.symbol_entry.insert(0, self.tile_data.get("symbol", ""))
        self.symbol_entry.pack(anchor="w", pady=(0, 10))

        # --- Exits Tab ---
        exits_frame = tk.Frame(notebook, bg="#34495e", padx=10, pady=10)
        notebook.add(exits_frame, text="Exits")

        # Exits
        tk.Label(exits_frame, text="Exits:", bg="#34495e", fg="white").pack(anchor="w", pady=(0, 5))
        frame_exits = tk.Frame(exits_frame)
        frame_exits.pack(fill="x", pady=(0,10))
        self.exits_listbox = tk.Listbox(frame_exits, selectmode="multiple", height=8, exportselection=False)
        exits_sb = tk.Scrollbar(frame_exits, orient="vertical", command=self.exits_listbox.yview)
        exits_sb.pack(side="right", fill="y")
        self.exits_listbox.configure(yscrollcommand=exits_sb.set)
        for d in self.valid_directions:
            self.exits_listbox.insert("end", d)
            if d in self.tile_data.get("exits", []):
                # select existing exits
                self.exits_listbox.select_set("end")
        self.exits_listbox.pack(side="left", fill="x", expand=True)
        # Mark exits as modified only if user changes selection
        self.exits_listbox.bind('<<ListboxSelect>>', lambda e: setattr(self, '_exits_modified', True))

        # Directions blocked
        tk.Label(exits_frame, text="Directions Blocked:", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        frame_dir = tk.Frame(exits_frame)
        frame_dir.pack(fill="x")
        self.directions_listbox = tk.Listbox(frame_dir, selectmode="multiple", height=8, exportselection=False)
        dir_sb = tk.Scrollbar(frame_dir, orient="vertical", command=self.directions_listbox.yview)
        dir_sb.pack(side="right", fill="y")
        self.directions_listbox.configure(yscrollcommand=dir_sb.set)
        self.directions_listbox.pack(side="left", fill="x", expand=True)
        for d in self.valid_directions:
            self.directions_listbox.insert("end", d)
            if d in self.tile_data.get("block_exit", []):
                self.directions_listbox.select_set("end")
        self.directions_listbox.bind('<<ListboxSelect>>', lambda e: setattr(self, '_blocked_modified', True))
        tk.Label(exits_frame, text="Only directions with adjacent tiles are shown.", font=("Helvetica", 8, "italic"), bg="#34495e", fg="#bdc3c7").pack(anchor="w", pady=(5,0))

        # --- Items/NPCs/Objects/Events Tabs ---
        tab_configs = [
            ("Item", "Add Item", "items_frame", "items"),
            ("NPC", "Add NPC", "npcs_frame", "npcs"),
            ("Object", "Add Object", "objects_frame", "objects"),
            ("Event", "Add Event", "events_frame", "events"),
        ]

        for obj_class_name, btn_text, frame_attr, element_list_name in tab_configs:
            tab_frame = tk.Frame(notebook, bg="#34495e", padx=10, pady=10)
            notebook.add(tab_frame, text=f'{obj_class_name}s')
            create_element_frame(self.window, tab_frame, frame_attr)
            btn_cmd = (lambda en=element_list_name, fa=frame_attr, this_baseclass_name=obj_class_name:
                open_chooser(self.window, self.tile_data[en], getattr(self.window, fa),
                             this_baseclass_name, (this_baseclass_name=="Event")))
            tk.Button(tab_frame, text=btn_text, command=btn_cmd,
                      font=("Helvetica", 10, "bold"), bg="#3498db", fg="white").pack(fill="x", pady=(0, 10))

        # Save Button (outside notebook)
        save_button = tk.Button(main_frame, text="Save Changes", command=self.save_and_close,
                                font=("Helvetica", 12, "bold"), bg="#2ecc71", fg="white")
        save_button.pack(fill="x", pady=(10, 0))

        self.refresh_all_tags()

    def save_and_close(self):
        """Saves the edited properties back to the tile data and closes the window."""
        try:
            self.tile_data["title"] = self.title_entry.get().strip()
            self.tile_data["description"] = self.description_text.get("1.0", tk.END).strip()
            # Only overwrite exits if user actually modified listbox selection or there are selected entries.
            sel = self.exits_listbox.curselection() if self.exits_listbox else ()
            if sel or self._exits_modified:
                new_exits = [self.exits_listbox.get(i) for i in sel]
            else:
                new_exits = list(self._initial_exits)
            # Same logic for blocked exits
            if self.directions_listbox:
                selected_blocked = self.directions_listbox.curselection()
                if selected_blocked or self._blocked_modified:
                    new_blocked = [self.directions_listbox.get(i) for i in selected_blocked]
                else:
                    new_blocked = list(self._initial_blocked)
            else:
                new_blocked = list(self._initial_blocked)
            # Enforce validity again (safety if map changed during edit)
            self.tile_data["exits"] = [d for d in new_exits if d in self.valid_directions]
            self.tile_data["block_exit"] = [d for d in new_blocked if d in self.valid_directions]
            self.tile_data["symbol"] = self.symbol_entry.get().strip()
            self.on_save_callback()
            self.window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input format. Please check your entries.\nDetails: {e}")


    def refresh_all_tags(self):
        # Frames are attached to self.window (the Toplevel) via create_element_frame,
        # so we must retrieve them from self.window rather than self. Previously this
        # method looked up attributes on self, resulting in None frames and no initial
        # tag population (frames appeared empty / not shown).
        wnd = getattr(self, 'window', None)
        if not wnd:
            return
        for key, frame in [
            ("events", getattr(wnd, "events_frame", None)),
            ("items", getattr(wnd, "items_frame", None)),
            ("npcs", getattr(wnd, "npcs_frame", None)),
            ("objects", getattr(wnd, "objects_frame", None)),
        ]:
            if frame is not None:
                refresh_tags(self.tile_data.get(key, []), frame)

"""
===== Static Methods to manage TagListFrames, which can be children of TileEditorWindow OR a container tk.Frame =====
"""


def create_element_frame(dialog_object: tk.Toplevel, parent: tk.Frame, attr_string: str):
    """
    Creates a TagListFrame, packs it into the parent, sets it as an attribute on the dialog_object, and returns it.

    Args:
        dialog_object: The TileEditorWindow or tk.Toplevel instance to attach the frame to.
        parent: The parent tk.Frame to pack the new TagListFrame into.
        attr_string: The attribute name to set on the dialog_object.

    Returns:
        The created TagListFrame instance.
    """
    frame = TagListFrame(parent)
    frame.pack(fill="both", expand=True)
    setattr(dialog_object, attr_string, frame)
    return frame

def _is_event_like(obj):
    """
    Return True if `obj` is an Event instance/class even if the Event base
    resolves from a different import path (e.g. src.events.Event).
    """
    try:
        cls = obj if isinstance(obj, type) else obj.__class__
    except Exception:
        return False

    # Prefer exact identity if available
    for base in inspect.getmro(cls):
        if base is Event:
            return True

    # Accept any base class named 'Event' coming from a module whose final
    # component is 'events' (covers both 'events' and 'src.events').
    for base in inspect.getmro(cls):
        try:
            if base.__name__ == 'Event' and base.__module__.split('.')[-1] == 'events':
                return True
        except Exception:
            continue

    # Fallback: accept any base simply named 'Event'
    for base in inspect.getmro(cls):
        if base.__name__ == 'Event':
            return True

    return False

def add_element(inst, lst: List, frame: TagListFrame):
    """
    Adds an instance `inst` to the list `lst` for the given frame of `obj`.
    If the instance has a `count` attribute and an existing item of the same class is present,
    their counts are stacked. Updates the associated tag frame if present.
    Shows an error message if the instance is invalid.
    """
    if inst is None or not hasattr(inst, '__class__'):
        messagebox.showerror("Error", "Invalid object instance.")
        return
    # stacking logic: if item has a count attribute, stack with existing same-class item
    # Ignores Event instances for stacking since events should never stack
    inst_is_event_subclass = _is_event_like(inst)
    if hasattr(inst, 'count') and not inst_is_event_subclass:
        for existing in lst:
            if isinstance(existing, inst.__class__):
                try:
                    existing.count = getattr(existing, 'count', 1) + getattr(inst, 'count', 1)
                except Exception:
                    pass
                if frame:
                    refresh_tags(lst, frame)
                return
        lst.append(inst)
    else:
        lst.append(inst)
    if frame:
        refresh_tags(lst, frame)


def duplicate_element(inst, lst: List, frame: TagListFrame):
    """
    Creates a duplicate of the given instance and adds it to the specified list.
    Uses deep copy if possible, otherwise falls back to a shallow copy.
    Calls add_element to handle stacking and UI refresh.
    """
    try:
        new_inst = copy.deepcopy(inst)
    except Exception:
        # fallback shallow
        new_inst = inst.__class__.__new__(inst.__class__)
        new_inst.__dict__.update({k: v for k, v in inst.__dict__.items()})
    add_element(new_inst, lst, frame)


def edit_element(dialog_object: tk.Toplevel, inst, lst: List, frame: TagListFrame):
    """
    Opens a property dialog to edit the given element instance.
    Updates or removes the element in the tag list frame based on user action.
    Args:
        dialog_object: The TileEditorWindow or property dialog (tk.Toplevel) instance
        inst: The instance to edit.
        lst: The list containing the instance.
        frame: The TagListFrame containing the element.
    """
    def callback(updated_inst, this_lst, this_frame):
        if updated_inst is None:  # Delete
            remove_element(updated_inst, this_lst, this_frame)
        else:
            refresh_tags(this_lst, frame)
    open_property_dialog(dialog_object, inst.__class__, existing=inst,
                         callback=lambda updated_inst: callback(updated_inst, lst, frame))

def remove_element(inst, lst: List, frame: TagListFrame):
    """
    Removes the given instance from the specified list and updates the tag frame.
    Args:
        inst: The instance to remove.
        lst: The list containing the instance.
        frame: The TagListFrame to refresh.
    """
    if inst in lst:
        lst.remove(inst)
        refresh_tags(lst, frame)


def refresh_tags(lst: List, frame: TagListFrame):
    """Populate TagListFrame with entries from lst.
    Supports instances and class (type) objects. Class objects show their __name__."""
    frame.clear()
    for inst in lst:
        if isinstance(inst, type):
            name = inst.__name__
        else:
            name = inst.__class__.__name__ if hasattr(inst, '__class__') else str(inst)
        frame.add_tag(inst, lst, name)


def open_chooser(dialog_object: tk.Toplevel, lst: List, tag_frame: TagListFrame,
                 base_class_name: str = None, is_event: bool = False):
    paths = []
    if is_event:
        story_dir = os.path.join(project_root, 'src', 'story')
        if os.path.isdir(story_dir):
            paths = [
                os.path.join(story_dir, fname)
                for fname in os.listdir(story_dir)
                if fname.endswith('.py') and not fname.startswith('__')
            ]
        if not paths:
            messagebox.showerror("Error", "No event files found in src/story.")
            return
        show_hierarchy_chooser(dialog_object, paths, "Choose Event", add_element, lst, tag_frame)
    else:
        # FIX: Previously only modules containing the base class definition were scanned, not those
        # defining subclasses. Use helper that gathers any module that defines the base OR a subclass.
        if not base_class_name:
            messagebox.showerror("Error", "Base class name not provided.")
            return
        try:
            paths = _get_module_paths_for_class(base_class_name)
        except Exception:
            paths = []
        if not paths:
            messagebox.showerror("Error", f"Could not find base class {base_class_name} or its subclasses in src/.")
            return
        show_hierarchy_chooser(dialog_object, paths, f"Choose {base_class_name}",
                               add_element, lst, tag_frame, base_class_name)


def show_hierarchy_chooser(dialog_object: tk.Toplevel, module_paths, dialog_title,
                           add_callback, lst: List, tag_frame: TagListFrame, filter_by_class: str=None):
    """Display hierarchical class chooser for one or more module paths.
    module_paths: list[str] absolute file system paths.
    """
    # Parse modules and build unified class hierarchy across them
    class_info = {}  # name -> { 'bases': [...], 'children': set(), 'module': import_path }
    # Determine project root (assumes all paths share same root two levels up from utils)
    for module_path in module_paths:
        if not os.path.isfile(module_path):
            continue
        try:
            class_info_module = parse_module_classes(module_path, project_root)
            if class_info_module:  # ensure not None/empty
                class_info.update(class_info_module)
        except Exception:
            continue
    # build children relations
    class_info = build_class_hierarchy(class_info)
    # --- Filtering by class name ---
    allowed_classes = filter_classes(class_info, filter_by_class)
    # roots: classes whose bases are not in class_info and are allowed
    roots = sorted([n for n, info in class_info.items() if not any(b in class_info for b in info['bases']) and n in allowed_classes])
    # Build dialog
    dlg = tk.Toplevel(dialog_object)
    dlg.title(dialog_title)
    dlg.geometry('320x450')
    dlg.transient(dialog_object)
    dlg.grab_set()
    # Filter entry
    filter_frame = tk.Frame(dlg)
    filter_frame.pack(fill='x', padx=5, pady=5)
    tk.Label(filter_frame, text='Filter:', anchor='w').pack(side='left')
    filter_var = tk.StringVar()
    tk.Entry(filter_frame, textvariable=filter_var).pack(side='left', fill='x', expand=True)
    # Listbox
    frame = tk.Frame(dlg)
    frame.pack(fill='both', expand=True)
    lb = tk.Listbox(frame)
    sb = tk.Scrollbar(frame, orient='vertical', command=lb.yview)
    lb.configure(yscrollcommand=sb.set)
    sb.pack(side='right', fill='y')
    lb.pack(side='left', fill='both', expand=True)
    # Maintain metadata externally to avoid adding typed attribute to tk.Listbox (silences warning)
    items_meta: List[Dict[str, str]] = []
    # helper to decide if subtree matches filter
    def update_list(*args):
        search = filter_var.get().lower().strip()
        lb.delete(0, tk.END)
        items_meta.clear()
        visited = set()
        def recurse(names, indent=0):
            for n in sorted(names):
                if n in visited or n not in allowed_classes:
                    continue
                visited.add(n)
                info = class_info[n]
                # determine if this node or any descendant matches filter
                def subtree_matches(cname):
                    if cname not in allowed_classes:
                        return False
                    if not search:
                        return True
                    if search in cname.lower():
                        return True
                    for child in class_info[cname]['children']:
                        if subtree_matches(child):
                            return True
                    return False
                if subtree_matches(n):
                    lb.insert('end', '  ' * indent + n)
                    items_meta.append({'name': n, 'module': info['module']})
                    if class_info[n]['children']:
                        recurse(class_info[n]['children'], indent + 1)
        recurse(roots)
    filter_var.trace_add('write', update_list)
    update_list()
    # double-click to instantiate and edit
    def on_double(e):
        if not lb.curselection():
            return
        idx = lb.curselection()[0]
        meta = cast(Dict[str,str], items_meta[idx])
        cls_name = meta.get('name', '')
        import_module = meta.get('module', '')
        try:
            module = importlib.import_module(import_module)
            cls = getattr(module, cls_name)
            open_property_dialog(dialog_object, cls, existing=None,
                                 callback=lambda inst: add_callback(inst, lst, tag_frame))
        except Exception as ex:
            messagebox.showerror("Error", f"Could not create instance: {ex}")
        dlg.destroy()
    lb.bind('<Double-Button-1>', on_double)


def open_class_type_chooser(dialog_object: tk.Toplevel, base_class_name: str, lst: List[type], tag_frame: TagListFrame):
    if not base_class_name:
        messagebox.showerror("Error", "Base class name not provided.")
        return
    try:
        module_paths = _get_module_paths_for_class(base_class_name)
    except Exception:
        module_paths = []
    if not module_paths:
        messagebox.showerror("Error", f"Could not find base class {base_class_name} or its subclasses in src/.")
        return
    show_class_type_hierarchy_chooser(dialog_object, module_paths, f"Choose {base_class_name} Type", lst, tag_frame, base_class_name)

# NEW: single-selection variant for Type[Base] (non-list) annotations
# Reuses the same hierarchy building logic but ensures only one class can be selected.
def open_single_class_type_chooser(dialog_object: tk.Toplevel, base_class_name: str, lst: List[type], tag_frame: TagListFrame):
    if not base_class_name:
        messagebox.showerror("Error", "Base class name not provided.")
        return
    try:
        module_paths = _get_module_paths_for_class(base_class_name)
    except Exception:
        module_paths = []
    if not module_paths:
        messagebox.showerror("Error", f"Could not find base class {base_class_name} or its subclasses in src/.")
        return
    # We inline a lightweight variant of show_class_type_hierarchy_chooser to inject single-select behavior.
    class_info = {}
    for module_path in module_paths:
        if not os.path.isfile(module_path):
            continue
        try:
            ci = parse_module_classes(module_path, project_root)
            if ci:
                class_info.update(ci)
        except Exception:
            continue
    class_info = build_class_hierarchy(class_info)
    allowed = filter_classes(class_info, base_class_name)
    roots = sorted([n for n, i in class_info.items() if not any(b in class_info for b in i['bases']) and n in allowed])
    dlg = tk.Toplevel(dialog_object)
    dlg.title(f"Choose {base_class_name} Type")
    dlg.geometry('300x430')
    dlg.transient(dialog_object)
    dlg.grab_set()
    filter_frame = tk.Frame(dlg)
    filter_frame.pack(fill='x', padx=5, pady=5)
    tk.Label(filter_frame, text='Filter:', anchor='w').pack(side='left')
    filter_var = tk.StringVar()
    tk.Entry(filter_frame, textvariable=filter_var).pack(side='left', fill='x', expand=True)
    frame_lb = tk.Frame(dlg)
    frame_lb.pack(fill='both', expand=True)
    lb = tk.Listbox(frame_lb)
    sb = tk.Scrollbar(frame_lb, orient='vertical', command=lb.yview)
    lb.configure(yscrollcommand=sb.set)
    sb.pack(side='right', fill='y')
    lb.pack(side='left', fill='both', expand=True)
    metas: List[Dict[str, str]] = []
    def update_list(*_):
        search = filter_var.get().lower().strip()
        lb.delete(0, tk.END)
        metas.clear()
        visited = set()
        def subtree_matches(cname):
            if cname not in allowed:
                return False
            if not search or search in cname.lower():
                return True
            return any(subtree_matches(ch) for ch in class_info[cname]['children'])
        def recurse(names, indent=0):
            for n in sorted(names):
                if n in visited or n not in allowed:
                    continue
                visited.add(n)
                if subtree_matches(n):
                    lb.insert('end', '  '*indent + n)
                    metas.append({'name': n, 'module': class_info[n]['module']})
                    if class_info[n]['children']:
                        recurse(class_info[n]['children'], indent+1)
        recurse(roots)
    filter_var.trace_add('write', update_list)
    update_list()
    def on_double(_):
        if not lb.curselection():
            return
        idx = lb.curselection()[0]
        meta = metas[idx]
        cls_name = meta['name']
        module_name = meta['module']
        try:
            mod = importlib.import_module(module_name)
            cls_obj = getattr(mod, cls_name)
            # Single-selection enforcement
            lst.clear()
            lst.append(cls_obj)
            refresh_tags(lst, tag_frame)
        except Exception as ex:
            messagebox.showerror("Error", f"Could not load class: {ex}")
        dlg.destroy()
    lb.bind('<Double-Button-1>', on_double)


def show_class_type_hierarchy_chooser(dialog_object: tk.Toplevel, module_paths, dialog_title, lst: List[type], tag_frame: TagListFrame, filter_by_class: str=None):
    class_info = {}
    for module_path in module_paths:
        if not os.path.isfile(module_path):
            continue
        try:
            ci = parse_module_classes(module_path, project_root)
            if ci:
                class_info.update(ci)
        except Exception:
            continue
    class_info = build_class_hierarchy(class_info)
    allowed = filter_classes(class_info, filter_by_class)
    roots = sorted([n for n, i in class_info.items() if not any(b in class_info for b in i['bases']) and n in allowed])
    dlg = tk.Toplevel(dialog_object)
    dlg.title(dialog_title)
    dlg.geometry('300x430')
    dlg.transient(dialog_object)
    dlg.grab_set()
    filter_frame = tk.Frame(dlg)
    filter_frame.pack(fill='x', padx=5, pady=5)
    tk.Label(filter_frame, text='Filter:', anchor='w').pack(side='left')
    filter_var = tk.StringVar()
    tk.Entry(filter_frame, textvariable=filter_var).pack(side='left', fill='x', expand=True)
    frame_lb = tk.Frame(dlg)
    frame_lb.pack(fill='both', expand=True)
    lb = tk.Listbox(frame_lb)
    sb = tk.Scrollbar(frame_lb, orient='vertical', command=lb.yview)
    lb.configure(yscrollcommand=sb.set)
    sb.pack(side='right', fill='y')
    lb.pack(side='left', fill='both', expand=True)
    metas: List[Dict[str, str]] = []
    def update_list(*_):
        search = filter_var.get().lower().strip()
        lb.delete(0, tk.END)
        metas.clear()
        visited = set()
        def subtree_matches(cname):
            if cname not in allowed:
                return False
            if not search or search in cname.lower():
                return True
            return any(subtree_matches(ch) for ch in class_info[cname]['children'])
        def recurse(names, indent=0):
            for n in sorted(names):
                if n in visited or n not in allowed:
                    continue
                visited.add(n)
                if subtree_matches(n):
                    lb.insert('end', '  '*indent + n)
                    metas.append({'name': n, 'module': class_info[n]['module']})
                    if class_info[n]['children']:
                        recurse(class_info[n]['children'], indent+1)
        recurse(roots)
    filter_var.trace_add('write', update_list)
    update_list()
    def on_double(_):
        if not lb.curselection():
            return
        idx = lb.curselection()[0]
        meta = metas[idx]
        cls_name = meta['name']
        module_name = meta['module']
        try:
            mod = importlib.import_module(module_name)
            cls_obj = getattr(mod, cls_name)
            if cls_obj not in lst:
                lst.append(cls_obj)
                refresh_tags(lst, tag_frame)
        except Exception as ex:
            messagebox.showerror("Error", f"Could not load class: {ex}")
        dlg.destroy()
    lb.bind('<Double-Button-1>', on_double)


def open_property_dialog(parent_dialog_object: tk.Toplevel, cls, existing=None, callback=None):
    dlg = tk.Toplevel(parent_dialog_object)
    dlg.title(f"Properties for {cls.__name__}")
    dlg.geometry('900x550')
    dlg.transient(parent_dialog_object)
    dlg.grab_set()

    entries = {}  # name -> {'type': 'text'|'bool'|'hierarchical', 'get': callable}
    editable_params, excluded_params = get_editable_params(cls)
    # Resolve annotations (handles PEP 563 postponed evaluation so get_origin works)
    try:
        resolved_hints = get_type_hints(cls.__init__)
    except Exception:
        resolved_hints = {}

    # Moved and optimized merchant collection
    def get_all_merchants(map_data):
        """
        Collects all merchant NPC instances from every tile in the map.
        Returns:
            dict: A mapping of merchant names (disambiguated if duplicates) to their instances.
        """
        all_npcs = []
        for tdata in map_data.values():
            all_npcs.extend(tdata.get('npcs', []))
        merchants = [npc for npc in all_npcs if isinstance(npc, Merchant)]
        merchant_map = {}
        for m in merchants:
            merchant_name = getattr(m, 'name', str(m))
            merchant_map[merchant_name] = m
        return merchant_map

    all_merchants = None
    if "merchant" in [p.name for p in editable_params]:
        try:
            # Attempt to use global app instance if present
            app_map_data = app.map_data  # type: ignore[name-defined]
        except Exception:
            app_map_data = {}
        try:
            all_merchants = get_all_merchants(app_map_data) if app_map_data else {}
        except Exception:
            all_merchants = {}

    # Auto-save function that will be called on every change
    def auto_save():
        if not existing:
            return  # Only auto-save for existing objects, not when creating new ones

        kwargs = {}
        for field_name, meta in entries.items():
            if meta['type'] == 'bool':
                kwargs[field_name] = meta['get']()
            elif meta['type'] == 'hierarchical':
                kwargs[field_name] = meta['get']()
            else:
                raw = meta['get']()
                if raw == '':
                    continue
                try:
                    import ast as _ast
                    # Special handling for merchant combobox
                    if meta.get('is_merchant'):
                        # The value is the merchant's name, map it back to the instance
                        kwargs[field_name] = all_merchants.get(raw)
                        # For hierarchical fields, especially class type lists, ensure we update the object's attribute
                        # If editing an existing object, assign the list directly to the attribute
                        if existing is not None:
                            setattr(existing, field_name, raw)
                        kwargs[field_name] = raw
                    else:
                        kwargs[field_name] = _ast.literal_eval(raw)
                except Exception:
                    kwargs[field_name] = raw

        # Apply changes to existing object
        for k, v in kwargs.items():
            setattr(existing, k, v)
        # Special handling: if an object defines an 'inventory' attribute and we edited an 'items' param,
        # keep them in sync so game logic (which reads inventory) reflects editor changes.
        if 'items' in kwargs and hasattr(existing, 'inventory'):
            try:
                existing.inventory = list(kwargs['items']) if kwargs['items'] else []
            except Exception:
                pass

        # Trigger callback to refresh UI if provided
        if callback:
            callback(existing)

    frm = tk.Frame(dlg, bg="#34495e", padx=14, pady=14)
    frm.pack(fill='both', expand=True)
    if editable_params:
        col_count = 2 if len(editable_params) > 6 else 1
        # Track map name StringVars so coordinate fields can refresh when map changes
        map_name_vars: List[tk.StringVar] = []
        coord_refreshers: List[callable] = []

        def _add_map_var(var: tk.StringVar):
            map_name_vars.append(var)

        def _get_selected_map_name() -> Optional[str]:
            # priority order: teleport_map then target_map_name (first non-empty)
            # Iterate in defined param order for deterministic selection
            for param_name in ('teleport_map', 'target_map_name'):
                for var in map_name_vars:
                    if getattr(var, '_hov_param', None) == param_name:
                        val = var.get().strip()
                        if val:
                            return val
            # Fallback: any non-empty var
            for var in map_name_vars:
                val = var.get().strip()
                if val:
                    return val
            return None

        def _attach_traces():
            for var in map_name_vars:
                # ensure multiple traces not duplicated
                def _make_cb():
                    def _cb(*_):
                        for r in coord_refreshers:
                            try:
                                r()
                            except Exception:
                                pass
                    return _cb
                var.trace_add('write', _make_cb())

        for idx, p in enumerate(editable_params):
            row = idx if col_count == 1 else idx // col_count
            col = 0 if col_count == 1 else idx % col_count
            container = tk.Frame(frm, bg="#34495e")
            container.grid(row=row*2, column=col, sticky='ew', padx=6, pady=(0,6))
            tk.Label(container, text=f"{p.name}:", bg="#34495e", fg="white", anchor='w').pack(anchor='w')

            # derive default/existing value
            if existing is not None:
                val = getattr(existing, p.name, p.default if p.default is not inspect._empty else getattr(cls, p.name, ''))
            else:
                if p.name == 'repeat':
                    # Force initial repeat to False as per requirement
                    val = False
                elif p.default is not inspect._empty:
                    val = p.default
                else:
                    val = getattr(cls, p.name, '')

            # --- Class TYPE list detection: list[type[Base]] ---
            try:
                # Use resolved annotation if available
                ann_for_detection = resolved_hints.get(p.name, p.annotation)
                ann_origin = get_origin(ann_for_detection)
                ann_args = get_args(ann_for_detection)
                # helper creators to avoid mutable default argument warnings
                def _make_list_getter(ref_list: List[type]):
                    return lambda: ref_list
                def _make_single_getter(ref_list: List[type]):
                    return lambda: (ref_list[0] if ref_list else None)
                def _make_multi_btn_handler(base_name: str, ref_list: List[type], frame_ref: TagListFrame):
                    return lambda: open_class_type_chooser(dlg, base_name, ref_list, frame_ref)
                def _make_single_btn_handler(base_name: str, ref_list: List[type], frame_ref: TagListFrame):
                    return lambda: open_single_class_type_chooser(dlg, base_name, ref_list, frame_ref)
                # First: list[Type[Base]] existing behavior
                if ann_origin in (list, List) and ann_args:
                    inner = ann_args[0]
                    inner_origin = get_origin(inner)
                    inner_args = get_args(inner)
                    if inner_origin in (type, Type) and inner_args and inspect.isclass(inner_args[0]):
                        base_cls = inner_args[0]
                        type_list = list(getattr(existing, p.name, []) if existing is not None else [])
                        tag_frame = create_element_frame(dlg, container, f"{p.name}_types_frame")
                        refresh_tags(type_list, tag_frame)
                        tk.Button(container, text="Choose Types", command=_make_multi_btn_handler(base_cls.__name__, type_list, tag_frame)).pack(fill='x', padx=(5,0), pady=(2,2))
                        entries[p.name] = {'type': 'hierarchical', 'get': _make_list_getter(type_list)}
                        continue
                # NEW: Single Type[Base] support (including Optional/Union[Type[Base], None])
                target_base_cls = None
                single_mode = False
                if ann_origin in (type, Type) and ann_args and inspect.isclass(ann_args[0]):
                    target_base_cls = ann_args[0]
                    single_mode = True
                # Optional / Union handling: Union[Type[Base], None]
                elif ann_origin is Union and ann_args:
                    for arg in ann_args:
                        arg_origin = get_origin(arg)
                        arg_args = get_args(arg)
                        if arg_origin in (type, Type) and arg_args and inspect.isclass(arg_args[0]):
                            target_base_cls = arg_args[0]
                            single_mode = True
                            break
                if single_mode and target_base_cls is not None:
                    existing_val = getattr(existing, p.name, None) if existing is not None else None
                    single_list: List[type] = [existing_val] if isinstance(existing_val, type) else []
                    tag_frame = create_element_frame(dlg, container, f"{p.name}_type_frame")
                    refresh_tags(single_list, tag_frame)
                    tk.Button(container, text="Choose Type", command=_make_single_btn_handler(target_base_cls.__name__, single_list, tag_frame)).pack(fill='x', padx=(5,0), pady=(2,2))
                    entries[p.name] = {'type': 'hierarchical', 'get': _make_single_getter(single_list)}
                    continue
            except Exception:
                pass

            # NEW: specialized combobox for map name selection
            if p.name in ('teleport_map', 'target_map_name'):
                try:
                    from pathlib import Path
                    base_dir = Path(__file__).resolve().parent
                    root_dir = base_dir.parent  # project root (utils' parent)
                    candidate_dirs = [
                        root_dir / 'src' / 'resources' / 'maps',
                        base_dir / 'src' / 'resources' / 'maps'
                    ]
                    map_names = set()
                    for d in candidate_dirs:
                        if d.exists():
                            for jf in d.glob('*.json'):
                                map_names.add(jf.stem)
                    map_list = sorted(map_names)
                except Exception:
                    map_list = []
                if not map_list:
                    tk.Label(container, text="No map files (*.json) found.", font=("Helvetica", 9, "italic"),
                             bg="#34495e", fg="#f39c12").pack(fill='x')
                combo_var = tk.StringVar()
                setattr(combo_var, '_hov_param', p.name)  # tag var with param name
                if isinstance(val, str) and val in map_list:
                    combo_var.set(val)
                elif map_list:
                    pass
                combo = ttk.Combobox(container, textvariable=combo_var, values=map_list, state='readonly')
                combo.pack(fill='x', pady=(2, 5))
                def _on_map_change(event=None):
                    # trigger coordinate refreshers then autosave
                    for r in coord_refreshers:
                        try:
                            r()
                        except Exception:
                            pass
                    auto_save()
                combo.bind('<<ComboboxSelected>>', _on_map_change)
                _add_map_var(combo_var)
                entries[p.name] = {'type': 'text', 'get': lambda v=combo_var: v.get(), 'is_map_name': True}
                # ensure traces attached after potential list filled
                _attach_traces()
                continue  # handled specialized field, move to next parameter

            # NEW: specialized combobox for selecting a tile's coordinates on selected map (or current map fallback)
            if p.name in ('teleport_tile', 'target_coordinates'):
                coord_combo_var = tk.StringVar()
                tuple_var = tk.StringVar()
                # UI combobox placeholder; values set in refresh
                coord_combo = ttk.Combobox(container, textvariable=coord_combo_var, values=[], state='readonly')
                coord_combo.pack(fill='x', pady=(2,5))
                display_to_coord: Dict[str, Tuple[int,int]] = {}
                # capture existing value to attempt reselect after refresh
                existing_coord = None
                if isinstance(val, (tuple, list)) and len(val) == 2:
                    try:
                        existing_coord = (int(val[0]), int(val[1]))
                    except Exception:
                        existing_coord = None
                search_param_order = ('teleport_map', 'target_map_name')
                def refresh_tiles():
                    nonlocal display_to_coord
                    display_to_coord = {}
                    # Determine map name
                    map_name = _get_selected_map_name()
                    tiles_source = None
                    if map_name:
                        # Attempt to load external map json
                        try:
                            from pathlib import Path
                            base_dir = Path(__file__).resolve().parent
                            root_dir = base_dir.parent  # project root (utils' parent)
                            candidate_dirs = [
                                root_dir / 'src' / 'resources' / 'maps',
                                base_dir / 'src' / 'resources' / 'maps'
                            ]
                            for d in candidate_dirs:
                                jf = d / f"{map_name}.json"
                                if jf.exists():
                                    with open(jf, 'r', encoding='utf-8') as f:
                                        data = json.load(f)
                                    tiles_source = data
                                    break
                        except Exception:
                            tiles_source = None
                    if tiles_source is None:
                        # fallback to current editor map
                        try:
                            tiles_source = {str(k): v for k,v in getattr(app, 'map_data', {}).items()}  # type: ignore[name-defined]
                        except Exception:
                            tiles_source = {}
                    # Build list
                    for k, tdata in tiles_source.items():
                        try:
                            if isinstance(k, str) and k.startswith('(') and k.endswith(')'):
                                parts = k.strip('()').split(',')
                                tx, ty = int(parts[0]), int(parts[1])
                            elif isinstance(k, (list, tuple)) and len(k) == 2:
                                tx, ty = int(k[0]), int(k[1])
                            else:
                                continue
                            title = tdata.get('title') if isinstance(tdata, dict) else None
                            if not title:
                                # attempt id fallback
                                if isinstance(tdata, dict):
                                    title = tdata.get('id', f"tile_{tx}_{ty}")
                                else:
                                    title = f"tile_{tx}_{ty}"
                            display = f"{title} ({tx},{ty})"
                            display_to_coord[display] = (tx, ty)
                        except Exception:
                            continue
                    # Update combobox values
                    values = sorted(display_to_coord.keys(), key=lambda s: (display_to_coord[s][0], display_to_coord[s][1]))
                    coord_combo.config(values=values)
                    # Preserve selection if still valid
                    if tuple_var.get():
                        try:
                            current_tuple = ast.literal_eval(tuple_var.get())
                        except Exception:
                            current_tuple = None
                    else:
                        current_tuple = existing_coord
                    if current_tuple and isinstance(current_tuple, (list, tuple)) and len(current_tuple) == 2:
                        for disp, coord in display_to_coord.items():
                            if coord == (int(current_tuple[0]), int(current_tuple[1])):
                                coord_combo_var.set(disp)
                                tuple_var.set(str(coord))
                                break
                    elif values:
                        # leave blank until user chooses (do not auto-select)
                        pass
                def on_coord_select(event=None):
                    disp = coord_combo_var.get()
                    coord = display_to_coord.get(disp)
                    if coord is not None:
                        tuple_var.set(str(coord))
                        auto_save()
                coord_combo.bind('<<ComboboxSelected>>', on_coord_select)
                refresh_tiles()
                coord_refreshers.append(refresh_tiles)
                # Ensure traces attached if map vars already exist
                _attach_traces()
                entries[p.name] = {'type': 'text', 'get': lambda v=tuple_var: v.get(), 'is_tile_coord': True}
                continue

            # Check for type hints that should use hierarchical selectors
            base_class, is_list, is_optional = parse_type_hint(p.annotation)

            # Use text entry for str, int, or no type hint
            if p.annotation is inspect._empty or p.annotation is str or p.annotation is int:
                ent = create_text_entry(container, val, auto_save)
                entries[p.name] = {'type': 'text', 'get': lambda v=ent: v.get()}

            elif base_class and inspect.isclass(base_class) and not isinstance(val, bool):
                # Use tag-based chooser for class-based type hints
                tag_frame = create_element_frame(dlg, container, f"{p.name}_frame")
                if is_list:
                    current_value = getattr(existing, p.name, []) if existing is not None else []
                else:
                    val = getattr(existing, p.name, None) if existing is not None else None
                    current_value = [val] if val is not None else []
                auto_save = auto_save  # capture in closure
                field_type = 'list' if is_list else 'single'

                # Initialize tags for any objects already present by default
                refresh_tags(current_value, tag_frame)

                base_class_name = str(base_class.__name__) if base_class else 'Object'
                is_event = True if base_class and base_class.__name__ == "Event" else False

                choose_btn = tk.Button(
                    container,
                    text="Choose",
                    command=lambda this_dlg=dlg, this_base_class_name=base_class_name,
                                       this_is_event=is_event, this_tag_frame=tag_frame,
                                       this_field_type=field_type: open_chooser(
                            this_dlg,
                            current_value if this_field_type == 'list' else (current_value[0] if current_value else []),
                            this_tag_frame,
                            base_class_name=this_base_class_name,
                            is_event=this_is_event
                        )
                )
                choose_btn.pack(fill='x', padx=(5, 0), pady=(2, 2))
                # Helper to avoid mutable default capture
                def _make_hier_getter(field_type_local: str, ref_list_local: List[Any]):
                    if field_type_local == 'list':
                        return lambda: ref_list_local
                    return lambda: (ref_list_local[0] if ref_list_local else None)
                entries[p.name] = {'type': 'hierarchical', 'get': _make_hier_getter(field_type, current_value)}
            elif p.name == 'merchant':
                if not all_merchants:
                    tk.Label(container, text="Add a Merchant NPC to this map first.",
                             font=("Helvetica", 9, "italic"), bg="#34495e", fg="#f39c12").pack(fill='x')
                else:
                    combo_var = tk.StringVar()
                    # If existing value is a merchant object, get its name
                    if val and isinstance(val, Merchant):
                        # Find the name corresponding to the instance
                        for name, inst in all_merchants.items():
                            if inst is val:
                                combo_var.set(name)
                                break
                    elif isinstance(val, str): # Fallback for name-based storage
                         combo_var.set(val)

                    combo = ttk.Combobox(container, textvariable=combo_var,
                                         values=list(all_merchants.keys()), state='readonly')
                    combo.pack(fill='x', pady=(2, 5))
                    def on_combo_change(event=None):
                        auto_save()
                    combo.bind('<<ComboboxSelected>>', on_combo_change)
                    entries[p.name] = {'type': 'text', 'get': lambda v=combo_var: v.get(), 'is_merchant': True}

            elif isinstance(val, bool):
                bool_var = create_bool_entry(container, val, auto_save)
                entries[p.name] = {'type': 'bool', 'get': lambda v=bool_var: v.get()}
            else:
                ent = create_text_entry(container, val, auto_save)
                entries[p.name] = {'type': 'text', 'get': lambda v=ent: v.get()}
        for i in range(col_count):
            frm.grid_columnconfigure(i, weight=1)
    else:
        tk.Label(frm, text="No editable properties.", bg="#34495e",
                 fg="#ecf0f1", font=("Helvetica", 12, "italic")).pack(pady=20)

    def on_add_save():
        if existing:
            auto_save()
            dlg.destroy()
        else:
            # For new objects, create the object and add it
            kwargs = {}
            for name, meta in entries.items():
                if meta['type'] == 'bool':
                    kwargs[name] = meta['get']()
                elif meta['type'] == 'hierarchical':
                    kwargs[name] = meta['get']()
                else:
                    raw = meta['get']()
                    if raw == '':
                        continue
                    try:
                        import ast as _ast
                        # Special handling for merchant combobox
                        if meta.get('is_merchant'):
                            kwargs[name] = all_merchants.get(raw)
                        else:
                            kwargs[name] = _ast.literal_eval(raw)
                    except Exception:
                        kwargs[name] = raw

            for p in excluded_params:
                kwargs[p.name] = None
            # Ensure repeat explicitly False if parameter exists but user didn't change
            if 'repeat' in [p.name for p in editable_params] and 'repeat' not in kwargs:
                kwargs['repeat'] = False
            inst = cls(**kwargs)
            if callback:
                callback(inst)
            dlg.destroy()

    def on_delete():
        if existing and messagebox.askyesno("Delete", f"Delete {existing.__class__.__name__}?"):
            if callback:
                callback(None)
            dlg.destroy()

    btn_frame = tk.Frame(dlg, bg="#34495e")
    btn_frame.pack(fill='x', pady=10)
    if existing:
        tk.Button(btn_frame, text="Delete", command=on_delete, bg="#e74c3c", fg="white",
                  font=("Helvetica", 12, "bold"), pady=5).pack(side='left', padx=5)
    # Update button text - "Close" for existing objects, "Add" for new objects
    button_text = "Close" if existing else "Add"
    tk.Button(btn_frame, text=button_text, command=on_add_save,
              bg="#2ecc71", fg="white", font=("Helvetica", 12, "bold"), pady=5).pack(side='right')


def get_editable_params(cls):
    sig = inspect.signature(cls.__init__)
    params = [p for p in sig.parameters.values() if p.name != 'self']
    excluded_names = {'player', 'tile'}
    editable_params = [p for p in params if p.name not in excluded_names]
    excluded_params = [p for p in params if p.name in excluded_names]
    return editable_params, excluded_params

def create_text_entry(container, val, auto_save):
    ent = tk.Entry(container)
    ent.insert(0, str(val) if val is not None else '')
    ent.pack(fill='x', pady=(2, 5))
    ent.bind('<FocusOut>', lambda e: auto_save())
    return ent

def create_bool_entry(container, val, auto_save):
    bool_var = tk.BooleanVar(value=bool(val))
    toggle_frame = tk.Frame(container, bg="#34495e")
    toggle_frame.pack(fill='x')
    def make_toggle_button(label, state):
        btn = tk.Button(toggle_frame, text=label, relief='sunken' if bool_var.get()==state else 'raised',
                        width=6,
                        command=lambda s=state: set_state(s))
        return btn
    def refresh_buttons():
        for b, state in buttons:
            if bool_var.get()==state:
                b.config(relief='sunken', bg='#2ecc71' if state else '#e74c3c', fg='white')
            else:
                b.config(relief='raised', bg='#7f8c8d', fg='black')
    def set_state(s):
        bool_var.set(s)
        refresh_buttons()
        auto_save()
    buttons = []
    btn_false = make_toggle_button('False', False)
    btn_false.pack(side='left', padx=(0,4))
    buttons.append((btn_false, False))
    btn_true = make_toggle_button('True', True)
    btn_true.pack(side='left')
    buttons.append((btn_true, True))
    refresh_buttons()
    return bool_var

# Do NOT remove this section; needed for testing the MapEditor directly
if __name__ == "__main__":
    root = tk.Tk()
    app = MapEditor(root)
    root.mainloop()
