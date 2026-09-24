"""Issue #643: a pre-#624 save's baked stack name is normalised on load.

Before #624, ``MineralPowder`` and ``DriedCrystalSap`` wrote the stack size
into ``item.name`` ("Mineral Powder x3"). ``name`` is ordinary pickled state,
so an old save restores that name verbatim. Stacking keys on ``stack_key``,
so the stack still merges with a fresh unit -- but the merged stack keeps the
baked name at a count it no longer matches, and from then on nothing (not
even ``stack_base_name``) can recover it; the name-keyed buyback lookup and
the display both see "Mineral Powder x3" on a stack of four.

These round-trip real items through ``src.secure_pickle``'s ``SafeUnpickler``
(the loader every save goes through), not ``__setstate__`` by hand.
"""

import io

from src.api.serializers.shop_serializer import find_stock_by_name
from src.functions import stack_items_list
from src.items import DriedCrystalSap, MineralPowder
from src.secure_pickle import safe_pickle_load, serialize_for_save


def _round_trip(obj):
    """Save and load ``obj`` through the real headered, strict save path."""
    return safe_pickle_load(io.BytesIO(serialize_for_save(obj)), strict=True)


def _baked(cls, base, count):
    """A stack as a pre-#624 save left it: count baked into the name."""
    item = cls()
    item.count = count
    item.name = f"{base} x{count}"
    return item


class TestBakedStackNameNormalisedOnLoad:
    def test_mineral_powder_baked_name_is_stripped(self):
        loaded = _round_trip(_baked(MineralPowder, "Mineral Powder", 3))
        assert type(loaded) is MineralPowder
        assert loaded.name == "Mineral Powder"
        assert loaded.count == 3

    def test_dried_crystal_sap_baked_name_is_stripped(self):
        loaded = _round_trip(_baked(DriedCrystalSap, "Dried Crystal Sap", 2))
        assert loaded.name == "Dried Crystal Sap"
        assert loaded.count == 2

    def test_loaded_stack_merges_with_a_fresh_unit_under_the_clean_name(self):
        loaded = _round_trip(_baked(MineralPowder, "Mineral Powder", 3))
        pile = [loaded, MineralPowder()]
        stack_items_list(pile)
        assert len(pile) == 1
        assert pile[0].count == 4
        assert pile[0].name == "Mineral Powder"
        # The buyback ledger's name fallback finds it under the real name.
        assert find_stock_by_name(pile, "Mineral Powder", "MineralPowder") is pile[0]

    def test_suffix_that_does_not_match_the_count_is_kept(self):
        item = MineralPowder()
        item.count = 2
        item.name = "Potion x3"
        assert _round_trip(item).name == "Potion x3"

    def test_suffix_on_a_single_unit_is_kept(self):
        item = MineralPowder()
        item.count = 1
        item.name = "Mineral Powder x1"
        assert _round_trip(item).name == "Mineral Powder x1"

    def test_fresh_item_round_trips_unchanged(self):
        item = MineralPowder()
        item.count = 5
        loaded = _round_trip(item)
        assert loaded.name == "Mineral Powder"
        assert loaded.count == 5
        assert loaded.stack_key == "Mineral Powder"

    def test_non_stackable_item_name_is_untouched(self):
        from src.items import Item

        item = Item("Relic x3", "An odd relic.", 1, "Special", "Relic", "a relic.")
        assert not hasattr(item, "count")
        assert _round_trip(item).name == "Relic x3"

    def test_loaded_item_keeps_its_own_wire_handle(self):
        """The override restores like default BUILD: a saved item's handle
        survives the load (it is the same item, not a split)."""
        from src.combatant import wire_handle

        item = _baked(MineralPowder, "Mineral Powder", 3)
        handle = wire_handle(item)
        assert wire_handle(_round_trip(item)) == handle


def test_a_non_string_name_survives_load_untouched():
    """A malformed save (name=None) must not have its name rewritten to ""."""
    from src.items import MineralPowder

    item = MineralPowder.__new__(MineralPowder)
    item.__setstate__({"name": None, "count": 3})
    assert item.name is None


def test_an_unconvertible_count_does_not_abort_the_load():
    """``int(inf)`` raises OverflowError; one bad stack must not fail a save."""
    from src.items import MineralPowder

    item = MineralPowder.__new__(MineralPowder)
    item.__setstate__({"name": "Mineral Powder x3", "count": float("inf")})
    assert item.name == "Mineral Powder x3"
