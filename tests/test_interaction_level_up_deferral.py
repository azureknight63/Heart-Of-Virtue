"""The level-up deferral has to hold on the interaction path too.

``_initialize_combat`` emits ``combat:started``, which races the level-up
dialog and leaves the frontend on the combat screen while the allocate calls
still 400 ("Not enough points") -- the counter is right, the client has just
moved on. ``move_player`` and ``process_event_input`` both guard against that
by stashing the enemies on ``player._combat_deferred_enemies`` and letting
``get_combat_status`` resume when the last point is spent.

``interact_with_target`` did not. The gap is reachable: opening a chest can
fire an ``NPCSpawnerEvent``, and the level-up that armed the pending points can
have come from anything earlier in the same beat. Nothing about the interaction
path makes the race less real -- it just had no guard.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from unittest.mock import patch  # noqa: E402

from src.api.services.game_service import GameService  # noqa: E402
from src.combatant import wire_handle  # noqa: E402
from src.objects import Object  # noqa: E402
from tests._gs_fixtures import live_world  # noqa: E402


@pytest.fixture
def game_service():
    return GameService()


@pytest.fixture
def world_with_a_touchable_object():
    """A real world, a real object, and one enemy waiting to be engaged."""
    player, game_map = live_world()
    tile = game_map[(0, 0)]

    obj = Object(
        name="Wall Sconce",
        description="A sconce juts from the wall.",
        hidden=False,
        hide_factor=0,
        idle_message="A sconce juts from the wall.",
        discovery_message="a sconce.",
        player=player,
        tile=tile,
    )
    obj.keywords.append("touch")
    obj.touch = lambda _player: None
    tile.objects_here.append(obj)

    return player, tile, obj


def _interact(game_service, player, obj, enemies):
    """Run one interaction with ``check_for_combat`` answering ``enemies``."""
    with patch(
        "src.api.services.game_service.check_for_combat", return_value=enemies
    ):
        return game_service.interact_with_target(
            player, wire_handle(obj), "touch", session_data={}
        )


class TestTheDeferralHoldsOnTheInteractionPath:
    def test_pending_points_defer_the_fight_instead_of_starting_it(
        self, game_service, world_with_a_touchable_object
    ):
        player, _tile, obj = world_with_a_touchable_object
        player.pending_attribute_points = 3
        enemies = [object()]

        with patch.object(game_service, "_start_combat") as start:
            result = _interact(game_service, player, obj, enemies)

        assert start.call_count == 0, "combat must not start with points unspent"
        assert result["combat_started"] is False, result
        assert result["combat_state"] is None, result
        assert player._combat_deferred_enemies is enemies

    def test_the_stash_is_what_get_combat_status_resumes_from(
        self, game_service, world_with_a_touchable_object
    ):
        """The deferral is only safe because something later picks it up.

        Asserting the stash without asserting the resume would let a future
        edit stash the enemies somewhere nothing reads -- which is a soft-lock
        (the fight never happens) dressed as a fix.
        """
        player, _tile, obj = world_with_a_touchable_object
        player.pending_attribute_points = 1
        enemies = [object()]

        with patch.object(game_service, "_start_combat"):
            _interact(game_service, player, obj, enemies)

        player.pending_attribute_points = 0
        with patch.object(game_service, "_initialize_combat") as init:
            game_service.get_combat_status(player)

        assert init.call_count == 1
        assert init.call_args.args[1] is enemies
        assert player._combat_deferred_enemies is None

    def test_no_pending_points_still_starts_the_fight(
        self, game_service, world_with_a_touchable_object
    ):
        """The negative control: the guard must not swallow ordinary combat."""
        player, _tile, obj = world_with_a_touchable_object
        player.pending_attribute_points = 0
        enemies = [object()]

        with patch.object(
            game_service, "_start_combat", return_value={"stub": True}
        ) as start:
            result = _interact(game_service, player, obj, enemies)

        assert start.call_count == 1
        assert result["combat_started"] is True, result
        assert result["combat_state"] == {"stub": True}
