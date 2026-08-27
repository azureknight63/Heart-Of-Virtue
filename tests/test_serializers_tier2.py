"""
SERIALIZATION TIER 2: Comprehensive tests for every serializer and combat adapter.

Target: 70%+ coverage on src/api/serializers and src/api/combat_adapter.
"""

import pytest
import uuid
import json
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from typing import Any, Dict, List
import src.items as items

from src.api.combat_adapter import (
    ApiCombatAdapter,
    CombatOutputCapture,
    _strip_combatant_prefix,
)
from src.api.serializers.combat import CombatStateSerializer, CombatantSerializer
from src.api.serializers.npc_serializer import NPCSerializer
from src.api.serializers.inventory import InventorySerializer, EquipmentSerializer
from src.api.serializers.shop_serializer import ShopSerializer
from src.api.serializers.event_serializer import EventSerializer
from src.api.serializers.item_serializer import ItemSerializer


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def live_player(make_player):
    """A **real** ``Player`` in combat.

    ``CombatantSerializer`` branches on ``isinstance(combatant, Player)``, so a
    ``Mock`` with ``__class__.__name__ = "Player"`` is serialized as an *enemy*
    -- which is exactly why the serializer tests below were skipped as an
    "implementation mismatch" instead of being fixed.
    """
    player = make_player(weapon="Sword", hp=80, maxhp=100)
    return player


@pytest.fixture
def live_goblin(make_npc):
    """A real ``NPC`` standing in for an enemy combatant."""
    return make_npc(name="Goblin", hp=30, maxhp=40, damage=6)


@pytest.fixture
def live_encounter(live_player, live_goblin, engage, place, repair_proximity):
    """Real player + real enemy, positioned three feet apart on the real grid."""
    engage(live_player, [live_goblin])
    place(live_player, 10, 10)
    place(live_goblin, 13, 10)
    repair_proximity([live_player, live_goblin])
    return live_player, live_goblin


class _AnimEntity:
    """A combatant stand-in carrying a real ``_pending_animation`` dict.

    ``CombatOutputCapture.write`` both mutates and ``delattr``s that attribute,
    neither of which a bare ``Mock`` models honestly: a Mock answers
    ``hasattr`` for an attribute that was never set, and swallows the delete.
    """

    def __init__(self, move_name="Attack"):
        self._pending_animation = {"outcome": None, "move_name": move_name}


@pytest.fixture
def mock_player():
    """Create a mock player object for testing."""
    player = Mock()
    player.name = "Jean Claire"
    player.hp = 80
    player.maxhp = 100
    player.fatigue = 60
    player.maxfatigue = 100
    player.heat = 1.0
    player.level = 5
    player.strength_base = 12
    player.finesse_base = 14
    player.speed_base = 11
    player.endurance_base = 13
    player.charisma_base = 10
    player.intelligence_base = 9
    player.exp = 500
    player.exp_to_level = 1000
    player.pending_attribute_points = 2
    player.speed = 10
    player.id = "player"
    player.__class__.__name__ = "Player"
    player.in_combat = True
    player.combat_beat = 1
    player.combat_list = []
    player.combat_list_allies = [player]
    player.known_moves = []
    player.inventory = []
    player.current_room = Mock()
    player.current_room.npcs_here = []
    player.current_room.items_here = []
    player.current_room.description = "Test room"
    player.combat_proximity = {}
    player.combat_adapter_state = {}
    player.combat_log = []
    player.is_alive = Mock(return_value=True)
    player.cycle_states = Mock()
    player.eq_weapon = None
    player.equipment = {}
    player.status_effects = []
    player.known_states = {}
    player.friend = False
    player.battle_symbol = "J"
    player.selected_profile_traits = ["Trait1", "Trait2"]
    player.experience_breakdown = {"Weapons": 10, "Spellcraft": 5}
    player.current_move = None
    player.last_move_name = None
    player.last_move_target_id = None
    player.last_move_summary = ""
    player.suggested_moves = []
    player.suggestions_loading = False
    player.combat_exp = {"Weapons": 0}
    player.gain_exp = Mock(return_value=[])
    player.reputation = {}
    return player


@pytest.fixture
def mock_npc():
    """Create a mock NPC object for testing."""
    npc = Mock()
    npc.name = "Goblin"
    npc.hp = 30
    npc.maxhp = 40
    npc.fatigue = 20
    npc.maxfatigue = 30
    npc.heat = 1.0
    npc.level = 2
    npc.speed = 6
    npc.id = f"enemy_{id(npc)}"
    npc.__class__.__name__ = "NPC"
    npc.friend = False
    npc.in_combat = True
    npc.known_moves = []
    npc.inventory = []
    npc.status_effects = []
    npc.is_alive = Mock(return_value=True)
    npc.die = Mock()
    npc.cycle_states = Mock()
    npc.battle_symbol = "G"
    npc.alert_message = "appears!"
    npc.combat_proximity = {}
    npc.default_proximity = 10
    npc.position = (5, 5)
    npc.combat_position = (5, 5)
    npc.current_move = None
    npc.target = None
    npc.combat_delay = 0
    npc.select_move = Mock()
    npc.equipment = {}
    npc.known_states = {}
    return npc


@pytest.fixture
def mock_move():
    """Create a mock move object for testing."""
    move = Mock()
    move.name = "Attack"
    move.category = "Attack"
    move.description = "A basic melee attack"
    move.fatigue_cost = 10
    move.targeted = True
    move.passive = False
    move.current_stage = 0
    move.beats_left = 0
    move.viable = Mock(return_value=True)
    move.cast = Mock()
    move.advance = Mock()
    move.stage_beat = [0, 1, 0, 2]
    move.mvrange = (0, 5)
    move.user = None
    move.target = None
    move.instant = False
    move.web_animation = None
    move.verbose_targeting = False
    move.accepts_ally_target = False
    return move


@pytest.fixture
def mock_item():
    """Create a mock item object."""
    item = Mock()
    item.name = "Iron Sword"
    item.type = "Weapon"
    item.maintype = "Weapon"
    item.subtype = "Sword"
    item.weight = 5.5
    item.value = 100
    item.description = "A sturdy iron sword"
    item.count = 1
    item._enchantment_count = 0
    item.use = Mock()
    return item


@pytest.fixture
def adapter_setup(mock_player):
    """Set up a combat adapter with a player."""
    adapter = ApiCombatAdapter(mock_player, session_id="test_session_123")
    return adapter


# ============================================================================
# TEST: CombatOutputCapture
# ============================================================================


class TestCombatOutputCapture:
    """Test output capture and log entry creation."""

    def test_capture_basic_text(self):
        """Test capturing basic text output."""
        capture = CombatOutputCapture()
        capture.write("Player attacks for 10 damage!")

        logs = capture.get_log()
        assert len(logs) == 1
        assert logs[0]["message"] == "Player attacks for 10 damage!"
        assert logs[0]["type"] == "combat"

    def test_capture_strips_ansi(self):
        """Test ANSI codes are stripped from captured output."""
        capture = CombatOutputCapture()
        capture.write("\x1B[1;32mGreen Text\x1B[0m")

        logs = capture.get_log()
        assert len(logs) == 1
        assert logs[0]["message"] == "Green Text"

    def test_capture_skips_debug_lines(self):
        """Test that DEBUG lines are skipped."""
        capture = CombatOutputCapture()
        capture.write("DEBUG: Some debug info")

        logs = capture.get_log()
        assert len(logs) == 0

    def test_capture_skips_animation_errors(self):
        """Test that animation errors are skipped."""
        capture = CombatOutputCapture()
        capture.write("Animation not found: test_anim")

        logs = capture.get_log()
        assert len(logs) == 0

    @pytest.mark.parametrize(
        "text, outcome",
        [
            ("Goblin is struck for 15 damage!", "hit"),
            ("Goblin just missed!", "miss"),
            ("Jean missed!", "miss"),
            ("Attack parried!", "parry"),
        ],
    )
    def test_capture_attaches_the_outcome_to_the_log_entry(self, text, outcome):
        """An impact line stamps the outcome onto the entry and consumes the pending anim.

        These three cases were skipped as a "Mock setup issue". The real problem
        was the assertion: ``write()`` calls ``delattr(entity,
        "_pending_animation")`` once it fires, so reading
        ``player._pending_animation`` afterwards can never see the outcome. The
        outcome travels out on the log entry's ``animation_data``, which is what
        the client actually consumes -- so that is what this now asserts.
        """
        entity = _AnimEntity(move_name="Attack")
        capture = CombatOutputCapture()
        capture.player = entity
        capture.active_entity = entity

        capture.write(text)

        (entry,) = capture.get_log()
        assert entry["message"] == text
        assert entry["trigger_animation"] is True
        assert entry["animation_data"] == {"outcome": outcome, "move_name": "Attack"}
        assert not hasattr(entity, "_pending_animation"), (
            "the pending animation must be consumed so it fires exactly once"
        )

    def test_capture_fires_the_animation_only_once(self):
        """A second impact line with no fresh pending animation must not re-trigger."""
        entity = _AnimEntity(move_name="Attack")
        capture = CombatOutputCapture()
        capture.active_entity = entity

        capture.write("Goblin is struck for 15 damage!")
        capture.write("Goblin is struck for 3 damage!")

        first, second = capture.get_log()
        assert first["trigger_animation"] is True
        assert "trigger_animation" not in second
        assert "animation_data" not in second

    def test_capture_non_impact_text_leaves_the_pending_animation_alone(self):
        entity = _AnimEntity(move_name="Attack")
        capture = CombatOutputCapture()
        capture.active_entity = entity

        capture.write("Jean winds up for a strike...")

        (entry,) = capture.get_log()
        assert "trigger_animation" not in entry
        assert entity._pending_animation == {"outcome": None, "move_name": "Attack"}

    def test_capture_prefers_active_entity_over_player(self):
        """Impact text must never be misattributed to a different combatant."""
        player = _AnimEntity(move_name="Attack")
        npc = _AnimEntity(move_name="NPC_Attack")
        capture = CombatOutputCapture(player)
        capture.active_entity = npc

        capture.write("Jean is struck for 8 damage!")

        (entry,) = capture.get_log()
        assert entry["animation_data"]["move_name"] == "NPC_Attack"
        assert player._pending_animation["outcome"] is None, "player must be untouched"

    def test_capture_empty_text_ignored(self):
        """Test that empty or whitespace-only text is ignored."""
        capture = CombatOutputCapture()
        capture.write("")
        capture.write("   ")
        capture.write("\n")

        logs = capture.get_log()
        assert len(logs) == 0

    def test_capture_clear(self):
        """Test clearing the capture log."""
        capture = CombatOutputCapture()
        capture.write("First message")
        capture.write("Second message")

        assert len(capture.get_log()) == 2

        capture.clear()

        assert len(capture.get_log()) == 0

    def test_capture_flush_noop(self):
        """Test flush() is a no-op (required for file-like interface)."""
        capture = CombatOutputCapture()
        capture.write("Test message")
        capture.flush()

        logs = capture.get_log()
        assert len(logs) == 1


# ============================================================================
# TEST: _strip_combatant_prefix Helper
# ============================================================================


class TestStripCombatantPrefix:
    """Test the combatant ID prefix stripper."""

    def test_strip_enemy_prefix(self):
        """Test stripping enemy_ prefix."""
        result = _strip_combatant_prefix("enemy_12345")
        assert result == "12345"

    def test_strip_ally_prefix(self):
        """Test stripping ally_ prefix."""
        result = _strip_combatant_prefix("ally_67890")
        assert result == "67890"

    def test_no_prefix_unchanged(self):
        """Test that IDs without prefix are returned unchanged."""
        result = _strip_combatant_prefix("player")
        assert result == "player"

    def test_empty_string(self):
        """Test empty string."""
        result = _strip_combatant_prefix("")
        assert result == ""


# ============================================================================
# TEST: ApiCombatAdapter - Initialization & Properties
# ============================================================================


class TestApiCombatAdapterInit:
    """Test combat adapter initialization."""

    def test_adapter_creates_with_player(self, mock_player):
        """Test adapter initializes with a player."""
        adapter = ApiCombatAdapter(mock_player)

        assert adapter.player == mock_player
        assert adapter.session_id is None
        assert adapter.output_capture is not None
        assert adapter.combat_grid_size == (13, 13)

    def test_adapter_creates_with_session_id(self, mock_player):
        """Test adapter initializes with session ID."""
        adapter = ApiCombatAdapter(mock_player, session_id="test_123")

        assert adapter.session_id == "test_123"

    def test_adapter_creates_state_dict(self, live_player):
        """A player with no ``combat_adapter_state`` gets the full default dict.

        Was skipped as a "Mock setup issue"; the real problem is that the
        adapter guards on ``hasattr``, and a ``Mock`` answers ``hasattr`` for
        every name, so the branch could never be reached with a mock at all.
        A real ``Player`` genuinely lacks the attribute until an adapter runs.
        """
        assert not hasattr(live_player, "combat_adapter_state")

        ApiCombatAdapter(live_player)

        assert live_player.combat_adapter_state == {
            "awaiting_input": False,
            "input_type": None,
            "pending_move_index": None,
            "available_options": [],
        }

    def test_adapter_preserves_existing_state(self, mock_player):
        """Test adapter preserves existing combat_adapter_state."""
        mock_player.combat_adapter_state = {"custom_key": "custom_value"}

        adapter = ApiCombatAdapter(mock_player)

        assert mock_player.combat_adapter_state["custom_key"] == "custom_value"

    def test_adapter_properties_awaiting_input(self, adapter_setup):
        """Test awaiting_input property."""
        adapter = adapter_setup

        assert adapter.awaiting_input is False
        adapter.awaiting_input = True
        assert adapter.awaiting_input is True

    def test_adapter_properties_input_type(self, adapter_setup):
        """Test input_type property."""
        adapter = adapter_setup

        assert adapter.input_type is None
        adapter.input_type = "move_selection"
        assert adapter.input_type == "move_selection"

    def test_adapter_properties_pending_move_index(self, adapter_setup):
        """Test pending_move_index property."""
        adapter = adapter_setup

        assert adapter.pending_move_index is None
        adapter.pending_move_index = 2
        assert adapter.pending_move_index == 2

    def test_adapter_properties_available_options(self, adapter_setup):
        """Test available_options property."""
        adapter = adapter_setup

        assert adapter.available_options == []
        options = [{"name": "Move1"}, {"name": "Move2"}]
        adapter.available_options = options
        assert adapter.available_options == options


# ============================================================================
# TEST: ApiCombatAdapter - Add Log Entry
# ============================================================================


class TestAddLogEntry:
    """Test the _add_log_entry method."""

    def test_add_basic_log_entry(self, adapter_setup, mock_player):
        """Test adding a basic log entry."""
        adapter = adapter_setup

        adapter._add_log_entry(1, "Test message")

        logs = mock_player.combat_log
        assert len(logs) == 1
        assert logs[0]["message"] == "Test message"
        assert logs[0]["round"] == 1
        assert logs[0]["type"] == "combat"

    def test_add_log_entry_with_animation(self, adapter_setup, mock_player):
        """Test adding log entry with animation data."""
        adapter = adapter_setup
        anim_data = {
            "type": "attack",
            "source_id": "player",
            "target_id": "enemy_123",
            "outcome": "hit",
            "move_name": "Attack"
        }

        adapter._add_log_entry(1, "Attack lands!", animation_data=anim_data)

        logs = mock_player.combat_log
        assert len(logs) == 1
        assert logs[0]["animation"] == anim_data

    def test_deduplication_same_round(self, adapter_setup, mock_player):
        """Test that duplicate entries in same round are deduplicated."""
        adapter = adapter_setup

        adapter._add_log_entry(1, "Duplicate message")
        adapter._add_log_entry(1, "Duplicate message")

        logs = mock_player.combat_log
        assert len(logs) == 1

    def test_same_message_different_rounds_allowed(self, adapter_setup, mock_player):
        """Test that same message in different rounds is allowed."""
        adapter = adapter_setup

        adapter._add_log_entry(1, "Same message")
        adapter._add_log_entry(2, "Same message")

        logs = mock_player.combat_log
        assert len(logs) == 2

    def test_log_entry_includes_beat_index(self, adapter_setup, mock_player):
        """Test that beat_index is included in log entry."""
        adapter = adapter_setup
        adapter.current_beat_state_index = 5

        adapter._add_log_entry(1, "Message", beat_index=5)

        logs = mock_player.combat_log
        assert logs[0]["beat_index"] == 5

    def test_log_entry_custom_timestamp(self, adapter_setup, mock_player):
        """Test that custom timestamp can be provided."""
        adapter = adapter_setup
        custom_ts = "12:34:56"

        adapter._add_log_entry(1, "Message", timestamp=custom_ts)

        logs = mock_player.combat_log
        assert logs[0]["timestamp"] == custom_ts


# ============================================================================
# TEST: CombatStateSerializer
# ============================================================================


class TestCombatStateSerializer:
    """Test combat state serialization."""

    def test_serialize_empty_combat_state(self, live_player):
        """No enemies: both rosters are empty and ``combatants`` holds only Jean."""
        result = CombatStateSerializer.serialize_combat_state(live_player, [])

        assert result["status"] == "active"
        assert result["round"] == 1
        assert result["current_turn_index"] == 0
        assert result["player"]["name"] == live_player.name
        assert result["player"]["id"] == "player"
        assert result["enemies"] == []
        assert result["allies"] == []
        assert [c["id"] for c in result["combatants"]] == ["player"]

    def test_serialize_combat_state_with_enemies(self, live_encounter):
        """Enemies appear in ``enemies`` and are appended after the player."""
        player, goblin = live_encounter

        result = CombatStateSerializer.serialize_combat_state(player, [goblin])

        assert result["status"] == "active"
        assert [e["name"] for e in result["enemies"]] == ["Goblin"]
        assert result["enemies"][0]["id"] == f"enemy_{id(goblin)}"
        assert result["enemies"][0]["type"] == "npc"
        # Distance is measured against the player reference, not invented.
        assert result["enemies"][0]["distance"] == 3
        assert [c["id"] for c in result["combatants"]] == [
            "player",
            f"enemy_{id(goblin)}",
        ]

    def test_serialize_combat_state_with_allies(self, live_player, live_goblin):
        """A ``friend`` NPC lands in ``allies`` and carries an ``ally_`` wire id."""
        live_goblin.friend = True

        result = CombatStateSerializer.serialize_combat_state(
            live_player, [], allies=[live_goblin]
        )

        assert [a["name"] for a in result["allies"]] == ["Goblin"]
        assert result["allies"][0]["id"] == f"ally_{id(live_goblin)}"
        assert result["enemies"] == []
        # combatants = player, then allies, then enemies -- order is the contract.
        assert [c["id"] for c in result["combatants"]] == [
            "player",
            f"ally_{id(live_goblin)}",
        ]

    def test_serialize_battle_summary_victory(self, mock_player, mock_npc):
        """Test battle summary for victory."""
        mock_npc.is_alive = Mock(return_value=False)
        mock_npc.exp_reward = 100

        result = CombatStateSerializer.serialize_battle_summary(
            mock_player, [mock_npc], victory=True
        )

        assert result["status"] == "victory"

    def test_serialize_battle_summary_defeat(self, mock_player, mock_npc):
        """Test battle summary for defeat."""
        result = CombatStateSerializer.serialize_battle_summary(
            mock_player, [mock_npc], victory=False
        )

        assert result["status"] == "defeat"
        assert result["experience_gained"] == 0

    def test_get_consumables_from_inventory(self, mock_player, mock_item):
        """Test extracting consumables from player inventory."""
        mock_player.inventory = [mock_item]

        result = CombatStateSerializer._get_consumables(mock_player)

        assert len(result) == 1
        assert result[0]["name"] == "Iron Sword"
        assert result[0]["qty"] == 1

    def test_get_consumables_empty_inventory(self, mock_player):
        """Test getting consumables from empty inventory."""
        mock_player.inventory = []

        result = CombatStateSerializer._get_consumables(mock_player)

        assert result == []


# ============================================================================
# TEST: CombatantSerializer
# ============================================================================


class TestCombatantSerializer:
    """Test combatant serialization."""

    def test_serialize_player(self, live_player):
        """The player's wire id is the literal string ``player``."""
        result = CombatantSerializer.serialize_combatant(live_player)

        assert result["id"] == "player"
        assert result["type"] == "player"
        assert result["name"] == live_player.name
        assert result["health"] == {"current": 80, "max": 100}
        assert result["hp"] == 80 and result["max_hp"] == 100
        assert result["heat"] == live_player.heat

    def test_serialize_enemy_npc(self, live_goblin):
        result = CombatantSerializer.serialize_combatant(live_goblin)

        assert result["type"] == "npc"
        assert result["name"] == "Goblin"
        assert result["id"] == f"enemy_{id(live_goblin)}"
        assert result["health"] == {"current": 30, "max": 40}

    def test_serialize_ally_npc(self, live_goblin):
        """``friend`` is what flips the id prefix -- nothing else changes."""
        enemy_id = CombatantSerializer.serialize_combatant(live_goblin)["id"]
        live_goblin.friend = True

        result = CombatantSerializer.serialize_combatant(live_goblin)

        assert result["id"] == f"ally_{id(live_goblin)}"
        assert result["id"] != enemy_id
        assert result["type"] == "npc", "allies are still NPCs, not players"

    def test_serialize_combatant_with_distance(self, live_encounter, place,
                                               repair_proximity):
        """``distance`` is computed from real grid coordinates, not stubbed."""
        player, goblin = live_encounter

        assert CombatantSerializer.serialize_combatant(
            goblin, reference=player
        )["distance"] == 3

        place(goblin, 20, 10)
        repair_proximity([player, goblin])
        assert CombatantSerializer.serialize_combatant(
            goblin, reference=player
        )["distance"] == 10

    def test_serialize_status_effects(self, live_player):
        """Real ``State`` objects are serialized with their name and beats left.

        ``description`` is the player-facing prose the status panel shows;
        ``tactical_mechanics`` is the engine's terse statement of the modifiers
        and tick interval it actually applies, which the combat LLM prompt
        reads (see ai/combat_strategist.py). Both are taken off the state
        rather than restated here, because restating them is precisely the
        drift tests/test_states_tactical_mechanics.py exists to prevent.
        """
        from src.states import Poisoned

        poison = Poisoned(live_player)
        poison.beats_left = 5
        live_player.states = [poison]

        result = CombatantSerializer.serialize_combatant(live_player)

        assert result["status_effects"] == [
            {
                "name": "Poisoned",
                "type": "ailment",
                "description": poison.description,
                "tactical_mechanics": poison.tactical_mechanics,
                "severity": "severe",
                "beats_left": 5,
            }
        ]
        # Not vacuous: the state really does declare one, and it really does
        # quote the interval effect() runs at.
        assert "every 5 beats" in poison.tactical_mechanics

    def test_serialize_equipment(self, live_player):
        """Equipment mirrors the real equipped weapon, not a placeholder."""
        result = CombatantSerializer.serialize_combatant(live_player)

        assert result["equipment"]["weapon"] == {
            "name": live_player.eq_weapon.name,
            "damage": live_player.eq_weapon.damage,
            "damage_type": items.get_base_damage_type(live_player.eq_weapon),
        }
        assert result["stats"]["damage"] == live_player.eq_weapon.damage


# ============================================================================
# TEST: NPCSerializer
# ============================================================================


class TestNPCSerializer:
    """Test NPC serialization."""

    def test_serialize_npc_basic(self, live_goblin):
        """The wire keys are ``health``/``max_health`` -- not ``hp``/``maxhp``.

        The previous version of this test called ``NPCSerializer.serialize_npc``
        (no such method; it is ``serialize``) and asserted ``"hp" in result``.
        Both were wrong, and the skip marker hid it.
        """
        result = NPCSerializer.serialize(live_goblin)

        assert result["name"] == "Goblin"
        assert result["type"] == "NPC"
        assert result["level"] == 1, "NPC has no level attribute; 1 is the default"
        assert result["health"] == 30
        assert result["max_health"] == 40
        assert result["is_hostile"] is True
        assert "attack" in result["keywords"]
        assert "hp" not in result and "maxhp" not in result

    def test_serialize_npc_friendly_is_not_hostile(self, live_goblin):
        live_goblin.friend = True
        assert NPCSerializer.serialize(live_goblin)["is_hostile"] is False

    def test_serialize_npc_list_preserves_order(self, make_npc):
        first = make_npc(name="Alpha")
        second = make_npc(name="Beta")

        result = NPCSerializer.serialize_list([first, second])

        assert [n["name"] for n in result] == ["Alpha", "Beta"]


# ============================================================================
# TEST: CombatAdapter - Move Execution
# ============================================================================


class TestMoveExecution:
    """Test move execution in combat adapter."""

    def test_handle_move_selection_valid_move(self, adapter_setup, mock_player, mock_move):
        """Test selecting a valid move."""
        adapter = adapter_setup
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"

        mock_move.viable = Mock(return_value=True)
        mock_move.fatigue_cost = 10
        mock_player.known_moves = [mock_move]
        mock_player.fatigue = 50
        mock_player.current_move = None

        result = adapter._handle_move_selection(0)

        assert result is not None

    def test_handle_move_selection_not_viable(self, adapter_setup, mock_player, mock_move):
        """Test selecting a move that's not viable."""
        adapter = adapter_setup
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"

        mock_move.viable = Mock(return_value=False)
        mock_player.known_moves = [mock_move]

        result = adapter._handle_move_selection(0)

        assert result.get("error") == "Move is not currently available"

    def test_handle_move_selection_not_enough_fatigue(self, adapter_setup, mock_player, mock_move):
        """Test selecting move without enough fatigue."""
        adapter = adapter_setup
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"

        mock_move.viable = Mock(return_value=True)
        mock_move.fatigue_cost = 100
        mock_player.known_moves = [mock_move]
        mock_player.fatigue = 10

        result = adapter._handle_move_selection(0)

        assert result.get("error") == "Not enough fatigue"

    def test_handle_invalid_move_index(self, adapter_setup, mock_player):
        """Test selecting move with invalid index."""
        adapter = adapter_setup
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        mock_player.known_moves = []

        result = adapter._handle_move_selection(99)

        assert result.get("error") == "Invalid move index"

    def test_handle_not_awaiting_input(self, adapter_setup):
        """Test move selection when not awaiting input."""
        adapter = adapter_setup
        adapter.awaiting_input = False

        result = adapter._handle_move_selection(0)

        assert "error" in result

    def test_handle_direction_selection(self, adapter_setup, mock_player, mock_move):
        """Test selecting a direction."""
        adapter = adapter_setup
        adapter.awaiting_input = True
        adapter.input_type = "direction_selection"
        adapter.pending_move_index = 0
        adapter.available_options = ["north", "south", "east", "west"]

        mock_move.user = mock_player
        mock_player.known_moves = [mock_move]

        result = adapter._handle_direction_selection("north")

        assert result is not None

    def test_handle_invalid_direction(self, adapter_setup):
        """Test selecting invalid direction."""
        adapter = adapter_setup
        adapter.awaiting_input = True
        adapter.input_type = "direction_selection"
        adapter.available_options = ["north", "south"]

        result = adapter._handle_direction_selection("invalid")

        assert result.get("error") == "Invalid direction"

    def test_handle_number_selection_valid(self, adapter_setup, mock_player, mock_move):
        """Test entering a valid number."""
        adapter = adapter_setup
        adapter.awaiting_input = True
        adapter.input_type = "number_input"
        adapter.pending_move_index = 0
        adapter.available_options = {"min": 3, "max": 10, "default": 5}

        mock_move.user = mock_player
        mock_player.known_moves = [mock_move]

        result = adapter._handle_number_selection(5)

        assert result is not None

    def test_handle_number_selection_out_of_range(self, adapter_setup):
        """Test entering number out of range."""
        adapter = adapter_setup
        adapter.awaiting_input = True
        adapter.input_type = "number_input"
        adapter.available_options = {"min": 3, "max": 10}

        result = adapter._handle_number_selection(50)

        assert "error" in result


# ============================================================================
# TEST: ProcessCommand
# ============================================================================


class TestProcessCommand:
    """Test command processing."""

    def test_process_move_selection_command(self, adapter_setup):
        """Test processing a move selection command."""
        adapter = adapter_setup
        adapter.awaiting_input = True

        with patch.object(adapter, '_handle_move_selection', return_value={"ok": True}):
            result = adapter.process_command({"type": "select_move", "move_index": 0})

        assert result.get("ok") is True

    def test_process_target_selection_command(self, adapter_setup):
        """Test processing a target selection command."""
        adapter = adapter_setup
        adapter.awaiting_input = True

        with patch.object(adapter, '_handle_target_selection', return_value={"ok": True}):
            result = adapter.process_command({"type": "select_target", "target_id": "enemy_123"})

        assert result.get("ok") is True

    def test_process_unknown_command(self, adapter_setup):
        """Test processing an unknown command type."""
        adapter = adapter_setup
        adapter.awaiting_input = True

        result = adapter.process_command({"type": "unknown_type"})

        assert "error" in result

    def test_process_command_not_awaiting_input(self, adapter_setup):
        """Test processing command when not awaiting input."""
        adapter = adapter_setup
        adapter.awaiting_input = False

        result = adapter.process_command({"type": "select_move", "move_index": 0})

        assert result.get("error") == "Not awaiting input"


# ============================================================================
# TEST: Inventory Serializers
# ============================================================================


class TestInventorySerializer:
    """Test inventory serialization."""

    def test_serialize_empty_inventory(self, live_player):
        """``InventorySerializer.serialize`` takes the *player*, not a list.

        (The prior version called ``serialize_inventory``, which does not exist,
        and asserted the result was a bare list. The real payload is a dict
        carrying the weight/slot summary the HUD reads.)
        """
        live_player.inventory = []

        result = InventorySerializer.serialize(live_player)

        assert result["items"] == []
        assert result["item_count"] == 0
        assert result["slots_used"] == 0
        assert result["total_weight"] == 0.0
        assert result["weight_percentage"] == 0.0

    def test_serialize_inventory_with_items(self, live_player, make_weapon):
        """Item count, slots used and total weight all track the real inventory."""
        dagger = make_weapon("Dagger")
        live_player.inventory = [dagger]

        result = InventorySerializer.serialize(live_player)

        assert result["item_count"] == 1
        assert result["slots_used"] == 1
        assert result["total_weight"] == pytest.approx(dagger.weight)
        (entry,) = result["items"]
        assert entry["name"] == dagger.name
        assert entry["index"] == 0
        assert entry["can_equip"] is True

    def test_serialize_inventory_weight_percentage_tracks_the_limit(
        self, live_player, make_weapon
    ):
        live_player.inventory = [make_weapon("Halberd")]
        result = InventorySerializer.serialize(live_player)

        expected = round(
            result["total_weight"] / result["weight_limit"] * 100, 1
        )
        assert result["weight_percentage"] == pytest.approx(expected, abs=0.05)


# ============================================================================
# TEST: Round-trip Serialization
# ============================================================================


class TestRoundTripSerialization:
    """Test serializing and deserializing data."""

    def test_combatant_roundtrip(self, mock_player):
        """Test serializing and deserializing a combatant."""
        serialized = CombatantSerializer.serialize_combatant(mock_player)

        json_str = json.dumps(serialized)
        assert len(json_str) > 0

    def test_combat_state_roundtrip(self, live_encounter):
        """The whole payload survives a real JSON round trip byte for byte."""
        player, goblin = live_encounter
        serialized = CombatStateSerializer.serialize_combat_state(player, [goblin])

        restored = json.loads(json.dumps(serialized))

        assert restored == serialized, "no value in the payload is JSON-lossy"
        assert restored["player"]["name"] == player.name
        assert [e["name"] for e in restored["enemies"]] == ["Goblin"]

    def test_multiple_combatants_roundtrip(self, mock_player, mock_npc):
        """Test roundtrip with multiple combatants."""
        allies = [mock_npc]
        enemies = [mock_npc]

        serialized = CombatStateSerializer.serialize_combat_state(
            mock_player, enemies, allies=allies
        )

        json_str = json.dumps(serialized)
        restored = json.loads(json_str)

        assert len(restored["allies"]) == 1
        assert len(restored["enemies"]) == 1


# ============================================================================
# TEST: Error Handling & Edge Cases
# ============================================================================


class TestErrorHandlingEdgeCases:
    """Test error handling and edge case serialization."""

    def test_serialize_combatant_null_values(self):
        """``None`` hp/name pass through instead of crashing the serializer.

        Previously this asserted only ``result is not None`` -- which the
        ``@safe_serializer`` decorator satisfies with ``{}`` even when the
        serializer blows up, so the test passed while proving nothing.
        """

        class NullCombatant:
            name = None
            hp = None
            maxhp = None
            friend = False

        result = CombatantSerializer.serialize_combatant(NullCombatant())

        assert result != {}, "an empty dict means the serializer raised"
        assert result["name"] is None
        assert result["health"] == {"current": None, "max": None}
        assert result["type"] == "npc"

    def test_serialize_player_missing_attributes(self):
        """A combatant with nothing but a name falls back to documented defaults.

        Note the ``type``: ``serialize_combatant`` branches on
        ``isinstance(combatant, Player)``, so an object that merely *claims* the
        name "Player" is still serialized as an NPC. The old version of this
        test set ``Mock().__class__.__name__ = "Player"`` and expected
        ``type == "player"``, which the real code has never done.
        """

        class BareCombatant:
            name = "Test"

        result = CombatantSerializer.serialize_combatant(BareCombatant())

        assert result["name"] == "Test"
        assert result["type"] == "npc"
        assert result["level"] == 1
        assert result["hp"] == 0 and result["max_hp"] == 100
        assert result["status_effects"] == []
        assert result["equipment"] == {
            "weapon": None,
            "armor": None,
            "resistances": {},
        }
        assert result["position"] is None

    def test_combat_log_with_special_characters(self, adapter_setup, mock_player):
        """Test log entries with special characters."""
        adapter = adapter_setup

        adapter._add_log_entry(1, "Message with emoji: 🎉")
        adapter._add_log_entry(1, 'Message with "quotes"')
        adapter._add_log_entry(1, "Message with <html>")

        logs = mock_player.combat_log
        assert len(logs) == 3

    def test_adapter_state_roundtrip(self, adapter_setup):
        """Test serializing and deserializing adapter state."""
        adapter = adapter_setup
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        adapter.available_options = [{"name": "Move1"}, {"name": "Move2"}]

        state = {
            "awaiting_input": adapter.awaiting_input,
            "input_type": adapter.input_type,
            "options": adapter.available_options
        }

        json_str = json.dumps(state)
        restored = json.loads(json_str)

        assert restored["awaiting_input"] is True
        assert restored["input_type"] == "move_selection"
        assert len(restored["options"]) == 2


# ============================================================================
# TEST: Available Moves Filtering
# ============================================================================


class TestGetAvailableMoves:
    """Test getting available moves and filtering."""

    def test_get_available_moves_filters_passives(self, adapter_setup, mock_player):
        """Test that passive moves are filtered from available moves."""
        passive_move = Mock()
        passive_move.passive = True

        active_move = Mock()
        active_move.passive = False
        active_move.name = "Attack"
        active_move.description = "A basic attack"
        active_move.category = "Attack"
        active_move.fatigue_cost = 10
        active_move.viable = Mock(return_value=True)
        active_move.current_stage = 0
        active_move.targeted = False

        mock_player.known_moves = [passive_move, active_move]
        adapter = adapter_setup

        result = adapter._get_available_moves()

        assert len(result) == 1
        assert result[0]["name"] == "Attack"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
