"""Regression tests for GitHub issue #712.

A queued, unanswered passageway confirmation (``PassagewayTransitionEvent``,
"Step through?", whose only option is ``continue``) plus a fight starting
was a permanent soft-lock:

* ``process_event_input`` refuses the ``continue`` while ``in_combat`` (#543),
* the confirmation offers no other option, so it can never be declined,
* ``execute_move`` refuses every combat action while any needs-input event
  is pending ("Event pending"),
* and nothing ever removed the confirmation.

Combat already wins over the passage (#543), so the fix drops the
confirmation at the one place every API combat start passes through,
``GameService._initialize_combat``. ONLY that event type is dropped: a
LootEvent queued before the fight is answered after it, and combat's own
needs-input events must survive their own fight's start.
"""

import random
from types import SimpleNamespace

import pytest

from src.combatant import wire_handle
from src.events import LootEvent, PassagewayTransitionEvent
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
def world(make_world, grid_3x3):
    """Jean at (0, 0) beside a passageway, with an aggro Slime that always
    notices him (``awareness`` far above any finesse roll)."""
    player, game_map = make_world(grid_3x3)
    tile = game_map[(0, 0)]
    passage = Passageway(player, tile, teleport_map="other-map", teleport_tile=(0, 0))
    tile.objects_here = [passage]
    slime = Slime()
    slime.aggro = True
    slime.awareness = 10**6
    slime.current_room = tile
    return player, tile, passage, slime


def _queue_confirmation(game_service, player, passage, session_data):
    queued = game_service.interact_with_target(
        player, wire_handle(passage), "enter", session_data=session_data
    )
    assert queued["success"] is True, queued
    assert _passage_names(session_data.get("pending_events")), (
        "precondition: the interact must have queued the confirmation"
    )


class TestCombatStartDropsTheConfirmation:
    def test_start_combat_drops_a_queued_passage_confirmation(
        self, world, game_service
    ):
        player, tile, passage, slime = world
        session_data = {}
        _queue_confirmation(game_service, player, passage, session_data)

        tile.npcs_here.append(slime)
        started = game_service.start_combat(
            player, wire_handle(slime), session_data=session_data
        )
        assert player.in_combat, started

        assert _passage_names(session_data.get("pending_events")) == [], (
            "the confirmation outlived the fight's start: it can never be "
            "answered in combat, and it blocks every combat action"
        )

    def test_a_combat_move_is_not_refused_as_event_pending(
        self, world, game_service
    ):
        """The issue's own acceptance test: queue, start combat, act."""
        player, tile, passage, slime = world
        session_data = {}
        _queue_confirmation(game_service, player, passage, session_data)
        tile.npcs_here.append(slime)
        game_service.start_combat(player, wire_handle(slime), session_data=session_data)

        wait = next(m for m in player.known_moves if m.name == "Wait")
        random.seed(712)
        result = game_service.execute_move(
            player,
            "move",
            str(player.known_moves.index(wait)),
            session_data=session_data,
        )

        assert result.get("error") != "Event pending", result


class TestInteractThatStartsCombatDoesNotEchoTheConfirmation:
    def test_events_triggered_omits_the_dropped_confirmation(
        self, world, game_service
    ):
        """An aggro enemy already on the tile engages on the very interact
        that queued the confirmation. The response must not hand the SPA a
        modal whose submit answers "Event not found"."""
        player, tile, passage, slime = world
        tile.npcs_here.append(slime)
        session_data = {}

        result = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data=session_data
        )

        assert result["combat_started"] is True, result
        echoed = [
            e.get("name", "")
            for e in result["events_triggered"]
            if e.get("name", "").startswith(PREFIX)
        ]
        assert echoed == [], result["events_triggered"]
        assert _passage_names(session_data.get("pending_events")) == []


class TestOnlyThePassageConfirmationIsDropped:
    """Negative control: other needs-input entries survive a combat start."""

    def test_a_pending_loot_event_survives_combat_start(self, world, game_service):
        player, tile, passage, slime = world
        # Queue the confirmation first: since #713 an interaction is refused
        # while another scene already awaits input.
        session_data = {}
        _queue_confirmation(game_service, player, passage, session_data)
        loot = LootEvent("Loot", player, tile, SimpleNamespace(nickname="chest"))
        session_data["pending_events"].update(
            {
                "loot-1": {
                    "event": loot,
                    "event_data": {
                        "name": "Loot",
                        "needs_input": True,
                        "completed": False,
                    },
                },
                "combat-1": {
                    "event": object(),
                    "event_data": {
                        "name": "RumblerAnnouncement",
                        "needs_input": True,
                        "completed": False,
                    },
                },
            }
        )
        tile.npcs_here.append(slime)

        game_service.start_combat(player, wire_handle(slime), session_data=session_data)

        pending = session_data["pending_events"]
        assert "loot-1" in pending and "combat-1" in pending, pending
        assert _passage_names(pending) == []
