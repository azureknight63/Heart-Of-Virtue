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

from src.player import Player
from src.objects import Container
from src.events import LootEvent
from src.items import Restorative, Antidote, Draught
from src.api.services.game_service import GameService
from src.combatant import wire_handle

LOOT_VERBS = ["loot", "check", "view", "examine", "inspect", "peruse"]

# Distinct item types so Container.stack_items() does not merge them into a
# single stack (which would make "take one of several" untestable).
_ITEM_TYPES = [Restorative, Antidote, Draught]


def _make_container(num_items=2, start_open=True, items=None):
    """A real, opened Container holding `num_items` distinct single items.

    Pass `items` to seed an explicit inventory instead (e.g. two of the same
    stackable so `Container.stack_items()` merges them).
    """
    if items is None:
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

        first, second = (i.name for i in container.inventory)

        result = event.process(user_input="0")

        assert result["success"] is True
        # Index 0 must move *that* item, not simply "an" item: a loop that
        # always popped the last entry would satisfy a bare length check.
        assert [i.name for i in player.inventory] == [first]
        assert [i.name for i in container.inventory] == [second]
        # Single item taken: event stays open for further choices.
        assert event.completed is False
        assert event.needs_input is True

    def test_take_all_completes_event(self):
        container = _make_container(num_items=3)
        player, _ = _make_player_on_tile(container)
        event = LootEvent("loot", player, None, container)

        expected = [i.name for i in container.inventory]

        event.process(user_input="all")

        assert container.inventory == []
        assert [i.name for i in player.inventory] == expected
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
            player, wire_handle(container), verb, session_data=session_data
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
            player, wire_handle(container), verb, session_data=session_data
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
            player, wire_handle(container), verb, session_data=session_data
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
            player, wire_handle(container), "view", session_data=session_data
        )
        event_id = next(iter(session_data["pending_events"]))

        result = service.process_event_input(player, event_id, "all", session_data)

        # ``result.get("success", True) is not False`` also passed when the key
        # was missing entirely -- i.e. when the event never ran.
        assert result["success"] is True
        assert result["needs_input"] is False
        assert [i.name for i in player.inventory] == ["Restorative", "Antidote"]
        assert all(name in result["output_text"]
                   for name in ("Restorative", "Antidote"))
        assert container.inventory == []


class TestBothInteractionArmsShipTheSameEventShape:
    """`_queue_passageway_confirmation`'s docstring promises this; nothing checked it.

    It says the two arms return "the same shape ... so a third arm has one
    contract to copy". They did not: the container arm wrapped its
    `_store_pending_event` call in `if session_data is not None`, while the
    passageway arm called it unconditionally. `_store_pending_event` already
    gates its own two session-touching blocks on that, so the guard's only
    effect was to withhold `event_id` from the container arm's payload — a
    silent divergence from the contract the sibling documents, in the one
    situation (a caller with no session) where a client has nothing else to
    identify the dialog by.

    Asserted through the two real arms rather than on the helper, because the
    helper was never the thing that differed.
    """

    def _container_arm(self, session_data):
        container = _make_container(num_items=2)
        player, _ = _make_player_on_tile(container)
        result = GameService().interact_with_target(
            player, wire_handle(container), "loot", session_data=session_data
        )
        return result

    def test_the_container_arm_ships_an_event_id_with_no_session(self):
        result = self._container_arm(None)

        events = result.get("events_triggered") or []
        assert len(events) == 1, (
            "expected exactly the loot dialog; a zero-length list would make "
            f"the assertion below vacuous. Got {events!r}"
        )
        assert events[0].get("event_id"), (
            "the container arm withheld event_id when session_data is None, so "
            "its payload does not match the shape "
            "_queue_passageway_confirmation's docstring says both arms return"
        )

    def test_a_session_backed_call_is_unchanged(self):
        # The negative control: the guard only ever fired on the None path, so
        # if this regressed too, the fix went further than the finding.
        session_data = {}
        result = self._container_arm(session_data)

        events = result.get("events_triggered") or []
        assert len(events) == 1, events
        assert events[0].get("event_id") in session_data.get("pending_events", {})


# ---------------------------------------------------------------------------
# Stacked items are counted once in engine-side labels (#565 engine half)
# ---------------------------------------------------------------------------

def _make_stacked_sap_container():
    """An opened Container whose two DriedCrystalSap merge into one x2 stack."""
    from src.items import DriedCrystalSap

    container = _make_container(items=[DriedCrystalSap(), DriedCrystalSap()])
    # Precondition: stack_items() merged them into a single count-2 stack. The
    # name stays unadorned -- stack_grammar() no longer bakes the count into it
    # (#624), which is what the labels below must supply exactly once.
    assert len(container.inventory) == 1
    assert container.inventory[0].count == 2
    assert container.inventory[0].name == "Dried Crystal Sap"
    return container


class TestStackedItemLabelsCountOnce:
    def test_take_all_narration_names_stack_once(self, narrated):
        container = _make_stacked_sap_container()
        player, _ = _make_player_on_tile(container)

        messages = narrated(container.take_all, player)
        texts = [m.get("text", "") for m in messages]
        takes = [t for t in texts if t.startswith("Jean takes")]

        assert takes == ["Jean takes 2× Dried Crystal Sap."]
        assert "x2" not in takes[0]

    def test_loot_event_option_label_counts_once(self):
        container = _make_stacked_sap_container()
        player, _ = _make_player_on_tile(container)

        event = LootEvent("loot", player, None, container)
        labels = [o["label"] for o in event.input_options]

        assert labels[0] == "Take Dried Crystal Sap (2)"
        assert "x2" not in labels[0]

    def test_unstacked_item_labels_unchanged(self, narrated):
        # Negative control: a single item carries no suffix and gets no count.
        container = _make_container(num_items=1)
        player, _ = _make_player_on_tile(container)
        name = container.inventory[0].name
        assert " x" not in name

        event = LootEvent("loot", player, None, container)
        assert event.input_options[0]["label"] == f"Take {name}"

        messages = narrated(container.take_all, player)
        takes = [m.get("text", "") for m in messages if m.get("text", "").startswith("Jean takes")]
        assert takes == [f"Jean takes {name}."]

    def test_loot_event_take_all_narrates_stack_once(self, narrated):
        # Same sentence form as Container.take_all: "2× Dried Crystal Sap",
        # not the baked "Dried Crystal Sap x2" (the two paths diverged).
        container = _make_stacked_sap_container()
        player, _ = _make_player_on_tile(container)
        event = LootEvent("loot", player, None, container)

        messages = narrated(event.process, "all")
        takes = [m.get("text", "") for m in messages if m.get("text", "").startswith("Jean takes")]

        assert takes == ["Jean takes everything: 2× Dried Crystal Sap"]

    def test_loot_event_single_take_narrates_stack_once(self, narrated):
        container = _make_stacked_sap_container()
        player, _ = _make_player_on_tile(container)
        event = LootEvent("loot", player, None, container)

        messages = narrated(event.process, "0")
        takes = [m.get("text", "") for m in messages if m.get("text", "").startswith("Jean takes")]

        assert takes == ["Jean takes 2× Dried Crystal Sap."]

    def test_stack_sentence_label_matches_take_all_form(self):
        from src.items import stack_sentence_label

        sap = SimpleNamespace(name="Dried Crystal Sap x2", count=2)
        assert stack_sentence_label(sap, 2) == "2× Dried Crystal Sap"
        single = SimpleNamespace(name="Rusty Key", count=1)
        assert stack_sentence_label(single, 1) == "Rusty Key"

    def test_stack_base_name_huge_digit_run_does_not_raise(self):
        # py3.11 caps int() parsing at 4300 digits (CVE-2020-10735); the
        # suffix is compared as a string so an absurd name degrades to
        # "keep the name" instead of raising into the loot dialog.
        from src.items import stack_base_name

        huge = "Potion x" + "9" * 5000
        assert stack_base_name(SimpleNamespace(name=huge, count=2)) == huge

    def test_stack_base_name_keeps_zero_padded_suffix(self):
        # Intended: stack_grammar() never zero-pads, so "x02" is part of the
        # item's own name rather than a baked count, even at stack size 2.
        from src.items import stack_base_name

        padded = SimpleNamespace(name="Potion x02", count=2)
        assert stack_base_name(padded) == "Potion x02"

    def test_stack_base_name_helper_is_conservative(self):
        from src.items import stack_base_name

        sap = SimpleNamespace(name="Dried Crystal Sap x3", count=3)
        assert stack_base_name(sap) == "Dried Crystal Sap"
        # Suffix that does not match the stack size is part of the name.
        odd = SimpleNamespace(name="Potion x3", count=2)
        assert stack_base_name(odd) == "Potion x3"
        # No count attribute at all: name passes through.
        plain = SimpleNamespace(name="Rusty Key")
        assert stack_base_name(plain) == "Rusty Key"
