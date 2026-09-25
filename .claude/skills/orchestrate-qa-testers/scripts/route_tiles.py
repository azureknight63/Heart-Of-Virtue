"""route_tiles.py — print a QA-brief-ready tile list from a map's JSON.

    python route_tiles.py <map name or path> [--tiles "1,2 2,2 ..."] [--events] [--md]

Why this exists: tester-roles.md says the thing that made briefs work was
"tile lists with titles and occupants ... e.g. (1,2) HighLedge [Rock Rumbler]"
— naming the destination tile saves a tester the BFS. Hand-copying that from
the map JSON goes stale; this script derives it straight from
src/resources/maps/<map>.json every time.

Each tile prints as:

    (x,y) Title [occupant1, occupant2, ...] exits: north->(x,y2), east->other_map@(x3,y3)

- Occupants are NPCs, enemies, items and objects placed directly on the tile
  (not ones a spawner event creates at runtime — those show up with --events).
  Display name is the entity's ``props.name`` when the JSON gives one,
  otherwise its ``__class__``.
- Exits show the direction and, where the JSON says so, where it leads: an
  in-map adjacent tile (computed from the standard 8-direction deltas and
  confirmed to exist in this map), or an explicit teleport target from a
  ``Passageway`` object on the tile (``teleport_map``/``teleport_tile``).
  A direction with neither is printed bare — the JSON just doesn't say.
- ``--events`` appends the tile's own event class names (``NPCSpawnerEvent``,
  etc.) — this is separate from occupants because a spawner's target class
  isn't a real occupant until it fires.
- ``--tiles "x,y x,y ..."`` prints only the named tiles, in that order — a
  route through the map, not a full survey.
- ``--md`` prints a GitHub-flavored markdown table instead of plain lines.

Map JSON schema varies across files (verified across all files under
src/resources/maps/*.json as of 2026-09-25): tiles are keyed by "(x, y)" or
"(x,y)" strings (a top-level "metadata" key, when present, is skipped); a
tile's "title" may be absent; "npcs"/"items"/"objects" may be absent or
empty; an object's props may lack "name" (falls back to __class__); a
Passageway's teleport fields are optional. Every lookup below is defensive
(``.get`` with a default) so a missing field prints as absent, not a crash.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4])
MAPS_DIR = ROOT / "src" / "resources" / "maps"

_TILE_KEY_RE = re.compile(r"^\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)$")

# Standard 8-direction deltas used by src/universe.py's exit whitelist.
_DIRECTION_DELTAS = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
    "northeast": (1, -1),
    "northwest": (-1, -1),
    "southeast": (1, 1),
    "southwest": (-1, 1),
}


def resolve_map_path(map_arg):
    """Resolve a map name or path argument to an existing map JSON file."""
    candidate = Path(map_arg)
    if candidate.is_file():
        return candidate
    name = map_arg
    if not name.lower().endswith(".json"):
        name = name + ".json"
    candidate = MAPS_DIR / name
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(
        f"no map found for {map_arg!r} (tried {candidate} and the literal path)"
    )


def load_tiles(map_path):
    """Load a map JSON file and return {(x, y): tile_dict}, skipping non-tile keys."""
    with open(map_path, encoding="utf-8") as f:
        data = json.load(f)
    tiles = {}
    for key, value in data.items():
        m = _TILE_KEY_RE.match(key)
        if not m or not isinstance(value, dict):
            continue
        tiles[(int(m.group(1)), int(m.group(2)))] = value
    return tiles


def _entity_name(entry):
    """Display name for an NPC/item/object entry: props.name, else __class__."""
    if not isinstance(entry, dict):
        return str(entry)
    props = entry.get("props") or {}
    name = props.get("name")
    if name:
        return name
    return entry.get("__class__") or "Unknown"


def _object_label(entry):
    """Display label for an object entry; appends a Passageway's destination."""
    label = _entity_name(entry)
    if not isinstance(entry, dict):
        return label
    if entry.get("__class__") == "Passageway":
        props = entry.get("props") or {}
        tmap = props.get("teleport_map")
        ttile = props.get("teleport_tile")
        if tmap and isinstance(ttile, (list, tuple)) and len(ttile) == 2:
            label = f"{label} -> {tmap}@({ttile[0]},{ttile[1]})"
    return label


def tile_occupants(tile_data):
    """Occupant display names: NPCs, items, then objects, in that order."""
    occupants = []
    for entry in tile_data.get("npcs") or []:
        occupants.append(_entity_name(entry))
    for entry in tile_data.get("items") or []:
        occupants.append(_entity_name(entry))
    for entry in tile_data.get("objects") or []:
        occupants.append(_object_label(entry))
    return occupants


def tile_event_classes(tile_data):
    """Event class names attached directly to the tile."""
    names = []
    for entry in tile_data.get("events") or []:
        if isinstance(entry, dict):
            names.append(entry.get("__class__") or "UnknownEvent")
        else:
            names.append(str(entry))
    return names


def _passageway_targets(tile_data):
    """Map of direction-independent Passageway labels, for exit annotation fallback."""
    targets = []
    for entry in tile_data.get("objects") or []:
        if isinstance(entry, dict) and entry.get("__class__") == "Passageway":
            props = entry.get("props") or {}
            tmap = props.get("teleport_map")
            ttile = props.get("teleport_tile")
            if tmap and isinstance(ttile, (list, tuple)) and len(ttile) == 2:
                targets.append(f"{tmap}@({ttile[0]},{ttile[1]})")
    return targets


def tile_exits(coord, tile_data, all_tiles):
    """List of "direction" or "direction->destination" strings for a tile's exits."""
    x, y = coord
    exits = tile_data.get("exits") or []
    passageway_targets = _passageway_targets(tile_data)
    labeled = []
    for direction in exits:
        delta = _DIRECTION_DELTAS.get(direction)
        dest = None
        if delta:
            neighbor = (x + delta[0], y + delta[1])
            if neighbor in all_tiles:
                dest = f"({neighbor[0]},{neighbor[1]})"
        if dest is None and passageway_targets:
            # A tile with a Passageway object and no in-map neighbor for this
            # direction: the passageway is the most likely destination for it
            # (single-passageway tiles are the common case in this codebase).
            if len(passageway_targets) == 1:
                dest = passageway_targets[0]
        labeled.append(f"{direction}->{dest}" if dest else direction)
    return labeled


def format_tile_line(coord, tile_data, all_tiles, show_events):
    x, y = coord
    title = tile_data.get("title") or tile_data.get("id") or f"tile_{x}_{y}"
    occupants = tile_occupants(tile_data)
    line = f"({x},{y}) {title}"
    if occupants:
        line += f" [{', '.join(occupants)}]"
    exits = tile_exits(coord, tile_data, all_tiles)
    if exits:
        line += f" exits: {', '.join(exits)}"
    if show_events:
        events = tile_event_classes(tile_data)
        if events:
            line += f" events: {', '.join(events)}"
    return line


def format_tile_row(coord, tile_data, all_tiles, show_events):
    x, y = coord
    title = tile_data.get("title") or tile_data.get("id") or f"tile_{x}_{y}"
    occupants = ", ".join(tile_occupants(tile_data)) or "—"
    exits = ", ".join(tile_exits(coord, tile_data, all_tiles)) or "—"
    row = [f"({x},{y})", title, occupants, exits]
    if show_events:
        row.append(", ".join(tile_event_classes(tile_data)) or "—")
    return row


def print_markdown_table(coords, all_tiles, show_events):
    headers = ["Tile", "Title", "Occupants", "Exits"]
    if show_events:
        headers.append("Events")
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for coord in coords:
        tile_data = all_tiles.get(coord)
        if tile_data is None:
            row = [f"({coord[0]},{coord[1]})", "*(not found in map)*", "", ""]
            if show_events:
                row.append("")
            print("| " + " | ".join(row) + " |")
            continue
        row = format_tile_row(coord, tile_data, all_tiles, show_events)
        print("| " + " | ".join(row) + " |")


def parse_tiles_arg(tiles_arg):
    """Parse "x,y x,y ..." into an ordered list of (x, y) tuples."""
    coords = []
    for chunk in tiles_arg.split():
        parts = chunk.split(",")
        if len(parts) != 2:
            raise ValueError(f"bad tile spec {chunk!r}, expected x,y")
        coords.append((int(parts[0]), int(parts[1])))
    return coords


def build_arg_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map", help="map name (e.g. grondia) or a path to its JSON file")
    parser.add_argument(
        "--tiles",
        help='only print these tiles, in order, e.g. --tiles "1,2 2,2 3,2"',
    )
    parser.add_argument("--events", action="store_true", help="also list tile event classes")
    parser.add_argument("--md", action="store_true", help="print a markdown table")
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    map_path = resolve_map_path(args.map)
    all_tiles = load_tiles(map_path)

    if args.tiles:
        coords = parse_tiles_arg(args.tiles)
    else:
        coords = sorted(all_tiles.keys())

    if args.md:
        print_markdown_table(coords, all_tiles, args.events)
        return 0

    missing = 0
    for coord in coords:
        tile_data = all_tiles.get(coord)
        if tile_data is None:
            print(f"({coord[0]},{coord[1]}) *(not found in {map_path.name})*")
            missing += 1
            continue
        print(format_tile_line(coord, tile_data, all_tiles, args.events))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
