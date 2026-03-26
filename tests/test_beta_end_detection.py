"""
Tests for beta-end detection in ApiCombatAdapter._handle_victory().
Verifies that combat_end_summary["beta_end"] is set iff the player just
defeated the Lurker on the AfterDefeatingLurker tile.
"""
import pytest
from unittest.mock import MagicMock, patch


def _make_player(tile=None):
    """Return a minimal mock player sufficient for _handle_victory()."""
    player = MagicMock()
    player.in_combat = True
    player.maxfatigue = 100
    player.fatigue = 0
    player.combat_exp = {}
    player.combat_drops = []
    player.pending_attribute_points = 0
    player.exp_to_level = 100
    player.exp = 0
    player.strength_base = 10
    player.finesse_base = 10
    player.speed_base = 10
    player.endurance_base = 10
    player.charisma_base = 10
    player.intelligence_base = 10
    player.current_room = tile
    player.combat_end_summary = {}
    # gain_exp returns None in a non-level-up scenario
    player.gain_exp.return_value = None
    return player


def _make_tile(has_lurker_event=False, lurker_in_npcs=False):
    """Return a mock tile with the given event/NPC configuration.
    Class names must match the strings checked in _handle_victory().
    """

    class AfterDefeatingLurker:
        pass

    class Lurker:
        pass

    events_here = [AfterDefeatingLurker()] if has_lurker_event else []
    npcs_here = [Lurker()] if lurker_in_npcs else []

    tile = MagicMock()
    tile.events_here = events_here
    tile.npcs_here = npcs_here
    return tile


@pytest.fixture
def adapter_for(request):
    """Factory: returns an ApiCombatAdapter for a given player, with heavy deps patched."""
    from src.api.combat_adapter import ApiCombatAdapter

    def factory(player):
        with patch("src.api.combat_adapter.CombatStrategist"):
            with patch("src.api.combat_adapter.CombatOutputCapture") as mock_capture_cls:
                mock_capture = mock_capture_cls.return_value
                mock_capture.current_round = 1
                adapter = ApiCombatAdapter.__new__(ApiCombatAdapter)
                adapter.player = player
                adapter.session_id = None
                adapter.output_capture = mock_capture
                adapter.strategist = MagicMock()
                return adapter

    return factory


class TestBetaEndDetection:
    def test_sets_beta_end_when_lurker_event_present_and_lurker_gone(self, adapter_for):
        """Defeating the Lurker on the correct tile → beta_end=True."""
        tile = _make_tile(has_lurker_event=True, lurker_in_npcs=False)
        player = _make_player(tile=tile)
        adapter = adapter_for(player)

        adapter._handle_victory()

        assert player.combat_end_summary.get("beta_end") is True

    def test_no_beta_end_when_lurker_still_present(self, adapter_for):
        """Lurker event on tile but Lurker still alive → no beta_end flag."""
        tile = _make_tile(has_lurker_event=True, lurker_in_npcs=True)
        player = _make_player(tile=tile)
        adapter = adapter_for(player)

        adapter._handle_victory()

        assert "beta_end" not in player.combat_end_summary

    def test_no_beta_end_when_no_lurker_event(self, adapter_for):
        """Victory on a tile without AfterDefeatingLurker → no beta_end flag."""
        tile = _make_tile(has_lurker_event=False, lurker_in_npcs=False)
        player = _make_player(tile=tile)
        adapter = adapter_for(player)

        adapter._handle_victory()

        assert "beta_end" not in player.combat_end_summary

    def test_no_beta_end_when_no_current_room(self, adapter_for):
        """Player has no current_room (edge case) → no beta_end flag."""
        player = _make_player(tile=None)
        adapter = adapter_for(player)

        adapter._handle_victory()

        assert "beta_end" not in player.combat_end_summary
