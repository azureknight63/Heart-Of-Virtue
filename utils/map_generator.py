import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import glob
import ast
import inspect
import sys
import copy
import re
# Ensure the src directory is in sys.path for imports
project_root = os.path.dirname(os.path.dirname(__file__))
src_root = os.path.join(project_root, 'src')
if src_root not in sys.path:
    sys.path.insert(0, src_root)


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
        create_button("Load Legacy Map", lambda: (self.ensure_add_mode_off(), self.load_legacy_map()), controls_frame)
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
        self.draw_map()

    def remove_selected_tile(self):
        """
        Removes the currently selected tile from the map.
        """
        if self.selected_tile:
            x, y = self.selected_tile
            del self.map_data[self.selected_tile]
            self.selected_tile = None
            # Direction deltas
            deltas = {"north":(0,-1),"south":(0,1),"west":(-1,0),"east":(1,0),
                      "northeast":(1,-1),"northwest":(-1,-1),"southeast":(1,1),"southwest":(-1,1)}
            # Clean exits and block_exit references in all remaining tiles
            for pos_key, tile in self.map_data.items():
                def neighbor_exists(direction):
                    dx, dy = deltas[direction]
                    return (pos_key[0] + dx, pos_key[1] + dy) in self.map_data
                tile["exits"] = [d for d in tile.get("exits", []) if d in deltas and neighbor_exists(d)]
                tile["block_exit"] = [d for d in tile.get("block_exit", []) if d in deltas and neighbor_exists(d)]
            self.draw_map()
            self.set_status(f"Removed tile at ({x}, {y}).")
        else:
            self.set_status("No tile selected to remove.")

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
            def serialize_instance(inst):
                data = {k: v for k, v in vars(inst).items() if not k.startswith('_') and isinstance(v, (int,float,str,bool,list,dict,tuple))}
                return {
                    '__class__': inst.__class__.__name__,
                    '__module__': inst.__class__.__module__,
                    'props': data
                }
            serializable_map = {}
            for k, v in self.map_data.items():
                tile = dict(v)
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
                    if not isinstance(d, dict) or '__class__' not in d:
                        return d
                    cls_name = d.get('__class__')
                    mod_name = d.get('__module__')
                    props = d.get('props', {})
                    try:
                        module = __import__(mod_name, fromlist=[cls_name])
                        cls = getattr(module, cls_name)
                        # try instantiate with matching args
                        try:
                            param_names = [p.name for p in inspect.signature(cls.__init__).parameters.values() if p.name != 'self']
                            init_kwargs = {k: v for k, v in props.items() if k in param_names}
                            inst = cls(**init_kwargs)
                        except Exception:
                            inst = cls.__new__(cls)
                            try:
                                cls.__init__(inst)  # type: ignore
                            except Exception:
                                pass
                        for k2, v2 in props.items():
                            setattr(inst, k2, v2)
                        return inst
                    except Exception:
                        return props  # fallback raw
                self.map_data = {}
                for k, tile in data.items():
                    pos = tuple(int(x) for x in k.strip('()').split(','))
                    tile_copy = dict(tile)
                    for key in ['events','items','npcs','objects']:
                        tile_copy[key] = [deserialize_instance(d) for d in tile_copy.get(key, [])]
                    self.map_data[pos] = tile_copy
                self.current_map_filepath = filepath
                self.selected_tile = None
                self.draw_map()
                self.update_map_label()
                self.set_status(f"Map loaded from {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not load map file:\n{e}")
                self.set_status(f"Error loading map.")

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
            # dynamic class loader
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
                                # try no-arg object creation without init
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
                                # rMin-Max pattern
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
                            # Format: @TileDescription.<id>.<text~>
                            segs = part.split('.')
                            if len(segs) >= 3:
                                text = '.'.join(segs[2:])
                                if text.endswith('~'):
                                    text = text[:-1]
                                description = text.replace('~', '').strip()
                            continue
                        if part.startswith('#'):
                            # item token possibly with :count or :rA-B
                            body = part[1:]
                            name, count_spec = (body.split(':',1)+[None])[:2]
                            add_item(name, count_spec)
                            continue
                        # expand composite part containing mixed markers using '.'
                        if part.startswith('@'):
                            # Could contain embedded markers separated by '.'
                            subparts = part.split('.')
                            head = subparts[0]  # e.g. @WoodenChest
                            cls_name = head[1:]
                            # classify as object or npc by attempting instantiation in order
                            # We'll first try objects then npc
                            cls = load_class(cls_name)
                            inst = ensure_instance(cls) if cls else None
                            if inst:
                                # naive classification: if class name contains 'Chest' or 'Switch' -> objects
                                target = objects_list if any(k in cls_name.lower() for k in ['chest','switch','wall','inscription']) else npcs
                                target.append(inst)
                            # process remaining dotted subparts for embedded items/events (# / !)
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
                        # Plain base tile title
                        if tile_title is None:
                            tile_title = part
                    if tile_title is None:
                        tile_title = tile_id
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


# Helper frame to display tags with edit and remove capabilities
class TagListFrame(tk.Frame):
    def __init__(self, parent, on_edit, on_remove, on_duplicate=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_edit = on_edit
        self.on_remove = on_remove
        self.on_duplicate = on_duplicate
        self._tags = []  # list of (identifier, frame)
        self._tooltip = None  # tooltip window

    def _get_editable_properties(self, obj):
        props = []
        try:
            cls = obj.__class__
            sig = inspect.signature(cls.__init__)
            params = [p for p in sig.parameters.values() if p.name != 'self']
            excluded = {'player', 'tile'}
            editable = [p for p in params if p.name not in excluded]
            for p in editable:
                try:
                    val = getattr(obj, p.name)
                except Exception:
                    continue
                # represent value safely
                try:
                    rep = repr(val)
                except Exception:
                    rep = str(val)
                # truncate long representations
                if len(rep) > 80:
                    rep = rep[:77] + '...'
                props.append((p.name, rep))
        except Exception:
            pass
        return props

    def _show_tooltip(self, event, obj):
        # destroy existing
        self._hide_tooltip()
        # build text
        header = obj.__class__.__name__ if hasattr(obj, '__class__') else 'Object'
        lines = [header]
        props = self._get_editable_properties(obj)
        if props:
            for name, rep in props:
                lines.append(f"{name} = {rep}")
        else:
            lines.append('(No editable properties)')
        text = '\n'.join(lines)
        # create window
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

    def add_tag(self, identifier, text):
        frm = tk.Frame(self, bd=1, relief="solid", padx=4, pady=2)
        lbl = tk.Label(frm, text=text)
        lbl.pack(side="left")
        # Delete button packed first so it stays at far right
        del_btn = tk.Button(frm, text="×", command=lambda: self.remove(identifier), bd=0, padx=2, pady=0)
        del_btn.pack(side="right")
        # Duplicate button now appears to the right of label but left of delete (since packed after delete with side=right earlier logic reversed)
        if self.on_duplicate:
            dup_btn = tk.Button(frm, text="⧉", command=lambda: self.on_duplicate(identifier), bd=0, padx=2, pady=0)
            dup_btn.pack(side="right")
        frm.pack(side="left", padx=2, pady=2)
        frm.bind("<Double-Button-1>", lambda e: self.on_edit(identifier))
        lbl.bind("<Double-Button-1>", lambda e: self.on_edit(identifier))
        # Hover tooltips for properties
        self._bind_tooltip(frm, identifier)
        self._bind_tooltip(lbl, identifier)
        self._tags.append((identifier, frm))

    def remove(self, identifier):
        # Update underlying data via callback
        self.on_remove(identifier)
        # Remove only this tag's frame; do NOT clear all (prevents wiping others inadvertently)
        for i, (ident, frm) in enumerate(list(self._tags)):
            if ident is identifier:
                try:
                    frm.destroy()
                except Exception:
                    pass
                self._tags.pop(i)
                break
        # Ensure tooltip hidden if any
        self._hide_tooltip()
        # Caller may choose to refresh fully; if so duplicates won't cause UI inconsistency

    def clear(self):
        for _, frm in self._tags:
            frm.destroy()
        self._tags.clear()

    def get_all(self):
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
        # Purge stale exits / block_exit entries referencing missing neighbors
        self.tile_data["exits"] = [d for d in self.tile_data.get("exits", []) if d in self.valid_directions]
        self.tile_data["block_exit"] = [d for d in self.tile_data.get("block_exit", []) if d in self.valid_directions]

        self.window = tk.Toplevel(parent)
        self.window.title(f"Editing Tile: {self.tile_data['id']}")
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
        vsb.pack(side='right', fill='y')
        dialog_canvas.pack(side='left', fill='both', expand=True)
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
        for d in self.valid_directions:
            self.exits_listbox.insert("end", d)
            if d in self.tile_data.get("exits", []):
                self.exits_listbox.select_set("end")
        self.exits_listbox.pack(side="left", fill="x", expand=True, pady=(0, 10))
        exits_sb.pack(side="right", fill="y")
        tk.Label(main_frame, text="Only directions with adjacent tiles are shown.", font=("Helvetica", 8, "italic"), bg="#34495e", fg="#bdc3c7").pack(anchor="w")

        # Events
        tk.Label(main_frame, text="Events:", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        self.events_frame = TagListFrame(main_frame, self.edit_event, self.remove_event)
        self.events_frame.pack(fill="x", pady=(0, 10))
        tk.Button(main_frame, text="Add Event", command=self.open_event_chooser,
                  font=("Helvetica", 10, "bold"), bg="#3498db", fg="white").pack(fill="x", pady=(0, 10))

        # Items
        tk.Label(main_frame, text="Items:", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        self.items_frame = TagListFrame(main_frame, self.edit_item, self.remove_item, self.duplicate_item)
        self.items_frame.pack(fill="x", pady=(0, 10))
        tk.Button(main_frame, text="Add Item", command=self.open_item_chooser,
                  font=("Helvetica", 10, "bold"), bg="#3498db", fg="white").pack(fill="x", pady=(0, 10))

        # NPCs
        tk.Label(main_frame, text="NPCs:", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        self.npcs_frame = TagListFrame(main_frame, self.edit_npc, self.remove_npc, self.duplicate_npc)
        self.npcs_frame.pack(fill="x", pady=(0, 10))
        tk.Button(main_frame, text="Add NPC", command=self.open_npc_chooser,
                  font=("Helvetica", 10, "bold"), bg="#3498db", fg="white").pack(fill="x", pady=(0, 10))

        # Objects
        tk.Label(main_frame, text="Objects:", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        self.objects_frame = TagListFrame(main_frame, self.edit_object, self.remove_object, self.duplicate_object)
        self.objects_frame.pack(fill="x", pady=(0, 10))
        tk.Button(main_frame, text="Add Object", command=self.open_object_chooser,
                  font=("Helvetica", 10, "bold"), bg="#3498db", fg="white").pack(fill="x", pady=(0, 10))

        # Directions blocked
        tk.Label(main_frame, text="Directions Blocked:", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        frame_dir = tk.Frame(main_frame)
        frame_dir.pack(fill="x")
        self.directions_listbox = tk.Listbox(frame_dir, selectmode="multiple", height=6)
        dir_sb = tk.Scrollbar(frame_dir, orient="vertical", command=self.directions_listbox.yview)
        self.directions_listbox.configure(yscrollcommand=dir_sb.set)
        self.directions_listbox.pack(side="left", fill="x", expand=True)
        dir_sb.pack(side="right", fill="y")
        for d in self.valid_directions:
            self.directions_listbox.insert("end", d)
            if d in self.tile_data.get("block_exit", []):
                self.directions_listbox.select_set("end")
        tk.Label(main_frame, text="Only directions with adjacent tiles are shown.", font=("Helvetica", 8, "italic"), bg="#34495e", fg="#bdc3c7").pack(anchor="w")
        # Symbol
        tk.Label(main_frame, text="Symbol:", bg="#34495e", fg="white").pack(anchor="w", pady=(10, 5))
        self.symbol_entry = tk.Entry(main_frame, width=10, font=("Helvetica", 12))
        self.symbol_entry.insert(0, self.tile_data.get("symbol", ""))
        self.symbol_entry.pack(anchor="w", pady=(0, 10))

        # Save Button
        save_button = tk.Button(main_frame, text="Save Changes", command=self.save_and_close,
                                font=("Helvetica", 12, "bold"), bg="#2ecc71", fg="white")
        save_button.pack(fill="x", pady=(20, 0))

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
        src_root = os.path.join(project_root, 'src')
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
                import_mod = 'src.' + import_mod
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
        lb._items = []  # parallel list of {'name': class_name, 'module': import_mod}
        # helper to decide if subtree matches filter
        def update_list(*args):
            search = filter_var.get().lower().strip()
            lb.delete(0, tk.END)
            lb._items.clear()
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
                        lb._items.append({'name': n, 'module': info['module']})
                        # recurse children
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
            meta = lb._items[idx]
            cls_name = meta['name']
            import_module = meta['module']
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
        dlg.geometry('900x450')  # triple width
        dlg.transient(self.window)
        dlg.grab_set()
        entries = {}  # name -> {'type': 'text'|'bool', 'get': callable}
        sig = inspect.signature(cls.__init__)
        params = [p for p in sig.parameters.values() if p.name != 'self']
        excluded_names = {'player', 'tile'}
        editable_params = [p for p in params if p.name not in excluded_names]
        excluded_params = [p for p in params if p.name in excluded_names]
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
                    entries[p.name] = {'type': 'text', 'get': lambda e=ent: e.get().strip()}
            for i in range(col_count):
                frm.grid_columnconfigure(i, weight=1)
        else:
            tk.Label(frm, text="No editable properties.", bg="#34495e", fg="#ecf0f1", font=("Helvetica", 12, "italic")).pack(pady=20)
        def on_add_save():
            kwargs = {}
            for name, meta in entries.items():
                if meta['type'] == 'bool':
                    kwargs[name] = meta['get']()
                else:
                    raw = meta['get']()
                    if raw == '':
                        continue
                    try:
                        kwargs[name] = eval(raw)
                    except Exception:
                        kwargs[name] = raw
            if existing:
                for k, v in kwargs.items():
                    setattr(existing, k, v)
                inst = existing
            else:
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
        tk.Button(btn_frame, text=("Save" if existing else "Add"), command=on_add_save,
                  bg="#2ecc71", fg="white").pack(side='right')

    def edit_event(self, inst):
        def cb(res):
            if res is None:
                self.tile_data['events'].remove(inst)
            self._refresh_tags('events', self.events_frame)
        self._open_property_dialog(inst.__class__, existing=inst, callback=cb)

    def remove_event(self, inst):
        self.tile_data['events'].remove(inst)
        self._refresh_tags('events', self.events_frame)

    def edit_item(self, inst):
        def cb(res):
            if res is None:
                self.tile_data['items'].remove(inst)
            self._refresh_tags('items', self.items_frame)
        self._open_property_dialog(inst.__class__, existing=inst, callback=cb)
    def remove_item(self, inst):
        self.tile_data['items'].remove(inst)
        self._refresh_tags('items', self.items_frame)
    def edit_npc(self, inst):
        def cb(res):
            if res is None:
                self.tile_data['npcs'].remove(inst)
            self._refresh_tags('npcs', self.npcs_frame)
        self._open_property_dialog(inst.__class__, existing=inst, callback=cb)
    def remove_npc(self, inst):
        self.tile_data['npcs'].remove(inst)
        self._refresh_tags('npcs', self.npcs_frame)
    def edit_object(self, inst):
        def cb(res):
            if res is None:
                self.tile_data['objects'].remove(inst)
            self._refresh_tags('objects', self.objects_frame)
        self._open_property_dialog(inst.__class__, existing=inst, callback=cb)
    def remove_object(self, inst):
        self.tile_data['objects'].remove(inst)
        self._refresh_tags('objects', self.objects_frame)


if __name__ == "__main__":
    root = tk.Tk()
    app = MapEditor(root)
    root.mainloop()
