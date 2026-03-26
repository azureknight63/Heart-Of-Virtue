"""
Unit tests for QuickSwap move (HV-1 Tier 2 ability).

Tests cover:
- Ally detection (nearby allies within range)
- Position swaps (coordinate and distance-based)
- Distance recalculation post-swap
- Edge cases (no allies, out of range, dead allies, etc.)
"""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules resolve
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.moves import QuickSwap  # type: ignore
from src.positions import CombatPosition, Direction  # type: ignore


@pytest.fixture
def mock_player():
    """Create a mock player with combat properties."""
    player = Mock()
    player.name = "Jean"
    player.is_alive.return_value = True
    player.fatigue = 100
    player.combat_list_allies = []
    player.combat_proximity = {}
    player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
    return player


@pytest.fixture
def mock_ally():
    """Create a mock ally."""
    ally = Mock()
    ally.name = "Ally1"
    ally.is_alive.return_value = True
    ally.combat_position = CombatPosition(x=27, y=25, facing=Direction.E)
    ally.combat_proximity = {}
    return ally


@pytest.fixture
def mock_distant_ally():
    """Create a mock ally that's too far away."""
    ally = Mock()
    ally.name = "DistantAlly"
    ally.is_alive.return_value = True
    ally.combat_position = CombatPosition(x=10, y=10, facing=Direction.S)
    ally.combat_proximity = {}
    return ally


@pytest.fixture
def mock_dead_ally():
    """Create a mock dead ally."""
    ally = Mock()
    ally.name = "DeadAlly"
    ally.is_alive.return_value = False
    ally.combat_position = CombatPosition(x=26, y=26, facing=Direction.NE)
    ally.combat_proximity = {}
    return ally


@pytest.fixture
def quickswap_move(mock_player):
    """Create a QuickSwap move instance."""
    return QuickSwap(mock_player)


class TestQuickSwapViability:
    """Tests for QuickSwap viable() method."""

    def test_viable_with_nearby_ally(self, quickswap_move, mock_player, mock_ally):
        """QuickSwap should be viable when nearby ally exists."""
        mock_player.combat_list_allies = [mock_ally]
        assert quickswap_move.viable() is True

    def test_not_viable_no_allies(self, quickswap_move, mock_player):
        """QuickSwap should not be viable when no allies exist."""
        mock_player.combat_list_allies = []
        assert quickswap_move.viable() is False

    def test_not_viable_all_allies_too_distant(self, quickswap_move, mock_player, mock_distant_ally):
        """QuickSwap should not be viable when all allies are out of range."""
        mock_player.combat_list_allies = [mock_distant_ally]
        assert quickswap_move.viable() is False

    def test_not_viable_all_allies_dead(self, quickswap_move, mock_player, mock_dead_ally):
        """QuickSwap should not be viable when all allies are dead."""
        mock_player.combat_list_allies = [mock_dead_ally]
        assert quickswap_move.viable() is False

    def test_viable_with_mixed_allies(self, quickswap_move, mock_player, mock_ally, mock_distant_ally, mock_dead_ally):
        """QuickSwap should be viable if at least one nearby living ally exists."""
        mock_player.combat_list_allies = [mock_distant_ally, mock_dead_ally, mock_ally]
        assert quickswap_move.viable() is True


class TestNearbyAllyDetection:
    """Tests for _get_nearby_allies() method."""

    def test_detect_single_nearby_ally(self, quickswap_move, mock_player, mock_ally):
        """Should detect a single nearby ally within range."""
        mock_player.combat_list_allies = [mock_ally]
        nearby = quickswap_move._get_nearby_allies()
        assert len(nearby) == 1
        assert nearby[0] is mock_ally

    def test_exclude_out_of_range_ally(self, quickswap_move, mock_player, mock_distant_ally):
        """Should exclude allies beyond maximum range (4 squares)."""
        mock_player.combat_list_allies = [mock_distant_ally]
        nearby = quickswap_move._get_nearby_allies()
        assert len(nearby) == 0

    def test_exclude_dead_allies(self, quickswap_move, mock_player, mock_dead_ally):
        """Should exclude dead allies from swap options."""
        mock_player.combat_list_allies = [mock_dead_ally]
        nearby = quickswap_move._get_nearby_allies()
        assert len(nearby) == 0

    def test_exclude_self(self, quickswap_move, mock_player, mock_ally):
        """Should never include self in nearby allies."""
        mock_player.combat_list_allies = [mock_player, mock_ally]
        nearby = quickswap_move._get_nearby_allies()
        assert mock_player not in nearby
        assert len(nearby) == 1

    def test_multiple_nearby_allies(self, quickswap_move, mock_player):
        """Should detect multiple nearby allies."""
        ally1 = Mock()
        ally1.name = "Ally1"
        ally1.is_alive.return_value = True
        ally1.combat_position = CombatPosition(x=26, y=25, facing=Direction.E)

        ally2 = Mock()
        ally2.name = "Ally2"
        ally2.is_alive.return_value = True
        ally2.combat_position = CombatPosition(x=25, y=27, facing=Direction.S)

        mock_player.combat_list_allies = [ally1, ally2]
        nearby = quickswap_move._get_nearby_allies()
        assert len(nearby) == 2
        assert ally1 in nearby
        assert ally2 in nearby


class TestCoordinateBasedSwap:
    """Tests for coordinate-based position swapping."""

    def test_swap_positions_coordinate_based(self, quickswap_move, mock_player, mock_ally):
        """Should correctly swap x,y coordinates between player and ally."""
        player_orig_x, player_orig_y = 25, 25
        ally_orig_x, ally_orig_y = 27, 25

        mock_player.combat_position = CombatPosition(x=player_orig_x, y=player_orig_y, facing=Direction.N)
        mock_ally.combat_position = CombatPosition(x=ally_orig_x, y=ally_orig_y, facing=Direction.E)
        mock_player.combat_list_allies = [mock_ally]
        mock_player.combat_proximity = {}
        mock_ally.combat_proximity = {}

        # Execute swap
        quickswap_move._execute_coordinate_based(mock_player, mock_ally)

        # Verify positions were swapped: player now at ally's original position
        assert mock_player.combat_position.x == ally_orig_x
        assert mock_player.combat_position.y == ally_orig_y
        # Verify ally now at player's original position
        assert mock_ally.combat_position.x == player_orig_x
        assert mock_ally.combat_position.y == player_orig_y

    def test_swap_facing_direction(self, quickswap_move, mock_player, mock_ally):
        """Should also swap facing directions."""
        player_facing = Direction.N
        ally_facing = Direction.E

        mock_player.combat_position = CombatPosition(x=25, y=25, facing=player_facing)
        mock_ally.combat_position = CombatPosition(x=27, y=25, facing=ally_facing)
        mock_player.combat_list_allies = [mock_ally]
        mock_player.combat_proximity = {}
        mock_ally.combat_proximity = {}

        quickswap_move._execute_coordinate_based(mock_player, mock_ally)

        # Verify facings were swapped
        assert mock_player.combat_position.facing == ally_facing
        assert mock_ally.combat_position.facing == player_facing


class TestDistanceRecalculation:
    """Tests for distance recalculation after swap."""

    def test_recalculate_distances_with_enemy(self, quickswap_move, mock_player, mock_ally):
        """Should recalculate distances to enemies after swap."""
        enemy = Mock()
        enemy.name = "Enemy1"
        enemy.combat_position = CombatPosition(x=40, y=25, facing=Direction.W)
        enemy.combat_proximity = {}

        mock_player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
        mock_ally.combat_position = CombatPosition(x=27, y=25, facing=Direction.E)
        mock_player.combat_list_allies = [mock_ally]
        mock_player.combat_proximity = {enemy: 15}  # Distance to enemy before swap
        mock_ally.combat_proximity = {enemy: 13}  # Distance to enemy before swap
        enemy.combat_proximity = {mock_player: 15, mock_ally: 13}

        quickswap_move._execute_coordinate_based(mock_player, mock_ally)

        # After swap, player should be closer to enemy than before
        # Player moved from 25 to 27 (closer to enemy at 40)
        assert mock_player.combat_proximity[enemy] < 15


class TestLegacyDistanceBasedSwap:
    """Tests for legacy distance-based swap (backward compatibility)."""

    def test_swap_proximity_dicts(self, quickswap_move, mock_player, mock_ally):
        """Should swap combat_proximity dicts in legacy system."""
        enemy = Mock()
        enemy.name = "Enemy1"
        enemy.combat_proximity = {}

        player_prox = {enemy: 15}
        ally_prox = {enemy: 13}

        mock_player.combat_proximity = player_prox
        mock_ally.combat_proximity = ally_prox
        mock_player.combat_list_allies = [mock_ally]

        quickswap_move._execute_legacy(mock_player, mock_ally)

        # Verify proximity dicts were swapped
        assert mock_player.combat_proximity == ally_prox
        assert mock_ally.combat_proximity == player_prox


class TestExecuteMethod:
    """Tests for execute() method."""

    def test_execute_selects_nearby_ally(self, quickswap_move, mock_player, mock_ally):
        """Execute should automatically select a nearby ally."""
        mock_player.combat_list_allies = [mock_ally]
        mock_player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
        mock_ally.combat_position = CombatPosition(x=27, y=25, facing=Direction.E)
        mock_player.combat_proximity = {}
        mock_ally.combat_proximity = {}

        # This should not raise any exception
        quickswap_move.execute(mock_player)

        # Positions should have been swapped
        assert mock_player.combat_position.x == 27
        assert mock_ally.combat_position.x == 25

    def test_execute_fails_gracefully_no_allies(self, quickswap_move, mock_player):
        """Execute should fail gracefully when no allies available."""
        mock_player.combat_list_allies = []

        # This should not raise exception, just print error message
        quickswap_move.execute(mock_player)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_range_boundary_exactly_at_range(self, quickswap_move, mock_player):
        """Should include ally exactly at maximum range (4 squares)."""
        ally = Mock()
        ally.name = "BoundaryAlly"
        ally.is_alive.return_value = True
        # Euclidean distance from (25, 25) to (29, 25) = 4 squares
        ally.combat_position = CombatPosition(x=29, y=25, facing=Direction.E)

        mock_player.combat_list_allies = [ally]
        nearby = quickswap_move._get_nearby_allies()
        assert len(nearby) == 1

    def test_range_boundary_just_beyond_range(self, quickswap_move, mock_player):
        """Should exclude ally just beyond maximum range."""
        ally = Mock()
        ally.name = "TooDistantAlly"
        ally.is_alive.return_value = True
        # Euclidean distance from (25, 25) to (30, 25) = 5 squares
        ally.combat_position = CombatPosition(x=30, y=25, facing=Direction.E)

        mock_player.combat_list_allies = [ally]
        nearby = quickswap_move._get_nearby_allies()
        assert len(nearby) == 0

    def test_minimum_range_requirement(self, quickswap_move, mock_player):
        """Should exclude ally at same position (0 distance, but min_range is 1)."""
        ally = Mock()
        ally.name = "SamePositionAlly"
        ally.is_alive.return_value = True
        ally.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)

        mock_player.combat_list_allies = [ally]
        nearby = quickswap_move._get_nearby_allies()
        # Should exclude because distance is 0, min_range is 1
        assert len(nearby) == 0


class TestMoveProperties:
    """Tests for QuickSwap move properties."""

    def test_move_name(self, quickswap_move):
        """Move should have correct name."""
        assert quickswap_move.name == "Quick Swap"

    def test_move_fatigue_cost(self, quickswap_move):
        """Move should have correct fatigue cost (10)."""
        assert quickswap_move.fatigue_cost == 10

    def test_move_range(self, quickswap_move):
        """Move should have range 1-4 squares."""
        assert quickswap_move.mvrange == (1, 4)

    def test_move_beats(self, quickswap_move):
        """Move should have correct beat costs."""
        # [prep, execute, recoil, cooldown] = [0, 2, 0, 2]
        assert quickswap_move.stage_beat == [0, 2, 0, 2]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
