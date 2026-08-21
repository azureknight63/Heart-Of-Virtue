"""
Regression tests for 5 bugs fixed during the beta QA run (2026-03-28).

BUG-001: NPCSpawnerEvent.evaluate_for_map_entry not called via API (spawn_tile fallback)
BUG-002: New wave enemies missing from combat_proximity after reinforcement spawn
BUG-003: awaiting_input stale True after combat victory
BUG-004: awaiting_input stale True after player defeat
BUG-005: current_stage/pending_move deadlock when combat event fires mid-beat
BUG-006: game_service.move_player never called universe.game_tick_events()
"""

from unittest.mock import MagicMock, patch

import pytest
from src.player import Player
from src.api.combat_adapter import ApiCombatAdapter


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def player():
    """Minimal Player with the combat-adapter state bag pre-initialised."""
    p = Player()
    p.known_moves = []
    p.combat_log = []
    p.last_move_summary = ""
    p.combat_beat = 1
    p.combat_list = []
    p.combat_list_allies = [p]
    p.combat_proximity = {}
    return p


@pytest.fixture
def adapter(player):
    with patch("src.api.combat_adapter.CombatStrategist"):
        return ApiCombatAdapter(player)


# ---------------------------------------------------------------------------
# BUG-003 — awaiting_input stale after victory
# ---------------------------------------------------------------------------

class TestAwaitingInputAfterVictory:
    def test_handle_victory_clears_awaiting_input(self, adapter, player):
        """_handle_victory() must set awaiting_input=False (regression: was missing)."""
        adapter.awaiting_input = True
        # _handle_victory needs minimal combat_exp and combat_drops on player
        player.combat_exp = {}
        player.combat_drops = []
        adapter._handle_victory()
        assert adapter.awaiting_input is False

    def test_handle_victory_clears_in_combat(self, adapter, player):
        """_handle_victory() must also clear player.in_combat."""
        player.in_combat = True
        player.combat_exp = {}
        player.combat_drops = []
        adapter._handle_victory()
        assert player.in_combat is False


# ---------------------------------------------------------------------------
# BUG-004 — awaiting_input stale after defeat
# ---------------------------------------------------------------------------

class TestAwaitingInputAfterDefeat:
    def test_defeat_path_sets_awaiting_input_false(
        self, make_player, make_npc, make_adapter
    ):
        """Executing a beat while Jean is down must clear awaiting_input.

        Previously this test hand-assigned ``adapter.awaiting_input = False``
        and asserted the assignment stuck, which proved only that a property
        setter works. Now it drives the real defeat branch inside
        ``_execute_move_inner``: deleting that ``self.awaiting_input = False``
        line fails this test, because the "battle continues" branch below it
        would otherwise set the flag back to True.
        """
        from src.npc import Slime
        import src.moves as moves

        jean = make_player(weapon="Sword")
        live_adapter = make_adapter(jean, enemies=[make_npc(cls=Slime, hp=40)])
        live_adapter.awaiting_input = True

        jean.hp = 0
        assert jean.is_alive() is False

        live_adapter._execute_move(moves.Wait(jean))

        assert live_adapter.awaiting_input is False
        assert jean.in_combat is False
        # The flag lives in the player-side state bag, so a status poll on a
        # fresh adapter instance still reports "no input expected".
        assert jean.combat_adapter_state["awaiting_input"] is False

    def test_awaiting_input_property_persists_in_state_bag(self, adapter, player):
        """Setting awaiting_input=False is reflected in player.combat_adapter_state."""
        adapter.awaiting_input = True
        assert player.combat_adapter_state["awaiting_input"] is True
        adapter.awaiting_input = False
        assert player.combat_adapter_state["awaiting_input"] is False


# ---------------------------------------------------------------------------
# BUG-001 — NPCSpawnerEvent.evaluate_for_map_entry tile fallback
# ---------------------------------------------------------------------------

class TestNPCSpawnerEventTileFallback:
    """NPCSpawnerEvent must use self.tile when spawn_tile is None."""

    def _make_event(self, spawn_tile=None, tile=None):
        from src.story.effects import NPCSpawnerEvent
        mock_player = MagicMock()
        evt = NPCSpawnerEvent.__new__(NPCSpawnerEvent)
        evt.has_run = False
        evt.repeat = False
        evt.spawn_tile = spawn_tile
        evt.tile = tile
        evt.npc_cls = None
        evt.npc_class_name = None
        evt.count = 1
        evt.spawned_npcs = []
        evt._conditions_passed = False
        return evt, mock_player

    def test_spawn_tile_none_tile_same_map_fires(self):
        """spawn_tile=None with tile on player's map triggers pass_conditions_to_process."""
        evt, player = self._make_event()
        mock_map = MagicMock()
        mock_tile = MagicMock()
        mock_tile.map = mock_map
        player.map = mock_map  # same map object
        evt.tile = mock_tile
        evt.spawn_tile = None

        evt.pass_conditions_to_process = MagicMock()
        evt.evaluate_for_map_entry(player)
        evt.pass_conditions_to_process.assert_called_once()

    def test_spawn_tile_none_tile_different_map_does_not_fire(self):
        """spawn_tile=None with tile on a different map does not fire."""
        evt, player = self._make_event()
        mock_tile = MagicMock()
        mock_tile.map = MagicMock()  # different object
        player.map = MagicMock()
        evt.tile = mock_tile
        evt.spawn_tile = None

        evt.pass_conditions_to_process = MagicMock()
        evt.evaluate_for_map_entry(player)
        evt.pass_conditions_to_process.assert_not_called()

    def test_spawn_tile_none_tile_none_does_not_raise(self):
        """spawn_tile=None and tile=None must not raise — evaluate silently returns."""
        evt, player = self._make_event()
        evt.spawn_tile = None
        evt.tile = None
        evt.pass_conditions_to_process = MagicMock()
        # Should not raise
        evt.evaluate_for_map_entry(player)
        evt.pass_conditions_to_process.assert_not_called()

    def test_has_run_true_no_repeat_skips_evaluation(self):
        """Event that already ran (has_run=True, repeat=False) must not re-fire."""
        evt, player = self._make_event()
        mock_map = MagicMock()
        mock_tile = MagicMock()
        mock_tile.map = mock_map
        player.map = mock_map
        evt.tile = mock_tile
        evt.has_run = True
        evt.repeat = False

        evt.pass_conditions_to_process = MagicMock()
        evt.evaluate_for_map_entry(player)
        evt.pass_conditions_to_process.assert_not_called()


# ---------------------------------------------------------------------------
# BUG-006 — game_service.move_player calls universe.game_tick_events()
# ---------------------------------------------------------------------------

class TestGameServiceCallsGameTickEvents:
    """move_player must call player.universe.game_tick_events() so NPCSpawnerEvents fire."""

    @staticmethod
    def _spawner_on(tile):
        """Attach a minimal map-entry spawner to ``tile`` and return its call log.

        ``Universe._evaluate_map_entry_spawners`` only looks for the
        ``evaluate_for_map_entry`` attribute and the ``has_run``/``repeat``
        flags, so this is a faithful stand-in for ``NPCSpawnerEvent`` without
        dragging in a real NPC roster.
        """
        fired = []

        class _Spawner:
            has_run = False
            repeat = False

            def evaluate_for_map_entry(self, player):
                fired.append((player.location_x, player.location_y))

        tile.events_here = [_Spawner()]
        return fired

    def test_move_player_ticks_the_universe_clock(self, make_world, grid_3x3, game_service):
        """A successful move advances universe.game_tick by exactly one."""
        player, _ = make_world(grid_3x3)
        assert player.universe.game_tick == 0

        assert game_service.move_player(player, "east")["success"] is True

        assert player.universe.game_tick == 1

    def test_every_move_ticks_not_just_the_first(self, make_world, grid_3x3, game_service):
        """The tick is per-move, not once per session (BUG-006 regression)."""
        player, _ = make_world(grid_3x3)

        for direction in ("east", "north", "west", "south"):
            assert game_service.move_player(player, direction)["success"] is True

        assert player.universe.game_tick == 4
        assert (player.location_x, player.location_y) == (0, 0)

    def test_move_player_fires_map_entry_spawners(self, make_world, grid_3x3, game_service):
        """The tick actually reaches evaluate_for_map_entry — the point of BUG-006.

        The spawner sits on a *different* tile than the one Jean walks onto, so
        this proves the whole-map sweep runs, not just the destination tile's
        own entry events.
        """
        player, game_map = make_world(grid_3x3)
        fired = self._spawner_on(game_map[(-1, -1)])

        game_service.move_player(player, "east")

        assert fired == [(1, 0)], "spawner never evaluated after the move"

    def test_blocked_move_does_not_tick(self, make_world, game_service):
        """A rejected move is not a game action: no tick, no spawner evaluation."""
        player, game_map = make_world([(0, 0), (1, 0)])
        fired = self._spawner_on(game_map[(1, 0)])

        result = game_service.move_player(player, "north")

        assert "error" in result
        assert player.universe.game_tick == 0
        assert fired == []

    def test_tick_failure_does_not_abort_the_move(self, make_world, grid_3x3, game_service):
        """game_tick_events() raising is logged and swallowed — Jean still moves.

        Movement must never be held hostage by a broken story event; the engine
        wraps the tick in try/except for exactly this reason.
        """
        player, _ = make_world(grid_3x3)
        player.universe.game_tick_events = MagicMock(side_effect=RuntimeError("boom"))

        result = game_service.move_player(player, "east")

        assert result["success"] is True
        assert (player.location_x, player.location_y) == (1, 0)
        player.universe.game_tick_events.assert_called_once_with()
