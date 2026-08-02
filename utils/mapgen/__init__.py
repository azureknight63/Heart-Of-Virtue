"""The map editor, split into a package for maintainability. Historically
this was a single ~4700-line utils/map_generator.py file; it's now:

  constants.py        -- MapSerializationError, DIRECTION_DELTAS,
                          RECIPROCAL_DIRECTIONS, and the project_root/
                          src_root sys.path bootstrap (imported first).
  class_discovery.py   -- src/ AST-scanning and class-hierarchy resolution
                          (parse_type_hint, _get_module_paths_for_class,
                          build_class_hierarchy, filter_classes, ...).
  widgets.py            -- generic Tk widget builders and the property-
                          dialog field metadata (descriptions/grouping).
  property_dialog.py   -- TagListFrame, the element add/edit/remove
                          helpers, the hierarchical class choosers, and
                          open_property_dialog. These are all mutually
                          recursive and so live in one module.
  tile_editor.py        -- TileEditorWindow.
  editor.py             -- MapEditor (the top-level app) and the Convert
                          Elements report helpers.

This __init__.py re-exports every public and private-but-tested name from
those submodules, mirroring the src/moves/ package split (see CLAUDE.md's
"Completed Milestones"), so every existing caller and test -- which does
`import utils.map_generator` or `importlib.import_module("utils.map_generator")`
-- keeps working unchanged. utils/map_generator.py itself is now a thin
compatibility shim: `from utils.mapgen import *` plus the
`if __name__ == "__main__":` launch block, so `python utils/map_generator.py`
(the documented entry point) is also unchanged.
"""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# constants must be imported first: it performs the sys.path bootstrap that
# the bare `from events import ...`/`from npc import ...` imports below
# depend on (see constants.py's own docstring).
from utils.mapgen.constants import (
    DIRECTION_DELTAS,
    RECIPROCAL_DIRECTIONS,
    MapSerializationError,
    project_root,
    src_root,
)

from events import Event  # type: ignore
from npc import Merchant  # type: ignore

# Issue #463: imported canonically (src.*), unlike the two bare imports above
# -- this module is shared with the game engine's own Universe loader and
# must resolve to the exact same module object (a bare `import
# map_placeholders` would create a duplicate with its own class-metadata
# registry, silently breaking cross-loader consistency).
import src.map_placeholders as map_placeholders  # type: ignore

# _CLASS_HIERARCHY_SCAN_CACHE is deliberately NOT re-exported here: it's a
# module-level global that _scan_class_hierarchy() rebinds via `global` in
# class_discovery.py's own namespace, so a `from ... import` snapshot of it
# here would never see updates after the first cache population -- the same
# "from-import binds a value, not a live reference" trap CLAUDE.md documents
# for sys.modules patching. Nothing outside class_discovery.py reads it
# (verified via repo-wide grep); if that ever needs to change, add a
# get_class_hierarchy_scan_cache() accessor instead of re-exporting the
# variable directly.
from utils.mapgen.class_discovery import (
    _DEBUG_ONLY_NPC_CLASSES,
    _get_module_paths_for_class,
    _scan_class_hierarchy,
    _src_tree_signature,
    build_class_hierarchy,
    filter_classes,
    get_class_hierarchy,
    get_import_path,
    parse_module_classes,
    parse_type_hint,
)
from utils.mapgen.widgets import (
    _PROPERTY_DESCRIPTION_FALLBACK,
    _PROPERTY_DESCRIPTIONS,
    _PROPERTY_GROUP_MAP,
    _PROPERTY_GROUPS_ORDER,
    _grouped_field_layout,
    _property_description,
    _property_group,
    create_bool_entry,
    create_button,
    create_hierarchical_selector,
    create_separator,
    create_text_entry,
    get_editable_params,
)
from utils.mapgen.property_dialog import (
    TagListFrame,
    _build_hierarchy_chooser,
    _get_editable_properties,
    _is_event_like,
    _is_merchant_like,
    _open_bulk_class_chooser,
    add_element,
    create_element_frame,
    duplicate_element,
    edit_element,
    open_chooser,
    open_class_type_chooser,
    open_property_dialog,
    open_single_class_type_chooser,
    refresh_tags,
    remove_element,
    show_class_type_hierarchy_chooser,
    show_hierarchy_chooser,
)
from utils.mapgen.tile_editor import TileEditorWindow
from utils.mapgen.editor import (
    _CONVERT_ELEMENTS_EXPECTED_DROPS,
    _dropped_fields_for_conversion,
    _get_last_map_file,
    compute_convert_elements_report,
    MapEditor,
)

__all__ = [
    "tk",
    "ttk",
    "messagebox",
    "filedialog",
    "Event",
    "Merchant",
    "map_placeholders",
    "project_root",
    "src_root",
    "MapSerializationError",
    "DIRECTION_DELTAS",
    "RECIPROCAL_DIRECTIONS",
    "parse_type_hint",
    "get_class_hierarchy",
    "_src_tree_signature",
    "_scan_class_hierarchy",
    "_get_module_paths_for_class",
    "get_import_path",
    "parse_module_classes",
    "build_class_hierarchy",
    "_DEBUG_ONLY_NPC_CLASSES",
    "filter_classes",
    "create_hierarchical_selector",
    "create_button",
    "create_separator",
    "_PROPERTY_DESCRIPTIONS",
    "_PROPERTY_DESCRIPTION_FALLBACK",
    "_property_description",
    "_PROPERTY_GROUPS_ORDER",
    "_PROPERTY_GROUP_MAP",
    "_property_group",
    "_grouped_field_layout",
    "get_editable_params",
    "create_text_entry",
    "create_bool_entry",
    "_get_editable_properties",
    "TagListFrame",
    "create_element_frame",
    "_is_event_like",
    "_is_merchant_like",
    "add_element",
    "duplicate_element",
    "edit_element",
    "remove_element",
    "refresh_tags",
    "open_chooser",
    "_build_hierarchy_chooser",
    "show_hierarchy_chooser",
    "open_class_type_chooser",
    "open_single_class_type_chooser",
    "show_class_type_hierarchy_chooser",
    "_open_bulk_class_chooser",
    "open_property_dialog",
    "TileEditorWindow",
    "_get_last_map_file",
    "_CONVERT_ELEMENTS_EXPECTED_DROPS",
    "_dropped_fields_for_conversion",
    "compute_convert_elements_report",
    "MapEditor",
]
