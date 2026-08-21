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
        """Reads ``<root>/ai/player/jean.json`` and memoises it.

        The previous version of this test built an elaborate tower of
        ``MagicMock`` ``Path`` objects and a patched ``builtins.open``, wrote a
        temp ``jean.json`` — and none of it took effect: the loader read the
        *real* ``ai/player/jean.json`` from the repo. Because the assertion was
        ``isinstance(result, dict)``, that went unnoticed. Patching ``Path``
        with a real ``pathlib.Path`` root does what the mocks were trying to.
        """
        jean_data = {
            "character_name": "Jean",
            "pronouns": {
                "subject": "he",
                "object": "him",
                "possessive_adjective": "his",
            },
            "system_prompt_snippet": "Jean is the player.",
        }
        jean_path = tmp_path / "ai" / "player" / "jean.json"
        jean_path.parent.mkdir(parents=True)
        jean_path.write_text(json.dumps(jean_data), encoding="utf-8")

        m = _make_mynx()
        # _load_player_advisor does Path(__file__).resolve().parent x3
        fake_module_file = tmp_path / "src" / "npc" / "_llm.py"
        fake_module_file.parent.mkdir(parents=True)
        fake_module_file.touch()

        with patch("src.npc._llm.Path", return_value=fake_module_file):
            result = m._load_player_advisor()

        assert result == jean_data
        assert m._jean_advisor is result

    def test_second_call_does_not_touch_the_filesystem_again(self, tmp_path):
        """Memoisation is the only thing keeping a per-chat-turn disk read out
        of the request path."""
        jean_path = tmp_path / "ai" / "player" / "jean.json"
        jean_path.parent.mkdir(parents=True)
        jean_path.write_text('{"character_name": "Jean"}', encoding="utf-8")
        fake_module_file = tmp_path / "src" / "npc" / "_llm.py"
        fake_module_file.parent.mkdir(parents=True)
        fake_module_file.touch()

        m = _make_mynx()
        with patch("src.npc._llm.Path", return_value=fake_module_file) as path_mock:
            first = m._load_player_advisor()
            second = m._load_player_advisor()

        assert first is second
        assert path_mock.call_count == 1

    def test_the_advisor_shipped_in_the_repo_is_the_one_production_loads(self):
        """Pins the real file, not a fixture: the pronoun keys
        ``_enforce_pronouns_and_names`` reads (``subject``/``object``/
        ``possessive_adjective``) must actually be present, or every Jean
        sentence silently falls back to he/him/his defaults."""
        m = _make_mynx()

        advisor = m._load_player_advisor()

        assert advisor["character_name"] == "Jean"
        assert advisor["pronouns"]["subject"] == "he"
        assert advisor["pronouns"]["object"] == "him"
        assert advisor["pronouns"]["possessive_adjective"] == "his"
        assert advisor["system_prompt_snippet"].strip() != ""

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
                mod_mock = MagicMock()
                mod_mock.MynxLLMAdapter = MagicMock(return_value=fake_adapter_inst)
                with patch(
                    "src.npc._llm._load_llm_client_module", return_value=mod_mock
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

    def test_exception_returns_the_text_unchanged(self):
        """``pronouns`` missing entirely raises inside the sanitiser; the
        contract is silent recovery returning the *original* text verbatim, not
        merely "some string" (the old assertion), and certainly not ``None`` —
        a ``None`` here would blank the mynx's line in the chat panel."""
        m = _make_mynx()
        del m.pronouns

        assert m._sanitize_mynx_llm_text("Whisper purrs.", set()) == "Whisper purrs."

    def test_empty_pronouns_dict_falls_back_to_it_its_without_mangling_names(self):
        m = _make_mynx()
        m.pronouns = {}

        result = m._sanitize_mynx_llm_text("Whisper and Jean walk together.", {"Jean"})

        # Both allowed names survive; no pronoun substitution fires.
        assert result == "Whisper and Jean walk together."


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

    def test_lowercase_jean_sentence_uses_jeans_pronouns(self):
        """A sentence naming Jean has its gendered pronouns rewritten to the
        advisor's pronoun set. The old test asserted only ``isinstance(result,
        str)``, so it passed no matter what came out."""
        m = _make_mynx()
        m._jean_advisor = {
            "pronouns": {
                "subject": "she",
                "object": "her",
                "possessive_adjective": "her",
            }
        }

        result = m._enforce_pronouns_and_names("Jean opened his pack.", set())

        assert result == "Jean opened her pack."

    def test_sentence_initial_pronoun_is_eaten_by_the_name_regex(self):
        """CHARACTERIZATION OF A KNOWN DEFECT — see the report accompanying this
        change. ``_re_disallowed_name_token`` is ``\b([A-Z][A-Za-z-]+)('s)?\b``,
        which matches capitalised *pronouns* ("She", "He", "Her") as if they
        were invented creature names, so they are replaced with the mynx's
        pronoun before the sentence-aware pass can classify them. The docstring
        on ``_enforce_pronouns_and_names`` promises the opposite ("sentences
        referencing Jean use Jean's pronouns").

        Pinned exactly so the day the stop-word fix lands, this test goes red
        and has to be updated deliberately rather than silently drifting.
        """
        m = _make_mynx()
        m._jean_advisor = {
            "pronouns": {
                "subject": "she",
                "object": "her",
                "possessive_adjective": "her",
            }
        }

        result = m._enforce_pronouns_and_names(
            "Jean sat down. She opened her pack.", set()
        )

        # Desired: "Jean sat down. She opened her pack."
        assert result == "Jean sat down. it opened them pack."

    def test_mynx_sentence_uses_mynx_pronouns(self):
        m = _make_mynx()
        text = "Whisper tilted his head."
        result = m._enforce_pronouns_and_names(text, set())
        # "his" → "its" (mynx's pronoun)
        assert "his" not in result or "its" in result

    def test_neutral_sentence_lowercase_pronouns_become_they_them_their(self):
        """The neutral branch of ``map_token``: no Jean, no mynx in the
        sentence, so gendered pronouns collapse to they/them/their."""
        m = _make_mynx()

        result = m._enforce_pronouns_and_names(
            "the guard walked by. the guard gripped his spear.", set()
        )

        assert result == "the guard walked by. the guard gripped their spear."

    def test_exception_returns_original(self):
        m = _make_mynx()
        # Cause exception by breaking _load_player_advisor
        with patch.object(m, "_load_player_advisor", side_effect=Exception("crash")):
            result = m._enforce_pronouns_and_names("some text", set())
        assert result == "some text"

    def test_empty_pronouns_dict_leaves_allowed_names_alone(self):
        m = _make_mynx()
        m.pronouns = {}

        result = m._enforce_pronouns_and_names("Whisper watches Jean.", {"Jean"})

        assert result == "Whisper watches Jean."

    def test_empty_pronouns_dict_still_defaults_the_mynx_to_it(self):
        """With ``pronouns`` empty, ``pron_mynx`` must default to "it" — that
        default is the only thing standing between a config gap and the
        sanitiser emitting the literal word ``None``."""
        m = _make_mynx()
        m.pronouns = {}

        result = m._enforce_pronouns_and_names("Fluffy watches Jean.", {"Jean"})

        assert result == "it watches Jean."


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
        # Silent recovery: an unusable room contributes nothing to the prompt
        # rather than propagating and killing the chat turn.
        env_str, leftover = m._gather_environment_lists()
        assert env_str == ""
        assert leftover == set()


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

    def test_no_pronouns_uses_the_it_its_default(self):
        m = _make_mynx()
        m.pronouns = {}

        assert m._build_pronoun_guidance("", "") == (
            "For the mynx use: it/its. For any other nearby NPCs, prefer using "
            "their NAME; if a pronoun is needed, use they/them/their."
        )

    def test_exception_returns_the_static_fallback_guidance(self):
        """A non-string ``jean_pronoun_line`` raises on ``.strip()``. The
        fallback must still be usable prompt text — the old assertion
        (``isinstance(result, str)``) would have passed on ``""``, which would
        have silently stripped all pronoun guidance from the prompt."""
        m = _make_mynx()

        assert m._build_pronoun_guidance(object(), "") == (
            "Use Jean and Mynx pronouns consistently; prefer names for others "
            "or they/them."
        )


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

    def test_without_room_the_context_carries_no_location_clause(self):
        m = _make_mynx()
        m.current_room = None

        result = m._build_llm_context({"Jean"}, "play", "", "")

        assert "You are in" not in result
        assert "Player action/intent: 'play'." in result
        # The bare "." room placeholder must not leave a double space seam.
        assert "  " not in result

    def test_debug_mode_narrates_the_assembled_context(self):
        """The whole value of MYNX_LLM_DEBUG is seeing the prompt that was
        actually built. Assert the narration fires and echoes the context,
        not merely that a string came back."""
        from src.narration import capture_narration

        m = _make_mynx()
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            with capture_narration() as messages:
                result = m._build_llm_context({"Jean"}, "pet", "", "")

        assert len(messages) == 1
        assert messages[0]["text"] == (
            f"[MYNX_LLM_DEBUG] Built context ({len(result)} chars): {result[:4000]}"
        )

    def test_debug_off_narrates_nothing(self):
        from src.narration import capture_narration

        m = _make_mynx()
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "0"}):
            with capture_narration() as messages:
                m._build_llm_context({"Jean"}, "pet", "", "")

        assert messages == []

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

    # ── Prompt → canned-reaction routing ──────────────────────────────────
    #
    # Eighteen near-identical tests here previously asserted only
    # ``isinstance(result, str)`` / ``isinstance(result, dict)``. Every one of
    # them would have passed against ``def interact_with_player(...): return
    # ""`` — none pinned which reaction the prompt actually routes to, that the
    # plain and structured return paths agree, that the mynx's name is
    # interpolated, or that anything was narrated to the player.
    #
    # The parametrised cases below pin the routing table itself; the
    # invariants that hold for *every* prompt are asserted once, in
    # ``_assert_fallback_invariants``.

    ROUTES = [
        ("pet", "groom", "Jean reaches out to pet the mynx."),
        ("stroke", "groom", "Jean reaches out to pet the mynx."),
        ("scritch", "groom", "Jean reaches out to pet the mynx."),
        ("PET", "groom", "Jean reaches out to pet the mynx."),
        ("  pet  ", "groom", "Jean reaches out to pet the mynx."),
        ("feed", "take_food", "Jean offers a morsel of food to the mynx."),
        ("offer food", "take_food", "Jean offers a morsel of food to the mynx."),
        ("give food", "take_food", "Jean offers a morsel of food to the mynx."),
        ("play", "play", "Jean tries to play with the mynx."),
        ("toy", "play", "Jean tries to play with the mynx."),
        ("tease", "play", "Jean tries to play with the mynx."),
        ("wave", "investigate", "Jean wave."),
        ("", "investigate", "Jean interacts with the mynx."),
        (None, "investigate", "Jean interacts with the mynx."),
    ]

    def _assert_fallback_invariants(self, text, expected_action, expected_action_line,
                                    messages, prompt):
        """Invariants every deterministic fallback reaction must satisfy."""
        stored = self.m._llm_last_response
        # 1. The prompt routed to the right canned reaction bucket.
        assert stored["action"] == expected_action
        # 2. Plain and structured paths return the *same* description — the
        #    chat panel and the animation layer must not disagree.
        assert text == stored["description"]
        # 3. The mynx refers to itself by name, not a hardcoded "the mynx".
        assert text.startswith("Whisper ")
        # 4. Structured payload is complete: the API serializer reads all five.
        assert set(stored) == {
            "action", "intensity", "description", "duration_seconds", "audible"
        }
        assert isinstance(stored["duration_seconds"], int)
        assert stored["intensity"] in ("gentle", "low", "medium", "high")
        # 5. Both halves of the exchange reached the player: Jean's action
        #    first, then the mynx's reaction, in that order.
        assert [m["text"] for m in messages] == [expected_action_line, text]
        # 6. History records the *normalised* prompt against the reply, so the
        #    next turn's prompt can reference it.
        assert self.m._llm_history == [
            {"prompt": (prompt or "").strip().lower(), "response": text}
        ]

    @pytest.mark.parametrize("prompt,action,action_line", ROUTES)
    def test_prompt_routes_to_its_canned_reaction(self, prompt, action, action_line):
        from src.narration import capture_narration

        with capture_narration() as messages:
            text = self._call(prompt)

        self._assert_fallback_invariants(text, action, action_line, messages, prompt)

    @pytest.mark.parametrize("prompt,action,action_line", ROUTES)
    def test_structured_mode_returns_the_payload_and_narrates_only_jean(
        self, prompt, action, action_line
    ):
        """``structured=True`` returns the dict *and deliberately does not
        narrate the reaction* — the web client renders it from the payload.
        Only Jean's action line is narrated."""
        from src.narration import capture_narration

        with capture_narration() as messages:
            result = self._call(prompt, structured=True)

        assert result is self.m._llm_last_response
        assert result["action"] == action
        assert [m["text"] for m in messages] == [action_line]

    def test_play_with_an_item_names_the_item_in_jeans_action_line(self):
        """CHARACTERIZATION OF A KNOWN DEFECT — see the report accompanying this
        change. ``interact_with_player`` special-cases ``"play with <item>"``
        when composing *Jean's* action line, but the reaction branch below it
        tests only ``p in ("play", "toy", "tease")``. So playing with a named
        item narrates "Jean plays with the mynx using rope." and then gets the
        generic ``investigate`` idle reaction instead of the ``play`` one.
        """
        from src.narration import capture_narration

        with capture_narration() as messages:
            text = self._call("play with rope")

        assert messages[0]["text"] == "Jean plays with the mynx using rope."
        # Desired: "play". Actual:
        assert self.m._llm_last_response["action"] == "investigate"
        assert messages[1]["text"] == text

    def test_repeated_interactions_accumulate_history_in_order(self):
        self._call("pet")
        self._call("feed")

        assert [h["prompt"] for h in self.m._llm_history] == ["pet", "feed"]
        assert all(h["response"].startswith("Whisper ") for h in self.m._llm_history)

    def test_reactions_vary_across_repeat_prompts(self, seeded):
        """Four variations exist per bucket precisely so repeat PETs do not
        read as a canned response."""
        with seeded(20260821):
            replies = {self._call("pet") for _ in range(40)}

        assert len(replies) == 4

    def test_fallback_delay_defaults_to_one_and_a_half_seconds(self):
        """conftest pins ``MYNX_FALLBACK_DELAY=0`` suite-wide, so the default
        has to be exercised by removing the variable."""
        with patch("time.sleep") as mock_sleep:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("MYNX_FALLBACK_DELAY", None)
                self.m.interact_with_player(player=MagicMock(), prompt="pet")

        mock_sleep.assert_called_once_with(1.5)

    def test_zero_delay_env_skips_the_sleep_entirely(self):
        """``MYNX_FALLBACK_DELAY=0`` is what keeps the API responsive; the old
        test patched nothing and asserted ``isinstance(result, str)``, so it
        would have passed while still sleeping."""
        with patch("time.sleep") as mock_sleep:
            with patch.dict(os.environ, {"MYNX_FALLBACK_DELAY": "0"}):
                self.m.interact_with_player(player=MagicMock(), prompt="pet")

        mock_sleep.assert_not_called()

    def test_invalid_delay_env_uses_default(self):
        with patch("time.sleep") as mock_sleep:
            with patch.dict(os.environ, {"MYNX_FALLBACK_DELAY": "not_a_number"}):
                self.m.interact_with_player(player=MagicMock(), prompt="pet")
        # sleep called with fallback 1.5
        mock_sleep.assert_called_once_with(1.5)

    def test_structured_mode_never_sleeps(self):
        """The delay is a terminal-era pacing beat; the structured path returns
        before it, so an API caller is never held up."""
        with patch("time.sleep") as mock_sleep:
            with patch.dict(os.environ, {"MYNX_FALLBACK_DELAY": "1.5"}):
                self.m.interact_with_player(
                    player=MagicMock(), prompt="pet", structured=True
                )

        mock_sleep.assert_not_called()

    def test_room_roster_includes_present_npcs_and_always_the_mynx(self):
        """The roster is the allow-list of names the LLM may use. It is built
        from ``current_room.npcs_here`` and must always contain the mynx
        itself. The old test built the same room and then asserted only
        ``isinstance(result, str)``, never looking at the roster at all."""
        room = MagicMock()
        guard, kaelen = MagicMock(), MagicMock()
        guard.name = "Guard"
        kaelen.name = "Kaelen"
        room.npcs_here = [guard, kaelen]
        self.m.current_room = room

        captured = {}

        def record(roster_set, *args):
            captured["roster"] = roster_set
            return ""

        with patch.object(self.m, "_build_llm_context", side_effect=record):
            with patch.object(self.m, "_get_llm_adapter", return_value=MagicMock()):
                with patch("time.sleep"):
                    self.m.interact_with_player(player=MagicMock(), prompt="pet")

        assert captured["roster"] == {"Guard", "Kaelen", "Whisper"}

    def test_a_room_whose_npc_list_explodes_does_not_break_the_turn(self):
        """"Prefer silent recovery over crashing the game loop" — a broken room
        must still yield a normal reaction."""
        class _ExplodingRoom:
            @property
            def npcs_here(self):
                raise RuntimeError("room is corrupt")

        self.m.current_room = _ExplodingRoom()

        text = self._call("pet")

        assert self.m._llm_last_response["action"] == "groom"
        assert text.startswith("Whisper ")

    def test_a_narration_failure_does_not_abort_the_reaction(self):
        """``narrate`` for Jean's action line is wrapped in try/except; if the
        sink raises (a UnicodeEncodeError on a Windows console, historically),
        the mynx must still react. The old version patched ``builtins.print``,
        which the narration sink no longer routes through, so it exercised
        nothing."""
        calls = []
        real_narrate = __import__(
            "src.npc._llm", fromlist=["narrate"]
        ).narrate

        def flaky_narrate(*args, **kwargs):
            calls.append(args)
            if len(calls) == 1:
                raise UnicodeEncodeError("utf-8", "", 0, 1, "encode error")
            return real_narrate(*args, **kwargs)

        with patch("src.npc._llm.narrate", side_effect=flaky_narrate):
            with patch("time.sleep"):
                result = self.m.interact_with_player(
                    player=MagicMock(), prompt="pet"
                )

        assert len(calls) == 2
        assert self.m._llm_last_response["action"] == "groom"
        assert result == self.m._llm_last_response["description"]


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
                mod_mock = MagicMock()
                mod_mock.MynxLLMAdapter = MagicMock(
                    return_value=fake_adapter_inst
                )
                with patch(
                    "src.npc._llm._load_llm_client_module", return_value=mod_mock
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
    def test_a_broken_narration_sink_still_yields_the_full_context(self):
        """Debug logging must never cost the caller its prompt. Asserting
        ``isinstance(result, str)`` (the old assertion) would also have passed
        on ``""`` — an empty prompt sent to the LLM."""
        m = _make_mynx()
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "0"}):
            expected = m._build_llm_context(set(), "pet", "", "")

        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            with patch("src.npc._llm.narrate", side_effect=RuntimeError("boom")):
                result = m._build_llm_context(set(), "pet", "", "")

        assert result == expected
        assert "Player action/intent: 'pet'." in result


class TestCheckAndCorrectMynxTextException:
    def test_exception_returns_none(self):
        m = _make_mynx()
        m.pronouns = None  # .get on None inside try raises AttributeError
        result = m._check_and_correct_mynx_text("Some valid text here.", "pet", [])
        assert result is None


class TestInteractWithPlayerRosterException:
    def test_roster_building_exception_still_produces_the_pet_reaction(self):
        m = _make_mynx()

        class _BadRoom:
            @property
            def npcs_here(self):
                raise RuntimeError("boom")

        m.current_room = _BadRoom()
        with patch("time.sleep"):
            result = m.interact_with_player(player=MagicMock(), prompt="pet")

        assert m._llm_last_response["action"] == "groom"
        assert result == m._llm_last_response["description"]
        assert m._llm_history == [{"prompt": "pet", "response": result}]


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

        assert result["description"] == "Whisper tilts its head at Jean."
        assert self.m._llm_last_response is result
        assert self.m._llm_history == [
            {"prompt": "pet", "response": "Whisper tilts its head at Jean."}
        ]

    def test_the_prompt_sent_to_the_adapter_carries_persona_roster_and_action(self):
        """The single most important thing about an LLM call is what was
        actually asked. Nothing in this file previously inspected the assembled
        context at all — every adapter test asserted only the shape of the
        canned reply, which proves that ``MagicMock`` returns what you set."""
        adapter = MagicMock()
        adapter.generate_plain.return_value = "Whisper leans in close to Jean."
        self.m._llm_adapter = adapter

        room = MagicMock()
        room.description = "a dripping mineral pool chamber"
        room.items_here = []
        room.objects_here = []
        guard = MagicMock()
        guard.name = "Guard"
        room.npcs_here = [guard]
        self.m.current_room = room
        self.m._llm_history = [{"prompt": "feed", "response": "Whisper ate."}]

        with patch("time.sleep"):
            self.m.interact_with_player(player=MagicMock(), prompt="pet")

        context = adapter.generate_plain.call_args.kwargs["context"]
        # Persona: who the actor is and that it never targets itself.
        assert "The mynx's proper name is Whisper." in context
        assert "Whisper is the ACTOR, never its own target." in context
        # Roster: the allow-list of names, Jean always included.
        assert "Allowed entity names you may reference (no others): Guard, Jean, Whisper." in context
        # World state: the room the mynx is standing in.
        assert "You are in a dripping mineral pool chamber." in context
        # The player's actual action.
        assert "Player action/intent: 'pet'." in context
        # Conversation history, so the reply can avoid repeating itself.
        assert "feed" in context and "Whisper ate." in context
        assert "be novel relative to the above history" in context

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
        """Named "narrates raw description" but asserted only
        ``isinstance(result, dict)`` — it never checked that anything was
        narrated, let alone the raw text."""
        from src.narration import capture_narration

        adapter = MagicMock()
        adapter.generate_structured.return_value = {
            "description": "Whisper chirps happily."
        }
        self.m._llm_adapter = adapter
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            with patch("time.sleep"):
                with capture_narration() as messages:
                    result = self.m.interact_with_player(
                        player=MagicMock(), prompt="pet", structured=True
                    )

        texts = [m["text"] for m in messages]
        assert "[MYNX_LLM_DEBUG] Built context" in " ".join(texts)
        assert (
            "[MYNX_LLM_DEBUG] Raw structured description: Whisper chirps happily."
            in texts
        )
        assert result["description"] == "Whisper chirps happily."

    def test_plain_text_valid_response_narrated(self):
        from src.narration import capture_narration

        adapter = MagicMock()
        adapter.generate_plain.return_value = "Whisper leans in close to Jean."
        self.m._llm_adapter = adapter
        with patch("time.sleep"):
            with capture_narration() as messages:
                result = self.m.interact_with_player(
                    player=MagicMock(), prompt="pet", structured=False
                )

        assert result == "Whisper leans in close to Jean."
        assert self.m._llm_last_response == {
            "action": "narrate",
            "intensity": "low",
            "description": "Whisper leans in close to Jean.",
            "duration_seconds": 2,
            "audible": "soft chitter",
        }
        assert [m["text"] for m in messages] == [
            "Jean reaches out to pet the mynx.",
            "Whisper leans in close to Jean.",
        ]
        assert self.m._llm_history == [
            {"prompt": "pet", "response": "Whisper leans in close to Jean."}
        ]

    def test_the_adapter_never_sees_a_structured_call_in_plain_mode(self):
        adapter = MagicMock()
        adapter.generate_plain.return_value = "Whisper leans in close to Jean."
        self.m._llm_adapter = adapter
        with patch("time.sleep"):
            self.m.interact_with_player(player=MagicMock(), prompt="pet")

        adapter.generate_structured.assert_not_called()
        assert adapter.generate_plain.call_count == 1

    def test_plain_text_with_debug_narrates_raw(self):
        from src.narration import capture_narration

        adapter = MagicMock()
        adapter.generate_plain.return_value = "Whisper chitters."
        self.m._llm_adapter = adapter
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            with patch("time.sleep"):
                with capture_narration() as messages:
                    result = self.m.interact_with_player(
                        player=MagicMock(), prompt="pet", structured=False
                    )

        texts = [m["text"] for m in messages]
        assert "[MYNX_LLM_DEBUG] Raw plain text: Whisper chitters." in texts
        assert result == "Whisper chitters."

    # ── Provider-failure fallbacks ────────────────────────────────────────
    #
    # Each of these previously asserted only ``isinstance(result, str)``, which
    # cannot distinguish "the fallback fired correctly" from "the broken LLM
    # text was passed through to the player". The shared helper asserts the
    # deterministic ``groom`` reaction actually took over, that the bad LLM
    # text is nowhere in the output, and that the player still got both halves
    # of the exchange.

    def _assert_fell_back_to_the_canned_pet_reaction(self, result, messages, bad_text=None):
        assert self.m._llm_last_response["action"] == "groom"
        assert result == self.m._llm_last_response["description"]
        assert result.startswith("Whisper ")
        if bad_text is not None:
            assert bad_text not in result
        narrated = [m["text"] for m in messages]
        assert narrated[0] == "Jean reaches out to pet the mynx."
        assert result in narrated
        assert self.m._llm_history == [{"prompt": "pet", "response": result}]

    @pytest.mark.parametrize(
        "returned,bad_text",
        [
            (None, None),
            (123, None),
            ("", None),
            ("zq.", "zq"),                     # under the 5-char floor
            ("A" * 250 + ".", "A" * 250),      # over the 200-char ceiling
            ('"Hello there," Whisper says.', "Hello there"),  # quoted speech
        ],
        ids=["none", "non_string", "empty", "too_short", "too_long", "quoted_speech"],
    )
    def test_malformed_provider_content_falls_back_without_reaching_the_player(
        self, returned, bad_text
    ):
        from src.narration import capture_narration

        adapter = MagicMock()
        adapter.generate_plain.return_value = returned
        self.m._llm_adapter = adapter
        with patch("time.sleep"):
            with capture_narration() as messages:
                result = self.m.interact_with_player(
                    player=MagicMock(), prompt="pet", structured=False
                )

        self._assert_fell_back_to_the_canned_pet_reaction(result, messages, bad_text)

    @pytest.mark.parametrize(
        "error",
        [
            RuntimeError("network down"),
            TimeoutError("provider timed out"),
            ValueError("malformed json"),
            KeyboardInterrupt,
        ],
        ids=["runtime", "timeout", "value", "keyboard_interrupt"],
    )
    def test_a_provider_that_raises_cannot_crash_the_game_loop(self, error):
        """"Prefer silent recovery over crashing the game loop" — whatever the
        provider throws, the player still gets a reaction.

        ``KeyboardInterrupt`` is included deliberately: it does **not** inherit
        from ``Exception``, so ``except Exception`` does not catch it. This
        case pins that the interrupt propagates rather than being swallowed —
        the one failure mode that must NOT be silent.
        """
        from src.narration import capture_narration

        adapter = MagicMock()
        adapter.generate_plain.side_effect = error
        self.m._llm_adapter = adapter

        if error is KeyboardInterrupt:
            with pytest.raises(KeyboardInterrupt):
                with patch("time.sleep"):
                    self.m.interact_with_player(player=MagicMock(), prompt="pet")
            return

        with patch("time.sleep"):
            with capture_narration() as messages:
                result = self.m.interact_with_player(
                    player=MagicMock(), prompt="pet", structured=False
                )

        self._assert_fell_back_to_the_canned_pet_reaction(result, messages)

    def test_generation_exception_with_debug_narrates_the_reason(self):
        from src.narration import capture_narration

        adapter = MagicMock()
        adapter.generate_plain.side_effect = RuntimeError("network down")
        self.m._llm_adapter = adapter
        with patch.dict(os.environ, {"MYNX_LLM_DEBUG": "1"}):
            with patch("time.sleep"):
                with capture_narration() as messages:
                    result = self.m.interact_with_player(
                        player=MagicMock(), prompt="pet", structured=False
                    )

        assert (
            "[MYNX_LLM_DEBUG] Generation/validation error, falling back: network down"
            in [m["text"] for m in messages]
        )
        self._assert_fell_back_to_the_canned_pet_reaction(result, messages)


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

        # The debug narration blew up; the LLM's answer still reached the caller.
        assert result["description"] == "Whisper chirps happily."
        assert self.m._llm_last_response is result

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

        # History bookkeeping failed; the reaction is unaffected and the
        # history stays empty rather than half-written.
        assert result["description"] == "Whisper chirps happily."
        assert self.m._llm_history == []

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

        assert result == "Whisper chitters."

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

        assert result == "Whisper chitters happily today."
        assert self.m._llm_last_response["action"] == "narrate"
        assert self.m._llm_history == []


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

        assert m._llm_last_response["action"] == "groom"
        assert result == m._llm_last_response["description"]
        assert m._llm_history == []


class TestInteractWithPlayerSleepException:
    def test_sleep_exception_is_swallowed(self):
        """A pacing delay that raises must not cost the player the reaction,
        and must not truncate the return value."""
        m = _make_mynx()
        m._llm_adapter = None
        with patch("src.npc._llm.time.sleep", side_effect=RuntimeError("boom")) as sleeper:
            with patch.dict(os.environ, {"MYNX_FALLBACK_DELAY": "1.5"}):
                result = m.interact_with_player(player=MagicMock(), prompt="pet")

        sleeper.assert_called_once_with(1.5)
        assert result == m._llm_last_response["description"]
        assert m._llm_last_response["action"] == "groom"
