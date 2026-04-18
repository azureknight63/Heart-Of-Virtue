"""
Unit tests for ally-healing targeting feature.

Covers:
- _resolve_ally_target: valid/invalid IDs, prefix stripping
- _npc_try_heal_ally: finds most-injured ally, respects range, consumes item, error safety
"""

import contextlib
import pytest
from unittest.mock import MagicMock, patch

from src.api.routes.inventory import _resolve_ally_target
from src.api.constants import ITEM_USE_RANGE, ALLY_HEAL_THRESHOLD

# ---------------------------------------------------------------------------
# _resolve_ally_target
# ---------------------------------------------------------------------------


def _make_player_with_allies(*allies):
    player = MagicMock()
    player.combat_list_allies = [player] + list(allies)  # index 0 = player
    return player


def test_resolve_ally_target_valid():
    ally = MagicMock()
    player = _make_player_with_allies(ally)
    assert _resolve_ally_target(player, f"ally_{id(ally)}") is ally


def test_resolve_ally_target_enemy_prefix_not_stripped():
    """enemy_ prefix must NOT be resolved as an ally — that was a bug (M2 fix)."""
    ally = MagicMock()
    player = _make_player_with_allies(ally)
    assert _resolve_ally_target(player, f"enemy_{id(ally)}") is None


def test_resolve_ally_target_unknown_id_returns_none():
    ally = MagicMock()
    player = _make_player_with_allies(ally)
    assert _resolve_ally_target(player, "ally_99999999") is None


def test_resolve_ally_target_no_allies_returns_none():
    player = MagicMock()
    player.combat_list_allies = [player]
    assert _resolve_ally_target(player, "ally_1") is None


def test_resolve_ally_target_skips_player_at_index_zero():
    """The player at index 0 must never be returned."""
    player = MagicMock()
    player.combat_list_allies = [player]
    assert _resolve_ally_target(player, f"ally_{id(player)}") is None


# ---------------------------------------------------------------------------
# _npc_try_heal_ally helpers
# ---------------------------------------------------------------------------


def _make_adapter():
    from src.api.combat_adapter import ApiCombatAdapter

    adapter = ApiCombatAdapter.__new__(ApiCombatAdapter)
    player = MagicMock()
    player.name = "Jean"
    player.hp = 100
    player.maxhp = 100
    player.is_alive.return_value = True
    player.combat_beat = 1
    adapter.player = player
    adapter.current_beat_state_index = 0
    adapter._add_log_entry = MagicMock()

    @contextlib.contextmanager
    def _noop_capture():
        yield

    adapter._capture_output = _noop_capture
    return adapter


def _make_npc(friend=True):
    npc = MagicMock()
    npc.name = "Gorran"
    npc.friend = friend
    npc.hp = 100
    npc.maxhp = 100
    npc.is_alive.return_value = True
    npc.combat_proximity = {}
    return npc


def _make_ally(hp=20, maxhp=100):
    ally = MagicMock()
    ally.name = "AllyNPC"
    ally.hp = hp
    ally.maxhp = maxhp
    ally.is_alive.return_value = True
    return ally


def _run_heal(adapter, npc):
    with patch("items.Consumable", MagicMock) as mock_cls:
        mock_cls.__instancecheck__ = lambda cls, obj: True
        return adapter._npc_try_heal_ally(npc)


# ---------------------------------------------------------------------------
# _npc_try_heal_ally tests
# ---------------------------------------------------------------------------


def test_npc_try_heal_ally_heals_injured_friendly():
    adapter = _make_adapter()
    npc = _make_npc(friend=True)
    ally = _make_ally(hp=20, maxhp=100)
    npc.combat_proximity = {ally: 3}

    item = MagicMock(name="Health Potion")
    npc.inventory = [item]
    adapter.player.combat_list_allies = [adapter.player, ally]

    result = _run_heal(adapter, npc)

    item.use.assert_called_once_with(ally, user=npc)
    assert result is True
    assert item not in npc.inventory


def test_npc_try_heal_ally_skips_out_of_range():
    adapter = _make_adapter()
    npc = _make_npc(friend=True)
    ally = _make_ally(hp=10, maxhp=100)
    npc.combat_proximity = {ally: ITEM_USE_RANGE + 1}

    item = MagicMock(name="Health Potion")
    npc.inventory = [item]
    adapter.player.combat_list_allies = [adapter.player, ally]

    result = _run_heal(adapter, npc)

    item.use.assert_not_called()
    assert result is False


def test_npc_try_heal_ally_skips_healthy_ally():
    adapter = _make_adapter()
    npc = _make_npc(friend=True)
    ally = _make_ally(hp=80, maxhp=100)  # 80% HP — above threshold
    npc.combat_proximity = {ally: 2}

    item = MagicMock(name="Health Potion")
    npc.inventory = [item]
    adapter.player.combat_list_allies = [adapter.player, ally]

    result = _run_heal(adapter, npc)

    item.use.assert_not_called()
    assert result is False


def test_npc_try_heal_ally_exception_does_not_consume_item():
    """If item.use() raises, item must not be removed and False is returned."""
    adapter = _make_adapter()
    npc = _make_npc(friend=True)
    ally = _make_ally(hp=10, maxhp=100)
    npc.combat_proximity = {ally: 2}

    item = MagicMock(name="Health Potion")
    item.use.side_effect = RuntimeError("item exploded")
    npc.inventory = [item]
    adapter.player.combat_list_allies = [adapter.player, ally]

    result = _run_heal(adapter, npc)

    assert result is False
    assert item in npc.inventory


def test_npc_try_heal_ally_no_consumables():
    adapter = _make_adapter()
    npc = _make_npc(friend=True)
    npc.inventory = []
    adapter.player.combat_list_allies = [adapter.player]

    result = _run_heal(adapter, npc)

    assert result is False
