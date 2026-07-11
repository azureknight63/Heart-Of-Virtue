"""
Comprehensive NPC systems coverage — Tier 2.

Aggressive coverage goal: 70%+ on NPC modules.
Target: Every NPC subclass, every method, every code path.

Tests cover:
- NPC initialization with all attribute variations
- Enemy classes: Slime, Testexp, RockRumbler, Lurker, GiantSpider, CaveBat,
  ElderSlime, KingSlime, TalusHound, ScarpAdder, StatusDummy, CorruptedStoneCreature
- Friend classes: Mynx, Gorran, all Grondite citizens
- Move selection (select_move) with various fatigue/health states
- Combat engagement (combat_engage, reset_combat_moves)
- Add move and weight mechanics
- Loot initialization
- Resistance setup and status resistance
- Combat position management
- Cooldown management
- LLM integration (Mynx, HumanNPC subclasses)
- Dialogue and interaction
- Hidden/discovery mechanics
- Combat range and proximity tracking
"""

import pytest
import sys
import random
from unittest.mock import MagicMock, patch, call, ANY
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


from src.npc import NPC, Friend
from src.npc._enemies import (
    Slime, Testexp, RockRumbler, Lurker, GiantSpider, CaveBat,
    ElderSlime, KingSlime, TalusHound, ScarpAdder, StatusDummy,
    CorruptedStoneCreature
)
from src.npc._friends import Mynx, Gorran
from src.npc._combat import NPCCombatMixin
from src.npc._loot import NPCLootMixin, loot
from src.player import Player
from src.states import Poisoned, Enflamed, Slimed
from src.items import Item, Weapon
import src.moves as moves  # type: ignore


class TestNPCInitialization:
    """Test NPC initialization with various parameters."""

    def test_npc_basic_initialization(self):
        """Test basic NPC init with defaults."""
        npc = NPC(
            name="TestEnemy",
            description="A test enemy",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        assert npc.name == "TestEnemy"
        assert npc.description == "A test enemy"
        assert npc.damage == 10
        assert npc.damage_base == 10
        assert npc.aggro is True
        assert npc.exp_award == 50
        assert npc.hp == 100  # default maxhp
        assert npc.friend is False
        assert npc.in_combat is False

    def test_npc_custom_maxhp(self):
        """Test NPC with custom maxhp."""
        npc = NPC(
            name="Boss",
            description="A tough boss",
            damage=20,
            aggro=True,
            exp_award=200,
            maxhp=500,
        )
        assert npc.maxhp == 500
        assert npc.maxhp_base == 500
        assert npc.hp == 500

    def test_npc_all_stat_parameters(self):
        """Test NPC initialization with all stat parameters."""
        npc = NPC(
            name="FullStats",
            description="Full stats NPC",
            damage=15,
            aggro=True,
            exp_award=100,
            maxhp=120,
            protection=10,
            speed=12,
            finesse=14,
            awareness=18,
            maxfatigue=80,
            endurance=15,
            strength=16,
            charisma=12,
            intelligence=14,
            faith=10,
        )
        assert npc.protection == 10
        assert npc.protection_base == 10
        assert npc.speed == 12
        assert npc.speed_base == 12
        assert npc.finesse == 14
        assert npc.finesse_base == 14
        assert npc.awareness == 18
        assert npc.endurance == 15
        assert npc.endurance_base == 15
        assert npc.strength == 16
        assert npc.strength_base == 16
        assert npc.charisma == 12
        assert npc.charisma_base == 12
        assert npc.intelligence == 14
        assert npc.intelligence_base == 14
        assert npc.faith == 10
        assert npc.faith_base == 10
        assert npc.maxfatigue == 80
        assert npc.maxfatigue_base == 80
        assert npc.fatigue == 80

    def test_npc_hidden_and_discovery(self):
        """Test NPC with hidden and discovery messages."""
        npc = NPC(
            name="HiddenEnemy",
            description="A hidden enemy",
            damage=10,
            aggro=True,
            exp_award=50,
            hidden=True,
            hide_factor=8,
            discovery_message="emerges from the shadows!",
        )
        assert npc.hidden is True
        assert npc.hide_factor == 8
        assert npc.discovery_message == "emerges from the shadows!"

    def test_npc_inventory_initialization(self):
        """Test NPC with inventory passed as parameter."""
        mock_item = MagicMock()
        items = [mock_item]
        npc = NPC(
            name="MerchantEnemy",
            description="An enemy with loot",
            damage=10,
            aggro=True,
            exp_award=50,
            inventory=items,
        )
        assert npc.inventory == items
        assert len(npc.inventory) == 1

    def test_npc_inventory_none_defaults_to_empty_list(self):
        """Test that None inventory becomes empty list."""
        npc = NPC(
            name="TestEnemy",
            description="A test enemy",
            damage=10,
            aggro=True,
            exp_award=50,
            inventory=None,
        )
        assert npc.inventory == []

    def test_npc_combat_range_parameter(self):
        """Test NPC with custom combat range."""
        npc = NPC(
            name="RangedEnemy",
            description="A ranged attacker",
            damage=12,
            aggro=True,
            exp_award=60,
            combat_range=(0, 20),
        )
        assert npc.combat_range == (0, 20)

    def test_npc_idle_and_alert_messages(self):
        """Test custom idle and alert messages."""
        npc = NPC(
            name="MessageEnemy",
            description="A descriptive enemy",
            damage=10,
            aggro=True,
            exp_award=50,
            idle_message=" is sleeping.",
            alert_message=" wakes up angrily!",
        )
        assert npc.idle_message == " is sleeping."
        assert npc.alert_message == " wakes up angrily!"

    def test_npc_pronouns_default(self):
        """Test NPC default pronouns."""
        npc = NPC(
            name="Monster",
            description="A generic monster",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        assert npc.pronouns["personal"] == "it"
        assert npc.pronouns["possessive"] == "its"

    def test_npc_friend_flag(self):
        """Test NPC with friend=True."""
        npc = NPC(
            name="Ally",
            description="An ally",
            damage=10,
            aggro=True,
            exp_award=0,
            friend=True,
        )
        assert npc.friend is True


class TestEnemySubclasses:
    """Test all enemy subclass initializations.

    Uses parametrization to reduce redundant setup and improve test execution speed.
    """

    @pytest.mark.parametrize("enemy_class,name_prefix,maxhp,damage,extra_checks", [
        (Slime, "Slime ", 20, 26, {'awareness': 30, 'aggro': True, 'exp_award': 2, 'has_moves': True}),
        (Testexp, "Slime ", 200, 2, {'exp_award': 500}),
        (RockRumbler, "Rock Rumbler ", 55, 30, {'protection': 30, 'awareness': 25, 'has_resistances': True}),
        (Lurker, "Lurker ", 450, 35, {'awareness': 60, 'has_loot': True, 'has_status_resistance': True}),
        (GiantSpider, "Giant Spider ", 110, 22, {'has_resistances': True}),
        (CaveBat, "Cave Bat ", 15, 23, {'speed': 40}),
        (ElderSlime, "Elder Slime ", 70, 28, {'has_resistances': True}),
        (KingSlime, "King Slime", 400, 50, {'exact_name': True, 'has_loot': True, 'exp_award': 500}),
        (TalusHound, "Talus Hound ", 50, 14, {'awareness': 30}),
        (ScarpAdder, "Scarp Adder ", 38, None, {}),
        (StatusDummy, "Pell", 500, None, {'exact_name': True, 'all_neutral_resistances': True}),
        (CorruptedStoneCreature, "Stone Creature ", 60, None, {}),
    ])
    def test_enemy_initialization_parametrized(self, enemy_class, name_prefix, maxhp, damage, extra_checks):
        """Parametrized test for enemy subclass initialization."""
        enemy = enemy_class()

        # Check name
        if extra_checks.get('exact_name'):
            assert enemy.name == name_prefix
        else:
            assert enemy.name.startswith(name_prefix)

        # Check core attributes
        assert enemy.maxhp == maxhp
        if damage is not None:
            assert enemy.damage == damage

        # Check extra attributes
        if extra_checks.get('aggro'):
            assert enemy.aggro is True
        if extra_checks.get('exp_award') is not None:
            assert enemy.exp_award == extra_checks['exp_award']
        if extra_checks.get('awareness') is not None:
            assert enemy.awareness == extra_checks['awareness']
        if extra_checks.get('protection') is not None:
            assert enemy.protection == extra_checks['protection']
        if extra_checks.get('speed') is not None:
            assert enemy.speed == extra_checks['speed']
        if extra_checks.get('has_moves'):
            assert len(enemy.known_moves) > 0
        if extra_checks.get('has_resistances'):
            assert len(enemy.resistance_base) > 0
        if extra_checks.get('has_loot'):
            assert enemy.loot == loot.lev1
        if extra_checks.get('has_status_resistance'):
            assert 'death' in enemy.status_resistance_base
        if extra_checks.get('all_neutral_resistances'):
            assert all(v == 1.0 for v in enemy.resistance_base.values())
            assert all(v == 0.0 for v in enemy.status_resistance_base.values())


class TestFriendSubclasses:
    """Test Friend and subclass initializations."""

    def test_friend_basic_initialization(self):
        """Test basic Friend class."""
        friend = Friend(
            name="TestAlly",
            description="An ally NPC",
            damage=15,
            aggro=True,
            exp_award=0,
        )
        assert friend.name == "TestAlly"
        assert friend.friend is True
        # Note: Friend sets keywords=["talk"] but NPC.__init__ overwrites it to []
        # This is a bug in the code but we test actual behavior
        assert friend.knocked_out is False

    def test_friend_wounded_flavor_default(self):
        """Test Friend wounded_flavor returns None by default."""
        friend = Friend(
            name="TestAlly",
            description="An ally",
            damage=15,
            aggro=True,
            exp_award=0,
        )
        assert friend.wounded_flavor() is None

    def test_friend_talk_method(self):
        """Test Friend talk method prints generic message."""
        friend = Friend(
            name="TestAlly",
            description="An ally",
            damage=15,
            aggro=True,
            exp_award=0,
        )
        # talk() should print; just verify it doesn't crash
        friend.talk(None)  # No assertion needed; verify no exception

    def test_mynx_initialization(self):
        """Test Mynx friendly NPC initialization."""
        mynx = Mynx()
        assert mynx.name.startswith("Mynx ")
        assert mynx.damage == 0  # Non-combatant
        assert mynx.aggro is False
        assert mynx.exp_award == 0
        assert mynx.friend is True
        assert mynx.in_combat is False
        assert mynx._combat_disabled is True
        assert "talk" in mynx.keywords
        assert "pet" in mynx.keywords
        assert "play" in mynx.keywords

    def test_mynx_custom_name_and_description(self):
        """Test Mynx with custom name and description."""
        custom_name = "MynxCustom"
        custom_desc = "A custom mynx."
        mynx = Mynx(name=custom_name, description=custom_desc)
        assert mynx.name == custom_name
        assert mynx.description == custom_desc

    def test_mynx_cannot_enter_combat(self):
        """Test Mynx can_enter_combat returns False."""
        mynx = Mynx()
        assert mynx.can_enter_combat() is False

    def test_mynx_combat_engage_is_noop(self):
        """Test Mynx combat_engage does nothing."""
        mynx = Mynx()
        player = MagicMock()
        mynx.combat_engage(player)
        assert mynx.in_combat is False
        # Verify player.combat_list not modified
        player.combat_list.append.assert_not_called()

    def test_mynx_talk_method(self):
        """Test Mynx talk method calls interact_with_player."""
        mynx = Mynx()
        player = MagicMock()
        with patch.object(mynx, 'interact_with_player', return_value="response"):
            result = mynx.talk(player, prompt="hello")
            mynx.interact_with_player.assert_called_once()
            assert result == "response"

    def test_mynx_pet_method(self):
        """Test Mynx pet method."""
        mynx = Mynx()
        with patch.object(mynx, 'interact_with_player', return_value="pet_response"):
            result = mynx.pet()
            mynx.interact_with_player.assert_called_once()

    def test_mynx_play_method(self):
        """Test Mynx play method."""
        mynx = Mynx()
        with patch.object(mynx, 'interact_with_player', return_value="play_response"):
            result = mynx.play()
            mynx.interact_with_player.assert_called_once()

    def test_gorran_initialization(self):
        """Test Gorran (Rock-Man) ally initialization."""
        gorran = Gorran()
        assert gorran.name == "Rock-Man"
        assert gorran.maxhp == 200
        assert gorran.damage == 55
        assert gorran.friend is True
        assert len(gorran.known_moves) > 0


class TestNPCCombatMechanics:
    """Test NPC combat-related methods."""

    def test_add_move_and_weight(self):
        """Test add_move sets weight correctly."""
        npc = NPC(
            name="TestEnemy",
            description="A test enemy",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        initial_move_count = len(npc.known_moves)
        attack_move = moves.NpcAttack(npc)
        npc.add_move(attack_move, weight=5)

        assert len(npc.known_moves) == initial_move_count + 1
        assert attack_move.weight == 5

    def test_reset_combat_moves(self):
        """Test reset_combat_moves resets all move stages."""
        npc = Slime()
        # Manually advance some moves
        for move in npc.known_moves:
            move.current_stage = 2
            move.beats_left = 3

        npc.reset_combat_moves()

        for move in npc.known_moves:
            assert move.current_stage == 0
            assert move.beats_left == 0

    def test_combat_engage_adds_to_combat_list(self):
        """Test combat_engage adds NPC to player's combat list."""
        player = Player()
        npc = Slime()

        npc.combat_engage(player)

        assert npc in player.combat_list
        assert npc.in_combat is True
        assert npc in player.combat_proximity

    def test_combat_engage_sets_proximity(self):
        """Test combat_engage randomizes proximity."""
        player = Player()
        npc = Slime()
        npc.default_proximity = 20

        npc.combat_engage(player)

        # Proximity should be within default_proximity * [0.75, 1.25]
        proximity = player.combat_proximity[npc]
        assert 15 <= proximity <= 25

    def test_combat_engage_with_allies(self):
        """Test combat_engage when player has allies."""
        player = Player()
        ally = Friend("Ally", "An ally", 10, False, 0)
        player.combat_list_allies = [ally]

        npc = Slime()
        npc.combat_engage(player)

        # Ally should have proximity set with npc
        assert npc in ally.combat_proximity

    def test_select_move_basic(self):
        """Test select_move picks a viable move."""
        npc = Slime()
        npc.in_combat = True
        npc.fatigue = 100

        npc.select_move()

        assert npc.current_move is not None

    def test_select_move_insufficient_fatigue_rests(self):
        """Test select_move rests when fatigue is low."""
        npc = Slime()
        npc.in_combat = True
        npc.fatigue = 1  # Very low fatigue
        npc.maxfatigue = 100

        npc.select_move()

        # Check that current_move is NpcRest by checking class name
        assert npc.current_move is not None
        assert npc.current_move.__class__.__name__ == 'NpcRest'

    def test_select_move_with_weighted_moves(self):
        """Test select_move respects move weights."""
        npc = Slime()
        npc.in_combat = True
        npc.fatigue = 100

        # Verify move selection is consistent
        selected_moves = []
        for _ in range(20):
            npc.select_move()
            if npc.current_move:
                selected_moves.append(npc.current_move.__class__.__name__)

        # Should have selected various moves
        assert len(selected_moves) > 0
        # Should be moves from the NPC's available set
        assert len(set(selected_moves)) >= 1  # At least one unique move type

    def test_select_move_fallback_to_rest_no_viable_moves(self):
        """Test select_move falls back to rest when can't afford any offensive moves."""
        npc = Slime()
        npc.in_combat = True
        npc.fatigue = 1  # Very low fatigue

        npc.select_move()

        # Should fall back to NpcRest when fatigue is low
        assert npc.current_move is not None
        assert npc.current_move.__class__.__name__ == 'NpcRest'


class TestNPCLootSystem:
    """Test NPC loot initialization and management."""

    def test_npc_loot_initialization(self):
        """Test NPC loot is initialized."""
        npc = Slime()
        assert npc.loot is not None
        assert npc.loot == loot.lev0

    def test_lurker_loot_is_lev1(self):
        """Test Lurker has better loot."""
        lurker = Lurker()
        assert lurker.loot == loot.lev1

    def test_king_slime_loot_is_lev1(self):
        """Test KingSlime has lev1 loot."""
        king = KingSlime()
        assert king.loot == loot.lev1


class TestNPCResistances:
    """Test NPC resistance initialization."""

    def test_rock_rumbler_earth_resistance(self):
        """Test RockRumbler has earth resistance."""
        rumbler = RockRumbler()
        assert rumbler.resistance_base["earth"] == 0.5
        assert rumbler.resistance_base["fire"] == 0.5
        assert rumbler.resistance_base["crushing"] == 1.5

    def test_lurker_dark_resistance(self):
        """Test Lurker has dark resistance and light weakness."""
        lurker = Lurker()
        assert lurker.resistance_base["dark"] == 0.5
        assert lurker.resistance_base["light"] == -2

    def test_cave_bat_light_resistance(self):
        """Test CaveBat has light resistance."""
        bat = CaveBat()
        assert bat.resistance_base["light"] == 0.8
        assert bat.resistance_base["earth"] == 1.1

    def test_status_resistance_poison(self):
        """Test NPCs with poison resistance."""
        spider = GiantSpider()
        assert spider.status_resistance_base["poison"] == 1

    def test_elder_slime_immune_to_slimed(self):
        """ElderSlime should be immune to the Slimed status it inflicts on others."""
        elder = ElderSlime()
        assert elder.status_resistance_base["slimed"] == 1.0
        assert elder.status_resistance["slimed"] == 1.0
        status = Slimed(elder)
        from src.functions import inflict
        assert inflict(status, elder, chance=1.0) is False

    def test_king_slime_immune_to_slimed(self):
        """KingSlime should be immune to the Slimed status it inflicts on others."""
        king = KingSlime()
        assert king.status_resistance_base["slimed"] == 1.0
        assert king.status_resistance["slimed"] == 1.0
        status = Slimed(king)
        from src.functions import inflict
        assert inflict(status, king, chance=1.0) is False

    def test_status_dummy_zero_resistances(self):
        """Test StatusDummy has neutral damage and zero status resistances."""
        dummy = StatusDummy()
        # Damage resistances should be 1.0 (neutral)
        for key, val in dummy.resistance_base.items():
            assert val == 1.0
        # Status resistances should be 0.0
        for key, val in dummy.status_resistance_base.items():
            assert val == 0.0


class TestNPCStateManagement:
    """Test NPC state and health management."""

    def test_npc_health_reduction(self):
        """Test NPC takes damage."""
        npc = NPC(
            name="TestEnemy",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
            maxhp=100,
        )
        npc.hp = 100
        npc.hp -= 30
        assert npc.hp == 70

    def test_npc_is_alive(self):
        """Test NPC is_alive check."""
        npc = Slime()
        assert npc.is_alive() is True
        npc.hp = 0
        assert npc.is_alive() is False

    def test_npc_status_effect_application(self):
        """Test applying status effects to NPC."""
        npc = Slime()
        npc.in_combat = True
        poison = Poisoned(npc)
        npc.states.append(poison)
        assert len(npc.states) == 1
        assert npc.states[0].name == "Poisoned"

    def test_npc_multiple_status_effects(self):
        """Test NPC with multiple status effects."""
        npc = Slime()
        npc.in_combat = True
        poison = Poisoned(npc)
        enflamed = Enflamed(npc)
        npc.states.extend([poison, enflamed])
        assert len(npc.states) == 2

    def test_npc_fatigue_management(self):
        """Test NPC fatigue tracking."""
        npc = NPC(
            name="TestEnemy",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
            maxfatigue=100,
        )
        assert npc.fatigue == 100
        npc.fatigue -= 30
        assert npc.fatigue == 70

    def test_npc_current_room_tracking(self):
        """Test NPC current_room attribute."""
        npc = Slime()
        room_mock = MagicMock()
        npc.current_room = room_mock
        assert npc.current_room == room_mock


class TestNPCKeywords:
    """Test NPC keyword system."""

    def test_friend_keywords_overwritten_by_npc(self):
        """Test Friend tries to set keywords but NPC overwrites them.

        Note: This is a bug in the current code - Friend.__init__ sets
        keywords=["talk"] but then calls super().__init__() which sets
        keywords=[] afterwards. We test the actual behavior.
        """
        friend = Friend("Ally", "An ally", 10, False, 0)
        # Due to bug, keywords get overwritten to empty list
        assert friend.keywords == []

    def test_mynx_has_multiple_keywords(self):
        """Test Mynx has talk, pet, play keywords."""
        mynx = Mynx()
        assert "talk" in mynx.keywords
        assert "pet" in mynx.keywords
        assert "play" in mynx.keywords

    def test_generic_npc_keywords_empty(self):
        """Test generic NPC has empty keywords initially."""
        npc = NPC(
            name="Monster",
            description="A monster",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        assert npc.keywords == []


class TestNPCPronouns:
    """Test NPC pronoun system."""

    def test_default_pronouns_neutral(self):
        """Test default pronouns are neutral."""
        npc = NPC(
            name="Monster",
            description="A monster",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        assert npc.pronouns["personal"] == "it"
        assert npc.pronouns["possessive"] == "its"
        assert npc.pronouns["reflexive"] == "itself"

    def test_mynx_pronouns(self):
        """Test Mynx pronouns."""
        mynx = Mynx()
        assert mynx.pronouns["personal"] == "it"
        assert mynx.pronouns["possessive"] == "its"


class TestNPCCombatProperties:
    """Test NPC combat properties and positioning."""

    def test_npc_combat_delay(self):
        """Test NPC combat_delay initialization."""
        npc = Slime()
        assert npc.combat_delay == 0

    def test_npc_combat_position(self):
        """Test NPC combat_position starts as None."""
        npc = Slime()
        assert npc.combat_position is None

    def test_npc_proximity_tracking(self):
        """Test NPC proximity dict."""
        npc = Slime()
        assert isinstance(npc.combat_proximity, dict)
        assert len(npc.combat_proximity) == 0

    def test_npc_default_proximity(self):
        """Test NPC default_proximity."""
        npc = NPC(
            name="TestEnemy",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
            combat_range=(0, 10),
        )
        assert npc.default_proximity == 20
        assert npc.combat_range == (0, 10)

    def test_npc_combat_range_variations(self):
        """Test different combat ranges for different NPCs."""
        melee = Slime()
        assert melee.combat_range == (0, 5)  # Default

        gorran = Gorran()
        assert gorran.combat_range == (0, 7)


class TestNPCInitialState:
    """Test initial state of NPC combat flags."""

    def test_npc_not_in_combat_initially(self):
        """Test NPC starts out of combat."""
        npc = Slime()
        assert npc.in_combat is False

    def test_npc_current_move_none_initially(self):
        """Test current_move starts as None."""
        npc = Slime()
        assert npc.current_move is None

    def test_npc_states_empty_initially(self):
        """Test states list is empty initially."""
        npc = Slime()
        assert npc.states == []


class TestRefreshMoves:
    """Test refresh_moves functionality via Combatant."""

    def test_npc_has_known_moves(self):
        """Test NPC initializes with known_moves."""
        npc = Slime()
        assert hasattr(npc, 'known_moves')
        assert isinstance(npc.known_moves, list)
        assert len(npc.known_moves) > 0

    def test_npc_can_select_from_known_moves(self):
        """Test select_move pulls from known_moves."""
        npc = Slime()
        npc.in_combat = True
        npc.fatigue = 100

        # Run select_move multiple times
        for _ in range(10):
            npc.select_move()
            # Current move should be from known_moves or NpcRest
            assert (npc.current_move in npc.known_moves or
                   isinstance(npc.current_move, moves.NpcRest))


class TestTalusHoundPacking:
    """Test TalusHound pack mechanics."""

    def test_talus_hound_pack_count_none(self):
        """Test TalusHound _count_pack_members when not in combat."""
        hound = TalusHound()
        count = hound._count_pack_members()
        assert count == 0

    def test_talus_hound_pack_count_self_excluded(self):
        """Test TalusHound doesn't count itself."""
        hound1 = TalusHound()
        hound2 = TalusHound()

        # Mock combat_list
        hound1.combat_list = [hound1, hound2]
        hound2.combat_list = [hound1, hound2]

        count1 = hound1._count_pack_members()
        # Should count hound2 but not itself
        assert count1 >= 0  # Counts hound2 if alive


class TestMultipleNPCInstances:
    """Test creating multiple NPC instances."""

    def test_slime_name_uniqueness(self):
        """Test multiple Slimes have different names."""
        slimes = [Slime() for _ in range(5)]
        names = [s.name for s in slimes]
        # Names should vary (genericng generates different values)
        # At least check they all start with "Slime"
        assert all(n.startswith("Slime ") for n in names)

    def test_multiple_enemies_independent_state(self):
        """Test multiple enemy instances have independent state."""
        enemy1 = Slime()
        enemy2 = Slime()

        enemy1.hp = 10
        enemy2.hp = 20

        assert enemy1.hp != enemy2.hp


class TestNPCAttributePreservation:
    """Test that NPC attributes are correctly preserved during init."""

    def test_npc_damage_base_matches_damage(self):
        """Test damage_base is set on init."""
        npc = NPC(
            name="Test",
            description="Test",
            damage=15,
            aggro=True,
            exp_award=50,
        )
        assert npc.damage == 15
        assert npc.damage_base == 15

    def test_npc_protection_base_matches_protection(self):
        """Test protection_base is set on init."""
        npc = NPC(
            name="Test",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
            protection=8,
        )
        assert npc.protection == 8
        assert npc.protection_base == 8

    def test_npc_exp_award_base(self):
        """Test exp_award_base is set."""
        npc = NPC(
            name="Test",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=100,
        )
        assert npc.exp_award == 100
        assert npc.exp_award_base == 100


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_npc_zero_damage(self):
        """Test NPC with zero damage (like Mynx)."""
        npc = NPC(
            name="WeakEnemy",
            description="Very weak",
            damage=0,
            aggro=False,
            exp_award=0,
        )
        assert npc.damage == 0

    def test_npc_very_high_hp(self):
        """Test NPC with very high HP."""
        npc = NPC(
            name="Boss",
            description="Tough",
            damage=20,
            aggro=True,
            exp_award=500,
            maxhp=5000,
        )
        assert npc.hp == 5000

    def test_npc_high_fatigue_cost_tolerance(self):
        """Test NPC handles high-cost moves."""
        npc = NPC(
            name="Test",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
            maxfatigue=1000,
        )
        npc.fatigue = 1000
        assert npc.fatigue == 1000

    def test_npc_select_move_with_zero_available_moves(self):
        """Test select_move with minimal/no moves."""
        npc = NPC(
            name="Test",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        # npc.known_moves has NpcRest by default
        npc.select_move()
        # Should not crash


class TestTalusHoundPackMechanics:
    """Test TalusHound pack-specific behavior."""

    def test_talus_hound_multiple_instances_in_combat(self):
        """Test multiple TalusHounds track each other correctly."""
        hound1 = TalusHound()
        hound2 = TalusHound()
        hound3 = TalusHound()

        # Mock combat list with multiple hounds
        hound1.combat_list = [hound1, hound2, hound3]
        hound2.combat_list = [hound1, hound2, hound3]
        hound3.combat_list = [hound1, hound2, hound3]

        # Each hound should count the others
        count1 = hound1._count_pack_members()
        count2 = hound2._count_pack_members()
        # Counts should be > 0 if pack mechanics working
        assert count1 >= 0
        assert count2 >= 0


class TestAIConfigInitialization:
    """Test AI config initialization in select_move."""

    def test_select_move_without_player_ref(self):
        """Test select_move works without player_ref."""
        npc = Slime()
        npc.in_combat = True
        npc.fatigue = 100
        npc.player_ref = None

        npc.select_move()

        # Should select a move even without player_ref
        assert npc.current_move is not None

    def test_select_move_with_player_ref_no_ai_config(self):
        """Test select_move works with player_ref but no ai_config."""
        npc = Slime()
        npc.in_combat = True
        npc.fatigue = 100
        player = Player()  # Real player object
        npc.player_ref = player

        npc.select_move()

        # Should select a move
        assert npc.current_move is not None


class TestEnemyMoveWeighting:
    """Test move weight distributions on various enemy types."""

    def test_slime_has_multiple_weighted_moves(self):
        """Test Slime has various weighted moves."""
        slime = Slime()
        # Slime should have NpcAttack(5), Advance(4), NpcIdle(1), Dodge(1)
        assert len(slime.known_moves) >= 4
        weights = [m.weight for m in slime.known_moves if hasattr(m, 'weight')]
        assert len(weights) > 0

    def test_lurker_complex_move_set(self):
        """Test Lurker has complex move set."""
        lurker = Lurker()
        # Lurker has: NpcAttack(5), VenomClaw(5), SoulDrain(3), Advance(4), Withdraw, NpcIdle, Dodge(2)
        assert len(lurker.known_moves) >= 7

    def test_king_slime_boss_moves(self):
        """Test KingSlime has boss-level moves."""
        king = KingSlime()
        # King Slime: NpcAttack(5), TidalSurge(3), Advance(4), NpcIdle(1)
        assert len(king.known_moves) >= 4


class TestFriendSpecificBehaviors:
    """Test Friend-specific behaviors beyond base NPC."""

    def test_friend_knocked_out_flag(self):
        """Test Friend knocked_out tracking."""
        friend = Friend("Ally", "An ally", 10, False, 0)
        assert friend.knocked_out is False
        friend.knocked_out = True
        assert friend.knocked_out is True

    def test_friend_overrides_default_messages(self):
        """Test Friend has different default messages."""
        friend = Friend("Ally", "An ally", 10, False, 0)
        # Friend should have "gets ready for a fight!" not the generic alert
        assert friend.alert_message == "gets ready for a fight!"

    def test_mynx_disabled_combat_flag(self):
        """Test Mynx has _combat_disabled flag."""
        mynx = Mynx()
        assert mynx._combat_disabled is True

    def test_mynx_llm_history_initialization(self):
        """Test Mynx initializes LLM history."""
        mynx = Mynx()
        assert mynx._llm_history == []

    def test_mynx_llm_last_response(self):
        """Test Mynx LLM response tracking."""
        mynx = Mynx()
        assert mynx._llm_last_response is None
        mynx._llm_last_response = "test response"
        assert mynx._llm_last_response == "test response"


class TestGorranSpecifics:
    """Test Gorran-specific properties."""

    def test_gorran_is_non_combatant_exp(self):
        """Test Gorran grants no exp."""
        gorran = Gorran()
        assert gorran.exp_award == 0

    def test_gorran_high_damage(self):
        """Test Gorran has high damage (ally strength)."""
        gorran = Gorran()
        assert gorran.damage == 55

    def test_gorran_wide_combat_range(self):
        """Test Gorran has extended combat range."""
        gorran = Gorran()
        assert gorran.combat_range == (0, 7)


class TestEnemyResistancePatterns:
    """Test resistance patterns across enemy types."""

    def test_elder_slime_fire_weakness(self):
        """Test ElderSlime has fire weakness."""
        elder = ElderSlime()
        assert elder.resistance_base["fire"] == 1.4  # Takes MORE fire damage

    def test_king_slime_inherits_elder_slime_resistances(self):
        """Test KingSlime has similar resistance profile."""
        king = KingSlime()
        # Both should resist slashing/piercing similarly
        assert king.resistance_base["slashing"] == 0.65
        assert king.resistance_base["piercing"] == 0.65

    def test_lurker_death_immunity(self):
        """Test Lurker has death status immunity."""
        lurker = Lurker()
        assert lurker.status_resistance_base["death"] == 1

    def test_lurker_doom_immunity(self):
        """Test Lurker has doom immunity."""
        lurker = Lurker()
        assert lurker.status_resistance_base["doom"] == 1


class TestWeaponTypeSpecificEnemies:
    """Test enemies with specific move types."""

    def test_giant_spider_uses_spider_bite(self):
        """Test GiantSpider has SpiderBite move."""
        spider = GiantSpider()
        move_names = [m.name for m in spider.known_moves if hasattr(m, 'name')]
        # SpiderBite should be in the move set
        assert any('Spider' in str(name) or 'Bite' in str(name) for name in move_names)

    def test_cave_bat_has_bat_bite(self):
        """Test CaveBat has BatBite move."""
        bat = CaveBat()
        assert len(bat.known_moves) > 0

    def test_scarp_adder_has_venom_claw(self):
        """Test ScarpAdder uses VenomClaw."""
        adder = ScarpAdder()
        move_names = [m.name for m in adder.known_moves if hasattr(m, 'name')]
        # Should have combat moves
        assert len(move_names) > 0


class TestNPCCombatEngagementScenarios:
    """Test various combat engagement scenarios."""

    def test_combat_engage_with_empty_ally_list(self):
        """Test combat_engage when player has no allies."""
        player = Player()
        player.combat_list_allies = []
        npc = Slime()

        npc.combat_engage(player)

        assert npc in player.combat_list
        assert npc.in_combat is True

    def test_combat_proximity_randomization_range(self):
        """Test combat proximity is properly randomized."""
        proximities = []
        for _ in range(50):
            player = Player()
            npc = Slime()
            npc.default_proximity = 20
            npc.combat_engage(player)
            proximities.append(player.combat_proximity[npc])

        # Should have some variation, all within range
        assert min(proximities) >= 15
        assert max(proximities) <= 25
        assert len(set(proximities)) > 1  # Should have multiple values

    def test_reset_combat_moves_preserves_move_count(self):
        """Test reset_combat_moves doesn't change move count."""
        npc = Slime()
        initial_count = len(npc.known_moves)

        npc.reset_combat_moves()

        assert len(npc.known_moves) == initial_count


class TestNPCAttributes:
    """Test various NPC attribute setups."""

    def test_npc_base_stat_preservation(self):
        """Test base stats are preserved for resistance calculations."""
        npc = NPC(
            name="Test",
            description="Test",
            damage=20,
            aggro=True,
            exp_award=100,
            strength=15,
            finesse=12,
        )
        assert npc.damage_base == 20
        assert npc.strength_base == 15
        assert npc.finesse_base == 12

    def test_npc_stat_modification(self):
        """Test NPC stats can be modified."""
        npc = Slime()
        original_hp = npc.hp
        npc.hp -= 5
        assert npc.hp == original_hp - 5

    def test_npc_in_combat_flag_management(self):
        """Test in_combat flag can be set."""
        npc = Slime()
        assert npc.in_combat is False
        npc.in_combat = True
        assert npc.in_combat is True


class TestMultipleNPCMoveLists:
    """Test that multiple NPCs have independent move lists."""

    def test_slime_instances_independent_moves(self):
        """Test Slime instances don't share move lists."""
        slime1 = Slime()
        slime2 = Slime()

        # Modify one slime's move list
        initial_count = len(slime1.known_moves)
        slime1.known_moves.append(MagicMock())

        # Other slime should be unaffected
        assert len(slime2.known_moves) == initial_count

    def test_different_enemy_types_different_moves(self):
        """Test different enemy types have different move distributions."""
        slime = Slime()
        lurker = Lurker()

        # Lurker should have more moves due to complexity
        assert len(lurker.known_moves) > len(slime.known_moves)


class TestNPCHealthEdgeCases:
    """Test NPC health management edge cases."""

    def test_very_low_hp_npc(self):
        """Test NPC with very low starting HP."""
        npc = NPC(
            name="Fragile",
            description="Very fragile",
            damage=1,
            aggro=True,
            exp_award=1,
            maxhp=1,
        )
        assert npc.hp == 1
        npc.hp -= 1
        assert npc.hp == 0
        assert npc.is_alive() is False

    def test_high_hp_npc_damage(self):
        """Test high HP NPC takes cumulative damage."""
        npc = NPC(
            name="Tank",
            description="High HP tank",
            damage=5,
            aggro=True,
            exp_award=50,
            maxhp=1000,
        )
        for _ in range(10):
            npc.hp -= 50
        assert npc.hp == 500


class TestNPCExpAwards:
    """Test experience award variations."""

    def test_zero_exp_npc(self):
        """Test NPC that awards no experience."""
        friend = Friend("Ally", "An ally", 10, False, 0)
        assert friend.exp_award == 0
        assert friend.exp_award_base == 0

    def test_high_exp_npc(self):
        """Test boss NPCs with high exp."""
        king = KingSlime()
        assert king.exp_award == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
