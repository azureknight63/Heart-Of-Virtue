"""Generic Tkinter widget builders and property-dialog field metadata:
plain button/separator/entry helpers, the (currently unused --
create_hierarchical_selector/get_class_hierarchy have no remaining callers,
kept as-is rather than deleted as part of an unrelated package split)
hierarchical class selector, and the property-description/grouping/layout
logic used by open_property_dialog.
"""
import inspect
import tkinter as tk
from collections import OrderedDict
from tkinter import messagebox, ttk
from typing import Any, Dict, List

from utils.mapgen.class_discovery import get_class_hierarchy


def create_hierarchical_selector(
    parent, base_class, is_list=False, current_values=None, on_change_callback=None
):
    """
    Create a hierarchical selector widget for choosing classes.
    Returns a widget that manages selection of class instances.
    """
    container = tk.Frame(parent, bg="#34495e")

    # Get available classes
    class_hierarchy = get_class_hierarchy(base_class)

    if not class_hierarchy:
        tk.Label(
            container,
            text=f"No {base_class.__name__} classes found",
            font=("Helvetica", 9, "italic"),
            bg="#34495e",
            fg="#f39c12",
        ).pack(fill="x")
        return container, lambda: []

    selected_items = []

    if is_list:
        # Multi-selection for list types
        list_frame = tk.Frame(container, bg="#34495e")
        list_frame.pack(fill="both", expand=True, pady=(0, 5))

        # Listbox to show selected items
        listbox_frame = tk.Frame(list_frame, bg="#34495e")
        listbox_frame.pack(fill="both", expand=True)

        selected_listbox = tk.Listbox(
            listbox_frame,
            height=8,
            bg="#2c3e50",
            fg="white",
            selectbackground="#3498db",
        )
        selected_listbox.pack(fill="both", expand=True, side="left")

        # Scrollbar for listbox
        scrollbar = tk.Scrollbar(
            listbox_frame, orient="vertical", command=selected_listbox.yview
        )
        scrollbar.pack(side="right", fill="y")
        selected_listbox.config(yscrollcommand=scrollbar.set)

        # Dropdown to add new items
        add_frame = tk.Frame(container, bg="#34495e")
        add_frame.pack(fill="x", pady=(5, 0))

        tk.Label(
            add_frame, text=f"Add {base_class.__name__}:", bg="#34495e", fg="white"
        ).pack(anchor="w")

        class_var = tk.StringVar()
        class_combo = ttk.Combobox(
            add_frame,
            textvariable=class_var,
            values=list(class_hierarchy.keys()),
            state="readonly",
        )
        class_combo.pack(fill="x", pady=(2, 5))

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
                        if param.name in ["self", "player", "tile"]:
                            continue
                        if param.default is not inspect._empty:
                            continue
                        # Add default values for required parameters
                        if param.annotation == str or param.name in [
                            "name",
                            "description",
                        ]:
                            kwargs[param.name] = f"Default {class_name}"
                        elif param.annotation == int:
                            kwargs[param.name] = 0
                        elif param.annotation == float:
                            kwargs[param.name] = 0.0
                        elif param.annotation == bool:
                            kwargs[param.name] = False

                    instance = cls(**kwargs)
                    selected_items.append(instance)
                    selected_listbox.insert(
                        tk.END,
                        f"{class_name}: {getattr(instance, 'name', str(instance))}",
                    )
                    class_var.set("")

                    if on_change_callback:
                        on_change_callback()

                except Exception as e:
                    messagebox.showerror(
                        "Error", f"Failed to create {class_name}: {str(e)}"
                    )

        tk.Button(
            add_frame, text="Add", command=add_selected, bg="#27ae60", fg="white"
        ).pack(fill="x")

        def remove_selected():
            selection = selected_listbox.curselection()
            if selection:
                index = selection[0]
                selected_listbox.delete(index)
                if index < len(selected_items):
                    selected_items.pop(index)
                if on_change_callback:
                    on_change_callback()

        tk.Button(
            add_frame,
            text="Remove Selected",
            command=remove_selected,
            bg="#e74c3c",
            fg="white",
        ).pack(fill="x", pady=(2, 0))

        # Initialize with current values
        if current_values:
            for item in current_values:
                if item:
                    selected_items.append(item)
                    class_name = item.__class__.__name__
                    selected_listbox.insert(
                        tk.END, f"{class_name}: {getattr(item, 'name', str(item))}"
                    )

        def get_values():
            return selected_items.copy()

    else:
        # Single selection for non-list types
        tk.Label(
            container, text=f"Select {base_class.__name__}:", bg="#34495e", fg="white"
        ).pack(anchor="w")

        class_var = tk.StringVar()
        class_combo = ttk.Combobox(
            container,
            textvariable=class_var,
            values=["None"] + list(class_hierarchy.keys()),
            state="readonly",
        )
        class_combo.pack(fill="x")

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
                        if param.name in ["self", "player", "tile"]:
                            continue
                        if param.default is not inspect._empty:
                            continue
                        # Add default values for required parameters
                        if param.annotation == str or param.name in [
                            "name",
                            "description",
                        ]:
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
                    messagebox.showerror(
                        "Error", f"Failed to create {class_name}: {str(e)}"
                    )
                    current_instance = None

        class_combo.bind("<<ComboboxSelected>>", on_selection_change)

        # Initialize with current value
        if current_values:
            if hasattr(current_values, "__class__"):
                class_var.set(current_values.__class__.__name__)
                current_instance = current_values
            else:
                class_var.set("None")
        else:
            class_var.set("None")

        def get_values():
            return current_instance

    container.pack(fill="x")
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
        width=20,
    )
    button.pack(fill="x", pady=5)
    return button


def create_separator(parent):
    """
    Helper function to create a visual separator.
    """
    separator = tk.Frame(parent, height=2, bg="#5d6d7e")
    separator.pack(fill="x", pady=10)


# Human-readable descriptions for property names that recur across many
# classes (issue #16's "display tooltips for each property" ask). Scoped to
# the common/generic names shared by most Object/Event/NPC __init__
# signatures -- there's no per-class documentation source to draw a
# comprehensive mapping from, so names not covered here fall back to a
# generic message rather than silently having no tooltip at all.
_PROPERTY_DESCRIPTIONS: Dict[str, str] = {
    "name": "Display name shown to the player.",
    "description": "Prose shown when the player examines/interacts with this.",
    "idle_message": "Short line shown when the player is on the same tile, before interacting.",
    "discovery_message": "Line shown the first time the player notices/reveals this.",
    "hidden": "Whether this starts concealed until discovered (see hide_factor).",
    "hide_factor": "How hard this is to notice while hidden (higher = harder to find).",
    "locked": "Whether this starts locked and needs a key/unlock action.",
    "start_open": "Whether a container starts already open.",
    "nickname": "Short internal name used in player-facing messages (e.g. 'the container').",
    "inventory": "Items contained inside (the canonical items list).",
    "keywords": "Words the player can type/click to interact with this.",
    "repeat": "Whether this event can fire more than once.",
    "check_conditions": "Extra logic gating whether this event is eligible to fire.",
    "teleport_map": "Map file this passage leads to.",
    "teleport_tile": "Coordinate on the destination map the player arrives at.",
    "target_map_name": "Map file this coordinate field refers to.",
    "target_coordinates": "Coordinate on the referenced map.",
    "merchant": "The Merchant NPC that stocks/prices this shop's inventory.",
    "allowed_subtypes": "Item base classes this can hold/generate (restricts random stock).",
    "stock_count": "Maximum number of items this should carry (used for shop restocking).",
    "events": "Events attached to this that can trigger on interaction/entry.",
}


_PROPERTY_DESCRIPTION_FALLBACK = "No description available for this property."


def _property_description(name: str) -> str:
    return _PROPERTY_DESCRIPTIONS.get(name, _PROPERTY_DESCRIPTION_FALLBACK)


# Fixed thematic buckets for grouping related properties (issue #16's
# "group related properties together" ask). A name-pattern map rather than
# per-class config, so it works uniformly across every editable class
# without needing a group defined for each of the ~100+ distinct property
# names in this codebase. Order here is also the display order.
_PROPERTY_GROUPS_ORDER: List[str] = [
    "Appearance",
    "State",
    "Location",
    "Contents",
    "Other",
]


_PROPERTY_GROUP_MAP: Dict[str, str] = {
    # Appearance
    "name": "Appearance",
    "description": "Appearance",
    "idle_message": "Appearance",
    "discovery_message": "Appearance",
    "nickname": "Appearance",
    # State
    "hidden": "State",
    "hide_factor": "State",
    "locked": "State",
    "start_open": "State",
    "repeat": "State",
    "check_conditions": "State",
    # Location
    "teleport_map": "Location",
    "teleport_tile": "Location",
    "target_map_name": "Location",
    "target_coordinates": "Location",
    # Contents
    "inventory": "Contents",
    "items": "Contents",
    "events": "Contents",
    "allowed_subtypes": "Contents",
    "stock_count": "Contents",
    "merchant": "Contents",
    "keywords": "Contents",
}


def _property_group(name: str) -> str:
    return _PROPERTY_GROUP_MAP.get(name, "Other")


def _grouped_field_layout(editable_params, col_count: int) -> List[Dict[str, Any]]:
    """Compute grid placements for the property dialog, grouping params by
    _property_group() while preserving each group's original relative
    order, and inserting a header entry before each non-empty group's
    fields (only when more than one group is actually present -- a single
    "Other" header for a class whose properties all fall in one bucket
    would just be noise).

    Pure/tkinter-free by design so the grouping logic is unit-testable
    without a display, which this module otherwise has no way to exercise.

    Returns a list of entries in placement order:
      {"kind": "header", "text": group_name, "row": int}
      {"kind": "field", "param": Parameter, "row": int, "col": int}
    """
    groups: "OrderedDict[str, list]" = OrderedDict(
        (g, []) for g in _PROPERTY_GROUPS_ORDER
    )
    for p in editable_params:
        groups[_property_group(p.name)].append(p)
    groups = OrderedDict((g, ps) for g, ps in groups.items() if ps)
    show_headers = len(groups) > 1

    layout: List[Dict[str, Any]] = []
    next_row = 0
    for group_name, params in groups.items():
        if show_headers:
            layout.append({"kind": "header", "text": group_name, "row": next_row})
            next_row += 1
        for local_idx, p in enumerate(params):
            row = next_row + (local_idx if col_count == 1 else local_idx // col_count)
            col = 0 if col_count == 1 else local_idx % col_count
            layout.append({"kind": "field", "param": p, "row": row, "col": col})
        rows_used = (
            len(params) if col_count == 1 else -(-len(params) // col_count)
        )  # ceil division
        next_row += rows_used
    return layout


def get_editable_params(cls):
    sig = inspect.signature(cls.__init__)
    params = [p for p in sig.parameters.values() if p.name != "self"]
    excluded_names = {"player", "tile"}
    param_names = {p.name for p in params}
    # 'items' is a legacy/test-only alias accepted by Container-like __init__
    # signatures that also take 'inventory' (the real, canonical attribute --
    # 'items' is normalized into 'inventory' at construction time and never
    # stored on the instance). Editing both as separate property-dialog
    # widgets created two independently-tracked lists for one underlying
    # field: the 'items' widget, processed after 'inventory' in constructor-
    # parameter order, silently overwrote any edit made via the 'inventory'
    # widget on save (issue #131 -- a container's items vanishing after
    # opening/closing its properties with no intended edit). Only 'inventory'
    # is a real editable field.
    if "items" in param_names and "inventory" in param_names:
        excluded_names = excluded_names | {"items"}
    editable_params = [p for p in params if p.name not in excluded_names]
    excluded_params = [p for p in params if p.name in excluded_names]
    return editable_params, excluded_params


def create_text_entry(container, val, auto_save):
    ent = tk.Entry(container)
    ent.insert(0, str(val) if val is not None else "")
    ent.pack(fill="x", pady=(2, 5))
    ent.bind("<FocusOut>", lambda e: auto_save())
    return ent


def create_bool_entry(container, val, auto_save):
    bool_var = tk.BooleanVar(value=bool(val))
    toggle_frame = tk.Frame(container, bg="#34495e")
    toggle_frame.pack(fill="x")

    def make_toggle_button(label, state):
        btn = tk.Button(
            toggle_frame,
            text=label,
            relief="sunken" if bool_var.get() == state else "raised",
            width=6,
            command=lambda s=state: set_state(s),
        )
        return btn

    def refresh_buttons():
        for b, state in buttons:
            if bool_var.get() == state:
                b.config(
                    relief="sunken", bg="#2ecc71" if state else "#e74c3c", fg="white"
                )
            else:
                b.config(relief="raised", bg="#7f8c8d", fg="black")

    def set_state(s):
        bool_var.set(s)
        refresh_buttons()
        auto_save()

    buttons = []
    btn_false = make_toggle_button("False", False)
    btn_false.pack(side="left", padx=(0, 4))
    buttons.append((btn_false, False))
    btn_true = make_toggle_button("True", True)
    btn_true.pack(side="left")
    buttons.append((btn_true, True))
    refresh_buttons()
    return bool_var

