"""Regression tests for GitHub issue #713.

``GameService.move_player`` and ``interact_with_target`` never read
``pending_events``: over the API, Jean could walk away from a scene that was
still waiting for an answer. Answering it later ran the next stage from the
wrong place (``Ch02GuideToCitadel`` teleported him back to Grondia), and it
was the easy road into the #712 passageway/combat deadlock. The only guard
was the SPA's modal dialog.

The engine now refuses both while any pending event needs input and is not
completed -- the same predicate ``execute_move`` already used to refuse
combat actions ("Event pending"), now one shared helper. Each method keeps
its own refusal shape: ``move_player`` answers ``{"error": ...}`` (the
``/world/move`` route maps it to a 400), ``interact_with_target`` answers
``{"success": False, "message": ...}``.
"""

from types import SimpleNamespace

import pytest

from src.combatant import wire_handle
from src.events import LootEvent, PassagewayTransitionEvent
from src.objects import Passageway


def _pending_entry(player, tile, name, needs_input=True, completed=False):
    return {
        "event": LootEvent(name, player, tile, SimpleNamespace(nickname="chest")),
        "event_data": {
            "name": name,
            "needs_input": needs_input,
            "completed": completed,
        },
    }


@pytest.fixture
def world(make_world, grid_3x3):
    player, game_map = make_world(grid_3x3)
    tile = game_map[(0, 0)]
    passage = Passageway(player, tile, teleport_map="other-map", teleport_tile=(0, 0))
    tile.objects_here = [passage]
    return player, tile, passage


class TestMoveRefusedWhileASceneAwaitsInput:
    def test_move_is_refused_naming_the_pending_event(self, world, game_service):
        player, tile, _passage = world
        session_data = {
            "pending_events": {"loot-1": _pending_entry(player, tile, "ChestLoot")}
        }
        tick_before = player.universe.game_tick

        result = game_service.move_player(player, "east", session_data)

        assert "error" in result, result
        assert "success" not in result, (
            "move_player's refusal convention is a bare {'error': ...}, "
            "which /world/move maps to a 400"
        )
        # The engine name rides in its own field for clients; the prose is
        # player-facing, so it carries no internal event name, and Jean is he/him.
        assert result.get("pending_event") == "ChestLoot", result
        assert "ChestLoot" not in result["error"]
        assert " him" in result["error"] and " her" not in result["error"]
        assert (player.location_x, player.location_y) == (0, 0)
        assert player.universe.game_tick == tick_before, (
            "a refused move must not advance the world"
        )
        assert "loot-1" in session_data["pending_events"]

    def test_a_queued_passage_confirmation_blocks_the_move(
        self, world, game_service
    ):
        """The live #712 road: queue the confirmation, then walk off."""
        player, _tile, passage = world
        session_data = {}
        queued = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data=session_data
        )
        assert queued["success"] is True, queued

        result = game_service.move_player(player, "east", session_data)

        assert "error" in result, result
        assert result.get("pending_event", "").startswith(
            PassagewayTransitionEvent.NAME_PREFIX
        ), result
        assert PassagewayTransitionEvent.NAME_PREFIX not in result["error"]
        assert (player.location_x, player.location_y) == (0, 0)

    @pytest.mark.parametrize(
        "needs_input, completed",
        [(False, False), (True, True)],
        ids=["no-input", "completed"],
    )
    def test_an_event_that_awaits_nothing_does_not_block(
        self, world, game_service, needs_input, completed
    ):
        """Negative control: only an open question blocks."""
        player, tile, _passage = world
        session_data = {
            "pending_events": {
                "done": _pending_entry(
                    player, tile, "Stale", needs_input=needs_input, completed=completed
                )
            }
        }

        result = game_service.move_player(player, "east", session_data)

        assert result.get("success") is True, result
        assert (player.location_x, player.location_y) == (1, 0)


class TestInteractRefusedWhileASceneAwaitsInput:
    def test_interact_is_refused_naming_the_pending_event(
        self, world, game_service
    ):
        player, tile, passage = world
        session_data = {
            "pending_events": {"loot-1": _pending_entry(player, tile, "ChestLoot")}
        }

        result = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data=session_data
        )

        assert result["success"] is False, result
        assert result.get("pending_event") == "ChestLoot", result
        assert "ChestLoot" not in result["message"]
        assert list(session_data["pending_events"]) == ["loot-1"], (
            "the refused interact must not have queued a confirmation"
        )

    def test_an_event_that_awaits_nothing_does_not_block_interact(
        self, world, game_service
    ):
        player, tile, passage = world
        session_data = {
            "pending_events": {
                "done": _pending_entry(player, tile, "Stale", completed=True)
            }
        }

        result = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data=session_data
        )

        assert result["success"] is True, result
