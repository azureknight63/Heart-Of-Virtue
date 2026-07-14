"""Data-only (JSON) save format prototype for Heart of Virtue (issue #13, Phase 3).

Pickle saves execute arbitrary code on load (see :mod:`src.secure_pickle` and
``SECURITY.md``). The long-term fix is a **data-only** format that contains only
primitive types -- no pickled objects, no code execution on load. This module is
the *experimental prototype* of that format, gated behind the ``HOV_SAVE_V2``
feature flag.

Scope (deliberately a subset, per the issue): it captures the player's scalar
state (stats, level, HP/fatigue, gold, position, preferences), the names of the
current map/room, known-move names, and the universe story flags. It does **not**
yet capture the full world/tile graph, NPC placements, or combat state, so it is
not a drop-in replacement for pickle -- it is a forward-compatible on-disk schema
plus a one-shot converter that runs after a successful (trusted) pickle load.

Version negotiation: every document carries ``format_version`` (bumped on
breaking changes) and ``schema_version`` (bumped on additive changes). Loaders
reject unknown ``format_version`` values and, in strict validation, unknown
top-level keys.
"""

import io
import os
import json
import logging

logger = logging.getLogger(__name__)

# Bumped on breaking layout changes; loaders reject versions they don't know.
SAVE_FORMAT_VERSION = 2
# Bumped on additive (backward-compatible) field additions.
SAVE_SCHEMA_VERSION = 1

# Feature flag: enables writing the v2 sidecar alongside pickle saves.
SAVE_V2_ENV_VAR = "HOV_SAVE_V2"

# Top-level keys a valid v2 document may contain. Strict validation rejects any
# key outside this set (defends against smuggled/unexpected data).
_ALLOWED_TOP_LEVEL_KEYS = frozenset({
    "format_version", "schema_version", "player", "world",
})

# Minimum keys that must be present for a document to be considered valid.
_REQUIRED_TOP_LEVEL_KEYS = frozenset({"format_version", "player", "world"})
_REQUIRED_PLAYER_KEYS = frozenset({"name", "level", "hp", "maxhp"})
_REQUIRED_WORLD_KEYS = frozenset({"map_name"})

# Player scalar attributes copied verbatim (name -> default when absent).
_PLAYER_SCALARS = {
    "name": "Jean",
    "level": 1,
    "exp": 0,
    "exp_to_level": 150,
    "hp": 100,
    "maxhp": 100,
    "fatigue": 150,
    "maxfatigue": 150,
    "heat": 1.0,
    "protection": 0,
    "time_elapsed": 0,
    "location_x": 0,
    "location_y": 0,
    "pending_attribute_points": 0,
}

# Primary stats persisted with their *_base counterparts.
_PLAYER_STATS = (
    "strength", "finesse", "speed", "endurance",
    "charisma", "intelligence", "faith",
)


class SaveSchemaError(Exception):
    """Raised when a data-only save fails schema validation."""


def save_v2_enabled():
    """Return True when the v2 sidecar writer is enabled via env flag."""
    return os.environ.get(SAVE_V2_ENV_VAR, "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _map_name(player):
    _map = getattr(player, "map", None)
    if isinstance(_map, dict):
        return _map.get("name", "Unknown")
    return getattr(_map, "name", "Unknown")


def _room_name(player):
    room = getattr(player, "current_room", None)
    if room is None:
        return None
    return getattr(room, "name", None) or type(room).__name__


def _story_flags(player):
    universe = getattr(player, "universe", None)
    story = getattr(universe, "story", None)
    if isinstance(story, dict):
        # Story values are already primitive (strings/ints); copy defensively.
        return {str(k): v for k, v in story.items()}
    return {}


def player_to_data(player):
    """Extract a data-only (primitive) snapshot of ``player`` state.

    Returns a JSON-serializable dict conforming to the v2 schema. Only the
    documented subset is captured; unknown/complex attributes are dropped.
    """
    from src.inventory_utils import get_gold

    stats = {}
    for stat in _PLAYER_STATS:
        stats[stat] = getattr(player, stat, 10)
        stats[f"{stat}_base"] = getattr(player, f"{stat}_base", stats[stat])

    inventory = []
    for item in getattr(player, "inventory", []) or []:
        name = getattr(item, "name", None)
        if name is None:
            continue
        entry = {"name": name, "type": getattr(item, "type", None)}
        count = getattr(item, "count", None)
        if count is not None:
            entry["count"] = count
        inventory.append(entry)

    player_data = {key: getattr(player, key, default)
                   for key, default in _PLAYER_SCALARS.items()}
    player_data["stats"] = stats
    player_data["gold"] = get_gold(getattr(player, "inventory", []) or [])
    player_data["inventory"] = inventory
    player_data["known_moves"] = [
        getattr(m, "name", type(m).__name__)
        for m in getattr(player, "known_moves", []) or []
    ]
    prefs = getattr(player, "preferences", None)
    player_data["preferences"] = dict(prefs) if isinstance(prefs, dict) else {}

    return {
        "format_version": SAVE_FORMAT_VERSION,
        "schema_version": SAVE_SCHEMA_VERSION,
        "player": player_data,
        "world": {
            "map_name": _map_name(player),
            "room_name": _room_name(player),
            "story_flags": _story_flags(player),
        },
    }


def validate_save_data(data, *, strict=False):
    """Validate a decoded v2 document. Returns ``data`` or raises.

    Args:
        data: The decoded JSON object.
        strict: When True, reject unknown top-level keys as well.

    Raises:
        SaveSchemaError: The document is malformed or the wrong version.
    """
    if not isinstance(data, dict):
        raise SaveSchemaError("Save document must be a JSON object")

    version = data.get("format_version")
    if version != SAVE_FORMAT_VERSION:
        raise SaveSchemaError(
            f"Unsupported save format_version {version!r} "
            f"(expected {SAVE_FORMAT_VERSION})"
        )

    missing = _REQUIRED_TOP_LEVEL_KEYS - data.keys()
    if missing:
        raise SaveSchemaError(f"Save is missing required keys: {sorted(missing)}")

    if strict:
        extra = data.keys() - _ALLOWED_TOP_LEVEL_KEYS
        if extra:
            raise SaveSchemaError(f"Save has unexpected top-level keys: {sorted(extra)}")

    player = data["player"]
    if not isinstance(player, dict):
        raise SaveSchemaError("'player' must be an object")
    p_missing = _REQUIRED_PLAYER_KEYS - player.keys()
    if p_missing:
        raise SaveSchemaError(f"Player is missing required keys: {sorted(p_missing)}")

    world = data["world"]
    if not isinstance(world, dict):
        raise SaveSchemaError("'world' must be an object")
    w_missing = _REQUIRED_WORLD_KEYS - world.keys()
    if w_missing:
        raise SaveSchemaError(f"World is missing required keys: {sorted(w_missing)}")

    return data


def dumps_v2(player, *, indent=2):
    """Serialize ``player`` to a v2 JSON string."""
    return json.dumps(player_to_data(player), indent=indent, sort_keys=True)


def loads_v2(text, *, strict=False):
    """Parse and validate a v2 JSON string, returning the data dict."""
    return validate_save_data(json.loads(text), strict=strict)


def write_v2_file(player, path):
    """Write ``player`` state as a v2 JSON document to ``path``."""
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(dumps_v2(player))
    logger.debug("Wrote data-only save to %s", path)
    return path


def read_v2_file(path, *, strict=False):
    """Read and validate a v2 JSON document from ``path``."""
    with io.open(path, "r", encoding="utf-8") as f:
        return loads_v2(f.read(), strict=strict)


def apply_data_to_player(player, data, *, strict=False):
    """Restore the captured scalar subset of ``data`` onto ``player`` in place.

    This is a *partial* restore: it sets the scalar/stat fields and story flags
    that the prototype captures. Inventory objects, the world/tile graph, and
    combat state are NOT reconstructed here (they still require the pickle path).
    Returns the mutated ``player``.
    """
    validate_save_data(data, strict=strict)
    p = data["player"]
    for key in _PLAYER_SCALARS:
        if key in p:
            setattr(player, key, p[key])
    for stat, value in (p.get("stats") or {}).items():
        setattr(player, stat, value)
    if isinstance(p.get("preferences"), dict):
        player.preferences = dict(p["preferences"])

    story = (data.get("world") or {}).get("story_flags")
    universe = getattr(player, "universe", None)
    if isinstance(story, dict) and getattr(universe, "story", None) is not None:
        universe.story.update(story)
    return player


def convert_pickle_save_to_v2(player, out_path):
    """One-shot conversion: write a v2 sidecar after a trusted pickle load.

    Intended to be called immediately after a successful pickle load so the save
    is progressively migrated to the safe format. The pickle file is left
    untouched; the v2 document is written alongside it.
    """
    write_v2_file(player, out_path)
    logger.info(
        "Converted legacy pickle save to data-only format at %s "
        "(pickle format is deprecated; see SECURITY.md)",
        out_path,
    )
    return out_path
