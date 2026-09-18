"""#613: Gorran waits at the pools threshold until the King Slime falls.

``Ch02GorranAtPools`` narrates that Gorran "had come to the threshold and no
further" and seats him "at the entrance to the atrium", with Jean coming up
beside him -- so the fiction puts them both on the tile the scene plays on.
The code seated him one tile further in, *inside* the Atrium, and appended him
there without taking him off the tile he was standing on, so he stood in two
rooms at once: the Grondia-side tile he last followed Jean to (the passage
into the pools teleports, and ``teleport`` does not recall the party) and the
Atrium.

Everything here runs on real engine objects -- a real ``Player``, real
``MapTile``s for every tile the shipped pools map authors, a real ``Gorran``
-- and follows the party the way ``GameService.move_player`` does, through
``Player.recall_friends``. Mocks agreeing with mocks is how this stayed
invisible: the atrium placement was asserted against a ``Mock`` tile whose
``npcs_here`` nobody else read.

The threshold coordinate is derived from the shipped map -- the tile it
authors ``Ch02GorranAtPools`` onto -- never typed here, so moving the
placement moves the expectation with it. ch02's own ``THRESHOLD_COORDS`` is
read only by the two tests that pin it to that tile, and read through the
module at run time: imported by name, a checkout without it fails this whole
file at collection and never shows which behaviour regressed.

#577 (Gorran rejoins when the King Slime falls) is held to its contract in
the last class: the aftermath must still find the waiting Gorran and put him
back in ``combat_list_allies``, wherever the wait now happens.
"""

from unittest.mock import patch

import pytest

import src.npc as npc
import src.story.ch02 as ch02
from src.player import Player
from src.story.ch02 import (
    ATRIUM_COORDS,
    AfterDefeatingKingSlime,
    Ch02GorranAtPools,
)
from src.tiles import MapTile
from src.universe import Universe
from tests._ch02_fixtures import (
    POOLS_MAP_NAME,
    arena_coord,
    pools_coords,
    threshold_coord,
)

#: The map Jean walks in from. Gorran is standing on it when the passage
#: teleports Jean into the pools, so it is where a Gorran who is never taken
#: off his old tile is left behind as a second copy.
OUTSIDE_MAP_NAME = "grondia"
OUTSIDE_COORD = (7, 9)


class PoolsWorld:
    """A real Player standing on the pools threshold with Gorran in tow."""

    def __init__(self):
        self.player = Player()
        self.player.skip_dialog = True
        universe = Universe(player=self.player)
        self.player.universe = universe

        self.pools = {"name": POOLS_MAP_NAME}
        for x, y in pools_coords():
            self.pools[(x, y)] = MapTile(
                universe, self.pools, x, y, description=f"pools ({x}, {y})"
            )
        self.outside = {"name": OUTSIDE_MAP_NAME}
        self.outside[OUTSIDE_COORD] = MapTile(
            universe, self.outside, *OUTSIDE_COORD, description="the way in"
        )
        universe.maps = [self.outside, self.pools]

        # Gorran is where he last followed Jean to: the Grondia-side tile.
        # The passage teleports Jean into the pools and ``teleport`` never
        # recalls the party, so this is the state the scene actually meets.
        self.gorran = npc.Gorran()
        self.gorran.current_room = self.outside[OUTSIDE_COORD]
        self.outside[OUTSIDE_COORD].npcs_here.append(self.gorran)
        self.player.combat_list_allies = [self.player, self.gorran]

        self.threshold_coord = threshold_coord()
        self.threshold = self.pools[self.threshold_coord]
        # The passage into the pools is a Passageway, so arriving is a
        # ``Player.teleport`` -- which does not recall the party. Gorran is
        # left standing where he was, and the scene is what has to move him.
        self._stand_on(self.pools, self.threshold_coord)

    def _stand_on(self, game_map, coord):
        self.player.map = game_map
        self.player.location_x, self.player.location_y = coord
        self.player.current_room = game_map[coord]

    def enter(self, game_map, coord):
        """Put Jean on ``coord`` and follow the party there, the way
        ``GameService.move_player`` does (``Player.recall_friends``)."""
        self._stand_on(game_map, coord)
        if len(self.player.combat_list_allies) > 1:
            with patch("src.player._movement.narrate"):
                self.player.recall_friends()

    def run_threshold_scene(self):
        event = Ch02GorranAtPools(player=self.player, tile=self.threshold)
        self.threshold.events_here.append(event)
        with (
            patch("src.story.ch02.print_slow"),
            patch("src.story.ch02.await_input"),
            patch("src.story.ch02.time.sleep"),
        ):
            event.check_conditions()
        return event

    def rooms_holding_gorran(self):
        """Every coordinate, in either map, whose ``npcs_here`` holds a
        Gorran -- the room state a player actually sees."""
        return {
            (game_map["name"], coord)
            for game_map in (self.outside, self.pools)
            for coord, tile in game_map.items()
            if isinstance(coord, tuple)
            and any(type(n).__name__ == "Gorran" for n in tile.npcs_here)
        }


@pytest.fixture
def world():
    return PoolsWorld()


@pytest.fixture
def waited(world):
    """The world after the threshold scene has played."""
    world.run_threshold_scene()
    return world


def test_the_threshold_constant_is_the_tile_the_map_plays_the_scene_on():
    """``THRESHOLD_COORDS`` is where the shipped map authors
    ``Ch02GorranAtPools`` -- the tile Jean is standing on when the scene
    seats Gorran beside him. Derived from the map, not restated from the
    engine, so a placement that moves without the constant fails here."""
    assert ch02.THRESHOLD_COORDS == threshold_coord()


def test_the_threshold_is_not_the_atrium():
    """The whole of #613: the scene leaves him at the entrance, and the
    Atrium is one tile past it. A fix that merely renamed the constant
    would pass everything else in this file."""
    assert ch02.THRESHOLD_COORDS != ATRIUM_COORDS


class TestGorranIsLeftAtTheThreshold:
    def test_he_stands_in_exactly_one_room(self, waited):
        assert waited.rooms_holding_gorran() == {
            (POOLS_MAP_NAME, waited.threshold_coord)
        }

    def test_he_is_off_the_tile_he_came_from(self, waited):
        """Appending him to the wait tile without taking him off his old one
        left a second Gorran standing in Grondia for the rest of the game."""
        assert waited.gorran not in waited.outside[OUTSIDE_COORD].npcs_here

    def test_the_engine_agrees_on_which_room_he_is_in(self, waited):
        """``current_room`` is what ``recall_friends`` reads to take a
        follower off his old tile; a placement that only sets ``tile``
        leaves the engine pointing at the room he left."""
        assert waited.gorran.current_room is waited.threshold

    def test_he_has_left_the_party(self, waited):
        """``combat_list_allies`` is the single source of truth for the
        status party, the battle allies and tile-following (#577), so
        staying in it is what would walk him into the pools fights."""
        assert waited.gorran not in waited.player.combat_list_allies


class TestHeIsInNoRoomJeanExploresAlone:
    """Jean walks the whole pools map -- every tile past the threshold,
    including the arena -- and Gorran is in none of those rooms."""

    def test_no_interior_tile_ever_holds_him(self, waited):
        interior = [coord for coord in pools_coords() if coord != waited.threshold_coord]
        assert interior, "the pools map authors nothing past the threshold"
        seen = set()
        for coord in interior:
            waited.enter(waited.pools, coord)
            seen |= {
                room for room in waited.rooms_holding_gorran()
                if room != (POOLS_MAP_NAME, waited.threshold_coord)
            }
        assert seen == set(), f"Gorran followed Jean into {sorted(seen)}"

    def test_the_arena_is_among_the_tiles_walked(self):
        """The positive control for the sweep above: the boss room is a
        tile past the threshold, so an empty or threshold-only interior
        would have passed that test vacuously."""
        assert arena_coord() in pools_coords()
        assert arena_coord() != threshold_coord()


class TestTheWaitingGorranSaysHeIsWaiting:
    """The room prints ``npc.idle_message`` (``NPCSerializer`` /
    ``RoomContents.jsx``). The generic wandering line rendered directly
    under the scene that settles him against the arch."""

    def test_his_idle_line_is_not_the_wandering_one(self, waited):
        assert waited.gorran.idle_message != npc.Gorran().idle_message

    def test_the_line_says_he_is_waiting(self, waited):
        assert "wait" in waited.gorran.idle_message.lower()

    def test_the_line_still_asks_for_his_name_in_front(self, waited):
        """``RoomContents.jsx`` prepends the NPC's name to an idle line that
        opens with a space, and renders one that does not as-is. Dropping
        the leading space would print a sentence with no subject."""
        assert waited.gorran.idle_message.startswith(" ")
        assert npc.Gorran().idle_message.startswith(" ")


class TestTheAftermathStillFindsHim:
    """#577's contract, held wherever the wait now happens."""

    @pytest.fixture
    def rejoined(self, waited):
        arena = waited.pools[arena_coord()]
        waited.player.level = 3
        with (
            patch("src.story.ch02.print_slow"),
            patch("src.story.ch02.narrate"),
            patch("src.story.ch02.begin_conversation"),
            patch("src.story.ch02.end_conversation"),
            patch("src.story.ch02.say"),
            patch("src.story.ch02.time.sleep"),
        ):
            AfterDefeatingKingSlime(player=waited.player, tile=arena).process()
        return waited

    def test_he_rejoins_the_party(self, rejoined):
        assert rejoined.gorran in rejoined.player.combat_list_allies

    def test_he_stands_in_the_arena_and_nowhere_else(self, rejoined):
        assert rejoined.rooms_holding_gorran() == {(POOLS_MAP_NAME, arena_coord())}

    def test_his_ordinary_idle_line_is_back(self, rejoined):
        assert rejoined.gorran.idle_message == npc.Gorran().idle_message

    def test_he_leaves_the_arena_when_jean_does(self, rejoined):
        """He follows Jean out of the arena instead of being copied out of
        it. ``recall_friends`` takes a follower off his ``current_room``, so
        a rejoin that moved only ``tile`` left that pointing at the room he
        waited in -- and left him listed in the arena for the rest of the
        game, beside the Gorran walking with Jean: the "present on every
        pools tile including the Arena" of the report (#613)."""
        x, y = arena_coord()
        way_out = next(
            (c for c in pools_coords() if abs(c[0] - x) + abs(c[1] - y) == 1), None
        )
        assert way_out is not None, "the pools map authors no tile beside the arena"

        rejoined.enter(rejoined.pools, way_out)

        assert rejoined.rooms_holding_gorran() == {(POOLS_MAP_NAME, way_out)}


def test_a_gorran_who_never_waited_is_listed_in_the_arena_once(world):
    """The aftermath's other source: a Gorran still in the party -- the
    threshold scene never played -- has already followed Jean into the
    arena, so moving him there must not list him in it a second time."""
    arena_xy = arena_coord()
    arena = world.pools[arena_xy]
    world.enter(world.pools, arena_xy)
    assert world.gorran in arena.npcs_here, "precondition: he followed Jean in"

    with (
        patch("src.story.ch02.print_slow"),
        patch("src.story.ch02.narrate"),
        patch("src.story.ch02.begin_conversation"),
        patch("src.story.ch02.end_conversation"),
        patch("src.story.ch02.say"),
        patch("src.story.ch02.time.sleep"),
    ):
        AfterDefeatingKingSlime(player=world.player, tile=arena).process()

    assert [n for n in arena.npcs_here if n is world.gorran] == [world.gorran]
