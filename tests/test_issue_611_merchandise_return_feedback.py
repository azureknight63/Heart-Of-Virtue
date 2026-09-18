"""Regression tests for GitHub issue #611.

BUG: merchandise taken off a shop's stock is confiscated the moment the player
interacts with a Passageway, and the player was never told. The confiscation
itself is correct and intended -- ``Player.drop_merchandise_items`` puts every
unpaid item back on the shop's tile and narrates a line per item -- but that
narration reached the client only as the ``/world/interact`` response's
``message``, and the client's passageway branch
(``useWorldInteract.handlePassagewayTransition``) returns before
``setInteractionOutput`` and closes the panel that would have rendered it. The
inventory came back one item lighter with nothing on screen saying why.

Fix: the narration rides on the confirmation event the player is about to read
anyway. ``drop_merchandise_items`` now RETURNS the lines it narrated, and
``_queue_passageway_confirmation`` stages them onto the
``PassagewayTransitionEvent`` payload as ``output_text`` (the existing staged
key that ``EventDialog`` already prefers over ``description``). The player sees
the returned goods named, above the "Step through?" prompt, in the one dialog
the crossing cannot skip -- and, because ``_store_pending_event`` persists the
staged payload, the same text survives a reload of the pending confirmation.

These tests fail against the pre-fix code: ``drop_merchandise_items`` returned
None and the serialized confirmation event carried no ``output_text`` at all.
"""

import pytest

from src.combatant import wire_handle
from src.items import Restorative
from src.objects import Passageway

#: Every phrase ``drop_merchandise_items`` can pick names the item and says
#: something about not having paid; the choice is an unseeded ``random.choice``
#: (CLAUDE.md: never assert on an unseeded roll), so the assertions below pin
#: the item name and the staging, never which of the six phrases came up.
ITEM_NAME = "Rusted Iron Mace"


@pytest.fixture
def shop_doorway(make_world, grid_3x3):
    """A player on a tile whose Passageway leads to the next tile over.

    Returns ``(player, tile, passage)``. The caller decides what, if anything,
    the player is carrying.
    """
    player, game_map = make_world(grid_3x3)
    tile = game_map[(0, 0)]
    passage = Passageway(
        player, tile, teleport_map=game_map["name"], teleport_tile=(1, 0)
    )
    passage.name = "Tent Flap"
    tile.objects_here = [passage]
    return player, tile, passage


def _carry_merchandise(player, name=ITEM_NAME):
    """Put one piece of unpaid shop stock in the player's inventory."""
    stock = Restorative(merchandise=True)
    stock.name = name
    player.inventory.append(stock)
    return stock


class TestDropMerchandiseItemsReportsWhatItDropped:
    """The engine method is the only thing that knows what it took back."""

    def test_returns_the_narrated_lines(self, shop_doorway):
        player, tile, _ = shop_doorway
        _carry_merchandise(player)

        lines = player.drop_merchandise_items()

        assert isinstance(lines, list), (
            "drop_merchandise_items must report the lines it narrated so the "
            "API can show them; a bare None forces the caller to re-derive "
            "them from a post-drop inventory, which is empty by construction"
        )
        assert len(lines) == 1
        assert ITEM_NAME in lines[0]

    def test_returns_one_line_per_item(self, shop_doorway):
        player, _, _ = shop_doorway
        _carry_merchandise(player, "Rusted Iron Mace")
        _carry_merchandise(player, "Chipped Buckler")

        lines = player.drop_merchandise_items()

        assert len(lines) == 2
        assert any("Rusted Iron Mace" in line for line in lines)
        assert any("Chipped Buckler" in line for line in lines)

    def test_returns_empty_when_nothing_was_merchandise(self, shop_doorway):
        player, _, _ = shop_doorway
        player.inventory.append(Restorative())

        assert player.drop_merchandise_items() == []

    def test_returns_empty_when_there_is_no_tile_to_drop_onto(self, shop_doorway):
        """The early-out still answers the caller's question: nothing dropped."""
        player, _, _ = shop_doorway
        _carry_merchandise(player)
        player.map = {}

        assert player.drop_merchandise_items() == []


class TestPassagewayConfirmationNamesTheReturnedGoods:
    """The player-facing half: the confirmation dialog says what it took."""

    def test_confirmation_event_carries_the_return_narration(
        self, shop_doorway, game_service
    ):
        player, _, passage = shop_doorway
        _carry_merchandise(player)

        result = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data={}
        )

        event = result["events_triggered"][0]
        assert ITEM_NAME in event.get("output_text", ""), (
            "the crossing confirmation is the one dialog the player cannot "
            "skip, so it is where the confiscation has to be reported"
        )

    def test_confirmation_still_shows_the_step_through_prose(
        self, shop_doorway, game_service
    ):
        """output_text REPLACES description in EventDialog, so it must carry both."""
        player, _, passage = shop_doorway
        _carry_merchandise(player)

        result = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data={}
        )

        event = result["events_triggered"][0]
        assert event["description"] in event["output_text"]
        assert event["output_text"].index(ITEM_NAME) < event["output_text"].index(
            event["description"]
        ), "the goods are set down before Jean steps through, and read that way"

    def test_nothing_is_staged_when_no_merchandise_was_held(
        self, shop_doorway, game_service
    ):
        player, _, passage = shop_doorway

        result = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data={}
        )

        event = result["events_triggered"][0]
        assert "output_text" not in event, (
            "an ordinary crossing must keep the payload shape it had before "
            "staged confirmations existed -- EventDialog falls back to "
            "description on its own"
        )

    def test_staged_text_survives_a_reload_of_the_pending_confirmation(
        self, shop_doorway, game_service
    ):
        """GET /world/events/pending serves the stored payload, not a fresh one."""
        player, _, passage = shop_doorway
        _carry_merchandise(player)
        session_data = {}

        result = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data=session_data
        )

        event_id = result["events_triggered"][0]["event_id"]
        stored = session_data["pending_events"][event_id]["event_data"]
        assert ITEM_NAME in stored.get("output_text", "")

    def test_interact_message_still_carries_the_narration(
        self, shop_doorway, game_service
    ):
        """The narration sink half, pinned independently of the event payload.

        Nothing in the client reads this on the passageway branch any more, but
        it is the capture that proves the drop ran inside
        ``capture_narration`` at all -- if this goes quiet, the staged
        ``output_text`` above is the only thing left standing between the
        player and a silent confiscation.
        """
        player, _, passage = shop_doorway
        _carry_merchandise(player)

        result = game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data={}
        )

        assert ITEM_NAME in result["message"]

    def test_the_goods_really_do_land_on_the_shop_floor(
        self, shop_doorway, game_service
    ):
        """The feedback would be a lie if the drop itself regressed."""
        player, tile, passage = shop_doorway
        _carry_merchandise(player)

        game_service.interact_with_target(
            player, wire_handle(passage), "enter", session_data={}
        )

        assert [i.name for i in tile.items_here] == [ITEM_NAME]
        assert not [i for i in player.inventory if getattr(i, "merchandise", False)]
