"""MapEditor -- the top-level Tkinter application window -- plus the Convert
Elements report helpers it drives (compute_convert_elements_report,
_dropped_fields_for_conversion, _get_last_map_file)."""
import copy
import glob
import inspect
import json
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Dict, List

# Issue #463: imported canonically (src.*) -- this module is shared with the
# game engine's own Universe loader and must resolve to the exact same module
# object (a bare `import map_placeholders` would create a duplicate with its
# own class-metadata registry, silently breaking cross-loader consistency).
import src.map_placeholders as map_placeholders  # type: ignore

from utils.mapgen.constants import DIRECTION_DELTAS, MapSerializationError, RECIPROCAL_DIRECTIONS
from utils.mapgen.property_dialog import _open_bulk_class_chooser
from utils.mapgen.tile_editor import TileEditorWindow
from utils.mapgen.widgets import create_button, create_separator


def _get_last_map_file():
    """
    Returns the path to the most recently modified JSON map file in cwd, or None.
    """
    try:
        files = glob.glob(os.path.join(os.getcwd(), "*.json"))
        if not files:
            return None
        return max(files, key=os.path.getmtime)
    except Exception:
        return None


# Issue #463: attribute names common enough across NPC/Item/Object/Event
# families that dropping them during Convert Elements is expected and not
# worth flagging in the review report -- circular backrefs, derived/base
# stat mirrors, and session-only bookkeeping. Not exhaustive per-class; only
# used to decide whether a converted element is reported as clean
# ("converted") or worth a second look ("ambiguous"). It never gates what's
# actually written to a saved placeholder -- that's governed entirely by
# each class's own MAP_AUTHORED_PARAMS/MAP_AUTHORED_OVERRIDES declarations.
_CONVERT_ELEMENTS_EXPECTED_DROPS = frozenset({
    "tile", "player", "current_room", "player_ref", "target", "owner",
    "known_moves", "current_move", "states", "in_combat",
    "combat_proximity", "combat_position", "hp", "fatigue", "ai_config",
    "shop_conditions", "resistance", "status_resistance",
    "maxhp_base", "damage_base", "protection_base", "speed_base",
    "finesse_base", "exp_award_base", "maxfatigue_base", "endurance_base",
    "strength_base", "charisma_base", "intelligence_base", "faith_base",
    "keywords", "action_aliases", "interactions", "aliases", "loot",
    "default_proximity", "can_yield", "pronouns", "isequipped",
    "equip_states", "add_resistance", "add_status_resistance",
    "gives_exp", "stack_key", "state", "revealed", "possible_states",
    "events", "thread", "has_run", "referenceobj", "completed",
    "api_event_id", "needs_input", "input_type", "input_prompt",
    "input_options", "description", "presentation", "spawned_npcs",
    "directions", "available_choices",
    # Friend/ally progression + tactical config (class-level or runtime, per
    # the issue #463 audit's NPC bucket findings) -- not per-instance authored.
    "level", "exp", "knocked_out", "battle_symbol", "bow_range",
    "dagger_range", "preferred_range", "wisdom",
})


def _dropped_fields_for_conversion(inst):
    """Return instance attribute names that won't survive Convert Elements
    for ``inst``, excluding the common runtime/circular names in
    ``_CONVERT_ELEMENTS_EXPECTED_DROPS`` and any leading-underscore
    (private/cache) attribute. Used only to flag an element "ambiguous" in
    the Convert Elements report -- see that constant's docstring.
    """
    cls = type(inst)
    kept = map_placeholders.authored_param_names(cls) | map_placeholders.authored_override_names(cls)
    dropped = []
    for name in vars(inst):
        if name.startswith("_") or name in kept or name in _CONVERT_ELEMENTS_EXPECTED_DROPS:
            continue
        dropped.append(name)
    return sorted(dropped)


def compute_convert_elements_report(map_data):
    """Issue #463: convert every not-yet-placeholder element across the
    whole map to the authored-placeholder format, in place.

    Tags each converted instance's ``_hov_placeholder_format = True`` so
    ``save_map``'s ``serialize_instance_for_save`` starts writing the
    compact shape for it. Nothing here writes to disk -- Convert Elements
    only changes the in-memory tag; Save Map remains a separate, explicit
    action, so the user can review this function's report before committing
    anything (the "whole map, but per-element review" flow).

    Returns a dict with "converted" / "ambiguous" / "skipped" lists of
    ``(label, detail)`` tuples:
      - converted: cleanly represented, nothing of note dropped.
      - ambiguous: converted, but some non-standard attribute was dropped
        (listed in ``detail``) -- worth a manual look.
      - skipped: left as legacy shape entirely -- the class has no
        authored-parameter metadata registered at all yet.
    """
    report = {"converted": [], "ambiguous": [], "skipped": []}
    for pos, tile in map_data.items():
        for category in ("events", "items", "npcs", "objects"):
            for inst in tile.get(category, []):
                if getattr(inst, "_hov_placeholder_format", None) is True:
                    continue  # already a placeholder; nothing to do
                label = f"{pos} / {category} / {type(inst).__name__}"
                cls = type(inst)
                if not map_placeholders.is_authorable(cls):
                    report["skipped"].append(
                        (label, "No authored-parameter metadata registered for this class yet.")
                    )
                    continue
                dropped = _dropped_fields_for_conversion(inst)
                inst._hov_placeholder_format = True
                if dropped:
                    report["ambiguous"].append((label, ", ".join(dropped)))
                else:
                    report["converted"].append((label, ""))
    return report


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
        self.map_title_label = tk.Label(
            self.root,
            text="Current Map: (Unsaved Map)",
            bg="#1f2d3a",
            fg="white",
            font=("Helvetica", 14, "bold"),
            pady=6,
        )
        self.map_title_label.pack(side="top", fill="x")
        # Coordinate tooltip label (always visible bottom-right)
        self.coord_label = tk.Label(
            self.root,
            text="Tile (0,0)  px(0,0)",
            bg="#1f2d3a",
            fg="white",
            font=("Helvetica", 9),
        )
        self.coord_label.place(relx=1.0, rely=1.0, x=-6, y=-6, anchor="se")
        # Update on any mouse movement inside the root
        self.root.bind("<Motion>", self._update_mouse_coordinates)
        # Also update periodically in case of external offset changes without movement
        self.root.after(200, self._poll_mouse_position)
        # Main Frame for UI controls
        controls_frame = tk.Frame(self.root, bg="#34495e", padx=10, pady=10)
        controls_frame.pack(side="left", fill="y")

        # Map Canvas
        self.canvas = tk.Canvas(
            self.root, bg="#ecf0f1", width=800, height=800, relief="sunken", bd=2
        )
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
        self.root.bind_all("<Control-c>", lambda e: self.copy_selection())
        self.root.bind_all("<Control-C>", lambda e: self.copy_selection())
        self.root.bind_all("<Control-x>", lambda e: self.cut_selection())
        self.root.bind_all("<Control-X>", lambda e: self.cut_selection())
        self.root.bind_all("<Control-v>", lambda e: self.paste_clipboard())
        self.root.bind_all("<Control-V>", lambda e: self.paste_clipboard())
        # Changed: route Delete key through guard handler so it is disabled while editor/property submenus are open.
        self.root.bind_all("<Delete>", self._delete_hotkey_handler)
        # --- Control Buttons ---
        create_button(
            "New Map",
            lambda: (self.ensure_add_mode_off(), self.create_new_map()),
            controls_frame,
        )
        create_button(
            "Load Map",
            lambda: (self.ensure_add_mode_off(), self.load_map()),
            controls_frame,
        )
        create_button(
            "Save Map",
            lambda: (self.ensure_add_mode_off(), self.save_map()),
            controls_frame,
        )
        create_button(
            "Convert Elements...",
            lambda: (self.ensure_add_mode_off(), self.convert_elements()),
            controls_frame,
        )
        create_separator(controls_frame)

        # Keep reference to Add Tile button to allow visual toggle
        self.add_tile_button = create_button(
            "Add Tile", self.toggle_add_tile_mode, controls_frame
        )
        create_button(
            "Remove Tile",
            lambda: (self.ensure_add_mode_off(), self.remove_selected_tile()),
            controls_frame,
        )
        create_button(
            "Edit Tile",
            lambda: (self.ensure_add_mode_off(), self.edit_selected_tile()),
            controls_frame,
        )
        create_button(
            "Bulk Edit...",
            lambda: (self.ensure_add_mode_off(), self.bulk_edit_selected_tiles()),
            controls_frame,
        )
        create_separator(controls_frame)

        create_button(
            "Auto-Connect Exits",
            lambda: (self.ensure_add_mode_off(), self.auto_connect_exits()),
            controls_frame,
        )
        create_separator(controls_frame)

        # Status Label
        self.status_label = tk.Label(
            controls_frame,
            text="Ready.",
            bg="#34495e",
            fg="white",
            font=("Helvetica", 10),
            wraplength=200,
            justify="left",
        )
        self.status_label.pack(side="bottom", fill="x", pady=(10, 0))
        # Adjust wraplength dynamically to match panel width
        controls_frame.bind(
            "<Configure>", lambda e: self.status_label.config(wraplength=e.width)
        )
        # Ensure coordinate label is on top of canvas stacking order
        self._raise_coord_label()

    def _raise_coord_label(self):
        """Raise (lift) the coordinate label above the canvas so it is never obscured."""
        if getattr(self, "coord_label", None):
            try:
                self.coord_label.lift()  # lift above sibling widgets
            except Exception:
                pass

    def handle_canvas_click(self, event):
        """Updated to support modifier-based multi-select and empty tile selection."""
        x = int((event.x - self.offset_x) // self.tile_size)
        y = int((event.y - self.offset_y) // self.tile_size)
        pos = (x, y)
        ctrl = (event.state & 0x0004) != 0
        shift = (event.state & 0x0001) != 0
        if self.is_adding_tile:
            if pos not in self.map_data:
                self.add_tile(x, y)
                self.set_status(f"Added new tile at ({x}, {y}).")
            else:
                self.set_status(f"Tile already exists at ({x}, {y}).")
            return
        # Selection logic
        if shift and self.selection_anchor:
            ax, ay = self.selection_anchor
            minx, maxx = sorted((ax, x))
            miny, maxy = sorted((ay, y))
            region = {
                (ix, iy) for ix in range(minx, maxx + 1) for iy in range(miny, maxy + 1)
            }
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
            "objects": [],
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
            old_id = tile.get("id")
            old_title = tile.get("title")
            nx, ny = x - shift_x, y - shift_y
            tile = dict(tile)  # shallow copy
            new_id = f"tile_{nx}_{ny}"
            tile["id"] = new_id
            # If the title was auto-generated (matched the old id), update it to new id
            if old_title == old_id:
                tile["title"] = new_id
            new_map[(nx, ny)] = tile
        # Update selected tile reference if present
        if self.selected_tile:
            sx, sy = self.selected_tile
            self.selected_tile = (sx - shift_x, sy - shift_y)
        # Update all multi-selected tiles
        if self.selected_tiles:
            self.selected_tiles = {
                (x - shift_x, y - shift_y) for (x, y) in self.selected_tiles
            }
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
            deltas = DIRECTION_DELTAS
            for pos_key, tile in self.map_data.items():

                def neighbor_exists(direction):
                    dx, dy = deltas[direction]
                    return (pos_key[0] + dx, pos_key[1] + dy) in self.map_data

                tile["exits"] = [
                    d
                    for d in tile.get("exits", [])
                    if d in deltas and neighbor_exists(d)
                ]
                tile["block_exit"] = [
                    d
                    for d in tile.get("block_exit", [])
                    if d in deltas and neighbor_exists(d)
                ]
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
            TileEditorWindow(
                self.root, self.map_data, self.selected_tile, self.draw_map
            )
        else:
            self.set_status("No tile selected to edit.")

    def bulk_edit_selected_tiles(self):
        """Edit one property set across every matching object on the
        current multi-tile selection (issue #16's "bulk editing of
        properties for multiple selected tiles" ask).

        Reuses the existing multi-select mechanism (self.selected_tiles,
        already populated by ctrl-click/drag-select) rather than adding a
        new selection UI. Scans every "objects"/"npcs"/"events" bucket
        across the selected tiles, groups the instances found by class, and
        -- once the user picks a class -- opens one property dialog whose
        edits apply to every instance of that class across the whole
        selection (open_property_dialog's existing_list support).
        """
        if len(self.selected_tiles) < 2:
            self.set_status(
                "Select 2+ tiles (ctrl-click or drag-select) to bulk edit."
            )
            return

        candidates: Dict[type, List[Any]] = {}
        for pos in self.selected_tiles:
            tile_data = self.map_data.get(pos)
            if not tile_data:
                continue
            for bucket in ("objects", "npcs", "events", "items"):
                for inst in tile_data.get(bucket, []) or []:
                    candidates.setdefault(type(inst), []).append(inst)

        if not candidates:
            self.set_status("No editable objects found on the selected tiles.")
            return

        _open_bulk_class_chooser(
            self.root, candidates, self.draw_map, map_data=self.map_data
        )

    def toggle_add_tile_mode(self):
        """
        Toggles the add tile mode and updates the Add Tile button appearance.
        """
        self.is_adding_tile = not self.is_adding_tile
        if self.is_adding_tile:
            self.set_status("Click on the canvas to add a new tile.")
            self.select_tile(None)
            if hasattr(self, "add_tile_button") and self.add_tile_button:
                self.add_tile_button.config(
                    relief="sunken", bg="#e67e22", activebackground="#d35400"
                )
        else:
            self.set_status("Add tile mode off.")
            if hasattr(self, "add_tile_button") and self.add_tile_button:
                self.add_tile_button.config(
                    relief="raised", bg="#3498db", activebackground="#2980b9"
                )

    def auto_connect_exits(self):
        """Automatically creates exits between adjacent tiles (cardinal + diagonal)."""
        # Clear existing exits
        for tile in self.map_data.values():
            tile["exits"] = []
        deltas = DIRECTION_DELTAS
        reciprocal = RECIPROCAL_DIRECTIONS
        for pos, tile in self.map_data.items():
            x, y = pos
            for direction, (dx, dy) in deltas.items():
                nbr = (x + dx, y + dy)
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
        return (
            int((event.x - self.offset_x) // self.tile_size),
            int((event.y - self.offset_y) // self.tile_size),
        )

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
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._drag_data["dragged"] = False

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
                    self.canvas.create_rectangle(
                        rx1, ry1, rx2, ry2, outline="black", dash=(3, 2)
                    )
        self._drag_data["dragged"] = True

    def _on_mouse_up(self, event):
        # Finish marquee or treat as click if no drag started
        if self.drag_select_mode and self.drag_start_tile is not None:
            if self._drag_started and self.drag_current_tile is not None:
                # Marquee selection
                x0, y0 = self.drag_start_tile
                x1, y1 = self.drag_current_tile
                minx, maxx = sorted((x0, x1))
                miny, maxy = sorted((y0, y1))
                new_region = {
                    (x, y) for x in range(minx, maxx + 1) for y in range(miny, maxy + 1)
                }
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
                    self.selection_anchor = (
                        next(iter(new_region)) if new_region else None
                    )
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
        self._drag_data["dragged"] = False

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
                self.clipboard = {"empty": True}
                self.set_status("Copied empty tile placeholder.")
                return
        # Capture tiles present within selection
        tiles_present = {
            p: self.map_data[p] for p in self.selected_tiles if p in self.map_data
        }
        if not tiles_present:
            self.clipboard = {"empty": True}
            self.set_status("Copied empty area (acts as delete on paste).")
            return
        minx = min(p[0] for p in tiles_present)
        miny = min(p[1] for p in tiles_present)
        payload = {}
        for (x, y), tile in tiles_present.items():
            rel = (x - minx, y - miny)
            payload[rel] = copy.deepcopy(tile)
        w = 1 + max(p[0] for p in payload.keys())
        h = 1 + max(p[1] for p in payload.keys())
        self.clipboard = {"tiles": payload, "w": w, "h": h}
        self.set_status(f"Copied {len(payload)} tile(s).")

    def cut_selection(self):
        self.copy_selection()
        # Only remove if clipboard not empty placeholder
        if self.clipboard and self.clipboard.get("empty"):
            return  # nothing to cut; treat like copying empty
        removed = 0
        for p in list(self.selected_tiles):
            if p in self.map_data:
                del self.map_data[p]
                removed += 1
        if removed:
            self._normalize_min_padding()
            self.draw_map()
        self.set_status(f"Cut {removed} tile(s).")

    def paste_clipboard(self):
        if not self.clipboard or not self.selected_tiles:
            return
        # Empty clipboard => delete selected existing tiles
        if self.clipboard.get("empty"):
            removed = 0
            for p in list(self.selected_tiles):
                if p in self.map_data:
                    del self.map_data[p]
                    removed += 1
            if removed:
                self._normalize_min_padding()
                self.draw_map()
            self.set_status(f"Deleted {removed} tile(s) via empty paste.")
            return
        payload = self.clipboard.get("tiles", {})
        if not payload:
            return
        # If clipboard has single tile and selection has multiple -> replicate
        if len(payload) == 1 and len(self.selected_tiles) > 1:
            rel_pos, tile_data = next(iter(payload.items()))
            for target in self.selected_tiles:
                self._paste_single_tile(tile_data, target)
            self._normalize_min_padding()
            self.draw_map()
            self.set_status(f"Pasted tile to {len(self.selected_tiles)} positions.")
            return
        # Otherwise paste relative pattern anchored at first selected tile
        anchor = next(iter(sorted(self.selected_tiles)))
        base = min(payload.keys())  # smallest (dx,dy) lexicographically
        count = 0
        for (dx, dy), tile_data in payload.items():
            offsetx = dx - base[0]
            offsety = dy - base[1]
            target = (anchor[0] + offsetx, anchor[1] + offsety)
            self._paste_single_tile(tile_data, target)
            count += 1
        self._normalize_min_padding()
        self.draw_map()
        self.set_status(f"Pasted {count} tile(s).")

    def _paste_single_tile(self, tile_data, target):
        x, y = target
        new_id = f"tile_{x}_{y}"
        tcopy = copy.deepcopy(tile_data)
        old_id = tcopy.get("id")
        old_title = tcopy.get("title")
        tcopy["id"] = new_id
        if old_title == old_id or re.fullmatch(r"tile_\d+_\d+", str(old_title)):
            tcopy["title"] = new_id
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
                x, y = p
                x1 = x * self.tile_size + self.offset_x
                y1 = y * self.tile_size + self.offset_y
                x2 = x1 + self.tile_size
                y2 = y1 + self.tile_size
                self.canvas.create_rectangle(x1, y1, x2, y2, outline="black", width=2)
                # small coord text inside
                self.canvas.create_text(
                    (x1 + x2) / 2,
                    (y1 + y2) / 2,
                    text=f"{x},{y}",
                    fill="black",
                    font=("Helvetica", 8),
                )
            else:
                # Highlight already handled by tile color; add border for clarity if multi-select
                if len(self.selected_tiles) > 1:
                    x, y = p
                    x1 = x * self.tile_size + self.offset_x
                    y1 = y * self.tile_size + self.offset_y
                    x2 = x1 + self.tile_size
                    y2 = y1 + self.tile_size
                    self.canvas.create_rectangle(
                        x1, y1, x2, y2, outline="yellow", width=2
                    )
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
        self.canvas.create_rectangle(
            x1, y1, x2, y2, fill=color, outline="#2c3e50", tags=(tag,)
        )
        # show exclamation points if there are events
        tile = self.map_data.get(pos, {})
        if tile.get("events"):
            center_y = y1 + self.tile_size / 2
            ex_size = int(self.tile_size * 0.4)
            left_x = x1 + ex_size / 2
            right_x = x2 - ex_size / 2
            self.canvas.create_text(
                left_x,
                center_y,
                text="!",
                fill="red",
                font=("Helvetica", ex_size, "bold"),
            )
            self.canvas.create_text(
                right_x,
                center_y,
                text="!",
                fill="red",
                font=("Helvetica", ex_size, "bold"),
            )

        # Display truncated title at top
        title = self.map_data.get(pos, {}).get("title", self.map_data[pos]["id"])
        max_chars = max(int(self.tile_size / 6), 1)
        disp = title if len(title) <= max_chars else title[: max_chars - 1] + "…"
        title_tag = f"title_{x}_{y}"
        self.canvas.create_text(
            x1 + self.tile_size / 2,
            y1 + 2,
            text=disp,
            fill="white",
            font=("Helvetica", 8, "bold"),
            anchor="n",
            tags=(tag, title_tag),
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
            tags=(tag, counts_tag),
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
        deltas = DIRECTION_DELTAS
        reciprocal = RECIPROCAL_DIRECTIONS
        for direction in tile.get("exits", []):
            dx, dy = deltas.get(direction, (0, 0))
            target_pos = (pos[0] + dx, pos[1] + dy)
            if target_pos in self.map_data:
                x_target = (
                    target_pos[0] * self.tile_size + self.tile_size / 2 + self.offset_x
                )
                y_target = (
                    target_pos[1] * self.tile_size + self.tile_size / 2 + self.offset_y
                )
                bidir = reciprocal.get(direction) in self.map_data[target_pos].get(
                    "exits", []
                )
                arrow_style = tk.BOTH if bidir else tk.LAST
                self.canvas.create_line(
                    x_center,
                    y_center,
                    x_target,
                    y_target,
                    arrow=arrow_style,
                    fill="#2c3e50",
                    width=2,
                )

    def save_map(self):
        """
        Saves the current map data to a JSON file.
        Enhanced: Provides detailed diagnostic information (tile, category, index, object type, attribute) if
        serialization fails so the user can quickly locate and fix problematic data.
        """
        try:
            # build serializable structure
            def serialize_instance(
                inst: Any, seen=None, *, tile_pos=None, category=None, index=None
            ) -> Dict[str, Any] | str:
                if seen is None:
                    seen = set()
                obj_id = id(inst)
                if obj_id in seen:
                    return f"<circular_ref:{type(inst).__name__}>"
                seen.add(obj_id)

                def recursive_serialize(val, *, attr_name=None):
                    try:
                        if inspect.isclass(val):
                            return {
                                "__class_type__": f"{val.__module__}:{val.__name__}"
                            }
                        if inspect.ismethod(val) or inspect.isfunction(val):
                            # Bound/unbound methods are dynamically-attached
                            # convenience aliases (e.g. Passageway's per-word
                            # keyword aliases binding self.enter under names
                            # like "ferry"/"jambo") -- not persistable state.
                            # Serializing them previously produced bogus
                            # {"__class__": "method", "__module__": "builtins"}
                            # payloads that the map loader's security gate
                            # correctly refuses at load time. Drop them; the
                            # loader always re-derives the alias attributes
                            # from the class's own __init__ logic.
                            return None
                        if isinstance(val, (int, float, str, bool)) or val is None:
                            return val
                        elif isinstance(val, list):
                            out = []
                            for i, subv in enumerate(val):
                                try:
                                    out.append(
                                        recursive_serialize(
                                            subv, attr_name=f"{attr_name}[{i}]"
                                        )
                                    )
                                except MapSerializationError:
                                    raise
                                except Exception as ex_list:
                                    raise MapSerializationError(
                                        tile=tile_pos,
                                        category=category,
                                        index=index,
                                        attribute=f"{attr_name}[{i}]",
                                        object_type=type(subv).__name__,
                                        object_repr=repr(subv)[:180],
                                        original=ex_list,
                                    )
                            return out
                        elif isinstance(val, tuple):
                            tup_out = []
                            for i, subv in enumerate(val):
                                try:
                                    tup_out.append(
                                        recursive_serialize(
                                            subv, attr_name=f"{attr_name}({i})"
                                        )
                                    )
                                except MapSerializationError:
                                    raise
                                except Exception as ex_tup:
                                    raise MapSerializationError(
                                        tile=tile_pos,
                                        category=category,
                                        index=index,
                                        attribute=f"{attr_name}({i})",
                                        object_type=type(subv).__name__,
                                        object_repr=repr(subv)[:180],
                                        original=ex_tup,
                                    )
                            return tup_out  # store tuples as lists
                        elif isinstance(val, dict):
                            result_dict = {}
                            for dk, dv in val.items():
                                try:
                                    result_dict[dk] = recursive_serialize(
                                        dv,
                                        attr_name=(
                                            f"{attr_name}.{dk}"
                                            if attr_name
                                            else str(dk)
                                        ),
                                    )
                                except MapSerializationError:
                                    raise
                                except Exception as ex_dict:
                                    raise MapSerializationError(
                                        tile=tile_pos,
                                        category=category,
                                        index=index,
                                        attribute=(
                                            f"{attr_name}.{dk}"
                                            if attr_name
                                            else str(dk)
                                        ),
                                        object_type=type(dv).__name__,
                                        object_repr=repr(dv)[:180],
                                        original=ex_dict,
                                    )
                            return result_dict
                        elif hasattr(val, "__dict__"):
                            return serialize_instance(
                                val,
                                seen,
                                tile_pos=tile_pos,
                                category=category,
                                index=index,
                            )
                        else:
                            # Fallback: best-effort stringification
                            return str(val)
                    except MapSerializationError:
                        raise
                    except Exception as ex_other:
                        raise MapSerializationError(
                            tile=tile_pos,
                            category=category,
                            index=index,
                            attribute=attr_name,
                            object_type=type(val).__name__,
                            object_repr=repr(val)[:180],
                            original=ex_other,
                        )

                try:
                    data = {}
                    for kx, vx in vars(inst).items():
                        if kx.startswith("_"):
                            continue
                        if inspect.ismethod(vx) or inspect.isfunction(vx):
                            # Dynamically-attached alias attributes (see
                            # recursive_serialize's method/function branch)
                            # are not persistable state; omit the key
                            # entirely rather than writing a null placeholder.
                            continue
                        try:
                            data[kx] = recursive_serialize(vx, attr_name=kx)
                        except MapSerializationError:
                            raise
                        except Exception as ex_attr:
                            raise MapSerializationError(
                                tile=tile_pos,
                                category=category,
                                index=index,
                                attribute=kx,
                                object_type=type(vx).__name__,
                                object_repr=repr(vx)[:180],
                                original=ex_attr,
                            )
                    # Attempt to include merchant property if accessible
                    if "merchant" not in data and hasattr(inst, "merchant"):
                        try:
                            mval = getattr(inst, "merchant")
                            data["merchant"] = recursive_serialize(
                                mval, attr_name="merchant"
                            )
                        except Exception:
                            pass
                except MapSerializationError:
                    raise
                except Exception as ex_unknown:
                    raise MapSerializationError(
                        tile=tile_pos,
                        category=category,
                        index=index,
                        attribute="__dict__",
                        object_type=type(inst).__name__,
                        object_repr=repr(inst)[:180],
                        original=ex_unknown,
                    )
                return {
                    "__class__": inst.__class__.__name__,
                    # Issue #463: strip any "src." prefix before writing.
                    # load_map() now resolves classes exclusively through
                    # map_placeholders.resolve_class (canonical-only), so an
                    # instance reloaded through this editor reports a
                    # "src."-prefixed __module__ even for legacy-shape
                    # elements -- writing that verbatim would produce a
                    # legacy map file Universe's own loader rejects outright
                    # (it raises on a "src."-prefixed __module__, since
                    # persisted data must store bare names by contract).
                    "__module__": map_placeholders.bare_module_name(
                        inst.__class__.__module__
                    ),
                    "props": data,
                }

            def serialize_instance_for_save(inst, *, tile_pos, category, index):
                """Issue #463: write the compact authored-placeholder shape for
                any element the editor considers placeholder-eligible, falling
                back to the legacy full-instance dump above for everything
                else. Nothing here forces a migration: an element loaded from
                a legacy map file (see load_map's deserialize_instance) is
                tagged ``_hov_placeholder_format = False`` and always keeps
                writing legacy shape until it goes through Convert Elements,
                even if the class has since gained authored metadata. Newly
                placed elements (no tag yet) default to placeholder when the
                class supports it.
                """
                use_placeholder = getattr(inst, "_hov_placeholder_format", None)
                if use_placeholder is not False:
                    def nested_fallback(value):
                        return serialize_instance(
                            value, tile_pos=tile_pos, category=category, index=index
                        )

                    try:
                        payload = map_placeholders.to_placeholder(
                            inst, nested_fallback=nested_fallback
                        )
                    except map_placeholders.PlaceholderError as e:
                        raise MapSerializationError(
                            tile=tile_pos,
                            category=category,
                            index=index,
                            object_type=type(inst).__name__,
                            object_repr=repr(inst)[:180],
                            original=e,
                            note="Placeholder serialization failure",
                        )
                    if payload is not None:
                        return payload
                return serialize_instance(
                    inst, tile_pos=tile_pos, category=category, index=index
                )

            serializable_map: Dict[str, Any] = {"meta": {"schema_version": map_placeholders.SCHEMA_VERSION}}
            for k, v in self.map_data.items():
                tile: Dict[str, Any] = dict(v)
                # Serialize each instance collection with granular error handling
                for key in ["events", "items", "npcs", "objects"]:
                    inst_list = tile.get(key, [])
                    serialized_instances = []
                    for idx, inst in enumerate(inst_list):
                        try:
                            serialized_instances.append(
                                serialize_instance_for_save(
                                    inst, tile_pos=k, category=key, index=idx
                                )
                            )
                        except MapSerializationError as mse:
                            # Re-raise to outer except so unified handling occurs
                            raise mse
                        except Exception as ex_generic:
                            raise MapSerializationError(
                                tile=k,
                                category=key,
                                index=idx,
                                object_type=type(inst).__name__,
                                object_repr=repr(inst)[:180],
                                original=ex_generic,
                                note="Generic serialization failure",
                            )
                    tile[key] = serialized_instances
                serializable_map[str(k)] = tile

            # Default save directory
            default_dir = os.path.join(os.getcwd(), "src", "resources", "maps")
            os.makedirs(default_dir, exist_ok=True)
            filepath = filedialog.asksaveasfilename(
                initialdir=default_dir,
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")],
            )
            if filepath:
                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(serializable_map, f, indent=4)
                except Exception as ex_write:
                    raise MapSerializationError(
                        note="Failed writing JSON to disk", original=ex_write
                    )
                self.current_map_filepath = filepath
                self.update_map_label()
                self.set_status(f"Map saved to {os.path.basename(filepath)}")
        except MapSerializationError as mse:
            detailed = str(mse)
            self.set_status(f"Error saving map: {detailed}")
            try:
                messagebox.showerror("Save Error", detailed)
            except Exception:
                pass
        except Exception as e:
            # Fallback generic error (unexpected)
            self.set_status(f"Error saving map: {type(e).__name__}: {e}")
            try:
                messagebox.showerror(
                    "Save Error",
                    f"Unexpected error saving map:\n{type(e).__name__}: {e}",
                )
            except Exception:
                pass

    def load_map(self, filepath=None):
        """
        Loads map data from a JSON file.
        """
        if filepath is None:
            filepath = filedialog.askopenfilename(
                defaultextension=".json", filetypes=[("JSON files", "*.json")]
            )
        if filepath:
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)

                def deserialize_instance(d):
                    # Issue #463: authored-placeholder shape, tried first (see
                    # save_map's serialize_instance_for_save). Tagged so a
                    # later save keeps writing the compact shape without
                    # requiring an explicit Convert Elements pass on it.
                    if isinstance(d, dict) and map_placeholders.is_placeholder_payload(d):
                        try:
                            inst = map_placeholders.instantiate_placeholder(d)
                        except map_placeholders.PlaceholderError as e:
                            self.set_status(f"Error loading placeholder: {e}")
                            return d
                        try:
                            inst._hov_placeholder_format = True
                        except Exception:
                            pass
                        return inst
                    # Restore class objects. Issue #463: routed through the
                    # same canonicalize + secure_pickle allow-list gate as
                    # Universe's game-boot loader (previously ungated here --
                    # a map file is attacker-influenceable the same way a save
                    # file is, see the issue #463 audit's "Risks found").
                    if isinstance(d, dict) and "__class_type__" in d:
                        try:
                            return map_placeholders.resolve_class(d["__class_type__"])
                        except map_placeholders.PlaceholderError as e:
                            self.set_status(f"Error resolving class reference: {e}")
                            return d["__class_type__"]  # fallback to string spec
                    # Recursively reconstruct any dict with '__class__' and '__module__' as an object
                    if isinstance(d, dict):
                        if "__class__" in d and "__module__" in d:
                            cls_name = d.get("__class__")
                            mod_name = d.get("__module__")
                            # `or {}` (not just a .get default) because some
                            # existing map files have a literal JSON null for
                            # "props" (a pre-existing serialization gap, not
                            # introduced here) -- the key is present but the
                            # value is None, so a plain .get default never
                            # kicks in and `.items()` below would raise.
                            props = d.get("props") or {}
                            try:
                                cls = map_placeholders.resolve_class(f"{mod_name}:{cls_name}")
                            except map_placeholders.PlaceholderError as e:
                                self.set_status(
                                    f"Error resolving '{mod_name}.{cls_name}': {e}"
                                )
                                return d
                            try:
                                consumed_keys: set = set()
                                try:
                                    param_names = [
                                        p.name
                                        for p in inspect.signature(
                                            cls.__init__
                                        ).parameters.values()
                                        if p.name != "self"
                                    ]
                                    init_kwargs = {
                                        k: deserialize_instance(v)
                                        for k, v in props.items()
                                        if k in param_names
                                    }
                                    inst = cls(**init_kwargs)
                                    # Keys already consumed by the constructor are
                                    # skipped below -- re-deserializing them would
                                    # discard the just-constructed nested instances
                                    # and build fresh duplicates for no benefit.
                                    consumed_keys = set(init_kwargs)
                                except Exception:
                                    inst = cls.__new__(cls)
                                    try:
                                        cls.__init__(inst)  # type: ignore
                                    except Exception:
                                        pass
                                # Recursively set any remaining attributes not covered
                                # by the constructor call above.
                                for k2, v2 in props.items():
                                    if k2 in consumed_keys:
                                        continue
                                    setattr(inst, k2, deserialize_instance(v2))
                                # Tagged so save_map's serialize_instance_for_save
                                # keeps writing legacy shape for this element
                                # until it goes through an explicit Convert
                                # Elements pass -- no forced migration.
                                try:
                                    inst._hov_placeholder_format = False
                                except Exception:
                                    pass
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
                        pos = tuple(int(x) for x in k.strip("()").split(","))
                    except ValueError:
                        continue
                    tile_copy: Dict[str, Any] = dict(tile)
                    for key in ["events", "items", "npcs", "objects"]:
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

    def convert_elements(self):
        """Convert Elements action (issue #463).

        Converts every legacy-shape element on the *currently loaded* map to
        the compact authored-placeholder format in one pass, then shows a
        review dialog grouped into converted / needs-review / skipped before
        anything is written to disk -- Save Map remains a separate, explicit
        step. See ``compute_convert_elements_report`` for the conversion
        rules and what each category means.
        """
        if not getattr(self, "map_data", None):
            messagebox.showinfo("Convert Elements", "No map is currently loaded.")
            return
        report = compute_convert_elements_report(self.map_data)
        self._show_convert_elements_report(report)

    def _show_convert_elements_report(self, report):
        total = (
            len(report["converted"]) + len(report["ambiguous"]) + len(report["skipped"])
        )
        if total == 0:
            messagebox.showinfo(
                "Convert Elements",
                "Every element on this map is already in the compact placeholder format.",
            )
            return

        summary = (
            f"Converted: {len(report['converted'])}   "
            f"Needs review: {len(report['ambiguous'])}   "
            f"Skipped: {len(report['skipped'])}"
        )

        win = tk.Toplevel(self.root)
        win.title("Convert Elements — Review")
        win.geometry("640x480")

        tk.Label(win, text=summary, font=("Helvetica", 10, "bold")).pack(pady=(10, 4))
        tk.Label(
            win,
            text="Nothing has been saved yet. Review below, then use Save Map "
            "to write the compact output.",
            font=("Helvetica", 9, "italic"),
        ).pack(pady=(0, 8))

        text_frame = tk.Frame(win)
        text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        report_text = tk.Text(text_frame, wrap="word", yscrollcommand=scrollbar.set)
        report_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=report_text.yview)

        for label, _detail in report["converted"]:
            report_text.insert("end", f"[converted] {label}\n")
        for label, detail in report["ambiguous"]:
            report_text.insert("end", f"[needs review] {label} — dropped: {detail}\n")
        for label, detail in report["skipped"]:
            report_text.insert("end", f"[skipped] {label} — {detail}\n")
        report_text.config(state="disabled")

        tk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))
        self.set_status(f"Convert Elements: {summary}")

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
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._drag_data["dragged"] = False

    def on_pan_move(self, event):
        """Handle canvas panning on mouse drag."""
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self.offset_x += dx
        self.offset_y += dy
        self._drag_data["dragged"] = True
        self.draw_map()

    def on_pan_end(self, event):
        """End panning; if left click without drag, treat as click."""
        if event.num == 1 and not self._drag_data["dragged"]:
            self.handle_canvas_click(event)
        self._drag_data["dragged"] = False

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
        label = tk.Label(
            tw,
            text=text,
            bg="#ffffe0",
            fg="black",
            bd=1,
            relief="solid",
            font=("Helvetica", 9),
        )
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
            self.canvas.create_text(
                x,
                y,
                text=sym,
                fill="black",
                font=("Helvetica", int(self.tile_size * 0.4), "bold"),
            )

    def draw_blocked(self, pos, tile):
        """Draw red X's for blocked directions."""
        x1 = pos[0] * self.tile_size + self.offset_x
        y1 = pos[1] * self.tile_size + self.offset_y
        x2 = x1 + self.tile_size
        y2 = y1 + self.tile_size
        # increase size of blocked-X markers
        half = int(self.tile_size * 0.1)
        coords = {
            "north": ((x1 + x2) / 2, y1 + half),
            "south": ((x1 + x2) / 2, y2 - half),
            "west": (x1 + half, (y1 + y2) / 2),
            "east": (x2 - half, (y1 + y2) / 2),
            "northwest": (x1 + half, y1 + half),
            "northeast": (x2 - half, y1 + half),
            "southwest": (x1 + half, y2 - half),
            "southeast": (x2 - half, y2 - half),
        }
        for d in tile.get("block_exit", []):
            if d in coords:
                cx, cy = coords[d]
                self.canvas.create_line(
                    cx - half, cy - half, cx + half, cy + half, fill="red", width=2
                )
                self.canvas.create_line(
                    cx + half, cy - half, cx - half, cy + half, fill="red", width=2
                )

    # --- Delete hotkey guard helpers ---
    def _collect_toplevel_windows(self):
        """Return list of open editor/property dialogs (Toplevels) excluding root and tooltip windows."""
        tops = []
        try:
            for widget in self.root.winfo_children():
                try:
                    if (
                        isinstance(widget, tk.Toplevel)
                        and widget is not self.root
                        and widget.winfo_exists()
                    ):
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
                self.set_status(
                    "Delete disabled: close open editor/property dialogs to delete tiles."
                )
                self._last_delete_block_msg = now
            return
        self.remove_selected_tile()

    # Coordinate helper methods (restored)
    def _update_mouse_coordinates(self, event=None):
        if not getattr(self, "coord_label", None) or not self.canvas:
            return
        try:
            px = self.root.winfo_pointerx()
            py = self.root.winfo_pointery()
            cx = self.canvas.winfo_rootx()
            cy = self.canvas.winfo_rooty()
            rel_x = px - cx
            rel_y = py - cy
            if (
                rel_x < 0
                or rel_y < 0
                or rel_x > self.canvas.winfo_width()
                or rel_y > self.canvas.winfo_height()
            ):
                self.coord_label.config(text=f"Tile (-,-)  px({rel_x},{rel_y})")
                return
            tile_x = int((rel_x - self.offset_x) // self.tile_size)
            tile_y = int((rel_y - self.offset_y) // self.tile_size)
            self.coord_label.config(
                text=f"Tile ({tile_x},{tile_y})  px({rel_x},{rel_y})"
            )
        except Exception:
            pass

    def _poll_mouse_position(self):
        try:
            self._update_mouse_coordinates()
            self.root.after(300, self._poll_mouse_position)
        except Exception:
            pass

