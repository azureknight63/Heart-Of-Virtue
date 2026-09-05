"""Regression coverage for Jambo's tent action list and the eastern-descent ->
nomad-camp -> Jambo's tent -> exit navigation route.

Issue: Jambo's Tent passageway exposed an "Enter", "Jambo" and "Tent" action; it
should expose only "Enter". The "Jambo"/"Tent" verbs come from the name-word
aliases ``Passageway.__init__`` synthesizes from the name "Jambo's Tent" and
which were persisted into the map's serialized ``keywords`` array. The frontend
(``actionKeywords``) hides anything in ``action_aliases`` but NOT these, so they
rendered as extra buttons that misled navigation.

This test loads the REAL map JSON through the engine loader (the same path the
game boots) and:
  * proves the serialized ``keywords`` for the Jambo's Tent passage no longer
    carry the name-word aliases ``jambo``/``tent``,
  * proves the *displayed* actions (keywords minus action_aliases) are exactly
    ``["enter"]``,
  * proves the complete enter/exit route lands on the expected map name and
    (x, y) after every passageway traversal (east-descent -> nomad-camp ->
    jambos-tent -> back to nomad-camp -> back to eastern-descent).

The route-coordinate assertions encode the diagnosis: the teleport coordinates
are correct; there is no backend coordinate/source regression. Only the
serialized keyword data needed fixing.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.universe import Universe
from src.player._movement import PlayerMovementMixin
from src.narration import capture_narration

MAP_DIR = ROOT / "src" / "resources" / "maps"
MAP_FILES = [
    "eastern-descent.json",
    "eastern-descent-nomad-camp.json",
    "eastern-descent-jambos-tent.json",
]


class _MinPlayer(PlayerMovementMixin):
    """Minimal Player stand-in sufficient for Passageway._commit_teleport /
    PlayerMovementMixin.teleport (drop_merchandise_items, map, location, room)."""

    def __init__(self, universe):
        self.universe = universe
        self.map = None
        self.location_x = None
        self.location_y = None
        self.current_room = None

    def drop_merchandise_items(self):
        return None


def _build_universe():
    universe = Universe()
    player = _MinPlayer(universe)
    universe.player = player
    for m in MAP_FILES:
        universe._load_single_json_map(player, MAP_DIR / m)
    return universe, player


def _find_passage(map_dict, name):
    for coord, tile in map_dict.items():
        if not isinstance(coord, tuple):
            continue
        for obj in getattr(tile, "objects_here", []) or []:
            if (
                getattr(obj, "name", None) == name
                and getattr(obj, "__class__", None).__name__ == "Passageway"
            ):
                return coord, tile, obj
    return None


def _displayed_actions(pw):
    """The buttons the frontend renders for a PASSAGEWAY, and only a passageway.

    ``actionKeywords`` (frontend/src/components/InteractPanel.jsx) applies four
    rules. Two of them can fire on a passageway, and those two are reproduced
    here:

    * drop anything the engine lists in ``action_aliases``;
    * de-duplicate case-insensitively, keeping the first spelling.

    The other two are deliberately NOT mirrored, because no passageway can
    reach them: the container rule needs ``is_container`` (a Container thing,
    never a Passageway), and the talk/chat alias collapse needs a chat keyword
    (served by NPCs, never by a passageway). Copying them would put a second,
    untested implementation of the chat collapse in Python, free to drift from
    the one that matters. If a passageway ever grows either shape, this helper
    stops describing the frontend and must be revisited rather than trusted.
    """
    seen = set()
    out = []
    for kw in pw.keywords:
        if kw in pw.action_aliases:
            continue
        # Case-folded, matching the JS `String(keyword).toLowerCase()`: the
        # rendered list collapses 'Enter' and 'enter' into one button, so a
        # case-sensitive check here would claim two where the player sees one.
        folded = str(kw).lower()
        if folded in seen:
            continue
        seen.add(folded)
        out.append(kw)
    return out


@pytest.fixture(scope="module")
def universe_player():
    return _build_universe()


def test_jambos_tent_serialized_keywords_have_no_name_word_aliases():
    """The serialized Jambo's Tent passage must not carry the 'jambo'/'tent'
    name-word aliases that rendered as extra frontend buttons."""
    raw = json.loads((MAP_DIR / "eastern-descent-nomad-camp.json").read_text(encoding="utf-8"))
    for coord, tile in raw.items():
        if not isinstance(tile, dict):
            continue
        for obj in tile.get("objects", []):
            if obj.get("props", {}).get("name") == "Jambo's Tent":
                keywords = obj["props"].get("keywords", [])
                assert "jambo" not in keywords, keywords
                assert "tent" not in keywords, keywords
                return
    pytest.fail("Jambo's Tent passage not found in serialized nomad-camp map")


def test_jambos_tent_displayed_actions_are_only_enter(universe_player):
    """After loading through the real engine, the only displayed action for
    Jambo's Tent is 'enter' (the frontend hides action_aliases + dups)."""
    universe, _ = universe_player
    nomad = next(a for a in universe.maps if a.get("name") == "eastern-descent-nomad-camp")
    res = _find_passage(nomad, "Jambo's Tent")
    assert res, "Jambo's Tent passage not loaded"
    pw = res[2]
    assert _displayed_actions(pw) == ["enter"], _displayed_actions(pw)


def test_full_enter_exit_route_coordinates(universe_player):
    """Reproduce the user's sequence and verify map name + (x, y) after every
    passageway traversal. Coordinates are correct; this encodes the diagnosis
    that there is no backend teleport regression."""
    universe, player = universe_player

    ed = next(a for a in universe.maps if a.get("name") == "eastern-descent")
    # Presence-only checks: StopIteration here means the map failed to load.
    next(a for a in universe.maps if a.get("name") == "eastern-descent-nomad-camp")
    next(a for a in universe.maps if a.get("name") == "eastern-descent-jambos-tent")

    # Start on the eastern-descent tile that holds the Camp Entrance passage.
    start = _find_passage(ed, "Camp Entrance")
    assert start, "Camp Entrance passage not found in eastern-descent"
    coord, tile, _ = start
    player.map = ed
    player.location_x, player.location_y = coord
    player.current_room = tile

    def step(target_name, expected_map, expected_coords):
        res = _find_passage(player.map, target_name)
        assert res, f"{target_name} not found in {player.map['name']}"
        pw = res[2]
        with capture_narration():
            pw._commit_teleport(player)
        got = (player.map["name"], (player.location_x, player.location_y))
        assert got == (expected_map, expected_coords), (target_name, got)

    # eastern-descent -> nomad-camp
    step("Camp Entrance", "eastern-descent-nomad-camp", (3, 0))
    # nomad-camp -> Jambo's tent
    step("Jambo's Tent", "eastern-descent-jambos-tent", (2, 2))
    # Jambo's tent -> back to nomad-camp (exit)
    step("Tent Flap", "eastern-descent-nomad-camp", (3, 0))
    # nomad-camp -> back to eastern-descent (exit the camp)
    step("Camp Boundary", "eastern-descent", (3, 6))
