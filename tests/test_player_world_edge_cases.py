"""Additional coverage tests for src/player/_world.py edge cases.

Targets the remaining uncovered branches:
  27, 30, 34, 36-37 — _is_merchant_instance() corner cases
  47, 55-57 — None tile and exception in npc iteration
  78-80 — initialize_shop() raises
  95-96 — outer exception handler for m
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent


import pytest
from src.player import Player


def _player():
    return Player()


def _make_tile_with_npc(npc):
    tile = MagicMock()
    tile.npcs_here = [npc]
    return tile


class TestIsMerchantInstanceEdgeCases:
    """Force the _is_merchant_instance nested function's corner-case branches."""

    def test_npc_is_none(self):
        """Line 26-27: obj is None — _is_merchant_instance returns False immediately."""
        p = _player()

        tile = _make_tile_with_npc(None)  # NPC is None
        universe = MagicMock()
        universe.maps = [{"name": "test", (0, 0): tile}]
        p.universe = universe

        with patch("src.player._world.cprint"), patch("time.sleep"):
            p.refresh_merchants()  # Should not crash

    def test_npc_mro_not_callable(self):
        """Line 32-34: cls.mro is not callable — returns False."""
        p = _player()

        class NPC:
            pass

        npc = NPC()
        # Replace mro with a non-callable
        NPC.mro = "not_callable"

        tile = _make_tile_with_npc(npc)
        universe = MagicMock()
        universe.maps = [{"name": "test", (0, 0): tile}]
        p.universe = universe

        try:
            with patch("src.player._world.cprint"), patch("time.sleep"):
                p.refresh_merchants()  # Should not crash
        finally:
            # Restore mro
            del NPC.mro

    def test_npc_mro_raises_exception(self):
        """Lines 36-37: cls.mro() raises — _is_merchant_instance returns False."""
        p = _player()

        class BrokenMROClass:
            @classmethod
            def mro(cls):
                raise RuntimeError("MRO broken")

        npc = object.__new__(BrokenMROClass)

        tile = _make_tile_with_npc(npc)
        universe = MagicMock()
        universe.maps = [{"name": "test", (0, 0): tile}]
        p.universe = universe

        with patch("src.player._world.cprint"), patch("time.sleep"):
            p.refresh_merchants()  # Should not crash

    def test_none_tile_skipped(self):
        """Line 47: None tile in map is skipped."""
        p = _player()
        universe = MagicMock()
        # Map with None tile at a coordinate
        universe.maps = [{"name": "test", (0, 0): None}]
        p.universe = universe

        with patch("src.player._world.cprint") as mock_cp, patch("time.sleep"):
            p.refresh_merchants()

        # No merchants found — cprint may or may not be called depending on implementation
        # The important thing is no exception was raised

    def test_npc_body_exception_after_is_merchant_skipped(self):
        """Lines 55-57: exception after _is_merchant_instance returns True is silently skipped.

        The NPC has Merchant in its MRO so _is_merchant_instance returns True, but
        then accessing .name raises, which should be caught by the outer try/except.
        """
        p = _player()

        class Merchant:
            pass

        class ExplodingNameMerchant(Merchant):
            @property
            def name(self):
                raise RuntimeError("name property exploded")

        npc = ExplodingNameMerchant()

        tile = _make_tile_with_npc(npc)
        universe = MagicMock()
        universe.maps = [{"name": "test", (0, 0): tile}]
        p.universe = universe

        with patch("src.player._world.cprint"), patch("time.sleep"):
            p.refresh_merchants()  # Should not crash

    def test_initialize_shop_raises_continues(self):
        """Lines 78-80: initialize_shop() raises — non-fatal, update_goods still tried."""

        class Merchant:
            pass

        class BrokenInitMerchant(Merchant):
            def __init__(self):
                self.name = "BrokenInit"
                self.shop = None
                self._update_called = False

            def initialize_shop(self):
                raise RuntimeError("init failed")

            def update_goods(self):
                self._update_called = True

        m = BrokenInitMerchant()
        p = _player()

        tile = _make_tile_with_npc(m)
        universe = MagicMock()
        universe.maps = [{"name": "test", (0, 0): tile}]
        p.universe = universe

        with patch("src.player._world.cprint"), patch("time.sleep"):
            p.refresh_merchants()

        # update_goods should still be called despite initialize_shop failing
        assert m._update_called is True

    def test_outer_exception_captured_in_failures(self):
        """Lines 95-96: outer exception for merchant captured in failures list."""

        class Merchant:
            pass

        class TotallyBrokenMerchant(Merchant):
            def __init__(self):
                self.name = "TotallyBroken"

            @property
            def shop(self):
                raise RuntimeError("property exploded")

        m = TotallyBrokenMerchant()
        p = _player()

        tile = _make_tile_with_npc(m)
        universe = MagicMock()
        universe.maps = [{"name": "test", (0, 0): tile}]
        p.universe = universe

        with patch("src.player._world.cprint"), patch("time.sleep"):
            p.refresh_merchants()  # Should not raise
