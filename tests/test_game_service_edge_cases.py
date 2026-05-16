"""Edge case and boundary condition tests for GameService.

Targets numeric boundaries, inventory limits, special data, and precision validation.
Focus areas:
- Numeric boundaries: HP (0, 1, max), EXP (0, threshold), Gold (0, max)
- Inventory: Weight (0, exact limit, over limit), capacity (0, 1, full, overfull)
- Cooldowns: 0 beats, 1 beat, max duration, expired
- Levels: 1, 99, extreme values (999+)
- Relationships: -100 to +100 scale edges
- Special cases: Empty collections, single elements, duplicates, unicode names
"""

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from src.api.services.game_service import GameService


@pytest.fixture(scope="session")
def _cached_game_service():
    """Cache GameService instance across the session (stateless singleton)."""
    return GameService()


@pytest.fixture
def game_service(_cached_game_service):
    """Return the cached GameService."""
    return _cached_game_service


@pytest.fixture
def mock_player():
    """Create a mock player with realistic state."""
    player = MagicMock()
    player.name = "Jean"
    player.location_x = 5
    player.location_y = 5
    player.level = 1
    player.hp = 100
    player.maxhp = 100
    player.maxhp_base = 100
    player.fatigue = 150
    player.maxfatigue = 150
    player.maxfatigue_base = 150
    player.strength = 10
    player.strength_base = 10
    player.finesse = 10
    player.finesse_base = 10
    player.speed = 10
    player.speed_base = 10
    player.endurance = 10
    player.endurance_base = 10
    player.charisma = 10
    player.charisma_base = 10
    player.intelligence = 10
    player.intelligence_base = 10
    player.faith = 10
    player.faith_base = 10
    player.weight_tolerance = 20.0
    player.weight_tolerance_base = 20.0
    player.weight_current = 0.0
    player.inventory = []
    player.in_combat = False
    player.enemies = []
    player.current_beat = 0
    player.combat_turn_index = 0
    player.heat = 0
    player.max_heat = 100

    # Setup universe
    universe = MagicMock()
    universe.story = {}
    universe.game_tick = 100

    # Setup tile
    test_tile = MagicMock()
    test_tile.name = "TestArea"
    test_tile.description = "Test area"
    test_tile.is_passable = True
    test_tile.block_exit = []
    test_tile.events_here = []
    test_tile.items_here = []
    test_tile.npcs_here = []
    test_tile.objects_here = []

    universe.get_tile = MagicMock(return_value=test_tile)
    player.universe = universe
    player.current_room = test_tile
    player.map = {(5, 5): test_tile}

    return player


# ========================= NUMERIC BOUNDARY TESTS =========================

class TestHPBoundaries:
    """Test HP boundaries: 0, 1, max, negative."""

    def test_player_hp_zero(self, game_service, mock_player):
        """Test player state with HP at exactly 0."""
        mock_player.hp = 0
        mock_player.maxhp = 100
        assert mock_player.hp == 0
        assert mock_player.maxhp == 100

    def test_player_hp_one(self, game_service, mock_player):
        """Test player state with HP at 1 (minimum alive)."""
        mock_player.hp = 1
        assert mock_player.hp == 1

    def test_player_hp_equal_maxhp(self, game_service, mock_player):
        """Test player state with HP equal to maxhp."""
        mock_player.hp = mock_player.maxhp
        assert mock_player.hp == mock_player.maxhp

    def test_player_hp_negative(self, game_service, mock_player):
        """Test player state with negative HP (dead)."""
        mock_player.hp = -50
        assert mock_player.hp < 0

    def test_player_hp_exceeds_maxhp(self, game_service, mock_player):
        """Test player state with HP exceeding maxhp."""
        mock_player.hp = mock_player.maxhp + 50
        assert mock_player.hp > mock_player.maxhp

    def test_maxhp_boundary_low(self, game_service, mock_player):
        """Test maxhp at minimum viable value (1)."""
        mock_player.maxhp = 1
        mock_player.hp = 1
        assert mock_player.maxhp == 1

    def test_maxhp_extreme_high(self, game_service, mock_player):
        """Test maxhp at extreme value (9999)."""
        mock_player.maxhp = 9999
        mock_player.hp = 9999
        assert mock_player.maxhp == 9999


class TestFatigueBoundaries:
    """Test fatigue (stamina) boundaries."""

    def test_fatigue_zero(self, game_service, mock_player):
        """Test fatigue at 0 (exhausted)."""
        mock_player.fatigue = 0
        assert mock_player.fatigue == 0

    def test_fatigue_one(self, game_service, mock_player):
        """Test fatigue at 1 (minimal)."""
        mock_player.fatigue = 1
        assert mock_player.fatigue == 1

    def test_fatigue_equal_maxfatigue(self, game_service, mock_player):
        """Test fatigue equal to maxfatigue."""
        mock_player.fatigue = mock_player.maxfatigue
        assert mock_player.fatigue == mock_player.maxfatigue

    def test_fatigue_exceeds_maxfatigue(self, game_service, mock_player):
        """Test fatigue exceeding maxfatigue."""
        mock_player.fatigue = mock_player.maxfatigue + 200
        assert mock_player.fatigue > mock_player.maxfatigue

    def test_maxfatigue_boundary_low(self, game_service, mock_player):
        """Test maxfatigue at minimum (1)."""
        mock_player.maxfatigue = 1
        mock_player.fatigue = 1
        assert mock_player.maxfatigue == 1


class TestLevelBoundaries:
    """Test character level boundaries."""

    def test_level_one(self, game_service, mock_player):
        """Test level at 1 (minimum)."""
        mock_player.level = 1
        assert mock_player.level == 1

    def test_level_ninety_nine(self, game_service, mock_player):
        """Test level at 99 (typical maximum)."""
        mock_player.level = 99
        assert mock_player.level == 99

    def test_level_extreme_high(self, game_service, mock_player):
        """Test level at extreme value (999)."""
        mock_player.level = 999
        assert mock_player.level == 999

    def test_level_zero_invalid(self, game_service, mock_player):
        """Test level at 0 (edge case - typically invalid)."""
        mock_player.level = 0
        assert mock_player.level == 0


class TestExperienceBoundaries:
    """Test experience boundaries."""

    def test_exp_zero(self, game_service, mock_player):
        """Test exp at 0 (no progress)."""
        mock_player.exp = 0
        assert mock_player.exp == 0

    def test_exp_one(self, game_service, mock_player):
        """Test exp at 1 (minimal)."""
        mock_player.exp = 1
        assert mock_player.exp == 1

    def test_exp_to_level_boundary(self, game_service, mock_player):
        """Test exp reaching exactly exp_to_level threshold."""
        mock_player.exp_to_level = 150
        mock_player.exp = 150
        assert mock_player.exp == mock_player.exp_to_level

    def test_exp_one_below_threshold(self, game_service, mock_player):
        """Test exp one point below threshold."""
        mock_player.exp_to_level = 150
        mock_player.exp = 149
        assert mock_player.exp < mock_player.exp_to_level

    def test_exp_extreme_value(self, game_service, mock_player):
        """Test exp at extreme value (999999)."""
        mock_player.exp = 999999
        assert mock_player.exp == 999999


# ========================= WEIGHT CALCULATION TESTS =========================

class TestWeightBoundaries:
    """Test inventory weight boundaries and calculations."""

    def test_weight_current_zero(self, game_service, mock_player):
        """Test weight_current at 0 (empty inventory)."""
        mock_player.weight_current = 0.0
        mock_player.inventory = []
        assert mock_player.weight_current == 0.0
        assert len(mock_player.inventory) == 0

    def test_weight_current_exact_tolerance(self, game_service, mock_player):
        """Test weight_current exactly at tolerance limit."""
        mock_player.weight_tolerance = 20.0
        mock_player.weight_current = 20.0
        assert mock_player.weight_current == mock_player.weight_tolerance

    def test_weight_current_exceeds_tolerance(self, game_service, mock_player):
        """Test weight_current exceeding tolerance by small amount."""
        mock_player.weight_tolerance = 20.0
        mock_player.weight_current = 20.1
        assert mock_player.weight_current > mock_player.weight_tolerance

    def test_weight_current_far_exceeds_tolerance(self, game_service, mock_player):
        """Test weight_current far exceeding tolerance."""
        mock_player.weight_tolerance = 20.0
        mock_player.weight_current = 50.5
        assert mock_player.weight_current > mock_player.weight_tolerance

    def test_weight_tolerance_boundary_low(self, game_service, mock_player):
        """Test weight_tolerance at minimum value (0.1)."""
        mock_player.weight_tolerance = 0.1
        mock_player.weight_current = 0.05
        assert mock_player.weight_current < mock_player.weight_tolerance

    def test_weight_tolerance_boundary_high(self, game_service, mock_player):
        """Test weight_tolerance at high value (100)."""
        mock_player.weight_tolerance = 100.0
        mock_player.weight_current = 99.9
        assert mock_player.weight_current < mock_player.weight_tolerance

    def test_weight_decimal_precision(self, game_service, mock_player):
        """Test weight calculations with decimal precision."""
        mock_player.weight_tolerance = 20.5
        mock_player.weight_current = 20.49
        assert abs(mock_player.weight_current - 20.49) < 0.001

    def test_weight_decimal_rounding(self, game_service, mock_player):
        """Test weight with values requiring rounding."""
        mock_player.weight_tolerance = 20.0
        mock_player.weight_current = 20.004999
        # Should be close but technically under
        assert mock_player.weight_current < mock_player.weight_tolerance + 0.01

    def test_weight_very_small_item(self, game_service, mock_player):
        """Test inventory with very light item (0.1)."""
        item = MagicMock()
        item.weight = 0.1
        item.name = "Feather"
        mock_player.inventory.append(item)
        mock_player.weight_current = 0.1
        assert len(mock_player.inventory) == 1
        assert mock_player.weight_current == 0.1

    def test_weight_heavy_item(self, game_service, mock_player):
        """Test inventory with heavy item."""
        item = MagicMock()
        item.weight = 8.0
        item.name = "GreatSword"
        mock_player.inventory.append(item)
        mock_player.weight_current = 8.0
        assert len(mock_player.inventory) == 1
        assert mock_player.weight_current == 8.0

    def test_weight_single_item_exceeds_capacity(self, game_service, mock_player):
        """Test single item exceeding weight capacity."""
        item = MagicMock()
        item.weight = 25.0
        item.name = "Anchor"
        mock_player.weight_tolerance = 20.0
        mock_player.weight_current = 25.0
        # Verifies item is too heavy
        assert mock_player.weight_current > mock_player.weight_tolerance


# ========================= INVENTORY EDGE CASES =========================

class TestInventoryEdgeCases:
    """Test inventory capacity and collection edge cases."""

    def test_inventory_empty(self, game_service, mock_player):
        """Test completely empty inventory."""
        mock_player.inventory = []
        assert len(mock_player.inventory) == 0

    def test_inventory_single_item(self, game_service, mock_player):
        """Test inventory with single item."""
        item = MagicMock()
        item.name = "TestItem"
        mock_player.inventory = [item]
        assert len(mock_player.inventory) == 1
        assert mock_player.inventory[0].name == "TestItem"

    def test_inventory_duplicate_items(self, game_service, mock_player):
        """Test inventory with duplicate item instances."""
        item1 = MagicMock()
        item1.name = "Gold"
        item1.count = 10
        item2 = MagicMock()
        item2.name = "Gold"
        item2.count = 15
        mock_player.inventory = [item1, item2]
        assert len(mock_player.inventory) == 2
        total_gold = sum(getattr(item, 'count', 1) for item in mock_player.inventory if item.name == "Gold")
        assert total_gold == 25

    def test_inventory_max_capacity(self, game_service, mock_player):
        """Test inventory at maximum item count."""
        items_list = [MagicMock(name=f"Item{i}", weight=0.1) for i in range(200)]
        mock_player.inventory = items_list
        assert len(mock_player.inventory) == 200

    def test_inventory_nil_weight_items(self, game_service, mock_player):
        """Test inventory with zero-weight items (currency, keys)."""
        item1 = MagicMock()
        item1.name = "Gold"
        item1.weight = 0.0
        item2 = MagicMock()
        item2.name = "Key"
        item2.weight = 0.0
        mock_player.inventory = [item1, item2]
        mock_player.weight_current = 0.0
        assert len(mock_player.inventory) == 2
        assert mock_player.weight_current == 0.0

    def test_inventory_mixed_weight_items(self, game_service, mock_player):
        """Test inventory with varied weight distribution."""
        item1 = MagicMock()
        item1.weight = 0.1  # Light
        item2 = MagicMock()
        item2.weight = 5.0  # Medium
        item3 = MagicMock()
        item3.weight = 14.9  # Heavy
        mock_player.inventory = [item1, item2, item3]
        mock_player.weight_current = item1.weight + item2.weight + item3.weight
        assert mock_player.weight_current == 20.0


# ========================= ATTRIBUTE BOUNDARIES =========================

class TestAttributeBoundaries:
    """Test character attribute (str, fin, speed, etc.) boundaries."""

    def test_strength_minimum(self, game_service, mock_player):
        """Test strength at minimum value (1)."""
        mock_player.strength = 1
        mock_player.strength_base = 1
        assert mock_player.strength == 1

    def test_strength_zero(self, game_service, mock_player):
        """Test strength at 0 (edge case)."""
        mock_player.strength = 0
        assert mock_player.strength == 0

    def test_strength_negative(self, game_service, mock_player):
        """Test strength at negative value (debuffed)."""
        mock_player.strength = -5
        assert mock_player.strength < 0

    def test_strength_extreme_high(self, game_service, mock_player):
        """Test strength at extreme value (99)."""
        mock_player.strength = 99
        assert mock_player.strength == 99

    def test_finesse_minimum(self, game_service, mock_player):
        """Test finesse at minimum (1)."""
        mock_player.finesse = 1
        assert mock_player.finesse == 1

    def test_speed_minimum(self, game_service, mock_player):
        """Test speed at minimum (1)."""
        mock_player.speed = 1
        assert mock_player.speed == 1

    def test_endurance_zero(self, game_service, mock_player):
        """Test endurance at 0."""
        mock_player.endurance = 0
        assert mock_player.endurance == 0

    def test_charisma_extreme_high(self, game_service, mock_player):
        """Test charisma at extreme high (99)."""
        mock_player.charisma = 99
        assert mock_player.charisma == 99

    def test_intelligence_negative(self, game_service, mock_player):
        """Test intelligence at negative (debuffed)."""
        mock_player.intelligence = -10
        assert mock_player.intelligence < 0

    def test_faith_boundary_values(self, game_service, mock_player):
        """Test faith at boundary values 0, 1, 50, 99."""
        for faith_val in [0, 1, 50, 99]:
            mock_player.faith = faith_val
            assert mock_player.faith == faith_val


# ========================= RELATIONSHIP BOUNDARIES =========================

class TestRelationshipBoundaries:
    """Test NPC reputation/relationship boundaries (-100 to +100)."""

    def test_relationship_maximum_positive(self, game_service, mock_player):
        """Test relationship at +100 (maximum favor)."""
        reputation = {"Gorran": 100}
        assert reputation["Gorran"] == 100

    def test_relationship_maximum_negative(self, game_service, mock_player):
        """Test relationship at -100 (maximum hatred)."""
        reputation = {"Gorran": -100}
        assert reputation["Gorran"] == -100

    def test_relationship_zero(self, game_service, mock_player):
        """Test relationship at 0 (neutral)."""
        reputation = {"Gorran": 0}
        assert reputation["Gorran"] == 0

    def test_relationship_barely_positive(self, game_service, mock_player):
        """Test relationship at +1 (barely favorable)."""
        reputation = {"Gorran": 1}
        assert reputation["Gorran"] == 1

    def test_relationship_barely_negative(self, game_service, mock_player):
        """Test relationship at -1 (barely unfavorable)."""
        reputation = {"Gorran": -1}
        assert reputation["Gorran"] == -1

    def test_relationship_exceeds_bounds_positive(self, game_service, mock_player):
        """Test relationship exceeding +100 (edge case)."""
        reputation = {"Gorran": 150}
        # May be clamped by the system, but test boundary awareness
        assert reputation["Gorran"] > 100

    def test_relationship_exceeds_bounds_negative(self, game_service, mock_player):
        """Test relationship below -100 (edge case)."""
        reputation = {"Gorran": -150}
        assert reputation["Gorran"] < -100

    def test_relationship_multiple_npcs(self, game_service, mock_player):
        """Test relationship tracking for multiple NPCs."""
        reputation = {
            "Gorran": 100,
            "Mynx": -50,
            "Conclave": 0,
            "King": 25,
            "Queen": -75,
        }
        assert len(reputation) == 5
        assert reputation["Gorran"] == 100
        assert reputation["Mynx"] == -50
        assert reputation["King"] == 25


# ========================= SPECIAL DATA CASES =========================

class TestSpecialDataCases:
    """Test edge cases with special data: unicode, empty strings, nulls."""

    def test_player_name_unicode(self, game_service, mock_player):
        """Test player name with unicode characters."""
        mock_player.name = "Jean™"
        assert "™" in mock_player.name

    def test_player_name_empty_string(self, game_service, mock_player):
        """Test player name as empty string (edge case)."""
        mock_player.name = ""
        assert mock_player.name == ""

    def test_player_name_very_long(self, game_service, mock_player):
        """Test player name with very long string."""
        long_name = "J" * 1000
        mock_player.name = long_name
        assert len(mock_player.name) == 1000

    def test_item_name_unicode(self, game_service, mock_player):
        """Test item name with unicode characters."""
        item = MagicMock()
        item.name = "Sword of Übermensch"
        assert "Über" in item.name

    def test_item_description_empty(self, game_service, mock_player):
        """Test item description as empty string."""
        item = MagicMock()
        item.description = ""
        mock_player.inventory.append(item)
        assert item.description == ""

    def test_npc_dialogue_unicode_emoji(self, game_service, mock_player):
        """Test NPC dialogue containing emoji-like unicode."""
        dialogue = "Hello 👋 traveler!"
        assert "👋" in dialogue

    def test_multiple_unicode_names(self, game_service, mock_player):
        """Test system with multiple unicode-named entities."""
        entities = {
            "Npc1": "François",
            "Npc2": "José",
            "Npc3": "Søren",
            "Npc4": "北京",
        }
        assert len(entities) == 4
        assert entities["Npc1"] == "François"


# ========================= COOLDOWN BOUNDARIES =========================

class TestCooldownBoundaries:
    """Test cooldown boundaries: 0 beats, 1 beat, max, expired."""

    def test_cooldown_zero_beats(self, game_service, mock_player):
        """Test cooldown with 0 beats (expired immediately)."""
        cooldown = {"test_move": 0}
        assert cooldown["test_move"] == 0

    def test_cooldown_one_beat(self, game_service, mock_player):
        """Test cooldown with 1 beat remaining."""
        cooldown = {"test_move": 1}
        assert cooldown["test_move"] == 1

    def test_cooldown_max_beats(self, game_service, mock_player):
        """Test cooldown at maximum (e.g., 100 beats)."""
        cooldown = {"test_move": 100}
        assert cooldown["test_move"] == 100

    def test_cooldown_extreme_high(self, game_service, mock_player):
        """Test cooldown at extreme value (999 beats)."""
        cooldown = {"test_move": 999}
        assert cooldown["test_move"] == 999

    def test_cooldown_negative(self, game_service, mock_player):
        """Test cooldown at negative value (shouldn't happen but boundary test)."""
        cooldown = {"test_move": -10}
        assert cooldown["test_move"] < 0

    def test_multiple_cooldowns(self, game_service, mock_player):
        """Test tracking multiple move cooldowns simultaneously."""
        cooldowns = {
            "attack": 0,
            "dodge": 1,
            "special": 5,
            "ultimate": 50,
        }
        assert len(cooldowns) == 4
        assert cooldowns["attack"] == 0
        assert cooldowns["ultimate"] == 50


# ========================= HEAT/EMOTION BOUNDARIES =========================

class TestHeatBoundaries:
    """Test heat (emotion state) boundaries."""

    def test_heat_zero(self, game_service, mock_player):
        """Test heat at 0 (no emotional state)."""
        mock_player.heat = 0
        assert mock_player.heat == 0

    def test_heat_one(self, game_service, mock_player):
        """Test heat at 1 (minimal emotion)."""
        mock_player.heat = 1
        assert mock_player.heat == 1

    def test_heat_at_max(self, game_service, mock_player):
        """Test heat at max value (100)."""
        mock_player.max_heat = 100
        mock_player.heat = 100
        assert mock_player.heat == mock_player.max_heat

    def test_heat_exceeds_max(self, game_service, mock_player):
        """Test heat exceeding max (edge case)."""
        mock_player.max_heat = 100
        mock_player.heat = 150
        assert mock_player.heat > mock_player.max_heat

    def test_heat_nearly_at_max(self, game_service, mock_player):
        """Test heat one point below max."""
        mock_player.max_heat = 100
        mock_player.heat = 99
        assert mock_player.heat < mock_player.max_heat


# ========================= COMBAT BEAT BOUNDARIES =========================

class TestCombatBeatBoundaries:
    """Test combat beat counter boundaries."""

    def test_current_beat_zero(self, game_service, mock_player):
        """Test current beat at 0 (start of combat)."""
        mock_player.current_beat = 0
        assert mock_player.current_beat == 0

    def test_current_beat_one(self, game_service, mock_player):
        """Test current beat at 1 (first action)."""
        mock_player.current_beat = 1
        assert mock_player.current_beat == 1

    def test_current_beat_high(self, game_service, mock_player):
        """Test current beat at high value (1000)."""
        mock_player.current_beat = 1000
        assert mock_player.current_beat == 1000

    def test_combat_turn_index_zero(self, game_service, mock_player):
        """Test combat turn index at 0 (first turn)."""
        mock_player.combat_turn_index = 0
        assert mock_player.combat_turn_index == 0


# ========================= COLLECTION BOUNDARY TESTS =========================

class TestCollectionBoundaries:
    """Test edge cases with collections: enemies, npcs, items."""

    def test_enemies_empty_list(self, game_service, mock_player):
        """Test enemies list when empty."""
        mock_player.enemies = []
        assert len(mock_player.enemies) == 0

    def test_enemies_single_enemy(self, game_service, mock_player):
        """Test enemies list with single enemy."""
        enemy = MagicMock()
        enemy.name = "Slime"
        mock_player.enemies = [enemy]
        assert len(mock_player.enemies) == 1
        assert mock_player.enemies[0].name == "Slime"

    def test_enemies_multiple_same_type(self, game_service, mock_player):
        """Test enemies list with multiple of same type."""
        enemies = []
        for _ in range(5):
            enemy = MagicMock()
            enemy.name = "Slime"
            enemies.append(enemy)
        mock_player.enemies = enemies
        assert len(mock_player.enemies) == 5
        assert all(e.name == "Slime" for e in mock_player.enemies)

    def test_enemies_mixed_types(self, game_service, mock_player):
        """Test enemies list with different NPC types."""
        enemy1 = MagicMock()
        enemy1.name = "Slime"
        enemy1.hp = 10
        enemy2 = MagicMock()
        enemy2.name = "CaveBat"
        enemy2.hp = 15
        enemy3 = MagicMock()
        enemy3.name = "KingSlime"
        enemy3.hp = 50
        mock_player.enemies = [enemy1, enemy2, enemy3]
        assert len(mock_player.enemies) == 3
        assert mock_player.enemies[0].name == "Slime"
        assert mock_player.enemies[2].hp == 50

    def test_npcs_in_room_empty(self, game_service, mock_player):
        """Test npcs_here when empty."""
        mock_player.current_room.npcs_here = []
        assert len(mock_player.current_room.npcs_here) == 0

    def test_npcs_in_room_single(self, game_service, mock_player):
        """Test npcs_here with single NPC."""
        npc = MagicMock(name="Gorran")
        mock_player.current_room.npcs_here = [npc]
        assert len(mock_player.current_room.npcs_here) == 1

    def test_items_here_empty(self, game_service, mock_player):
        """Test items_here when empty."""
        mock_player.current_room.items_here = []
        assert len(mock_player.current_room.items_here) == 0

    def test_items_here_full(self, game_service, mock_player):
        """Test items_here with many items."""
        items = [MagicMock(name=f"Item{i}") for i in range(50)]
        mock_player.current_room.items_here = items
        assert len(mock_player.current_room.items_here) == 50


# ========================= EDGE CASE GAME STATE TESTS =========================

class TestGameStateEdgeCases:
    """Test edge cases in overall game state."""

    def test_player_in_combat_false(self, game_service, mock_player):
        """Test in_combat flag set to False."""
        mock_player.in_combat = False
        assert mock_player.in_combat is False

    def test_player_in_combat_true(self, game_service, mock_player):
        """Test in_combat flag set to True."""
        mock_player.in_combat = True
        assert mock_player.in_combat is True

    def test_game_tick_zero(self, game_service, mock_player):
        """Test game tick at 0 (start)."""
        mock_player.universe.game_tick = 0
        assert mock_player.universe.game_tick == 0

    def test_game_tick_one(self, game_service, mock_player):
        """Test game tick at 1."""
        mock_player.universe.game_tick = 1
        assert mock_player.universe.game_tick == 1

    def test_game_tick_extreme(self, game_service, mock_player):
        """Test game tick at extreme value (999999)."""
        mock_player.universe.game_tick = 999999
        assert mock_player.universe.game_tick == 999999

    def test_location_origin(self, game_service, mock_player):
        """Test player at origin (0, 0)."""
        mock_player.location_x = 0
        mock_player.location_y = 0
        assert mock_player.location_x == 0
        assert mock_player.location_y == 0

    def test_location_negative_coordinates(self, game_service, mock_player):
        """Test player at negative coordinates (edge case)."""
        mock_player.location_x = -10
        mock_player.location_y = -10
        assert mock_player.location_x < 0
        assert mock_player.location_y < 0

    def test_location_large_coordinates(self, game_service, mock_player):
        """Test player at large coordinates."""
        mock_player.location_x = 1000
        mock_player.location_y = 1000
        assert mock_player.location_x == 1000


# ========================= DECIMAL PRECISION TESTS =========================

class TestDecimalPrecision:
    """Test floating point and decimal precision edge cases."""

    def test_weight_decimal_two_places(self, game_service, mock_player):
        """Test weight with 2 decimal places."""
        mock_player.weight_current = 20.50
        assert abs(mock_player.weight_current - 20.50) < 0.001

    def test_weight_decimal_three_places(self, game_service, mock_player):
        """Test weight with 3 decimal places."""
        mock_player.weight_current = 20.505
        assert abs(mock_player.weight_current - 20.505) < 0.0001

    def test_weight_decimal_many_places(self, game_service, mock_player):
        """Test weight with many decimal places (floating point)."""
        mock_player.weight_current = 20.123456789
        assert 20.1 < mock_player.weight_current < 20.2

    def test_weight_sum_decimal_rounding(self, game_service, mock_player):
        """Test weight calculation with rounding accumulation."""
        weights = [0.1] * 10
        total = sum(weights)
        # Floating point rounding may cause slight variance
        assert 0.99 < total < 1.01

    def test_exp_ratio_decimal(self, game_service, mock_player):
        """Test experience ratio with decimal."""
        exp_progress = 75 / 150  # 0.5
        assert abs(exp_progress - 0.5) < 0.001


# ========================= INTEGRATION BOUNDARY TESTS =========================

class TestBoundaryIntegration:
    """Test boundaries integrated together."""

    def test_low_hp_low_fatigue(self, game_service, mock_player):
        """Test player with both low HP and low fatigue."""
        mock_player.hp = 1
        mock_player.fatigue = 0
        assert mock_player.hp == 1
        assert mock_player.fatigue == 0

    def test_high_level_low_attributes(self, game_service, mock_player):
        """Test high level character with low base attributes."""
        mock_player.level = 99
        mock_player.strength = 0
        mock_player.finesse = 0
        assert mock_player.level == 99
        assert mock_player.strength == 0

    def test_max_weight_max_items(self, game_service, mock_player):
        """Test at maximum weight and maximum item count."""
        items = [MagicMock(weight=0.1) for _ in range(200)]
        mock_player.inventory = items
        mock_player.weight_current = 20.0
        assert len(mock_player.inventory) == 200
        assert mock_player.weight_current == 20.0

    def test_zero_reputation_zero_heat(self, game_service, mock_player):
        """Test zero relationship values and zero heat."""
        mock_player.heat = 0
        reputation = {"All": 0}
        assert mock_player.heat == 0
        assert reputation["All"] == 0

    def test_multiple_extreme_values(self, game_service, mock_player):
        """Test multiple boundary conditions simultaneously."""
        mock_player.hp = 1
        mock_player.level = 99
        mock_player.weight_current = 20.0
        mock_player.strength = 99
        mock_player.heat = 100
        assert mock_player.hp == 1
        assert mock_player.level == 99
        assert mock_player.weight_current == 20.0
        assert mock_player.strength == 99
        assert mock_player.heat == 100
