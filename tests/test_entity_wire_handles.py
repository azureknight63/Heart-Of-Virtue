"""Regression tests for the non-combat wire-id scheme (issue #518).

Issue #511 replaced ``id(combatant)`` with an opaque handle for the *combat*
payload. Everything else the API gives the client an identity for — the NPCs,
world objects and floor items in a room, container contents, inventory rows,
merchants, shop stock and events — kept minting its id as ``str(id(entity))``.
That was the same defect in a different payload:

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
from src.items import Restorative, RustedDagger
from src.npc._enemies import Slime
from src.npc._merchants import Merchant
from src.objects import Container
from src.player import Player
from tests._gs_fixtures import live_world


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
        dead_address, _, replacement = _force_address_reuse(Slime)

        # This IS the old wire id, recomputed for a different object. A client
        # still holding the dead Slime's id would have addressed this one.
        assert str(id(replacement)) == dead_address

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
            assert not handle.isdigit(), f"{handle!r} is a decimal address"
            assert str(id(entity)) not in handle


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

    def test_find_by_handle_refuses_to_resolve_an_empty_id(self):
        """An absent id must not silently address the first entity present."""
        room = [Slime(), Slime()]

        assert find_by_handle(room, "") is None
        assert find_by_handle(room, None) is None


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

        assert [e["id"] for e in state["buyback_items"]] == [wire_handle(item)]
        assert state["stock"] == [], (
            "the buyback entry must subtract its item from the stock list; "
            "leaving it in offers the same object twice at two prices"
        )

    def test_an_entry_naming_stock_the_merchant_no_longer_has_is_left_alone(self):
        """Nothing to re-point it at — ``shop_buyback`` reports and drops it."""
        sold_on = Restorative(merchandise=True)
        merchant = _stocked_merchant(RustedDagger())
        entry = _legacy_entry(sold_on)
        merchant._buyback_ledger = [entry]

        ShopSerializer.flush_stale_buyback(merchant, 0)

        assert merchant._buyback_ledger == [entry]

    def test_repointing_does_not_disturb_an_already_current_ledger(self):
        item = Restorative(merchandise=True)
        merchant = _stocked_merchant(item)
        entry = _legacy_entry(item)
        entry["item_id"] = wire_handle(item)
        merchant._buyback_ledger = [entry]

        ShopSerializer.flush_stale_buyback(merchant, 0)

        assert merchant._buyback_ledger[0]["item_id"] == wire_handle(item)

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

        result = gs.shop_buyback(player, "npc1", wire_handle(item))

        assert result["success"], result.get("error")
        assert any(getattr(i, "name", None) == "Restorative"
                   for i in player.inventory)
