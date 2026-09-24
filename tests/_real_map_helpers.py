"""Shared stand-ins for tests that load the REAL shipped map JSON (#674).

Four modules (the #582 Eastern Gate arrival, the #663 tent wayfinding, the #664
shop intro and the Jambo's-tent navigation route) each carried their own copy
of a minimal Player, a universe builder and a passage lookup. They load maps
through ``Universe._load_single_json_map`` -- the path the game boots -- so
their crossings run the real ``Passageway.enter`` / ``Player.teleport`` code.

Importing this module builds no universe: every helper is called per test.
"""

from pathlib import Path

from src.player._movement import PlayerMovementMixin
from src.universe import Universe

MAPS_DIR = Path(__file__).resolve().parent.parent / "src" / "resources" / "maps"


class MinPlayer(PlayerMovementMixin):
    """Just enough Player for ``Passageway.enter`` / ``Player.teleport`` on
    real maps: a map, a location, the room, the previous tile (#377), the
    dialog-skip flag and empty combat sides."""

    def __init__(self, universe):
        self.universe = universe
        self.map = None
        self.location_x = None
        self.location_y = None
        self.current_room = None
        self.previous_tile = None
        self.skip_dialog = False
        self.combat_list = []
        self.combat_list_allies = []

    def drop_merchandise_items(self):
        return []


def build_universe(*map_files):
    """A fresh ``Universe`` holding ``map_files`` (names under ``MAPS_DIR``)
    and the ``MinPlayer`` it was loaded for. Returns ``(universe, player)``."""
    universe = Universe()
    player = MinPlayer(universe)
    universe.player = player
    for map_file in map_files:
        universe._load_single_json_map(player, MAPS_DIR / map_file)
    return universe, player


def map_named(universe, name):
    """The loaded map dict whose ``name`` is ``name``."""
    return next(m for m in universe.maps if m.get("name") == name)


def find_passage(tile, name):
    """The Passageway called ``name`` on ``tile``, or None."""
    for obj in getattr(tile, "objects_here", []) or []:
        if type(obj).__name__ == "Passageway" and getattr(obj, "name", None) == name:
            return obj
    return None


def find_passage_on_map(map_dict, name):
    """``(coords, tile, passage)`` for the first Passageway called ``name``
    anywhere on ``map_dict``, or None. Non-tuple keys (``name``, metadata)
    are skipped."""
    for coord, tile in map_dict.items():
        if not isinstance(coord, tuple):
            continue
        passage = find_passage(tile, name)
        if passage is not None:
            return coord, tile, passage
    return None


def spoken(messages, speaker=None):
    """The dialogue messages in ``messages``, optionally from one speaker."""
    return [
        m for m in messages
        if m.get("type") == "dialogue" and (speaker is None or m.get("speaker") == speaker)
    ]


def text_of(messages):
    """Every message's text joined with spaces."""
    return " ".join(m.get("text", "") for m in messages)
