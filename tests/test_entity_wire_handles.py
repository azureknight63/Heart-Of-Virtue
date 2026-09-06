"""Regression tests for the non-combat wire-id scheme (issue #518).

Issue #511 replaced ``id(combatant)`` with an opaque handle for the *combat*
payload. Everything else the API gives the client an identity for kept minting
its id as ``str(id(entity))``. (For WHICH entity kinds those are, read
``src.combatant.wire_handle``'s docstring — it is the single home of that list,
and re-stating it here is how the copies came to disagree; for the live sites,
``grep -rn "wire_handle(" src/``.) That was the same defect in a different
payload:

  1. it shipped raw CPython heap addresses to the browser, and
  2. addresses are RECYCLED, so a client-held id for an entity that has since
     been freed can resolve to a *different* entity allocated at the same
     address.

``TestAddressRecyclingAliasesEntities`` below is not an argument that (2) could
happen — it forces a real address reuse and shows the old scheme aliasing.

The other half of #518 is that these entities are the *same objects* as the
combat ones: the ``Slime`` in ``tile.npcs_here`` is the instance the fight puts
in ``combat_list``. It gets ONE handle, not one per payload — ``combatant_handle``
is an alias of ``wire_handle`` — so ``TestOneIdentityPerObject`` pins that the
room id and the combat id name the same object.

The end-to-end "the id a serializer emits is the id its resolver accepts"
contracts live in ``tests/test_wire_field_contract.py`` (real engine objects
through the real serializers), not here.
"""

import pickle

import pytest

from src.api.serializers.combat import CombatantSerializer
from src.api.serializers.item_serializer import ItemSerializer
from src.api.serializers.npc_serializer import NPCSerializer
from src.api.serializers.object_serializer import ObjectSerializer
from src.api.serializers.shop_serializer import ShopSerializer
from src.api.services.game_service import GameService
from src.combatant import (
    COMBAT_HANDLE_ATTR,
    combatant_handle,
    find_by_handle,
    wire_handle,
)
from src.items import Gold, Restorative, RustedDagger
from src.npc._enemies import Slime
from src.npc._merchants import Merchant
from src.objects import Container
from src.player import Player
from tests._gs_fixtures import assert_opaque_wire_id, live_shop, live_world


# ---------------------------------------------------------------------------
# The hazard, forced rather than argued
# ---------------------------------------------------------------------------

#: How many allocate/free rounds to spend looking for an address reuse. CPython
#: hands a just-freed instance block of a given size class straight back to the
#: next allocation of the same class, so the first round succeeds — measured
#: 200/200 under pymalloc and 200/200 under ``PYTHONMALLOC=malloc`` on CPython
#: 3.11. The retry budget is there so a single unlucky round (an interleaved
#: allocation stealing the block) cannot turn this into a flake. If it ever
#: exhausts, the failure message says so explicitly rather than pretending the
#: hazard is disproven.
_RECYCLE_ATTEMPTS = 64


def _force_address_reuse(cls):
    """Free an instance of ``cls`` and allocate one at the same address.

    Both objects are built with ``cls.__new__`` and no ``__init__``: only the
    instance block is allocated, so the freed block is the very next one handed
    out. (Running a full ``cls()`` in between allocates the instance dict and
    whatever else ``__init__`` touches, which reorders the free list and makes
    the reuse stop happening — measured 0/200. Hence the bare ``__new__``.)

    Returns ``(dead_address, dead_handle, replacement)``: the string id the OLD
    scheme published for the now-dead object, the handle the NEW scheme
    published for it, and the live object that inherited its address.
    """
    for _ in range(_RECYCLE_ATTEMPTS):
        ghost = cls.__new__(cls)
        ghost.name = "Ghost"
        dead_handle = wire_handle(ghost)
        dead_address = str(id(ghost))
        del ghost

        replacement = cls.__new__(cls)
        if str(id(replacement)) == dead_address:
            replacement.name = "Replacement"
            return dead_address, dead_handle, replacement
        del replacement

    pytest.fail(
        f"could not force a heap-address reuse for {cls.__name__} in "
        f"{_RECYCLE_ATTEMPTS} rounds — the aliasing hazard could not be "
        "demonstrated on this interpreter/allocator, so this test proved "
        "nothing. Do not delete it; investigate why the allocator stopped "
        "recycling."
    )


class TestAddressRecyclingAliasesEntities:
    """The concrete reason #518 is a bug and not a style preference."""

    def test_the_old_scheme_hands_a_dead_npcs_id_to_a_live_one(self):
        """Both schemes, same room, same client-held id — opposite answers.

        ``_force_address_reuse`` guarantees the address equality itself, so
        asserting only that would restate the helper's own loop-exit
        condition and could fail only through the helper. What is asserted
        here instead is what the two *lookups* do with the dead entity's
        published id: the pre-#511 resolver, spelled out below exactly as it
        was written, hands back a live Slime that is not the one the client
        asked for — and it is a different object, not the same one
        resurrected. ``find_by_handle`` refuses.
        """
        dead_address, dead_handle, replacement = _force_address_reuse(Slime)
        room = [replacement]

        def _pre_511_lookup(entities, wire_id):
            """The resolver #511 removed: compare the heap address."""
            return next((e for e in entities if str(id(e)) == wire_id), None)

        aliased = _pre_511_lookup(room, dead_address)

        assert aliased is replacement
        assert aliased.name == "Replacement", (
            "the aliased object is a different Slime, not the dead one"
        )
        assert find_by_handle(room, dead_handle) is None

    def test_a_handle_is_never_reissued_to_the_object_that_inherits_the_address(self):
        _, dead_handle, replacement = _force_address_reuse(Slime)

        assert wire_handle(replacement) != dead_handle

    def test_a_stale_room_id_does_not_resolve_to_the_npc_that_took_the_address(self):
        """The end of the chain: the lookup the client's id actually reaches."""
        dead_address, dead_handle, replacement = _force_address_reuse(Slime)
        player, game_map = live_world()
        tile = game_map[(0, 0)]
        tile.npcs_here = [replacement]

        assert find_by_handle(tile.npcs_here, dead_handle) is None
        # …while the address the old scheme would have replayed does hit it.
        assert str(id(tile.npcs_here[0])) == dead_address

        result = GameService().interact_with_target(player, dead_handle, "look")

        assert result["success"] is False
        assert result["message"] == "Target not found."

    def test_the_same_hazard_holds_for_items_and_world_objects(self):
        for cls in (RustedDagger, Container):
            dead_address, dead_handle, replacement = _force_address_reuse(cls)
            assert str(id(replacement)) == dead_address
            assert wire_handle(replacement) != dead_handle


# ---------------------------------------------------------------------------
# One identity per object
# ---------------------------------------------------------------------------


class TestOneIdentityPerObject:
    """A room NPC and the enemy it becomes are one entity with one handle.

    #518 could have namespaced the room scheme separately (``room_<uuid>``).
    It deliberately did not: the client would then hold two unrelated names for
    one Slime and every cross-reference between the panels — clicking the NPC
    you are looking at to attack it — would need a translation table on one
    side or the other. Instead the handle is the identity and the combat
    payload decorates it with a side prefix.
    """

    def test_the_room_id_is_the_combat_ids_suffix(self):
        slime = Slime()

        room_id = NPCSerializer.serialize(slime)["id"]
        combat_id = CombatantSerializer.stream_id(slime)

        assert combat_id == f"enemy_{room_id}"

    def test_combatant_handle_is_the_same_function_not_a_parallel_scheme(self):
        slime = Slime()

        assert combatant_handle is wire_handle
        assert combatant_handle(slime) == wire_handle(slime)

    def test_every_room_payload_names_the_object_the_same_way(self):
        """NPC, item and object serializers agree with the shared minter."""
        slime, dagger, chest = Slime(), RustedDagger(), Container(name="Chest")

        assert NPCSerializer.serialize(slime)["id"] == wire_handle(slime)
        assert ItemSerializer.serialize(dagger)["id"] == wire_handle(dagger)
        assert ObjectSerializer.serialize(chest)["id"] == wire_handle(chest)

    def test_no_payload_id_looks_like_a_heap_address(self):
        for entity in (Slime(), RustedDagger(), Container(name="Chest")):
            handle = wire_handle(entity)
            assert_opaque_wire_id(handle, type(entity).__name__)
            assert str(id(entity)) not in handle


class TestAClassNeverLendsItsHandleToItsInstances:
    """A handle minted for a CLASS must not become every instance's handle.

    ``wire_handle`` used to read the existing handle with ``getattr``, which
    resolves through the class. A class object's ``__dict__`` is a read-only
    ``mappingproxy``, so minting for one fell through to ``setattr`` and
    stamped the handle on the class itself — after which every instance with no
    handle of its own answered to that one id. One wire id naming many objects
    is exactly the aliasing #511/#518 exist to remove, and nothing would have
    raised.

    Classes reach a serializer in principle: ``_deserialize_saved_instance``
    returns bare class objects for ``__class_type__`` markers.
    """

    def test_minting_for_a_class_does_not_stamp_the_class(self):
        wire_handle(Slime)

        assert COMBAT_HANDLE_ATTR not in Slime.__dict__

    def test_two_instances_of_a_handled_class_get_different_handles(self):
        class Widget:
            pass

        class_handle = wire_handle(Widget)
        first, second = Widget(), Widget()

        assert wire_handle(first) != class_handle
        assert wire_handle(second) != class_handle
        assert wire_handle(first) != wire_handle(second)

    def test_a_class_handle_is_still_stable_across_calls(self):
        class Widget:
            pass

        assert wire_handle(Widget) == wire_handle(Widget)

    def test_an_inherited_handle_attribute_is_not_read_as_the_instances_own(self):
        """The same hazard reached by any other route — a class attribute."""
        class Widget:
            pass

        setattr(Widget, COMBAT_HANDLE_ATTR, "inherited" * 4)
        first, second = Widget(), Widget()

        assert wire_handle(first) != wire_handle(second)
        assert wire_handle(first) != getattr(Widget, COMBAT_HANDLE_ATTR)


class TestHandleDurability:
    def test_an_entity_handle_survives_a_pickle_round_trip(self):
        """Saves pickle the world graph. An id that changed on load would break
        every persisted reference to it — see the buyback ledger below."""
        for entity in (RustedDagger(), Container(name="Chest")):
            before = wire_handle(entity)
            after = wire_handle(pickle.loads(pickle.dumps(entity)))
            assert after == before

    def test_an_entity_saved_before_the_handle_existed_gets_one_on_demand(self):
        dagger = RustedDagger()
        dagger.__dict__.pop(COMBAT_HANDLE_ATTR, None)

        assert wire_handle(dagger)
        assert ItemSerializer.serialize(dagger)["id"] == wire_handle(dagger)

    def test_a_lookup_with_no_id_resolves_to_nothing_and_mints_nothing(self):
        """A falsy id cannot match a 32-hex handle, so the only thing left to
        get wrong is the cost: scanning would mint a handle onto every entity
        in the room to answer a question already answered."""
        room = [Slime(), Slime()]
        for npc in room:
            npc.__dict__.pop(COMBAT_HANDLE_ATTR, None)

        assert find_by_handle(room, "") is None
        assert find_by_handle(room, None) is None
        assert all(COMBAT_HANDLE_ATTR not in npc.__dict__ for npc in room), (
            "a lookup with no id minted handles as a side effect"
        )

    def test_a_lookup_with_an_unknown_id_still_resolves_to_nothing(self):
        room = [Slime(), Slime()]

        assert find_by_handle(room, "0" * 32) is None
        assert find_by_handle(room, wire_handle(room[1])) is room[1]


# ---------------------------------------------------------------------------
# The buyback ledger: the one place a wire id is persisted
# ---------------------------------------------------------------------------


def _stocked_merchant(item):
    merchant = Merchant(
        name="Tester", description="desc", damage=1, aggro=False,
        exp_award=0, stock_count=0,
    )
    merchant.inventory = [item]
    return merchant


def _legacy_entry(item, price=5):
    """A ledger entry exactly as a pre-#518 save wrote it: a decimal address."""
    return {
        "item_id": str(id(item)),
        "item_name": item.name,
        "buyback_price": price,
        "weight": getattr(item, "weight", 0.0),
        "count": 1,
        "type": type(item).__name__,
        "subtype": getattr(item, "subtype", ""),
        "description": getattr(item, "description", ""),
        "value": getattr(item, "value", 0),
        "power": getattr(item, "power", None),
        "beat_acquired": 0,
    }


class TestBuybackLedgerMigration:
    """A pre-migration save's ledger holds decimal ids that can never match a
    handle again. Unmigrated, the stock subtraction in ``serialize_state``
    misses and the just-sold item is offered twice in the BUY tab — once as
    full-price stock and once as buyback."""

    def test_a_legacy_ledger_id_is_repointed_at_the_stock_item_it_names(self):
        item = Restorative(merchandise=True)
        merchant = _stocked_merchant(item)
        merchant._buyback_ledger = [_legacy_entry(item)]

        ShopSerializer.flush_stale_buyback(merchant, 0)

        assert merchant._buyback_ledger[0]["item_id"] == wire_handle(item)

    def test_a_legacy_ledger_no_longer_double_lists_its_item(self):
        item = Restorative(merchandise=True)
        merchant = _stocked_merchant(item)
        merchant._buyback_ledger = [_legacy_entry(item)]
        player = Player()
        player.inventory = []

        ShopSerializer.flush_stale_buyback(merchant, 0)
        state = ShopSerializer.serialize_state(merchant, player, 0)

        # The row's id is the LEDGER ENTRY's handle; its ``item_id`` is the
        # internal pointer at the stock the entry draws from, and that is what
        # the repoint migrated.
        entry = merchant._buyback_ledger[0]
        assert entry["item_id"] == wire_handle(item)
        assert [e["id"] for e in state["buyback_items"]] == [wire_handle(entry)]
        assert state["stock"] == [], (
            "the buyback entry must subtract its item from the stock list; "
            "leaving it in offers the same object twice at two prices"
        )

    def test_an_entry_naming_stock_the_merchant_no_longer_has_is_left_alone(self):
        """Nothing to re-point it at — ``shop_buyback`` reports and drops it.

        The id is captured BEFORE the flush. Comparing the ledger to the entry
        object it already holds (``ledger == [entry]``) is true however much
        the repoint mutated ``entry["item_id"]`` in place — it proves only that
        the entry was not dropped, which is not what "left alone" claims.
        """
        sold_on = Restorative(merchandise=True)
        merchant = _stocked_merchant(RustedDagger())
        entry = _legacy_entry(sold_on)
        original_item_id = entry["item_id"]
        merchant._buyback_ledger = [entry]

        ShopSerializer.flush_stale_buyback(merchant, 0)

        assert merchant._buyback_ledger == [entry]
        assert entry["item_id"] == original_item_id

    def test_repointing_does_not_disturb_an_already_current_ledger(self):
        """Two same-named stock items, and the entry names the SECOND.

        With only one stocked item, "skipped the entry" and "rewrote it to the
        handle it already had" are indistinguishable. The name fallback returns
        the *first* name match, so pointing the entry at the second is a target
        an unconditional rewrite could not reproduce.
        """
        first, second = Restorative(merchandise=True), Restorative(merchandise=True)
        merchant = _stocked_merchant(first)
        merchant.inventory = [first, second]
        entry = _legacy_entry(second)
        entry["item_id"] = wire_handle(second)
        merchant._buyback_ledger = [entry]

        ShopSerializer.flush_stale_buyback(merchant, 0)

        assert merchant._buyback_ledger[0]["item_id"] == wire_handle(second)
        assert merchant._buyback_ledger[0]["item_id"] != wire_handle(first)

    def test_a_legacy_ledger_entry_can_still_be_bought_back(self):
        item = Restorative(merchandise=True)
        item.value = 10
        merchant = _stocked_merchant(item)
        merchant._buyback_ledger = [_legacy_entry(item, price=5)]

        player = Player()
        player.universe = type("U", (), {"game_tick": 0})()
        player.inventory = []
        from tests._gs_fixtures import set_player_gold
        set_player_gold(player, 100)

        gs = GameService()
        gs._find_merchant = lambda p, nid: merchant

        # The client only ever holds the id the payload published, so redeem
        # through that rather than through the stock item's handle.
        row = ShopSerializer.serialize_state(merchant, player, 0)["buyback_items"][0]

        result = gs.shop_buyback(player, "npc1", row["id"])

        assert result["success"], result.get("error")
        assert any(getattr(i, "name", None) == "Restorative"
                   for i in player.inventory)


# ---------------------------------------------------------------------------
# A ledger entry claims COUNTS of a stock item, not the object
# ---------------------------------------------------------------------------


def _sell_one(gs, player, merchant, item):
    """Sell a single unit of ``item`` to ``merchant`` and return the result."""
    return gs.shop_sell(player, wire_handle(merchant), wire_handle(item), 1)


class TestALedgerEntryClaimsCountsNotTheWholeStock:
    """Selling into a stack must not take the whole stack off the BUY tab.

    ``stack_inv_items`` merges a sold unit into the merchant's pre-existing
    same-name stack, so the ledger entry ends up naming that whole stack. While
    ``serialize_state`` excluded any stock object the ledger named, selling one
    Restorative to a merchant holding five removed all six from the BUY tab and
    offered a single buyback row in their place — five units of stock the player
    could no longer buy until the beat advanced.
    """

    def test_selling_into_a_stack_leaves_the_rest_of_the_stack_on_sale(self):
        stock = Restorative(count=5, merchandise=True)
        stock.value = 10
        player, _, merchant = live_shop(stock=[stock, Gold(500)])
        goods = Restorative()
        goods.value = 10
        player.inventory.append(goods)
        gs = GameService()

        assert _sell_one(gs, player, merchant, goods)["success"]
        state = ShopSerializer.serialize_state(merchant, player, 0)

        assert [(r["name"], r["count"]) for r in state["stock"]] == [
            ("Restorative", 5)
        ], "the merchant's own stock must survive a sale into it"
        assert [r["count"] for r in state["buyback_items"]] == [1]

    def test_the_last_claimed_unit_drops_the_row_rather_than_showing_zero(self):
        player, _, merchant = live_shop(stock=[Gold(500)])
        goods = Restorative()
        goods.value = 10
        player.inventory.append(goods)
        gs = GameService()

        assert _sell_one(gs, player, merchant, goods)["success"]
        state = ShopSerializer.serialize_state(merchant, player, 0)

        assert state["stock"] == []
        assert len(state["buyback_items"]) == 1


class TestTwoOffersOnOneStackAreTellableApart:
    """Two sales of one item name collapse onto one merchant stack.

    While the buyback row's ``id`` was that stack's handle, both rows shipped
    the SAME id — duplicate list keys on the client, and ``shop_buyback``
    redeemed whichever entry it scanned first. Clicking the cheaper row charged
    the dearer row's price. The row id is the ledger ENTRY's handle now.
    """

    @staticmethod
    def _two_sales_at_different_prices():
        player, _, merchant = live_shop(stock=[Gold(500)], player_gold=500)
        first, second = Restorative(), Restorative()
        for item in (first, second):
            item.value = 10
        player.inventory.extend([first, second])
        gs = GameService()

        assert _sell_one(gs, player, merchant, first)["success"]
        merchant.sell_modifier = 0.1  # the second sale is booked cheaper
        assert _sell_one(gs, player, merchant, second)["success"]
        return gs, player, merchant

    def test_the_two_rows_carry_different_ids(self):
        gs, player, merchant = self._two_sales_at_different_prices()

        rows = ShopSerializer.serialize_state(merchant, player, 0)["buyback_items"]

        assert len(rows) == 2
        assert len({r["id"] for r in rows}) == 2
        assert {r["price"] for r in rows} == {5, 1}

    def test_buying_back_charges_the_price_of_the_row_that_was_clicked(self):
        gs, player, merchant = self._two_sales_at_different_prices()
        rows = ShopSerializer.serialize_state(merchant, player, 0)["buyback_items"]
        cheap = min(rows, key=lambda r: r["price"])

        result = gs.shop_buyback(player, wire_handle(merchant), cheap["id"])

        assert result["success"], result.get("error")
        assert result["gold_spent"] == cheap["price"]
