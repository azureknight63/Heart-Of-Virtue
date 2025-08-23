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
from typing import Any, Dict, List, Tuple, Optional, cast  # type hinting (removed unused Iterable)


# Ensure the src directory is in sys.path for imports
project_root = os.path.dirname(os.path.dirname(__file__))
src_root = os.path.join(project_root, 'src')
if src_root not in sys.path:
    sys.path.insert(0, src_root)


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
        self.root.bind_all('<Delete>', lambda e: self.remove_selected_tile())
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
            # bring title on top of all other elements
            title_tag = f"title_{pos[0]}_{pos[1]}"
            self.canvas.tag_raise(title_tag)
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

        # Display truncated title
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
        """
        try:
            # build serializable structure
            def serialize_instance(inst: Any, seen=None) -> Dict[str, Any] | str:
                if seen is None:
                    seen = set()
                obj_id = id(inst)
                if obj_id in seen:
                    return f"<circular_ref:{type(inst).__name__}>"
                seen.add(obj_id)
                def recursive_serialize(val):
                    if isinstance(val, (int, float, str, bool)) or val is None:
                        return val
                    elif isinstance(val, list):
                        return [recursive_serialize(v) for v in val]
                    elif isinstance(val, tuple):
                        return tuple(recursive_serialize(v) for v in val)
                    elif isinstance(val, dict):
                        return {k: recursive_serialize(v) for k, v in val.items()}
                    elif hasattr(val, '__dict__'):
                        return serialize_instance(val, seen)
                    else:
                        return str(val)
                data = {kx: recursive_serialize(vx) for kx, vx in vars(inst).items() if not kx.startswith('_')}
                return {
                    '__class__': inst.__class__.__name__,
                    '__module__': inst.__class__.__module__,
                    'props': data
                }
            serializable_map: Dict[str, Any] = {}
            for k, v in self.map_data.items():
                tile: Dict[str, Any] = dict(v)
                for key in ['events','items','npcs','objects']:
                    inst_list = tile.get(key, [])
                    tile[key] = [serialize_instance(i) for i in inst_list]
                serializable_map[str(k)] = tile

            # Default save directory
            default_dir = os.path.join(os.getcwd(), 'src', 'resources', 'maps')
            os.makedirs(default_dir, exist_ok=True)
            filepath = filedialog.asksaveasfilename(
                initialdir=default_dir,
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )
            if filepath:
                with open(filepath, "w") as f:
                    json.dump(serializable_map, f, indent=4)
                self.current_map_filepath = filepath
                self.update_map_label()
                self.set_status(f"Map saved to {os.path.basename(filepath)}")
        except Exception as e:
            self.set_status(f"Error saving map: {e}")

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
                    # Recursively reconstruct any dict with __class__ and __module__ as an object
                    if isinstance(d, dict):
                        if '__class__' in d and '__module__' in d:
                            cls_name = d.get('__class__')
                            mod_name = d.get('__module__')
                            # Normalize module name for items, moves, etc.
                            if mod_name != 'builtins' and not mod_name.startswith('src.'):
                                mod_name = f'src.{mod_name}'
                            props = d.get('props', {})
                            try:
                                module = __import__(mod_name, fromlist=[cls_name])
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
                    pos = tuple(int(x) for x in k.strip('()').split(','))
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
                                        for inner in ast.walk(sub):
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
                            module_cache[mod_name] = __import__(mod_name, fromlist=['*'])
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

    # --- Added missing mouse coordinate helpers ---
    def _update_mouse_coordinates(self, event=None):
        """Update the coordinate label based on current pointer location (canvas-relative)."""
        if not getattr(self, 'coord_label', None):
            return
        if not self.canvas:
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
        self._update_mouse_coordinates()
        try:
            self.root.after(200, self._poll_mouse_position)
        except Exception:
            pass
    # --- end helpers ---



# Added back previously removed TagListFrame (required by TileEditorWindow)
class TagListFrame(tk.Frame):
    def __init__(self, parent, on_edit, on_remove, on_duplicate=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_edit = on_edit
        self.on_remove = on_remove
        self.on_duplicate = on_duplicate
        self._tags: List[Tuple[Any, tk.Frame]] = []
        self._tooltip: Optional[tk.Toplevel] = None

    def _get_editable_properties(self, obj) -> List[Tuple[str, str]]:
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

    def _show_tooltip(self, event, obj):
        self._hide_tooltip()
        header = obj.__class__.__name__ if hasattr(obj, '__class__') else 'Object'
        lines = [header]
        props = self._get_editable_properties(obj)
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

    def add_tag(self, identifier, text: str):
        frm = tk.Frame(self, bd=1, relief='solid', padx=4, pady=2)
        lbl = tk.Label(frm, text=text)
        lbl.pack(side='left')
        del_btn = tk.Button(frm, text='×', command=lambda: self.remove(identifier), bd=0, padx=2, pady=0)
        del_btn.pack(side='right')
        if self.on_duplicate:
            dup_btn = tk.Button(frm, text='⧉', command=lambda: self.on_duplicate(identifier), bd=0, padx=2, pady=0)
            dup_btn.pack(side='right')
        frm.pack(side='left', padx=2, pady=2)
        frm.bind('<Double-Button-1>', lambda e: self.on_edit(identifier))
        lbl.bind('<Double-Button-1>', lambda e: self.on_edit(identifier))
        self._bind_tooltip(frm, identifier)
        self._bind_tooltip(lbl, identifier)
        self._tags.append((identifier, frm))

    def remove(self, identifier):
        self.on_remove(identifier)
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
        self.tile_data = map_data[position]
        self.on_save_callback = on_save_callback

        # Pre-compute adjacency directions
        self._deltas = {"north":(0,-1),"south":(0,1),"east":(1,0),"west":(-1,0),
                        "northeast":(1,-1),"northwest":(-1,-1),"southeast":(1,1),"southwest":(-1,1)}
        self.valid_directions = [d for d,(dx,dy) in self._deltas.items() if (self.pos[0]+dx, self.pos[1]+dy) in self.map_data]
        # Purge stale exits / block_exit references referencing missing neighbors
        self.tile_data["exits"] = [d for d in self.tile_data.get("exits", []) if d in self.valid_directions]
        self.tile_data["block_exit"] = [d for d in self.tile_data.get("block_exit", []) if d in self.valid_directions]

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
        self.exits_listbox = tk.Listbox(frame_exits, selectmode="multiple", height=8)
        exits_sb = tk.Scrollbar(frame_exits, orient="vertical", command=self.exits_listbox.yview)
        self.exits_listbox.configure(yscrollcommand=exits_sb.set)
        for d in self.valid_directions:
            self.exits_listbox.insert("end", d)
            if d in self.tile_data.get("exits", []):
                self.exits_listbox.select_set("end")
        self.exits_listbox.pack(side="left", fill="x", expand=True)
        exits_sb.pack(side="right", fill="y")

        # Directions blocked
        tk.Label(exits_frame, text="Directions Blocked:", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        frame_dir = tk.Frame(exits_frame)
        frame_dir.pack(fill="x")
        self.directions_listbox = tk.Listbox(frame_dir, selectmode="multiple", height=8)
        dir_sb = tk.Scrollbar(frame_dir, orient="vertical", command=self.directions_listbox.yview)
        self.directions_listbox.configure(yscrollcommand=dir_sb.set)
        self.directions_listbox.pack(side="left", fill="x", expand=True)
        dir_sb.pack(side="right", fill="y")
        for d in self.valid_directions:
            self.directions_listbox.insert("end", d)
            if d in self.tile_data.get("block_exit", []):
                self.directions_listbox.select_set("end")
        tk.Label(exits_frame, text="Only directions with adjacent tiles are shown.", font=("Helvetica", 8, "italic"), bg="#34495e", fg="#bdc3c7").pack(anchor="w", pady=(5,0))


        # --- Items Tab ---
        items_tab_frame = tk.Frame(notebook, bg="#34495e", padx=10, pady=10)
        notebook.add(items_tab_frame, text="Items")
        tk.Button(items_tab_frame, text="Add Item", command=self.open_item_chooser,
                  font=("Helvetica", 10, "bold"), bg="#3498db", fg="white").pack(fill="x", pady=(0, 10))
        self.items_frame = TagListFrame(items_tab_frame, self.edit_item, self.remove_item, self.duplicate_item)
        self.items_frame.pack(fill="both", expand=True)


        # --- NPCs Tab ---
        npcs_tab_frame = tk.Frame(notebook, bg="#34495e", padx=10, pady=10)
        notebook.add(npcs_tab_frame, text="NPCs")
        tk.Button(npcs_tab_frame, text="Add NPC", command=self.open_npc_chooser,
                  font=("Helvetica", 10, "bold"), bg="#3498db", fg="white").pack(fill="x", pady=(0, 10))
        self.npcs_frame = TagListFrame(npcs_tab_frame, self.edit_npc, self.remove_npc, self.duplicate_npc)
        self.npcs_frame.pack(fill="both", expand=True)


        # --- Objects Tab ---
        objects_tab_frame = tk.Frame(notebook, bg="#34495e", padx=10, pady=10)
        notebook.add(objects_tab_frame, text="Objects")
        tk.Button(objects_tab_frame, text="Add Object", command=self.open_object_chooser,
                  font=("Helvetica", 10, "bold"), bg="#3498db", fg="white").pack(fill="x", pady=(0, 10))
        self.objects_frame = TagListFrame(objects_tab_frame, self.edit_object, self.remove_object, self.duplicate_object)
        self.objects_frame.pack(fill="both", expand=True)


        # --- Events Tab ---
        events_tab_frame = tk.Frame(notebook, bg="#34495e", padx=10, pady=10)
        notebook.add(events_tab_frame, text="Events")
        tk.Button(events_tab_frame, text="Add Event", command=self.open_event_chooser,
                  font=("Helvetica", 10, "bold"), bg="#3498db", fg="white").pack(fill="x", pady=(0, 10))
        self.events_frame = TagListFrame(events_tab_frame, self.edit_event, self.remove_event)
        self.events_frame.pack(fill="both", expand=True)


        # Save Button (outside notebook)
        save_button = tk.Button(main_frame, text="Save Changes", command=self.save_and_close,
                                font=("Helvetica", 12, "bold"), bg="#2ecc71", fg="white")
        save_button.pack(fill="x", pady=(10, 0))

        self.refresh_all_tags()

    def open_event_chooser(self):
        project_root = os.path.dirname(os.path.dirname(__file__))
        event_paths = []
        story_dir = os.path.join(project_root, 'src', 'story')
        if os.path.isdir(story_dir):
            for fname in os.listdir(story_dir):
                if fname.endswith('.py') and not fname.startswith('__'):
                    event_paths.append(os.path.join(story_dir, fname))
        self._show_hierarchy_chooser(event_paths, "Choose Event", self._add_event)

    def open_item_chooser(self):
        project_root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(project_root, 'src', 'items.py')
        self._show_hierarchy_chooser([path], "Choose Item", self._add_item)

    def open_npc_chooser(self):
        project_root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(project_root, 'src', 'npc.py')
        self._show_hierarchy_chooser([path], "Choose NPC", self._add_npc)

    def open_object_chooser(self):
        project_root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(project_root, 'src', 'objects.py')
        self._show_hierarchy_chooser([path], "Choose Object", self._add_object)

    def _show_hierarchy_chooser(self, module_paths, dialog_title, add_callback):
        """Display hierarchical class chooser for one or more module paths.
        module_paths: list[str] absolute file system paths.
        """
        # Parse modules and build unified class hierarchy across them
        class_info = {}  # name -> { 'bases': [...], 'children': set(), 'module': import_path }
        # Determine project root (assumes all paths share same root two levels up from utils)
        project_root = os.path.dirname(os.path.dirname(__file__))
        for module_path in module_paths:
            if not os.path.isfile(module_path):
                continue
            try:
                with open(module_path, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
            except Exception as e:
                messagebox.showerror("Error", f"Could not load module {module_path}:\n{e}")
                return
            # compute import path (e.g., src.events, src.tilesets.general)
            rel = os.path.relpath(module_path, project_root)
            # change path separators to dots and strip .py
            import_mod = rel.replace(os.sep, '.')
            if import_mod.lower().endswith('.py'):
                import_mod = import_mod[:-3]
            # ensure it starts with 'src.' (it should) else prepend
            if not import_mod.startswith('src.'):
                import_mod = 'src.' + str(import_mod)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    bases = []
                    for b in node.bases:
                        if isinstance(b, ast.Name):
                            bases.append(b.id)
                        elif isinstance(b, ast.Attribute):  # handle something.SomeBase
                            # take rightmost name
                            bases.append(b.attr)
                    info = class_info.setdefault(node.name, {'bases': [], 'children': set(), 'module': import_mod})
                    info['bases'] = bases
                    # keep first module encountered (avoid overwriting if duplicate name)
                    # if duplicate definitions across modules, we could namespace, but assume unique
        # build children relations
        for name, info in class_info.items():
            for base in info['bases']:
                if base in class_info:
                    class_info[base]['children'].add(name)
        # roots: classes whose bases are not in class_info
        roots = sorted([n for n, info in class_info.items() if not any(b in class_info for b in info['bases'])])
        # Build dialog
        dlg = tk.Toplevel(self.window)
        dlg.title(dialog_title)
        dlg.geometry('320x450')
        dlg.transient(self.window)
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
                    if n in visited:
                        continue
                    visited.add(n)
                    info = class_info[n]
                    # determine if this node or any descendant matches filter
                    def subtree_matches(cname):
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
                module = __import__(import_module, fromlist=[cls_name])
                cls = getattr(module, cls_name)
                self._open_property_dialog(cls, existing=None, callback=lambda inst: add_callback(inst))
            except Exception as ex:
                messagebox.showerror("Error", f"Could not create instance: {ex}")
            dlg.destroy()
        lb.bind('<Double-Button-1>', on_double)

    def _add_event(self, inst):
        self.tile_data.setdefault('events', []).append(inst)
        self._refresh_tags('events', self.events_frame)
    def _add_item(self, inst):
        items = self.tile_data.setdefault('items', [])
        # stacking logic
        if hasattr(inst, 'count'):
            for existing in items:
                if isinstance(existing, inst.__class__):
                    existing.count = getattr(existing, 'count', 1) + getattr(inst, 'count', 1)
                    break
            else:
                items.append(inst)
        else:
            items.append(inst)
        self._refresh_tags('items', self.items_frame)
    def _add_npc(self, inst):
        self.tile_data.setdefault('npcs', []).append(inst)
        self._refresh_tags('npcs', self.npcs_frame)
    def _add_object(self, inst):
        self.tile_data.setdefault('objects', []).append(inst)
        self._refresh_tags('objects', self.objects_frame)

    def duplicate_item(self, inst):
        try:
            new_inst = copy.deepcopy(inst)
        except Exception:
            # fallback shallow
            new_inst = inst.__class__.__new__(inst.__class__)
            new_inst.__dict__.update({k: v for k, v in inst.__dict__.items()})
        self._add_item(new_inst)

    def duplicate_npc(self, inst):
        try:
            new_inst = copy.deepcopy(inst)
        except Exception:
            new_inst = inst.__class__.__new__(inst.__class__)
            new_inst.__dict__.update({k: v for k, v in inst.__dict__.items()})
        self.tile_data.setdefault('npcs', []).append(new_inst)
        self._refresh_tags('npcs', self.npcs_frame)

    def duplicate_object(self, inst):
        try:
            new_inst = copy.deepcopy(inst)
        except Exception:
            new_inst = inst.__class__.__new__(inst.__class__)
            new_inst.__dict__.update({k: v for k, v in inst.__dict__.items()})
        self.tile_data.setdefault('objects', []).append(new_inst)
        self._refresh_tags('objects', self.objects_frame)

    def save_and_close(self):
        """Saves the edited properties back to the tile data and closes the window."""
        try:
            self.tile_data["title"] = self.title_entry.get().strip()
            self.tile_data["description"] = self.description_text.get("1.0", tk.END).strip()
            sel = self.exits_listbox.curselection()
            self.tile_data["exits"] = [self.exits_listbox.get(i) for i in sel]
            if self.directions_listbox:
                selected = self.directions_listbox.curselection()
                self.tile_data["block_exit"] = [self.directions_listbox.get(i) for i in selected]
            # Enforce validity again (safety if map changed during edit)
            self.tile_data["exits"] = [d for d in self.tile_data.get("exits", []) if d in self.valid_directions]
            self.tile_data["block_exit"] = [d for d in self.tile_data.get("block_exit", []) if d in self.valid_directions]
            self.tile_data["symbol"] = self.symbol_entry.get().strip()
            self.on_save_callback()
            self.window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input format. Please check your entries.\nDetails: {e}")

    # New methods for refresh, add, edit, remove
    def _refresh_tags(self, key, frame):
        frame.clear()
        for inst in self.tile_data.get(key, []):
            name = inst.__class__.__name__ if hasattr(inst, '__class__') else str(inst)
            frame.add_tag(inst, name)

    def refresh_all_tags(self):
        self._refresh_tags('events', self.events_frame)
        self._refresh_tags('items', self.items_frame)
        self._refresh_tags('npcs', self.npcs_frame)
        self._refresh_tags('objects', self.objects_frame)

    def _open_property_dialog(self, cls, existing=None, callback=None):
        dlg = tk.Toplevel(self.window)
        dlg.title(f"Properties for {cls.__name__}")
        dlg.geometry('900x550')  # triple width
        dlg.transient(self.window)
        dlg.grab_set()
        entries = {}  # name -> {'type': 'text'|'bool', 'get': callable}
        sig = inspect.signature(cls.__init__)
        params = [p for p in sig.parameters.values() if p.name != 'self']
        excluded_names = {'player', 'tile'}
        editable_params = [p for p in params if p.name not in excluded_names]
        excluded_params = [p for p in params if p.name in excluded_names]

        # Auto-save function that will be called on every change
        def auto_save():
            if not existing:
                return  # Only auto-save for existing objects, not when creating new ones

            kwargs = {}
            for name, meta in entries.items():
                if meta['type'] == 'bool':
                    kwargs[name] = meta['get']()
                else:
                    raw = meta['get']()
                    if raw == '':
                        continue
                    try:
                        import ast as _ast
                        kwargs[name] = _ast.literal_eval(raw)
                    except Exception:
                        kwargs[name] = raw

            # Apply changes to existing object
            for k, v in kwargs.items():
                setattr(existing, k, v)

            # Trigger callback to refresh UI if provided
            if callback:
                callback(existing)

        frm = tk.Frame(dlg, bg="#34495e", padx=14, pady=14)
        frm.pack(fill='both', expand=True)
        if editable_params:
            col_count = 2 if len(editable_params) > 6 else 1
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
                # boolean toggle if value is bool or default is bool
                if isinstance(val, bool):
                    bool_var = tk.BooleanVar(value=bool(val))
                    toggle_frame = tk.Frame(container, bg="#34495e")
                    toggle_frame.pack(fill='x')
                    def make_toggle_button(label, state):
                        btn = tk.Button(toggle_frame, text=label, relief='sunken' if bool_var.get()==state else 'raised',
                                        width=6,
                                        command=lambda s=state, b=label: set_state(s))
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
                        auto_save()  # Auto-save on boolean change
                    buttons = []
                    btn_false = make_toggle_button('False', False)
                    btn_false.pack(side='left', padx=(0,4))
                    buttons.append((btn_false, False))
                    btn_true = make_toggle_button('True', True)
                    btn_true.pack(side='left')
                    buttons.append((btn_true, True))
                    refresh_buttons()
                    entries[p.name] = {'type': 'bool', 'get': lambda v=bool_var: v.get()}
                else:
                    ent = tk.Entry(container)
                    if not isinstance(val, str):
                        try:
                            val = repr(val)
                        except Exception:
                            val = str(val)
                    ent.insert(0, val)
                    ent.pack(fill='x')
                    # Add auto-save on text field changes
                    def on_entry_change(event=None):
                        auto_save()
                    ent.bind('<KeyRelease>', on_entry_change)  # Auto-save on key release
                    ent.bind('<FocusOut>', on_entry_change)    # Auto-save when focus leaves field
                    entries[p.name] = {'type': 'text', 'get': lambda e=ent: e.get().strip()}
            for i in range(col_count):
                frm.grid_columnconfigure(i, weight=1)
        else:
            tk.Label(frm, text="No editable properties.", bg="#34495e", fg="#ecf0f1", font=("Helvetica", 12, "italic")).pack(pady=20)

        def on_add_save():
            if existing:
                # For existing objects, just close dialog since auto-save handles changes
                dlg.destroy()
            else:
                # For new objects, create the object and add it
                kwargs = {}
                for name, meta in entries.items():
                    if meta['type'] == 'bool':
                        kwargs[name] = meta['get']()
                    else:
                        raw = meta['get']()
                        if raw == '':
                            continue
                        try:
                            import ast as _ast
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
        tk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side='right', padx=5)
        if existing:
            tk.Button(btn_frame, text="Delete", command=on_delete, bg="#e74c3c", fg="white").pack(side='left', padx=5)
        # Update button text - "Close" for existing objects, "Add" for new objects
        button_text = "Close" if existing else "Add"
        tk.Button(btn_frame, text=button_text, command=on_add_save,
                  bg="#2ecc71", fg="white").pack(side='right')

    def edit_event(self, inst):
        def cb(res):
            if res is None:
                self.tile_data['events'].remove(inst)
            self._refresh_tags('events', self.events_frame)
        self._open_property_dialog(inst.__class__, existing=inst, callback=cb)

    def remove_event(self, inst):
        if inst in self.tile_data.get('events', []):
            self.tile_data['events'].remove(inst)
        self._refresh_tags('events', self.events_frame)

    def edit_item(self, inst):
        def cb(res):
            if res is None:
                self.tile_data['items'].remove(inst)
            self._refresh_tags('items', self.items_frame)
        self._open_property_dialog(inst.__class__, existing=inst, callback=cb)

    def remove_item(self, inst):
        if inst in self.tile_data.get('items', []):
            self.tile_data['items'].remove(inst)
        self._refresh_tags('items', self.items_frame)

    def edit_npc(self, inst):
        def cb(res):
            if res is None:
                self.tile_data['npcs'].remove(inst)
            self._refresh_tags('npcs', self.npcs_frame)
        self._open_property_dialog(inst.__class__, existing=inst, callback=cb)

    def remove_npc(self, inst):
        if inst in self.tile_data.get('npcs', []):
            self.tile_data['npcs'].remove(inst)
        self._refresh_tags('npcs', self.npcs_frame)

    def edit_object(self, inst):
        def cb(res):
            if res is None:
                self.tile_data['objects'].remove(inst)
            self._refresh_tags('objects', self.objects_frame)
        self._open_property_dialog(inst.__class__, existing=inst, callback=cb)

    def remove_object(self, inst):
        if inst in self.tile_data.get('objects', []):
            self.tile_data['objects'].remove(inst)
        self._refresh_tags('objects', self.objects_frame)

# Do NOT remove this section; needed for testing the MapEditor directly
if __name__ == "__main__":
    root = tk.Tk()
    app = MapEditor(root)
    root.mainloop()
