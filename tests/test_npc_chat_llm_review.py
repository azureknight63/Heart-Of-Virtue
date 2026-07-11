"""
Tests for the NPC LLM chat review changes:

- Combined single-call turn (NPC reply + Jean options) via ``generate_turn``
- Signed ``loquacity_delta`` (drain *and* gain)
- Graceful closure: options omitted once loquacity is exhausted
- Proper-noun QC no longer mangles sentence-initial / common words
- ``GameService._recover_npc_loquacity`` recovers persisted loquacity
- Adapter ``generate_turn`` parsing / clamping
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.npc._chat_llm import HumanNPCLLMMixin  # noqa: E402


def _make_npc(**overrides):
    """Build a minimally-wired chat NPC whose helper methods are stubbed."""

    class TestNPC(HumanNPCLLMMixin):
        def __init__(self):
            self.name = "TestNPC"
            self.charisma = 10
            self.wisdom = 10
            self.keywords = []
            self._chat_config_path = None
            self._chat_char_config = None
            self._chat_world_facts = {}
            self._chat_personality = {"given_name": "Ren", "voice": "dry"}
            self._chat_history = [{"npc": "Hello", "jean": ""}]
            self._chat_npc_key = None
            self._chat_adapter = None
            self._chat_fallback_idx = 0
            self._prohibited_patterns = []
            self.loquacity_current = 50
            self.loquacity_max = 100
            self.loquacity_threshold = 20
            self.loquacity_recovery = 2

        def _compute_loquacity(self, player):
            pass

        def _get_npc_key(self, player):
            return "test_key"

        def _load_history_from_persistence(self, player):
            pass

        def _ensure_personality(self, player):
            pass

        def _build_system_prompt(self, player):
            return "System prompt"

        def _get_chapter(self, player):
            return "1"

        def _save_exchange_to_persistence(self, player, npc, jean, tick, chapter):
            pass

        def _display_name(self):
            return self.name

    npc = TestNPC()
    for k, v in overrides.items():
        setattr(npc, k, v)
    return npc


class _CombinedAdapter:
    """Adapter exposing the new single-call combined interface."""

    enabled = True

    def __init__(self, npc_text, quality="neutral", rep=0, loq=-8, options=None):
        self._npc_text = npc_text
        self._quality = quality
        self._rep = rep
        self._loq = loq
        self._options = options or [
            {"tone": "direct", "text": "What happened out there in the badlands?"},
            {"tone": "guarded", "text": "I would rather keep my distance for now."},
            {"tone": "open", "text": "Tell me more about the crossing you mentioned."},
        ]
        self.turn_calls = 0
        self.option_calls = 0

    def generate_turn(self, system, history, is_opening=False, jean_text=None):
        self.turn_calls += 1
        return {
            "npc_text": self._npc_text,
            "conversation_quality": self._quality,
            "reputation_delta": self._rep,
            "loquacity_delta": self._loq,
            "jean_options": self._options,
        }

    def generate_jean_options(self, name, voice, line, history, turn):
        # Should never be called on the combined path.
        self.option_calls += 1
        return None


def _player():
    player = MagicMock()
    player.universe.game_tick = 10
    player.universe.story = {}
    player.npc_chat_histories = {}
    player.reputation = {}
    return player


# ---------------------------------------------------------------------------
# Combined single-call path
# ---------------------------------------------------------------------------


class TestCombinedTurn:
    def test_respond_uses_single_combined_call(self):
        adapter = _CombinedAdapter("The river runs high this season.")
        npc = _make_npc(_chat_adapter=adapter)

        result = npc.chat_respond(_player(), "Tell me about the river", "direct")

        assert result["success"] is True
        assert result["llm_available"] is True
        assert result["npc_response"] == "The river runs high this season."
        assert len(result["jean_options"]) == 3
        # Exactly one combined call, and no separate options call.
        assert adapter.turn_calls == 1
        assert adapter.option_calls == 0

    def test_open_uses_combined_options(self):
        adapter = _CombinedAdapter("She looks up, unhurried, and waits.")
        npc = _make_npc(_chat_adapter=adapter, _chat_history=[])

        result = npc.chat_open(_player())

        assert result["success"] is True
        assert result["llm_available"] is True
        assert len(result["jean_options"]) == 3
        assert adapter.option_calls == 0


# ---------------------------------------------------------------------------
# Loquacity delta — drain and gain
# ---------------------------------------------------------------------------


class TestLoquacityDelta:
    def test_negative_delta_drains(self):
        adapter = _CombinedAdapter("Noted, for what it is worth.", loq=-12)
        npc = _make_npc(_chat_adapter=adapter, loquacity_current=50)
        result = npc.chat_respond(_player(), "Whatever", "direct")
        assert result["loquacity_current"] == 38

    def test_positive_delta_increases_loquacity(self):
        # Jean hit a topic the NPC finds interesting.
        adapter = _CombinedAdapter("Now that is worth talking about.", loq=8)
        npc = _make_npc(_chat_adapter=adapter, loquacity_current=50)
        result = npc.chat_respond(_player(), "The old crossing", "open")
        assert result["loquacity_current"] == 58

    def test_gain_clamped_to_max(self):
        adapter = _CombinedAdapter("Go on, I am listening.", loq=15)
        npc = _make_npc(_chat_adapter=adapter, loquacity_current=95, loquacity_max=100)
        result = npc.chat_respond(_player(), "topic", "open")
        assert result["loquacity_current"] == 100

    def test_delta_lower_bound_clamped(self):
        adapter = _CombinedAdapter("Get out of my sight.", quality="offensive", loq=-999)
        npc = _make_npc(_chat_adapter=adapter, loquacity_current=100)
        result = npc.chat_respond(_player(), "insult", "direct")
        # Clamped to -40.
        assert result["loquacity_current"] == 60


# ---------------------------------------------------------------------------
# Graceful closure
# ---------------------------------------------------------------------------


class TestGracefulClosure:
    def test_exhaustion_omits_options(self):
        adapter = _CombinedAdapter("She turns back to the river.", loq=-40)
        npc = _make_npc(
            _chat_adapter=adapter,
            loquacity_current=25,
            loquacity_threshold=20,
        )
        result = npc.chat_respond(_player(), "One more thing", "direct")
        assert result["conversation_ended"] is True
        # The NPC's context-aware line stands as the closing; no options remain.
        assert result["npc_response"] == "She turns back to the river."
        assert result["jean_options"] == []


# ---------------------------------------------------------------------------
# Proper-noun QC no longer mangles ordinary English
# ---------------------------------------------------------------------------


class TestProperNounQC:
    def _npc(self):
        class QCNPC(HumanNPCLLMMixin):
            def __init__(self):
                self.name = "TestNPC"
                self._chat_world_facts = {"allowed_proper_nouns": []}
                self._prohibited_patterns = []

        return QCNPC()

    def test_sentence_initial_words_preserved(self):
        npc = self._npc()
        result = npc._qc_npc_text("The storm is coming. She warned us before.", [])
        assert "The" in result
        assert "She" in result
        assert "they" not in result.split()

    def test_common_words_preserved_midsentence(self):
        npc = self._npc()
        result = npc._qc_npc_text("I trust in God when the North wind rises.", [])
        assert "God" in result
        assert "North" in result

    def test_invented_noun_still_scrubbed(self):
        npc = self._npc()
        result = npc._qc_npc_text("I saw Xanthor near the ridge.", [])
        assert "Xanthor" not in result


# ---------------------------------------------------------------------------
# GameService loquacity recovery wiring
# ---------------------------------------------------------------------------


class TestLoquacityRecovery:
    def _service(self):
        from src.api.services.game_service import GameService

        return GameService()

    def test_recovers_persisted_loquacity(self):
        svc = self._service()
        player = MagicMock()
        player.__dict__["_active_chat_npc_id"] = None
        player.npc_chat_histories = {
            "Mara": {
                "loquacity_current": 40,
                "loquacity_max": 100,
                "loquacity_recovery": 5,
            }
        }
        svc._recover_npc_loquacity(player)
        assert player.npc_chat_histories["Mara"]["loquacity_current"] == 45

    def test_recovery_respects_max(self):
        svc = self._service()
        player = MagicMock()
        player.__dict__["_active_chat_npc_id"] = None
        player.npc_chat_histories = {
            "Mara": {"loquacity_current": 98, "loquacity_max": 100, "loquacity_recovery": 5}
        }
        svc._recover_npc_loquacity(player)
        assert player.npc_chat_histories["Mara"]["loquacity_current"] == 100

    def test_no_recovery_during_active_chat(self):
        svc = self._service()
        player = MagicMock()
        player.__dict__["_active_chat_npc_id"] = "Mara"
        player.npc_chat_histories = {
            "Mara": {"loquacity_current": 40, "loquacity_max": 100, "loquacity_recovery": 5}
        }
        svc._recover_npc_loquacity(player)
        assert player.npc_chat_histories["Mara"]["loquacity_current"] == 40

    def test_meta_key_skipped(self):
        svc = self._service()
        player = MagicMock()
        player.__dict__["_active_chat_npc_id"] = None
        player.npc_chat_histories = {"__meta__": {"SomeClass": 2}}
        # Should not raise.
        svc._recover_npc_loquacity(player)
        assert player.npc_chat_histories["__meta__"] == {"SomeClass": 2}

    def test_respond_clears_active_flag_on_end(self):
        """A conversation that ends must clear _active_chat_npc_id so recovery
        (which is skipped while a chat is active) is not frozen globally."""
        svc = self._service()

        npc = MagicMock()
        npc.chat_respond.return_value = {
            "success": True,
            "conversation_ended": True,
        }
        player = MagicMock()
        player.__dict__["_active_chat_npc_id"] = "Mara"
        svc._find_chat_npc = MagicMock(return_value=npc)
        svc._enrich_chat_result_with_relationship = lambda result, n: result

        svc.npc_chat_respond(player, "Mara", "goodbye", "direct")

        assert "_active_chat_npc_id" not in player.__dict__

    def test_respond_keeps_active_flag_when_not_ended(self):
        svc = self._service()

        npc = MagicMock()
        npc.chat_respond.return_value = {
            "success": True,
            "conversation_ended": False,
        }
        player = MagicMock()
        player.__dict__["_active_chat_npc_id"] = "Mara"
        svc._find_chat_npc = MagicMock(return_value=npc)
        svc._enrich_chat_result_with_relationship = lambda result, n: result

        svc.npc_chat_respond(player, "Mara", "more", "direct")

        assert player.__dict__["_active_chat_npc_id"] == "Mara"


# ---------------------------------------------------------------------------
# Adapter generate_turn parsing / clamping
# ---------------------------------------------------------------------------


class TestAdapterGenerateTurn:
    def _adapter(self, raw):
        import ai.llm_client as llm

        adapter = llm.NpcChatLLMAdapter.__new__(llm.NpcChatLLMAdapter)
        adapter.enabled = True
        adapter._call_llm = lambda *a, **k: raw
        return adapter

    def test_parses_and_clamps(self):
        adapter = self._adapter(
            '{"npc_text": "The road is long.", "conversation_quality": "positive", '
            '"reputation_delta": 99, "loquacity_delta": 99, '
            '"jean_options": [{"tone":"direct","text":"a"},'
            '{"tone":"guarded","text":"b"},{"tone":"open","text":"c"}]}'
        )
        result = adapter.generate_turn("sys", [], is_opening=False, jean_text="hi")
        assert result["npc_text"] == "The road is long."
        assert result["reputation_delta"] == 5  # clamped
        assert result["loquacity_delta"] == 15  # clamped
        assert len(result["jean_options"]) == 3

    def test_invalid_quality_defaults_neutral(self):
        adapter = self._adapter(
            '{"npc_text": "Hmm.", "conversation_quality": "weird", '
            '"jean_options": []}'
        )
        result = adapter.generate_turn("sys", [], is_opening=True)
        assert result["conversation_quality"] == "neutral"
        assert result["jean_options"] == []

    def test_missing_npc_text_returns_none(self):
        adapter = self._adapter('{"conversation_quality": "neutral"}')
        assert adapter.generate_turn("sys", [], is_opening=True) is None

    def test_none_raw_returns_none(self):
        adapter = self._adapter(None)
        assert adapter.generate_turn("sys", [], is_opening=True) is None
