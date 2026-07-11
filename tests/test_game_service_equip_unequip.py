"""Characterization tests for the canonical equip/unequip/drop path.

These exercise the *real* engine mechanics (``Player.equip_item`` /
``Player.unequip_item``) through ``GameService`` with a real ``Player`` and
realistic item stand-ins, locking in the behavior of the hybrid delegation
introduced for issue #260:

- ``GameService.equip_item`` is a toggle (equip / unequip) plus a merchandise
  guard, delegating the core mechanics to the engine.
- ``GameService.unequip_item`` delegates to the new engine
  ``Player.unequip_item``.
- ``GameService.drop_item`` unequips an equipped item before moving it to the
  current tile.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player():
    """Return a real Player with a minimal tile/universe for inventory methods."""
    from src.player import Player

    p = Player()
    p.weight_tolerance = 100.0
    p.weight_current = 0.0
    p.combat_exp = {}
    p.skill_exp = {}
    p.testing_mode = False
    tile = MagicMock()
    tile.items_here = []
    p.current_room = tile
    p.tile = tile
    return p


def _make_equippable(maintype="Weapon", subtype="Sword", name="TestSword"):
    """Return an equippable item stand-in with real interaction/state fields."""
    item = MagicMock()
    item.name = name
    item.announce = name.lower()
    item.maintype = maintype
    item.subtype = subtype
    item.isequipped = False
    item.merchandise = False
    item.gives_exp = False
    item.weight = 1.0
    item.interactions = ["equip"]
    item.on_equip = MagicMock()
    item.on_unequip = MagicMock()
    return item


@pytest.fixture
def game_service():
    from src.api.services.game_service import GameService

    return GameService()


# ---------------------------------------------------------------------------
# Engine: Player.unequip_item
# ---------------------------------------------------------------------------


def test_engine_unequip_weapon_resets_to_fists():
    p = _make_player()
    item = _make_equippable(maintype="Weapon")
    item.isequipped = True
    item.interactions = ["unequip"]
    p.inventory = [item]
    p.eq_weapon = item

    with (
        patch("src.player._inventory.functions.refresh_stat_bonuses") as mock_refresh,
        patch("src.player._inventory.cprint"),
    ):
        p.unequip_item(item_object=item)

    assert item.isequipped is False
    item.on_unequip.assert_called_once_with(p)
    assert "unequip" not in item.interactions
    assert "equip" in item.interactions
    assert p.eq_weapon is getattr(p, "fists", None)
    mock_refresh.assert_called_once_with(p)


def test_engine_unequip_not_equipped_is_noop():
    p = _make_player()
    item = _make_equippable(maintype="Armor")
    item.isequipped = False
    p.inventory = [item]

    with patch("src.player._inventory.functions.refresh_stat_bonuses") as mock_refresh:
        p.unequip_item(item_object=item)

    assert item.isequipped is False
    item.on_unequip.assert_not_called()
    mock_refresh.assert_not_called()


# ---------------------------------------------------------------------------
# GameService.equip_item (toggle + merchandise guard + delegation)
# ---------------------------------------------------------------------------


def test_service_equip_equips_weapon(game_service):
    p = _make_player()
    item = _make_equippable(maintype="Weapon")
    p.inventory = [item]

    with (
        patch("src.player._inventory.functions.refresh_stat_bonuses"),
        patch("src.player._inventory.cprint"),
    ):
        result = game_service.equip_item(p, item)

    assert result["success"] is True
    assert "equipped" in result["message"]
    assert item.isequipped is True
    assert p.eq_weapon is item


def test_service_equip_toggles_unequip_when_equipped(game_service):
    p = _make_player()
    item = _make_equippable(maintype="Armor")
    item.isequipped = True
    item.interactions = ["unequip"]
    p.inventory = [item]

    with (
        patch("src.player._inventory.functions.refresh_stat_bonuses"),
        patch("src.player._inventory.cprint"),
    ):
        result = game_service.equip_item(p, item)

    assert result["success"] is True
    assert "unequipped" in result["message"]
    assert item.isequipped is False


def test_service_equip_rejects_merchandise(game_service):
    p = _make_player()
    item = _make_equippable()
    item.merchandise = True
    p.inventory = [item]

    result = game_service.equip_item(p, item)

    assert "error" in result
    assert "purchase" in result["error"].lower()
    assert item.isequipped is False


def test_service_equip_rejects_non_equippable(game_service):
    p = _make_player()
    item = MagicMock(spec=["name"])
    item.name = "Herb"

    result = game_service.equip_item(p, item)

    assert "error" in result
    assert "cannot be equipped" in result["error"].lower()


# ---------------------------------------------------------------------------
# GameService.unequip_item
# ---------------------------------------------------------------------------


def test_service_unequip_success(game_service):
    p = _make_player()
    item = _make_equippable(maintype="Armor")
    item.isequipped = True
    item.interactions = ["unequip"]
    p.inventory = [item]

    with (
        patch("src.player._inventory.functions.refresh_stat_bonuses"),
        patch("src.player._inventory.cprint"),
    ):
        result = game_service.unequip_item(p, item)

    assert result["success"] is True
    assert "unequipped" in result["message"]
    assert item.isequipped is False


def test_service_unequip_not_equipped_errors(game_service):
    p = _make_player()
    item = _make_equippable(maintype="Armor")
    item.isequipped = False
    p.inventory = [item]

    result = game_service.unequip_item(p, item)

    assert "error" in result
    assert "not equipped" in result["error"].lower()


# ---------------------------------------------------------------------------
# GameService.drop_item (unequips equipped item, moves to tile)
# ---------------------------------------------------------------------------


def test_service_drop_equipped_item_unequips_then_drops(game_service):
    p = _make_player()
    item = _make_equippable(maintype="Weapon")
    item.isequipped = True
    item.interactions = ["unequip"]
    p.inventory = [item]
    p.eq_weapon = item

    tile = MagicMock()
    tile.items_here = []
    p.universe = MagicMock()
    p.universe.get_tile.return_value = tile

    with (
        patch("src.player._inventory.functions.refresh_stat_bonuses"),
        patch("src.player._inventory.cprint"),
    ):
        result = game_service.drop_item(p, item)

    assert result["success"] is True
    assert item.isequipped is False
    assert item in tile.items_here
    assert item not in p.inventory
    assert p.eq_weapon is getattr(p, "fists", None)


# ---------------------------------------------------------------------------
# Narration capture — engine flavor is surfaced via the `messages` field
# ---------------------------------------------------------------------------


def test_service_equip_returns_engine_narration(game_service):
    """cprint flavor from the engine equip is captured into `messages`."""
    p = _make_player()
    item = _make_equippable(maintype="Weapon", name="TestSword")
    p.inventory = [item]

    # Note: cprint is NOT patched here so real narration flows into the sink.
    with patch("src.player._inventory.functions.refresh_stat_bonuses"):
        result = game_service.equip_item(p, item)

    assert result["success"] is True
    assert any("equipped" in m.lower() for m in result["messages"])


def test_service_drop_returns_drop_narration(game_service):
    """A plain drop narrates the drop itself into `messages`."""
    p = _make_player()
    item = _make_equippable(name="TestSword")
    item.isequipped = False
    p.inventory = [item]

    tile = MagicMock()
    tile.items_here = []
    p.universe = MagicMock()
    p.universe.get_tile.return_value = tile

    result = game_service.drop_item(p, item)

    assert result["success"] is True
    assert any("drops" in m.lower() for m in result["messages"])


def test_service_drop_equipped_returns_unequip_narration(game_service):
    """The unequip-before-drop flavor is captured into `messages`."""
    p = _make_player()
    item = _make_equippable(maintype="Weapon", name="TestSword")
    item.isequipped = True
    item.interactions = ["unequip"]
    p.inventory = [item]
    p.eq_weapon = item

    tile = MagicMock()
    tile.items_here = []
    p.universe = MagicMock()
    p.universe.get_tile.return_value = tile

    with patch("src.player._inventory.functions.refresh_stat_bonuses"):
        result = game_service.drop_item(p, item)

    assert result["success"] is True
    assert any("back into his bag" in m.lower() for m in result["messages"])
