"""Regression tests for GitHub issue #722 (the level-up deferral item).

#712 drops a queued passage confirmation when a fight starts, and
``interact_with_target`` filters the dropped one out of its own response, so
the client is never handed a dialog whose answer is "Event not found".

That filter ran only on the branch that STARTS the fight. When unspent
attribute points defer it (``_defer_combat_for_level_up``), the fight is just
as committed -- the enemies are stashed and ``get_combat_status`` resumes it
on the poll after the last allocation -- but the confirmation was echoed and
left pending. The resume then went through ``_initialize_combat``, which
dropped it, and the dialog the client had open answered "Event not found".
"""

import random

import pytest

from src.combatant import wire_handle
from src.events import PassagewayTransitionEvent
from src.npc import Slime
from src.objects import Passageway

PREFIX = PassagewayTransitionEvent.NAME_PREFIX


def _passage_names(pending):
    return [
        name
        for name in (
            (entry.get("event_data") or {}).get("name", "")
            for entry in (pending or {}).values()
        )
        if name.startswith(PREFIX)
    ]


@pytest.fixture
def deferred_world(make_world, grid_3x3):
    """Jean beside a passageway, an aggro Slime that always notices him on
    the same tile, and unspent attribute points so the fight defers."""
    player, game_map = make_world(grid_3x3)
    tile = game_map[(0, 0)]
    passage = Passageway(player, tile, teleport_map="other-map", teleport_tile=(0, 0))
    tile.objects_here = [passage]
    slime = Slime()
    slime.aggro = True
    slime.awareness = 10**6
    slime.current_room = tile
    tile.npcs_here.append(slime)
    player.pending_attribute_points = 2
    return player, tile, passage, slime


def _enter(game_service, player, passage, session_data):
    return game_service.interact_with_target(
        player, wire_handle(passage), "enter", session_data=session_data
    )


class TestADeferredFightDoesNotEchoTheConfirmation:
    def test_the_interact_response_carries_no_passage_confirmation(
        self, deferred_world, game_service
    ):
        player, _tile, passage, _slime = deferred_world
        session_data = {}

        result = _enter(game_service, player, passage, session_data)

        assert result["combat_started"] is False, result
        assert player._combat_deferred_enemies, (
            "precondition: the fight must have been deferred, not skipped"
        )
        echoed = [
            e.get("name", "")
            for e in result["events_triggered"]
            if e.get("name", "").startswith(PREFIX)
        ]
        assert echoed == [], result["events_triggered"]
        assert _passage_names(session_data.get("pending_events")) == [], (
            "a confirmation left pending behind a committed fight is dropped "
            "at the resume, under a dialog the client already opened"
        )

    def test_every_echoed_event_is_still_answerable_after_the_resume(
        self, deferred_world, game_service
    ):
        """The issue's own sequence: interact, spend the points, poll combat
        status (which resumes the fight), then submit what the client got."""
        player, _tile, passage, _slime = deferred_world
        session_data = {}

        result = _enter(game_service, player, passage, session_data)

        random.seed(722)
        spent = game_service.allocate_level_up_points(player, "randomize", None)
        assert spent["success"] is True, spent
        assert player.pending_attribute_points == 0
        game_service.get_combat_status(player, session_data=session_data)
        assert player.in_combat, "precondition: the deferred fight resumed"

        for event in result["events_triggered"]:
            answer = game_service.process_event_input(
                player, event["event_id"], "continue", session_data
            )
            assert "not found" not in str(answer.get("error", "")), (
                event.get("name"),
                answer,
            )


class TestTheDeferralStillStashesTheFight:
    """Negative control: dropping the confirmation must not cancel the fight."""

    def test_the_fight_is_still_stashed_and_resumes(
        self, deferred_world, game_service
    ):
        player, _tile, passage, slime = deferred_world
        session_data = {}

        _enter(game_service, player, passage, session_data)

        assert player._combat_deferred_enemies == [slime]
        player.pending_attribute_points = 0
        game_service.get_combat_status(player, session_data=session_data)
        assert player.in_combat
        assert slime in player.combat_list


class TestTheDropLivesInTheDeferralItself:
    """Every caller of ``_defer_combat_for_level_up`` -- movement, event
    resolution, interaction -- gets the drop, not only the one that echoes
    events, just as ``_initialize_combat`` is the one place for a start."""

    def _queued(self, game_service, player, passage, tile, slime):
        tile.npcs_here.remove(slime)  # queue without a fight on this call
        player.pending_attribute_points = 0
        session_data = {}
        _enter(game_service, player, passage, session_data)
        assert _passage_names(session_data["pending_events"]), "precondition"
        return session_data

    def test_deferring_drops_a_queued_confirmation(
        self, deferred_world, game_service
    ):
        player, tile, passage, slime = deferred_world
        session_data = self._queued(game_service, player, passage, tile, slime)

        player.pending_attribute_points = 1
        assert game_service._defer_combat_for_level_up(player, [slime], session_data)

        assert _passage_names(session_data["pending_events"]) == []

    def test_not_deferring_leaves_it_to_the_fight_start(
        self, deferred_world, game_service
    ):
        player, tile, passage, slime = deferred_world
        session_data = self._queued(game_service, player, passage, tile, slime)

        assert not game_service._defer_combat_for_level_up(
            player, [slime], session_data
        )

        assert _passage_names(session_data["pending_events"]), (
            "no deferral, no drop: the caller's _start_combat owns it then"
        )
