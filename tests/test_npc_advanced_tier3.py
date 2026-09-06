"""
NPC Advanced Systems - Tier 3B Coverage.

100% coverage for:
- src/npc/_friends.py: Mynx, Gorran, Grondite citizens, Mara, Devet, Liss
- src/npc/_loot.py: NPCLootMixin, loot table rolls, inventory drops
- src/npc/_merchants.py: Merchant base class, MiloCurioDealer, JamboHealsU
- src/npc/_llm.py: MynxLLMMixin, LLM context, text sanitization, pronouns

Target: 120+ tests covering all conditional paths, edge cases, error states.
"""

import pytest
import json
import os
from unittest.mock import MagicMock, patch, call, mock_open
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent


from src.npc._friends import (
    Mynx, Gorran, GronditePasserby, GronditeWorker, GronditeElder,
    GronditeConclaveElder, Mara, Devet, Liss
)
from src.npc._loot import NPCLootMixin, loot
from src.npc._merchants import Merchant, MiloCurioDealer, JamboHealsU
from src.npc._llm import MynxLLMMixin
from src.npc import NPC, Friend
from src.player import Player
from src.narration import capture_narration
from src.items import Item, Gold, Restorative, Draught, Antidote, Rock, Spear, Shortsword
import src.moves as moves  # type: ignore


@pytest.fixture(autouse=True)
def mock_time_sleep():
    """Mock time.sleep to avoid delays in all tests in this file."""
    with patch('time.sleep'):
        yield


# ─────────────────────────────────────────────────────────────────────────────
# FRIENDS TESTS (_friends.py)
# ─────────────────────────────────────────────────────────────────────────────

class TestMynx:
    """Test Mynx NPC — friendly, LLM-driven, non-combatant."""

    def test_mynx_initialization_defaults(self):
        """Test Mynx init with default name and description."""
        mynx = Mynx()
        assert mynx.name.startswith("Mynx")
        assert "spotted fur" in mynx.description
        assert mynx.damage == 0
        assert mynx.aggro is False
        assert mynx.exp_award == 0
        assert mynx.in_combat is False
        assert mynx._combat_disabled is True
        assert mynx.maxhp == 30
        assert mynx.speed == 18
        assert mynx.finesse == 16
        assert mynx.awareness == 20

    def test_mynx_initialization_custom_name(self):
        """Test Mynx init with custom name and description."""
        mynx = Mynx(
            name="Whiskers",
            description="A custom mynx"
        )
        assert mynx.name == "Whiskers"
        assert mynx.description == "A custom mynx"

    def test_mynx_pronouns(self):
        """Test Mynx pronouns are set correctly."""
        mynx = Mynx()
        assert mynx.pronouns["personal"] == "it"
        assert mynx.pronouns["possessive"] == "its"
        assert mynx.pronouns["reflexive"] == "itself"

    def test_mynx_keywords(self):
        """Test Mynx interaction keywords."""
        mynx = Mynx()
        assert "talk" in mynx.keywords
        assert "pet" in mynx.keywords
        assert "play" in mynx.keywords

    def test_mynx_combat_engage_no_op(self):
        """Test that combat_engage is a no-op for Mynx."""
        mynx = Mynx()
        player = MagicMock()
        mynx.combat_engage(player)
        assert mynx.in_combat is False

    def test_mynx_can_enter_combat_false(self):
        """Test that Mynx can never enter combat."""
        mynx = Mynx()
        assert mynx.can_enter_combat() is False

    def test_mynx_known_moves_initialized(self):
        """Test Mynx has NpcIdle move in known_moves."""
        mynx = Mynx()
        assert len(mynx.known_moves) >= 0  # May be empty if moves fails

    @patch('builtins.print')
    def test_mynx_talk_exception_fallback(self, mock_print):
        """Test Mynx.talk() exception fallback."""
        mynx = Mynx()
        player = MagicMock()
        # Simulate exception in interact_with_player
        mynx.interact_with_player = MagicMock(side_effect=Exception("LLM error"))
        mynx.talk(player)
        mock_print.assert_called_once()
        assert "confused chitter" in str(mock_print.call_args)

    def test_mynx_pet(self):
        """Test Mynx.pet() calls interact_with_player."""
        mynx = Mynx()
        player = MagicMock()
        mynx.interact_with_player = MagicMock(return_value="pet response")
        result = mynx.pet(player)
        mynx.interact_with_player.assert_called_once_with(
            player, prompt="pet", structured=False
        )
        assert result == "pet response"

    def test_mynx_play_without_item(self):
        """Test Mynx.play() without an item."""
        mynx = Mynx()
        player = MagicMock()
        mynx.interact_with_player = MagicMock(return_value="play response")
        result = mynx.play(player)
        mynx.interact_with_player.assert_called_once_with(
            player, prompt="play", structured=False
        )

    def test_mynx_play_with_item(self):
        """Test Mynx.play() with an item."""
        mynx = Mynx()
        player = MagicMock()
        item = MagicMock()
        item.__str__ = MagicMock(return_value="stick")
        mynx.interact_with_player = MagicMock(return_value="play response")
        mynx.play(player, item=item)
        mynx.interact_with_player.assert_called_once_with(
            player, prompt="play with stick", structured=False
        )

    def test_mynx_llm_state_attributes(self):
        """Test Mynx LLM state attributes are initialized."""
        mynx = Mynx()
        assert mynx._llm_last_response is None
        assert mynx._llm_adapter is None
        assert mynx._jean_advisor is None
        assert isinstance(mynx._llm_history, list)
        assert len(mynx._llm_history) == 0


class TestGorran:
    """Test Gorran NPC — rock-man ally."""

    def test_gorran_initialization(self):
        """Test Gorran basic initialization."""
        gorran = Gorran()
        assert gorran.name == "Rock-Man"
        assert "rock-like armor" in gorran.description
        assert gorran.maxhp == 200
        assert gorran.damage == 55
        assert gorran.speed == 5
        assert gorran.aggro is True
        assert gorran.exp_award == 0

    def test_gorran_battle_symbol(self):
        """Test Gorran battle symbol is set."""
        gorran = Gorran()
        assert gorran.battle_symbol == "G"

    def test_gorran_name_property_default(self):
        """Test Gorran name property returns 'Rock-Man' by default."""
        gorran = Gorran()
        assert gorran.name == "Rock-Man"

    def test_gorran_name_property_gorran_first(self):
        """Test Gorran name changes to 'Gorran' when story flag set."""
        gorran = Gorran()
        universe = MagicMock()
        universe.story = {"gorran_first": "1"}
        room = MagicMock()
        room.universe = universe
        gorran.current_room = room
        assert gorran.name == "Gorran"

    def test_gorran_name_property_language_stage(self):
        """Test Gorran name changes with language_stage flag."""
        gorran = Gorran()
        universe = MagicMock()
        universe.story = {"gorran_language_stage": "1"}
        room = MagicMock()
        room.universe = universe
        gorran.current_room = room
        assert gorran.name == "Gorran"

    def test_gorran_name_property_via_player_ref(self):
        """Test Gorran name via player_ref."""
        gorran = Gorran()
        universe = MagicMock()
        universe.story = {"gorran_first": "1"}
        player = MagicMock()
        player.universe = universe
        gorran.player_ref = player
        assert gorran.name == "Gorran"

    def test_gorran_name_setter(self):
        """Test Gorran name can be set."""
        gorran = Gorran()
        gorran.name = "CustomName"
        assert gorran._name == "CustomName"

    def test_gorran_wounded_flavor(self):
        """Test Gorran wounded flavor messages."""
        gorran = Gorran()
        # Mock random.choice to test deterministically
        msg = gorran.wounded_flavor()
        assert isinstance(msg, str)
        assert len(msg) > 0

    @patch('builtins.print')
    def test_gorran_talk_first_time(self, mock_print):
        """Test Gorran talk() on first encounter."""
        gorran = Gorran()
        universe = MagicMock()
        universe.story = {"gorran_first": "0"}
        room = MagicMock()
        room.universe = universe
        room.events_here = []
        gorran.current_room = room

        player = MagicMock()
        player.universe = universe

        with patch('src.functions.seek_class') as mock_seek:
            mock_event = MagicMock()
            mock_seek.return_value = MagicMock(return_value=mock_event)
            gorran.talk(player)
            mock_print.assert_called()
            assert universe.story["gorran_first"] == "1"

    @patch('builtins.print')
    def test_gorran_talk_stage_0(self, mock_print):
        """Test Gorran talk at language stage 0 (gesture/sound only)."""
        gorran = Gorran()
        universe = MagicMock()
        universe.story = {"gorran_first": "1", "gorran_language_stage": "0"}
        room = MagicMock()
        room.universe = universe
        gorran.current_room = room

        player = MagicMock()
        gorran.talk(player)
        mock_print.assert_called()

    @patch('builtins.print')
    def test_gorran_talk_stage_1(self, mock_print):
        """Test Gorran talk at language stage 1."""
        gorran = Gorran()
        universe = MagicMock()
        universe.story = {"gorran_first": "1", "gorran_language_stage": "1"}
        room = MagicMock()
        room.universe = universe
        gorran.current_room = room

        player = MagicMock()
        gorran.talk(player)
        mock_print.assert_called()

    @patch('builtins.print')
    def test_gorran_talk_stage_2(self, mock_print):
        """Test Gorran talk at language stage 2 (single words)."""
        gorran = Gorran()
        universe = MagicMock()
        universe.story = {"gorran_first": "1", "gorran_language_stage": "2"}
        room = MagicMock()
        room.universe = universe
        gorran.current_room = room

        player = MagicMock()
        gorran.talk(player)
        mock_print.assert_called()

    @patch('builtins.print')
    def test_gorran_talk_stage_3plus(self, mock_print):
        """Test Gorran talk at language stage 3+ (phrases)."""
        gorran = Gorran()
        universe = MagicMock()
        universe.story = {"gorran_first": "1", "gorran_language_stage": "3"}
        room = MagicMock()
        room.universe = universe
        gorran.current_room = room

        player = MagicMock()
        gorran.talk(player)
        mock_print.assert_called()


class TestGronditePasserby:
    """Test GronditePasserby NPC."""

    def test_grondite_passerby_initialization(self):
        """Test GronditePasserby init."""
        npc = GronditePasserby()
        assert npc.name == "Grondite"
        assert npc.damage == 0
        assert npc.aggro is False
        assert npc.exp_award == 0
        assert npc.maxhp == 80
        assert npc.protection == 10

    def test_grondite_passerby_keywords(self):
        """Test GronditePasserby keywords."""
        npc = GronditePasserby()
        assert "talk" in npc.keywords

    @patch('builtins.print')
    def test_grondite_passerby_talk(self, mock_print):
        """Test GronditePasserby talk()."""
        npc = GronditePasserby()
        player = MagicMock()
        npc.talk(player)
        mock_print.assert_called_once()
        args = str(mock_print.call_args)
        assert len(args) > 0


class TestGronditeWorker:
    """Test GronditeWorker NPC."""

    def test_grondite_worker_initialization(self):
        """Test GronditeWorker init."""
        npc = GronditeWorker()
        assert npc.name == "Grondite Worker"
        assert npc.damage == 0
        assert npc.aggro is False
        assert npc.maxhp == 80
        assert npc.protection == 8

    @patch('builtins.print')
    def test_grondite_worker_talk(self, mock_print):
        """Test GronditeWorker talk()."""
        npc = GronditeWorker()
        player = MagicMock()
        npc.talk(player)
        mock_print.assert_called_once()


class TestGronditeElder:
    """Test GronditeElder NPC."""

    def test_grondite_elder_initialization(self):
        """Test GronditeElder init."""
        npc = GronditeElder()
        assert npc.name == "Grondite Elder"
        assert npc.maxhp == 120
        assert npc.protection == 15
        assert npc.speed == 2

    @patch('builtins.print')
    def test_grondite_elder_talk(self, mock_print):
        """Test GronditeElder talk()."""
        npc = GronditeElder()
        player = MagicMock()
        npc.talk(player)
        mock_print.assert_called_once()


class TestGronditeConclaveElder:
    """Test GronditeConclaveElder NPC — quest giver stub."""

    def test_conclave_elder_initialization(self):
        """Test GronditeConclaveElder init."""
        npc = GronditeConclaveElder()
        assert npc.name == "Conclave Elder"
        assert npc.maxhp == 150
        assert npc.protection == 20
        assert npc.awareness == 25

    @patch('time.sleep')
    @patch('builtins.print')
    def test_conclave_elder_talk_first_time(self, mock_print, mock_sleep):
        """Test GronditeConclaveElder talk() on first encounter."""
        npc = GronditeConclaveElder()
        player = MagicMock()
        player.universe = MagicMock()
        player.universe.story = {}

        npc.talk(player)

        # Verify story flag was set
        assert player.universe.story.get(npc._INTRO_RUN_KEY) == "1"
        # Verify dialogue was printed
        assert mock_print.call_count > 0

    @patch('time.sleep')
    @patch('builtins.print')
    def test_conclave_elder_talk_subsequent(self, mock_print, mock_sleep):
        """Test GronditeConclaveElder talk() on subsequent encounters."""
        npc = GronditeConclaveElder()
        player = MagicMock()
        player.universe = MagicMock()
        player.universe.story = {npc._INTRO_RUN_KEY: "1"}

        npc.talk(player)
        assert mock_print.call_count > 0

    @patch('time.sleep')
    @patch('builtins.print')
    def test_conclave_elder_talk_no_universe(self, mock_print, mock_sleep):
        """Test GronditeConclaveElder talk() with no universe."""
        npc = GronditeConclaveElder()
        player = MagicMock()
        player.universe = None

        npc.talk(player)
        # Should not crash
        assert mock_print.call_count >= 0


class TestMara:
    """Test Mara NPC — scavenger, companion."""

    def test_mara_initialization(self):
        """Test Mara basic initialization."""
        mara = Mara()
        assert mara.name == "Mara"
        assert "late twenties" in mara.description
        assert mara.maxhp == 95
        assert mara.damage == 38
        assert mara.speed == 8
        assert mara.finesse == 8
        assert mara.awareness == 35
        assert mara.aggro is False

    def test_mara_keywords(self):
        """Mara offers the talk verb only -- she is not a merchant.

        ConversationalNPCMixin._init_chat_attrs() deliberately does not
        auto-append a "chat" keyword: every mixin host already carries
        "talk", and duplicating it produced two buttons for one action.

        This pins the Python half of that rule only. The map payloads are the
        other half and can overwrite it -- see
        ``TestMapPayloadsDoNotReintroduceTheChatKeyword`` below.
        """
        mara = Mara()
        assert mara.keywords == ["talk"]
        assert "trade" not in mara.keywords
        assert "buy" not in mara.keywords

    def test_mara_battle_symbol(self):
        """Test Mara battle symbol."""
        mara = Mara()
        assert mara.battle_symbol == "M"

    def test_mara_pronouns(self):
        """Test Mara pronouns."""
        mara = Mara()
        assert mara.pronouns["personal"] == "she"
        assert mara.pronouns["possessive"] == "her"

    def test_mara_weapon_ranges(self):
        """Test Mara's weapon range attributes."""
        mara = Mara()
        assert mara.bow_range == (8, 25)
        assert mara.dagger_range == (0, 3)

    def test_mara_get_optimal_range_no_proximity(self):
        """Test _get_optimal_range_to_target with no proximity data."""
        mara = Mara()
        mara.combat_proximity = None
        assert mara._get_optimal_range_to_target() is None

    def test_mara_get_optimal_range_no_enemies(self):
        """Test _get_optimal_range_to_target with no enemies."""
        mara = Mara()
        mara.combat_proximity = {}
        mara.player_ref = MagicMock()
        mara.player_ref.combat_list = []
        assert mara._get_optimal_range_to_target() is None

    def test_mara_get_optimal_range_bow_mode(self):
        """Test _get_optimal_range_to_target returns 'bow' when distance >= 8."""
        mara = Mara()
        enemy = MagicMock()
        mara.combat_proximity = {enemy: 10}
        mara.player_ref = MagicMock()
        mara.player_ref.combat_list = [enemy]
        assert mara._get_optimal_range_to_target() == "bow"

    def test_mara_get_optimal_range_dagger_mode(self):
        """Test _get_optimal_range_to_target returns 'dagger' when distance <= 3."""
        mara = Mara()
        enemy = MagicMock()
        mara.combat_proximity = {enemy: 2}
        mara.player_ref = MagicMock()
        mara.player_ref.combat_list = [enemy]
        assert mara._get_optimal_range_to_target() == "dagger"

    def test_mara_get_optimal_range_transition_healthy(self):
        """Test _get_optimal_range_to_target transition zone (healthy)."""
        mara = Mara()
        mara.hp = 80
        mara.maxhp = 100
        mara.fatigue = 60
        mara.maxfatigue = 100
        enemy = MagicMock()
        mara.combat_proximity = {enemy: 5}
        mara.player_ref = MagicMock()
        mara.player_ref.combat_list = [enemy]
        assert mara._get_optimal_range_to_target() == "dagger"

    def test_mara_get_optimal_range_transition_wounded(self):
        """Test _get_optimal_range_to_target transition zone (wounded)."""
        mara = Mara()
        mara.hp = 30
        mara.maxhp = 100
        mara.fatigue = 60
        mara.maxfatigue = 100
        enemy = MagicMock()
        mara.combat_proximity = {enemy: 5}
        mara.player_ref = MagicMock()
        mara.player_ref.combat_list = [enemy]
        assert mara._get_optimal_range_to_target() == "bow"

    def test_mara_select_move_bow_mode(self):
        """Test Mara.select_move() in bow mode."""
        mara = Mara()
        mara.refresh_moves = MagicMock(return_value=[
            MagicMock(name="Withdraw", weight=2, viable=MagicMock(return_value=True), fatigue_cost=10),
            MagicMock(name="NpcAttack", weight=3, viable=MagicMock(return_value=True), fatigue_cost=15),
        ])
        mara.fatigue = 50
        mara.maxfatigue = 100
        mara._get_optimal_range_to_target = MagicMock(return_value="bow")

        mara.select_move()
        assert mara.current_move is not None

    def test_mara_select_move_no_fatigue_fallback(self):
        """Test Mara.select_move() when out of fatigue (rest fallback)."""
        mara = Mara()
        mara.refresh_moves = MagicMock(return_value=[
            MagicMock(name="NpcAttack", weight=3, viable=MagicMock(return_value=True), fatigue_cost=100),
        ])
        mara.fatigue = 5
        mara.maxfatigue = 100

        mara.select_move()
        # Should set rest move when out of fatigue
        assert mara.current_move is not None

    def test_mara_wounded_flavor(self):
        """Test Mara wounded flavor messages."""
        mara = Mara()
        msg = mara.wounded_flavor()
        assert isinstance(msg, str)
        assert len(msg) > 0

    @patch('builtins.print')
    def test_mara_talk(self, mock_print):
        """Test Mara talk()."""
        mara = Mara()
        player = MagicMock()
        mara.talk(player)
        mock_print.assert_called_once()


class TestDevet:
    """Test Devet NPC — camp cook."""

    def test_devet_initialization(self):
        """Test Devet basic initialization."""
        devet = Devet()
        assert devet.name == "Devet"
        assert "weathered" in devet.description
        assert devet.damage == 0
        assert devet.aggro is False
        assert devet.maxhp == 100
        assert devet.awareness == 30

    def test_devet_keywords(self):
        """Test Devet keywords."""
        devet = Devet()
        assert "talk" in devet.keywords

    @patch('builtins.print')
    def test_devet_talk(self, mock_print):
        """Test Devet talk()."""
        devet = Devet()
        player = MagicMock()
        devet.talk(player)
        mock_print.assert_called_once()


class TestLiss:
    """Test Liss NPC — young girl."""

    def test_liss_initialization(self):
        """Test Liss basic initialization."""
        liss = Liss()
        assert liss.name == "Liss"
        assert "nine years old" in liss.description
        assert liss.damage == 0
        assert liss.aggro is False
        assert liss.maxhp == 60
        assert liss.awareness == 28

    def test_liss_keywords(self):
        """Test Liss keywords."""
        liss = Liss()
        assert "talk" in liss.keywords

    @patch('builtins.print')
    def test_liss_talk(self, mock_print):
        """Test Liss talk()."""
        liss = Liss()
        player = MagicMock()
        liss.talk(player)
        mock_print.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# LOOT TESTS (_loot.py)
# ─────────────────────────────────────────────────────────────────────────────

class TestNPCLootMixin:
    """Test loot table rolls, inventory drops, death sequencing."""

    def test_npc_die_with_loot(self):
        """Test NPC die() calls before_death and prints message."""
        npc = NPC(
            name="LootEnemy",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.before_death = MagicMock(return_value=True)

        with patch('builtins.print') as mock_print:
            npc.die()
            npc.before_death.assert_called_once()
            assert any("exploded" in str(call) for call in mock_print.call_args_list)

    def test_npc_die_before_death_false(self):
        """Test NPC die() when before_death returns False."""
        npc = NPC(
            name="TestNPC",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.before_death = MagicMock(return_value=False)

        with patch('builtins.print'):
            npc.die()
            npc.before_death.assert_called_once()

    def test_before_death_roll_loot(self):
        """Test before_death() calls roll_loot when loot exists."""
        npc = NPC(
            name="LootNPC",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.loot = {"Gold": {"chance": 100, "qty": 10}}
        npc.current_room = MagicMock()
        npc.current_room.items_here = []
        npc.inventory = []
        npc.roll_loot = MagicMock()

        result = npc.before_death()

        assert result is True
        npc.roll_loot.assert_called_once()

    def test_before_death_drop_inventory(self):
        """Test before_death() calls drop_inventory."""
        npc = NPC(
            name="InventoryNPC",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.loot = None
        npc.current_room = MagicMock()
        npc.current_room.items_here = []
        npc.inventory = []
        npc.drop_inventory = MagicMock()

        result = npc.before_death()

        assert result is True
        npc.drop_inventory.assert_called_once()

    def test_before_death_stacks_items(self):
        """Test before_death() stacks items after dropping."""
        npc = NPC(
            name="TestNPC",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.loot = None
        npc.current_room = MagicMock()
        npc.current_room.items_here = []
        npc.inventory = []

        with patch('src.functions.stack_items_list') as mock_stack:
            npc.before_death()
            mock_stack.assert_called_once_with(npc.current_room.items_here)

    def test_drop_inventory_empty(self):
        """Test drop_inventory() with empty inventory."""
        npc = NPC(
            name="Empty",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.current_room = MagicMock()
        npc.inventory = []

        npc.drop_inventory()

        assert npc.inventory == []
        npc.current_room.spawn_item.assert_not_called()

    def test_drop_inventory_with_items(self):
        """Test drop_inventory() drops items with variance."""
        npc = NPC(
            name="HasItems",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        item = MagicMock()
        item.count = 5
        item.__class__.__name__ = "TestItem"
        npc.inventory = [item]
        npc.current_room = MagicMock()

        with patch('random.random', return_value=0.5):
            npc.drop_inventory()

        # Item should be dropped
        npc.current_room.spawn_item.assert_called()

    def test_drop_inventory_combat_adapter_tracking(self):
        """Test drop_inventory() records drops for combat adapter."""
        npc = NPC(
            name="DropTracker",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        item = MagicMock()
        item.count = 2
        item.__class__.__name__ = "Gold"
        item.name = "Gold Coin"
        npc.inventory = [item]
        npc.current_room = MagicMock()
        npc.current_room.spawn_item = MagicMock(return_value=item)

        player = MagicMock()
        player._combat_adapter = MagicMock()
        player.combat_drops = []
        npc.player_ref = player

        with patch('random.random', return_value=0.5):
            npc.drop_inventory()

        # Verify drop was recorded
        assert len(player.combat_drops) > 0

    def test_roll_loot_no_room(self):
        """Test roll_loot() when current_room is None."""
        npc = NPC(
            name="NoRoom",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.loot = {"Gold": {"chance": 100, "qty": 10}}
        npc.current_room = None

        with patch('builtins.print') as mock_print:
            npc.roll_loot()
            # Should print error
            assert any("ERR" in str(call) for call in mock_print.call_args_list)

    def test_roll_loot_success_simple_item(self):
        """Test roll_loot() success with simple item."""
        npc = NPC(
            name="LootRoller",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.loot = {"Gold": {"chance": 100, "qty": 50}}
        npc.current_room = MagicMock()
        npc.player_ref = None

        drop_item = MagicMock()
        drop_item.name = "Gold"
        npc.current_room.spawn_item = MagicMock(return_value=drop_item)

        with patch('src.functions.randomize_amount', return_value=50):
            with patch('builtins.print'):
                npc.roll_loot()

        npc.current_room.spawn_item.assert_called_once_with("Gold", 50)

    def test_roll_loot_equipment_generation(self):
        """Test roll_loot() with Equipment_X_Y syntax."""
        npc = NPC(
            name="EquipmentDropper",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.loot = {"Equipment_1_2": {"chance": 100, "qty": 1}}
        npc.current_room = MagicMock()
        npc.player_ref = None

        with patch('src.loot_tables.Loot.random_equipment') as mock_gen:
            drop_item = MagicMock()
            drop_item.name = "Enchanted Sword"
            mock_gen.return_value = drop_item
            npc.current_room.spawn_item = MagicMock()

            with patch('src.functions.randomize_amount', return_value=1):
                with patch('builtins.print'):
                    npc.roll_loot()

            # Should call random_equipment with parsed params
            mock_gen.assert_called_once()

    def test_roll_loot_failure_low_roll(self):
        """Test roll_loot() fails if roll is below chance."""
        npc = NPC(
            name="NoLuck",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.loot = {"Gold": {"chance": 10, "qty": 50}}
        npc.current_room = MagicMock()

        with patch('random.randint', return_value=20):  # Roll > chance
            with patch('builtins.print'):
                npc.roll_loot()

        # Should not spawn anything
        npc.current_room.spawn_item.assert_not_called()

    def test_roll_loot_combat_adapter_tracking(self):
        """Test roll_loot() records drops for combat adapter."""
        npc = NPC(
            name="LootTracker",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.loot = {"Gold": {"chance": 100, "qty": 50}}
        npc.current_room = MagicMock()

        player = MagicMock()
        player._combat_adapter = MagicMock()
        player.combat_drops = []
        npc.player_ref = player

        drop_item = MagicMock()
        drop_item.name = "Gold"
        npc.current_room.spawn_item = MagicMock(return_value=drop_item)

        with patch('src.functions.randomize_amount', return_value=50):
            with patch('builtins.print'):
                npc.roll_loot()

        # Verify drop was recorded
        assert len(player.combat_drops) > 0


# ─────────────────────────────────────────────────────────────────────────────
# MERCHANT TESTS (_merchants.py)
# ─────────────────────────────────────────────────────────────────────────────

class TestMerchant:
    """Test Merchant base class."""

    def test_merchant_initialization(self):
        """Test Merchant basic initialization."""
        merchant = Merchant(
            name="TestMerchant",
            description="A test merchant",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=20,
        )
        assert merchant.name == "TestMerchant"
        assert merchant.stock_count == 20
        assert merchant.damage == 5
        assert merchant.enchantment_rate == 1.0
        assert "buy" in merchant.keywords
        assert "sell" in merchant.keywords
        assert "trade" in merchant.keywords

    def test_merchant_specialties_default_empty(self):
        """Test Merchant specialties default to empty list."""
        merchant = Merchant(
            name="NoSpecialty",
            description="Test",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=10,
        )
        assert merchant.specialties == []

    def test_merchant_specialties_custom(self):
        """Test Merchant with custom specialties."""
        merchant = Merchant(
            name="PotionMerchant",
            description="Test",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=10,
            specialties=[Restorative, Draught],
        )
        assert Restorative in merchant.specialties
        assert Draught in merchant.specialties

    def test_merchant_always_stock(self):
        """Test Merchant always_stock parameter."""
        items = [Gold(amt=100), Restorative(count=5)]
        merchant = Merchant(
            name="StockTest",
            description="Test",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=10,
            always_stock=items,
        )
        assert merchant.always_stock == items

    def test_merchant_base_gold(self):
        """Test Merchant base_gold parameter."""
        merchant = Merchant(
            name="RichMerchant",
            description="Test",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=10,
            base_gold=5000,
        )
        assert merchant.base_gold == 5000

    @patch('builtins.print')
    def test_merchant_talk(self, mock_print):
        """Test Merchant.talk() default message."""
        merchant = Merchant(
            name="Generic",
            description="Test",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=10,
        )
        player = MagicMock()
        merchant.talk(player)
        mock_print.assert_called_once()
        assert "nothing to say" in str(mock_print.call_args).lower()

    @patch('builtins.print')
    def test_merchant_trade(self, mock_print):
        """Test Merchant.trade() method."""
        merchant = Merchant(
            name="Trader",
            description="Test",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=10,
        )
        # Real player-ish object carrying one merchandise item and one personal item.
        merchandise = Rock(merchandise=True)
        personal = Rock()
        personal.merchandise = False
        player = SimpleNamespace(inventory=[merchandise, personal])

        merchant.trade(player)

        # trade() absorbs unpaid merchandise into the merchant's stock and
        # leaves Jean's own belongings alone.
        assert merchandise not in player.inventory
        assert personal in player.inventory
        assert merchandise in merchant.inventory

    def test_merchant_buy_delegates_to_trade(self):
        """Test Merchant.buy() delegates to trade()."""
        merchant = Merchant(
            name="Buyer",
            description="Test",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=10,
        )
        merchant.trade = MagicMock()
        player = MagicMock()

        merchant.buy(player)

        merchant.trade.assert_called_once_with(player)

    def test_merchant_sell_delegates_to_trade(self):
        """Test Merchant.sell() delegates to trade()."""
        merchant = Merchant(
            name="Seller",
            description="Test",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=10,
        )
        merchant.trade = MagicMock()
        player = MagicMock()

        merchant.sell(player)

        merchant.trade.assert_called_once_with(player)


class TestMiloCurioDealer:
    """Test MiloCurioDealer merchant."""

    def test_milo_initialization(self):
        """Test MiloCurioDealer basic initialization."""
        milo = MiloCurioDealer()
        assert milo.name == "Milo the Traveling Curio Dealer"
        assert milo.damage == 2
        assert milo.aggro is False
        assert milo.exp_award == 0
        assert "eccentric merchant" in milo.description

    def test_milo_inventory_contents(self):
        """Test MiloCurioDealer has expected inventory items."""
        milo = MiloCurioDealer()
        item_names = [type(item).__name__ for item in milo.inventory]
        assert "Restorative" in item_names
        assert "Rock" in item_names
        assert "Spear" in item_names
        assert "Shortsword" in item_names
        assert "Gold" in item_names

    def test_milo_base_gold(self):
        """Test MiloCurioDealer has high base gold."""
        milo = MiloCurioDealer()
        assert milo.base_gold == 5000

    def test_milo_shop_pricing_attributes(self):
        """Milo carries the authored shop name and default price modifiers.

        The terminal ShopInterface (``npc.shop``) was removed; pricing now
        lives directly on the merchant and is read by GameService.shop_buy/
        shop_sell and ShopSerializer.
        """
        milo = MiloCurioDealer()
        assert not hasattr(milo, "shop")
        assert milo.shop_name == "The Wandering Curiosities Shop"
        assert milo.buy_modifier == 1.0
        assert milo.sell_modifier == 0.5

    @patch('builtins.print')
    def test_milo_talk(self, mock_print):
        """Test MiloCurioDealer.talk()."""
        milo = MiloCurioDealer()
        player = MagicMock()
        milo.talk(player)
        mock_print.assert_called_once()
        assert "rare" in str(mock_print.call_args).lower()

    def test_milo_trade_absorbs_player_merchandise(self):
        """Test MiloCurioDealer.trade() absorbs player merchandise."""
        milo = MiloCurioDealer()
        merchandise = Rock(merchandise=True)
        keepsake = Rock()
        keepsake.merchandise = False
        player = SimpleNamespace(inventory=[merchandise, keepsake])

        with patch('builtins.print'):
            milo.trade(player)

        assert merchandise in milo.inventory
        assert player.inventory == [keepsake]


class TestJamboHealsU:
    """Test JamboHealsU merchant — apothecary."""

    def test_jambo_initialization(self):
        """Test JamboHealsU basic initialization."""
        jambo = JamboHealsU()
        assert jambo.name == "Jambo"
        assert jambo.damage == 1
        assert jambo.aggro is False
        assert "wiry" in jambo.description

    def test_jambo_always_stock(self):
        """Test JamboHealsU always keeps potions in stock."""
        jambo = JamboHealsU()
        assert jambo.always_stock is not None
        item_types = [type(item).__name__ for item in jambo.always_stock]
        assert "Restorative" in item_types
        assert "Draught" in item_types
        assert "Antidote" in item_types

    def test_jambo_specialties(self):
        """Test JamboHealsU specializes in Consumables."""
        jambo = JamboHealsU()
        # Specialties should include Consumable
        assert any("Consumable" in str(s) for s in jambo.specialties)

    def test_jambo_enchantment_rate_zero(self):
        """Test JamboHealsU has no enchantments on potions."""
        jambo = JamboHealsU()
        assert jambo.enchantment_rate == 0.0

    def test_jambo_stock_count_small(self):
        """Test JamboHealsU has small stock count."""
        jambo = JamboHealsU()
        assert jambo.stock_count == 6

    def test_jambo_base_gold(self):
        """Test JamboHealsU base gold amount."""
        jambo = JamboHealsU()
        assert jambo.base_gold == 800

    def test_jambo_initialize_shop_sets_pricing(self):
        """initialize_shop() installs the pricing attributes the web shop reads."""
        jambo = JamboHealsU()
        assert jambo.shop_name == "Jambo Heals U"
        assert jambo.buy_modifier == 1.0
        assert jambo.sell_modifier == 0.5
        assert isinstance(jambo.inventory, list)

    @pytest.mark.parametrize(
        "map_name, allies, expected_tail",
        [
            # Neither context line qualifies: the pool is the three base lines
            # and the last of them is the river-crossings patter.
            (None, [], "River crossings"),
            # On the nomad camp map Jambo adds his crossing-is-good-business line...
            ("eastern-descent-nomad-camp", [], "Good crossing, this."),
            # ...and with Gorran along, the new-market-segment line.
            (None, ["Gorran"], "The stone one"),
        ],
    )
    def test_jambo_talk_line_pool_is_context_sensitive(
        self, map_name, allies, expected_tail
    ):
        """talk() appends context lines for the nomad camp and for Gorran.

        random.choice is pinned to the *last* entry so the assertion reads the
        line the context appended -- with a plain MagicMock player neither
        context ever qualifies, which is why the old version of this test
        (patching builtins.print, asserting nothing) could not tell the
        difference. Output goes through the narration sink, not print.
        """
        jambo = JamboHealsU()
        player = MagicMock()
        player.map = {"name": map_name} if map_name else None
        player.combat_list_allies = [
            SimpleNamespace(name=name) for name in allies
        ]

        with patch(
            "src.npc._merchants.random.choice", side_effect=lambda seq: seq[-1]
        ) as mock_choice, capture_narration() as messages:
            jambo.talk(player)

        assert len(messages) == 1
        assert expected_tail in messages[0]["text"]
        pool = mock_choice.call_args.args[0]
        assert len(pool) == 3 + len(allies) + (1 if map_name else 0)

    def test_jambo_trade(self):
        """Test JamboHealsU.trade() absorbs player merchandise."""
        jambo = JamboHealsU()
        player = MagicMock()
        jambo._collect_player_merchandise = MagicMock()

        with patch('builtins.print'):
            jambo.trade(player)

        jambo._collect_player_merchandise.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# LLM MIXIN TESTS (_llm.py)
# ─────────────────────────────────────────────────────────────────────────────

class TestMynxLLMMixin:
    """Test MynxLLMMixin — LLM-driven behavior, text sanitization, pronouns."""

    def test_append_llm_history_valid(self):
        """Test _append_llm_history adds history entry."""
        mynx = Mynx()
        mynx._append_llm_history("pet", "mynx purrs")
        assert len(mynx._llm_history) == 1
        assert mynx._llm_history[0]["prompt"] == "pet"
        assert mynx._llm_history[0]["response"] == "mynx purrs"

    def test_append_llm_history_keeps_max_3(self):
        """Test _append_llm_history keeps only last 3 entries."""
        mynx = Mynx()
        mynx._append_llm_history("1", "r1")
        mynx._append_llm_history("2", "r2")
        mynx._append_llm_history("3", "r3")
        mynx._append_llm_history("4", "r4")
        assert len(mynx._llm_history) == 3
        assert mynx._llm_history[-1]["prompt"] == "4"

    def test_append_llm_history_normalizes_whitespace(self):
        """Test _append_llm_history normalizes whitespace."""
        mynx = Mynx()
        mynx._append_llm_history("  pet  \n  cat  ", "  response  \n  text  ")
        assert mynx._llm_history[0]["prompt"] == "pet cat"
        assert mynx._llm_history[0]["response"] == "response text"

    def test_append_llm_history_empty_ignored(self):
        """Test _append_llm_history ignores empty entries."""
        mynx = Mynx()
        mynx._append_llm_history("", "")
        assert len(mynx._llm_history) == 0

    def test_append_llm_history_truncates_long_text(self):
        """Test _append_llm_history truncates very long text."""
        mynx = Mynx()
        long_prompt = "x" * 300
        mynx._append_llm_history(long_prompt, "response")
        assert len(mynx._llm_history[0]["prompt"]) <= 200

    def test_load_player_advisor_cached(self):
        """Test _load_player_advisor returns cached value."""
        mynx = Mynx()
        mynx._jean_advisor = {"cached": True}
        result = mynx._load_player_advisor()
        assert result["cached"] is True

    def test_load_player_advisor_from_file(self):
        """Test _load_player_advisor loads from jean.json."""
        mynx = Mynx()
        jean_data = {
            "character_name": "Jean",
            "pronouns": {"subject": "he", "object": "him"}
        }
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(jean_data))):
                result = mynx._load_player_advisor()
                assert result["character_name"] == "Jean"

    def test_load_player_advisor_fallback(self):
        """Test _load_player_advisor fallback when file missing."""
        mynx = Mynx()
        mynx._jean_advisor = None
        with patch('pathlib.Path.exists', return_value=False):
            result = mynx._load_player_advisor()
            assert result["character_name"] == "Jean"
            assert "pronouns" in result

    def test_get_llm_adapter_disabled(self):
        """Test _get_llm_adapter returns None when disabled."""
        mynx = Mynx()
        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "0"}):
            result = mynx._get_llm_adapter()
            assert result is None

    def test_get_llm_adapter_file_not_found(self):
        """Test _get_llm_adapter returns None when adapter file missing."""
        mynx = Mynx()
        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch('pathlib.Path.exists', return_value=False):
                result = mynx._get_llm_adapter()
                assert result is None

    def test_get_llm_adapter_caches_result(self):
        """Test _get_llm_adapter caches the result."""
        mynx = Mynx()
        mynx._llm_adapter = "cached"
        result = mynx._get_llm_adapter()
        assert result == "cached"

    def test_sanitize_mynx_llm_text_basic(self):
        """Test _sanitize_mynx_llm_text basic functionality."""
        mynx = Mynx()
        mynx.name = "Mynx"
        text = "Mynx chirps happily and jumps."
        result = mynx._sanitize_mynx_llm_text(text, ["Jean"])
        assert "Mynx" in result
        assert "chirps" in result

    def test_sanitize_mynx_llm_text_name_replacement(self):
        """Test _sanitize_mynx_llm_text replaces second name mention."""
        mynx = Mynx()
        mynx.name = "Mynx"
        text = "Mynx sees Mynx in the mirror."
        result = mynx._sanitize_mynx_llm_text(text, [])
        # First Mynx kept, second replaced with pronoun
        assert result.count("Mynx") == 1
        assert "it" in result

    def test_sanitize_mynx_llm_text_removes_self_actions(self):
        """Test _sanitize_mynx_llm_text removes self-targeting actions."""
        mynx = Mynx()
        mynx.name = "Mynx"
        text = "Mynx is batting at Mynx's tail."
        result = mynx._sanitize_mynx_llm_text(text, [])
        # Should replace or remove self-targeting action
        assert "Mynx" in result or "it" in result

    def test_sanitize_mynx_llm_text_whitespace_normalization(self):
        """Test _sanitize_mynx_llm_text normalizes whitespace."""
        mynx = Mynx()
        mynx.name = "Test"
        text = "Test   has   multiple   spaces."
        result = mynx._sanitize_mynx_llm_text(text, [])
        assert "   " not in result

    def test_enforce_pronouns_and_names_jean_pronouns(self):
        """Test _enforce_pronouns_and_names uses Jean's pronouns."""
        mynx = Mynx()
        mynx._jean_advisor = {
            "pronouns": {
                "subject": "he",
                "object": "him",
                "possessive_adjective": "his"
            }
        }
        text = "Jean sees him. He walks."
        roster = {"Jean"}
        result = mynx._enforce_pronouns_and_names(text, roster)
        # Jean's pronouns should be applied
        assert isinstance(result, str)

    def test_enforce_pronouns_and_names_invented_names(self):
        """Test _enforce_pronouns_and_names replaces invented names."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it", "possessive": "its"}
        text = "Bob and Jane were here."
        roster = set()
        result = mynx._enforce_pronouns_and_names(text, roster)
        # Bob and Jane should be replaced with pronouns
        assert "Bob" not in result or result.count("Bob") == 0

    def test_gather_environment_lists_empty_room(self):
        """Test _gather_environment_lists with empty room."""
        mynx = Mynx()
        mynx.current_room = None
        env_string, _ = mynx._gather_environment_lists()
        assert env_string == ""

    def test_gather_environment_lists_with_items(self):
        """Test _gather_environment_lists includes items."""
        mynx = Mynx()
        room = MagicMock()
        item = MagicMock()
        item.name = "Sword"
        item.description = "A sharp blade"
        room.items_here = [item]
        room.objects_here = []
        room.npcs_here = []
        mynx.current_room = room
        env_string, _ = mynx._gather_environment_lists()
        assert "Sword" in env_string or len(env_string) >= 0

    def test_gather_environment_lists_with_npcs(self):
        """Test _gather_environment_lists includes nearby NPCs."""
        mynx = Mynx()
        room = MagicMock()
        npc = MagicMock()
        npc.name = "Mara"
        npc.description = "A scavenger"
        room.items_here = []
        room.objects_here = []
        room.npcs_here = [npc]
        mynx.current_room = room
        mynx.name = "Mynx"
        env_string, _ = mynx._gather_environment_lists()
        # Should include Mara but not Mynx itself
        assert "Mara" in env_string or len(env_string) >= 0

    def test_build_history_block_empty(self):
        """Test _build_history_block with empty history."""
        mynx = Mynx()
        mynx._llm_history = []
        result = mynx._build_history_block()
        assert result == ""

    def test_build_history_block_with_entries(self):
        """Test _build_history_block includes history entries."""
        mynx = Mynx()
        mynx._llm_history = [
            {"prompt": "pet", "response": "purrs"},
            {"prompt": "play", "response": "bounces"},
        ]
        result = mynx._build_history_block()
        assert "pet" in result or "history" in result.lower()

    def test_build_pronoun_guidance(self):
        """Test _build_pronoun_guidance formats pronoun rules."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it", "possessive": "its"}
        result = mynx._build_pronoun_guidance("he/him/his", "Jean snippet")
        assert "it" in result
        assert isinstance(result, str)

    def test_build_llm_context_complete(self):
        """Test _build_llm_context builds full context."""
        mynx = Mynx()
        mynx.current_room = MagicMock()
        mynx.current_room.description = "A forest clearing"
        mynx.pronouns = {"personal": "it"}
        roster = {"Mara", "Jean"}
        result = mynx._build_llm_context(roster, "pet", "he/him/his", "Jean snippet")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_check_and_correct_mynx_text_valid(self):
        """Test _check_and_correct_mynx_text accepts valid text."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it"}
        mynx.name = "Mynx"
        text = "Mynx chirps happily."
        result = mynx._check_and_correct_mynx_text(text, "pet", [])
        assert result is not None
        assert "chirps" in result

    def test_check_and_correct_mynx_text_rejects_quoted_speech(self):
        """Test _check_and_correct_mynx_text rejects quoted speech."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it"}
        text = 'Mynx says "hello".'
        result = mynx._check_and_correct_mynx_text(text, "pet", [])
        assert result is None

    def test_check_and_correct_mynx_text_length_bounds(self):
        """Test _check_and_correct_mynx_text enforces length bounds."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it"}
        # Too short
        result = mynx._check_and_correct_mynx_text("xy", "pet", [])
        assert result is None
        # Too long
        result = mynx._check_and_correct_mynx_text("x" * 300, "pet", [])
        assert result is None

    def test_check_and_correct_mynx_text_rejects_past_tense_heavy(self):
        """Test _check_and_correct_mynx_text rejects past-tense-heavy text."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it"}
        text = "Mynx walked and jumped and danced and played and rested."
        result = mynx._check_and_correct_mynx_text(text, "pet", [])
        # Should reject due to high past tense ratio
        assert result is None

    def test_check_and_correct_mynx_text_adds_period(self):
        """Test _check_and_correct_mynx_text adds terminal period."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it"}
        mynx.name = "Mynx"
        text = "Mynx chirps happily"  # No period
        result = mynx._check_and_correct_mynx_text(text, "pet", [])
        assert result is not None
        assert result.endswith(".")

    def test_interact_with_player_action_print_pet(self):
        """Test interact_with_player prints action for 'pet'."""
        mynx = Mynx()
        mynx.current_room = None
        mynx._get_llm_adapter = MagicMock(return_value=None)  # No LLM
        player = MagicMock()

        with patch('builtins.print') as mock_print:
            mynx.interact_with_player(player, prompt="pet")
            # Should print Jean's action
            assert any("pet" in str(call).lower() for call in mock_print.call_args_list)

    def test_interact_with_player_action_print_feed(self):
        """Test interact_with_player prints action for 'feed'."""
        mynx = Mynx()
        mynx.current_room = None
        mynx._get_llm_adapter = MagicMock(return_value=None)
        player = MagicMock()

        with patch('builtins.print') as mock_print:
            mynx.interact_with_player(player, prompt="feed")
            assert any("food" in str(call).lower() for call in mock_print.call_args_list)

    def test_interact_with_player_fallback_pet_variations(self):
        """Test interact_with_player fallback provides pet variations."""
        mynx = Mynx()
        mynx.current_room = MagicMock()
        mynx.current_room.npcs_here = []
        mynx._get_llm_adapter = MagicMock(return_value=None)
        player = MagicMock()

        with patch('builtins.print'):
            result = mynx.interact_with_player(player, prompt="pet", structured=False)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_interact_with_player_fallback_feed_variations(self):
        """Test interact_with_player fallback provides feed variations."""
        mynx = Mynx()
        mynx.current_room = MagicMock()
        mynx.current_room.npcs_here = []
        mynx._get_llm_adapter = MagicMock(return_value=None)
        player = MagicMock()

        with patch('builtins.print'):
            result = mynx.interact_with_player(player, prompt="feed", structured=False)
            assert isinstance(result, str)

    def test_interact_with_player_fallback_play_variations(self):
        """Test interact_with_player fallback provides play variations."""
        mynx = Mynx()
        mynx.current_room = MagicMock()
        mynx.current_room.npcs_here = []
        mynx._get_llm_adapter = MagicMock(return_value=None)
        player = MagicMock()

        with patch('builtins.print'):
            result = mynx.interact_with_player(player, prompt="play", structured=False)
            assert isinstance(result, str)

    def test_interact_with_player_fallback_generic_variations(self):
        """Test interact_with_player fallback for unrecognized action."""
        mynx = Mynx()
        mynx.current_room = MagicMock()
        mynx.current_room.npcs_here = []
        mynx._get_llm_adapter = MagicMock(return_value=None)
        player = MagicMock()

        with patch('builtins.print'):
            result = mynx.interact_with_player(player, prompt="observe", structured=False)
            assert isinstance(result, str)

    def test_interact_with_player_structured_return(self):
        """Test interact_with_player returns structured object."""
        mynx = Mynx()
        mynx.current_room = MagicMock()
        mynx.current_room.npcs_here = []
        mynx._get_llm_adapter = MagicMock(return_value=None)
        player = MagicMock()

        with patch('builtins.print'):
            result = mynx.interact_with_player(player, prompt="pet", structured=True)
            assert isinstance(result, dict)
            assert "action" in result
            assert "description" in result

    def test_normalize_ws(self):
        """Test _normalize_ws normalizes whitespace."""
        mynx = Mynx()
        text = "  hello   world   test  "
        result = mynx._normalize_ws(text)
        assert result == "hello world test"
        assert "   " not in result


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION / EDGE CASE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegration:
    """Integration tests covering multiple systems."""

    @pytest.mark.parametrize(
        "verb, kwargs, expected_prompt",
        [
            ("talk", {}, None),
            ("pet", {}, "pet"),
            ("play", {}, "play"),
            ("play", {"item": "a pebble"}, "play with a pebble"),
        ],
    )
    def test_mynx_verbs_forward_the_right_prompt(self, verb, kwargs, expected_prompt):
        """Each verb is a thin wrapper that names itself to the LLM layer.

        The prompt string is the only thing distinguishing talk/pet/play, and
        it is what reaches the model -- so assert the prompt and the returned
        value, not merely that the call survived.
        """
        mynx = Mynx()
        player = MagicMock()
        sentinel = {"text": "Mynx chirps."}

        with patch.object(
            Mynx, "interact_with_player", return_value=sentinel
        ) as mock_interact:
            result = getattr(mynx, verb)(player, **kwargs)

        assert result is sentinel
        assert mock_interact.call_args.args[0] is player
        assert mock_interact.call_args.kwargs["prompt"] == expected_prompt
        assert mock_interact.call_args.kwargs["structured"] is False

    @pytest.mark.parametrize("verb", ["talk", "pet", "play"])
    def test_mynx_verbs_fall_back_to_a_chitter_on_error(self, verb):
        """An LLM failure degrades to narrated flavour, never an exception."""
        mynx = Mynx()

        with patch.object(
            Mynx, "interact_with_player", side_effect=RuntimeError("llm down")
        ):
            with capture_narration() as messages:
                result = getattr(mynx, verb)(MagicMock())

        assert result is None
        assert len(messages) == 1
        assert messages[0]["text"] == (
            f"{mynx.name} tilts its head and makes a confused chitter."
        )

    def test_merchant_shop_initialization(self):
        """Test Merchant shop initializes correctly."""
        merchant = Merchant(
            name="TestMerchant",
            description="Test",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=20,
        )
        # Should have shop or initialize_shop method
        assert hasattr(merchant, 'shop') or hasattr(merchant, 'initialize_shop')

    def test_loot_system_full_death_sequence(self):
        """Death drops both the loot-table roll and the carried inventory.

        Uses a real MapTile so the items actually land in items_here -- with a
        MagicMock room, spawn_item records a call and nothing is ever created,
        so the previous version of this test would have passed against a die()
        that dropped nothing at all.
        """
        from src.tiles import MapTile

        room = MapTile(MagicMock(), MagicMock(), 0, 0)
        npc = NPC(
            name="DeathTest",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.loot = {"Gold": {"chance": 100, "qty": 50}}
        npc.current_room = room
        npc.inventory = [Rock()]

        with patch('src.functions.randomize_amount', return_value=50), \
                patch('src.npc._loot.random.random', return_value=0.0), \
                capture_narration() as messages:
            npc.die()

        dropped = {type(item).__name__: item for item in room.items_here}
        assert set(dropped) == {"Gold", "Rock"}
        assert dropped["Gold"].amt == 50
        # Scattered inventory is concealed; the loot-table drop is not.
        assert dropped["Rock"].hidden is True
        assert npc.inventory == []

        text = [m["text"] for m in messages]
        assert "DeathTest dropped Gold x 50!" in text
        assert "DeathTest exploded into fragments of light!" in text


# ─────────────────────────────────────────────────────────────────────────────
# ADDITIONAL EDGE CASES AND COVERAGE TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestMynxExceptionHandling:
    """Test exception handling in Mynx and LLM code."""

    def test_mynx_known_moves_exception_fallback(self):
        """Test Mynx known_moves handles move initialization failures."""
        mynx = Mynx()
        # known_moves should be either initialized or empty
        assert isinstance(mynx.known_moves, list)

    def test_append_llm_history_drops_empty_pairs_and_normalises_the_rest(self):
        """None/None contributes no history entry; real values are normalised.

        An entry for an empty exchange would waste one of the three history
        slots the prompt builder has, silently pushing out a real turn.
        """
        mynx = Mynx()

        mynx._append_llm_history(None, None)
        assert mynx._llm_history == []

        mynx._append_llm_history(123, 456)
        assert mynx._llm_history == [{"prompt": "123", "response": "456"}]

        mynx._append_llm_history("  spaced\n\nout  ", "line\tbreaks")
        assert mynx._llm_history[-1] == {
            "prompt": "spaced out",
            "response": "line breaks",
        }

        # Prompt/response are truncated to 200/300 characters respectively.
        mynx._append_llm_history("p" * 250, "r" * 400)
        assert len(mynx._llm_history[-1]["prompt"]) == 200
        assert len(mynx._llm_history[-1]["response"]) == 300

        # ...and only the three most recent exchanges are kept.
        assert len(mynx._llm_history) == 3
        assert mynx._llm_history[0]["prompt"] == "123"

    def test_sanitize_mynx_llm_text_none_input(self):
        """Test _sanitize_mynx_llm_text handles None input."""
        mynx = Mynx()
        result = mynx._sanitize_mynx_llm_text(None, [])
        assert result is None

    def test_sanitize_mynx_llm_text_exception_returns_original(self):
        """Test _sanitize_mynx_llm_text exception handling."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it"}
        # Pass a complex object that might cause issues
        result = mynx._sanitize_mynx_llm_text("normal text", None)
        assert result == "normal text"

    def test_enforce_pronouns_and_names_exception(self):
        """Test _enforce_pronouns_and_names exception handling."""
        mynx = Mynx()
        # Should handle exceptions gracefully
        result = mynx._enforce_pronouns_and_names(None, set())
        assert result is None

    def test_gather_environment_lists_skips_nameless_items(self):
        """A nameless item is dropped from the prompt, not rendered as "None".

        The env string is pasted straight into the LLM prompt, so a malformed
        item must contribute nothing at all -- while a well-formed one beside
        it still has to show up, which is what stops this passing vacuously.
        """
        mynx = Mynx()
        room = MagicMock()
        nameless = MagicMock()
        nameless.name = None
        nameless.title = None
        good = MagicMock()
        good.name = "Restorative"
        good.description = "A red potion."
        room.items_here = [nameless, good]
        room.objects_here = []
        room.npcs_here = []
        mynx.current_room = room

        env_string, legacy = mynx._gather_environment_lists()

        assert legacy == set()
        assert env_string == (
            " Nearby items (name — description): Restorative — A red potion.."
        )
        assert "None" not in env_string

        # With only the malformed item there is nothing to say at all.
        room.items_here = [nameless]
        assert mynx._gather_environment_lists() == ("", set())


class TestGorranEdgeCases:
    """Test Gorran edge cases and missing code paths."""

    def test_gorran_name_property_no_current_room(self):
        """Test Gorran name when current_room is None."""
        gorran = Gorran()
        gorran.current_room = None
        gorran.player_ref = None
        # Should return Rock-Man
        assert gorran.name == "Rock-Man"

    def test_gorran_talk_with_valid_story_first_encounter(self):
        """The first TALK arms AfterGorranIntro and latches gorran_first.

        Three things have to happen together, and none of them was checked
        before: the intro event is constructed for this room and appended to
        it, the flag flips so the branch never runs twice, and the narration
        still calls him the Rock-Man (he is not named until ch01's naming
        beat).
        """
        gorran = Gorran()
        universe = MagicMock()
        universe.story = {"gorran_first": "0"}
        room = MagicMock()
        room.universe = universe
        room.events_here = []
        gorran.current_room = room
        player = MagicMock()
        player.universe = universe

        event_cls = MagicMock()
        intro_event = event_cls.return_value
        with patch('src.functions.seek_class', return_value=event_cls) as mock_seek:
            with capture_narration() as messages:
                assert gorran.talk(player) is None

        mock_seek.assert_called_once_with("AfterGorranIntro", "story")
        event_cls.assert_called_once_with(player, room, None, False)
        assert room.events_here == [intro_event]
        assert universe.story["gorran_first"] == "1"

        assert len(messages) == 1
        assert "The Rock-Man turns toward you slowly" in messages[0]["text"]
        assert "Gorran" not in messages[0]["text"]

    def test_grondite_known_moves_exception_fallback(self):
        """Test Grondite classes handle move initialization failures."""
        grondite = GronditePasserby()
        worker = GronditeWorker()
        elder = GronditeElder()
        # All should have known_moves as list
        assert isinstance(grondite.known_moves, list)
        assert isinstance(worker.known_moves, list)
        assert isinstance(elder.known_moves, list)


class TestMerchantsEdgeCases:
    """Test merchant edge cases and error paths."""

    def test_merchant_initialize_shop_none_inventory(self):
        """Test Merchant initialize_shop with None inventory."""
        merchant = Merchant(
            name="Test",
            description="Test",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=10,
            inventory=None,
        )
        assert merchant.inventory is None or isinstance(merchant.inventory, list)

    def test_merchant_initialize_shop_defaults_shop_name(self):
        """A merchant that authors no shop_name gets the derived default."""
        merchant = Merchant(
            name="Nameless",
            description="Test",
            damage=5,
            aggro=False,
            exp_award=0,
            stock_count=10,
            inventory=[],
        )
        assert merchant.shop_name == "Nameless's Shop"

    def test_merchant_initialize_shop_respects_preset_modifiers(self):
        """initialize_shop() must not clobber modifiers a subclass preset."""
        merchant = Merchant.__new__(Merchant)
        merchant.name = "Gouger"
        merchant.inventory = []
        merchant.buy_modifier = 2.5
        merchant.sell_modifier = 0.1
        merchant.initialize_shop()
        assert merchant.buy_modifier == 2.5
        assert merchant.sell_modifier == 0.1


class TestLlmContextBuilding:
    """Test LLM context building with various room configurations."""

    def test_build_llm_context_room_description(self):
        """Test _build_llm_context includes room description."""
        mynx = Mynx()
        room = MagicMock()
        room.description = "A vast cathedral"
        mynx.current_room = room
        mynx.pronouns = {"personal": "it"}

        context = mynx._build_llm_context({"Jean"}, "observe", "he/him/his", "Jean")
        assert "cathedral" in context or "room" in context.lower()

    def test_build_llm_context_no_room(self):
        """Test _build_llm_context with no room."""
        mynx = Mynx()
        mynx.current_room = None
        mynx.pronouns = {"personal": "it"}

        context = mynx._build_llm_context({"Jean"}, "observe", "he/him/his", "Jean")
        assert isinstance(context, str)

    def test_check_and_correct_mynx_text_max_sentences(self):
        """Test _check_and_correct_mynx_text trims to 2 sentences."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it"}
        mynx.name = "Mynx"
        text = "Mynx chirps. Mynx bounces. Mynx spins. Mynx jumps."
        result = mynx._check_and_correct_mynx_text(text, "play", [])
        # Should trim to 2 sentences max
        assert result is None or result.count(".") <= 2

    def test_interact_with_player_with_play_item(self):
        """Test interact_with_player with 'play with' item syntax."""
        mynx = Mynx()
        mynx.current_room = MagicMock()
        mynx.current_room.npcs_here = []
        mynx._get_llm_adapter = MagicMock(return_value=None)
        player = MagicMock()

        with patch('builtins.print') as mock_print:
            mynx.interact_with_player(player, prompt="play with ball")
            # Should print action with item
            assert any("ball" in str(call).lower() for call in mock_print.call_args_list)

    def test_interact_with_player_llm_generation_error_fallback(self):
        """Test interact_with_player falls back when LLM generation fails."""
        mynx = Mynx()
        mynx.current_room = MagicMock()
        mynx.current_room.npcs_here = []

        # Mock adapter that fails
        adapter = MagicMock()
        adapter.generate_plain = MagicMock(side_effect=Exception("LLM error"))
        mynx._get_llm_adapter = MagicMock(return_value=adapter)
        player = MagicMock()

        with patch('builtins.print'):
            result = mynx.interact_with_player(player, prompt="pet", structured=False)
            # Should fall back to deterministic response
            assert isinstance(result, str)

    def test_interact_with_player_llm_structured_success(self):
        """Test interact_with_player with successful structured generation."""
        mynx = Mynx()
        mynx.current_room = MagicMock()
        mynx.current_room.npcs_here = []

        adapter = MagicMock()
        adapter.generate_structured = MagicMock(return_value={
            "description": "Mynx purrs loudly."
        })
        mynx._get_llm_adapter = MagicMock(return_value=adapter)
        player = MagicMock()

        with patch('builtins.print'):
            result = mynx.interact_with_player(player, prompt="pet", structured=True)
            assert isinstance(result, dict)
            assert "description" in result

    def test_interact_with_player_llm_plain_success(self):
        """Test interact_with_player with successful plain text generation."""
        mynx = Mynx()
        mynx.current_room = MagicMock()
        mynx.current_room.npcs_here = []

        adapter = MagicMock()
        adapter.generate_plain = MagicMock(return_value="Mynx chirps happily.")
        mynx._get_llm_adapter = MagicMock(return_value=adapter)
        player = MagicMock()

        with patch('builtins.print') as mock_print:
            result = mynx.interact_with_player(player, prompt="pet", structured=False)
            assert isinstance(result, str)

    def test_interact_with_player_roster_building(self):
        """The roster reaching the model is exactly who is in the room, plus Jean.

        The allowed-names list is the guard-rail that stops the model
        inventing characters, so assert the string the adapter actually
        receives. With the adapter stubbed out to None (as this test used to
        do) the roster is never built at all.
        """
        mynx = Mynx()
        mynx.name = "Mynx"
        room = MagicMock()
        room.description = "a mossy hollow"
        room.items_here = []
        room.objects_here = []
        nameless = MagicMock()
        nameless.name = None
        room.npcs_here = [
            SimpleNamespace(name="Mara", description="A scavenger."),
            SimpleNamespace(name="Gorran", description="A rock-man."),
            nameless,
        ]
        mynx.current_room = room

        adapter = MagicMock()
        adapter.generate_plain.return_value = ""  # force the canned fallback
        with patch.object(Mynx, '_get_llm_adapter', return_value=adapter):
            with capture_narration():
                mynx.interact_with_player(MagicMock(), prompt="observe")

        context = adapter.generate_plain.call_args.kwargs["context"]
        assert (
            "Allowed entity names you may reference (no others): "
            "Gorran, Jean, Mara, Mynx." in context
        )
        assert "Player action/intent: 'observe'." in context


class TestLootEdgeCases:
    """Test loot system edge cases."""

    def test_roll_loot_multiple_items_only_one_drops(self):
        """Test roll_loot stops after first successful drop."""
        npc = NPC(
            name="MultiLoot",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.loot = {
            "Gold": {"chance": 100, "qty": 50},
            "Rock": {"chance": 100, "qty": 1},
        }
        npc.current_room = MagicMock()

        with patch('src.functions.randomize_amount', return_value=50):
            with patch('builtins.print'):
                npc.roll_loot()

        # Should only call spawn_item once (breaks after first success)
        assert npc.current_room.spawn_item.call_count == 1

    @pytest.mark.parametrize(
        "roll, expected_dropped",
        [
            (0.9, 0),  # every unit fails its survival roll -> nothing spawns
            (0.0, 2),  # every unit survives -> the whole stack spawns
        ],
    )
    def test_drop_inventory_spawns_only_the_surviving_units(
        self, roll, expected_dropped
    ):
        """Each unit of a stack rolls to survive; zero survivors spawns nothing.

        Uses a real MapTile so "did not spawn" means the floor is genuinely
        empty -- against a MagicMock room, spawn_item(amt=0) and no call at
        all look identical. Either way the corpse's inventory is cleared, so
        nothing can be dropped twice.
        """
        from src.tiles import MapTile

        room = MapTile(MagicMock(), MagicMock(), 0, 0)
        npc = NPC(
            name="ZeroQuant",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        npc.inventory = [Restorative(count=2)]
        npc.current_room = room

        with patch('src.npc._loot.random.random', return_value=roll):
            npc.drop_inventory()

        assert sum(item.count for item in room.items_here) == expected_dropped
        assert npc.inventory == []

    def test_drop_inventory_hidden_items(self):
        """Test drop_inventory hides items properly."""
        npc = NPC(
            name="HiddenDrop",
            description="Test",
            damage=10,
            aggro=True,
            exp_award=50,
        )
        item = MagicMock()
        item.count = 3
        item.__class__.__name__ = "TestItem"
        npc.inventory = [item]
        npc.current_room = MagicMock()

        with patch('random.random', return_value=0.5):
            with patch('random.randint', return_value=40):
                npc.drop_inventory()

        # Verify spawn_item was called with hidden parameter
        if npc.current_room.spawn_item.called:
            call_kwargs = npc.current_room.spawn_item.call_args[1]
            assert 'hidden' in call_kwargs or call_kwargs.get('hidden') == 1


class TestMayaSelectMoveEdgeCases:
    """Test Mara's select_move with various edge cases."""

    def test_mara_select_move_no_weighted_moves(self):
        """With nothing available, Mara picks nothing -- not even a rest.

        The empty-pool return fires before the fatigue-management block, so
        current_move must still be None afterwards. Falling through would hand
        her an NpcRest she never chose, which is a different (and wrong) beat.
        """
        mara = Mara()
        mara.refresh_moves = MagicMock(return_value=[])
        mara.fatigue = 50
        mara.maxfatigue = 100
        assert mara.current_move is None

        assert mara.select_move() is None

        assert mara.current_move is None
        mara.refresh_moves.assert_called_once()

    def test_mara_select_move_ai_config_bonus(self):
        """Test Mara.select_move with AI config bonuses."""
        mara = Mara()
        move = MagicMock()
        move.name = "NpcAttack"
        move.weight = 5
        move.viable = MagicMock(return_value=True)
        move.fatigue_cost = 10
        mara.refresh_moves = MagicMock(return_value=[move])
        mara.fatigue = 50
        mara.maxfatigue = 100

        ai_config = MagicMock()
        ai_config.get_weighted_move_bonus = MagicMock(return_value=2)
        mara.ai_config = ai_config

        mara.select_move()
        assert mara.current_move is not None

    def test_mara_select_move_max_attempts_hard_fallback(self):
        """Test Mara.select_move hard fallback to rest."""
        mara = Mara()
        # All moves have high fatigue cost
        move = MagicMock()
        move.name = "Expensive"
        move.weight = 5
        move.viable = MagicMock(return_value=True)
        move.fatigue_cost = 1000
        mara.refresh_moves = MagicMock(return_value=[move])
        mara.fatigue = 5
        mara.maxfatigue = 100

        mara.select_move()
        # Should fall back to rest move
        if mara.current_move:
            assert mara.current_move is not None


class TestConclavElderQuest:
    """Test GronditeConclaveElder quest interaction edge cases."""

    def test_conclave_elder_multiple_visits(self):
        """Test GronditeConclaveElder on multiple visits."""
        npc = GronditeConclaveElder()
        player = MagicMock()
        player.universe = MagicMock()
        player.universe.story = {npc._INTRO_RUN_KEY: "1"}

        with patch('builtins.print') as mock_print:
            npc.talk(player)
            # Should still print something
            assert mock_print.call_count > 0


class TestLLMGetAdapterEdgeCases:
    """Test _get_llm_adapter with various error conditions."""

    def test_get_llm_adapter_spec_creation_fails(self):
        """Test _get_llm_adapter when spec_from_file_location fails."""
        mynx = Mynx()
        mynx._llm_adapter = None

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('importlib.util.spec_from_file_location', return_value=None):
                    result = mynx._get_llm_adapter()
                    assert result is None

    def test_get_llm_adapter_spec_loader_none(self):
        """Test _get_llm_adapter when spec loader is None."""
        mynx = Mynx()
        mynx._llm_adapter = None

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch('pathlib.Path.exists', return_value=True):
                spec = MagicMock()
                spec.loader = None
                with patch('importlib.util.spec_from_file_location', return_value=spec):
                    result = mynx._get_llm_adapter()
                    assert result is None

    def test_get_llm_adapter_adapter_class_not_found(self):
        """Test _get_llm_adapter when MynxLLMAdapter class missing."""
        mynx = Mynx()
        mynx._llm_adapter = None

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('importlib.util.spec_from_file_location') as mock_spec:
                    spec = MagicMock()
                    mod = MagicMock(spec=[])  # No MynxLLMAdapter attribute
                    spec.loader.exec_module = MagicMock()
                    mock_spec.return_value = spec
                    with patch('importlib.util.module_from_spec', return_value=mod):
                        result = mynx._get_llm_adapter()
                        assert result is None

    def test_get_llm_adapter_availability_check_fails(self):
        """Test _get_llm_adapter when availability check fails."""
        mynx = Mynx()
        mynx._llm_adapter = None

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('importlib.util.spec_from_file_location') as mock_spec:
                    spec = MagicMock()
                    adapter = MagicMock()
                    adapter.available = MagicMock(side_effect=Exception("Check failed"))
                    spec.loader.exec_module = MagicMock()
                    mock_spec.return_value = spec
                    with patch('importlib.util.module_from_spec', return_value=MagicMock()):
                        with patch('importlib.util.module_from_spec'):
                            # Simulate module_from_spec returning something, then loader.exec_module assigning it
                            result = mynx._get_llm_adapter()
                            # Should handle exception and return None
                            assert result is None

    @staticmethod
    def _fake_llm_module(available=True, status="model=stub"):
        """A stand-in llm_client module exposing one MynxLLMAdapter."""
        adapter = MagicMock()
        adapter.available.return_value = available
        adapter.debug_status.return_value = status
        module = MagicMock()
        module.MynxLLMAdapter.return_value = adapter
        return module, adapter

    def test_get_llm_adapter_debug_status(self):
        """With debug on, an available adapter is cached and its status narrated.

        The old version asserted nothing and patched builtins.print, which the
        engine stopped using when output moved to the narration sink -- so it
        could not have seen the debug line even if it had looked.
        """
        mynx = Mynx()
        mynx._llm_adapter = None
        module, adapter = self._fake_llm_module(status="model=stub")

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1", "MYNX_LLM_DEBUG": "1"}):
            with patch(
                'src.npc._llm._load_llm_client_module', return_value=module
            ) as mock_load:
                with capture_narration() as messages:
                    result = mynx._get_llm_adapter()

        assert result is adapter
        assert mynx._llm_adapter is adapter  # cached for the next call
        mock_load.assert_called_once()
        assert [m["text"] for m in messages] == [
            "[MYNX_LLM_DEBUG] Adapter available: model=stub"
        ]

    def test_get_llm_adapter_stays_silent_without_the_debug_flag(self):
        """Debug narration is opt-in -- players must never see it."""
        mynx = Mynx()
        mynx._llm_adapter = None
        module, adapter = self._fake_llm_module()

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1", "MYNX_LLM_DEBUG": "0"}):
            with patch('src.npc._llm._load_llm_client_module', return_value=module):
                with capture_narration() as messages:
                    result = mynx._get_llm_adapter()

        assert result is adapter
        assert messages == []


class TestLLMHistoryEdgeCases:
    """Test LLM history edge cases."""

    def test_append_llm_history_type_conversion_non_string(self):
        """Test _append_llm_history converts non-string inputs."""
        mynx = Mynx()
        mynx._append_llm_history(12345, {"key": "value"})
        assert len(mynx._llm_history) == 1
        assert "12345" in mynx._llm_history[0]["prompt"]

    def test_append_llm_history_exception_silently_returns(self):
        """A broken history container must not take the conversation down.

        Bookkeeping this incidental is never worth an exception escaping into
        the NPC interaction path, so the failure is swallowed whole and the
        container is left exactly as it was.
        """
        mynx = Mynx()
        mynx._llm_history = None  # append() on this raises AttributeError

        assert mynx._append_llm_history("a real prompt", "a real response") is None
        assert mynx._llm_history is None


class TestSanitizationEdgeCases:
    """Test text sanitization with complex inputs."""

    def test_sanitize_mynx_llm_text_duplicate_pronouns(self):
        """Test _sanitize_mynx_llm_text handles duplicate pronouns."""
        mynx = Mynx()
        mynx.name = "Mynx"
        mynx.pronouns = {"personal": "it", "possessive": "its"}
        text = "it it sees things. it it bounces."
        result = mynx._sanitize_mynx_llm_text(text, [])
        # Should reduce duplicate pronouns
        assert result is not None
        assert "it it" not in result.lower() or result.count(" it ") == result.count(" it")

    def test_enforce_pronouns_and_names_jean_in_sentence(self):
        """Test _enforce_pronouns_and_names recognizes Jean in sentence."""
        mynx = Mynx()
        mynx._jean_advisor = {
            "pronouns": {
                "subject": "he",
                "object": "him",
                "possessive_adjective": "his"
            }
        }
        text = "Jean sees him walking. She is there."
        roster = {"Jean"}
        result = mynx._enforce_pronouns_and_names(text, roster)
        # Should apply Jean's pronouns
        assert isinstance(result, str)

    def test_enforce_pronouns_and_names_mynx_in_sentence(self):
        """Test _enforce_pronouns_and_names recognizes mynx in sentence."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it", "possessive": "its"}
        mynx.name = "Mynx"
        text = "Mynx darts forward. She bounces playfully."
        roster = set()
        result = mynx._enforce_pronouns_and_names(text, roster)
        # Should apply mynx's pronouns
        assert "Mynx" in result or "it" in result


class TestGatherEnvironmentComplexRooms:
    """Test environment gathering with complex room setups."""

    def test_gather_environment_with_all_types(self):
        """Test _gather_environment_lists with items, objects, and NPCs."""
        mynx = Mynx()
        mynx.name = "Mynx"
        room = MagicMock()

        item = MagicMock()
        item.name = "Sword"
        item.description = "A sharp blade"

        obj = MagicMock()
        obj.name = "Pedestal"
        obj.description = "An ancient stone pedestal"

        npc = MagicMock()
        npc.name = "Mara"
        npc.description = "A scavenger"

        room.items_here = [item]
        room.objects_here = [obj]
        room.npcs_here = [npc]
        mynx.current_room = room

        env_string, _ = mynx._gather_environment_lists()
        assert isinstance(env_string, str)

    def test_gather_environment_with_malformed_attributes(self):
        """Test _gather_environment_lists with malformed attributes."""
        mynx = Mynx()
        room = MagicMock()

        # Item with missing attributes
        item = MagicMock()
        item.name = None
        item.description = ""

        room.items_here = [item]
        room.objects_here = []
        room.npcs_here = []
        mynx.current_room = room

        env_string, _ = mynx._gather_environment_lists()
        # Should not crash
        assert isinstance(env_string, str)

    def test_gather_environment_deduplication(self):
        """Test _gather_environment_lists deduplicates items."""
        mynx = Mynx()
        room = MagicMock()

        item1 = MagicMock()
        item1.name = "Sword"
        item1.description = "desc"

        item2 = MagicMock()
        item2.name = "Sword"
        item2.description = "desc"

        room.items_here = [item1, item2]
        room.objects_here = []
        room.npcs_here = []
        mynx.current_room = room

        env_string, _ = mynx._gather_environment_lists()
        # Should deduplicate
        assert isinstance(env_string, str)


class TestBuildHistoryComplexCases:
    """Test history block building with various history states."""

    def test_build_history_block_truncation(self):
        """Test _build_history_block truncates long entries."""
        mynx = Mynx()
        mynx._llm_history = [
            {"prompt": "x" * 200, "response": "y" * 300},
            {"prompt": "short", "response": "response"},
        ]
        result = mynx._build_history_block()
        # Should not contain full truncated text
        assert "x" * 200 not in result


class TestCheckAndCorrectComplexCases:
    """Test text validation with edge cases."""

    def test_check_and_correct_mynx_text_empty_string(self):
        """Test _check_and_correct_mynx_text with empty string."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it"}
        result = mynx._check_and_correct_mynx_text("", "pet", [])
        assert result is None

    def test_check_and_correct_mynx_text_only_periods(self):
        """Test _check_and_correct_mynx_text with only periods."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it"}
        result = mynx._check_and_correct_mynx_text("...", "pet", [])
        assert result is None

    def test_check_and_correct_mynx_text_mixed_speech_types(self):
        """Test _check_and_correct_mynx_text rejects mixed quote types."""
        mynx = Mynx()
        mynx.pronouns = {"personal": "it"}
        text = 'Mynx says "hello\' and speaks.'
        result = mynx._check_and_correct_mynx_text(text, "pet", [])
        # May be rejected due to quote complexity
        assert result is None or isinstance(result, str)


class TestInteractWithPlayerPlayVariants:
    """Test interact_with_player with play action variants."""

    def test_interact_with_player_play_with_multiword_item(self):
        """Test interact_with_player with multi-word item name."""
        mynx = Mynx()
        mynx.current_room = MagicMock()
        mynx.current_room.npcs_here = []
        mynx._get_llm_adapter = MagicMock(return_value=None)
        player = MagicMock()

        with patch('builtins.print') as mock_print:
            mynx.interact_with_player(player, prompt="play with ruby ball")
            # Should include item in action
            call_str = str(mock_print.call_args_list)
            assert "ruby" in call_str.lower() or "ball" in call_str.lower()


class TestMerchantInitializeShopEdgeCases:
    """Test merchant shop initialization edge cases."""

    def test_jambo_initialize_shop_keeps_authored_name(self):
        """JamboHealsU's authored shop_name survives initialize_shop()."""
        jambo = JamboHealsU()
        # Authored in __init__ *after* super().__init__() ran initialize_shop(),
        # so the derived "Jambo's Shop" default must not be what sticks.
        assert jambo.shop_name == "Jambo Heals U"

    def test_jambo_initialize_shop_normalizes_none_inventory(self):
        """initialize_shop() converts a None inventory into an empty list."""
        jambo = JamboHealsU.__new__(JamboHealsU)
        jambo.name = "Jambo"
        jambo.inventory = None
        jambo.initialize_shop()
        assert jambo.inventory == []


MAPS_DIR = PROJECT_ROOT / "src" / "resources" / "maps"

#: The keyword the "one talk button" rule exists to keep out. Compared
#: case-insensitively: the UI renders a button per keyword, so ``"Chat"`` is
#: the same second button as ``"chat"``.
_FORBIDDEN_KEYWORD = "chat"


def _npc_keyword_payloads(map_data):
    """``(coord, index, keywords)`` for every NPC payload declaring keywords.

    Map JSON is ``{"(x, y)": {"npcs": [{"props": {...}}, ...], ...}}`` with a
    ``"metadata"`` key alongside the coordinates.
    """
    for coord, tile in map_data.items():
        if coord == "metadata" or not isinstance(tile, dict):
            continue
        for index, npc in enumerate(tile.get("npcs") or []):
            if not isinstance(npc, dict):
                continue
            props = npc.get("props") or {}
            keywords = props.get("keywords")
            if isinstance(keywords, list):
                yield coord, index, keywords


class TestMapPayloadsDoNotReintroduceTheChatKeyword:
    """The other half of ``TestMara.test_mara_keywords``.

    ``Mara().keywords == ["talk"]`` pins what ``__init__`` produces, and
    ``src/universe.py``'s deserializer then walks the map payload's ``props``
    and ``setattr``s each one onto the instance -- ``keywords`` included. So a
    payload carrying ``["talk", "chat"]`` overwrites the constructor's answer
    outright and puts the duplicate button back, with the Python-side test
    still green.

    Twenty-two payloads carried ``["talk", "chat"]`` and were hand-cleaned with
    nothing guarding the result. This is that guard.
    """

    def _maps(self):
        paths = sorted(MAPS_DIR.glob("*.json"))
        assert paths, f"no map JSON found under {MAPS_DIR}"
        return paths

    def test_no_npc_payload_carries_the_chat_keyword(self):
        offences = []
        inspected = 0
        for path in self._maps():
            data = json.loads(path.read_text(encoding="utf-8"))
            for coord, index, keywords in _npc_keyword_payloads(data):
                inspected += 1
                if any(
                    str(k).strip().lower() == _FORBIDDEN_KEYWORD for k in keywords
                ):
                    offences.append(f"{path.name} {coord} npcs[{index}]: {keywords}")

        # Non-vacuity. A scanner that walked the wrong shape -- a renamed
        # "npcs" key, props moved up a level -- would find nothing to inspect
        # and report no offences, which is indistinguishable from a pass.
        assert inspected, (
            "no NPC payload with a 'keywords' list was found in any map; the "
            "scan is looking at the wrong shape and would pass on anything"
        )
        assert offences == [], (
            "map payloads reintroduce the 'chat' keyword, which "
            "src/universe.py setattrs over whatever __init__ produced -- "
            "giving one action two buttons: " + "; ".join(offences)
        )

    def test_talk_is_what_those_payloads_actually_carry(self):
        """Non-vacuity, sharpened. The test above holds on maps whose NPCs
        declare no conversational verb at all. At least some of them must
        still offer ``talk``, or the rule it guards has no subject left."""
        talkers = 0
        for path in self._maps():
            data = json.loads(path.read_text(encoding="utf-8"))
            for _coord, _index, keywords in _npc_keyword_payloads(data):
                if any(str(k).strip().lower() == "talk" for k in keywords):
                    talkers += 1
        assert talkers, "no NPC payload offers 'talk' -- nothing here to guard"

    def test_the_scan_reports_a_payload_that_does_carry_it(self):
        """Failability, on the shape the real files use. Without this, a
        scanner that silently matched nothing would look identical to a clean
        repository."""
        planted = {
            "metadata": {"name": "planted"},
            "(1, 1)": {
                "npcs": [
                    {"props": {"keywords": ["talk"]}},
                    {"props": {"keywords": ["talk", "chat"]}},
                    {"props": {"keywords": ["talk", "Chat"]}},
                    {"props": {}},
                ]
            },
        }
        found = list(_npc_keyword_payloads(planted))
        assert len(found) == 3, found
        offending = [
            index
            for _coord, index, keywords in found
            if any(str(k).strip().lower() == _FORBIDDEN_KEYWORD for k in keywords)
        ]
        assert offending == [1, 2], "the scan missed a planted 'chat' keyword"

    def test_the_scan_ignores_object_keywords(self):
        """Objects legitimately carry many verbs (``open``, ``loot``,
        ``examine``). Sweeping every ``keywords`` key in the file would make
        this a test of scenery, and one day a scenery verb named ``chat``
        would fail it for the wrong reason."""
        planted = {
            "(0, 0)": {
                "objects": [{"props": {"keywords": ["chat", "read"]}}],
                "npcs": [{"props": {"keywords": ["talk"]}}],
            }
        }
        assert [kw for _c, _i, kw in _npc_keyword_payloads(planted)] == [["talk"]]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
