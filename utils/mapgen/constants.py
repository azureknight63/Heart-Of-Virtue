"""Shared constants, the custom serialization exception, and the sys.path/
project-root bootstrap for the utils.mapgen package.

This module is imported first by utils/mapgen/__init__.py (and directly by
every sibling submodule that needs project_root), so its sys.path setup runs
before any submodule's bare `from npc import ...` / `from events import ...`
engine imports.
"""
import os
import sys
from typing import Dict, List, Tuple

# Ensure the project root and src/ are on sys.path for imports. Computed
# relative to this package's own location (utils/mapgen/constants.py is
# three directories below the project root), NOT re-derived independently
# in every submodule that needs it -- a previous version of this code (when
# it all lived in one utils/map_generator.py file) re-derived "project root"
# via `os.path.dirname(os.path.dirname(__file__))`/`Path(__file__).resolve()`
# in four different places, all of which depended on that file being
# directly inside utils/; splitting into a package would have silently
# broken every one of them by one directory level. Importing this single
# project_root constant everywhere instead removes that whole class of bug.
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
src_root = os.path.join(project_root, "src")
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if src_root not in sys.path:
    sys.path.insert(0, src_root)


class MapSerializationError(Exception):
    def __init__(
        self,
        *,
        tile: Tuple[int, int] | None = None,
        category: str | None = None,
        index: int | None = None,
        attribute: str | None = None,
        object_type: str | None = None,
        object_repr: str | None = None,
        original: Exception | None = None,
        note: str | None = None,
    ):
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


# 8-direction grid deltas and their opposite-direction mapping, shared by every
# exit-connecting/adjacency helper in the editor (auto_connect_exits,
# draw_exits, remove_selected_tile, TileEditorWindow). Order is significant:
# it drives the display order of the Exits/Blocked listboxes.
DIRECTION_DELTAS: Dict[str, Tuple[int, int]] = {
    "north": (0, -1),
    "south": (0, 1),
    "west": (-1, 0),
    "east": (1, 0),
    "northeast": (1, -1),
    "northwest": (-1, -1),
    "southeast": (1, 1),
    "southwest": (-1, 1),
}

RECIPROCAL_DIRECTIONS: Dict[str, str] = {
    "north": "south",
    "south": "north",
    "west": "east",
    "east": "west",
    "northeast": "southwest",
    "northwest": "southeast",
    "southeast": "northwest",
    "southwest": "northeast",
}

