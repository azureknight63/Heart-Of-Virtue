"""
Test that all combat attack moves update the user's facing direction toward the target.
"""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules resolve
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.player import Player  # type: ignore
from src.npc import NPC  # type: ignore
from src.moves import Attack, Slash, PowerStrike, Jab, PommelStrike, ShootBow, NpcAttack, GorranClub, VenomClaw, SpiderBite, BatBite  # type: ignore
from src.positions import Direction, CombatPosition  # type: ignore
import src.functions as functions  # type: ignore


class TestAttackMovesFacing:
    """Verify that attack moves update user's facing toward target."""

    @pytest.fixture
    def player(self):
        """Create a test player."""
        p = Player()
        p.name = "Test Player"
        p.friend = False  # Not an NPC ally
        # Equip a basic sword for attacks
        from src.items import Shortsword  # type: ignore
        p.eq_weapon = Shortsword()
        p.combat_proximity = {}
        return p

    @pytest.fixture
    def enemy(self):
        """Create a test enemy."""
        enemy = NPC(name="Test Enemy", description="A test enemy", damage=10, aggro=50, exp_award=25)
        enemy.friend = False
        enemy.combat_proximity = {}
        return enemy

    def test_attack_faces_target_east(self, player, enemy):
        """Test that Attack move faces target to the east."""
        # Setup combat positions
        player.combat_position = CombatPosition(x=0, y=0, facing=Direction.N)
        enemy.combat_position = CombatPosition(x=5, y=0, facing=Direction.N)
        
        player.combat_proximity[enemy] = 5
        enemy.combat_proximity[player] = 5
        
        attack = Attack(player)
        attack.target = enemy
        
        # Execute attack
        attack.execute(player)
        
        # Player should face east (target is to the east)
        assert player.combat_position.facing == Direction.E, \
            f"Expected E, got {player.combat_position.facing.name}"

    def test_slash_faces_target_northeast(self, player, enemy):
        """Test that Slash move faces target to the northeast."""
        # Setup combat positions
        player.combat_position = CombatPosition(x=0, y=25, facing=Direction.S)
        enemy.combat_position = CombatPosition(x=3, y=22, facing=Direction.S)
        
        player.combat_proximity[enemy] = 4  # roughly diagonal
        enemy.combat_proximity[player] = 4
        
        slash = Slash(player)
        slash.target = enemy
        
        # Execute attack
        slash.execute(player)
        
        # Player should face northeast (target is NE)
        assert player.combat_position.facing == Direction.NE, \
            f"Expected NE, got {player.combat_position.facing.name}"

    def test_powerstrike_faces_target_south(self, player, enemy):
        """Test that PowerStrike move faces target to the south."""
        # Setup combat positions
        player.combat_position = CombatPosition(x=0, y=0, facing=Direction.N)
        enemy.combat_position = CombatPosition(x=0, y=5, facing=Direction.N)
        
        player.combat_proximity[enemy] = 5
        enemy.combat_proximity[player] = 5
        
        ps = PowerStrike(player)
        ps.target = enemy
        
        # Execute attack
        ps.execute(player)
        
        # Player should face south (target is to the south)
        assert player.combat_position.facing == Direction.S, \
            f"Expected S, got {player.combat_position.facing.name}"

    def test_jab_faces_target_west(self, player, enemy):
        """Test that Jab move faces target to the west."""
        # Setup combat positions
        player.combat_position = CombatPosition(x=5, y=0, facing=Direction.E)
        enemy.combat_position = CombatPosition(x=0, y=0, facing=Direction.E)
        
        player.combat_proximity[enemy] = 5
        enemy.combat_proximity[player] = 5
        
        jab = Jab(player)
        jab.target = enemy
        
        # Execute attack
        jab.execute(player)
        
        # Player should face west (target is to the west)
        assert player.combat_position.facing == Direction.W, \
            f"Expected W, got {player.combat_position.facing.name}"

    def test_npc_attack_faces_target(self, enemy, player):
        """Test that NPC basic attack faces target."""
        # Setup combat positions
        enemy.combat_position = CombatPosition(x=0, y=0, facing=Direction.N)
        player.combat_position = CombatPosition(x=5, y=5, facing=Direction.S)
        
        enemy.combat_proximity[player] = 7
        player.combat_proximity[enemy] = 7
        
        npc_attack = NpcAttack(enemy)
        npc_attack.target = player
        
        # Execute attack
        npc_attack.execute(enemy)
        
        # NPC should face southeast (target is SE)
        assert enemy.combat_position.facing == Direction.SE, \
            f"Expected SE, got {enemy.combat_position.facing.name}"

    def test_gorran_club_faces_target(self, enemy, player):
        """Test that GorranClub special attack faces target."""
        # Setup combat positions
        enemy.combat_position = CombatPosition(x=10, y=10, facing=Direction.W)
        player.combat_position = CombatPosition(x=15, y=10, facing=Direction.W)
        
        enemy.combat_proximity[player] = 5
        player.combat_proximity[enemy] = 5
        
        gorran = GorranClub(enemy)
        gorran.target = player
        
        # Execute attack
        gorran.execute(enemy)
        
        # Enemy should face east (target is to the east)
        assert enemy.combat_position.facing == Direction.E, \
            f"Expected E, got {enemy.combat_position.facing.name}"

    def test_venom_claw_faces_target(self, enemy, player):
        """Test that VenomClaw special attack faces target."""
        # Setup combat positions
        enemy.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
        player.combat_position = CombatPosition(x=23, y=27, facing=Direction.N)
        
        enemy.combat_proximity[player] = 3  # NW direction
        player.combat_proximity[enemy] = 3
        
        vc = VenomClaw(enemy)
        vc.target = player
        
        # Execute attack
        vc.execute(enemy)
        
        # Enemy should face northwest (target is NW)
        assert enemy.combat_position.facing == Direction.NW, \
            f"Expected NW, got {enemy.combat_position.facing.name}"

    def test_spider_bite_faces_target(self, enemy, player):
        """Test that SpiderBite special attack faces target."""
        # Setup combat positions
        enemy.combat_position = CombatPosition(x=25, y=25, facing=Direction.S)
        player.combat_position = CombatPosition(x=25, y=20, facing=Direction.N)
        
        enemy.combat_proximity[player] = 5
        player.combat_proximity[enemy] = 5
        
        sb = SpiderBite(enemy)
        sb.target = player
        
        # Execute attack
        sb.execute(enemy)
        
        # Enemy should face north (target is to the north)
        assert enemy.combat_position.facing == Direction.N, \
            f"Expected N, got {enemy.combat_position.facing.name}"

    def test_bat_bite_faces_target(self, enemy, player):
        """Test that BatBite special attack faces target."""
        # Setup combat positions
        enemy.combat_position = CombatPosition(x=5, y=5, facing=Direction.S)
        player.combat_position = CombatPosition(x=2, y=8, facing=Direction.S)
        
        enemy.combat_proximity[player] = 4  # SW direction
        player.combat_proximity[enemy] = 4
        
        bb = BatBite(enemy)
        bb.target = player
        
        # Execute attack
        bb.execute(enemy)
        
        # Enemy should face southwest (target is SW)
        assert enemy.combat_position.facing == Direction.SW, \
            f"Expected SW, got {enemy.combat_position.facing.name}"

    def test_pommel_strike_faces_target(self, player, enemy):
        """Test that PommelStrike (using standard_execute_attack) faces target."""
        # Setup combat positions
        player.combat_position = CombatPosition(x=25, y=25, facing=Direction.N)
        enemy.combat_position = CombatPosition(x=21, y=21, facing=Direction.N)
        
        player.combat_proximity[enemy] = 5  # NW direction
        enemy.combat_proximity[player] = 5
        
        ps = PommelStrike(player)
        ps.target = enemy
        
        # Execute attack
        ps.execute(player)
        
        # Player should face northwest (target is NW)
        assert player.combat_position.facing == Direction.NW, \
            f"Expected NW, got {player.combat_position.facing.name}"

    def test_shoot_bow_faces_target(self, player, enemy):
        """Test that ShootBow (ranged attack) faces target."""
        # Setup combat positions
        player.combat_position = CombatPosition(x=0, y=0, facing=Direction.S)
        enemy.combat_position = CombatPosition(x=3, y=5, facing=Direction.S)
        
        player.combat_proximity[enemy] = 6  # SE direction at range
        enemy.combat_proximity[player] = 6
        
        # Need to add arrow to inventory
        from src.items import WoodenArrow  # type: ignore
        arrow = WoodenArrow()
        player.inventory.append(arrow)
        
        sb = ShootBow(player)
        sb.target = enemy
        sb.arrow = arrow
        
        # Execute attack
        sb.execute(player)
        
        # Player should face southeast (target is SE)
        assert player.combat_position.facing == Direction.SE, \
            f"Expected SE, got {player.combat_position.facing.name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
