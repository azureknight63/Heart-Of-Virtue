"""Test that Advance move updates facing direction during coordinate-based combat."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules resolve
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.npc import NPC  # type: ignore
from src.player import Player  # type: ignore
from src import positions  # type: ignore
from src.moves import Advance  # type: ignore


class TestAdvanceFacing:
    """Tests for Advance move facing direction updates."""
    
    def test_advance_updates_facing_toward_target(self):
        """Verify Advance move rotates player toward target."""
        player = Player()
        player.name = "Jean"
        enemy = NPC(name="Slime", description="A test slime", damage=10, aggro=50, exp_award=25)
        
        # Setup: Player at (10, 10) facing East (wrong), Enemy at (10, 20) directly North
        player.combat_position = positions.CombatPosition(x=10, y=10, facing=positions.Direction.E)
        enemy.combat_position = positions.CombatPosition(x=10, y=20, facing=positions.Direction.S)
        
        # Setup move
        advance = Advance(player)
        advance.target = enemy
        player.combat_proximity = {enemy: 10}
        enemy.combat_proximity = {player: 10}
        
        initial_facing = player.combat_position.facing
        assert initial_facing == positions.Direction.E, "Player should start facing East"
        
        # Execute Advance
        advance.execute(player)
        
        # Verify: Player should face North after advancing toward Northern target
        assert player.combat_position.facing == positions.Direction.N, \
            f"After advancing North toward target, player should face N, got {player.combat_position.facing.name}"
    
    def test_advance_updates_facing_diagonal(self):
        """Verify Advance move handles diagonal movement facing."""
        player = Player()
        player.name = "Jean"
        enemy = NPC(name="Goblin", description="A test goblin", damage=12, aggro=60, exp_award=30)
        
        # Setup: Player at (10, 10) facing South (wrong), Enemy at (20, 25) - Northeast
        player.combat_position = positions.CombatPosition(x=10, y=10, facing=positions.Direction.S)
        enemy.combat_position = positions.CombatPosition(x=20, y=25, facing=positions.Direction.NW)
        
        # Setup move
        advance = Advance(player)
        advance.target = enemy
        player.combat_proximity = {enemy: 15}
        enemy.combat_proximity = {player: 15}
        
        # Execute Advance
        advance.execute(player)
        
        # Verify: Player should face toward Northeast after advancing
        assert player.combat_position.facing == positions.Direction.NE, \
            f"After advancing NE toward target, player should face NE, got {player.combat_position.facing.name}"
    
    def test_advance_updates_position_and_facing(self):
        """Verify Advance updates BOTH position AND facing."""
        player = Player()
        player.name = "Jean"
        enemy = NPC(name="Bat", description="A test bat", damage=8, aggro=40, exp_award=20)
        
        # Setup: Player at (15, 15) facing West, Enemy at (25, 15) directly East
        player.combat_position = positions.CombatPosition(x=15, y=15, facing=positions.Direction.W)
        enemy.combat_position = positions.CombatPosition(x=25, y=15, facing=positions.Direction.W)
        
        # Setup move
        advance = Advance(player)
        advance.target = enemy
        player.combat_proximity = {enemy: 10}
        enemy.combat_proximity = {player: 10}
        
        initial_pos = (player.combat_position.x, player.combat_position.y)
        initial_dist = positions.distance_from_coords(player.combat_position, enemy.combat_position)
        
        # Execute Advance
        advance.execute(player)
        
        # Verify position changed
        new_pos = (player.combat_position.x, player.combat_position.y)
        new_dist = positions.distance_from_coords(player.combat_position, enemy.combat_position)
        assert new_pos != initial_pos, f"Position should change: {initial_pos} -> {new_pos}"
        assert new_dist < initial_dist, f"Distance should decrease: {initial_dist} -> {new_dist}"
        
        # Verify facing changed to East
        assert player.combat_position.facing == positions.Direction.E, \
            f"After advancing East toward target, player should face E, got {player.combat_position.facing.name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
