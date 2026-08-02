"""The single-tile property editor window (exits/blocked directions plus
Item/NPC/Object/Event tabs, each backed by a TagListFrame from
property_dialog.py)."""
import tkinter as tk
from tkinter import messagebox, ttk

from utils.mapgen.constants import DIRECTION_DELTAS
from utils.mapgen.property_dialog import create_element_frame, open_chooser, refresh_tags


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

        # Pre-compute adjacency directions. Uses the shared DIRECTION_DELTAS
        # order (north/south/west/east/...) -- previously this window had its
        # own copy with east and west swapped, which changed the Exits/Blocked
        # listbox display order relative to every other view in the editor.
        self._deltas = DIRECTION_DELTAS
        self.valid_directions = [
            d
            for d, (dx, dy) in self._deltas.items()
            if (self.pos[0] + dx, self.pos[1] + dy) in self.map_data
        ]
        # Purge stale exits / block_exit references with missing neighbors
        self.tile_data["exits"] = [
            d for d in self.tile_data.get("exits", []) if d in self.valid_directions
        ]
        self.tile_data["block_exit"] = [
            d
            for d in self.tile_data.get("block_exit", [])
            if d in self.valid_directions
        ]

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
        tk.Label(props_frame, text="Title:", bg="#34495e", fg="white").pack(
            anchor="w", pady=(0, 5)
        )
        self.title_entry = tk.Entry(props_frame, width=40, font=("Helvetica", 10))
        self.title_entry.insert(0, self.tile_data.get("title", ""))
        self.title_entry.pack(fill="x", pady=(0, 10))

        # Description
        tk.Label(props_frame, text="Description:", bg="#34495e", fg="white").pack(
            anchor="w", pady=(0, 5)
        )
        self.description_text = tk.Text(
            props_frame, height=4, width=40, font=("Helvetica", 10)
        )
        self.description_text.insert(tk.END, self.tile_data.get("description", ""))
        self.description_text.pack(fill="both", expand=True, pady=(0, 10))

        # Symbol
        tk.Label(props_frame, text="Symbol:", bg="#34495e", fg="white").pack(
            anchor="w", pady=(10, 5)
        )
        self.symbol_entry = tk.Entry(props_frame, width=10, font=("Helvetica", 12))
        self.symbol_entry.insert(0, self.tile_data.get("symbol", ""))
        self.symbol_entry.pack(anchor="w", pady=(0, 10))

        # --- Exits Tab ---
        exits_frame = tk.Frame(notebook, bg="#34495e", padx=10, pady=10)
        notebook.add(exits_frame, text="Exits")

        # Exits
        tk.Label(exits_frame, text="Exits:", bg="#34495e", fg="white").pack(
            anchor="w", pady=(0, 5)
        )
        frame_exits = tk.Frame(exits_frame)
        frame_exits.pack(fill="x", pady=(0, 10))
        self.exits_listbox = tk.Listbox(
            frame_exits, selectmode="multiple", height=8, exportselection=False
        )
        exits_sb = tk.Scrollbar(
            frame_exits, orient="vertical", command=self.exits_listbox.yview
        )
        exits_sb.pack(side="right", fill="y")
        self.exits_listbox.configure(yscrollcommand=exits_sb.set)
        for d in self.valid_directions:
            self.exits_listbox.insert("end", d)
            if d in self.tile_data.get("exits", []):
                # select existing exits
                self.exits_listbox.select_set("end")
        self.exits_listbox.pack(side="left", fill="x", expand=True)
        # Mark exits as modified only if user changes selection
        self.exits_listbox.bind(
            "<<ListboxSelect>>", lambda e: setattr(self, "_exits_modified", True)
        )

        # Directions blocked
        tk.Label(
            exits_frame, text="Directions Blocked:", bg="#34495e", fg="white"
        ).pack(anchor="w", pady=(10, 5))
        frame_dir = tk.Frame(exits_frame)
        frame_dir.pack(fill="x")
        self.directions_listbox = tk.Listbox(
            frame_dir, selectmode="multiple", height=8, exportselection=False
        )
        dir_sb = tk.Scrollbar(
            frame_dir, orient="vertical", command=self.directions_listbox.yview
        )
        dir_sb.pack(side="right", fill="y")
        self.directions_listbox.configure(yscrollcommand=dir_sb.set)
        self.directions_listbox.pack(side="left", fill="x", expand=True)
        for d in self.valid_directions:
            self.directions_listbox.insert("end", d)
            if d in self.tile_data.get("block_exit", []):
                self.directions_listbox.select_set("end")
        self.directions_listbox.bind(
            "<<ListboxSelect>>", lambda e: setattr(self, "_blocked_modified", True)
        )
        tk.Label(
            exits_frame,
            text="Only directions with adjacent tiles are shown.",
            font=("Helvetica", 8, "italic"),
            bg="#34495e",
            fg="#bdc3c7",
        ).pack(anchor="w", pady=(5, 0))

        # --- Items/NPCs/Objects/Events Tabs ---
        tab_configs = [
            ("Item", "Add Item", "items_frame", "items"),
            ("NPC", "Add NPC", "npcs_frame", "npcs"),
            ("Object", "Add Object", "objects_frame", "objects"),
            ("Event", "Add Event", "events_frame", "events"),
        ]

        for obj_class_name, btn_text, frame_attr, element_list_name in tab_configs:
            tab_frame = tk.Frame(notebook, bg="#34495e", padx=10, pady=10)
            notebook.add(tab_frame, text=f"{obj_class_name}s")
            create_element_frame(self.window, tab_frame, frame_attr, map_data=self.map_data)
            btn_cmd = lambda en=element_list_name, fa=frame_attr, this_baseclass_name=obj_class_name: open_chooser(
                self.window,
                self.tile_data[en],
                getattr(self.window, fa),
                this_baseclass_name,
                (this_baseclass_name == "Event"),
                map_data=self.map_data,
            )
            tk.Button(
                tab_frame,
                text=btn_text,
                command=btn_cmd,
                font=("Helvetica", 10, "bold"),
                bg="#3498db",
                fg="white",
            ).pack(fill="x", pady=(0, 10))

        # Save Button (outside notebook)
        save_button = tk.Button(
            main_frame,
            text="Save Changes",
            command=self.save_and_close,
            font=("Helvetica", 12, "bold"),
            bg="#2ecc71",
            fg="white",
        )
        save_button.pack(fill="x", pady=(10, 0))

        self.refresh_all_tags()

    def save_and_close(self):
        """Saves the edited properties back to the tile data and closes the window."""
        try:
            self.tile_data["title"] = self.title_entry.get().strip()
            self.tile_data["description"] = self.description_text.get(
                "1.0", tk.END
            ).strip()
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
                    new_blocked = [
                        self.directions_listbox.get(i) for i in selected_blocked
                    ]
                else:
                    new_blocked = list(self._initial_blocked)
            else:
                new_blocked = list(self._initial_blocked)
            # Enforce validity again (safety if map changed during edit)
            self.tile_data["exits"] = [
                d for d in new_exits if d in self.valid_directions
            ]
            self.tile_data["block_exit"] = [
                d for d in new_blocked if d in self.valid_directions
            ]
            self.tile_data["symbol"] = self.symbol_entry.get().strip()
            self.on_save_callback()
            self.window.destroy()
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Invalid input format. Please check your entries.\nDetails: {e}",
            )

    def refresh_all_tags(self):
        # Frames are attached to self.window (the Toplevel) via create_element_frame,
        # so we must retrieve them from self.window rather than self. Previously this
        # method looked up attributes on self, resulting in None frames and no initial
        # tag population (frames appeared empty / not shown).
        wnd = getattr(self, "window", None)
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

