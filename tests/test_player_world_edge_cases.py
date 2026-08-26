"""Coverage tests for src/player/_world.py edge cases.

Every test here pins the *observable* outcome of ``refresh_merchants`` — the
summary line it narrates through ``cprint`` — rather than merely asserting that
no exception escaped. The distinction matters: the defensive ``except`` clauses
in ``_world.py`` exist so that one broken NPC cannot abort the sweep, and the
only way to see whether the sweep actually continued (versus silently
short-circuiting) is the success/failure tally in that summary.
"""

from unittest.mock import MagicMock, patch




def _universe_with_tile(tile):
    """A universe whose single map holds ``tile`` at (0, 0)."""
    universe = MagicMock()
    universe.maps = [{"name": "test", (0, 0): tile}]
    return universe


def _tile_with_npc(npc):
    tile = MagicMock()
    tile.npcs_here = [npc]
    return tile


def _refresh(player, phrase=""):
    """Run refresh_merchants and return the narrated lines as a list of strings."""
    lines = []
    with patch(
        "src.player._world.cprint", side_effect=lambda text, *a, **kw: lines.append(text)
    ), patch("time.sleep"):
        player.refresh_merchants(phrase)
    return lines


class Merchant:
    """Stand-in base: ``_is_merchant_instance`` matches on the class *name*
    ``Merchant`` anywhere in the MRO, so this local class is what makes the
    subclasses below register as merchants."""


class TestRefreshMerchantsGuards:
    def test_no_universe_reports_and_returns(self, player):
        player.universe = None
        assert _refresh(player) == [
            "Universe not initialized; cannot refresh merchants."
        ]

    def test_universe_without_maps_reports_and_returns(self, player):
        universe = MagicMock(spec=[])  # no ``maps`` attribute at all
        player.universe = universe
        assert _refresh(player) == [
            "Universe not initialized; cannot refresh merchants."
        ]


class TestIsMerchantInstanceEdgeCases:
    """Objects that are not merchants must be rejected, never crash the sweep."""

    def test_npc_is_none(self, player):
        player.universe = _universe_with_tile(_tile_with_npc(None))
        assert _refresh(player) == ["No merchants found to refresh."]

    def test_npc_mro_not_callable(self, player):
        class Weird:
            pass

        Weird.mro = "not_callable"
        try:
            player.universe = _universe_with_tile(_tile_with_npc(Weird()))
            assert _refresh(player) == ["No merchants found to refresh."]
        finally:
            del Weird.mro

    def test_npc_mro_raises_exception(self, player):
        class BrokenMRO:
            @classmethod
            def mro(cls):
                raise RuntimeError("MRO broken")

        player.universe = _universe_with_tile(
            _tile_with_npc(object.__new__(BrokenMRO))
        )
        assert _refresh(player) == ["No merchants found to refresh."]

    def test_none_tile_skipped(self, player):
        universe = MagicMock()
        universe.maps = [{"name": "test", (0, 0): None}]
        player.universe = universe
        assert _refresh(player) == ["No merchants found to refresh."]

    def test_non_dict_map_skipped(self, player):
        universe = MagicMock()
        universe.maps = ["not-a-map", None, 42]
        player.universe = universe
        assert _refresh(player) == ["No merchants found to refresh."]

    def test_npc_body_exception_after_is_merchant_skipped(self, player):
        """A merchant whose ``name`` explodes is dropped, not counted, not fatal."""

        class ExplodingName(Merchant):
            @property
            def name(self):
                raise RuntimeError("name property exploded")

        player.universe = _universe_with_tile(_tile_with_npc(ExplodingName()))
        assert _refresh(player) == ["No merchants found to refresh."]


class TestRefreshMerchantsOutcomes:
    def test_initialize_shop_raises_but_update_goods_still_runs(self, player):
        """A failing initialize_shop is non-fatal; the merchant still counts as refreshed."""

        class BrokenInit(Merchant):
            def __init__(self):
                self.name = "BrokenInit"
                self.shop = None
                self.update_calls = 0

            def initialize_shop(self):
                raise RuntimeError("init failed")

            def update_goods(self):
                self.update_calls += 1

        m = BrokenInit()
        player.universe = _universe_with_tile(_tile_with_npc(m))

        lines = _refresh(player)

        assert m.update_calls == 1
        assert lines == ["Merchant refresh complete: 1 succeeded, 0 failed."]

    def test_outer_exception_recorded_as_named_failure(self, player):
        """An exception reading ``shop`` is reported against that merchant by name."""

        class TotallyBroken(Merchant):
            name = "TotallyBroken"

            @property
            def shop(self):
                raise RuntimeError("property exploded")

        player.universe = _universe_with_tile(_tile_with_npc(TotallyBroken()))

        lines = _refresh(player)

        assert lines == [
            "Merchant refresh complete: 0 succeeded, 1 failed.",
            " - TotallyBroken: property exploded",
        ]

    def test_update_goods_exception_recorded_as_named_failure(self, player):
        class UpdateExplodes(Merchant):
            name = "Sprocket"
            shop = object()

            def update_goods(self):
                raise ValueError("stock table missing")

        player.universe = _universe_with_tile(_tile_with_npc(UpdateExplodes()))

        assert _refresh(player) == [
            "Merchant refresh complete: 0 succeeded, 1 failed.",
            " - Sprocket: stock table missing",
        ]

    def test_merchant_without_update_goods_is_a_failure(self, player):
        class NoUpdate(Merchant):
            name = "Stumpy"
            shop = object()

        player.universe = _universe_with_tile(_tile_with_npc(NoUpdate()))

        assert _refresh(player) == [
            "Merchant refresh complete: 0 succeeded, 1 failed.",
            " - Stumpy: missing update_goods",
        ]

    def test_phrase_filters_by_case_insensitive_substring(self, player):
        class Vendor(Merchant):
            def __init__(self, name):
                self.name = name
                self.shop = object()
                self.update_calls = 0

            def update_goods(self):
                self.update_calls += 1

        wanted = Vendor("Gorran the Smith")
        other = Vendor("Fishmonger")
        tile = MagicMock()
        tile.npcs_here = [wanted, other]
        player.universe = _universe_with_tile(tile)

        lines = _refresh(player, phrase="  GORRAN ")

        assert wanted.update_calls == 1
        assert other.update_calls == 0
        assert lines == ["Merchant refresh complete: 1 succeeded, 0 failed."]

    def test_phrase_with_no_match_reports_the_filter(self, player):
        class Vendor(Merchant):
            name = "Fishmonger"
            shop = object()

            def update_goods(self):
                pass

        player.universe = _universe_with_tile(_tile_with_npc(Vendor()))

        assert _refresh(player, phrase="Gorran") == [
            "No merchants matched filter 'gorran'."
        ]

    def test_failure_list_is_capped_at_ten_lines(self, player):
        """Twelve broken merchants produce a summary plus at most ten detail lines."""

        class Broken(Merchant):
            def __init__(self, idx):
                self.name = f"Broken{idx}"
                self.shop = object()

            def update_goods(self):
                raise RuntimeError("boom")

        tile = MagicMock()
        tile.npcs_here = [Broken(i) for i in range(12)]
        player.universe = _universe_with_tile(tile)

        lines = _refresh(player)

        assert lines[0] == "Merchant refresh complete: 0 succeeded, 12 failed."
        assert len(lines) == 11
        assert lines[1] == " - Broken0: boom"
        assert lines[-1] == " - Broken9: boom"
