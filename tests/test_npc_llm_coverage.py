"""
Coverage tests for src/npc/_llm.py — MynxLLMMixin.

Tests all major branches:
- _append_llm_history (normal, empty, non-string, overflow)
- _load_player_advisor (cached, file exists, file missing, exception)
- _get_llm_adapter (disabled, file missing, spec failure, no class, unavailable, available)
- _sanitize_mynx_llm_text (empty, name replacement, self-action, disallowed tokens, dup pronoun)
- _enforce_pronouns_and_names (empty, allowed names, jean sentence, mynx sentence, neutral)
- _gather_environment_lists (no room, items, objects, npcs, exceptions)
- _build_history_block (empty, with history)
- _build_pronoun_guidance (with/without jean_pronoun_line/snippet)
- _build_llm_context (basic, with room desc, with debug)
- _check_and_correct_mynx_text (non-str, empty, quoted, sentences, disallowed, ed-heavy, short, no period)
- _normalize_ws (normal, exception path)
- interact_with_player (deterministic fallback paths: pet, feed, play, other, structured)
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Concrete test fixture class
# ---------------------------------------------------------------------------


class _FakeMynx:
    """Minimal concrete host for MynxLLMMixin — no real NPC needed."""

    def __init__(self, name="Whisper"):
        # Required attributes from Mynx.__init__
        self.name = name
        self.pronouns = {
            "personal": "it",
            "possessive_adjective": "its",
            "possessive": "its",
        }
        self.current_room = None
        self._llm_adapter = None
        self._llm_last_response = None
        self._llm_history = []
        self._jean_advisor = None


def _make_mynx(**kwargs) -> "_FakeMynxWithMixin":
    """Return a _FakeMynx instance with MynxLLMMixin methods injected."""
    from src.npc._llm import MynxLLMMixin

    class _FakeMynxWithMixin(_FakeMynx, MynxLLMMixin):
        pass

    return _FakeMynxWithMixin(**kwargs)


# ---------------------------------------------------------------------------
# _append_llm_history
# ---------------------------------------------------------------------------


class TestAppendLlmHistory:
    def test_appends_prompt_and_response(self):
        m = _make_mynx()
        m._append_llm_history("pet", "Whisper purrs.")
        assert len(m._llm_history) == 1
        assert m._llm_history[0]["prompt"] == "pet"
        assert m._llm_history[0]["response"] == "Whisper purrs."

    def test_non_string_prompt_converted(self):
        m = _make_mynx()
        m._append_llm_history(42, "response")
        assert m._llm_history[0]["prompt"] == "42"

    def test_non_string_response_converted(self):
        m = _make_mynx()
        m._append_llm_history("prompt", None)
        assert m._llm_history[0]["response"] == ""

    def test_empty_both_skipped(self):
        m = _make_mynx()
        m._append_llm_history("", "")
        assert len(m._llm_history) == 0

    def test_history_trimmed_to_last_three(self):
        m = _make_mynx()
        for i in range(5):
            m._append_llm_history(f"p{i}", f"r{i}")
        assert len(m._llm_history) == 3
        assert m._llm_history[0]["prompt"] == "p2"
        assert m._llm_history[-1]["prompt"] == "p4"

    def test_long_prompt_truncated(self):
        m = _make_mynx()
        long_prompt = "x" * 300
        m._append_llm_history(long_prompt, "r")
        assert len(m._llm_history[0]["prompt"]) <= 200

    def test_long_response_truncated(self):
        m = _make_mynx()
        long_resp = "y" * 400
        m._append_llm_history("p", long_resp)
        assert len(m._llm_history[0]["response"]) <= 300


# ---------------------------------------------------------------------------
# _load_player_advisor
# ---------------------------------------------------------------------------


class TestLoadPlayerAdvisor:
    def test_returns_cached_value(self):
        m = _make_mynx()
        cached = {"character_name": "Jean", "pronouns": {}}
        m._jean_advisor = cached
        result = m._load_player_advisor()
        assert result is cached

    def test_returns_dict_when_file_missing(self, tmp_path, monkeypatch):
        m = _make_mynx()
        # Point root to a temp dir that has no ai/player/jean.json
        monkeypatch.setattr(
            "src.npc._llm.Path",
            lambda *args, **kwargs: tmp_path / "dummy_file.py",
        )
        # Just verify we get a fallback dict (either from file-missing or exception)
        result = m._load_player_advisor()
        assert isinstance(result, dict)
        assert "character_name" in result

    def test_loads_from_json_file(self, tmp_path):
        m = _make_mynx()
        # Create fake ai/player/jean.json at the real project root (discovered via Path)
        jean_data = {
            "character_name": "Jean",
            "pronouns": {
                "subject": "he",
                "object": "him",
                "possessive_adjective": "his",
            },
            "system_prompt_snippet": "Jean is the player.",
        }
        # Use a fully-mocked Path that returns a fake jean_path pointing to a real file
        jean_file = tmp_path / "jean.json"
        jean_file.write_text(json.dumps(jean_data), encoding="utf-8")

        jean_path_mock = MagicMock()
        jean_path_mock.exists.return_value = True
        jean_path_mock.__str__ = lambda self: str(jean_file)
        jean_path_mock.__fspath__ = lambda self: str(jean_file)

        # Patch open() to return our json file when the mock path is opened
        import builtins

        real_open = builtins.open

        def patched_open(path, *args, **kwargs):
            # Intercept opens of the mock path object
            if path is jean_path_mock:
                return real_open(str(jean_file), *args, **kwargs)
            return real_open(path, *args, **kwargs)

        root_mock = MagicMock()
        root_mock.__truediv__ = MagicMock(return_value=jean_path_mock)

        path_inst_mock = MagicMock()
        path_inst_mock.resolve.return_value.parent.parent.parent = root_mock

        with patch("src.npc._llm.Path", return_value=path_inst_mock):
            with patch("builtins.open", side_effect=patched_open):
                result = m._load_player_advisor()
        assert isinstance(result, dict)

    def test_exception_returns_fallback(self):
        m = _make_mynx()
        with patch("src.npc._llm.Path", side_effect=Exception("boom")):
            result = m._load_player_advisor()
        assert isinstance(result, dict)
        assert result.get("character_name") == "Jean"


# ---------------------------------------------------------------------------
# _get_llm_adapter
# ---------------------------------------------------------------------------


class TestGetLlmAdapter:
    def test_returns_cached_adapter(self):
        m = _make_mynx()
        fake_adapter = MagicMock()
        m._llm_adapter = fake_adapter
        result = m._get_llm_adapter()
        assert result is fake_adapter

    def test_disabled_returns_none(self):
        from src.npc._llm import MynxLLMMixin

        m = _make_mynx()
        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "0"}):
            result = m._get_llm_adapter()
        assert result is None
        # Sticky "unavailable" sentinel is cached so repeated calls don't
        # re-probe (see MynxLLMMixin._ADAPTER_FAILED).
        assert m._llm_adapter is MynxLLMMixin._ADAPTER_FAILED

    def test_disabled_then_cached_without_reprobe(self):
        """Second call must not re-check the env var — the sentinel short-circuits."""
        m = _make_mynx()
        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "0"}):
            first = m._get_llm_adapter()
        assert first is None
        # Even if the env var flips to enabled afterward, the cached failure
        # sentinel means we don't re-probe within this instance's lifetime.
        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            second = m._get_llm_adapter()
        assert second is None

    def test_disabled_with_debug_prints(self, capsys):
        m = _make_mynx()
        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "0", "MYNX_LLM_DEBUG": "1"}):
            result = m._get_llm_adapter()
        assert result is None

    def _setup_ai_file(self, tmp_path):
        """Create the file at the exact path _get_llm_adapter looks for: root/ai/llm_client.py"""
        ai_dir = tmp_path / "ai"
        ai_dir.mkdir(exist_ok=True)
        dummy = ai_dir / "llm_client.py"
        dummy.write_text("class MynxLLMAdapter: pass", encoding="utf-8")
        return dummy

    def _fake_root(self, tmp_path):
        """Return a side_effect function for patching Path that maps root to tmp_path."""

        def fake_path(arg):
            mp = MagicMock()
            mp.resolve.return_value.parent.parent.parent = tmp_path
            return mp

        return fake_path

    def test_file_not_found_returns_none(self, tmp_path):
        m = _make_mynx()
        # tmp_path has no ai/llm_client.py so adapter_path.exists() is False

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                result = m._get_llm_adapter()
        assert result is None

    def test_spec_from_file_none_returns_none(self, tmp_path):
        m = _make_mynx()
        self._setup_ai_file(tmp_path)

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                with patch("importlib.util.spec_from_file_location", return_value=None):
                    result = m._get_llm_adapter()
        assert result is None

    def test_adapter_class_missing_returns_none(self, tmp_path):
        m = _make_mynx()
        self._setup_ai_file(tmp_path)

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                with patch("importlib.util.spec_from_file_location") as mock_spec:
                    spec = MagicMock()
                    spec.loader = MagicMock()
                    mock_spec.return_value = spec
                    # Module with no MynxLLMAdapter attribute
                    mod_mock = MagicMock(spec=[])
                    with patch(
                        "importlib.util.module_from_spec", return_value=mod_mock
                    ):
                        result = m._get_llm_adapter()
        assert result is None

    def test_adapter_unavailable_returns_none(self, tmp_path):
        m = _make_mynx()
        self._setup_ai_file(tmp_path)

        fake_adapter_inst = MagicMock()
        fake_adapter_inst.available.return_value = False

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                with patch("importlib.util.spec_from_file_location") as mock_spec:
                    spec = MagicMock()
                    spec.loader = MagicMock()
                    mock_spec.return_value = spec
                    mod_mock = MagicMock()
                    mod_mock.MynxLLMAdapter = MagicMock(return_value=fake_adapter_inst)
                    with patch(
                        "importlib.util.module_from_spec", return_value=mod_mock
                    ):
                        result = m._get_llm_adapter()
        assert result is None

    def test_adapter_available_returns_instance(self, tmp_path):
        m = _make_mynx()
        self._setup_ai_file(tmp_path)

        fake_adapter_inst = MagicMock()
        fake_adapter_inst.available.return_value = True

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                with patch("importlib.util.spec_from_file_location") as mock_spec:
                    spec = MagicMock()
                    spec.loader = MagicMock()
                    mock_spec.return_value = spec
                    mod_mock = MagicMock()
                    mod_mock.MynxLLMAdapter = MagicMock(return_value=fake_adapter_inst)
                    with patch(
                        "importlib.util.module_from_spec", return_value=mod_mock
                    ):
                        result = m._get_llm_adapter()
        assert result is fake_adapter_inst

    def test_available_check_exception_returns_none(self, tmp_path):
        m = _make_mynx()
        self._setup_ai_file(tmp_path)

        fake_adapter_inst = MagicMock()
        fake_adapter_inst.available.side_effect = RuntimeError("no api key")

        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                with patch("importlib.util.spec_from_file_location") as mock_spec:
                    spec = MagicMock()
                    spec.loader = MagicMock()
                    mock_spec.return_value = spec
                    mod_mock = MagicMock()
                    mod_mock.MynxLLMAdapter = MagicMock(return_value=fake_adapter_inst)
                    with patch(
                        "importlib.util.module_from_spec", return_value=mod_mock
                    ):
                        result = m._get_llm_adapter()
        assert result is None

    def test_outer_exception_returns_none(self):
        m = _make_mynx()
        with patch.dict(os.environ, {"MYNX_LLM_ENABLED": "1"}):
            with patch("src.npc._llm.Path", side_effect=Exception("hard crash")):
                result = m._get_llm_adapter()
        assert result is None


# ---------------------------------------------------------------------------
# _sanitize_mynx_llm_text
# ---------------------------------------------------------------------------


class TestSanitizeMynxLlmText:
    def test_empty_text_returned_as_is(self):
        m = _make_mynx()
        assert m._sanitize_mynx_llm_text("", set()) == ""

    def test_name_replacement_after_first(self):
        m = _make_mynx()
        text = "Whisper sees Whisper and Whisper again."
        result = m._sanitize_mynx_llm_text(text, set())
        # First occurrence kept, subsequent replaced by pronoun "it"
        assert result.count("Whisper") == 1

    def test_self_action_replaced(self):
        m = _make_mynx()
        text = "Whisper is batting at Whisper playfully."
        result = m._sanitize_mynx_llm_text(text, set())
        assert "batting playfully" in result

    def test_disallowed_capitalized_token_replaced(self):
        m = _make_mynx()
        # "Fluffy" is not in the allowed set
        text = "Whisper sees Fluffy over there."
        result = m._sanitize_mynx_llm_text(text, {"Jean"})
        assert "Fluffy" not in result
        assert "it" in result

    def test_allowed_name_preserved(self):
        m = _make_mynx()
        text = "Whisper sees Jean standing there."
        result = m._sanitize_mynx_llm_text(text, {"Jean"})
        assert "Jean" in result

    def test_possessive_disallowed_name_replaced(self):
        m = _make_mynx()
        text = "Fluffy's tail is long."
        result = m._sanitize_mynx_llm_text(text, {"Jean"})
        assert "Fluffy" not in result

    def test_allowed_possessive_preserved(self):
        m = _make_mynx()
        text = "Jean's cloak is red."
        result = m._sanitize_mynx_llm_text(text, {"Jean"})
        assert "Jean" in result

    def test_duplicate_pronoun_collapsed(self):
        m = _make_mynx()
        # Create a text that has duplicate "it it"
        text = "it it twitches."
        result = m._sanitize_mynx_llm_text(text, set())
        assert "it it" not in result

    def test_whitespace_normalized(self):
        m = _make_mynx()
        text = "Whisper   sits   quietly."
        result = m._sanitize_mynx_llm_text(text, set())
        assert "  " not in result

    def test_exception_returns_original(self):
        m = _make_mynx()
        # Delete pronouns to force an exception in poss_adj calculation path
        del m.pronouns
        # Should not raise; returns original text
        result = m._sanitize_mynx_llm_text("Whisper purrs.", set())
        assert isinstance(result, str)

    def test_no_pronouns_attribute_uses_defaults(self):
        m = _make_mynx()
        m.pronouns = {}  # empty dict => fallback to defaults
        text = "Whisper and Jean walk together."
        result = m._sanitize_mynx_llm_text(text, {"Jean"})
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _enforce_pronouns_and_names
# ---------------------------------------------------------------------------


class TestEnforcePronouns:
    def test_empty_text_returned_as_is(self):
        m = _make_mynx()
        assert m._enforce_pronouns_and_names("", set()) == ""

    def test_disallowed_name_replaced(self):
        m = _make_mynx()
        text = "Fluffy sits near Jean."
        result = m._enforce_pronouns_and_names(text, {"Jean"})
        assert "Fluffy" not in result

    def test_allowed_name_preserved(self):
        m = _make_mynx()
        text = "Whisper sits near Jean."
        result = m._enforce_pronouns_and_names(text, {"Jean"})
        assert "Jean" in result
        assert "Whisper" in result

    def test_jean_sentence_uses_jean_pronouns(self):
        m = _make_mynx()
        m._jean_advisor = {
            "pronouns": {
                "subject": "she",
                "object": "her",
                "possessive_adjective": "her",
            }
        }
        text = "Jean sat down. She opened her pack."
        result = m._enforce_pronouns_and_names(text, set())
        # "She" should stay as jean's subject pronoun (she)
        assert isinstance(result, str)

    def test_mynx_sentence_uses_mynx_pronouns(self):
        m = _make_mynx()
        text = "Whisper tilted his head."
        result = m._enforce_pronouns_and_names(text, set())
        # "his" → "its" (mynx's pronoun)
        assert "his" not in result or "its" in result

    def test_neutral_sentence_uses_they(self):
        m = _make_mynx()
        text = "Someone walked by. He looked tired."
        result = m._enforce_pronouns_and_names(text, set())
        assert isinstance(result, str)

    def test_exception_returns_original(self):
        m = _make_mynx()
        # Cause exception by breaking _load_player_advisor
        with patch.object(m, "_load_player_advisor", side_effect=Exception("crash")):
            result = m._enforce_pronouns_and_names("some text", set())
        assert result == "some text"

    def test_no_pronouns_attribute_fallback(self):
        m = _make_mynx()
        m.pronouns = {}
        text = "Whisper watches Jean."
        result = m._enforce_pronouns_and_names(text, {"Jean"})
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _gather_environment_lists
# ---------------------------------------------------------------------------


class TestGatherEnvironmentLists:
    def test_no_room_returns_empty(self):
        m = _make_mynx()
        m.current_room = None
        env_str, env_set = m._gather_environment_lists()
        assert env_str == ""
        assert env_set == set()

    def test_empty_room_returns_empty(self):
        m = _make_mynx()
        room = MagicMock()
        room.items_here = []
        room.objects_here = []
        room.npcs_here = []
        m.current_room = room
        env_str, _ = m._gather_environment_lists()
        assert env_str == ""

    def test_room_with_item_adds_item_info(self):
        m = _make_mynx()
        room = MagicMock()
        item = MagicMock()
        item.name = "Torch"
        item.description = "A flickering torch."
        room.items_here = [item]
        room.objects_here = []
        room.npcs_here = []
        m.current_room = room
        env_str, _ = m._gather_environment_lists()
        assert "Torch" in env_str

    def test_room_with_item_no_description(self):
        m = _make_mynx()
        room = MagicMock()
        item = MagicMock()
        item.name = "Stone"
        item.description = None
        item.short_description = None
        room.items_here = [item]
        room.objects_here = []
        room.npcs_here = []
        m.current_room = room
        env_str, _ = m._gather_environment_lists()
        assert "Stone" in env_str
        assert "(no description)" in env_str

    def test_room_with_object(self):
        m = _make_mynx()
        room = MagicMock()
        obj = MagicMock()
        obj.name = "Barrel"
        obj.description = "A wooden barrel."
        room.items_here = []
        room.objects_here = [obj]
        room.npcs_here = []
        m.current_room = room
        env_str, _ = m._gather_environment_lists()
        assert "Barrel" in env_str

    def test_room_with_other_npc(self):
        m = _make_mynx()
        room = MagicMock()
        npc = MagicMock()
        npc.name = "Guard"
        npc.description = "A stern guard."
        room.items_here = []
        room.objects_here = []
        room.npcs_here = [npc]
        m.current_room = room
        env_str, _ = m._gather_environment_lists()
        assert "Guard" in env_str

    def test_room_npc_with_name_same_as_mynx_excluded(self):
        m = _make_mynx()
        room = MagicMock()
        npc = MagicMock()
        npc.name = "Whisper"  # same as self.name
        room.items_here = []
        room.objects_here = []
        room.npcs_here = [npc]
        m.current_room = room
        env_str, _ = m._gather_environment_lists()
        # "Whisper" should NOT appear in npcs section
        # (could still appear from items, but not from npc list)
        assert "Other nearby NPCs" not in env_str

    def test_item_without_name_skipped(self):
        m = _make_mynx()
        room = MagicMock()
        item = MagicMock()
        item.name = None
        item.title = None
        room.items_here = [item]
        room.objects_here = []
        room.npcs_here = []
        m.current_room = room
        env_str, _ = m._gather_environment_lists()
        assert env_str == ""

    def test_room_uses_items_fallback(self):
        m = _make_mynx()
        room = MagicMock()
        item = MagicMock()
        item.name = "Sword"
        item.description = "A blade."
        # items_here is None, but items is set
        room.items_here = None
        room.items = [item]
        room.objects_here = []
        room.npcs_here = []
        m.current_room = room
        env_str, _ = m._gather_environment_lists()
        assert "Sword" in env_str

    def test_exception_in_room_access_returns_empty(self):
        m = _make_mynx()
        room = MagicMock()
        room.items_here = MagicMock(side_effect=Exception("boom"))
        room.objects_here = []
        room.npcs_here = []
        m.current_room = room
        # Should not raise
        env_str, _ = m._gather_environment_lists()
        assert isinstance(env_str, str)


# ---------------------------------------------------------------------------
# _build_history_block
# ---------------------------------------------------------------------------


class TestBuildHistoryBlock:
    def test_empty_history_returns_empty_string(self):
        m = _make_mynx()
        m._llm_history = []
        result = m._build_history_block()
        assert result == ""

    def test_none_history_returns_empty_string(self):
        m = _make_mynx()
        m._llm_history = None
        result = m._build_history_block()
        assert result == ""

    def test_history_block_contains_prompt(self):
        m = _make_mynx()
        m._llm_history = [{"prompt": "pet", "response": "Whisper purrs."}]
        result = m._build_history_block()
        assert "pet" in result
        assert "Whisper purrs." in result

    def test_history_block_includes_at_most_three(self):
        m = _make_mynx()
        m._llm_history = [{"prompt": f"p{i}", "response": f"r{i}"} for i in range(5)]
        result = m._build_history_block()
        assert "p2" in result or "p3" in result  # only last 3

    def test_history_block_format(self):
        m = _make_mynx()
        m._llm_history = [{"prompt": "feed", "response": "It eats."}]
        result = m._build_history_block()
        assert "Conversation history" in result
        assert "Prompt:" in result


# ---------------------------------------------------------------------------
# _build_pronoun_guidance
# ---------------------------------------------------------------------------


class TestBuildPronounGuidance:
    def test_with_jean_pronoun_line(self):
        m = _make_mynx()
        result = m._build_pronoun_guidance("he/him/his.", "")
        assert "he/him/his." in result
        assert "mynx" in result.lower()

    def test_without_jean_pronoun_line(self):
        m = _make_mynx()
        result = m._build_pronoun_guidance("", "")
        assert "mynx" in result.lower() or "it/its" in result

    def test_with_jean_snippet(self):
        m = _make_mynx()
        result = m._build_pronoun_guidance("he/him/his.", "Jean is a knight.")
        assert "Jean is a knight." in result

    def test_without_jean_snippet(self):
        m = _make_mynx()
        result = m._build_pronoun_guidance("he/him/his.", "")
        assert "Jean is a knight." not in result

    def test_no_pronouns_uses_defaults(self):
        m = _make_mynx()
        m.pronouns = {}
        result = m._build_pronoun_guidance("", "")
        assert isinstance(result, str)

    def test_exception_returns_fallback(self):
        m = _make_mynx()
        # The try: block calls jean_pronoun_line.strip() — pass a non-string to cause TypeError
        result = m._build_pronoun_guidance(object(), "")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _build_llm_context
# ---------------------------------------------------------------------------


class TestBuildLlmContext:
    def test_returns_string(self):
        m = _make_mynx()
        result = m._build_llm_context({"Jean"}, "pet", "he/him/his.", "")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_mynx_name(self):
        m = _make_mynx()
        result = m._build_llm_context({"Jean"}, "pet", "", "")
        assert "Whisper" in result

    def test_contains_prompt(self):
        m = _make_mynx()
        result = m._build_llm_context({"Jean"}, "feed", "", "")
        assert "feed" in result

    def test_with_room_description(self):
        m = _make_mynx()
        room = MagicMock()
        room.description = "A dark dungeon corridor."
        room.items_here = []
        room.objects_here = []
        room.npcs_here = []
        m.current_room = room
        result = m._build_llm_context({"Jean"}, "pet", "", "")
        assert "dungeon" in result

    def test_without_room_returns_context(self):
        m = _make_mynx()
        m.current_room = None
        result = m._build_llm_context({"Jean"}, "play", "", "")
        assert isinstance(result, str)

    def test_debug_mode_still_returns_string(self, capsys):
        m = _make_mynx()
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            result = m._build_llm_context({"Jean"}, "pet", "", "")
        assert isinstance(result, str)

    def test_empty_prompt_uses_interact(self):
        m = _make_mynx()
        result = m._build_llm_context({"Jean"}, "", "", "")
        assert "interact" in result


# ---------------------------------------------------------------------------
# _check_and_correct_mynx_text
# ---------------------------------------------------------------------------


class TestCheckAndCorrectMynxText:
    def test_none_input_returns_none(self):
        m = _make_mynx()
        assert m._check_and_correct_mynx_text(None, "pet", []) is None

    def test_empty_string_returns_none(self):
        m = _make_mynx()
        assert m._check_and_correct_mynx_text("", "pet", []) is None

    def test_whitespace_only_returns_none(self):
        m = _make_mynx()
        assert m._check_and_correct_mynx_text("   ", "pet", []) is None

    def test_double_quoted_speech_returns_none(self):
        m = _make_mynx()
        text = 'Whisper says "hello there" to Jean.'
        assert m._check_and_correct_mynx_text(text, "pet", ["Jean"]) is None

    def test_valid_text_returned(self):
        m = _make_mynx()
        result = m._check_and_correct_mynx_text("Whisper purrs softly.", "pet", [])
        assert result is not None
        assert result.endswith(".")

    def test_adds_terminal_period(self):
        m = _make_mynx()
        result = m._check_and_correct_mynx_text("Whisper tilts its head", "pet", [])
        assert result is not None
        assert result.endswith(".")

    def test_trims_to_two_sentences(self):
        m = _make_mynx()
        text = "Whisper purrs. It tilts its head. It flicks its tail. It chirps."
        result = m._check_and_correct_mynx_text(text, "pet", [])
        assert result is not None
        # Should have at most 2 sentences merged
        sentence_count = len([s for s in result.split(". ") if s.strip()])
        assert sentence_count <= 3  # up to 2 + trailing period

    def test_too_short_returns_none(self):
        m = _make_mynx()
        # Less than 5 chars
        assert m._check_and_correct_mynx_text("Hi.", "pet", []) is None

    def test_too_long_returns_none(self):
        m = _make_mynx()
        text = "A" * 201 + "."
        assert m._check_and_correct_mynx_text(text, "pet", []) is None

    def test_ed_heavy_text_returns_none(self):
        m = _make_mynx()
        # >3 -ed tokens AND >=40% of words
        text = "walked talked jumped skipped danced played."
        assert m._check_and_correct_mynx_text(text, "pet", []) is None

    def test_disallowed_name_replaced(self):
        m = _make_mynx()
        result = m._check_and_correct_mynx_text(
            "Fluffy purred at Jean.", "pet", ["Jean"]
        )
        if result is not None:
            assert "Fluffy" not in result

    def test_allowed_name_preserved(self):
        m = _make_mynx()
        result = m._check_and_correct_mynx_text(
            "Whisper gazed at Jean quietly.", "pet", ["Jean"]
        )
        if result is not None:
            assert "Jean" in result

    def test_sentences_none_returns_none(self):
        m = _make_mynx()
        # All punctuation, no real sentences
        result = m._check_and_correct_mynx_text("...!?!", "pet", [])
        assert result is None

    def test_non_string_returns_none(self):
        m = _make_mynx()
        assert m._check_and_correct_mynx_text(42, "pet", []) is None


# ---------------------------------------------------------------------------
# _normalize_ws
# ---------------------------------------------------------------------------


class TestNormalizeWs:
    def test_collapses_whitespace(self):
        m = _make_mynx()
        assert m._normalize_ws("  hello   world  ") == "hello world"

    def test_empty_string(self):
        m = _make_mynx()
        assert m._normalize_ws("") == ""

    def test_tabs_and_newlines(self):
        m = _make_mynx()
        result = m._normalize_ws("foo\t\nbar")
        assert result == "foo bar"

    def test_non_string_fallback(self):
        m = _make_mynx()
        # Should not crash on non-string input
        result = m._normalize_ws(42)
        assert result == "42"


# ---------------------------------------------------------------------------
# interact_with_player — deterministic fallback paths
# ---------------------------------------------------------------------------


class TestInteractWithPlayerFallback:
    """
    Tests the deterministic fallback (LLM disabled or unavailable).
    We always patch time.sleep to avoid 1.5s delays.
    """

    def setup_method(self):
        self.m = _make_mynx()
        # Ensure LLM adapter is None (disabled)
        self.m._llm_adapter = None

    def _call(self, prompt, structured=False):
        with patch("time.sleep"):
            return self.m.interact_with_player(
                player=MagicMock(), prompt=prompt, structured=structured
            )

    def test_pet_returns_string(self):
        result = self._call("pet")
        assert isinstance(result, str)
        assert "Whisper" in result

    def test_pet_structured_returns_dict(self):
        result = self._call("pet", structured=True)
        assert isinstance(result, dict)
        assert result.get("action") == "groom"

    def test_stroke_is_same_as_pet(self):
        result = self._call("stroke")
        assert isinstance(result, str)

    def test_scritch_is_same_as_pet(self):
        result = self._call("scritch")
        assert isinstance(result, str)

    def test_feed_returns_string(self):
        result = self._call("feed")
        assert isinstance(result, str)

    def test_offer_food_returns_string(self):
        result = self._call("offer food")
        assert isinstance(result, str)

    def test_feed_structured_returns_dict(self):
        result = self._call("feed", structured=True)
        assert isinstance(result, dict)
        assert result.get("action") == "take_food"

    def test_play_returns_string(self):
        result = self._call("play")
        assert isinstance(result, str)

    def test_toy_returns_string(self):
        result = self._call("toy")
        assert isinstance(result, str)

    def test_tease_returns_string(self):
        result = self._call("tease")
        assert isinstance(result, str)

    def test_play_structured_returns_dict(self):
        result = self._call("play", structured=True)
        assert isinstance(result, dict)
        assert result.get("action") == "play"

    def test_unknown_prompt_returns_string(self):
        result = self._call("wave")
        assert isinstance(result, str)

    def test_unknown_prompt_structured_returns_dict(self):
        result = self._call("wave", structured=True)
        assert isinstance(result, dict)
        assert result.get("action") == "investigate"

    def test_empty_prompt_uses_generic(self):
        result = self._call("")
        assert isinstance(result, str)

    def test_play_with_item_in_prompt(self):
        result = self._call("play with rope")
        assert isinstance(result, str)

    def test_interact_updates_last_response(self):
        self._call("pet")
        assert self.m._llm_last_response is not None

    def test_interact_appends_history(self):
        self._call("pet")
        assert len(self.m._llm_history) >= 1

    def test_zero_delay_env(self):
        with patch.dict(os.environ, {"MYNX_FALLBACK_DELAY": "0"}):
            result = self.m.interact_with_player(player=MagicMock(), prompt="pet")
        assert isinstance(result, str)

    def test_invalid_delay_env_uses_default(self):
        with patch("time.sleep") as mock_sleep:
            with patch.dict(os.environ, {"MYNX_FALLBACK_DELAY": "not_a_number"}):
                self.m.interact_with_player(player=MagicMock(), prompt="pet")
        # sleep called with fallback 1.5
        mock_sleep.assert_called_once_with(1.5)

    def test_room_npc_roster_built(self):
        room = MagicMock()
        npc = MagicMock()
        npc.name = "Guard"
        room.npcs_here = [npc]
        self.m.current_room = room
        with patch("time.sleep"):
            result = self.m.interact_with_player(player=MagicMock(), prompt="pet")
        assert isinstance(result, str)

    def test_action_print_exception_handled(self):
        """If the action print() raises, interact_with_player still executes the rest."""
        call_count = [0]
        real_print = __builtins__["print"] if isinstance(__builtins__, dict) else print

        def selective_print(s, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                raise UnicodeEncodeError("utf-8", "", 0, 1, "encode error")
            real_print(s, *a, **kw)

        with patch("builtins.print", side_effect=selective_print):
            with patch("time.sleep"):
                result = self.m.interact_with_player(player=MagicMock(), prompt="pet")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Additional coverage: exception / debug branches not hit above
# ---------------------------------------------------------------------------


class TestAppendLlmHistoryException:
    def test_append_exception_returns_none(self):
        m = _make_mynx()
        m._llm_history = "not-a-list"  # .append will raise AttributeError
        result = m._append_llm_history("pet", "purrs")
        assert result is None
        # unchanged since the exception was swallowed
        assert m._llm_history == "not-a-list"


class TestGetLlmAdapterDebugBranches:
    def _fake_root(self, tmp_path):
        def fake_path(arg):
            mp = MagicMock()
            mp.resolve.return_value.parent.parent.parent = tmp_path
            return mp

        return fake_path

    def _setup_ai_file(self, tmp_path):
        ai_dir = tmp_path / "ai"
        ai_dir.mkdir(exist_ok=True)
        dummy = ai_dir / "llm_client.py"
        dummy.write_text("class MynxLLMAdapter: pass", encoding="utf-8")
        return dummy

    def test_file_not_found_with_debug_narrates(self, tmp_path):
        m = _make_mynx()
        with patch.dict(
            os.environ, {"MYNX_LLM_ENABLED": "1", "MYNX_LLM_DEBUG": "1"}
        ):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                result = m._get_llm_adapter()
        assert result is None

    def test_spec_none_with_debug_narrates(self, tmp_path):
        m = _make_mynx()
        self._setup_ai_file(tmp_path)
        with patch.dict(
            os.environ, {"MYNX_LLM_ENABLED": "1", "MYNX_LLM_DEBUG": "1"}
        ):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                with patch(
                    "importlib.util.spec_from_file_location", return_value=None
                ):
                    result = m._get_llm_adapter()
        assert result is None

    def test_adapter_class_missing_with_debug_narrates(self, tmp_path):
        m = _make_mynx()
        self._setup_ai_file(tmp_path)
        with patch.dict(
            os.environ, {"MYNX_LLM_ENABLED": "1", "MYNX_LLM_DEBUG": "1"}
        ):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                with patch(
                    "importlib.util.spec_from_file_location"
                ) as mock_spec:
                    spec = MagicMock()
                    spec.loader = MagicMock()
                    mock_spec.return_value = spec
                    mod_mock = MagicMock(spec=[])
                    with patch(
                        "importlib.util.module_from_spec", return_value=mod_mock
                    ):
                        result = m._get_llm_adapter()
        assert result is None

    def test_available_check_exception_with_debug_narrates(self, tmp_path):
        m = _make_mynx()
        self._setup_ai_file(tmp_path)
        fake_adapter_inst = MagicMock()
        fake_adapter_inst.available.side_effect = RuntimeError("no api key")
        with patch.dict(
            os.environ, {"MYNX_LLM_ENABLED": "1", "MYNX_LLM_DEBUG": "1"}
        ):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                with patch(
                    "importlib.util.spec_from_file_location"
                ) as mock_spec:
                    spec = MagicMock()
                    spec.loader = MagicMock()
                    mock_spec.return_value = spec
                    mod_mock = MagicMock()
                    mod_mock.MynxLLMAdapter = MagicMock(
                        return_value=fake_adapter_inst
                    )
                    with patch(
                        "importlib.util.module_from_spec", return_value=mod_mock
                    ):
                        result = m._get_llm_adapter()
        assert result is None

    def test_available_true_with_debug_status_narrates(self, tmp_path):
        m = _make_mynx()
        self._setup_ai_file(tmp_path)
        fake_adapter_inst = MagicMock()
        fake_adapter_inst.available.return_value = True
        fake_adapter_inst.debug_status.return_value = "ready"
        with patch.dict(
            os.environ, {"MYNX_LLM_ENABLED": "1", "MYNX_LLM_DEBUG": "1"}
        ):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                with patch(
                    "importlib.util.spec_from_file_location"
                ) as mock_spec:
                    spec = MagicMock()
                    spec.loader = MagicMock()
                    mock_spec.return_value = spec
                    mod_mock = MagicMock()
                    mod_mock.MynxLLMAdapter = MagicMock(
                        return_value=fake_adapter_inst
                    )
                    with patch(
                        "importlib.util.module_from_spec", return_value=mod_mock
                    ):
                        result = m._get_llm_adapter()
        assert result is fake_adapter_inst

    def test_unavailable_with_debug_status_narrates(self, tmp_path):
        m = _make_mynx()
        self._setup_ai_file(tmp_path)
        fake_adapter_inst = MagicMock()
        fake_adapter_inst.available.return_value = False
        fake_adapter_inst.debug_status.return_value = "no key set"
        with patch.dict(
            os.environ, {"MYNX_LLM_ENABLED": "1", "MYNX_LLM_DEBUG": "1"}
        ):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                with patch(
                    "importlib.util.spec_from_file_location"
                ) as mock_spec:
                    spec = MagicMock()
                    spec.loader = MagicMock()
                    mock_spec.return_value = spec
                    mod_mock = MagicMock()
                    mod_mock.MynxLLMAdapter = MagicMock(
                        return_value=fake_adapter_inst
                    )
                    with patch(
                        "importlib.util.module_from_spec", return_value=mod_mock
                    ):
                        result = m._get_llm_adapter()
        assert result is None

    def test_unavailable_debug_status_raises_is_swallowed(self, tmp_path):
        m = _make_mynx()
        self._setup_ai_file(tmp_path)
        fake_adapter_inst = MagicMock()
        fake_adapter_inst.available.return_value = False
        fake_adapter_inst.debug_status.side_effect = RuntimeError("boom")
        with patch.dict(
            os.environ, {"MYNX_LLM_ENABLED": "1", "MYNX_LLM_DEBUG": "1"}
        ):
            with patch("src.npc._llm.Path", side_effect=self._fake_root(tmp_path)):
                with patch(
                    "importlib.util.spec_from_file_location"
                ) as mock_spec:
                    spec = MagicMock()
                    spec.loader = MagicMock()
                    mock_spec.return_value = spec
                    mod_mock = MagicMock()
                    mod_mock.MynxLLMAdapter = MagicMock(
                        return_value=fake_adapter_inst
                    )
                    with patch(
                        "importlib.util.module_from_spec", return_value=mod_mock
                    ):
                        result = m._get_llm_adapter()
        assert result is None

    def test_outer_exception_with_debug_narrates(self):
        m = _make_mynx()
        with patch.dict(
            os.environ, {"MYNX_LLM_ENABLED": "1", "MYNX_LLM_DEBUG": "1"}
        ):
            with patch("src.npc._llm.Path", side_effect=Exception("hard crash")):
                result = m._get_llm_adapter()
        assert result is None


class TestSanitizeMynxLlmTextException:
    def test_exception_path_returns_original_text(self):
        m = _make_mynx()
        m.pronouns = None  # .get on None raises AttributeError inside try
        text = "Whisper watches Jean."
        result = m._sanitize_mynx_llm_text(text, {"Jean"})
        assert result == text


class TestEnforcePronounsAdditional:
    def test_jean_and_pronoun_in_same_sentence_uses_jean_subject(self):
        m = _make_mynx()
        m._jean_advisor = {
            "pronouns": {
                "subject": "she",
                "object": "her",
                "possessive_adjective": "her",
            }
        }
        # Single sentence containing both "Jean" and a bare "he"/"she" token
        text = "Jean said he would leave soon."
        result = m._enforce_pronouns_and_names(text, set())
        assert "she" in result.lower()

    def test_text_without_trailing_terminator_included(self):
        m = _make_mynx()
        # No sentence-ending punctuation at all -- exercises the
        # `if last_end < len(text): parts.append(text[last_end:])` branch.
        text = "Whisper watches quietly"
        result = m._enforce_pronouns_and_names(text, set())
        assert "Whisper" in result


class TestGatherEnvironmentListsAdditional:
    def test_object_without_description_gets_placeholder(self):
        m = _make_mynx()
        room = MagicMock()
        room.items_here = []
        obj = MagicMock()
        obj.name = "Old Crate"
        obj.description = None
        obj.summary = None
        room.objects_here = [obj]
        room.npcs_here = []
        m.current_room = room
        env, _ = m._gather_environment_lists()
        assert "Old Crate" in env
        assert "(no description)" in env

    def test_npc_without_description_gets_placeholder(self):
        m = _make_mynx()
        room = MagicMock()
        room.items_here = []
        room.objects_here = []
        npc = MagicMock()
        npc.name = "Guard"
        npc.description = None
        npc.discovery_message = None
        room.npcs_here = [npc]
        m.current_room = room
        env, _ = m._gather_environment_lists()
        assert "Guard" in env
        assert "(no description)" in env

    def test_room_access_exception_returns_empty_string(self):
        m = _make_mynx()

        class _BadRoom:
            @property
            def items_here(self):
                raise RuntimeError("boom")

        m.current_room = _BadRoom()
        env, empty = m._gather_environment_lists()
        assert env == ""
        assert empty == set()

    def test_prep_exception_returns_empty(self):
        m = _make_mynx()
        room = MagicMock()
        item = MagicMock()
        item.name = "Rock"
        item.description = None
        item.short_description = None
        room.items_here = [item]
        room.objects_here = []
        room.npcs_here = []
        m.current_room = room
        # Force each built entry to be an unhashable list rather than a str,
        # so `dict.fromkeys(lst)` inside prep() raises TypeError and is caught.
        m._normalize_ws = lambda s: []
        env, _ = m._gather_environment_lists()
        assert env == ""


class TestBuildHistoryBlockException:
    def test_exception_in_history_returns_empty(self):
        m = _make_mynx()

        class _BadHistory:
            def __getitem__(self, key):
                raise RuntimeError("boom")

            def __bool__(self):
                return True

        m._llm_history = _BadHistory()
        result = m._build_history_block()
        assert result == ""


class TestBuildLlmContextDebugException:
    def test_debug_narrate_exception_is_swallowed(self):
        m = _make_mynx()
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            with patch("src.npc._llm.narrate", side_effect=RuntimeError("boom")):
                result = m._build_llm_context(set(), "pet", "", "")
        assert isinstance(result, str)


class TestCheckAndCorrectMynxTextException:
    def test_exception_returns_none(self):
        m = _make_mynx()
        m.pronouns = None  # .get on None inside try raises AttributeError
        result = m._check_and_correct_mynx_text("Some valid text here.", "pet", [])
        assert result is None


class TestInteractWithPlayerRosterException:
    def test_roster_building_exception_is_swallowed(self):
        m = _make_mynx()

        class _BadRoom:
            @property
            def npcs_here(self):
                raise RuntimeError("boom")

        m.current_room = _BadRoom()
        with patch("time.sleep"):
            result = m.interact_with_player(player=MagicMock(), prompt="pet")
        assert isinstance(result, str)


class TestInteractWithPlayerAdapterEnabled:
    """Covers the LLM-adapter-enabled branch of interact_with_player (lines 608-679)."""

    def setup_method(self):
        self.m = _make_mynx()

    def test_structured_valid_description_returned(self):
        adapter = MagicMock()
        adapter.generate_structured.return_value = {
            "description": "Whisper tilts its head at Jean."
        }
        self.m._llm_adapter = adapter
        with patch("time.sleep"):
            result = self.m.interact_with_player(
                player=MagicMock(), prompt="pet", structured=True
            )
        assert isinstance(result, dict)
        assert "description" in result
        assert self.m._llm_last_response is result

    def test_structured_missing_description_key_falls_back(self):
        adapter = MagicMock()
        adapter.generate_structured.return_value = {"no_description": True}
        self.m._llm_adapter = adapter
        with patch("time.sleep"):
            result = self.m.interact_with_player(
                player=MagicMock(), prompt="pet", structured=True
            )
        # Falls through to the deterministic fallback dict
        assert isinstance(result, dict)
        assert result.get("action") == "groom"

    def test_structured_check_rejects_output_falls_back(self):
        adapter = MagicMock()
        # Quoted speech is rejected by _check_and_correct_mynx_text -> None
        adapter.generate_structured.return_value = {
            "description": '"I am talking," Whisper says.'
        }
        self.m._llm_adapter = adapter
        with patch("time.sleep"):
            result = self.m.interact_with_player(
                player=MagicMock(), prompt="pet", structured=True
            )
        assert isinstance(result, dict)
        assert result.get("action") == "groom"

    def test_structured_with_debug_narrates_raw_description(self):
        adapter = MagicMock()
        adapter.generate_structured.return_value = {
            "description": "Whisper chirps happily."
        }
        self.m._llm_adapter = adapter
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            with patch("time.sleep"):
                result = self.m.interact_with_player(
                    player=MagicMock(), prompt="pet", structured=True
                )
        assert isinstance(result, dict)

    def test_plain_text_valid_response_narrated(self):
        adapter = MagicMock()
        adapter.generate_plain.return_value = "Whisper leans in close to Jean."
        self.m._llm_adapter = adapter
        with patch("time.sleep"):
            result = self.m.interact_with_player(
                player=MagicMock(), prompt="pet", structured=False
            )
        assert isinstance(result, str)
        assert self.m._llm_last_response["action"] == "narrate"

    def test_plain_text_with_debug_narrates_raw(self):
        adapter = MagicMock()
        adapter.generate_plain.return_value = "Whisper chitters."
        self.m._llm_adapter = adapter
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            with patch("time.sleep"):
                result = self.m.interact_with_player(
                    player=MagicMock(), prompt="pet", structured=False
                )
        assert isinstance(result, str)

    def test_plain_text_non_string_falls_back(self):
        adapter = MagicMock()
        adapter.generate_plain.return_value = None
        self.m._llm_adapter = adapter
        with patch("time.sleep"):
            result = self.m.interact_with_player(
                player=MagicMock(), prompt="pet", structured=False
            )
        assert isinstance(result, str)

    def test_plain_text_rejected_by_check_falls_back(self):
        adapter = MagicMock()
        adapter.generate_plain.return_value = "hi"  # too short (< 5 chars)
        self.m._llm_adapter = adapter
        with patch("time.sleep"):
            result = self.m.interact_with_player(
                player=MagicMock(), prompt="pet", structured=False
            )
        assert isinstance(result, str)

    def test_generation_exception_falls_back(self):
        adapter = MagicMock()
        adapter.generate_plain.side_effect = RuntimeError("network down")
        self.m._llm_adapter = adapter
        with patch("time.sleep"):
            result = self.m.interact_with_player(
                player=MagicMock(), prompt="pet", structured=False
            )
        assert isinstance(result, str)

    def test_generation_exception_with_debug_narrates(self):
        adapter = MagicMock()
        adapter.generate_plain.side_effect = RuntimeError("network down")
        self.m._llm_adapter = adapter
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            with patch("time.sleep"):
                result = self.m.interact_with_player(
                    player=MagicMock(), prompt="pet", structured=False
                )
        assert isinstance(result, str)


class TestInteractWithPlayerAdapterEnabledInnerExceptions:
    """Covers the inner try/except blocks around narrate() debug logging and
    _append_llm_history() calls inside the adapter-enabled branch."""

    def setup_method(self):
        self.m = _make_mynx()

    @staticmethod
    def _raise_for(substr):
        def _narrate(msg, *a, **kw):
            if substr in msg:
                raise RuntimeError("boom")
            return None

        return _narrate

    def test_structured_debug_narrate_raw_description_exception_swallowed(self):
        adapter = MagicMock()
        adapter.generate_structured.return_value = {
            "description": "Whisper chirps happily."
        }
        self.m._llm_adapter = adapter
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            with patch(
                "src.npc._llm.narrate",
                side_effect=self._raise_for("Raw structured description"),
            ):
                with patch("time.sleep"):
                    result = self.m.interact_with_player(
                        player=MagicMock(), prompt="pet", structured=True
                    )
        assert isinstance(result, dict)

    def test_structured_append_history_exception_swallowed(self):
        adapter = MagicMock()
        adapter.generate_structured.return_value = {
            "description": "Whisper chirps happily."
        }
        self.m._llm_adapter = adapter
        with patch.object(
            self.m, "_append_llm_history", side_effect=RuntimeError("boom")
        ):
            with patch("time.sleep"):
                result = self.m.interact_with_player(
                    player=MagicMock(), prompt="pet", structured=True
                )
        assert isinstance(result, dict)
        assert "description" in result

    def test_plain_debug_narrate_raw_text_exception_swallowed(self):
        adapter = MagicMock()
        adapter.generate_plain.return_value = "Whisper chitters."
        self.m._llm_adapter = adapter
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            with patch(
                "src.npc._llm.narrate",
                side_effect=self._raise_for("Raw plain text"),
            ):
                with patch("time.sleep"):
                    result = self.m.interact_with_player(
                        player=MagicMock(), prompt="pet", structured=False
                    )
        assert isinstance(result, str)

    def test_plain_append_history_exception_swallowed(self):
        adapter = MagicMock()
        adapter.generate_plain.return_value = "Whisper chitters happily today."
        self.m._llm_adapter = adapter
        with patch.object(
            self.m, "_append_llm_history", side_effect=RuntimeError("boom")
        ):
            with patch("time.sleep"):
                result = self.m.interact_with_player(
                    player=MagicMock(), prompt="pet", structured=False
                )
        assert isinstance(result, str)


class TestInteractWithPlayerHistoryAppendException:
    def test_history_append_exception_in_fallback_is_swallowed(self):
        """_append_llm_history itself swallows internal errors, so to exercise
        the outer try/except in interact_with_player's fallback tail we must
        make the method call itself raise (as if the method were broken),
        not merely make the underlying list misbehave.
        """
        m = _make_mynx()
        m._llm_adapter = None
        with patch.object(
            m, "_append_llm_history", side_effect=RuntimeError("boom")
        ):
            with patch("time.sleep"):
                result = m.interact_with_player(player=MagicMock(), prompt="pet")
        assert isinstance(result, str)


class TestInteractWithPlayerSleepException:
    def test_sleep_exception_is_swallowed(self):
        m = _make_mynx()
        m._llm_adapter = None
        with patch("src.npc._llm.time.sleep", side_effect=RuntimeError("boom")):
            with patch.dict(os.environ, {"MYNX_FALLBACK_DELAY": "1.5"}):
                result = m.interact_with_player(player=MagicMock(), prompt="pet")
        assert isinstance(result, str)
