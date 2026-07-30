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


import pytest

try:
    from src.api.serializers.combat import (
        CombatStateSerializer,
        CombatantSerializer,
        StateEffectSerializer,
    )

    SERIALIZERS_AVAILABLE = True
except ImportError:
    SERIALIZERS_AVAILABLE = False


class FakeCombatant:
    """Stand-in for a Player/NPC using only attributes the engine really defines.

    Player/NPC/Combatant have no ``armor``/``defense``/``evasion``/``accuracy``/
    ``attack_power`` attributes, no ``equipped`` dict and no plural
    ``resistances`` (issue #430) — the serializer derives combat stats from
    ``protection``/``finesse``/``intelligence``/``eq_weapon`` and reads the
    singular ``resistance`` dict. Mocks that hand-set the old names are exactly
    why the always-default bug shipped, so this fake deliberately omits them.
    """

    def __init__(
        self,
        name="Goblin",
        level=5,
        hp=20,
        maxhp=30,
        damage=8,
        protection=1,
        speed=5,
        finesse=10,
        intelligence=10,
        strength=10,
        endurance=10,
        combat_proximity=1,
        resistance=None,
        inventory=None,
        eq_weapon=None,
    ):
        self.name = name
        self.level = level
        self.hp = hp
        self.maxhp = maxhp
        self.damage = damage
        self.protection = protection
        self.speed = speed
        self.finesse = finesse
        self.intelligence = intelligence
        self.strength = strength
        self.endurance = endurance
        self.combat_proximity = combat_proximity
        self.resistance = {} if resistance is None else resistance
        self.inventory = [] if inventory is None else inventory
        self.states = []
        if eq_weapon is not None:
            self.eq_weapon = eq_weapon


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Combat serializers not available"
)
class TestCombatStateSerializer:
    """Tests for CombatStateSerializer."""

    def test_serialize_combat_state_basic(self):
        """Test basic combat state serialization."""
        player = FakeCombatant(
            name="Jean",
            level=10,
            hp=80,
            maxhp=100,
            protection=5,
            speed=10,
            combat_proximity=0,
            resistance={"fire": 1.0, "ice": 1.0},
        )
        enemies = [FakeCombatant(resistance={"fire": 1.0, "ice": 1.0})]

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
        from types import SimpleNamespace

        # The serializer isinstance-checks the engine Player class, so build
        # an uninitialized real Player and attach just the attrs it reads.
        from src.player import Player

        weapon = SimpleNamespace(
            name="Iron Sword", damage=15, str_mod=0, fin_mod=0, subtype="Sword"
        )
        player = Player.__new__(Player)
        player.name = "Jean"
        player.level = 10
        player.hp = 80
        player.maxhp = 100
        player.protection = 5
        player.speed = 10
        player.finesse = 10
        player.intelligence = 10
        player.strength = 10
        player.states = []
        player.combat_proximity = 0
        player.inventory = []
        player.eq_weapon = weapon
        player.resistance = {"fire": 1.0}

        result = CombatantSerializer.serialize_combatant(player)

        assert result["name"] == "Jean"
        assert result["type"] == "player"
        assert result["level"] == 10
        assert result["health"]["current"] == 80
        assert result["health"]["max"] == 100
        assert "stats" in result
        # Player damage comes from the equipped weapon — Player has no `damage`.
        assert result["stats"]["damage"] == 15
        assert result["stats"]["defense"] == 5  # protection
        assert result["equipment"]["weapon"]["name"] == "Iron Sword"
        assert result["equipment"]["resistances"] == {"fire": 1.0}
        assert "status_effects" in result

    def test_serialize_combatant_npc(self):
        """Test serializing NPC as combatant."""
        npc = FakeCombatant()
        result = CombatantSerializer.serialize_combatant(npc)

        assert result["name"] == "Goblin"
        assert result["type"] == "npc"
        assert result["level"] == 5
        # NPCs equip nothing; their flat `damage` is their power.
        assert result["stats"]["damage"] == 8
        assert result["stats"]["attack_power"] == 8
        assert result["equipment"]["weapon"] is None

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
        combatants = [
            FakeCombatant(name="Test", level=1, hp=10, maxhp=10, damage=1, protection=0),
            FakeCombatant(name="Test", level=1, hp=10, maxhp=10, damage=1, protection=0),
        ]
        result = CombatantSerializer.serialize_combatant_list(combatants)

        assert len(result) == 2
        assert all("name" in c for c in result)


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Combat serializers not available"
)
class TestStateEffectSerializer:
    """Tests for StateEffectSerializer.

    Real `State` objects (src/states.py) expose `statustype` (e.g. "poison",
    "stun", "enraged") — not `state_type` — and have no generic
    `damage_per_turn`/`healing_per_turn`/`resistable` attributes (each
    subclass computes its own damage inline). The serializer maps
    `statustype` to the frontend's buff/debuff/ailment vocabulary.
    """

    def test_serialize_state_poison_is_ailment(self):
        """Test serializing a poison-like status effect."""

        class MockState:
            name = "Poison"
            statustype = "poison"
            description = "Takes damage each turn"

        state = MockState()
        result = StateEffectSerializer.serialize_state(state)

        assert result["name"] == "Poison"
        assert result["type"] == "ailment"
        assert result["severity"] == "severe"

    def test_serialize_state_buff(self):
        """Test serializing a positive status effect."""

        class MockState:
            name = "Regeneration"
            statustype = "revive"
            description = "Heals each turn"

        state = MockState()
        result = StateEffectSerializer.serialize_state(state)

        assert result["name"] == "Regeneration"
        assert result["type"] == "buff"
        assert result["severity"] == "light"

    def test_serialize_state_passthrough_type(self):
        """A statustype that is already a valid frontend type passes through unchanged."""

        class MockState:
            name = "Custom"
            statustype = "debuff"
            description = ""

        state = MockState()
        result = StateEffectSerializer.serialize_state(state)

        assert result["type"] == "debuff"

    def test_serialize_state_list(self):
        """Test serializing multiple status effects."""

        class MockState:
            name = "Effect"
            statustype = "disoriented"
            description = ""

        states = [MockState(), MockState()]
        result = StateEffectSerializer.serialize_state_list(states)

        assert len(result) == 2
        assert all("name" in s for s in result)

    def test_serialize_state_with_duration(self):
        """Test state with duration remaining."""

        class MockState:
            name = "Stun"
            statustype = "stun"
            description = "Cannot move"

        state = MockState()
        result = StateEffectSerializer.serialize_state_with_duration(state, duration_remaining=2)

        assert result["duration_remaining"] == 2
        assert result["active"] is True

    def test_serialize_state_duration_expired(self):
        """Test expired state effect."""

        class MockState:
            name = "Stun"
            statustype = "stun"
            description = ""

        state = MockState()
        result = StateEffectSerializer.serialize_state_with_duration(state, duration_remaining=0)

        assert result["active"] is False

    def test_get_severity_light_for_buff(self):
        """Test severity classification for a buff-category effect."""

        class MockState:
            name = "Fervent"
            statustype = "enraged"
            description = ""

        state = MockState()
        result = StateEffectSerializer.serialize_state(state)

        assert result["severity"] == "light"

    def test_get_severity_moderate_for_debuff(self):
        """Test severity classification for a debuff-category effect."""

        class MockState:
            name = "Disoriented"
            statustype = "disoriented"
            description = ""

        state = MockState()
        result = StateEffectSerializer.serialize_state(state)

        assert result["severity"] == "moderate"

    def test_get_severity_severe_for_ailment(self):
        """Test severity classification for an ailment-category effect."""

        class MockState:
            name = "Enflamed"
            statustype = "enflamed"
            description = ""

        state = MockState()
        result = StateEffectSerializer.serialize_state(state)

        assert result["severity"] == "severe"

    def test_serialize_state_missing_statustype_defaults(self):
        """A state with no statustype attribute at all defaults to generic/buff."""

        class MockState:
            name = "Mystery"
            description = ""

        state = MockState()
        result = StateEffectSerializer.serialize_state(state)

        assert result["type"] == "buff"


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
        player = FakeCombatant(
            name="Jean", level=10, hp=80, maxhp=100, protection=5, speed=10,
            combat_proximity=0,
        )
        enemies = [FakeCombatant()]

        state = CombatStateSerializer.serialize_combat_state(player, enemies)

        # Verify required fields
        required_fields = ["status", "round", "current_turn_index", "player", "enemies", "turn_order"]
        for field in required_fields:
            assert field in state, f"Missing required field: {field}"
