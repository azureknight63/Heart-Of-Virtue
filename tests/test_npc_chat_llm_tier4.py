"""
Tier 4B - Comprehensive test suite for ConversationalNPCMixin chat system.

100% coverage on src/npc/_chat_llm.py (373 lines).

Tests cover:
- Initialization and attribute setup
- LLM adapter lazy-loading and fallback
- World facts and character config loading
- Loquacity computation (base + modifiers)
- NPC key generation (story NPCs vs generics)
- Chat history persistence
- System prompt building
- NPC personality generation and fallback
- Text QC pipeline (slang, Jean-dialogue, proper nouns, repetition, truncation)
- Jean options QC pipeline
- Chat flow (open, respond, end)
- Pronoun handling for generic NPCs
- Fallback line selection
- Loquacity recovery ticks
- All edge cases and error paths
"""

import pytest
import sys
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock, call, PropertyMock
from typing import Dict, Any, List

# Ensure src is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent


from src.npc._chat_llm import (
    MAX_OPTION_CHARS,
    _MIN_OPTION_CHARS,
    ConversationalNPCMixin,
)
from tests._gs_fixtures import live_world
from tests._npc_fixtures import (
    ScriptedAdapter,
    chat_npc,
    chat_player,
    prohibit,
    qc_npc,
    ready_npc,
    wired_chat_npc,
)


class TestInitChatAttrs:
    """Test _init_chat_attrs initialization."""

    def test_init_chat_attrs_basic(self):
        """Test basic initialization of chat attributes."""
        npc = chat_npc()
        assert npc.loquacity_current == 0
        assert npc.loquacity_max == 0
        assert npc.loquacity_threshold == 0
        assert npc.loquacity_recovery == 2
        assert npc._chat_history == []
        assert npc._chat_personality is None
        assert npc._chat_npc_key is None
        assert npc._chat_adapter is None
        assert npc._chat_fallback_idx == 0
        assert "chat" not in npc.keywords

    def test_init_chat_attrs_chat_keyword_not_duplicated_if_present(self):
        """Test that a pre-existing 'chat' keyword is left alone, not duplicated."""
        npc = chat_npc(keywords=["chat", "talk"])
        assert npc.keywords.count("chat") == 1

    def test_init_chat_attrs_no_keywords_attr(self):
        """Test initialization when keywords attribute doesn't exist."""
        # Not built with chat_npc: ChatHost always assigns ``keywords``, so the
        # factory cannot produce the missing-attribute state this pins.
        class TestNPC(ConversationalNPCMixin):
            def __init__(self):
                self.name = "TestNPC"
                self.charisma = 10
                self.wisdom = 10
                # Don't set keywords
                self._init_chat_attrs()

        npc = TestNPC()
        assert hasattr(npc, "keywords")
        assert npc.keywords == []

    def test_init_chat_attrs_with_config_path(self):
        """Test initialization with character config path."""
        npc = chat_npc(config_path=None)
        assert npc._chat_char_config is None

    def test_prohibited_patterns_are_empty_without_a_character_config(self):
        """Generic NPCs have no authored prohibitions."""
        assert chat_npc()._prohibited_patterns == []


class TestGetAdapter:
    """``_get_adapter`` lazy-loading, caching and failure sentinel.

    Two of the tests this replaces (``test_get_adapter_not_yet_loaded`` and
    ``test_get_adapter_spec_none``) called ``_get_adapter()`` and then asserted
    *nothing* — their only comments were "Either None (failed) or a mock
    adapter" and "Will fail gracefully". Worse, they invoked the real
    ``_load_llm_client_module``, importing ``ai/llm_client.py`` from disk. These
    stub the loader so the outcome is decided by the test, not the environment.
    """

    def test_a_successful_load_is_cached_after_the_first_call(self):
        sentinel = object()
        module = MagicMock()
        module.NpcChatLLMAdapter.get_instance.return_value = sentinel
        npc = chat_npc(init=False, _chat_adapter=None)

        with patch(
            "src.npc._chat_llm._load_llm_client_module", return_value=module
        ) as loader:
            assert npc._get_adapter() is sentinel
            assert npc._get_adapter() is sentinel

        # Cached: the module is loaded once, not once per conversation turn.
        assert loader.call_count == 1
        assert npc._chat_adapter is sentinel

    def test_an_unavailable_module_is_remembered_as_failed(self):
        npc = chat_npc(init=False, _chat_adapter=None)

        with patch(
            "src.npc._chat_llm._load_llm_client_module", return_value=None
        ) as loader:
            assert npc._get_adapter() is None
            assert npc._get_adapter() is None

        # The failure sentinel short-circuits, so a missing LLM does not cost a
        # filesystem import attempt on every single turn.
        assert loader.call_count == 1
        assert npc._chat_adapter is ConversationalNPCMixin._ADAPTER_FAILED

    def test_a_raising_loader_is_swallowed_into_the_failed_sentinel(self):
        """CLAUDE.md: prefer silent recovery over crashing the game loop."""
        npc = chat_npc(init=False, _chat_adapter=None)

        with patch(
            "src.npc._chat_llm._load_llm_client_module",
            side_effect=ImportError("no llm_client on disk"),
        ):
            assert npc._get_adapter() is None

        assert npc._chat_adapter is ConversationalNPCMixin._ADAPTER_FAILED

    def test_an_adapter_that_raises_on_get_instance_is_also_swallowed(self):
        module = MagicMock()
        module.NpcChatLLMAdapter.get_instance.side_effect = RuntimeError("boom")
        npc = chat_npc(init=False, _chat_adapter=None)

        with patch("src.npc._chat_llm._load_llm_client_module", return_value=module):
            assert npc._get_adapter() is None

        assert npc._chat_adapter is ConversationalNPCMixin._ADAPTER_FAILED

    def test_an_already_cached_adapter_is_returned_without_loading(self):
        npc = chat_npc(init=False, _chat_adapter="cached_adapter")

        with patch("src.npc._chat_llm._load_llm_client_module") as loader:
            assert npc._get_adapter() == "cached_adapter"

        loader.assert_not_called()

    def test_the_failed_sentinel_reports_none_rather_than_leaking(self):
        """The sentinel is an internal marker; callers must only ever see None."""
        npc = chat_npc(
            init=False, _chat_adapter=ConversationalNPCMixin._ADAPTER_FAILED
        )

        with patch("src.npc._chat_llm._load_llm_client_module") as loader:
            assert npc._get_adapter() is None

        loader.assert_not_called()


class TestStoryMethod:
    """Test _story helper method."""

    def test_story_with_valid_universe(self):
        """Test _story returns story dict from player."""
        npc = chat_npc(init=False)
        player = MagicMock()
        player.universe.story = {"chapter": 1}
        assert npc._story(player) == {"chapter": 1}

    def test_story_with_missing_universe(self):
        """Test _story returns empty dict when universe missing."""
        npc = chat_npc(init=False)
        player = MagicMock(spec=[])
        result = npc._story(player)
        assert result == {}

    def test_story_with_missing_story_attr(self):
        """Test _story returns empty dict when story attr missing."""
        npc = chat_npc(init=False)
        player = MagicMock()
        player.universe = MagicMock(spec=[])
        result = npc._story(player)
        assert result == {}

    def test_story_with_none_story(self):
        """Test _story returns empty dict when story is None."""
        npc = chat_npc(init=False)
        player = MagicMock()
        player.universe.story = None
        result = npc._story(player)
        assert result == {}


class TestGetChapter:
    """Test _get_chapter helper method."""

    def test_get_chapter_from_story(self):
        """Test chapter retrieval from story dict."""
        npc = chat_npc(init=False)
        player = MagicMock()
        player.universe.story = {"chapter": 2}
        assert npc._get_chapter(player) == "2"

    def test_get_chapter_default(self):
        """Test default chapter when not in story."""
        npc = chat_npc(init=False)
        player = MagicMock()
        player.universe.story = {}
        assert npc._get_chapter(player) == "1"


class TestComputeLoquacity:
    """Test _compute_loquacity loquacity calculation."""

    def test_compute_loquacity_basic(self):
        """Test basic loquacity computation with default base."""
        npc = chat_npc()
        player = chat_player(charisma=10, equipped={}, allies=[])

        npc._compute_loquacity(player)
        assert npc.loquacity_max >= 20  # Min is 20
        assert npc.loquacity_current > 0
        assert npc.loquacity_threshold > 0

    def test_compute_loquacity_caches_result(self):
        """Test loquacity is only computed once."""
        npc = chat_npc(
            loquacity_max=50,
            loquacity_current=50,
            loquacity_threshold=10,
        )
        player = chat_player(charisma=10, equipped={}, allies=[])

        original_max = npc.loquacity_max
        npc._compute_loquacity(player)
        assert npc.loquacity_max == original_max  # Unchanged

    def test_compute_loquacity_npc_charisma_bonus(self):
        """Test NPC charisma bonus to loquacity."""
        npc = chat_npc(charisma=15)
        player = chat_player(charisma=10, equipped={}, allies=[])

        npc._compute_loquacity(player)
        # Charisma 15 gives +5*3=+15 bonus
        assert npc.loquacity_max > 60

    def test_compute_loquacity_reputation_bonus(self):
        """Test positive reputation bonus."""
        npc = chat_npc()
        player = chat_player(
            charisma=10, reputation={"TestNPC": 1}, equipped={}, allies=[]
        )

        npc._compute_loquacity(player)
        # Positive rep gives +20
        assert npc.loquacity_max >= 80

    def test_compute_loquacity_reputation_penalty(self):
        """Test negative reputation penalty."""
        npc = chat_npc()
        player = chat_player(
            charisma=10, reputation={"TestNPC": -1}, equipped={}, allies=[]
        )

        npc._compute_loquacity(player)
        # Negative rep gives -20
        assert npc.loquacity_max < 60

    def test_compute_loquacity_jean_charisma_bonus(self):
        """Test Jean's charisma modifier."""
        npc = chat_npc()
        player = chat_player(charisma=15, equipped={}, allies=[])

        npc._compute_loquacity(player)
        # Jean charisma 15 gives +5*2=+10 bonus
        assert npc.loquacity_max > 60

    def test_compute_loquacity_equipment_bonus(self):
        """Test equipment modifiers."""
        npc = chat_npc()
        player = chat_player(
            charisma=10, equipped={"head": {"name": "Crucifix"}}, allies=[]
        )

        npc._compute_loquacity(player)
        # Crucifix gives +10
        assert npc.loquacity_max > 60

    def test_compute_loquacity_gorran_ally_bonus(self):
        """Test Gorran in allies gives bonus."""
        gorran = MagicMock()
        gorran.name = "Gorran"
        npc = chat_npc()
        player = chat_player(charisma=10, equipped={}, allies=[gorran])

        npc._compute_loquacity(player)
        # Gorran gives +10
        assert npc.loquacity_max > 60

    def test_compute_loquacity_recovery_from_wisdom(self):
        """Test recovery rate derived from wisdom."""
        npc = chat_npc(wisdom=16)
        player = chat_player(charisma=10, equipped={}, allies=[])

        npc._compute_loquacity(player)
        # Wisdom 16 gives recovery = 16 // 8 = 2
        assert npc.loquacity_recovery >= 2

    def test_compute_loquacity_min_threshold(self):
        """Test loquacity threshold has minimum."""
        npc = chat_npc(charisma=1)
        player = chat_player(
            charisma=1, reputation={"TestNPC": -1}, equipped={}, allies=[]
        )

        npc._compute_loquacity(player)
        # Min threshold is 10
        assert npc.loquacity_threshold >= 10


class TestGetNPCKey:
    """Test _get_npc_key persistence key generation."""

    def test_get_npc_key_story_npc(self):
        """Test story NPC uses name as key."""
        npc = chat_npc(
            init=False,
            name="Gorran",
            config_path="/path/to/config.json",
            _chat_char_config={"some": "config"},
            _chat_npc_key=None,
        )
        player = MagicMock()
        player.npc_chat_histories = {}

        key = npc._get_npc_key(player)
        assert key == "Gorran"
        assert npc._chat_npc_key == "Gorran"

    def test_get_npc_key_generic_first_instance(self):
        """Test generic NPC gets unique key."""
        # Not built with chat_npc: the key is type(self).__name__, so this test
        # needs a class of its own to have a name to assert on.
        class CustomNomad(ConversationalNPCMixin):
            def __init__(self):
                self.name = "NomadTrader"
                self._chat_config_path = None
                self._chat_char_config = None
                self._chat_npc_key = None

        npc = CustomNomad()
        player = MagicMock()
        player.npc_chat_histories = {}

        key = npc._get_npc_key(player)
        assert "CustomNomad_0" == key

    def test_get_npc_key_generic_instance_count(self):
        """Test generic NPCs increment instance counter."""
        # Not built with chat_npc: the per-class counter is keyed on
        # type(self).__name__, which a shared host class cannot vary.
        class CustomNomad(ConversationalNPCMixin):
            def __init__(self):
                self.name = "NomadTrader"
                self._chat_config_path = None
                self._chat_char_config = None
                self._chat_npc_key = None

        npc1 = CustomNomad()
        npc2 = CustomNomad()
        player = MagicMock()
        player.npc_chat_histories = {}

        key1 = npc1._get_npc_key(player)
        key2 = npc2._get_npc_key(player)
        assert key1 == "CustomNomad_0"
        assert key2 == "CustomNomad_1"

    def test_get_npc_key_caching(self):
        """Test key is cached after first call."""
        npc = chat_npc(
            init=False,
            config_path=None,
            _chat_char_config=None,
            _chat_npc_key="cached_key",
        )
        player = MagicMock()
        player.npc_chat_histories = {}

        key = npc._get_npc_key(player)
        assert key == "cached_key"


class TestLoadHistoryFromPersistence:
    """Test _load_history_from_persistence."""

    def test_load_history_no_persistence_attr(self):
        """Test loading when player has no npc_chat_histories."""
        npc = chat_npc(
            init=False,
            _chat_history=[],
            _chat_personality=None,
            loquacity_current=0,
            _chat_npc_key="test_key",
        )
        player = MagicMock(spec=[])
        npc._load_history_from_persistence(player)
        assert npc._chat_history == []

    def test_load_history_key_not_found(self):
        """Test loading when key not in histories."""
        npc = chat_npc(
            init=False,
            _chat_history=[],
            _chat_personality=None,
            loquacity_current=0,
            _chat_npc_key="missing_key",
        )
        player = MagicMock()
        player.npc_chat_histories = {"other_key": {}}
        npc._load_history_from_persistence(player)
        assert npc._chat_history == []

    def test_load_history_with_exchanges(self):
        """Test loading exchanges from persistence."""
        npc = chat_npc(
            init=False,
            _chat_history=[],
            _chat_personality=None,
            loquacity_current=0,
            _chat_npc_key="test_key",
        )
        player = MagicMock()
        exchanges = [
            {"npc": "Hello", "jean": "Hi"},
            {"npc": "How are you?", "jean": "Good"},
        ]
        player.npc_chat_histories = {"test_key": {"exchanges": exchanges, "personality": None}}
        npc._load_history_from_persistence(player)
        assert npc._chat_history == exchanges

    def test_load_history_with_personality(self):
        """Test loading personality from persistence."""
        npc = chat_npc(
            init=False,
            _chat_history=[],
            _chat_personality=None,
            loquacity_current=0,
            _chat_npc_key="test_key",
        )
        player = MagicMock()
        personality = {"given_name": "Ren", "voice": "sparse"}
        player.npc_chat_histories = {
            "test_key": {"exchanges": [], "personality": personality}
        }
        npc._load_history_from_persistence(player)
        assert npc._chat_personality == personality

    def test_load_history_with_loquacity(self):
        """Test loading loquacity from persistence."""
        npc = chat_npc(
            init=False,
            _chat_history=[],
            _chat_personality=None,
            loquacity_current=0,
            _chat_npc_key="test_key",
        )
        player = MagicMock()
        player.npc_chat_histories = {"test_key": {"exchanges": [], "loquacity_current": 42}}
        npc._load_history_from_persistence(player)
        assert npc.loquacity_current == 42

    def test_load_history_with_loquacity_exactly_zero(self):
        """A persisted 0 (patience fully exhausted) must be restored as 0, not
        confused with 'never persisted' and silently reset back to a nonzero
        default (issue #381)."""
        npc = chat_npc(
            init=False,
            _chat_history=[],
            _chat_personality=None,
            loquacity_current=99,  # pre-existing nonzero value
            _chat_npc_key="test_key",
        )
        player = MagicMock()
        player.npc_chat_histories = {"test_key": {"exchanges": [], "loquacity_current": 0}}
        npc._load_history_from_persistence(player)
        assert npc.loquacity_current == 0


class TestSaveExchangeToPersistence:
    """Test _save_exchange_to_persistence."""

    def test_save_exchange_initializes_missing_persistence_attr(self):
        """A fresh Player has no npc_chat_histories (same gotcha as
        player.reputation — see CLAUDE.md). This used to make the save
        silently no-op forever; it must now initialize the dict in place and
        actually persist the exchange, whether the attribute was never set
        or was explicitly None.
        """
        npc = chat_npc(
            init=False,
            loquacity_current=50,
            loquacity_max=100,
            _chat_npc_key="test_key",
            _chat_personality=None,
        )
        player = MagicMock(spec=["universe"])
        player.npc_chat_histories = None
        npc._save_exchange_to_persistence(player, "NPC text", "Jean text", 10, "1")

        assert player.npc_chat_histories is not None
        entry = player.npc_chat_histories["test_key"]
        assert entry["exchanges"] == [
            {"npc": "NPC text", "jean": "Jean text", "game_tick": 10, "chapter": "1"}
        ]

    def test_save_exchange_creates_entry(self):
        """Test creating new history entry."""
        npc = chat_npc(
            init=False,
            loquacity_current=50,
            loquacity_max=100,
            _chat_npc_key="test_key",
            _chat_personality=None,
        )
        player = MagicMock()
        player.npc_chat_histories = {}
        npc._save_exchange_to_persistence(player, "Hello", "Hi", 10, "1")
        assert "test_key" in player.npc_chat_histories
        entry = player.npc_chat_histories["test_key"]
        assert len(entry["exchanges"]) == 1
        assert entry["exchanges"][0]["npc"] == "Hello"
        assert entry["exchanges"][0]["jean"] == "Hi"

    def test_save_exchange_keeps_last_20(self):
        """Test that only last 20 exchanges are kept."""
        npc = chat_npc(
            init=False,
            loquacity_current=50,
            loquacity_max=100,
            _chat_npc_key="test_key",
            _chat_personality=None,
        )
        player = MagicMock()
        exchanges = [{"npc": f"msg{i}", "jean": f"response{i}"} for i in range(25)]
        player.npc_chat_histories = {"test_key": {"exchanges": exchanges}}
        npc._save_exchange_to_persistence(player, "new", "response", 30, "1")
        # Should keep only last 20
        assert len(player.npc_chat_histories["test_key"]["exchanges"]) == 20

    def test_save_exchange_does_not_bump_conversation_count(self):
        """_save_exchange_to_persistence never touches conversation_count.

        _bump_conversation_count is the single owner of the counter (both
        chat_open and chat_respond persist rows with jean_text="", so a
        jean_text-truthy increment here would never fire for either caller —
        it was dead code and has been removed).
        """
        npc = chat_npc(
            init=False,
            loquacity_current=50,
            loquacity_max=100,
            _chat_npc_key="test_key",
            _chat_personality=None,
        )
        player = MagicMock()
        player.npc_chat_histories = {}
        # Even with a non-empty jean_text, the count stays untouched.
        npc._save_exchange_to_persistence(player, "Hello", "Hi", 10, "1")
        assert player.npc_chat_histories["test_key"]["conversation_count"] == 0
        npc._save_exchange_to_persistence(player, "Hello again", "", 11, "1")
        assert player.npc_chat_histories["test_key"]["conversation_count"] == 0
        # Only _bump_conversation_count increments it.
        npc._bump_conversation_count(player)
        assert player.npc_chat_histories["test_key"]["conversation_count"] == 1

    def test_save_exchange_stores_personality(self):
        """Test personality is stored when present."""
        npc = chat_npc(
            init=False,
            loquacity_current=50,
            loquacity_max=100,
            _chat_npc_key="test_key",
            _chat_personality={"given_name": "Ren"},
        )
        player = MagicMock()
        player.npc_chat_histories = {}
        npc._save_exchange_to_persistence(player, "Hello", "Hi", 10, "1")
        assert player.npc_chat_histories["test_key"]["personality"] == {"given_name": "Ren"}


class TestBuildSystemPrompt:
    """``_build_system_prompt`` — the thing actually sent to the model.

    Every test here previously passed ``MagicMock()`` as the player. That mock
    answers ``player.universe.story.get("chapter")`` with a *MagicMock*, which
    the prompt then f-string-interpolates, so the assembled prompt really read
    ``It is currently chapter <MagicMock name='mock.universe.story.get()'
    id='140461507550032'>``. Every assertion still passed, because they only
    looked for substrings elsewhere in the text. These use a real
    ``Player``/``Universe`` and assert no mock repr survives.
    """

    @pytest.fixture
    def player(self):
        return live_world()[0]

    def test_generic_npc_prompt_is_built_from_its_personality(self, player):
        npc = chat_npc(
            init=False,
            name="Nomad",
            _chat_world_facts={},
            _chat_char_config=None,
            _chat_personality={
                "given_name": "Tal",
                "voice": "methodical",
                "knowledge": ["trade routes", "water caches"],
            },
        )

        prompt = npc._build_system_prompt(player)

        assert "You are Tal, a nomad. methodical." in prompt
        assert "You know about trade routes, water caches." in prompt
        assert "Jean is he/him. Do not write Jean's dialogue." in prompt
        assert "MagicMock" not in prompt

    def test_generic_npc_prompt_falls_back_with_no_personality(self, player):
        npc = chat_npc(
            init=False,
            name="Nomad",
            _chat_world_facts={},
            _chat_char_config=None,
            _chat_personality=None,
        )

        prompt = npc._build_system_prompt(player)

        assert "You are Nomad, a nomad. terse." in prompt
        assert "You know about survival." in prompt

    def test_story_npc_prompt_carries_the_authored_config(self, player):
        npc = chat_npc(
            init=False,
            name="Gorran",
            _chat_world_facts={},
            _chat_char_config={
                "system_prompt_snippet": "Gorran is a Golemite who travels with Jean.",
                "role": "companion",
                "knowledge_scope": ["Golemite rites", "stonework"],
                "personality_notes": ["Speaks rarely.", "Watches first."],
            },
            _chat_personality=None,
        )

        prompt = npc._build_system_prompt(player)

        assert "Gorran is a Golemite who travels with Jean." in prompt
        assert "Role: companion." in prompt
        assert "You can speak to: Golemite rites; stonework." in prompt
        assert "About you: Speaks rarely. Watches first." in prompt
        # A story NPC must NOT also get the synthesized nomad block.
        assert "a nomad." not in prompt

    def test_story_npc_prompt_omits_absent_config_sections(self, player):
        npc = chat_npc(
            init=False,
            name="Gorran",
            _chat_world_facts={},
            _chat_char_config={"system_prompt_snippet": "Gorran is a friend"},
            _chat_personality=None,
        )

        prompt = npc._build_system_prompt(player)

        assert "Gorran is a friend" in prompt
        assert "Role:" not in prompt
        assert "You can speak to:" not in prompt
        assert "About you:" not in prompt

    def test_world_facts_block_is_assembled_in_full(self, player):
        npc = chat_npc(
            init=False,
            name="TestNPC",
            _chat_world_facts={
                "world_name": "Aurelion",
                "brief_description": "A dangerous world",
                "geography": ["Badlands", "Grondite"],
                "factions_and_peoples": ["Crusaders", "Nomads"],
                "world_rules": ["Magic is forbidden"],
                "tone_notes": "Dark and medieval",
            },
            _chat_char_config=None,
            _chat_personality=None,
        )

        prompt = npc._build_system_prompt(player)

        assert prompt.startswith(
            "WORLD: Aurelion. A dangerous world\n"
            "Places: Badlands, Grondite.\n"
            "Peoples: Crusaders, Nomads.\n"
            "Magic is forbidden\n"
            "Tone: Dark and medieval"
        )

    def test_no_world_facts_means_no_world_block(self, player):
        npc = chat_npc(
            init=False,
            name="TestNPC",
            _chat_world_facts={},
            _chat_char_config=None,
            _chat_personality={"given_name": "Ren", "voice": "sparse"},
        )

        prompt = npc._build_system_prompt(player)

        assert "WORLD:" not in prompt
        assert prompt.startswith("You are Ren, a nomad.")

    @pytest.mark.parametrize("chapter", ["1", "2", "7"])
    def test_the_real_story_chapter_reaches_the_spoiler_guard(self, player, chapter):
        """The spoiler guard is only meaningful if it names the true chapter."""
        player.universe.story["chapter"] = chapter
        npc = chat_npc(
            init=False,
            name="TestNPC",
            _chat_world_facts={},
            _chat_char_config=None,
            _chat_personality=None,
        )

        prompt = npc._build_system_prompt(player)

        assert f"It is currently chapter {chapter}." in prompt
        assert f"JEAN'S KNOWN CONTEXT (chapter {chapter})" in prompt

    def test_chapter_defaults_to_one_for_a_fresh_game(self, player):
        npc = chat_npc(
            init=False,
            name="TestNPC",
            _chat_world_facts={},
            _chat_char_config=None,
            _chat_personality=None,
        )

        assert "It is currently chapter 1." in npc._build_system_prompt(player)


class TestBuildJeanContextBlock:
    """``_build_jean_context_block`` — chapter-gates Jean's own dialogue options."""

    @pytest.fixture
    def player(self):
        return live_world()[0]

    @pytest.fixture
    def npc(self):
        return chat_npc(
            init=False,
            name="TestNPC",
            _chat_world_facts={},
            _chat_char_config=None,
            _chat_personality={"given_name": "Ren", "voice": "sparse"},
        )

    def test_includes_chapter_number(self, npc, player):
        assert "chapter 2" in npc._build_jean_context_block(player, "2")

    def test_defaults_to_no_unusual_developments(self, npc, player):
        block = npc._build_jean_context_block(player, "1")
        assert "Nothing unusual beyond ordinary travel" in block
        assert "words rather than only gesture" not in block

    @pytest.mark.parametrize("stage", ["1", "2", "3"])
    def test_includes_gorran_language_flag_once_he_speaks(self, npc, player, stage):
        player.universe.story["gorran_language_stage"] = stage
        block = npc._build_jean_context_block(player, "1")
        assert "Gorran" in block
        assert "words rather than only gesture" in block
        assert "Nothing unusual beyond ordinary travel" not in block

    def test_omits_gorran_flag_at_stage_zero(self, npc, player):
        """A fresh game starts at stage "0" — the string is truthy, so the flag
        has to be compared, not merely tested for presence. A MagicMock player
        made this branch unreachable."""
        assert player.universe.story["gorran_language_stage"] == "0"
        block = npc._build_jean_context_block(player, "1")
        assert "words rather than only gesture" not in block

    def test_included_in_full_system_prompt(self, npc, player):
        """The Jean-context block must actually be wired into the system prompt
        the adapter receives, not just callable in isolation."""
        player.universe.story["gorran_language_stage"] = "1"
        prompt = npc._build_system_prompt(player)
        assert "JEAN'S KNOWN CONTEXT" in prompt
        assert "words rather than only gesture" in prompt
        assert npc._build_jean_context_block(player, "1") in prompt


class TestEnsurePersonality:
    """Test _ensure_personality generation."""

    def test_ensure_personality_already_story_npc(self):
        """Test personality skipped for story NPCs."""
        npc = chat_npc(
            init=False,
            name="Gorran",
            _chat_char_config={"some": "config"},
            _chat_personality=None,
        )
        npc._ensure_personality(MagicMock())
        assert npc._chat_personality is None

    def test_ensure_personality_already_generated(self):
        """Test personality skipped if already generated."""
        npc = chat_npc(
            init=False,
            _chat_char_config=None,
            _chat_personality={"given_name": "Ren"},
        )
        npc._ensure_personality(MagicMock())
        assert npc._chat_personality == {"given_name": "Ren"}

    def test_ensure_personality_fallback_picks_a_real_generic_profile(self):
        """With no adapter, the NPC must still end up with a usable persona.

        The old assertion (``is not None`` plus ``"given_name" in ...``) would
        have passed on any dict the fallback happened to build. This pins the
        chosen profile to an actual entry of ``_GENERIC_FALLBACKS`` and proves
        it is a *copy*, so mutating one nomad's persona cannot rewrite the
        shared module-level pool for every other nomad in the world.
        """
        from src.npc._chat_llm import _GENERIC_FALLBACKS

        npc = chat_npc(
            init=False,
            name="NomadA",
            _chat_char_config=None,
            _chat_personality=None,
            _chat_npc_key="NomadA_0",
        )
        npc._get_adapter = lambda: None

        npc._ensure_personality(live_world()[0])

        assert npc._chat_personality in _GENERIC_FALLBACKS
        assert all(npc._chat_personality is not f for f in _GENERIC_FALLBACKS)
        npc._chat_personality["given_name"] = "Mutated"
        assert all(f.get("given_name") != "Mutated" for f in _GENERIC_FALLBACKS)

    def test_ensure_personality_is_stable_for_one_npc_key(self):
        """The same persistence key must resolve to the same persona.

        NB: only *within a process*. ``_ensure_personality`` selects via
        ``hash(key)``, and Python randomizes string hashing per interpreter
        run, so the same nomad draws a different persona on each game launch
        until the first conversation is persisted. Reported as a product bug
        alongside this change; asserting cross-process stability here would
        make this test flaky rather than fix it.
        """
        def build():
            npc = chat_npc(
                init=False,
                name="NomadA",
                _chat_char_config=None,
                _chat_personality=None,
                _chat_npc_key="NomadA_0",
            )
            npc._get_adapter = lambda: None
            npc._ensure_personality(live_world()[0])
            return npc._chat_personality

        assert build() == build()

    def test_different_keys_can_draw_different_personas(self):
        """The pool is indexed by key, so distinct nomads are not all identical."""
        from src.npc._chat_llm import _GENERIC_FALLBACKS

        personas = set()
        for i in range(40):
            npc = chat_npc(
                init=False,
                name=f"Nomad{i}",
                _chat_char_config=None,
                _chat_personality=None,
                _chat_npc_key=f"Nomad_{i}",
            )
            npc._get_adapter = lambda: None
            npc._ensure_personality(live_world()[0])
            personas.add(npc._chat_personality.get("given_name"))

        assert len(personas) == len(_GENERIC_FALLBACKS)

    def test_a_story_npc_with_a_config_keeps_its_authored_persona(self):
        """``_ensure_personality`` is a no-op once a character config exists."""
        npc = chat_npc(
            init=False,
            _chat_char_config={"given_name": "Mara"},
            _chat_personality=None,
        )
        npc._get_adapter = lambda: (_ for _ in ()).throw(
            AssertionError("must not consult the LLM for a story NPC")
        )

        npc._ensure_personality(live_world()[0])

        assert npc._chat_personality is None


class TestJaccard:
    """Test _jaccard similarity."""

    def test_jaccard_identical_text(self):
        """Test Jaccard of identical text is 1.0."""
        sim = chat_npc(init=False)._jaccard("hello world", "hello world")
        assert sim == 1.0

    def test_jaccard_completely_different(self):
        """Test Jaccard of completely different text is 0.0."""
        sim = chat_npc(init=False)._jaccard("hello world", "foo bar")
        assert sim == 0.0

    def test_jaccard_partial_overlap(self):
        """Test Jaccard with partial overlap."""
        sim = chat_npc(init=False)._jaccard("hello world test", "hello foo bar")
        assert 0 < sim < 1

    def test_jaccard_empty_strings(self):
        """Test Jaccard with empty strings."""
        sim = chat_npc(init=False)._jaccard("", "")
        assert sim == 1.0

    def test_jaccard_one_empty(self):
        """Test Jaccard with one empty string."""
        sim = chat_npc(init=False)._jaccard("hello", "")
        assert sim == 0.0


class TestQCNpcText:
    """The ``_qc_npc_text`` pipeline, asserted on its actual output text.

    Every case here previously asserted ``result is not None`` (or hid behind
    ``if result:``), which passes for *any* string the pipeline happens to
    return — including the mangled ones two of these now pin deliberately.
    """

    @pytest.mark.parametrize(
        "noise",
        ["", "   ", "k", "-- ...", "...", "-", "!?"],
        ids=["empty", "whitespace", "one-char", "dashes-dots", "ellipsis", "dash", "punct"],
    )
    def test_rejects_near_empty_noise(self, noise):
        """Below the 2-char floor, or no alphanumeric content at all."""
        assert qc_npc()._qc_npc_text(noise, []).text is None

    @pytest.mark.parametrize("terse", ["No.", "I see.", "Not now.", "Fine."])
    def test_allows_terse_in_character_replies(self, terse):
        """Regression: several NPCs are authored with terse, economical voices
        (Mara: "Says half of what she means") and can legitimately reply with
        something under 10 characters. A flat length floor used to reject these
        on every single turn, forcing a retry or fallback for exactly the NPCs
        whose voice most called for short answers. The text must come back
        *unchanged* — not merely non-None.
        """
        assert qc_npc()._qc_npc_text(terse, []).text == terse

    def test_clean_text_passes_through_verbatim(self):
        assert qc_npc()._qc_npc_text("This is a valid sentence.", []).text == (
            "This is a valid sentence."
        )

    @pytest.mark.parametrize(
        "jean_line",
        [
            "Jean said hello to me today.",
            "Jean replied that the road was closed.",
            "Jean asked about the mountain.",
            "Jean told me the truth.",
            'Jean: "Hello"',
            "jean: 'go on'",
        ],
    )
    def test_rejects_text_that_puts_words_in_jeans_mouth(self, jean_line):
        """The NPC speaks only for itself; narrating Jean is a hard reject."""
        assert qc_npc()._qc_npc_text(jean_line, []).text is None

    def test_mentioning_jean_without_speech_verbs_is_allowed(self):
        """The guard is about Jean *speaking*, not about naming him."""
        assert qc_npc()._qc_npc_text("Jean looks tired from the road.", []).text == (
            "Jean looks tired from the road."
        )

    def test_truncates_over_300_chars_at_a_sentence_boundary(self):
        """Cut back to the last ``.!?`` before position 300, then capped at 3
        sentences — so the result is the first three sentences, whole."""
        long_text = "This is a very long text. " * 20
        assert len(long_text) > 300
        result = qc_npc()._qc_npc_text(long_text, []).text
        assert result == (
            "This is a very long text. This is a very long text. "
            "This is a very long text."
        )
        assert len(result) <= 300

    def test_truncation_falls_back_to_a_hard_cut_without_a_boundary(self):
        """No ``.!?`` in the first 300 chars means a flat 300-char slice."""
        result = qc_npc()._qc_npc_text("word " * 100, []).text
        # 300-char slice, then terminal punctuation, then the 3-sentence cap
        # leaves a single sentence.
        assert result.endswith(".")
        assert len(result) <= 301
        assert result.startswith("word word word")

    @pytest.mark.parametrize(
        "raw, expected",
        [
            # The removed span is cleaned up after the substitution: no doubled
            # space, no orphan leading comma, and the sentence is recapitalised.
            # (Master pinned the doubled-space/orphan-comma artifacts as "the
            # engine's real output"; this branch fixed them, so the expectations
            # move rather than the behaviour.)
            ("Okay that's cool to me.", "That's cool to me."),
            ("I wanna tell you something important.", "I tell you something important."),
            ("Those guns are dangerous weapons.", "Those are dangerous weapons."),
            ("Yeah, that's cool okay?", "That's cool?"),
        ],
        ids=["okay", "wanna", "guns", "stacked"],
    )
    def test_strips_modern_slang(self, raw, expected):
        assert qc_npc()._qc_npc_text(raw, []).text == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [
            # -ia / -on / -or read as places; anything else as a person/group.
            (
                "I saw Mysteria in the wilderness last night.",
                "I saw that place in the wilderness last night.",
            ),
            (
                "The journey to Oblivion was long and dangerous.",
                "The journey to that place was long and dangerous.",
            ),
            # Heuristic limitation, pinned deliberately: a *person* whose title
            # ends in -or is also rewritten as a place.
            ("I met Emperor at the gate last week.", "I met that place at the gate last week."),
            ("I saw Xanthor in the wilderness.", "I saw that place in the wilderness."),
            ("I spoke with Bellweather yesterday.", "I spoke with someone yesterday."),
        ],
        ids=["ia", "on", "or-person", "or", "person"],
    )
    def test_replaces_invented_proper_nouns(self, raw, expected):
        assert qc_npc(allowed_proper_nouns=[])._qc_npc_text(raw, []).text == expected

    def test_replaces_every_occurrence_of_an_invented_noun(self):
        result = qc_npc(allowed_proper_nouns=[])._qc_npc_text(
            "The kingdom of Mysteria has many towers and the people of Mysteria "
            "speak of Mysteria with great pride.",
            [],
        ).text
        assert "Mysteria" not in result
        assert result.count("that place") == 3

    def test_world_allowed_nouns_survive_the_scan(self):
        npc = qc_npc(allowed_proper_nouns=["Grondite"])
        assert npc._qc_npc_text("The vein of Grondite runs deep.", []).text == (
            "The vein of Grondite runs deep."
        )

    @pytest.mark.parametrize("always_allowed", ["Jean", "Gorran", "TestNPC"])
    def test_the_speaker_jean_and_gorran_are_always_allowed(self, always_allowed):
        """``_qc_npc_text`` adds these three to the allow-list unconditionally."""
        text = f"I walked with {always_allowed} through the pass."
        assert qc_npc(allowed_proper_nouns=[])._qc_npc_text(text, []).text == text

    def test_sentence_initial_capitals_are_not_treated_as_proper_nouns(self):
        """Ordinary capitalization must not be mangled into "they"."""
        text = "Rain falls hard. Cold seeps through the stone."
        assert qc_npc(allowed_proper_nouns=[])._qc_npc_text(text, []).text == text

    def test_adds_terminal_punctuation(self):
        assert qc_npc()._qc_npc_text("This is a sentence without punctuation", []).text == (
            "This is a sentence without punctuation."
        )

    def test_caps_output_at_three_sentences(self):
        assert qc_npc()._qc_npc_text("First. Second. Third. Fourth. Fifth.", []).text == (
            "First. Second. Third."
        )

    def test_rejects_a_near_duplicate_of_a_recent_line(self):
        """Jaccard > 0.7 against any of the last 8 NPC lines is a reject; the
        caller's retry loop then asks the model again."""
        history = [{"npc": "The river is cold this time of year"}]
        assert qc_npc()._qc_npc_text("The river is cold this time of year", history).text is None

    def test_allows_a_merely_similar_line(self):
        """Below the 0.7 threshold the line goes through unchanged."""
        history = [{"npc": "The river is cold this time of year"}]
        text = "The mountain pass is closed until spring."
        assert qc_npc()._qc_npc_text(text, history).text == text

    def test_repetition_guard_only_looks_at_the_last_eight_lines(self):
        """A line repeated from nine turns ago is allowed back."""
        history = [{"npc": "The river is cold this time of year"}] + [
            {"npc": f"filler line number {i} here"} for i in range(8)
        ]
        assert qc_npc()._qc_npc_text("The river is cold this time of year", history).text == (
            "The river is cold this time of year."
        )

    def test_applies_prohibited_phrase_substitution(self):
        """Story-character prohibited phrases are excised, not placeholdered.

        Master pinned the old output verbatim -- ``This [. ] word should be
        replaced.`` -- because step 9 split the ``[...]`` placeholder's dots as
        sentence boundaries.  This branch removes the span and closes the gap
        instead, so the placeholder never reaches the player.  The assertion is
        still on the exact text: the previous one was ``result is not None``,
        which is why nobody noticed the artifact for so long.
        """
        npc = qc_npc(prohibited=["forbidden"])
        assert npc._qc_npc_text("This forbidden word should be replaced.", []).text == (
            "This word should be replaced."
        )
        assert "[" not in npc._qc_npc_text("A forbidden thing.", []).text

    def test_prohibited_phrase_matching_is_case_insensitive(self):
        npc = qc_npc(prohibited=["forbidden"])
        assert "Forbidden" not in npc._qc_npc_text("A Forbidden thing was seen.", []).text


class TestQCJeanOptions:
    """``_qc_jean_options`` — the three replies offered to the player.

    Rewritten from eight copy-pasted methods, one of which
    (``test_qc_jean_options_dedup``) called the method and then asserted
    *nothing at all*, and one of which hid its only assertion behind
    ``if result:``.

    The salvage policy is this branch's: a malformed option is dropped on its
    own rather than discarding the whole set, and the caller
    (``_top_up_jean_options``) refills from the authored pool. The method
    therefore returns a possibly-empty ``list`` and **never** ``None``.
    """

    @pytest.fixture(scope="class")
    def npc(self):
        return chat_npc(init=False)

    @pytest.mark.parametrize(
        "options",
        ["not a list", None, {"text": "a dict, not a list"}, [], 7],
        ids=["string", "none", "dict", "empty", "int"],
    )
    def test_an_unusable_container_yields_an_empty_list(self, npc, options):
        """Never ``None`` — a ``None`` return would blow up the caller's
        ``_top_up_jean_options(...)`` slice."""
        assert npc._qc_jean_options(options) == []

    @pytest.mark.parametrize(
        "bad",
        [
            "a bare string, not a dict",
            None,
            {"tone": "open"},
            {"text": "x"},
            {"text": "x" * 161},
            {"text": "   "},
            {"text": "[Option 1] Choose wisely"},
            {"text": "As Jean, I would ask about the road"},
            {"text": "I don't know what to say"},
            # The guard's regex is "I don.t know what to say" — the wildcard
            # covers a curly apostrophe as well as a straight one.
            {"text": "I don’t know what to say"},
        ],
        ids=[
            "not-a-dict",
            "none-entry",
            "missing-text",
            "too-short",
            "too-long",
            "blank",
            "bracketed",
            "as-jean",
            "straight-apostrophe",
            "curly-apostrophe",
        ],
    )
    def test_one_bad_option_is_dropped_and_the_rest_survive(self, npc, bad):
        """Salvage, not wholesale rejection: the two good siblings must reach
        the player even though the first entry is unusable."""
        result = npc._qc_jean_options(
            [bad, {"text": "Tell me about the road"}, {"text": "Where were you headed"}]
        )
        assert [o["text"] for o in result] == [
            "Tell me about the road",
            "Where were you headed",
        ]

    def test_a_dropped_leading_option_does_not_leave_a_hole_in_the_tone_cycle(
        self, npc
    ):
        """Tones are keyed on the KEPT position, not the source position, so a
        dropped option at index 0 must not cost the player the "direct" reply."""
        result = npc._qc_jean_options(
            [
                {"text": "x"},
                {"text": "Tell me about the road"},
                {"text": "Where were you headed"},
            ]
        )
        assert [o["tone"] for o in result] == ["direct", "guarded"]

    def test_a_missing_apostrophe_slips_past_the_meta_speech_guard(self, npc):
        """Pinned limitation: the regex requires *some* character where the
        apostrophe goes, so "I dont know what to say" reaches the player."""
        options = [
            {"text": "I dont know what to say"},
            {"text": "Second option"},
            {"text": "Third option"},
        ]
        assert npc._qc_jean_options(options)[0]["text"] == "I dont know what to say"

    def test_the_later_of_a_near_duplicate_pair_is_dropped(self, npc):
        """Jaccard > 0.6 between any pair. The test this replaces ended with a
        comment ("Might be rejected due to similarity") and no assertion."""
        options = [
            {"text": "Tell me more about this"},
            {"text": "Tell me more about that"},
            {"text": "Something completely different"},
        ]
        assert [o["text"] for o in npc._qc_jean_options(options)] == [
            "Tell me more about this",
            "Something completely different",
        ]

    def test_valid_options_pass_through_with_their_tones(self, npc):
        options = [
            {"text": "Tell me more", "tone": "open"},
            {"text": "I will keep that in mind", "tone": "guarded"},
            {"text": "What else?", "tone": "direct"},
        ]
        assert npc._qc_jean_options(options) == [
            {"tone": "open", "text": "Tell me more"},
            {"tone": "guarded", "text": "I will keep that in mind"},
            {"tone": "direct", "text": "What else?"},
        ]

    def test_an_unusable_tone_falls_back_to_the_positional_default(self, npc):
        """Missing or nonsense tones become direct/guarded/open by position, so
        the UI always has one button of each colour."""
        options = [
            {"text": "Tell me more", "tone": "invalid"},
            {"text": "Second option"},
            {"text": "Third option"},
        ]
        assert npc._qc_jean_options(options) == [
            {"tone": "direct", "text": "Tell me more"},
            {"tone": "guarded", "text": "Second option"},
            {"tone": "open", "text": "Third option"},
        ]

    def test_tone_matching_is_case_insensitive(self, npc):
        options = [
            {"text": "Tell me more", "tone": "OPEN"},
            {"text": "Second option"},
            {"text": "Third option"},
        ]
        assert npc._qc_jean_options(options)[0]["tone"] == "open"

    def test_only_the_first_three_options_are_kept(self, npc):
        options = [
            {"text": "Aaaa aaaa"},
            {"text": "Bbbb bbbb"},
            {"text": "Cccc cccc"},
            {"text": "Dddd dddd"},
        ]
        result = npc._qc_jean_options(options)
        assert [o["text"] for o in result] == ["Aaaa aaaa", "Bbbb bbbb", "Cccc cccc"]

    def test_the_whole_list_is_validated_before_it_is_cut_to_three(self, npc):
        """Slicing first made a good option at index 3 unreachable whenever an
        earlier one was malformed — the salvage this exists to provide,
        defeated by the first line of its own loop."""
        options = [
            {"text": "x"},
            {"text": "y"},
            {"text": "z"},
            {"text": "Aaaa aaaa"},
            {"text": "Bbbb bbbb"},
        ]
        assert [o["text"] for o in npc._qc_jean_options(options)] == [
            "Aaaa aaaa",
            "Bbbb bbbb",
        ]

    def test_only_the_first_twelve_candidates_are_scanned(self, npc):
        """``_MAX_OPTION_CANDIDATES`` bounds the work a hostile or rambling
        model can cause; the 13th entry is never looked at."""
        options = [{"text": "x"}] * 12 + [{"text": "Reachable option here"}]
        assert npc._qc_jean_options(options) == []

    def test_option_text_is_stripped(self, npc):
        options = [
            {"text": "   Padded out here   "},
            {"text": "Second option"},
            {"text": "Third option"},
        ]
        assert npc._qc_jean_options(options)[0]["text"] == "Padded out here"

    @pytest.mark.parametrize("length", [_MIN_OPTION_CHARS, MAX_OPTION_CHARS])
    def test_the_length_bounds_are_inclusive(self, npc, length):
        """``MAX_OPTION_CHARS`` is the single shared bound the llm_client
        truncates at and this filter drops at.

        Imported rather than written as 160: a literal here is the bug written
        down as a test — retune the constant and this keeps asserting the old
        number, which is precisely the drift the shared constant exists to stop.
        """
        options = [
            {"text": "x" * length},
            {"text": "Second option"},
            {"text": "Third option"},
        ]
        assert npc._qc_jean_options(options)[0]["text"] == "x" * length


class TestChatOpen:
    """``chat_open`` — the first turn of a conversation."""

    @pytest.fixture
    def player(self):
        return live_world()[0]

    def test_the_llm_line_reaches_the_player_and_the_history(self, player):
        """The old version of this test asserted ``"npc_opening" in result`` and
        ``isinstance(result["jean_options"], list)`` — both true for *any*
        opening, including an empty string and an empty list."""
        adapter = ScriptedAdapter(npc_text="The pass is shut until the thaw.")
        npc = ready_npc(adapter)

        result = npc.chat_open(player)

        assert result["success"] is True
        assert result["npc_opening"] == "The pass is shut until the thaw."
        assert result["npc_name"] == "Ren"
        assert result["llm_available"] is True
        assert result["turn"] == 0
        assert result["conversation_ended"] is False
        assert [o["text"] for o in result["jean_options"]] == [
            o["text"] for o in ScriptedAdapter.VALID_OPTIONS
        ]
        assert [o["tone"] for o in result["jean_options"]] == [
            "direct",
            "guarded",
            "open",
        ]
        # ...and it is persisted, so a reload resumes mid-conversation.
        stored = player.npc_chat_histories[result["npc_key"]]["exchanges"]
        assert stored == [
            {
                "npc": "The pass is shut until the thaw.",
                "jean": "",
                "game_tick": 0,
                "chapter": "1",
            }
        ]

    def test_the_adapter_receives_the_assembled_system_prompt(self, player):
        """What is *sent* is the part a mock-return assertion never checks."""
        adapter = ScriptedAdapter()
        npc = ready_npc(
            adapter,
            _chat_world_facts={
                "world_name": "Aurelion",
                "geography": ["Badlands"],
                "factions_and_peoples": ["Crusaders"],
            },
            _chat_personality={"given_name": "Tal", "voice": "methodical"},
        )

        npc.chat_open(player)

        assert len(adapter.prompts) == 1
        prompt = adapter.prompts[0]
        assert "WORLD: Aurelion." in prompt          # world state
        assert "You are Tal, a nomad. methodical." in prompt  # persona
        assert "It is currently chapter 1." in prompt         # spoiler guard
        assert "Do not write Jean's dialogue" in prompt
        assert "MagicMock" not in prompt

    def test_a_disabled_adapter_falls_back_to_the_authored_pool(self, player):
        npc = ready_npc(ScriptedAdapter(enabled=False))

        result = npc.chat_open(player)

        assert result["success"] is True
        assert result["llm_available"] is False
        assert result["npc_opening"] == "Nothing to say right now."
        assert len(result["jean_options"]) == 3

    def test_qc_rejected_llm_text_falls_back_rather_than_shipping_it(self, player):
        """A model that narrates Jean must not reach the player at all."""
        npc = ready_npc(ScriptedAdapter(npc_text="Jean said he was tired."))

        result = npc.chat_open(player)

        assert "Jean said" not in result["npc_opening"]
        assert result["npc_opening"] == "Nothing to say right now."
        assert result["llm_available"] is False

    def test_exhausted_loquacity_brushes_jean_off_without_options(self, player):
        """A story NPC's authored closing line is used verbatim."""
        npc = ready_npc(
            loquacity_current=5,
            loquacity_threshold=20,
            _chat_char_config={"closing_lines_when_exhausted": ["I have said enough."]},
        )
        npc._compute_loquacity = lambda player: None

        result = npc.chat_open(player)

        assert result["success"] is True
        assert result["conversation_ended"] is True
        assert result["jean_options"] == []
        assert result["npc_opening"] == "I have said enough."

    def test_a_generic_npc_brushes_off_with_a_line_from_the_pool(self, player):
        """No authored config, so one of three generic lines.

        NB: which one is selected via ``hash(self.name) % 3``, and Python
        randomizes string hashing per interpreter run — so the same NPC gives a
        different brush-off on every game launch. Reported as a product bug
        alongside this change; asserting a specific line here would be flaky.
        """
        npc = ready_npc(loquacity_current=5, loquacity_threshold=20)
        npc._compute_loquacity = lambda player: None

        result = npc.chat_open(player)

        assert result["npc_opening"] in (
            "They're not in the mood to talk.",
            "A brief shake of the head.",
            "Not now.",
        )
        assert result["conversation_ended"] is True
        assert result["jean_options"] == []

    def test_an_internal_error_returns_a_structured_failure(self, player):
        """``chat_open`` must never propagate — the game loop keeps running.

        Master asserted the raw ``"Test error"`` string here; the client-facing
        message is now a fixed generic one, with the detail kept server-side by
        ``logger.error(..., exc_info=True)``.
        """
        npc = ready_npc()
        npc._compute_loquacity = lambda player: (_ for _ in ()).throw(
            ValueError("Test error")
        )

        result = npc.chat_open(player)

        assert result == {
            "success": False,
            "error": "Conversation failed — try again.",
        }

    @pytest.mark.parametrize(
        "malformed",
        [None, {}, {"npc_text": ""}, {"npc_text": None}],
        ids=["none", "empty-dict", "empty-text", "null-text"],
    )
    def test_an_empty_llm_response_falls_back_cleanly(self, player, malformed):
        class _Empty:
            enabled = True

            def generate_npc_turn(self, *args, **kwargs):
                return malformed

            def generate_jean_options(self, *args, **kwargs):
                return None

            def generate_personality(self, class_name):
                return None

        result = ready_npc(_Empty()).chat_open(player)

        assert result["success"] is True
        assert result["llm_available"] is False
        assert result["npc_opening"] == "Nothing to say right now."

    @pytest.mark.parametrize(
        "malformed, leaked_detail",
        [
            ("just a string", "has no attribute"),
            ([1, 2, 3], "has no attribute"),
            ({"npc_text": 12345}, "has no attribute"),
        ],
        ids=["string", "list", "non-string-text"],
    )
    def test_a_malformed_llm_response_aborts_instead_of_falling_back(
        self, player, malformed, leaked_detail
    ):
        """PRODUCT BUG, pinned here so it is visible rather than silent.

        An adapter that *raises* is now handled (see the test below), but a
        response of the wrong *shape* still escapes ``_generate_turn`` into
        ``chat_open``'s outer handler, so Jean gets ``success: False`` instead of
        the authored fallback line the pool exists to provide. CLAUDE.md's
        stated policy is "prefer silent recovery over crashing the game loop",
        and ``_run_npc_turn`` already documents itself as returning None "if the
        caller should fall back".

        The conversation is at least not *crashed*, and the raw
        ``AttributeError`` text no longer reaches the client. When the fallback
        is fixed, this test should expect ``success: True`` and the pool line.
        """
        class _Malformed:
            enabled = True

            def generate_npc_turn(self, *args, **kwargs):
                return malformed

            def generate_jean_options(self, *args, **kwargs):
                return None

            def generate_personality(self, class_name):
                return None

        result = ready_npc(_Malformed()).chat_open(player)

        assert isinstance(result, dict)
        assert result["success"] is False
        assert result["error"] == "Conversation failed — try again."
        assert leaked_detail not in result["error"]

    def test_an_adapter_that_raises_falls_back_to_the_authored_line(self, player):
        """A timeout or connection error from the LLM must never cost the
        player a turn. Master pinned the old behaviour (the exception escaped
        to ``chat_open``'s handler and ended the conversation); the adapter call
        is now wrapped, so the authored fallback pool takes over."""
        class _Boom:
            enabled = True

            def generate_npc_turn(self, *args, **kwargs):
                raise RuntimeError("llm timed out")

            def generate_jean_options(self, *args, **kwargs):
                return None

            def generate_personality(self, class_name):
                return None

        result = ready_npc(_Boom()).chat_open(player)

        assert result["success"] is True
        assert result["llm_available"] is False
        assert result["npc_opening"]
        assert "llm timed out" not in result["npc_opening"]
        assert len(result["jean_options"]) == 3

    def test_chat_open_error_message_is_generic_not_raw_exception(self):
        """The client never sees raw internal exception text.

        The exception detail belongs server-side (via logger.error's
        exc_info=True); the client-facing error must be a fixed, generic
        message so an internal exception string never leaks in a 400 body.
        """
        npc = chat_npc(
            init=False,
            name="BrokenNPC",
            _compute_loquacity=lambda player: (_ for _ in ()).throw(
                ValueError("some sensitive internal detail: /etc/secret")
            ),
        )
        player = MagicMock()
        result = npc.chat_open(player)
        assert result["success"] is False
        assert result["error"] == "Conversation failed — try again."
        assert "sensitive internal detail" not in result["error"]


class TestChatRespond:
    """Test chat_respond flow."""

    def test_chat_respond_success(self):
        """Test successful chat response."""
        npc = wired_chat_npc(
            None,
            _chat_history=[{"npc": "Hello", "jean": ""}],
            loquacity_current=50,
            loquacity_threshold=20,
        )
        player = MagicMock()
        player.universe.game_tick = 10
        player.universe.story = {}
        player.npc_chat_histories = {}
        player.reputation = {}

        result = npc.chat_respond(player, "What's your story?", "direct")
        assert result["success"] is True
        assert "npc_response" in result
        assert "jean_options" in result

    def test_chat_respond_loquacity_drain(self):
        """Test loquacity is drained on response."""
        npc = wired_chat_npc(
            None,
            _chat_history=[{"npc": "Hello", "jean": ""}],
            loquacity_current=50,
            loquacity_threshold=20,
        )
        original = npc.loquacity_current
        player = MagicMock()
        player.universe.game_tick = 10
        player.universe.story = {}
        player.npc_chat_histories = {}

        npc.chat_respond(player, "Tell me", "direct")
        # Loquacity should be drained (neutral drain = 8)
        assert npc.loquacity_current < original

    def test_chat_respond_error_handling(self):
        """Test chat respond handles errors."""
        npc = chat_npc(
            init=False,
            name="BrokenNPC",
            _compute_loquacity=lambda player: (_ for _ in ()).throw(
                ValueError("Test error")
            ),
        )
        player = MagicMock()
        result = npc.chat_respond(player, "Hello", "direct")
        assert result["success"] is False

    def test_chat_respond_error_message_is_generic_not_raw_exception(self):
        """The client never sees raw internal exception text (chat_respond)."""
        npc = chat_npc(
            init=False,
            name="BrokenNPC",
            _compute_loquacity=lambda player: (_ for _ in ()).throw(
                ValueError("some sensitive internal detail: /etc/secret")
            ),
        )
        player = MagicMock()
        result = npc.chat_respond(player, "Hello", "direct")
        assert result["success"] is False
        assert result["error"] == "Conversation failed — try again."
        assert "sensitive internal detail" not in result["error"]


class TestLoquacityTick:
    """Test loquacity_tick recovery."""

    def test_loquacity_tick_recovery(self):
        """Test loquacity recovers each tick."""
        npc = chat_npc(
            init=False, loquacity_max=100, loquacity_current=50, loquacity_recovery=5
        )
        npc.loquacity_tick()
        assert npc.loquacity_current == 55

    def test_loquacity_tick_respects_max(self):
        """Test loquacity doesn't exceed max."""
        npc = chat_npc(
            init=False, loquacity_max=100, loquacity_current=98, loquacity_recovery=10
        )
        npc.loquacity_tick()
        assert npc.loquacity_current == 100

    def test_loquacity_tick_not_initialized(self):
        """Test loquacity tick skips if not initialized."""
        npc = chat_npc(
            init=False,
            loquacity_max=0,  # Not initialized
            loquacity_current=0,
            loquacity_recovery=2,
        )
        npc.loquacity_tick()
        assert npc.loquacity_current == 0


class TestDisplayName:
    """Test _display_name."""

    def test_display_name_story_npc(self):
        """Test story NPC displays actual name."""
        npc = chat_npc(
            init=False,
            name="Gorran",
            _chat_char_config={"some": "config"},
            _chat_personality=None,
        )
        assert npc._display_name() == "Gorran"

    def test_display_name_generic_with_personality(self):
        """Test generic NPC displays personality name."""
        npc = chat_npc(
            init=False,
            name="GenericNomad",
            _chat_char_config=None,
            _chat_personality={"given_name": "Ren"},
        )
        assert npc._display_name() == "Ren"

    def test_display_name_generic_fallback(self):
        """Test generic NPC without personality uses name."""
        npc = chat_npc(
            init=False,
            name="GenericNomad",
            _chat_char_config=None,
            _chat_personality=None,
        )
        assert npc._display_name() == "GenericNomad"


class TestGetBrushOffLine:
    """Test _get_brush_off_line."""

    def test_get_brush_off_line_story_npc(self):
        """Test story NPC uses config brush-off."""
        npc = chat_npc(
            init=False,
            name="Gorran",
            _chat_char_config={"closing_lines_when_exhausted": ["I'm tired now."]},
        )
        line = npc._get_brush_off_line()
        assert line == "I'm tired now."

    def test_get_brush_off_line_generic(self):
        """Test generic NPC uses fallback."""
        npc = chat_npc(init=False, name="GenericNomad", _chat_char_config=None)
        line = npc._get_brush_off_line()
        assert line in [
            "They're not in the mood to talk.",
            "A brief shake of the head.",
            "Not now.",
        ]


class TestGetFallbackNpcLine:
    """Test _get_fallback_npc_line."""

    def test_get_fallback_npc_line_story_opening(self):
        """Test story NPC opening fallback from config."""
        npc = chat_npc(
            init=False,
            name="Gorran",
            _chat_char_config={
                "conversation_starters_by_chapter": {"1": ["Hello, friend!"]}
            },
            _get_chapter=lambda player: "1",
        )
        player = MagicMock()
        line = npc._get_fallback_npc_line(is_opening=True, player=player)
        assert line == "Hello, friend!"

    def test_get_fallback_npc_line_story_non_opening(self):
        """Test story NPC non-opening fallback from config."""
        npc = chat_npc(
            init=False,
            name="Gorran",
            _chat_char_config={"closing_lines_when_exhausted": ["Goodbye."]},
            _get_chapter=lambda player: "1",
        )
        player = MagicMock()
        line = npc._get_fallback_npc_line(is_opening=False, player=player)
        assert line == "Goodbye."

    def test_get_fallback_npc_line_generic(self):
        """Test generic NPC uses personality speech sample."""
        npc = chat_npc(
            init=False,
            name="GenericNomad",
            _chat_char_config=None,
            _chat_personality={"speech_sample": "The river's cold."},
            _get_chapter=lambda player: "1",
        )
        player = MagicMock()
        line = npc._get_fallback_npc_line(is_opening=True, player=player)
        assert line == "The river's cold."

    def test_get_fallback_npc_line_default(self):
        """Test default fallback when nothing else available."""
        npc = chat_npc(
            init=False,
            name="GenericNomad",
            _chat_char_config=None,
            _chat_personality=None,
            _get_chapter=lambda player: "1",
        )
        player = MagicMock()
        line = npc._get_fallback_npc_line(is_opening=True, player=player)
        assert line == "Nothing to say right now."

    def test_get_fallback_npc_line_rotates_through_pool(self):
        """Repeated fallback calls must not return the same line every time.

        Regression test: the fallback used to always index [0], which made an
        NPC repeat the exact same line on every turn when the LLM was
        unavailable.
        """
        npc = chat_npc(
            init=False,
            name="Gorran",
            _chat_char_config={
                "conversation_starters_by_chapter": {
                    "1": ["First line.", "Second line.", "Third line."]
                }
            },
            _get_chapter=lambda player: "1",
        )
        player = MagicMock()
        lines = [
            npc._get_fallback_npc_line(is_opening=True, player=player)
            for _ in range(3)
        ]
        assert lines == ["First line.", "Second line.", "Third line."]
        # Rotation wraps back to the start rather than raising.
        assert npc._get_fallback_npc_line(is_opening=True, player=player) == "First line."

    def test_get_fallback_npc_line_exhausted_uses_closing(self):
        """When the conversation is actually ending, use the closing pool."""
        npc = chat_npc(
            init=False,
            name="Gorran",
            _chat_char_config={
                "conversation_starters_by_chapter": {"1": ["Hello, friend!"]},
                "closing_lines_when_exhausted": ["Farewell."],
            },
            _get_chapter=lambda player: "1",
        )
        player = MagicMock()
        line = npc._get_fallback_npc_line(is_opening=False, player=player, exhausted=True)
        assert line == "Farewell."

    def test_get_fallback_npc_line_mid_conversation_prefers_starters(self):
        """A non-exhausted mid-conversation LLM hiccup must not claim the NPC
        is done talking — it should reuse chapter-flavor starters instead of
        the 'done talking' closing lines.
        """
        npc = chat_npc(
            init=False,
            name="Gorran",
            _chat_char_config={
                "conversation_starters_by_chapter": {"1": ["Hello, friend!"]},
                "closing_lines_when_exhausted": ["Farewell."],
            },
            _get_chapter=lambda player: "1",
        )
        player = MagicMock()
        line = npc._get_fallback_npc_line(is_opening=False, player=player, exhausted=False)
        assert line == "Hello, friend!"

    def test_get_fallback_npc_line_generic_rotates(self):
        """Generic-nomad fallback must vary rather than repeat the speech sample."""
        npc = chat_npc(
            init=False,
            name="GenericNomad",
            _chat_char_config=None,
            _chat_personality={
                "given_name": "Ren",
                "speech_sample": "The river's cold.",
                "knowledge": ["river crossings"],
            },
            _get_chapter=lambda player: "1",
        )
        player = MagicMock()
        first = npc._get_fallback_npc_line(is_opening=False, player=player)
        second = npc._get_fallback_npc_line(is_opening=False, player=player)
        assert first == "The river's cold."
        assert second != first


class TestGetFallbackJeanOptions:
    """Test _get_fallback_jean_options."""

    def test_get_fallback_jean_options_rotation(self):
        """Test Jean options rotate through pool."""
        npc = chat_npc(init=False, _chat_fallback_idx=0)
        opts1 = npc._get_fallback_jean_options()
        opts2 = npc._get_fallback_jean_options()
        # Different calls should potentially use different pool entries
        assert len(opts1) == 3
        assert len(opts2) == 3

    def test_get_fallback_jean_options_format(self):
        """Test Jean options have correct format."""
        npc = chat_npc(init=False, _chat_fallback_idx=0)
        opts = npc._get_fallback_jean_options()
        for opt in opts:
            assert "text" in opt
            assert "tone" in opt
            assert opt["tone"] in ("direct", "guarded", "open")


class TestIntegrationChatFlow:
    """Integration tests for complete chat flows."""

    def test_full_conversation_cycle(self):
        """Test opening and responding in sequence."""
        # Not ready_npc: this drives the real _get_adapter lookup, and
        # ready_npc always installs an adapter of its own.
        npc = chat_npc(
            init=False,
            name="Ren",
            _chat_char_config=None,
            _chat_world_facts={},
            _chat_personality={"given_name": "Ren"},
            _chat_history=[],
            _chat_npc_key=None,
            _chat_adapter=None,
            _chat_fallback_idx=0,
            _prohibited_patterns=[],
            loquacity_current=0,
            loquacity_max=0,
            loquacity_threshold=0,
            loquacity_recovery=2,
        )
        player = chat_player(
            persist=True,
            universe=MagicMock(story={}, game_tick=10),
            charisma=10,
            equipped={},
            allies=[],
        )

        # Open chat
        open_result = npc.chat_open(player)
        assert open_result["success"] is True

        # Respond to NPC
        respond_result = npc.chat_respond(player, "Tell me more", "direct")
        assert respond_result["success"] is True

        # Check loquacity decreased
        assert respond_result["loquacity_current"] < 100

    def test_loquacity_exhaustion(self):
        """Test conversation ends when loquacity exhausted."""
        npc = wired_chat_npc(
            None,
            _chat_history=[{"npc": "Hello", "jean": ""}],
            loquacity_current=15,  # Below threshold of 20
            loquacity_threshold=20,
        )
        player = MagicMock()
        player.universe.game_tick = 10
        player.universe.story = {}
        player.npc_chat_histories = {}
        player.reputation = {}

        # With loquacity below threshold, conversation should end after drain
        result = npc.chat_respond(player, "Hello", "direct")
        # Loquacity drain of 8 brings 15 - 8 = 7, which is below threshold
        assert result["conversation_ended"] is True


class TestCacheManagement:
    """Test class-level cache management."""

    def test_world_facts_cache_shared(self):
        """Test world facts cache is shared across instances."""
        ConversationalNPCMixin._world_facts_cache = {"cached": True}

        npc1 = chat_npc(init=False, name="NPC1")
        npc2 = chat_npc(init=False, name="NPC2")

        # Both should use the same cache reference
        assert ConversationalNPCMixin._world_facts_cache == {"cached": True}

    def test_char_config_cache(self):
        """Test character config cache."""
        ConversationalNPCMixin._char_config_cache = {}

        chat_npc(config_path="/nonexistent/path.json")
        # Cache should be populated even on error
        assert "/nonexistent/path.json" in ConversationalNPCMixin._char_config_cache


class TestProhibitedPatternsSetup:
    """Prohibited phrases are compiled from the character config."""

    @pytest.fixture(autouse=True)
    def _isolate_config_cache(self):
        """``_char_config_cache`` is a *class-level* dict shared by every NPC in
        the process. Snapshot and restore it so these tests cannot leak a cached
        config into an unrelated test (or into a parallel worker's file)."""
        saved = dict(ConversationalNPCMixin._char_config_cache)
        yield
        ConversationalNPCMixin._char_config_cache.clear()
        ConversationalNPCMixin._char_config_cache.update(saved)

    def test_patterns_are_compiled_from_config_and_actually_match(self, tmp_path):
        config = tmp_path / "char.json"
        config.write_text(
            json.dumps({"prohibited_phrases": ["the Conclave", "blood price"]}),
            encoding="utf-8",
        )

        npc = chat_npc(config_path=str(config))

        assert len(npc._prohibited_patterns) == 2
        # The point of compiling them: they must fire, case-insensitively, on
        # the authored phrase and not on unrelated text.
        assert npc._prohibited_patterns[0].search("we spoke of THE CONCLAVE once")
        assert npc._prohibited_patterns[1].search("a Blood Price was paid")
        assert not npc._prohibited_patterns[0].search("we spoke of the council")

    def test_phrases_are_regex_escaped_not_interpreted(self, tmp_path):
        """``re.escape`` means a phrase containing regex metacharacters matches
        literally instead of blowing up or matching everything."""
        config = tmp_path / "char.json"
        config.write_text(
            json.dumps({"prohibited_phrases": ["what (really) happened?"]}),
            encoding="utf-8",
        )

        npc = chat_npc(config_path=str(config))

        assert npc._prohibited_patterns[0].search("I know what (really) happened?")
        assert not npc._prohibited_patterns[0].search("I know what really happened?")

    def test_an_unreadable_config_leaves_the_npc_speaking(self, tmp_path):
        """A missing config must degrade to "no prohibitions", not raise —
        CLAUDE.md: prefer silent recovery over crashing the game loop."""
        npc = chat_npc(config_path=str(tmp_path / "does-not-exist.json"))

        assert npc._chat_char_config is None
        assert npc._prohibited_patterns == []

    def test_malformed_config_json_is_swallowed(self, tmp_path):
        config = tmp_path / "char.json"
        config.write_text("{not json at all", encoding="utf-8")

        npc = chat_npc(config_path=str(config))

        assert npc._chat_char_config is None
        assert npc._prohibited_patterns == []


class TestEquipmentHandling:
    """Test equipment dict handling in loquacity computation."""

    def test_compute_loquacity_equipment_non_dict(self):
        """Test equipment handling when value is not dict."""
        npc = chat_npc()
        player = chat_player(
            charisma=10, equipped={"hand": "Sword"}, allies=[]  # String, not dict
        )

        npc._compute_loquacity(player)
        # Should handle gracefully
        assert npc.loquacity_max >= 20

    def test_compute_loquacity_religious_token(self):
        """Test religious token equipment bonus."""
        npc = chat_npc()
        player = chat_player(
            charisma=10, equipped={"neck": {"name": "Religious Token"}}, allies=[]
        )

        npc._compute_loquacity(player)
        # Should get equipment bonus
        assert npc.loquacity_max > 60

    def test_compute_loquacity_nomad_gear(self):
        """Test nomad gear equipment bonus."""
        npc = chat_npc()
        player = chat_player(
            charisma=10, equipped={"back": {"name": "Nomad Gear Pack"}}, allies=[]
        )

        npc._compute_loquacity(player)
        # Should get equipment bonus
        assert npc.loquacity_max > 60


class TestChatOpenWithLLM:
    """Test chat_open with LLM adapter."""

    def test_chat_open_with_adapter_success(self):
        """Test chat_open when LLM adapter succeeds."""
        class MockAdapter:
            enabled = True

            def generate_npc_turn(self, system, history, is_opening=False):
                return {"npc_text": "Hello there, friend."}

            def generate_jean_options(self, name, voice, opening, history, turn):
                return [
                    {"text": "Who are you?", "tone": "direct"},
                    {"text": "Nice to meet you.", "tone": "open"},
                    {"text": "What do you want?", "tone": "guarded"},
                ]

        npc = ready_npc(
            MockAdapter(),
            loquacity_current=0,
            loquacity_max=0,
            loquacity_threshold=0,
        )
        player = chat_player(
            persist=True,
            universe=MagicMock(story={}, game_tick=10),
            charisma=10,
            equipped={},
            allies=[],
        )

        result = npc.chat_open(player)
        assert result["success"] is True
        assert result["llm_available"] is True


class TestChatRespondWithLLM:
    """Test chat_respond with LLM adapter."""

    def test_chat_respond_with_adapter_success(self):
        """Test chat_respond when LLM adapter succeeds."""
        class MockAdapter:
            enabled = True

            def generate_npc_turn(
                self, system, history, is_opening=False, jean_text=None
            ):
                return {
                    "npc_text": "That's very interesting to me.",
                    "conversation_quality": "positive",
                }

            def generate_jean_options(self, name, voice, response, history, turn):
                return [
                    {"text": "Tell me more.", "tone": "open"},
                    {"text": "I understand.", "tone": "guarded"},
                    {"text": "What else?", "tone": "direct"},
                ]

        npc = ready_npc(MockAdapter(), _chat_history=[{"npc": "Hello", "jean": ""}])
        player = MagicMock()
        player.universe.game_tick = 10
        player.universe.story = {}
        player.npc_chat_histories = {}
        player.reputation = {}

        result = npc.chat_respond(player, "Tell me about yourself", "direct")
        assert result["success"] is True
        assert result["llm_available"] is True
        # Positive quality drains 3 loquacity
        assert result["loquacity_current"] == 47

    def test_chat_respond_applies_reputation_delta(self):
        """The NPC's in-character reaction to Jean's words shifts reputation."""
        class MockAdapter:
            enabled = True

            def generate_npc_turn(
                self, system, history, is_opening=False, jean_text=None
            ):
                return {
                    "npc_text": "I won't forget that kindness.",
                    "conversation_quality": "positive",
                    "reputation_delta": 5,
                }

            def generate_jean_options(self, name, voice, response, history, turn):
                return [
                    {"text": "Tell me more.", "tone": "open"},
                    {"text": "I understand.", "tone": "guarded"},
                    {"text": "What else?", "tone": "direct"},
                ]

        npc = ready_npc(MockAdapter(), _chat_history=[{"npc": "Hello", "jean": ""}])
        player = MagicMock()
        player.universe.game_tick = 10
        player.universe.story = {}
        player.npc_chat_histories = {}
        player.reputation = {"TestNPC": 10}

        result = npc.chat_respond(player, "Here, take this gift.", "open")

        assert result["success"] is True
        assert result["reputation_delta"] == 5
        assert result["reputation"] == 15
        assert player.reputation["TestNPC"] == 15

    def test_chat_respond_clamps_reputation_to_bounds(self):
        """Reputation never exceeds +/-100 even with repeated extreme deltas."""
        class MockAdapter:
            enabled = True

            def generate_npc_turn(
                self, system, history, is_opening=False, jean_text=None
            ):
                return {
                    "npc_text": "How could you say something so cruel to me after everything.",
                    "conversation_quality": "offensive",
                    "reputation_delta": -5,
                }

            def generate_jean_options(self, name, voice, response, history, turn):
                return [
                    {"text": "Tell me more.", "tone": "open"},
                ]

        npc = ready_npc(MockAdapter(), _chat_history=[{"npc": "Hello", "jean": ""}])
        player = MagicMock()
        player.universe.game_tick = 10
        player.universe.story = {}
        player.npc_chat_histories = {}
        player.reputation = {"TestNPC": -98}

        result = npc.chat_respond(player, "Insulting remark.", "guarded")

        assert result["reputation"] == -100
        assert player.reputation["TestNPC"] == -100


class TestHistoryUpdating:
    """Test chat history update logic in chat_respond."""

    def test_chat_respond_updates_last_entry(self):
        """Test chat_respond updates last history entry."""
        npc = wired_chat_npc(
            None,
            _chat_history=[
                {"npc": "Hello", "jean": "", "game_tick": 5, "chapter": "1"}
            ],
            loquacity_current=50,
            loquacity_threshold=20,
        )
        player = MagicMock()
        player.universe.game_tick = 10
        player.universe.story = {}
        player.npc_chat_histories = {}

        npc.chat_respond(player, "My story is", "direct")
        # Last entry should have jean_text updated
        assert npc._chat_history[-1]["jean"] == "My story is"


class TestWorldFactsLoading:
    """World facts loading, including the failure path."""

    @pytest.fixture(autouse=True)
    def _isolate_world_facts_cache(self):
        """``_world_facts_cache`` is class-level state shared process-wide.
        The test this replaces set it to ``None`` and never restored it, so
        whichever test ran next re-read the file (or saw this test's ``{}``)."""
        saved = ConversationalNPCMixin._world_facts_cache
        ConversationalNPCMixin._world_facts_cache = None
        yield
        ConversationalNPCMixin._world_facts_cache = saved

    def test_an_unreadable_world_facts_file_yields_an_empty_dict(self):
        """The old test asserted ``_chat_world_facts is not None`` while
        injecting no error at all — it exercised the *success* path and would
        have passed whatever the failure path did."""
        with patch(
            "src.npc._chat_llm._WORLD_FACTS_PATH",
            Path("/nonexistent/world_facts.json"),
        ):
            npc = chat_npc()

        assert npc._chat_world_facts == {}
        # QC still runs with no allow-list rather than raising.
        assert npc._qc_npc_text("The road is long.", []).text == "The road is long."

    def test_malformed_world_facts_json_yields_an_empty_dict(self, tmp_path):
        bad = tmp_path / "world_facts.json"
        bad.write_text("[[[", encoding="utf-8")

        with patch("src.npc._chat_llm._WORLD_FACTS_PATH", bad):
            npc = chat_npc()

        assert npc._chat_world_facts == {}

    def test_world_facts_are_read_once_and_shared(self, tmp_path):
        facts = tmp_path / "world_facts.json"
        facts.write_text(
            json.dumps({"allowed_proper_nouns": ["Grondite"]}), encoding="utf-8"
        )

        with patch("src.npc._chat_llm._WORLD_FACTS_PATH", facts):
            first = chat_npc()
            facts.write_text(json.dumps({"allowed_proper_nouns": []}), encoding="utf-8")
            second = chat_npc()

        # The second NPC reuses the cached parse rather than re-reading.
        assert first._chat_world_facts == {"allowed_proper_nouns": ["Grondite"]}
        assert second._chat_world_facts is first._chat_world_facts


class TestCharConfigLoading:
    """Test character config loading with errors."""

    def test_char_config_load_with_invalid_json(self):
        """Test handling of invalid JSON in config."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            ConversationalNPCMixin._char_config_cache = {}

            npc = chat_npc(config_path=temp_path)
            # Should gracefully handle load error
            assert npc._chat_char_config is None
        finally:
            os.unlink(temp_path)


class TestALLMRetryLogic:
    """Test LLM retry logic on generation failure."""

    def test_chat_open_retries_on_first_attempt_failure(self):
        """Test chat_open retries when first LLM attempt fails."""

        class MockAdapterFailThenSucceed:
            enabled = True
            call_count = 0

            def generate_npc_turn(self, system, history, is_opening=False):
                self.call_count += 1
                if self.call_count == 1:
                    return {"npc_text": None}  # First attempt fails
                return {"npc_text": "Hello there."}

            def generate_jean_options(self, name, voice, opening, history, turn):
                return [
                    {"text": "Who?", "tone": "direct"},
                    {"text": "OK.", "tone": "guarded"},
                    {"text": "Tell.", "tone": "open"},
                ]

        npc = ready_npc(
            MockAdapterFailThenSucceed(),
            loquacity_current=0,
            loquacity_max=0,
            loquacity_threshold=0,
        )
        player = chat_player(
            persist=True,
            universe=MagicMock(story={}, game_tick=10),
            charisma=10,
            equipped={},
            allies=[],
        )

        result = npc.chat_open(player)
        assert result["success"] is True
        # Should have retried
        assert npc._chat_adapter.call_count == 2


class TestConversationQualityDrains:
    """Loquacity arithmetic across one ``chat_respond`` round.

    Driven against a *real* ``Player``/``Universe`` (via ``live_world``) rather
    than a ``MagicMock``: ``chat_respond`` writes ``player.reputation`` and
    ``player.npc_chat_histories``, neither of which exists on a fresh Player, so
    a MagicMock silently answers both and the lazy-initialization branches go
    untested.
    """

    @pytest.fixture
    def player(self):
        return live_world()[0]

    @pytest.mark.parametrize(
        "quality, expected",
        [
            ("positive", 47),   # drain 3
            ("neutral", 42),    # drain 8
            ("negative", 35),   # drain 15
            ("offensive", 20),  # drain 30
            # An unrecognised quality string falls back to the neutral drain
            # rather than raising or draining nothing.
            ("unknown_quality", 42),
        ],
    )
    def test_quality_selects_the_drain_amount(self, player, quality, expected):
        npc = ready_npc(
            ScriptedAdapter(npc_text="A plain answer.", quality=quality),
            _chat_history=[{"npc": "Hello", "jean": ""}],
        )
        result = npc.chat_respond(player, "How dare you", "direct")

        assert npc.loquacity_current == expected
        assert result["loquacity_current"] == expected
        assert result["loquacity_max"] == 100

    def test_an_explicit_delta_from_the_model_overrides_the_quality_drain(self, player):
        """The model may signal a *gain* when Jean raises an interesting topic."""
        npc = ready_npc(
            ScriptedAdapter(quality="negative", loquacity_delta=+10),
            _chat_history=[{"npc": "Hello", "jean": ""}],
        )
        npc.chat_respond(player, "Tell me of the mines", "open")
        # +10, not the -15 "negative" drain.
        assert npc.loquacity_current == 60

    @pytest.mark.parametrize(
        "delta, expected",
        [(-1000, 10), (1000, 65), (-40, 10), (15, 65)],
        ids=["clamped-drain", "clamped-gain", "at-drain-limit", "at-gain-limit"],
    )
    def test_the_model_supplied_delta_is_clamped_to_minus40_plus15(
        self, player, delta, expected
    ):
        """A hostile or buggy model must not empty or refill the meter at will."""
        npc = ready_npc(
            ScriptedAdapter(quality="neutral", loquacity_delta=delta),
            _chat_history=[{"npc": "Hello", "jean": ""}],
        )
        npc.chat_respond(player, "hello", "direct")
        assert npc.loquacity_current == expected

    def test_loquacity_floors_at_zero(self, player):
        """The real floor, exercised through ``chat_respond``.

        The test this replaces computed ``max(0, 5 - 30)`` *in the test body*
        and asserted the answer was 0 — no engine code ran at all.
        """
        npc = ready_npc(
            ScriptedAdapter(quality="offensive"),
            loquacity_current=5,
            _chat_history=[{"npc": "Hello", "jean": ""}],
        )
        npc.chat_respond(player, "You are a fool", "direct")
        assert npc.loquacity_current == 0

    def test_loquacity_ceilings_at_max(self, player):
        npc = ready_npc(
            ScriptedAdapter(quality="positive", loquacity_delta=15),
            loquacity_current=95,
            _chat_history=[{"npc": "Hello", "jean": ""}],
        )
        npc.chat_respond(player, "Well met", "open")
        assert npc.loquacity_current == 100

    def test_dropping_below_the_threshold_ends_the_conversation(self, player):
        npc = ready_npc(
            ScriptedAdapter(quality="offensive"),
            loquacity_current=25,
            loquacity_threshold=20,
            _chat_history=[{"npc": "Hello", "jean": ""}],
        )
        result = npc.chat_respond(player, "You are a fool", "direct")
        assert npc.loquacity_current == 0
        assert result["conversation_ended"] is True

    def test_staying_on_the_threshold_keeps_the_conversation_open(self, player):
        """The comparison is strict ``<``, so exactly the threshold survives."""
        npc = ready_npc(
            ScriptedAdapter(quality="offensive"),
            loquacity_current=50,
            loquacity_threshold=20,
            _chat_history=[{"npc": "Hello", "jean": ""}],
        )
        result = npc.chat_respond(player, "How dare you", "direct")
        assert npc.loquacity_current == 20
        assert result["conversation_ended"] is False


class TestEdgeCasesAndBoundaries:
    """Boundary conditions in the text pipeline."""

    def test_an_exclamation_survives_the_sentence_cap(self):
        """The sentence cap used to rejoin on ``". "``, flattening every ``!``
        and ``?`` into a full stop. It now preserves the terminator it found, so
        an NPC can still shout."""
        assert qc_npc()._qc_npc_text("You are insulting!", []).text == (
            "You are insulting!"
        )

    def test_a_question_mark_likewise_survives(self):
        assert qc_npc()._qc_npc_text("Who sent you?", []).text == "Who sent you?"


class TestCharConfigPathHandling:
    """Test character config path edge cases."""

    def test_init_chat_attrs_without_config_path_attr(self):
        """Test _init_chat_attrs when config path not pre-set."""
        # Not built with chat_npc: ChatHost always assigns ``_chat_config_path``,
        # so the factory cannot produce the missing-attribute state this pins.
        class TestNPC(ConversationalNPCMixin):
            def __init__(self):
                self.name = "TestNPC"
                self.charisma = 10
                self.wisdom = 10
                self.keywords = []
                # Don't set _chat_config_path, let _init_chat_attrs handle it
                self._init_chat_attrs()

        npc = TestNPC()
        assert npc._chat_config_path is None


class TestRetryOnQCFailure:
    """Test retry logic when QC rejects text."""

    def test_chat_open_retries_on_qc_failure(self):
        """Test chat_open retries when QC rejects NPC text."""

        class MockAdapterBadThenGood:
            enabled = True
            call_count = 0

            def generate_npc_turn(self, system, history, is_opening=False):
                self.call_count += 1
                if self.call_count == 1:
                    # Return text that will be rejected by QC
                    return {"npc_text": "x"}  # Too short, < 10 chars
                return {"npc_text": "This is a proper response."}

            def generate_jean_options(self, name, voice, opening, history, turn):
                return [
                    {"text": "Option one ok", "tone": "direct"},
                    {"text": "Option two ok", "tone": "guarded"},
                    {"text": "Option three ok", "tone": "open"},
                ]

        npc = ready_npc(
            MockAdapterBadThenGood(),
            loquacity_current=0,
            loquacity_max=0,
            loquacity_threshold=0,
        )
        player = chat_player(
            persist=True,
            universe=MagicMock(story={}, game_tick=10),
            charisma=10,
            equipped={},
            allies=[],
        )

        result = npc.chat_open(player)
        assert result["success"] is True
        # Should have retried once due to QC failure
        assert npc._chat_adapter.call_count == 2


class TestJeanOptionsQCRetry:
    """Test Jean options QC and fallback."""

    def test_chat_open_jean_options_bad_then_fallback(self):
        """Test chat_open falls back when Jean options QC fails."""

        class MockAdapterBadOptions:
            enabled = True

            def generate_npc_turn(self, system, history, is_opening=False):
                return {"npc_text": "Hello friend."}

            def generate_jean_options(self, name, voice, opening, history, turn):
                # Return invalid options that QC will reject
                return [{"text": "x"}]  # Not list of 3

        npc = ready_npc(
            MockAdapterBadOptions(),
            loquacity_current=0,
            loquacity_max=0,
            loquacity_threshold=0,
        )
        player = chat_player(
            persist=True,
            universe=MagicMock(story={}, game_tick=10),
            charisma=10,
            equipped={},
            allies=[],
        )

        result = npc.chat_open(player)
        assert result["success"] is True
        # Should use fallback options
        assert len(result["jean_options"]) == 3


class TestHistoryPersistenceAppend:
    """Test history appending vs updating."""

    def test_save_exchange_appends_new_entry(self):
        """Test saving with empty history appends new entry."""
        npc = chat_npc(
            init=False,
            loquacity_current=50,
            loquacity_max=100,
            _chat_npc_key="test_key",
            _chat_personality=None,
        )
        player = MagicMock()
        player.npc_chat_histories = {}

        # First save creates entry
        npc._save_exchange_to_persistence(player, "First", "Response", 10, "1")
        assert len(player.npc_chat_histories["test_key"]["exchanges"]) == 1

        # Second save appends
        npc._save_exchange_to_persistence(player, "Second", "Another", 20, "1")
        assert len(player.npc_chat_histories["test_key"]["exchanges"]) == 2


class TestChatRespondHistoryIntegrity:
    """End-to-end regression coverage for a full chat_open -> chat_respond*
    conversation against a player object that (like a real Player, unlike
    MinimalPlayer) has no npc_chat_histories attribute to start with.

    This is the exact scenario a live conversation with a story NPC (e.g.
    Mara) exercises: it caught two real bugs that unit tests calling
    _save_exchange_to_persistence directly couldn't see — (1)
    player.npc_chat_histories was never initialized on a real Player, so
    persistence silently no-opped every call, and (2) chat_respond's history
    bookkeeping double-appended a row every single turn once persistence
    actually worked.
    """

    def _make_npc(self, starters, closing):
        return chat_npc(
            init=False,
            name="Mara",
            _chat_char_config={
                "conversation_starters_by_chapter": {"1": starters},
                "closing_lines_when_exhausted": closing,
            },
            _chat_world_facts={},
            _chat_personality=None,
            _chat_history=[],
            _chat_npc_key=None,
            _chat_fallback_idx=0,
            _chat_npc_fallback_idx=0,
            _prohibited_patterns=[],
            loquacity_current=0,
            loquacity_max=0,
            loquacity_threshold=0,
            loquacity_recovery=2,
            _get_adapter=lambda: None,  # force the deterministic fallback path
            _get_chapter=lambda player: "1",
        )

    def _make_player(self):
        player = chat_player(
            universe=MagicMock(story={}, game_tick=0),
            charisma=10,
            equipped={},
            allies=[],
        )
        # Deliberately no npc_chat_histories attribute — matches a real
        # Player, which never initializes it (unlike MinimalPlayer).
        assert not hasattr(player, "npc_chat_histories")
        return player

    def test_full_conversation_creates_one_row_per_round(self):
        npc = self._make_npc(
            starters=["Line A.", "Line B.", "Line C."],
            closing=["Goodbye now."],
        )
        player = self._make_player()

        opened = npc.chat_open(player)
        assert hasattr(player, "npc_chat_histories")

        npc.chat_respond(player, "Q1", "direct")
        npc.chat_respond(player, "Q2", "direct")

        entry = player.npc_chat_histories["Mara"]
        # Opening + 2 respond rounds = 3 rows, never more (no double-append).
        assert len(entry["exchanges"]) == 3
        assert entry["conversation_count"] == 2

    def test_full_conversation_never_repeats_an_npc_line(self):
        """Regression test for the exact bug reported against this feature:
        a conversation that outlasts the authored fallback pool must end
        gracefully instead of visibly repeating a line already said.
        """
        npc = self._make_npc(
            starters=["Line A.", "Line B."],
            closing=["Goodbye now."],
        )
        player = self._make_player()

        opened = npc.chat_open(player)
        lines_said = [opened["npc_opening"]]

        for i in range(6):
            resp = npc.chat_respond(player, f"Question {i}", "direct")
            lines_said.append(resp["npc_response"])
            if resp["conversation_ended"]:
                break

        assert len(lines_said) == len(set(lines_said)), (
            f"NPC repeated a line within one conversation: {lines_said}"
        )

    def test_single_line_pool_ends_immediately_instead_of_repeating(self):
        """A one-line authored pool is the tightest case for the duplicate
        guard: rotation alone can never help (idx % 1 is always 0), so the
        very first respond turn must detect the repeat against the opening
        line itself and end there rather than echo it back.
        """
        npc = self._make_npc(
            starters=["Only line."],
            closing=["Goodbye now."],
        )
        player = self._make_player()

        opened = npc.chat_open(player)
        assert opened["npc_opening"] == "Only line."

        resp = npc.chat_respond(player, "Question", "direct")
        assert resp["npc_response"] != "Only line."
        assert resp["conversation_ended"] is True

    def test_conversation_history_is_chronologically_ordered(self):
        """Each persisted row must pair an NPC line with Jean's reply TO it,
        not with the reply that prompted the NEXT line — otherwise the
        formatted transcript handed to the LLM reads out of order.
        """
        npc = self._make_npc(
            starters=["Line A.", "Line B.", "Line C."],
            closing=["Goodbye now."],
        )
        player = self._make_player()

        npc.chat_open(player)
        npc.chat_respond(player, "Q1", "direct")
        npc.chat_respond(player, "Q2", "direct")

        exchanges = player.npc_chat_histories["Mara"]["exchanges"]
        assert exchanges[0]["jean"] == "Q1"
        assert exchanges[1]["jean"] == "Q2"
        assert exchanges[0]["npc"] != exchanges[1]["npc"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
