import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import glob
import ast


def create_button(text, command, parent):
    """
    Helper function to create styled buttons.
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

        # --- UI Elements ---
        self.create_widgets()
        self.draw_map()
        # Tooltip widget for showing full titles
        self.tooltip = None
        # Attempt to load most recently saved map
        last_map = _get_last_map_file()
        if last_map:
            self.load_map(last_map)

    def create_widgets(self):
        """
        Creates all the GUI widgets for the application.
        """
        # Main Frame for UI controls
        controls_frame = tk.Frame(self.root, bg="#34495e", padx=10, pady=10)
        controls_frame.pack(side="left", fill="y")

        # Map Canvas
        self.canvas = tk.Canvas(self.root, bg="#ecf0f1", width=800, height=800, relief="sunken", bd=2)
        self.canvas.pack(side="right", expand=True, fill="both", padx=10, pady=10)
        # Pan canvas and handle clicks
        self.canvas.bind("<ButtonPress-1>", self.on_pan_start)
        self.canvas.bind("<B1-Motion>", self.on_pan_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_pan_end)
        # Double-click on a tile to edit it directly
        self.canvas.bind("<Double-Button-1>", self.handle_canvas_double_click)
        # Press Enter to edit currently selected tile
        self.root.bind("<Return>", self.handle_enter_key)
        # Zoom with Ctrl + scroll
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom)

        # --- Control Buttons ---
        create_button("New Map", lambda: (self.ensure_add_mode_off(), self.create_new_map()), controls_frame)
        create_button("Load Map", lambda: (self.ensure_add_mode_off(), self.load_map()), controls_frame)
        create_button("Save Map", lambda: (self.ensure_add_mode_off(), self.save_map()), controls_frame)
        create_separator(controls_frame)

        create_button("Add Tile", self.toggle_add_tile_mode, controls_frame)
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

    def handle_canvas_click(self, event):
        """
        Handles clicks on the canvas to select or add tiles.
        """
        # adjust for pan offsets
        x = (event.x - self.offset_x) // self.tile_size
        y = (event.y - self.offset_y) // self.tile_size
        clicked_pos = (x, y)

        if self.is_adding_tile:
            # Add a new tile if in add mode
            if clicked_pos not in self.map_data:
                self.add_tile(x, y)
                self.set_status(f"Added new tile at ({x}, {y}). Click to add another or press 'Add Tile' again to exit mode.")
            else:
                self.set_status(f"Tile already exists at ({x}, {y}).")
            # Do not automatically exit add mode; user must toggle it off explicitly
        else:
            # Select an existing tile
            if clicked_pos in self.map_data:
                self.select_tile(clicked_pos)
                self.set_status(f"Selected tile at ({x}, {y})")
            else:
                self.select_tile(None)
                self.set_status("No tile selected.")

        self.draw_map()

    def create_new_map(self):
        """
        Clears the current map data to start a new map.
        """
        self.map_data = {}
        self.selected_tile = None
        self.draw_map()
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
        self.draw_map()

    def remove_selected_tile(self):
        """
        Removes the currently selected tile from the map.
        """
        if self.selected_tile:
            x, y = self.selected_tile
            del self.map_data[self.selected_tile]
            self.selected_tile = None

            # Also remove any exits that lead to this tile
            # Also remove any exit directions pointing to this removed tile
            deltas = {"north":(0,-1),"south":(0,1),"west":(-1,0),"east":(1,0),
                      "northeast":(1,-1),"northwest":(-1,-1),"southeast":(1,1),"southwest":(-1,1)}
            for pos_key, tile in self.map_data.items():
                # keep directions whose neighbor isn't the removed tile
                tile["exits"] = [d for d in tile.get("exits", [])
                                   if (pos_key[0] + deltas[d][0], pos_key[1] + deltas[d][1]) != (x, y)]

            self.draw_map()
            self.set_status(f"Removed tile at ({x}, {y}).")
        else:
            self.set_status("No tile selected to remove.")

    def edit_selected_tile(self):
        """
        Opens a new window to edit the properties of the selected tile.
        """
        if self.selected_tile:
            TileEditorWindow(self.root, self.map_data[self.selected_tile], self.draw_map)
        else:
            self.set_status("No tile selected to edit.")

    def toggle_add_tile_mode(self):
        """
        Toggles the add tile mode.
        """
        self.is_adding_tile = not self.is_adding_tile
        if self.is_adding_tile:
            self.set_status("Click on the canvas to add a new tile.")
            self.select_tile(None)
        else:
            self.set_status("Add tile mode off.")

    def select_tile(self, pos):
        """
        Sets the currently selected tile.
        """
        self.selected_tile = pos
        self.draw_map()

    def auto_connect_exits(self):
        """
        Automatically creates exits between adjacent tiles.
        """
        # Clear all existing exits
        for tile in self.map_data.values():
            tile["exits"] = []
        # Direction deltas and reciprocal mapping
        deltas = {"north":(0,-1),"south":(0,1),"west":(-1,0),"east":(1,0),
                  "northeast":(1,-1),"northwest":(-1,-1),"southeast":(1,1),"southwest":(-1,1)}
        reciprocal = {"north":"south","south":"north","west":"east","east":"west",
                      "northeast":"southwest","northwest":"southeast",
                      "southeast":"northwest","southwest":"northeast"}
        # Build new exits lists
        for pos, tile in self.map_data.items():
            x, y = pos
            for direction, (dx, dy) in deltas.items():
                nbr = (x+dx, y+dy)
                if nbr in self.map_data:
                    if direction not in tile["exits"]:
                        tile["exits"].append(direction)
                    # reciprocal
                    rev = reciprocal[direction]
                    if rev not in self.map_data[nbr]["exits"]:
                        self.map_data[nbr]["exits"].append(rev)

        self.draw_map()
        self.set_status("Exits automatically connected.")

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
        text_id = self.canvas.create_text(
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
        # direction deltas and reciprocal mapping
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
                # detect bidirectional
                bidir = reciprocal.get(direction) in self.map_data[target_pos].get("exits", [])
                arrow_style = tk.BOTH if bidir else tk.LAST
                self.canvas.create_line(x_center, y_center, x_target, y_target,
                                        arrow=arrow_style, fill="#2c3e50", width=2)

    def save_map(self):
        """
        Saves the current map data to a JSON file.
        """
        try:
            # A dictionary with string keys is needed for JSON serialization
            serializable_map = {str(k): v for k, v in self.map_data.items()}

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
                    # Convert string keys back to tuples
                    self.map_data = {tuple(int(x) for x in k.strip('()').split(',')): v for k, v in data.items()}
                    self.selected_tile = None
                    self.draw_map()
                    self.set_status(f"Map loaded from {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not load map file:\n{e}")
                self.set_status(f"Error loading map.")

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
        """End panning; if click without drag, treat as click."""
        if not self._drag_data['dragged']:
            self.handle_canvas_click(event)
        # reset drag flag
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
        x = (event.x - self.offset_x) // self.tile_size
        y = (event.y - self.offset_y) // self.tile_size
        pos = (x, y)
        if pos in self.map_data:
            # ensure add mode is off and select tile before editing
            self.ensure_add_mode_off()
            self.select_tile(pos)
            self.edit_selected_tile()

    def handle_enter_key(self):
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


def find_all_classes(tree):
    """Recursively find all class names in an AST tree."""
    class_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_names.append(node.name)
    return class_names


def find_class_hierarchy(tree):
    """Return roots and children mapping for class inheritance within one module."""
    class_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    names = {n.name: n for n in class_nodes}
    children = {name: [] for name in names}
    for n in class_nodes:
        for base in n.bases:
            if isinstance(base, ast.Name) and base.id in names:
                children[base.id].append(n.name)
    roots = [n.name for n in class_nodes
             if not any(isinstance(b, ast.Name) and b.id in names for b in n.bases)]
    return roots, children


class TileEditorWindow:
    """
    A separate window for editing a single tile's properties.
    """

    def __init__(self, parent, tile_data, on_save_callback):
        """
        Initializes the tile editor window.
        """
        self.tile_data = tile_data
        self.on_save_callback = on_save_callback

        self.window = tk.Toplevel(parent)
        self.window.title(f"Editing Tile: {tile_data['id']}")
        self.window.geometry("400x650")
        self.window.configure(bg="#34495e")
        self.window.grab_set()  # Make window modal

        # Pre-declare widget attributes
        self.title_entry = None
        self.description_text = None
        self.exits_text = None
        self.events_entry = None
        self.items_entry = None
        self.npcs_entry = None
        self.objects_entry = None
        self.directions_listbox = None
        self.symbol_entry = None
        self.exits_listbox = None

        # --- UI Elements ---
        self.create_widgets()

    def create_widgets(self):
        """
        Creates all the GUI widgets for the tile editor.
        """
        # add scrollable area for full dialog
        container = tk.Frame(self.window)
        container.pack(fill="both", expand=True)
        dialog_canvas = tk.Canvas(container, bg="#34495e", highlightthickness=0)
        vsb = tk.Scrollbar(container, orient="vertical", command=dialog_canvas.yview)
        dialog_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        dialog_canvas.pack(side="left", fill="both", expand=True)
        main_frame = tk.Frame(dialog_canvas, bg="#34495e", padx=10, pady=10)
        dialog_canvas.create_window((0,0), window=main_frame, anchor="nw")
        main_frame.bind("<Configure>", lambda e: dialog_canvas.configure(scrollregion=dialog_canvas.bbox("all")))

        # Title
        tk.Label(main_frame, text="Title:", bg="#34495e", fg="white").pack(anchor="w", pady=(0, 5))
        self.title_entry = tk.Entry(main_frame, width=40, font=("Helvetica", 10))
        self.title_entry.insert(0, self.tile_data.get("title", ""))
        self.title_entry.pack(fill="x", pady=(0, 10))

        # Description
        tk.Label(main_frame, text="Description:", bg="#34495e", fg="white").pack(anchor="w", pady=(0, 5))
        self.description_text = tk.Text(main_frame, height=4, width=40, font=("Helvetica", 10))
        self.description_text.insert(tk.END, self.tile_data.get("description", ""))
        self.description_text.pack(fill="x", pady=(0, 10))

        # Exits
        tk.Label(main_frame, text="Exits:", bg="#34495e", fg="white").pack(anchor="w", pady=(0, 5))
        frame_exits = tk.Frame(main_frame)
        frame_exits.pack(fill="x")
        self.exits_listbox = tk.Listbox(frame_exits, selectmode="multiple", height=6)
        exits_sb = tk.Scrollbar(frame_exits, orient="vertical", command=self.exits_listbox.yview)
        self.exits_listbox.configure(yscrollcommand=exits_sb.set)
        directions = ["north","south","east","west","northeast","northwest","southeast","southwest"]
        for d in directions:
            self.exits_listbox.insert("end", d)
            if d in self.tile_data.get("exits", []):
                self.exits_listbox.select_set("end")
        self.exits_listbox.pack(side="left", fill="x", expand=True, pady=(0, 10))
        exits_sb.pack(side="right", fill="y")
        tk.Label(main_frame, text="Select directions for exits.", font=("Helvetica", 8, "italic"), bg="#34495e", fg="#bdc3c7").pack(anchor="w")

        # Other Properties (as single-line entries)
        tk.Label(main_frame, text="Events (comma-separated):", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        self.events_entry = tk.Entry(main_frame, width=40, font=("Helvetica", 10))
        self.events_entry.insert(0, ", ".join(self.tile_data.get("events", [])))
        self.events_entry.pack(fill="x")

        choose_btn = tk.Button(main_frame, text="Choose Event", command=self.open_event_chooser,
                               font=("Helvetica", 10, "bold"), bg="#3498db", fg="white")
        choose_btn.pack(fill="x", pady=(0, 10))

        tk.Label(main_frame, text="Items (comma-separated):", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        self.items_entry = tk.Entry(main_frame, width=40, font=("Helvetica", 10))
        self.items_entry.insert(0, ", ".join(self.tile_data.get("items", [])))
        self.items_entry.pack(fill="x", pady=(0, 10))
        choose_item_btn = tk.Button(main_frame, text="Choose Item", command=self.open_item_chooser,
                                   font=("Helvetica", 10, "bold"), bg="#3498db", fg="white")
        choose_item_btn.pack(fill="x", pady=(0, 10))

        tk.Label(main_frame, text="NPCs (comma-separated):", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        self.npcs_entry = tk.Entry(main_frame, width=40, font=("Helvetica", 10))
        self.npcs_entry.insert(0, ", ".join(self.tile_data.get("npcs", [])))
        self.npcs_entry.pack(fill="x", pady=(0, 10))
        choose_npc_btn = tk.Button(main_frame, text="Choose NPC", command=self.open_npc_chooser,
                                 font=("Helvetica", 10, "bold"), bg="#3498db", fg="white")
        choose_npc_btn.pack(fill="x", pady=(0, 10))
        # Objects
        tk.Label(main_frame, text="Objects (comma-separated):", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        self.objects_entry = tk.Entry(main_frame, width=40, font=("Helvetica", 10))
        self.objects_entry.insert(0, ", ".join(self.tile_data.get("objects", [])))
        self.objects_entry.pack(fill="x", pady=(0, 10))
        choose_obj_btn = tk.Button(main_frame, text="Choose Object", command=self.open_object_chooser,
                                  font=("Helvetica", 10, "bold"), bg="#3498db", fg="white")
        choose_obj_btn.pack(fill="x", pady=(0, 10))
        # Directions blocked
        tk.Label(main_frame, text="Directions Blocked:", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        frame_dir = tk.Frame(main_frame)
        frame_dir.pack(fill="x")
        self.directions_listbox = tk.Listbox(frame_dir, selectmode="multiple", height=6)
        dir_sb = tk.Scrollbar(frame_dir, orient="vertical", command=self.directions_listbox.yview)
        self.directions_listbox.configure(yscrollcommand=dir_sb.set)
        self.directions_listbox.pack(side="left", fill="x", expand=True)
        dir_sb.pack(side="right", fill="y")
        directions = ["north","south","east","west","northeast","northwest","southeast","southwest"]
        for d in directions:
            self.directions_listbox.insert("end", d)
            if d in self.tile_data.get("block_exit", []):
                self.directions_listbox.select_set("end")
        # Symbol
        tk.Label(main_frame, text="Symbol:", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        self.symbol_entry = tk.Entry(main_frame, width=10, font=("Helvetica", 12))
        self.symbol_entry.insert(0, self.tile_data.get("symbol", ""))
        self.symbol_entry.pack(anchor="w", pady=(0, 10))

        # Save Button
        save_button = tk.Button(main_frame, text="Save Changes", command=self.save_and_close,
                                font=("Helvetica", 12, "bold"), bg="#2ecc71", fg="white")
        save_button.pack(fill="x", pady=(20, 0))

    def open_event_chooser(self):
        """
        Opens a dialog listing classes from story modules to choose as events.
        """
        # Determine story directory relative to this script file
        project_root = os.path.dirname(os.path.dirname(__file__))
        story_dir = os.path.join(project_root, 'src', 'story')

        classes_by_module = {}
        for fname in os.listdir(story_dir):
            if fname.endswith('.py') and not fname.startswith('__'):
                mod = fname[:-3]
                path = os.path.join(story_dir, fname)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                    cls_names = find_all_classes(tree)
                    # include module even if it has no classes
                    classes_by_module[mod] = cls_names
                except Exception:
                    continue
        dlg = tk.Toplevel(self.window)
        dlg.title("Choose Event")
        dlg.geometry('300x400')
        dlg.transient(self.window)
        dlg.grab_set()
        # Filter entry
        filter_frame = tk.Frame(dlg)
        filter_frame.pack(fill='x', padx=5, pady=5)
        tk.Label(filter_frame, text='Filter:', anchor='w').pack(side='left')
        filter_var = tk.StringVar()
        filter_entry = tk.Entry(filter_frame, textvariable=filter_var)
        filter_entry.pack(side='left', fill='x', expand=True)

        frame = tk.Frame(dlg)
        frame.pack(fill='both', expand=True)
        lb = tk.Listbox(frame)
        sb = tk.Scrollbar(frame, orient='vertical', command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        lb.pack(side='left', fill='both', expand=True)

        # Function to update listbox based on filter
        def update_listbox(*args):
            search = filter_var.get().lower()
            lb.delete(0, tk.END)
            for mod in sorted(classes_by_module):
                mod_match = search in mod.lower()
                matched = [c for c in classes_by_module[mod] if search in c.lower()]
                if mod_match or matched:
                    lb.insert('end', f"[{mod}]")
                    for cname in (classes_by_module[mod] if mod_match else matched):
                        lb.insert('end', f"  {cname}")

        # Bind filter updates and populate initial list
        filter_var.trace_add('write', update_listbox)
        update_listbox()

        def on_double(event):
            sel = lb.get(lb.curselection())
            if sel.startswith('  '):
                classname = sel.strip()
                current = [e.strip() for e in self.events_entry.get().split(',') if e.strip()]
                if classname not in current:
                    current.append(classname)
                    self.events_entry.delete(0, tk.END)
                    self.events_entry.insert(0, ', '.join(current))
                dlg.destroy()
        lb.bind('<Double-Button-1>', on_double)

    def _show_hierarchy_chooser(self, module_path, dialog_title, entry_widget):
        # parse module and build class hierarchy
        try:
            with open(module_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
        except Exception as e:
            messagebox.showerror("Error", f"Could not load module {module_path}:\n{e}")
            return
        roots, children = find_class_hierarchy(tree)
        dlg = tk.Toplevel(self.window)
        dlg.title(dialog_title)
        dlg.geometry('300x400')
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
        # populate based on filter
        def update_list(*args):
            search = filter_var.get().lower()
            lb.delete(0, tk.END)
            def match(name):
                if search in name.lower(): return True
                return any(match(c) for c in children.get(name, []))
            def recurse(names, indent=0):
                for n in sorted(names):
                    if match(n):
                        lb.insert('end', '  '*indent + n)
                        recurse(children.get(n, []), indent+1)
            recurse(roots)
        filter_var.trace_add('write', update_list)
        update_list()
        # double-click adds to entry
        def on_double(e):
            sel = lb.get(lb.curselection()).strip()
            current = [i.strip() for i in entry_widget.get().split(',') if i.strip()]
            if sel not in current:
                current.append(sel)
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, ', '.join(current))
            dlg.destroy()
        lb.bind('<Double-Button-1>', on_double)

    def open_item_chooser(self):
        """Chooser for item classes with hierarchy."""
        project_root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(project_root, 'src', 'items.py')
        self._show_hierarchy_chooser(path, "Choose Item", self.items_entry)

    def open_npc_chooser(self):
        """Chooser for NPC classes with hierarchy."""
        project_root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(project_root, 'src', 'npc.py')
        self._show_hierarchy_chooser(path, "Choose NPC", self.npcs_entry)

    def open_object_chooser(self):
        """Chooser for object classes with hierarchy."""
        project_root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(project_root, 'src', 'objects.py')
        self._show_hierarchy_chooser(path, "Choose Object", self.objects_entry)

    def save_and_close(self):
        """
        Saves the edited properties back to the tile data and closes the window.
        """
        try:
            # Update title
            self.tile_data["title"] = self.title_entry.get().strip()

            # Update description
            self.tile_data["description"] = self.description_text.get("1.0", tk.END).strip()

            # Update exits list
            sel = self.exits_listbox.curselection()
            self.tile_data["exits"] = [self.exits_listbox.get(i) for i in sel]

            # Update other lists
            self.tile_data["events"] = [item.strip() for item in self.events_entry.get().split(",") if item.strip()]
            self.tile_data["items"] = [item.strip() for item in self.items_entry.get().split(",") if item.strip()]
            self.tile_data["npcs"] = [item.strip() for item in self.npcs_entry.get().split(",") if item.strip()]
            # Update objects
            self.tile_data["objects"] = [item.strip() for item in self.objects_entry.get().split(",") if item.strip()]
            # Update blocked directions
            selected = self.directions_listbox.curselection()
            self.tile_data["block_exit"] = [self.directions_listbox.get(i) for i in selected]
            # Update symbol
            self.tile_data["symbol"] = self.symbol_entry.get().strip()

            # Callback to redraw the main map with the new data
            self.on_save_callback()
            self.window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input format. Please check your entries.\nDetails: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = MapEditor(root)
    root.mainloop()
