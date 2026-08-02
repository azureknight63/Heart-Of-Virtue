"""The property-edit dialog subsystem: TagListFrame (the tag-based picker
widget used throughout the editor), the add/edit/remove/duplicate element
helpers, the hierarchical class choosers, and open_property_dialog itself.

These are all mutually recursive (TagListFrame.on_edit -> edit_element ->
open_property_dialog -> open_chooser -> show_hierarchy_chooser ->
open_property_dialog again for the newly-created instance) and so must stay
in one module -- splitting them further would require circular imports
between files.
"""
import ast
import copy
import importlib
import inspect
import json
import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from events import Event  # type: ignore
from npc import Merchant  # type: ignore

from utils.mapgen.class_discovery import (
    _get_module_paths_for_class,
    build_class_hierarchy,
    filter_classes,
    parse_module_classes,
    parse_type_hint,
)
from utils.mapgen.constants import project_root
from utils.mapgen.widgets import (
    _grouped_field_layout,
    _property_description,
    _property_group,
    create_bool_entry,
    create_text_entry,
    get_editable_params,
)


def _get_editable_properties(obj) -> List[Tuple[str, str]]:
    props: List[Tuple[str, str]] = []
    try:
        cls = obj.__class__
        sig = inspect.signature(cls.__init__)
        params = [p for p in sig.parameters.values() if p.name != "self"]
        excluded = {"player", "tile"}
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
                rep = rep[:77] + "..."
            props.append((p.name, rep))
    except Exception:
        pass
    return props


class TagListFrame(tk.Frame):
    def __init__(self, parent, allow_duplicate=True, *args, map_data=None, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.on_edit = edit_element
        self.on_remove = remove_element
        self.on_duplicate = duplicate_element if allow_duplicate else None
        self._tags: List[Tuple[Any, tk.Frame]] = []
        self._tooltip: Optional[tk.Toplevel] = None
        self.topLevelWidget = self.winfo_toplevel()
        # Threaded through to edit_element -> open_property_dialog so editing
        # an existing tag has live map data available (e.g. the merchant
        # combobox), instead of relying on a module-level `app` global.
        self.map_data = map_data

    def _show_tooltip(self, event, obj):
        self._hide_tooltip()
        header = obj.__class__.__name__ if hasattr(obj, "__class__") else "Object"
        lines = [header]
        props = _get_editable_properties(obj)
        if props:
            lines.extend(f"{n} = {v}" for n, v in props)
        else:
            lines.append("(No editable properties)")
        text = "\n".join(lines)
        tw = tk.Toplevel(self.winfo_toplevel())
        tw.wm_overrideredirect(True)
        lbl = tk.Label(
            tw,
            text=text,
            justify="left",
            bg="#ffffe0",
            fg="black",
            bd=1,
            relief="solid",
            font=("Helvetica", 9),
        )
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
        widget.bind("<Enter>", lambda e, o=obj: self._show_tooltip(e, o))
        widget.bind("<Leave>", lambda e: self._hide_tooltip())

    def add_tag(self, identifier, lst: List, text: str):
        tag_frame = tk.Frame(self, bd=1, relief="solid", padx=4, pady=2)
        is_class_object = isinstance(identifier, type)
        # Set background color for class-type tags
        if is_class_object:
            tag_frame.config(bg="#3498db")  # blue background for class-type tags
        tag_label = tk.Label(tag_frame, text=text)
        # Also set label background for class-type tags
        if is_class_object:
            tag_label.config(bg="#3498db", fg="white")
        tag_label.pack(side="left")
        del_btn = tk.Button(
            tag_frame,
            text="×",
            command=lambda: self.remove(identifier, lst),
            bd=0,
            padx=2,
            pady=0,
        )
        del_btn.pack(side="right")
        is_class_object = isinstance(identifier, type)
        if self.on_duplicate and not is_class_object:
            dup_btn = tk.Button(
                tag_frame,
                text="⧉",
                command=lambda: self.on_duplicate(identifier, lst, frame=self),
                bd=0,
                padx=2,
                pady=0,
            )
            dup_btn.pack(side="right")
        tag_frame.pack(side="left", padx=2, pady=2)
        if not is_class_object:
            tag_frame.bind(
                "<Double-Button-1>",
                lambda e: self.on_edit(
                    self.topLevelWidget, identifier, lst, self, map_data=self.map_data
                ),
            )
            tag_label.bind(
                "<Double-Button-1>",
                lambda e: self.on_edit(
                    self.topLevelWidget, identifier, lst, self, map_data=self.map_data
                ),
            )
            self._bind_tooltip(tag_frame, identifier)
            self._bind_tooltip(tag_label, identifier)
        else:
            # Tooltip for class objects
            def _show_cls_tooltip(event, cls_obj=identifier):
                self._hide_tooltip()
                text = f"Class: {cls_obj.__name__}\nModule: {cls_obj.__module__}"
                tw = tk.Toplevel(self.winfo_toplevel())
                tw.wm_overrideredirect(True)
                lbl = tk.Label(
                    tw,
                    text=text,
                    justify="left",
                    bg="#ffffe0",
                    fg="black",
                    bd=1,
                    relief="solid",
                    font=("Helvetica", 9),
                )
                lbl.pack(ipadx=4, ipady=2)
                x = event.x_root + 20
                y = event.y_root + 20
                tw.wm_geometry(f"+{x}+{y}")
                self._tooltip = tw

            for w in (tag_frame, tag_label):
                w.bind("<Enter>", _show_cls_tooltip)
                w.bind("<Leave>", lambda e: self._hide_tooltip())
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


"""
===== Static Methods to manage TagListFrames, which can be children of TileEditorWindow OR a container tk.Frame =====
"""


def create_element_frame(
    dialog_object: tk.Toplevel,
    parent: tk.Frame,
    attr_string: str,
    map_data: Optional[dict] = None,
):
    """
    Creates a TagListFrame, packs it into the parent, sets it as an attribute on the dialog_object, and returns it.

    Args:
        dialog_object: The TileEditorWindow or tk.Toplevel instance to attach the frame to.
        parent: The parent tk.Frame to pack the new TagListFrame into.
        attr_string: The attribute name to set on the dialog_object.
        map_data: The currently-loaded map, threaded through so double-clicking
            an existing tag to edit it can open a property dialog with live
            map data available (e.g. for the merchant-picker combobox).

    Returns:
        The created TagListFrame instance.
    """
    frame = TagListFrame(parent, map_data=map_data)
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
            if base.__name__ == "Event" and base.__module__.split(".")[-1] == "events":
                return True
        except Exception:
            continue

    # Fallback: accept any base simply named 'Event'
    for base in inspect.getmro(cls):
        if base.__name__ == "Event":
            return True

    return False


def _is_merchant_like(obj):
    """Return True if `obj` is a Merchant instance/class even if Merchant
    resolves from a different import path (e.g. src.npc._merchants.Merchant
    vs. this module's bare `npc` import).

    Issue #463: needed once load_map()/instantiate_placeholder started
    resolving classes exclusively through the canonical `src.*` path (see
    map_placeholders.resolve_class) -- a plain `isinstance(x, Merchant)`
    against this file's bare-imported Merchant would silently stop matching
    placeholder-loaded merchants otherwise. Mirrors the existing
    `_is_event_like` pattern above.
    """
    try:
        cls = obj if isinstance(obj, type) else obj.__class__
    except Exception:
        return False

    for base in inspect.getmro(cls):
        if base is Merchant:
            return True

    # Fallback: accept any base simply named 'Merchant', regardless of which
    # of the npc package's duplicate-module variants it resolved from.
    for base in inspect.getmro(cls):
        if base.__name__ == "Merchant":
            return True

    return False


def add_element(inst, lst: List, frame: TagListFrame):
    """
    Adds an instance `inst` to the list `lst` for the given frame of `obj`.
    If the instance has a `count` attribute and an existing item of the same class is present,
    their counts are stacked. Updates the associated tag frame if present.
    Shows an error message if the instance is invalid.
    """
    if inst is None or not hasattr(inst, "__class__"):
        messagebox.showerror("Error", "Invalid object instance.")
        return
    # stacking logic: if item has a count attribute, stack with existing same-class item
    # Ignores Event instances for stacking since events should never stack
    inst_is_event_subclass = _is_event_like(inst)
    if hasattr(inst, "count") and not inst_is_event_subclass:
        for existing in lst:
            if isinstance(existing, inst.__class__):
                try:
                    existing.count = getattr(existing, "count", 1) + getattr(
                        inst, "count", 1
                    )
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


def edit_element(
    dialog_object: tk.Toplevel,
    inst,
    lst: List,
    frame: TagListFrame,
    map_data: Optional[dict] = None,
):
    """
    Opens a property dialog to edit the given element instance.
    Updates or removes the element in the tag list frame based on user action.
    Args:
        dialog_object: The TileEditorWindow or property dialog (tk.Toplevel) instance
        inst: The instance to edit.
        lst: The list containing the instance.
        frame: The TagListFrame containing the element.
        map_data: The currently-loaded map, forwarded to open_property_dialog.
    """

    def callback(updated_inst, this_lst, this_frame):
        if updated_inst is None:  # Delete
            remove_element(updated_inst, this_lst, this_frame)
        else:
            refresh_tags(this_lst, this_frame)

    open_property_dialog(
        dialog_object,
        inst.__class__,
        existing=inst,
        callback=lambda updated_inst: callback(updated_inst, lst, frame),
        map_data=map_data,
    )


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
            name = inst.__class__.__name__ if hasattr(inst, "__class__") else str(inst)
        frame.add_tag(inst, lst, name)


def open_chooser(
    dialog_object: tk.Toplevel,
    lst: List,
    tag_frame: TagListFrame,
    base_class_name: str = None,
    is_event: bool = False,
    map_data: Optional[dict] = None,
):
    paths = []
    if is_event:
        story_dir = os.path.join(project_root, "src", "story")
        if os.path.isdir(story_dir):
            paths = [
                os.path.join(story_dir, fname)
                for fname in os.listdir(story_dir)
                if fname.endswith(".py") and not fname.startswith("__")
            ]
        if not paths:
            messagebox.showerror("Error", "No event files found in src/story.")
            return
        show_hierarchy_chooser(
            dialog_object,
            paths,
            "Choose Event",
            add_element,
            lst,
            tag_frame,
            map_data=map_data,
        )
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
            messagebox.showerror(
                "Error",
                f"Could not find base class {base_class_name} or its subclasses in src/.",
            )
            return
        show_hierarchy_chooser(
            dialog_object,
            paths,
            f"Choose {base_class_name}",
            add_element,
            lst,
            tag_frame,
            base_class_name,
            map_data=map_data,
        )


def _build_hierarchy_chooser(
    dialog_object: tk.Toplevel,
    module_paths,
    dialog_title,
    filter_by_class,
    on_select,
    geometry: str = "300x430",
):
    """Shared hierarchical class-picker dialog behind show_hierarchy_chooser,
    open_single_class_type_chooser, and show_class_type_hierarchy_chooser.
    Those three were ~90% identical -- parse module_paths into a unified
    class hierarchy, build a filterable Listbox dialog over it, resolve the
    double-clicked entry to a class object -- differing only in dialog
    geometry and what to do with the resolved class once picked, which is
    exactly what `on_select` and `geometry` parameterize here.

    module_paths: list[str] absolute file system paths.
    on_select(cls_obj): called with the resolved class on double-click; any
        exception it raises is reported the same as a resolution failure.
    """
    # Parse modules and build unified class hierarchy across them
    class_info: Dict[str, Any] = (
        {}
    )  # name -> { 'bases': [...], 'children': set(), 'module': import_path }
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
    roots = sorted(
        [
            n
            for n, info in class_info.items()
            if not any(b in class_info for b in info["bases"]) and n in allowed_classes
        ]
    )
    # Build dialog
    dlg = tk.Toplevel(dialog_object)
    dlg.title(dialog_title)
    dlg.geometry(geometry)
    dlg.transient(dialog_object)
    dlg.grab_set()
    # Filter entry
    filter_frame = tk.Frame(dlg)
    filter_frame.pack(fill="x", padx=5, pady=5)
    tk.Label(filter_frame, text="Filter:", anchor="w").pack(side="left")
    filter_var = tk.StringVar()
    tk.Entry(filter_frame, textvariable=filter_var).pack(
        side="left", fill="x", expand=True
    )
    # Listbox
    frame = tk.Frame(dlg)
    frame.pack(fill="both", expand=True)
    lb = tk.Listbox(frame)
    sb = tk.Scrollbar(frame, orient="vertical", command=lb.yview)
    lb.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    lb.pack(side="left", fill="both", expand=True)
    # Maintain metadata externally to avoid adding typed attribute to tk.Listbox (silences warning)
    items_meta: List[Dict[str, str]] = []

    # helper to decide if subtree matches filter
    def update_list(*_args):
        search = filter_var.get().lower().strip()
        lb.delete(0, tk.END)
        items_meta.clear()
        visited = set()

        def subtree_matches(cname):
            if cname not in allowed_classes:
                return False
            if not search or search in cname.lower():
                return True
            return any(subtree_matches(ch) for ch in class_info[cname]["children"])

        def recurse(names, indent=0):
            for n in sorted(names):
                if n in visited or n not in allowed_classes:
                    continue
                visited.add(n)
                info = class_info[n]
                if subtree_matches(n):
                    lb.insert("end", "  " * indent + n)
                    items_meta.append({"name": n, "module": info["module"]})
                    if class_info[n]["children"]:
                        recurse(class_info[n]["children"], indent + 1)

        recurse(roots)

    filter_var.trace_add("write", update_list)
    update_list()

    # double-click to resolve the class and hand it to on_select
    def on_double(_event=None):
        if not lb.curselection():
            return
        idx = lb.curselection()[0]
        meta = cast(Dict[str, str], items_meta[idx])
        cls_name = meta.get("name", "")
        module_name = meta.get("module", "")
        try:
            module = importlib.import_module(module_name)
            cls_obj = getattr(module, cls_name)
            on_select(cls_obj)
        except Exception as ex:
            messagebox.showerror("Error", f"Could not load class: {ex}")
        dlg.destroy()

    lb.bind("<Double-Button-1>", on_double)
    return dlg


def show_hierarchy_chooser(
    dialog_object: tk.Toplevel,
    module_paths,
    dialog_title,
    add_callback,
    lst: List,
    tag_frame: TagListFrame,
    filter_by_class: str = None,
    map_data: Optional[dict] = None,
):
    """Display hierarchical class chooser for one or more module paths.
    On selection, opens a property dialog to configure the new instance
    before handing it to add_callback (e.g. add_element).
    module_paths: list[str] absolute file system paths.
    """

    def _on_select(cls_obj):
        open_property_dialog(
            dialog_object,
            cls_obj,
            existing=None,
            callback=lambda inst: add_callback(inst, lst, tag_frame),
            map_data=map_data,
        )

    _build_hierarchy_chooser(
        dialog_object,
        module_paths,
        dialog_title,
        filter_by_class,
        _on_select,
        geometry="320x450",
    )


def open_class_type_chooser(
    dialog_object: tk.Toplevel,
    base_class_name: str,
    lst: List[type],
    tag_frame: TagListFrame,
):
    if not base_class_name:
        messagebox.showerror("Error", "Base class name not provided.")
        return
    try:
        module_paths = _get_module_paths_for_class(base_class_name)
    except Exception:
        module_paths = []
    if not module_paths:
        messagebox.showerror(
            "Error",
            f"Could not find base class {base_class_name} or its subclasses in src/.",
        )
        return
    show_class_type_hierarchy_chooser(
        dialog_object,
        module_paths,
        f"Choose {base_class_name} Type",
        lst,
        tag_frame,
        base_class_name,
    )


# NEW: single-selection variant for Type[Base] (non-list) annotations
# Reuses the same hierarchy building logic but ensures only one class can be selected.
def open_single_class_type_chooser(
    dialog_object: tk.Toplevel,
    base_class_name: str,
    lst: List[type],
    tag_frame: TagListFrame,
):
    if not base_class_name:
        messagebox.showerror("Error", "Base class name not provided.")
        return
    try:
        module_paths = _get_module_paths_for_class(base_class_name)
    except Exception:
        module_paths = []
    if not module_paths:
        messagebox.showerror(
            "Error",
            f"Could not find base class {base_class_name} or its subclasses in src/.",
        )
        return

    def _on_select(cls_obj):
        # Single-selection enforcement
        lst.clear()
        lst.append(cls_obj)
        refresh_tags(lst, tag_frame)

    _build_hierarchy_chooser(
        dialog_object, module_paths, f"Choose {base_class_name} Type", base_class_name, _on_select
    )


def show_class_type_hierarchy_chooser(
    dialog_object: tk.Toplevel,
    module_paths,
    dialog_title,
    lst: List[type],
    tag_frame: TagListFrame,
    filter_by_class: str = None,
):
    def _on_select(cls_obj):
        if cls_obj not in lst:
            lst.append(cls_obj)
            refresh_tags(lst, tag_frame)

    _build_hierarchy_chooser(
        dialog_object, module_paths, dialog_title, filter_by_class, _on_select
    )


def _open_bulk_class_chooser(
    parent: tk.Tk,
    candidates: Dict[type, List[Any]],
    on_save_callback,
    map_data: Optional[dict] = None,
):
    """Let the user pick which class to bulk-edit when a multi-tile
    selection contains more than one kind of object, then open a single
    property dialog spanning every instance of that class across the
    selection (see MapEditor.bulk_edit_selected_tiles)."""
    if len(candidates) == 1:
        (cls, instances) = next(iter(candidates.items()))
        open_property_dialog(
            parent,
            cls,
            existing=instances,
            callback=lambda _: on_save_callback(),
            map_data=map_data,
        )
        return

    dlg = tk.Toplevel(parent)
    dlg.title("Bulk Edit — Choose a class")
    dlg.geometry("360x320")
    dlg.transient(parent)
    dlg.grab_set()

    tk.Label(
        dlg,
        text="Multiple object types found across the selection.\nChoose which one to bulk edit:",
        bg="#2c3e50",
        fg="white",
        justify="left",
        wraplength=340,
    ).pack(fill="x", padx=10, pady=(10, 6))

    lb = tk.Listbox(dlg)
    lb.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    ordered_classes = sorted(candidates.keys(), key=lambda c: c.__name__)
    for cls in ordered_classes:
        lb.insert(
            tk.END, f"{cls.__name__} ({len(candidates[cls])} found)"
        )

    def _on_choose(_event=None):
        selection = lb.curselection()
        if not selection:
            return
        cls = ordered_classes[selection[0]]
        dlg.destroy()
        open_property_dialog(
            parent,
            cls,
            existing=candidates[cls],
            callback=lambda _: on_save_callback(),
            map_data=map_data,
        )

    lb.bind("<Double-Button-1>", _on_choose)
    tk.Button(dlg, text="Edit Selected Class", command=_on_choose).pack(
        fill="x", padx=10, pady=(0, 10)
    )


def open_property_dialog(
    parent_dialog_object: tk.Toplevel,
    cls,
    existing=None,
    callback=None,
    map_data: Optional[dict] = None,
):
    # Bulk-edit support (issue #16): `existing` may be a single instance (the
    # normal case) or a list of instances of the same class collected across
    # multiple selected tiles (see MapEditor.bulk_edit_selected_tiles). Field
    # values below are read from/previewed against the first instance;
    # auto_save() applies every change to every instance in the list. The
    # rest of this function reads from `existing` (the primary instance)
    # exactly as in the single-object case -- only the save path needs to
    # know about the full list.
    existing_list = (
        existing if isinstance(existing, list) else ([existing] if existing is not None else [])
    )
    existing = existing_list[0] if existing_list else None
    is_bulk_edit = len(existing_list) > 1

    dlg = tk.Toplevel(parent_dialog_object)
    dlg.title(
        f"Properties for {cls.__name__} ({len(existing_list)} selected)"
        if is_bulk_edit
        else f"Properties for {cls.__name__}"
    )
    dlg.geometry("900x550")
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
            all_npcs.extend(tdata.get("npcs", []))
        merchants = [npc for npc in all_npcs if _is_merchant_like(npc)]
        merchant_map = {}
        for m in merchants:
            merchant_name = getattr(m, "name", str(m))
            merchant_map[merchant_name] = m
        return merchant_map

    all_merchants = None
    if "merchant" in [p.name for p in editable_params]:
        try:
            all_merchants = get_all_merchants(map_data) if map_data else {}
        except Exception:
            all_merchants = {}

    # Auto-save function that will be called on every change
    # Sentinel distinguishing "field had no value at snapshot time" from any
    # real value (including None) when diffing against initial_kwargs below.
    _UNSET = object()
    # Snapshot of every field's value as seeded from the primary instance,
    # captured once after the field-building loop below populates `entries`
    # (Python resolves this closure's free variable at call time, so it's
    # fine that auto_save is defined before initial_kwargs is assigned).
    initial_kwargs: Dict[str, Any] = {}

    def _collect_kwargs() -> Dict[str, Any]:
        """Read every field widget's current value. Pure -- no side effects
        on existing/existing_list; auto_save() is solely responsible for
        applying the result."""
        kwargs: Dict[str, Any] = {}
        for field_name, meta in entries.items():
            if meta["type"] == "bool":
                kwargs[field_name] = meta["get"]()
            elif meta["type"] == "hierarchical":
                kwargs[field_name] = meta["get"]()
            else:
                raw = meta["get"]()
                if raw == "":
                    continue
                try:
                    if meta.get("is_merchant"):
                        # The combobox value is the merchant's name; store the
                        # name (not the resolved instance) so it matches what
                        # get() will report on every subsequent read, and so
                        # unchanged-field diffing in auto_save() works.
                        kwargs[field_name] = raw
                    else:
                        kwargs[field_name] = ast.literal_eval(raw)
                except Exception:
                    kwargs[field_name] = raw
        return kwargs

    def auto_save():
        if not existing_list:
            return  # Only auto-save for existing objects, not when creating new ones

        kwargs = _collect_kwargs()

        # Apply changes to every object being edited (a single instance in
        # the normal case, or every instance collected for a bulk edit --
        # see is_bulk_edit above). Only fields the user actually changed
        # from their initial (primary-instance-seeded) value are applied --
        # auto_save reruns on every keystroke across every field, so without
        # this filter a bulk edit would flatten every selected instance to
        # the primary instance's values for every field the instant any one
        # field was touched, not just the field being edited. Harmless no-op
        # filtering for the single-object case (re-applying an unchanged
        # value is already a no-op there). 'items' never appears here for
        # Container-like objects -- get_editable_params() excludes it
        # whenever 'inventory' (the real attribute) is also a constructor
        # param, so there's no second, divergent widget to reconcile.
        for k, v in kwargs.items():
            if v == initial_kwargs.get(k, _UNSET):
                continue
            for obj in existing_list:
                setattr(obj, k, v)

        # Trigger callback to refresh UI if provided
        if callback:
            callback(existing_list if is_bulk_edit else existing)

    # Search/filter box (issue #16): only worth showing once there are enough
    # properties that finding one by eye is actually a chore.
    field_containers: Dict[str, tk.Frame] = {}
    # Populated once the property loop below runs; declared here (rather than
    # only inside that loop) so _apply_filter's closure always finds them,
    # even though it's defined before the loop executes -- Python resolves
    # enclosing-scope names at call time, not definition time, but only if
    # the name is assigned somewhere in this function body at all.
    group_header_widgets: Dict[str, tk.Widget] = {}
    group_fields: Dict[str, List[str]] = {}
    if len(editable_params) > 6:
        search_frame = tk.Frame(dlg, bg="#2c3e50", padx=14, pady=(10, 0))
        search_frame.pack(fill="x")
        tk.Label(
            search_frame, text="Filter:", bg="#2c3e50", fg="white"
        ).pack(side="left")
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))

        def _apply_filter(*_):
            query = search_var.get().strip().lower()
            for field_name, container_frame in field_containers.items():
                if not query or query in field_name.lower():
                    container_frame.grid()
                else:
                    container_frame.grid_remove()
            # Hide a group's header too once every field in that group has
            # been filtered out, so an orphaned "— State —" label doesn't
            # linger over nothing.
            for group_name, header_widget in group_header_widgets.items():
                any_visible = any(
                    (not query or query in fname.lower())
                    for fname in group_fields.get(group_name, [])
                )
                if any_visible:
                    header_widget.grid()
                else:
                    header_widget.grid_remove()

        search_var.trace_add("write", _apply_filter)

    frm = tk.Frame(dlg, bg="#34495e", padx=14, pady=14)
    frm.pack(fill="both", expand=True)
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
            for param_name in ("teleport_map", "target_map_name"):
                for var in map_name_vars:
                    if getattr(var, "_hov_param", None) == param_name:
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

                var.trace_add("write", _make_cb())

        def _build_class_type_field(p, container) -> bool:
            """Handles Type[Base]/list[Type[Base]] annotations (including
            Optional[Type[Base]]/Union[Type[Base], None]): a tag-based
            picker of *classes themselves* rather than instances. Returns
            True if the field was handled (entries[p.name] was set and the
            caller should move on to the next parameter), False otherwise
            (including on any resolution error -- matches the original
            inline code's blanket except-and-fall-through-to-the-next-
            specialized-field-check behavior)."""
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

                def _make_multi_btn_handler(
                    base_name: str, ref_list: List[type], frame_ref: TagListFrame
                ):
                    return lambda: open_class_type_chooser(
                        dlg, base_name, ref_list, frame_ref
                    )

                def _make_single_btn_handler(
                    base_name: str, ref_list: List[type], frame_ref: TagListFrame
                ):
                    return lambda: open_single_class_type_chooser(
                        dlg, base_name, ref_list, frame_ref
                    )

                # First: list[Type[Base]] existing behavior
                if ann_origin in (list, List) and ann_args:
                    inner = ann_args[0]
                    inner_origin = get_origin(inner)
                    inner_args = get_args(inner)
                    if (
                        inner_origin in (type, Type)
                        and inner_args
                        and inspect.isclass(inner_args[0])
                    ):
                        base_cls = inner_args[0]
                        type_list = list(
                            getattr(existing, p.name, [])
                            if existing is not None
                            else []
                        )
                        tag_frame = create_element_frame(
                            dlg, container, f"{p.name}_types_frame", map_data=map_data
                        )
                        refresh_tags(type_list, tag_frame)
                        tk.Button(
                            container,
                            text="Choose Types",
                            command=_make_multi_btn_handler(
                                base_cls.__name__, type_list, tag_frame
                            ),
                        ).pack(fill="x", padx=(5, 0), pady=(2, 2))
                        entries[p.name] = {
                            "type": "hierarchical",
                            "get": _make_list_getter(type_list),
                        }
                        return True
                # NEW: Single Type[Base] support (including Optional/Union[Type[Base], None])
                target_base_cls = None
                single_mode = False
                if (
                    ann_origin in (type, Type)
                    and ann_args
                    and inspect.isclass(ann_args[0])
                ):
                    target_base_cls = ann_args[0]
                    single_mode = True
                # Optional / Union handling: Union[Type[Base], None]
                elif ann_origin is Union and ann_args:
                    for arg in ann_args:
                        arg_origin = get_origin(arg)
                        arg_args = get_args(arg)
                        if (
                            arg_origin in (type, Type)
                            and arg_args
                            and inspect.isclass(arg_args[0])
                        ):
                            target_base_cls = arg_args[0]
                            single_mode = True
                            break
                if single_mode and target_base_cls is not None:
                    existing_val = (
                        getattr(existing, p.name, None)
                        if existing is not None
                        else None
                    )
                    single_list: List[type] = (
                        [existing_val] if isinstance(existing_val, type) else []
                    )
                    tag_frame = create_element_frame(
                        dlg, container, f"{p.name}_type_frame", map_data=map_data
                    )
                    refresh_tags(single_list, tag_frame)
                    tk.Button(
                        container,
                        text="Choose Type",
                        command=_make_single_btn_handler(
                            target_base_cls.__name__, single_list, tag_frame
                        ),
                    ).pack(fill="x", padx=(5, 0), pady=(2, 2))
                    entries[p.name] = {
                        "type": "hierarchical",
                        "get": _make_single_getter(single_list),
                    }
                    return True
            except Exception:
                pass
            return False

        def _build_map_name_field(p, container, val):
            """Specialized combobox for teleport_map/target_map_name fields,
            populated from the *.json files under src/resources/maps/."""
            try:
                from pathlib import Path

                # project_root is the shared constant (see constants.py),
                # not re-derived via __file__ here -- this used to compute
                # "project root" as two directories up from this file when
                # it lived at utils/map_generator.py directly; that math
                # would silently break once this code moved one directory
                # deeper into utils/mapgen/.
                candidate_dirs = [
                    Path(project_root) / "src" / "resources" / "maps",
                    Path(project_root) / "utils" / "src" / "resources" / "maps",
                ]
                map_names = set()
                for d in candidate_dirs:
                    if d.exists():
                        for jf in d.glob("*.json"):
                            map_names.add(jf.stem)
                map_list = sorted(map_names)
            except Exception:
                map_list = []
            if not map_list:
                tk.Label(
                    container,
                    text="No map files (*.json) found.",
                    font=("Helvetica", 9, "italic"),
                    bg="#34495e",
                    fg="#f39c12",
                ).pack(fill="x")
            combo_var = tk.StringVar()
            setattr(combo_var, "_hov_param", p.name)  # tag var with param name
            if isinstance(val, str) and val in map_list:
                combo_var.set(val)
            elif map_list:
                pass
            combo = ttk.Combobox(
                container, textvariable=combo_var, values=map_list, state="readonly"
            )
            combo.pack(fill="x", pady=(2, 5))

            def _on_map_change(event=None):
                # trigger coordinate refreshers then autosave
                for r in coord_refreshers:
                    try:
                        r()
                    except Exception:
                        pass
                auto_save()

            combo.bind("<<ComboboxSelected>>", _on_map_change)
            _add_map_var(combo_var)
            entries[p.name] = {
                "type": "text",
                "get": lambda v=combo_var: v.get(),
                "is_map_name": True,
            }
            # ensure traces attached after potential list filled
            _attach_traces()

        def _build_coordinate_field(p, container, val):
            """Specialized combobox for teleport_tile/target_coordinates
            fields: lists every tile on the currently-selected map (falling
            back to the in-progress editor map) as "Title (x,y)" entries."""
            coord_combo_var = tk.StringVar()
            tuple_var = tk.StringVar()
            # UI combobox placeholder; values set in refresh
            coord_combo = ttk.Combobox(
                container, textvariable=coord_combo_var, values=[], state="readonly"
            )
            coord_combo.pack(fill="x", pady=(2, 5))
            display_to_coord: Dict[str, Tuple[int, int]] = {}
            # capture existing value to attempt reselect after refresh
            existing_coord = None
            if isinstance(val, (tuple, list)) and len(val) == 2:
                try:
                    existing_coord = (int(val[0]), int(val[1]))
                except Exception:
                    existing_coord = None

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

                        # See _build_map_name_field's matching comment above.
                        candidate_dirs = [
                            Path(project_root) / "src" / "resources" / "maps",
                            Path(project_root) / "utils" / "src" / "resources" / "maps",
                        ]
                        for d in candidate_dirs:
                            jf = d / f"{map_name}.json"
                            if jf.exists():
                                with open(jf, "r", encoding="utf-8") as f:
                                    data = json.load(f)
                                tiles_source = data
                                break
                    except Exception:
                        tiles_source = None
                if tiles_source is None:
                    # fallback to current editor map, threaded in via
                    # open_property_dialog's map_data parameter
                    try:
                        tiles_source = {str(k): v for k, v in (map_data or {}).items()}
                    except Exception:
                        tiles_source = {}
                # Build list
                for k, tdata in tiles_source.items():
                    try:
                        if (
                            isinstance(k, str)
                            and k.startswith("(")
                            and k.endswith(")")
                        ):
                            parts = k.strip("()").split(",")
                            tx, ty = int(parts[0]), int(parts[1])
                        elif isinstance(k, (list, tuple)) and len(k) == 2:
                            tx, ty = int(k[0]), int(k[1])
                        else:
                            continue
                        title = (
                            tdata.get("title") if isinstance(tdata, dict) else None
                        )
                        if not title:
                            # attempt id fallback
                            if isinstance(tdata, dict):
                                title = tdata.get("id", f"tile_{tx}_{ty}")
                            else:
                                title = f"tile_{tx}_{ty}"
                        display = f"{title} ({tx},{ty})"
                        display_to_coord[display] = (tx, ty)
                    except Exception:
                        continue
                # Update combobox values
                values = sorted(
                    display_to_coord.keys(),
                    key=lambda s: (display_to_coord[s][0], display_to_coord[s][1]),
                )
                coord_combo.config(values=values)
                # Preserve selection if still valid
                if tuple_var.get():
                    try:
                        current_tuple = ast.literal_eval(tuple_var.get())
                    except Exception:
                        current_tuple = None
                else:
                    current_tuple = existing_coord
                if (
                    current_tuple
                    and isinstance(current_tuple, (list, tuple))
                    and len(current_tuple) == 2
                ):
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

            coord_combo.bind("<<ComboboxSelected>>", on_coord_select)
            refresh_tiles()
            coord_refreshers.append(refresh_tiles)
            # Ensure traces attached if map vars already exist
            _attach_traces()
            entries[p.name] = {
                "type": "text",
                "get": lambda v=tuple_var: v.get(),
                "is_tile_coord": True,
            }

        def _build_class_chooser_field(p, container, val, base_class, is_list):
            """Generic tag-based chooser for a class-typed field (an Item/
            NPC/Object/Event instance or list of them), as opposed to the
            Type[Base]-picks-a-class-itself field above."""
            tag_frame = create_element_frame(
                dlg, container, f"{p.name}_frame", map_data=map_data
            )
            if is_list:
                current_value = (
                    getattr(existing, p.name, None) if existing is not None else []
                )
                # 'items' (Container's legacy inventory alias) never reaches
                # this point -- get_editable_params() excludes it whenever
                # 'inventory' is also a constructor param, so this widget is
                # only ever built for the real, canonical attribute.
                if current_value is None:
                    current_value = []
            else:
                val = (
                    getattr(existing, p.name, None)
                    if existing is not None
                    else None
                )
                current_value = [val] if val is not None else []
            field_type = "list" if is_list else "single"

            # Initialize tags for any objects already present by default
            refresh_tags(current_value, tag_frame)

            base_class_name = str(base_class.__name__) if base_class else "Object"
            is_event = (
                True if base_class and base_class.__name__ == "Event" else False
            )

            choose_btn = tk.Button(
                container,
                text="Choose",
                command=lambda this_dlg=dlg, this_base_class_name=base_class_name, this_is_event=is_event, this_tag_frame=tag_frame, this_field_type=field_type: open_chooser(
                    this_dlg,
                    (
                        current_value
                        if this_field_type == "list"
                        else (current_value[0] if current_value else [])
                    ),
                    this_tag_frame,
                    base_class_name=this_base_class_name,
                    is_event=this_is_event,
                    map_data=map_data,
                ),
            )
            choose_btn.pack(fill="x", padx=(5, 0), pady=(2, 2))

            # Helper to avoid mutable default capture
            def _make_hier_getter(field_type_local: str, ref_list_local: List[Any]):
                if field_type_local == "list":
                    return lambda: ref_list_local
                return lambda: (ref_list_local[0] if ref_list_local else None)

            entries[p.name] = {
                "type": "hierarchical",
                "get": _make_hier_getter(field_type, current_value),
            }

        def _build_merchant_field(p, container, val):
            """Combobox listing every Merchant NPC placed on the map, for
            fields literally named 'merchant' (e.g. a Shop's stock source)."""
            if not all_merchants:
                tk.Label(
                    container,
                    text="Add a Merchant NPC to this map first.",
                    font=("Helvetica", 9, "italic"),
                    bg="#34495e",
                    fg="#f39c12",
                ).pack(fill="x")
                return
            combo_var = tk.StringVar()
            # If existing value is a merchant object, get its name
            if val and _is_merchant_like(val):
                # Find the name corresponding to the instance
                for name, inst in all_merchants.items():
                    if inst is val:
                        combo_var.set(name)
                        break
            elif isinstance(val, str):  # Fallback for name-based storage
                combo_var.set(val)

            combo = ttk.Combobox(
                container,
                textvariable=combo_var,
                values=list(all_merchants.keys()),
                state="readonly",
            )
            combo.pack(fill="x", pady=(2, 5))

            def on_combo_change(event=None):
                auto_save()

            combo.bind("<<ComboboxSelected>>", on_combo_change)
            entries[p.name] = {
                "type": "text",
                "get": lambda v=combo_var: v.get(),
                "is_merchant": True,
            }

        for _layout_entry in _grouped_field_layout(editable_params, col_count):
            if _layout_entry["kind"] == "header":
                header_lbl = tk.Label(
                    frm,
                    text=_layout_entry["text"],
                    bg="#34495e",
                    fg="#95a5a6",
                    font=("Helvetica", 10, "bold"),
                    anchor="w",
                )
                header_lbl.grid(
                    row=_layout_entry["row"] * 2,
                    column=0,
                    columnspan=col_count,
                    sticky="w",
                    padx=6,
                    pady=(10, 2),
                )
                group_header_widgets[_layout_entry["text"]] = header_lbl
                continue

            p = _layout_entry["param"]
            row = _layout_entry["row"]
            col = _layout_entry["col"]
            group_name = _property_group(p.name)
            group_fields.setdefault(group_name, []).append(p.name)
            container = tk.Frame(frm, bg="#34495e")
            container.grid(row=row * 2, column=col, sticky="ew", padx=6, pady=(0, 6))
            field_containers[p.name] = container

            # derive default/existing value
            if existing is not None:
                val = getattr(
                    existing,
                    p.name,
                    (
                        p.default
                        if p.default is not inspect._empty
                        else getattr(cls, p.name, "")
                    ),
                )
            else:
                if p.name == "repeat":
                    # Force initial repeat to False as per requirement
                    val = False
                elif p.default is not inspect._empty:
                    val = p.default
                else:
                    val = getattr(cls, p.name, "")

            # Highlight properties whose current value has been customized
            # away from the constructor default (issue #16's "highlight
            # commonly used properties" ask, read as "properties someone
            # deliberately set" -- there's no edit-history to draw a true
            # recency signal from, so a default-vs-current diff is the
            # closest honest proxy available without new state/plumbing).
            is_customized = False
            if p.default is not inspect._empty:
                try:
                    is_customized = val != p.default
                except Exception:
                    is_customized = False
            label_fg = "#f1c40f" if is_customized else "white"
            label_text = f"{p.name}*:" if is_customized else f"{p.name}:"
            field_label = tk.Label(
                container, text=label_text, bg="#34495e", fg=label_fg, anchor="w"
            )
            field_label.pack(anchor="w")

            # Tooltip (issue #16's "display tooltips for each property" ask).
            def _make_tooltip_handlers(owner_dlg, description_text):
                state = {"tip": None}

                def _show(event):
                    tw = tk.Toplevel(owner_dlg)
                    tw.wm_overrideredirect(True)
                    tk.Label(
                        tw,
                        text=description_text,
                        justify="left",
                        bg="#ffffe0",
                        fg="black",
                        bd=1,
                        relief="solid",
                        font=("Helvetica", 9),
                        wraplength=280,
                    ).pack(ipadx=4, ipady=2)
                    tw.wm_geometry(f"+{event.x_root + 16}+{event.y_root + 16}")
                    state["tip"] = tw

                def _hide(_event):
                    if state["tip"] is not None:
                        try:
                            state["tip"].destroy()
                        except Exception:
                            pass
                        state["tip"] = None

                return _show, _hide

            _tip_show, _tip_hide = _make_tooltip_handlers(
                dlg, _property_description(p.name)
            )
            field_label.bind("<Enter>", _tip_show)
            field_label.bind("<Leave>", _tip_hide)

            # --- Class TYPE list detection: list[type[Base]] (or single Type[Base]) ---
            if _build_class_type_field(p, container):
                continue

            # NEW: specialized combobox for map name selection
            if p.name in ("teleport_map", "target_map_name"):
                _build_map_name_field(p, container, val)
                continue  # handled specialized field, move to next parameter

            # NEW: specialized combobox for selecting a tile's coordinates on selected map (or current map fallback)
            if p.name in ("teleport_tile", "target_coordinates"):
                _build_coordinate_field(p, container, val)
                continue

            # Check for type hints that should use hierarchical selectors
            base_class, is_list, is_optional = parse_type_hint(p.annotation)

            # Use text entry for str, int, or no type hint
            if (
                p.annotation is inspect._empty
                or p.annotation is str
                or p.annotation is int
            ):
                ent = create_text_entry(container, val, auto_save)
                entries[p.name] = {"type": "text", "get": lambda v=ent: v.get()}

            elif (
                base_class and inspect.isclass(base_class) and not isinstance(val, bool)
            ):
                # Use tag-based chooser for class-based type hints
                _build_class_chooser_field(p, container, val, base_class, is_list)
            elif p.name == "merchant":
                _build_merchant_field(p, container, val)
            elif isinstance(val, bool):
                bool_var = create_bool_entry(container, val, auto_save)
                entries[p.name] = {"type": "bool", "get": lambda v=bool_var: v.get()}
            else:
                ent = create_text_entry(container, val, auto_save)
                entries[p.name] = {"type": "text", "get": lambda v=ent: v.get()}
        for i in range(col_count):
            frm.grid_columnconfigure(i, weight=1)
    else:
        tk.Label(
            frm,
            text="No editable properties.",
            bg="#34495e",
            fg="#ecf0f1",
            font=("Helvetica", 12, "italic"),
        ).pack(pady=20)

    if existing_list:
        # Snapshot every field's seeded (pre-edit) value now that `entries`
        # is fully populated, for auto_save's unchanged-field filter above.
        # List-typed values are copied rather than referenced -- hierarchical
        # fields' "get" callables can return the *same* mutable list object
        # on every call (e.g. a Container's own .inventory list edited via
        # the Choose dialog), so without a copy this snapshot would silently
        # track any later in-place mutation instead of the original state.
        initial_kwargs.update(
            {
                k: (list(v) if isinstance(v, list) else v)
                for k, v in _collect_kwargs().items()
            }
        )

    def on_add_save():
        if existing:
            auto_save()
            dlg.destroy()
        else:
            # For new objects, create the object and add it
            kwargs = {}
            for name, meta in entries.items():
                if meta["type"] == "bool":
                    kwargs[name] = meta["get"]()
                elif meta["type"] == "hierarchical":
                    kwargs[name] = meta["get"]()
                else:
                    raw = meta["get"]()
                    if raw == "":
                        continue
                    try:
                        # Special handling for merchant combobox
                        if meta.get("is_merchant"):
                            kwargs[name] = all_merchants.get(raw)
                        else:
                            kwargs[name] = ast.literal_eval(raw)
                    except Exception:
                        kwargs[name] = raw

            for p in excluded_params:
                kwargs[p.name] = None
            # Ensure repeat explicitly False if parameter exists but user didn't change
            if "repeat" in [p.name for p in editable_params] and "repeat" not in kwargs:
                kwargs["repeat"] = False
            inst = cls(**kwargs)
            if callback:
                callback(inst)
            dlg.destroy()

    def on_delete():
        if existing and messagebox.askyesno(
            "Delete", f"Delete {existing.__class__.__name__}?"
        ):
            if callback:
                callback(None)
            dlg.destroy()

    btn_frame = tk.Frame(dlg, bg="#34495e")
    btn_frame.pack(fill="x", pady=10)
    if existing:
        tk.Button(
            btn_frame,
            text="Delete",
            command=on_delete,
            bg="#e74c3c",
            fg="white",
            font=("Helvetica", 12, "bold"),
            pady=5,
        ).pack(side="left", padx=5)
    # Update button text - "Close" for existing objects, "Add" for new objects
    button_text = "Close" if existing else "Add"
    tk.Button(
        btn_frame,
        text=button_text,
        command=on_add_save,
        bg="#2ecc71",
        fg="white",
        font=("Helvetica", 12, "bold"),
        pady=5,
    ).pack(side="right")

