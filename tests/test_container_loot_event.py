"""Tests for the container-loot path that replaces the legacy ContainerLootInterface.

The web API never opens the terminal ContainerLootInterface; instead, looting a
container is driven by a structured LootEvent (src/events.py) routed through
GameService.interact_with_target / process_event_input.

These tests lock in that replacement behavior so the terminal menu class can be
removed safely:

* LootEvent performs take-one / take-all / exit transfers directly.
* Every loot-family verb (loot, check, view, examine, inspect, peruse) routes
  through a pending LootEvent rather than the terminal interface.
* A full round-trip (interact -> process_event_input) moves items into the
  player's inventory.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from player import Player
from objects import Container
from events import LootEvent
from items import Restorative, Antidote, Draught
from src.api.services.game_service import GameService

LOOT_VERBS = ["loot", "check", "view", "examine", "inspect", "peruse"]

# Distinct item types so Container.stack_items() does not merge them into a
# single stack (which would make "take one of several" untestable).
_ITEM_TYPES = [Restorative, Antidote, Draught]


def _make_container(num_items=2, start_open=True):
    """A real, opened Container holding `num_items` distinct single items."""
    items = [_ITEM_TYPES[i](count=1) for i in range(num_items)]
    return Container(
        name="Old Chest",
        nickname="old chest",
        inventory=items,
        start_open=start_open,
    )


def _make_player_on_tile(container):
    """A real Player whose current tile holds `container`."""
    player = Player()
    player.inventory = []
    tile = SimpleNamespace(
        x=1, y=1, npcs_here=[], objects_here=[container], items_here=[]
    )
    container.player = player
    container.tile = tile

    player.universe = MagicMock()
    player.universe.get_tile = MagicMock(return_value=tile)
    player.location_x = 1
    player.location_y = 1
    player.map = {"name": "test-map"}
    return player, tile


# ---------------------------------------------------------------------------
# LootEvent unit behavior (the replacement logic)
# ---------------------------------------------------------------------------

class TestLootEventLogic:
    def test_take_one_by_index_keeps_event_open(self):
        container = _make_container(num_items=2)
        player, _ = _make_player_on_tile(container)
        event = LootEvent("loot", player, None, container)

        result = event.process(user_input="0")

        assert result["success"] is True
        assert len(container.inventory) == 1
        assert len(player.inventory) == 1
        # Single item taken: event stays open for further choices.
        assert event.completed is False
        assert event.needs_input is True

    def test_take_all_completes_event(self):
        container = _make_container(num_items=3)
        player, _ = _make_player_on_tile(container)
        event = LootEvent("loot", player, None, container)

        event.process(user_input="all")

        assert container.inventory == []
        assert len(player.inventory) == 3
        assert event.completed is True
        assert event.needs_input is False

    def test_exit_completes_without_taking(self):
        container = _make_container(num_items=2)
        player, _ = _make_player_on_tile(container)
        event = LootEvent("loot", player, None, container)

        event.process(user_input="exit")

        assert len(container.inventory) == 2
        assert player.inventory == []
        assert event.completed is True
        assert event.needs_input is False

    def test_empty_container_offers_only_close(self):
        container = _make_container(num_items=0)
        player, _ = _make_player_on_tile(container)
        event = LootEvent("loot", player, None, container)

        labels = [opt["label"] for opt in event.input_options]
        assert labels == ["Close (Empty)"]


# ---------------------------------------------------------------------------
# interact_with_target routing: every loot verb -> pending LootEvent
# ---------------------------------------------------------------------------

class TestLootVerbRouting:
    @pytest.mark.parametrize("verb", LOOT_VERBS)
    def test_verb_creates_pending_loot_event(self, verb):
        container = _make_container(num_items=2)
        player, _ = _make_player_on_tile(container)
        service = GameService()
        session_data = {}

        result = service.interact_with_target(
            player, str(id(container)), verb, session_data=session_data
        )

        assert result["success"] is True, f"{verb} should succeed"
        pending = session_data.get("pending_events", {})
        assert len(pending) == 1, f"{verb} should queue exactly one pending event"
        (entry,) = pending.values()
        assert isinstance(entry["event"], LootEvent), (
            f"{verb} must route through LootEvent, not the terminal interface"
        )
        # Nothing transferred until the player makes a choice.
        assert len(player.inventory) == 0

    @pytest.mark.parametrize("verb", LOOT_VERBS)
    def test_locked_container_is_not_lootable(self, verb):
        """A locked container must not surface a loot menu via any verb."""
        container = _make_container(num_items=2, start_open=False)
        container.locked = True
        player, _ = _make_player_on_tile(container)
        service = GameService()
        session_data = {}

        result = service.interact_with_target(
            player, str(id(container)), verb, session_data=session_data
        )

        assert result["success"] is True
        # No pending loot event: the lock was respected.
        assert session_data.get("pending_events", {}) == {}
        assert len(player.inventory) == 0
        assert container.state != "opened"

    @pytest.mark.parametrize("verb", LOOT_VERBS)
    def test_verb_event_data_marked_needs_input(self, verb):
        container = _make_container(num_items=2)
        player, _ = _make_player_on_tile(container)
        service = GameService()
        session_data = {}

        service.interact_with_target(
            player, str(id(container)), verb, session_data=session_data
        )

        (entry,) = session_data["pending_events"].values()
        assert entry["event_data"]["needs_input"] is True
        assert entry["event_data"]["input_type"] == "choice"


# ---------------------------------------------------------------------------
# Full round-trip through GameService
# ---------------------------------------------------------------------------

class TestLootRoundTrip:
    def test_interact_then_take_all(self):
        container = _make_container(num_items=2)
        player, _ = _make_player_on_tile(container)
        service = GameService()
        session_data = {}

        service.interact_with_target(
            player, str(id(container)), "view", session_data=session_data
        )
        event_id = next(iter(session_data["pending_events"]))

        result = service.process_event_input(player, event_id, "all", session_data)

        assert result.get("success", True) is not False
        assert len(player.inventory) == 2
        assert container.inventory == []
