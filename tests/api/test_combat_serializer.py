"""
Unit tests for combat serializers.

Tests the serialization of:
- Combat state (full battle info)
- Combatants (player/NPC in combat)
- Moves (abilities and actions)
- State effects (status conditions)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

try:
    from src.api.serializers.combat import (
        CombatStateSerializer,
        CombatantSerializer,
        MoveSerializer,
        StateEffectSerializer,
    )

    SERIALIZERS_AVAILABLE = True
except ImportError:
    SERIALIZERS_AVAILABLE = False


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Combat serializers not available"
)
class TestCombatStateSerializer:
    """Tests for CombatStateSerializer."""

    def test_serialize_combat_state_basic(self):
        """Test basic combat state serialization."""
        # Mock player and enemies
        class MockPlayer:
            name = "Jean"
            level = 10
            health = 80
            max_health = 100
            damage = 15
            armor = 5
            speed = 10
            accuracy = 85
            evasion = 5
            states = []
            equipped = {"weapon": None, "body": None}
            resistances = {"fire": 1.0, "ice": 1.0}
            combat_proximity = 0

        class MockEnemy:
            name = "Goblin"
            level = 5
            health = 20
            max_health = 30
            damage = 8
            armor = 1
            speed = 5
            accuracy = 70
            evasion = 0
            states = []
            equipped = {"weapon": None, "body": None}
            resistances = {"fire": 1.0, "ice": 1.0}
            combat_proximity = 1

        player = MockPlayer()
        enemies = [MockEnemy()]

        result = CombatStateSerializer.serialize_combat_state(
            player, enemies, current_turn_index=0, round_number=1
        )

        assert result["status"] == "active"
        assert result["round"] == 1
        assert result["current_turn_index"] == 0
        assert "player" in result
        assert "enemies" in result
        assert len(result["enemies"]) == 1
        assert "turn_order" in result

    def test_serialize_turn_data(self):
        """Test turn data serialization."""

        class MockCombatant:
            name = "Warrior"

            def __init__(self):
                self.moves = ["attack", "defend"]

        combatant = MockCombatant()
        result = CombatStateSerializer.serialize_turn_data(combatant)

        assert result["name"] == "Warrior"
        assert "available_actions" in result
        assert "attack" in result["available_actions"]

    def test_serialize_battle_summary_victory(self):
        """Test battle summary serialization for victory."""

        class MockPlayer:
            name = "Jean"
            hp = 50
            maxhp = 100

        class MockEnemy:
            name = "Goblin"
            hp = 0
            maxhp = 30
            level = 5
            exp_reward = 100

        player = MockPlayer()
        enemies = [MockEnemy()]

        result = CombatStateSerializer.serialize_battle_summary(player, enemies, victory=True)

        assert result["status"] == "victory"
        assert result["player_hp"] == 50
        assert result["enemies_defeated"] == 1
        assert result["experience_gained"] > 0

    def test_serialize_battle_summary_defeat(self):
        """Test battle summary for defeat."""

        class MockPlayer:
            name = "Jean"
            hp = 0
            maxhp = 100

        class MockEnemy:
            name = "Goblin"
            hp = 10
            maxhp = 30

        player = MockPlayer()
        enemies = [MockEnemy()]

        result = CombatStateSerializer.serialize_battle_summary(player, enemies, victory=False)

        assert result["status"] == "defeat"
        assert result["experience_gained"] == 0


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Combat serializers not available"
)
class TestCombatantSerializer:
    """Tests for CombatantSerializer."""

    def test_serialize_combatant_player(self):
        """Test serializing player as combatant."""

        class MockInventory:
            pass

        class MockPlayer:
            name = "Jean"
            level = 10
            health = 80
            max_health = 100
            damage = 15
            armor = 5
            speed = 10
            accuracy = 85
            evasion = 5
            states = []
            combat_proximity = 0
            inventory = MockInventory()
            equipped = {"weapon": None, "body": None}
            resistances = {"fire": 1.0}

        player = MockPlayer()
        result = CombatantSerializer.serialize_combatant(player)

        assert result["name"] == "Jean"
        assert result["type"] == "player"
        assert result["level"] == 10
        assert result["health"]["current"] == 80
        assert result["health"]["max"] == 100
        assert "stats" in result
        assert result["stats"]["damage"] == 15
        assert "status_effects" in result

    def test_serialize_combatant_npc(self):
        """Test serializing NPC as combatant."""

        class MockNPC:
            name = "Goblin"
            level = 5
            health = 20
            max_health = 30
            damage = 8
            armor = 1
            speed = 5
            accuracy = 70
            evasion = 0
            states = []
            combat_proximity = 1
            equipped = {"weapon": None, "body": None}
            resistances = {}

        npc = MockNPC()
        result = CombatantSerializer.serialize_combatant(npc)

        assert result["name"] == "Goblin"
        assert result["type"] == "npc"
        assert result["level"] == 5

    def test_serialize_health_bar(self):
        """Test health bar serialization."""

        class MockCombatant:
            health = 25
            max_health = 100

        combatant = MockCombatant()
        result = CombatantSerializer.serialize_health_bar(combatant)

        assert result["current"] == 25
        assert result["max"] == 100
        assert result["percent"] == 25.0
        assert result["status"] == "critical"

    def test_serialize_health_bar_wounded(self):
        """Test health bar status for wounded."""

        class MockCombatant:
            health = 50
            max_health = 100

        combatant = MockCombatant()
        result = CombatantSerializer.serialize_health_bar(combatant)

        assert result["status"] == "wounded"
        assert result["percent"] == 50.0

    def test_serialize_combatant_list(self):
        """Test serializing multiple combatants."""

        class MockCombatant:
            name = "Test"
            level = 1
            health = 10
            max_health = 10
            damage = 1
            armor = 0
            speed = 5
            accuracy = 80
            evasion = 0
            states = []
            combat_proximity = 0
            equipped = {}
            resistances = {}

        combatants = [MockCombatant(), MockCombatant()]
        result = CombatantSerializer.serialize_combatant_list(combatants)

        assert len(result) == 2
        assert all("name" in c for c in result)


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Combat serializers not available"
)
class TestMoveSerializer:
    """Tests for MoveSerializer."""

    def test_serialize_move_basic(self):
        """Test basic move serialization."""

        class MockMove:
            name = "Slash"
            description = "A basic sword slash"
            move_type = "physical"
            base_damage = 15
            damage_type = "physical"
            mp_cost = 0
            stamina_cost = 10
            range = "melee"
            cooldown_max = 0
            cooldown = 0
            accuracy = 95

        move = MockMove()
        result = MoveSerializer.serialize_move(move)

        assert result["name"] == "Slash"
        assert result["type"] == "physical"
        assert result["damage"]["base"] == 15
        assert result["cost"]["stamina"] == 10
        assert result["range"] == "melee"
        assert result["accuracy"] == 95

    def test_serialize_move_list(self):
        """Test serializing multiple moves."""

        class MockMove:
            name = "Attack"
            description = ""
            move_type = "physical"
            base_damage = 10
            damage_type = "physical"
            mp_cost = 0
            stamina_cost = 5
            range = "melee"
            cooldown_max = 0
            cooldown = 0
            accuracy = 90

        moves = [MockMove(), MockMove()]
        result = MoveSerializer.serialize_move_list(moves)

        assert len(result) == 2
        assert all("name" in m for m in result)

    def test_serialize_move_with_cooldown(self):
        """Test move with cooldown state."""

        class MockMove:
            name = "Fireball"
            description = ""
            move_type = "magical"
            base_damage = 25
            damage_type = "fire"
            mp_cost = 20
            stamina_cost = 0
            range = "ranged"
            cooldown_max = 3
            cooldown = 0
            accuracy = 85

        move = MockMove()
        result = MoveSerializer.serialize_move_with_cooldown(move, cooldown_remaining=2)

        assert result["cooldown"]["remaining"] == 2
        assert result["available"] is False

    def test_serialize_move_available(self):
        """Test move is available when cooldown is zero."""

        class MockMove:
            name = "Attack"
            description = ""
            move_type = "physical"
            base_damage = 10
            damage_type = "physical"
            mp_cost = 0
            stamina_cost = 5
            range = "melee"
            cooldown_max = 0
            cooldown = 0
            accuracy = 90

        move = MockMove()
        result = MoveSerializer.serialize_move_with_cooldown(move, cooldown_remaining=0)

        assert result["available"] is True


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Combat serializers not available"
)
class TestStateEffectSerializer:
    """Tests for StateEffectSerializer."""

    def test_serialize_state_poison(self):
        """Test serializing poison status effect."""

        class MockState:
            name = "Poison"
            state_type = "debuff"
            description = "Takes damage each turn"
            damage_per_turn = 5
            healing_per_turn = 0
            resistable = True

        state = MockState()
        result = StateEffectSerializer.serialize_state(state)

        assert result["name"] == "Poison"
        assert result["type"] == "debuff"
        assert result["damage_per_turn"] == 5
        assert result["severity"] == "moderate"

    def test_serialize_state_heal(self):
        """Test serializing heal status effect."""

        class MockState:
            name = "Regeneration"
            state_type = "buff"
            description = "Heals each turn"
            damage_per_turn = 0
            healing_per_turn = 10
            resistable = False

        state = MockState()
        result = StateEffectSerializer.serialize_state(state)

        assert result["name"] == "Regeneration"
        assert result["type"] == "buff"
        assert result["healing_per_turn"] == 10

    def test_serialize_state_list(self):
        """Test serializing multiple status effects."""

        class MockState:
            name = "Effect"
            state_type = "debuff"
            description = ""
            damage_per_turn = 3
            healing_per_turn = 0
            resistable = True

        states = [MockState(), MockState()]
        result = StateEffectSerializer.serialize_state_list(states)

        assert len(result) == 2
        assert all("name" in s for s in result)

    def test_serialize_state_with_duration(self):
        """Test state with duration remaining."""

        class MockState:
            name = "Stun"
            state_type = "debuff"
            description = "Cannot move"
            damage_per_turn = 0
            healing_per_turn = 0
            resistable = True

        state = MockState()
        result = StateEffectSerializer.serialize_state_with_duration(state, duration_remaining=2)

        assert result["duration_remaining"] == 2
        assert result["active"] is True

    def test_serialize_state_duration_expired(self):
        """Test expired state effect."""

        class MockState:
            name = "Stun"
            state_type = "debuff"
            description = ""
            damage_per_turn = 0
            healing_per_turn = 0
            resistable = True

        state = MockState()
        result = StateEffectSerializer.serialize_state_with_duration(state, duration_remaining=0)

        assert result["active"] is False

    def test_get_severity_light(self):
        """Test severity classification for light damage."""

        class MockState:
            name = "Light Poison"
            state_type = "debuff"
            description = ""
            damage_per_turn = 0
            healing_per_turn = 0
            resistable = True

        state = MockState()
        result = StateEffectSerializer.serialize_state(state)

        assert result["severity"] == "light"

    def test_get_severity_severe(self):
        """Test severity classification for severe damage."""

        class MockState:
            name = "Severe Poison"
            state_type = "debuff"
            description = ""
            damage_per_turn = 10
            healing_per_turn = 0
            resistable = True

        state = MockState()
        result = StateEffectSerializer.serialize_state(state)

        assert result["severity"] == "severe"


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Combat serializers not available"
)
class TestGameServiceCombatMethods:
    """Integration tests for GameService combat methods."""

    def test_game_service_imports(self):
        """Test that GameService can import combat serializers."""
        from src.api.services.game_service import GameService

        # Verify imports work
        assert hasattr(GameService, "__init__")

    def test_combat_state_structure(self):
        """Test that combat state has required structure."""

        class MockPlayer:
            name = "Jean"
            level = 10
            health = 80
            max_health = 100
            damage = 15
            armor = 5
            speed = 10
            accuracy = 85
            evasion = 5
            states = []
            equipped = {}
            resistances = {}
            combat_proximity = 0

        class MockEnemy:
            name = "Goblin"
            level = 5
            health = 20
            max_health = 30
            damage = 8
            armor = 1
            speed = 5
            accuracy = 70
            evasion = 0
            states = []
            equipped = {}
            resistances = {}
            combat_proximity = 1

        player = MockPlayer()
        enemies = [MockEnemy()]

        state = CombatStateSerializer.serialize_combat_state(player, enemies)

        # Verify required fields
        required_fields = ["status", "round", "current_turn_index", "player", "enemies", "turn_order"]
        for field in required_fields:
            assert field in state, f"Missing required field: {field}"
