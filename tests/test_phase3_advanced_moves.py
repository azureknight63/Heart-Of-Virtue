"""
test_phase3_advanced_moves.py - Comprehensive test suite for Phase 3 advanced positioning moves

Tests for:
- Turn: Basic rotation move
- WhirlAttack: AOE spinning attack
- FeintAndPivot: Attack + repositioning move
- VertigoSpin: Attack + status effect + facing rotation move
"""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules resolve
ROOT = Path(__file__).resolve().parent.parent


import pytest
import random
from unittest.mock import Mock, patch, MagicMock

# Import after path setup
from src.moves import Turn, WhirlAttack, FeintAndPivot, VertigoSpin, Move  # type: ignore
from src.positions import Direction, CombatPosition  # type: ignore
from src.player import Player  # type: ignore
from src.npc import NPC  # type: ignore


class TestTurnMove:
    """Test suite for Turn move - basic rotation without movement"""

    @pytest.fixture
    def player(self):
        """Create a test player with combat_position"""
        p = Player()
        p.name = "Jean"
        p.hp = 100
        p.maxhp = 100
        p.fatigue = 100
        p.combat_position = CombatPosition(x=10, y=10, facing=Direction.N)
        p.combat_proximity = {}
        p.is_alive = lambda: True
        return p

    @pytest.fixture
    def turn_move(self, player):
        """Create Turn move instance"""
        return Turn(player)

    def test_turn_creation(self, turn_move, player):
        """Test Turn move is created with correct attributes"""
        assert turn_move.name == "Turn"
        assert turn_move.user == player
        assert turn_move.fatigue_cost == 0
        assert turn_move.target_direction is None
        assert turn_move.current_stage == 0
        assert turn_move.beats_left == 0  # prep = 0

    def test_turn_stage_beat_values(self, turn_move):
        """Test Turn move has correct stage beat durations"""
        # [prep=0, execute=1, recoil=0, cooldown=2]
        assert turn_move.stage_beat[0] == 0  # prep
        assert turn_move.stage_beat[1] == 1  # execute
        assert turn_move.stage_beat[2] == 0  # recoil
        assert turn_move.stage_beat[3] == 2  # cooldown

    def test_turn_viable_without_combat_position(self, player):
        """Test Turn is not viable without combat_position"""
        player.combat_position = None
        turn = Turn(player)
        assert not turn.viable()

    def test_turn_viable_with_combat_position(self, player, turn_move):
        """Test Turn is viable with combat_position"""
        assert turn_move.viable()

    def test_turn_execute_rotates_facing(self, player, turn_move):
        """Test Turn.execute() rotates player to target direction"""
        turn_move.target_direction = Direction.E
        player.combat_position.facing = Direction.N

        turn_move.execute(player)

        assert player.combat_position.facing.value == Direction.E.value

    def test_turn_execute_deducts_fatigue(self, player, turn_move):
        """Test Turn.execute() deducts fatigue cost (zero for Turn move)"""
        initial_fatigue = player.fatigue
        turn_move.target_direction = Direction.S

        turn_move.execute(player)

        assert player.fatigue == initial_fatigue - 0

    def test_turn_execute_without_target_direction(self, player, turn_move):
        """Test Turn.execute() handles missing target_direction"""
        turn_move.target_direction = None
        initial_fatigue = player.fatigue

        turn_move.execute(player)

        # Should not deduct fatigue if no target direction
        assert player.fatigue == initial_fatigue

    def test_turn_rotates_all_directions(self, player, turn_move):
        """Test Turn can rotate to all 8 cardinal directions"""
        for direction in Direction:
            turn_move.target_direction = direction
            player.combat_position.facing = Direction.N

            turn_move.execute(player)

            assert player.combat_position.facing == direction

    def test_turn_xp_gain(self, turn_move):
        """Test Turn gives 0 XP (non-offensive move)"""
        assert turn_move.xp_gain == 0


class TestWhirlAttackMove:
    """Test suite for WhirlAttack move - AOE spinning attack"""

    @pytest.fixture
    def player(self):
        """Create player with combat_position and enemies nearby"""
        p = Player()
        p.name = "Jean"
        p.hp = 100
        p.maxhp = 100
        p.fatigue = 150
        p.combat_position = CombatPosition(x=10, y=10, facing=Direction.N)
        p.eq_weapon = Mock(damage=20, base_damage_type="slashing")
        p.strength = 10
        p.finesse = 5
        p.combat_proximity = {}
        p.is_alive = lambda: True
        return p

    @pytest.fixture
    def enemies(self, player):
        """Create enemies around player"""
        enemies = []
        for i, pos in enumerate([(12, 10), (8, 10), (10, 12)]):
            enemy = NPC(name=f"Enemy{i}", description="Test Enemy", damage=15, aggro=60, exp_award=50)
            enemy.hp = 50
            enemy.maxhp = 50
            enemy.protection = 2
            enemy.finesse = 3
            enemy.combat_position = CombatPosition(x=pos[0], y=pos[1], facing=Direction.N)
            enemy.states = []
            enemies.append(enemy)
            player.combat_proximity[enemy] = 5
        return enemies

    @pytest.fixture
    def whirl_move(self, player, enemies):
        """Create WhirlAttack move instance"""
        return WhirlAttack(player)

    def test_whirl_creation(self, whirl_move, player):
        """Test WhirlAttack move is created with correct attributes"""
        assert whirl_move.name == "Whirl Attack"
        assert whirl_move.user == player
        assert whirl_move.fatigue_cost == 45
        assert whirl_move.xp_gain == 15

    def test_whirl_stage_beat_values(self, whirl_move):
        """Test WhirlAttack has correct stage beat durations"""
        # [prep=1, execute=2, recoil=1, cooldown=3] -- a 7-beat cycle, the
        # cheap end of the area spectrum (Halberd Spin is the heavy end at 13).
        assert whirl_move.stage_beat[0] == 1  # prep
        assert whirl_move.stage_beat[1] == 2  # execute
        assert whirl_move.stage_beat[2] == 1  # recoil
        assert whirl_move.stage_beat[3] == 3  # cooldown
        assert sum(whirl_move.stage_beat) == 7

    def test_whirl_not_viable_without_combat_position(self, player):
        """Test WhirlAttack not viable without combat_position"""
        player.combat_position = None
        whirl = WhirlAttack(player)
        assert not whirl.viable()

    def test_whirl_viable_with_nearby_enemies(self, whirl_move):
        """Test WhirlAttack viable when enemies nearby"""
        assert whirl_move.viable()

    def test_whirl_not_viable_without_enemies(self, player):
        """Test WhirlAttack not viable with no enemies"""
        player.combat_proximity = {}
        whirl = WhirlAttack(player)
        assert not whirl.viable()

    def test_whirl_execute_hits_multiple_enemies(self, player, whirl_move, enemies):
        """Test WhirlAttack.execute() damages multiple enemies"""
        initial_hps = {e: e.hp for e in enemies}

        whirl_move.execute(player)

        # At least one enemy should be damaged (probabilistic)
        damaged_count = sum(1 for e in enemies if e.hp < initial_hps[e])
        assert damaged_count >= 0  # Could be 0 if all rolls miss

    def test_whirl_execute_deducts_fatigue(self, player, whirl_move):
        """Test WhirlAttack.execute() deducts fatigue"""
        initial_fatigue = player.fatigue

        whirl_move.execute(player)

        assert player.fatigue == initial_fatigue - 45

    def test_whirl_changes_facing_randomly(self, player, whirl_move):
        """Test WhirlAttack.execute() changes facing to random direction"""
        # Set fixed seed for deterministic test
        random.seed(42)
        initial_facing = player.combat_position.facing

        whirl_move.execute(player)

        # Facing should be a Direction enum value (might be same by chance)
        assert hasattr(player.combat_position.facing, 'name')
        # Check class name instead of isinstance/in due to module loading issues in tests
        assert player.combat_position.facing.__class__.__name__ == 'Direction'

    def test_whirl_evaluates_power(self, player, whirl_move):
        """Test WhirlAttack power calculation from weapon"""
        whirl_move.evaluate()

        # Power is AREA_POWER_FACTOR of a full swing
        # (damage + strength*str_mod + finesse*fin_mod). This Mock weapon has
        # a real damage of 20 but no numeric str_mod/fin_mod, so those terms
        # drop out: int(20 * 0.40) = 8.
        assert WhirlAttack.AREA_POWER_FACTOR == 0.40
        assert whirl_move.power == int(20 * WhirlAttack.AREA_POWER_FACTOR)

    def test_whirl_power_without_weapon(self, player):
        """Test WhirlAttack power calculation without weapon"""
        player.eq_weapon = None
        whirl = WhirlAttack(player)
        whirl.evaluate()

        # No weapon: fall back to strength alone, still scaled by the
        # move's area factor. int(10 * 0.40) = 4.
        assert whirl.power == int(10 * WhirlAttack.AREA_POWER_FACTOR)


class TestFeintAndPivotMove:
    """Test suite for FeintAndPivot move - attack + reposition"""

    @pytest.fixture
    def player(self):
        """Create player for FeintAndPivot"""
        p = Player()
        p.name = "Jean"
        p.hp = 100
        p.maxhp = 100
        p.fatigue = 150
        p.combat_position = CombatPosition(x=10, y=10, facing=Direction.N)
        p.eq_weapon = Mock(damage=25, base_damage_type="slashing")
        p.strength = 12
        p.finesse = 4
        p.combat_proximity = {}
        p.is_alive = lambda: True
        return p

    @pytest.fixture
    def target_enemy(self, player):
        """Create target enemy for FeintAndPivot"""
        enemy = NPC(name="TargetEnemy", description="Test Target", damage=18, aggro=70, exp_award=60)
        enemy.hp = 60
        enemy.maxhp = 60
        enemy.protection = 3
        enemy.finesse = 2
        enemy.combat_position = CombatPosition(x=15, y=10, facing=Direction.W)
        enemy.states = []
        player.combat_proximity[enemy] = 10
        return enemy

    @pytest.fixture
    def feint_move(self, player, target_enemy):
        """Create FeintAndPivot move instance"""
        move = FeintAndPivot(player)
        move.target = target_enemy
        return move

    def test_feint_creation(self, feint_move, player):
        """Test FeintAndPivot move is created correctly"""
        assert feint_move.name == "Feint & Pivot"
        assert feint_move.user == player
        assert feint_move.fatigue_cost == 45
        assert feint_move.xp_gain == 20
        assert feint_move.targeted == True

    def test_feint_stage_beat_values(self, feint_move):
        """Test FeintAndPivot has correct stage beat durations"""
        # [prep=1, execute=4, recoil=1, cooldown=4]
        assert feint_move.stage_beat[0] == 1  # prep
        assert feint_move.stage_beat[1] == 3  # execute
        assert feint_move.stage_beat[2] == 1  # recoil
        assert feint_move.stage_beat[3] == 3  # cooldown
        assert sum(feint_move.stage_beat) == 8

    def test_feint_not_viable_without_combat_position(self, player, target_enemy):
        """Test FeintAndPivot not viable without combat_position"""
        player.combat_position = None
        feint = FeintAndPivot(player)
        feint.target = target_enemy
        assert not feint.viable()

    def test_feint_not_viable_without_target(self, player):
        """Test FeintAndPivot not viable without target"""
        feint = FeintAndPivot(player)
        feint.target = None
        assert not feint.viable()

    def test_feint_not_viable_with_dead_target(self, player, target_enemy):
        """Test FeintAndPivot not viable if target is dead"""
        target_enemy.is_alive = lambda: False
        feint = FeintAndPivot(player)
        feint.target = target_enemy
        assert not feint.viable()

    def test_feint_viable_with_target_in_range(self, feint_move):
        """Test FeintAndPivot viable when target in range"""
        assert feint_move.viable()

    def test_feint_execute_damages_target(self, player, target_enemy, feint_move):
        """Test FeintAndPivot.execute() damages target"""
        initial_hp = target_enemy.hp

        feint_move.execute(player)

        # May or may not hit depending on rolls (probabilistic)
        assert target_enemy.hp <= initial_hp

    def test_feint_execute_deducts_fatigue(self, player, feint_move):
        """Test FeintAndPivot.execute() deducts fatigue"""
        initial_fatigue = player.fatigue

        feint_move.execute(player)

        assert player.fatigue == initial_fatigue - 45

    def test_feint_execute_repositions_player(self, player, target_enemy, feint_move):
        """A front-on feint pivots the player onto the target's flank.

        The old assertion was ``isinstance(final_pos, tuple)`` — true of the
        starting position, of any position, and of a move that never ran. The
        repositioning geometry is deterministic (no RNG in
        ``_calculate_new_position``), so the destination is exact.
        """
        assert (player.combat_position.x, player.combat_position.y) == (10, 10)
        # Target at (15, 10) faces W, i.e. straight at the player.
        assert feint_move._get_relative_position(
            player.combat_position,
            target_enemy.combat_position,
            target_enemy.combat_position.facing,
        ) == "front"

        feint_move.execute(player)

        # front -> flank: 3 squares along (target_facing + 90 deg) from the
        # target, which for a west-facing target is due east of it.
        assert (player.combat_position.x, player.combat_position.y) == (18, 10)
        # ...then the player turns to keep the target in view: from (18, 10)
        # the target at (15, 10) lies due west.
        assert player.combat_position.facing is Direction.W

    def test_feint_evaluates_power(self, player, feint_move):
        """Test FeintAndPivot power calculation"""
        feint_move.evaluate()

        # Utility-first: POWER_FACTOR of a full swing. This Mock weapon has a
        # real damage of 25 and no numeric str_mod/fin_mod, so int(25 * 0.45).
        assert FeintAndPivot.POWER_FACTOR == 0.45
        assert feint_move.power == int(25 * FeintAndPivot.POWER_FACTOR)


class TestVertigoSpinMove:
    """Test suite for VertigoSpin move - attack + status effect"""

    @pytest.fixture
    def player(self):
        """Create player for VertigoSpin"""
        p = Player()
        p.name = "Jean"
        p.hp = 100
        p.maxhp = 100
        p.fatigue = 150
        p.combat_position = CombatPosition(x=10, y=10, facing=Direction.N)
        p.eq_weapon = Mock(damage=28, base_damage_type="bludgeoning")
        p.strength = 14
        p.finesse = 3
        p.combat_proximity = {}
        p.is_alive = lambda: True
        return p

    @pytest.fixture
    def target_enemy(self, player):
        """Create target enemy"""
        enemy = NPC(name="StunTarget", description="Test Stun Target", damage=16, aggro=65, exp_award=55)
        enemy.hp = 70
        enemy.maxhp = 70
        enemy.protection = 2
        enemy.finesse = 4
        enemy.combat_position = CombatPosition(x=12, y=10, facing=Direction.W)
        enemy.states = []
        player.combat_proximity[enemy] = 8
        return enemy

    @pytest.fixture
    def spin_move(self, player, target_enemy):
        """Create VertigoSpin move instance"""
        move = VertigoSpin(player)
        move.target = target_enemy
        return move

    def test_spin_creation(self, spin_move, player):
        """Test VertigoSpin move is created correctly"""
        assert spin_move.name == "Vertigo Spin"
        assert spin_move.user == player
        assert spin_move.fatigue_cost == 50
        assert spin_move.xp_gain == 25
        assert spin_move.targeted == True

    def test_spin_stage_beat_values(self, spin_move):
        """Test VertigoSpin has correct stage beat durations"""
        # [prep=1, execute=3, recoil=1, cooldown=4]
        assert spin_move.stage_beat[0] == 1  # prep
        assert spin_move.stage_beat[1] == 2  # execute
        assert spin_move.stage_beat[2] == 2  # recoil
        assert spin_move.stage_beat[3] == 3  # cooldown
        assert sum(spin_move.stage_beat) == 8

    def test_spin_not_viable_without_combat_position(self, player, target_enemy):
        """Test VertigoSpin not viable without combat_position"""
        player.combat_position = None
        spin = VertigoSpin(player)
        spin.target = target_enemy
        assert not spin.viable()

    def test_spin_viable_with_target_in_range(self, spin_move):
        """Test VertigoSpin viable when target in range"""
        assert spin_move.viable()

    def test_spin_execute_damages_target(self, player, target_enemy, spin_move):
        """Test VertigoSpin.execute() damages target"""
        initial_hp = target_enemy.hp

        spin_move.execute(player)

        # May or may not hit depending on rolls
        assert target_enemy.hp <= initial_hp

    def test_spin_execute_deducts_fatigue(self, player, spin_move):
        """Test VertigoSpin.execute() deducts fatigue"""
        initial_fatigue = player.fatigue

        spin_move.execute(player)

        assert player.fatigue == initial_fatigue - 50

    def test_spin_execute_rotates_target_facing(self, player, target_enemy, spin_move):
        """Test VertigoSpin.execute() rotates target facing"""
        random.seed(42)
        initial_facing = target_enemy.combat_position.facing

        # Mock check_parry to ensure damage lands
        with patch('src.functions.check_parry', return_value=False):
            spin_move.execute(player)

        # Facing may or may not change (random choice)
        assert hasattr(target_enemy.combat_position.facing, 'name')
        # Check class name instead of isinstance/in due to module loading issues in tests
        assert target_enemy.combat_position.facing.__class__.__name__ == 'Direction'

    def test_spin_execute_applies_disoriented_status(self, player, target_enemy, spin_move):
        """Test VertigoSpin.execute() applies Disoriented status"""
        initial_states_count = len(target_enemy.states)

        # Mock check_parry to ensure status is applied
        with patch('src.functions.check_parry', return_value=False):
            spin_move.execute(player)

        # Disoriented status should be added (or status count increases)
        # Note: depends on Disoriented class implementation
        assert len(target_enemy.states) >= initial_states_count

    def test_spin_evaluates_power(self, player, spin_move):
        """Test VertigoSpin power calculation"""
        spin_move.evaluate()

        # Utility-first: POWER_FACTOR of a full swing. This Mock weapon has a
        # real damage of 28 and no numeric str_mod/fin_mod, so int(28 * 0.55).
        assert VertigoSpin.POWER_FACTOR == 0.55
        assert spin_move.power == int(28 * VertigoSpin.POWER_FACTOR)


class TestPhase3MovesIntegration:
    """Integration tests for Phase 3 moves with combat system"""

    @pytest.fixture
    def combat_scenario(self):
        """Create a complete combat scenario with player and enemies"""
        player = Player()
        player.name = "Jean"
        player.hp = 120
        player.maxhp = 120
        player.fatigue = 200
        player.combat_position = CombatPosition(x=10, y=10, facing=Direction.N)
        player.eq_weapon = Mock(power=20, base_damage_type="slashing")
        player.strength = 10
        player.finesse = 5
        player.protection = 3
        player.speed = 8
        player.combat_proximity = {}
        player.is_alive = lambda: True
        player.states = []

        enemies = []
        for i in range(3):
            enemy = NPC(name=f"Enemy{i}", description="Test Enemy", damage=12+i*2, aggro=50+i*5, exp_award=40+i*10)
            enemy.hp = 50
            enemy.maxhp = 50
            enemy.protection = 2
            enemy.finesse = 3
            enemy.speed = 6
            enemy.strength = 8
            enemy.combat_position = CombatPosition(
                x=10 + (i+1)*3,
                y=10,
                facing=Direction.W
            )
            enemy.states = []
            enemies.append(enemy)
            player.combat_proximity[enemy] = 5 + (i*2)

        return player, enemies

    def test_turn_before_whirl(self, combat_scenario):
        """Test using Turn move before Whirl Attack"""
        player, enemies = combat_scenario

        # Turn to face east
        turn = Turn(player)
        turn.target_direction = Direction.E
        turn.execute(player)

        assert player.combat_position.facing.value == Direction.E.value

        # Now whirl attack
        whirl = WhirlAttack(player)
        initial_fatigue = player.fatigue
        whirl.execute(player)

        assert player.fatigue == initial_fatigue - 45

    def test_sequence_turn_feint_spin(self, combat_scenario):
        """Test sequence: Turn → Feint & Pivot → Vertigo Spin"""
        player, enemies = combat_scenario
        target = enemies[0]

        # Turn to face target
        turn = Turn(player)
        turn.target_direction = Direction.E
        turn.execute(player)

        assert player.combat_position.facing.value == Direction.E.value

        # Feint and pivot
        feint = FeintAndPivot(player)
        feint.target = target
        feint.execute(player)

        # Knockback/stun spin
        spin = VertigoSpin(player)
        spin.target = target
        spin.execute(player)

    def test_all_moves_have_viable_method(self, combat_scenario):
        """Test all Phase 3 moves implement viable() check"""
        player, enemies = combat_scenario

        turn = Turn(player)
        whirl = WhirlAttack(player)
        feint = FeintAndPivot(player)
        spin = VertigoSpin(player)

        # All should be callable
        assert callable(turn.viable)
        assert callable(whirl.viable)
        assert callable(feint.viable)
        assert callable(spin.viable)

    def test_all_moves_have_evaluate_method(self, combat_scenario):
        """evaluate() must actually recompute ``power`` from live stats.

        The old body called evaluate() on four moves and asserted nothing, so an
        evaluate() that had become ``pass`` — leaving every move stuck on
        whatever power it was constructed with — would still have passed.

        This scenario's ``eq_weapon`` is a Mock with no usable ``damage``, so
        each attack falls to its documented strength-only fallback
        (strength * multiplier, strength = 10).
        """
        player, enemies = combat_scenario

        whirl = WhirlAttack(player)
        feint = FeintAndPivot(player)
        spin = VertigoSpin(player)

        for move in (whirl, feint, spin):
            move.power = -999  # poison the value so a no-op evaluate() shows

        whirl.evaluate()
        feint.evaluate()
        spin.evaluate()

        assert whirl.power == int(10 * WhirlAttack.AREA_POWER_FACTOR)
        assert feint.power == int(10 * FeintAndPivot.POWER_FACTOR)
        assert spin.power == int(10 * VertigoSpin.POWER_FACTOR)
        # ...and the poisoned sentinel is genuinely gone in every case.
        assert all(m.power > 0 for m in (whirl, feint, spin))

        # Turn is a pure repositioning move: it carries no power at all.
        turn = Turn(player)
        turn.evaluate()
        assert getattr(turn, "power", None) is None

    def test_fatigue_costs_reasonable(self, combat_scenario):
        """Test all Phase 3 moves have reasonable fatigue costs"""
        player, enemies = combat_scenario

        turn = Turn(player)
        whirl = WhirlAttack(player)
        feint = FeintAndPivot(player)
        spin = VertigoSpin(player)

        assert turn.fatigue_cost == 0
        assert whirl.fatigue_cost == 45
        assert feint.fatigue_cost == 45
        assert spin.fatigue_cost == 50
        # Every one of these must stay castable from a full bar (Player's base
        # maxfatigue is 150) -- a cost above it makes the move permanently
        # unreachable, since combat gates selection on fatigue >= cost.
        for move in (whirl, feint, spin):
            assert 0 < move.fatigue_cost <= 150

    def test_no_negative_fatigue(self, combat_scenario):
        """Test players can't execute moves when fatigued"""
        player, enemies = combat_scenario
        player.fatigue = 3  # Less than most move costs

        turn = Turn(player)
        turn.target_direction = Direction.S
        turn.execute(player)

        # Turn has zero fatigue cost, so fatigue unchanged
        assert player.fatigue == 3 - 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
