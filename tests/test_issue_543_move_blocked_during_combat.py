"""Regression test for GitHub issue #543.

BUG: ``GameService.move_player`` validated universe/position/direction/exits
but never checked whether the player was mid-combat, so ``POST
/api/world/move`` would silently relocate the player off the battlefield
while ``GET /api/combat/status`` still reported ``combat_active: true`` and
the enemy alive. ``trigger_tile_events`` already guards on
``player.in_combat`` (so the walk-off didn't crash), which is exactly why the
bug was silent instead of loud.

Fix: ``move_player`` now rejects the move with an ``{"error": ...}`` result
(the same shape every other move_player validation failure already returns,
which the ``/world/move`` route maps to HTTP 400 — see
``tests/test_world_routes_coverage.py::TestMovePlayer::
test_move_returns_error_from_service``) whenever ``player.in_combat`` is
truthy, mirroring the guard ``trigger_tile_events`` already had.

The issue also asked whether ``POST /api/world/interact`` teleports (walking
through a ``Passageway``) have the same gap. Reading the code path shows
``interact_with_target`` never physically moves the player itself: for a
``Passageway`` target it queues a ``PassagewayTransitionEvent`` confirmation
(the frontend's "Jean steps through..." prompt) and the actual
``player.teleport()`` call only happens later, when the client confirms via
``POST /world/events/input``. So the gap is in queuing that confirmation
while combat is active: nothing checked ``player.in_combat`` before creating
it, meaning a direct API call could stage — and, on confirm, execute — a
battlefield-escaping teleport exactly like the ``/world/move`` bug.
``TestInteractPassagewayBlockedDuringCombat`` below covers that.
"""

from src.combatant import wire_handle
from src.objects import Passageway


class TestMoveBlockedDuringCombat:
    def test_move_player_rejects_move_while_in_combat(
        self, make_world, grid_3x3, game_service
    ):
        player, _ = make_world(grid_3x3)
        player.in_combat = True

        result = game_service.move_player(player, "east")

        assert "error" in result, (
            "move_player must reject movement while player.in_combat is True"
        )
        # Player must not have actually moved off the battlefield tile.
        assert (player.location_x, player.location_y) == (0, 0)

    def test_move_player_error_message_mentions_combat(
        self, make_world, grid_3x3, game_service
    ):
        player, _ = make_world(grid_3x3)
        player.in_combat = True

        result = game_service.move_player(player, "east")

        assert "combat" in result.get("error", "").lower()

    def test_move_player_still_works_when_not_in_combat(
        self, make_world, grid_3x3, game_service
    ):
        """Sanity check: the new guard must not block ordinary movement."""
        player, _ = make_world(grid_3x3)
        assert getattr(player, "in_combat", False) is False

        result = game_service.move_player(player, "east")

        assert result.get("success") is True
        assert (player.location_x, player.location_y) == (1, 0)


class TestInteractPassagewayBlockedDuringCombat:
    def test_passageway_interaction_is_rejected_while_in_combat(
        self, make_world, grid_3x3, game_service
    ):
        player, game_map = make_world(grid_3x3)
        tile = game_map[(0, 0)]
        passage = Passageway(
            player, tile, teleport_map="other-map", teleport_tile=(0, 0)
        )
        tile.objects_here = [passage]
        player.in_combat = True

        session_data = {}
        result = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data=session_data
        )

        assert result["success"] is False
        assert "combat" in result.get("message", "").lower()
        # No confirmation event should have been queued — the whole point of
        # blocking here is that it must never reach the confirm step
        # (POST /world/events/input) that actually performs the teleport.
        assert not session_data.get("pending_events")

    def test_passageway_interaction_still_works_when_not_in_combat(
        self, make_world, grid_3x3, game_service
    ):
        """Sanity check: the new guard must not block ordinary passageway use."""
        player, game_map = make_world(grid_3x3)
        tile = game_map[(0, 0)]
        passage = Passageway(
            player, tile, teleport_map="other-map", teleport_tile=(0, 0)
        )
        tile.objects_here = [passage]
        assert getattr(player, "in_combat", False) is False

        session_data = {}
        result = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data=session_data
        )

        assert result["success"] is True
        assert session_data.get("pending_events"), (
            "a normal (non-combat) passageway interaction should still queue "
            "the step-through confirmation event"
        )


class TestPassagewayConfirmBlockedDuringCombat:
    """The confirm step is refused in combat, as a backstop to the queue-time
    guard.

    Since #712 a queued confirmation does not normally survive into a fight:
    ``GameService._initialize_combat``, which every API combat start passes
    through, drops it (the confirmation's only option is ``continue``, so a
    surviving one deadlocked the session -- see
    ``tests/test_issue_712_passageway_confirmation_dropped_on_combat.py``).
    This class sets ``player.in_combat`` directly, bypassing that start, to
    pin the backstop on its own: if a confirmation ever does reach the
    confirm step mid-fight, the teleport still does not run.
    """

    def test_confirm_is_rejected_if_combat_started_after_queuing(
        self, make_world, grid_3x3, game_service
    ):
        player, game_map = make_world(grid_3x3)
        tile = game_map[(0, 0)]
        passage = Passageway(
            player, tile, teleport_map="other-map", teleport_tile=(0, 0)
        )
        tile.objects_here = [passage]

        # Queue the confirmation while NOT in combat (this must succeed --
        # it's the existing, already-tested behaviour).
        session_data = {}
        queued = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data=session_data
        )
        assert queued["success"] is True
        event_id = next(iter(session_data["pending_events"]))

        # Flag the fight directly -- NOT through a combat start, which would
        # drop the confirmation (#712) before this backstop is reached.
        player.in_combat = True

        result = game_service.process_event_input(player, event_id, "continue", session_data)

        assert result["success"] is False
        assert "combat" in result.get("error", "").lower()
        # The player must not have been teleported off the battlefield. The
        # refusal itself does not consume the entry: retiring a confirmation
        # is the job of the fight's start (#712), not of this guard, so a
        # refused answer leaves the store exactly as it found it.
        assert (player.location_x, player.location_y) == (0, 0)
        assert event_id in session_data["pending_events"]

    def test_confirm_still_works_when_not_in_combat(
        self, make_world, grid_3x3, game_service
    ):
        """Sanity check: the new guard must not block an ordinary confirm."""
        player, game_map = make_world(grid_3x3)
        tile = game_map[(0, 0)]
        passage = Passageway(
            player, tile, teleport_map="other-map", teleport_tile=(0, 0)
        )
        tile.objects_here = [passage]

        session_data = {}
        queued = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data=session_data
        )
        event_id = next(iter(session_data["pending_events"]))
        assert getattr(player, "in_combat", False) is False

        result = game_service.process_event_input(player, event_id, "continue", session_data)

        assert result["success"] is True
