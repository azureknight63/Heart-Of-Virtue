"""Coverage-focused tests for ai/llm_client.py.

Covers provider selection/validation, model discovery + ranking + disk cache,
retry/fallback logic, request/response parsing (ollama + openrouter, SDK + HTTP),
failure-tracking, and the Mynx/NpcChat adapters built on GenericLLMClient.

All network access is mocked: `requests.get`/`requests.post` are patched per-test,
`openai.OpenAI` is monkeypatched away from the local stub when SDK-path coverage is
needed, and `threading.Thread` is patched where the production code would otherwise
spawn a real (infinite-loop) background thread.
"""
import json
import os
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

import ai.llm_client as llm_client
from ai.llm_client import (
    GenericLLMClient,
    MynxLLMAdapter,
    NpcChatLLMAdapter,
    _JSONTools,
)


@pytest.fixture(autouse=True)
def _reset_llm_class_state(tmp_path, monkeypatch):
    """Isolate class-level shared state and disk cache per test."""
    GenericLLMClient.reset_class_state()
    GenericLLMClient._nightly_refresh_started = False
    monkeypatch.setattr(llm_client, "_MODEL_CACHE_FILE", str(tmp_path / ".model_cache.json"))
    # Ensure a clean baseline; individual tests override as needed.
    monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
    monkeypatch.setenv("MYNX_LLM_PROVIDER", "none")
    monkeypatch.delenv("MYNX_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("NPC_CHAT_LLM_ENABLED", raising=False)
    monkeypatch.delenv("NPC_CHAT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("NPC_CHAT_LLM_MODEL", raising=False)
    yield
    GenericLLMClient.reset_class_state()
    GenericLLMClient._nightly_refresh_started = False


# ---------------------------------------------------------------------------
# _JSONTools
# ---------------------------------------------------------------------------


class TestJSONToolsTryParseJson:
    def test_direct_parse(self):
        assert _JSONTools.try_parse_json('{"a": 1}') == {"a": 1}

    def test_code_fence_stripped(self):
        raw = "```json\n{\"a\": 1}\n```"
        assert _JSONTools.try_parse_json(raw) == {"a": 1}

    def test_heuristic_extraction_from_surrounding_text(self):
        raw = 'Sure thing! {"a": 1, "b": 2} Hope that helps.'
        assert _JSONTools.try_parse_json(raw) == {"a": 1, "b": 2}

    def test_heuristic_extraction_invalid_fragment_returns_none(self):
        raw = 'prefix { not json at all } suffix'
        assert _JSONTools.try_parse_json(raw) is None

    def test_no_braces_returns_none(self):
        assert _JSONTools.try_parse_json("just plain text") is None

    def test_empty_string_returns_none(self):
        assert _JSONTools.try_parse_json("") is None


class TestJSONToolsSanitizeText:
    def test_strips_double_quotes(self):
        assert _JSONTools.sanitize_text('"hello there"') == "hello there"

    def test_strips_single_quotes(self):
        assert _JSONTools.sanitize_text("'hello there'") == "hello there"

    def test_collapses_whitespace(self):
        assert _JSONTools.sanitize_text("hello   \n  there") == "hello there"

    def test_truncates_to_500_chars(self):
        text = "a" * 600
        result = _JSONTools.sanitize_text(text)
        assert len(result) == 500

    def test_no_quotes_left_untouched_content(self):
        assert _JSONTools.sanitize_text("no quotes here") == "no quotes here"


class TestJSONToolsExtractTextContent:
    def test_dict_block_content_fallback_key(self):
        blocks = [{"type": "text", "content": "fallback content"}]
        assert _JSONTools.extract_text_content(blocks) == "fallback content"

    def test_dict_without_text_or_content_skipped(self):
        blocks = [{"type": "text"}]
        assert _JSONTools.extract_text_content(blocks) is None

    def test_content_falsy_returns_none(self):
        assert _JSONTools.extract_text_content(0) is None

    def test_bare_string_elements_in_list(self):
        assert _JSONTools.extract_text_content(["hello", "world"]) == "hello\nworld"

    def test_mixed_dict_and_bare_string_elements(self):
        blocks = [{"type": "text", "text": "structured"}, "plain string"]
        assert _JSONTools.extract_text_content(blocks) == "structured\nplain string"


# ---------------------------------------------------------------------------
# GenericLLMClient — construction / provider selection
# ---------------------------------------------------------------------------


class TestInit:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        assert client.enabled is False

    def test_enabled_true_variants(self, monkeypatch):
        for val in ("1", "true", "True"):
            monkeypatch.setenv("MYNX_LLM_ENABLED", val)
            monkeypatch.setenv("MYNX_LLM_PROVIDER", "none")
            client = GenericLLMClient()
            assert client.enabled is True

    def test_default_provider_is_ollama(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        monkeypatch.delenv("MYNX_LLM_PROVIDER", raising=False)
        client = GenericLLMClient()
        assert client.provider == "ollama"

    def test_default_model_is_auto(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        assert client.model == "auto"

    def test_enabled_ollama_triggers_discovery(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        with patch.object(GenericLLMClient, "_discover_ollama_model") as mock_discover:
            GenericLLMClient()
            mock_discover.assert_called_once()

    def test_enabled_ollama_with_explicit_model_skips_discovery(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "custom-model")
        with patch.object(GenericLLMClient, "_discover_ollama_model") as mock_discover:
            client = GenericLLMClient()
            mock_discover.assert_not_called()
            assert client.model == "custom-model"

    def test_enabled_openrouter_triggers_discovery_and_validation(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")
        with patch.object(GenericLLMClient, "_discover_openrouter_model") as mock_discover, \
             patch.object(GenericLLMClient, "_validate_and_fallback_openrouter") as mock_validate:
            GenericLLMClient()
            mock_discover.assert_called_once()
            mock_validate.assert_called_once()

    def test_enabled_openrouter_skips_discovery_when_already_done(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")
        GenericLLMClient._discovery_done = True
        with patch.object(GenericLLMClient, "_discover_openrouter_model") as mock_discover, \
             patch.object(GenericLLMClient, "_validate_and_fallback_openrouter"):
            GenericLLMClient()
            mock_discover.assert_not_called()


# ---------------------------------------------------------------------------
# _discover_ollama_model
# ---------------------------------------------------------------------------


class TestDiscoverOllamaModel:
    def _make_client(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        return GenericLLMClient()

    def test_no_change_when_model_already_present(self, monkeypatch):
        client = self._make_client(monkeypatch)
        client.model = "llama3.1:7b"
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"models": [{"name": "llama3.1:7b"}]}
        with patch("requests.get", return_value=resp):
            client._discover_ollama_model()
        assert client.model == "llama3.1:7b"

    def test_prefers_gemma_over_others(self, monkeypatch):
        client = self._make_client(monkeypatch)
        client.model = "missing-model"
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"models": [{"name": "phi-2"}, {"name": "gemma-7b"}, {"name": "llama-3"}]}
        with patch("requests.get", return_value=resp):
            client._discover_ollama_model()
        assert client.model == "gemma-7b"

    def test_falls_back_to_first_model_when_no_preference_matches(self, monkeypatch):
        client = self._make_client(monkeypatch)
        client.model = "missing-model"
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"models": [{"name": "totally-custom"}]}
        with patch("requests.get", return_value=resp):
            client._discover_ollama_model()
        assert client.model == "totally-custom"

    def test_non_200_status_leaves_model_unchanged(self, monkeypatch):
        client = self._make_client(monkeypatch)
        client.model = "missing-model"
        resp = MagicMock(status_code=500)
        with patch("requests.get", return_value=resp):
            client._discover_ollama_model()
        assert client.model == "missing-model"

    def test_request_exception_swallowed(self, monkeypatch):
        client = self._make_client(monkeypatch)
        client.model = "missing-model"
        with patch("requests.get", side_effect=Exception("network down")):
            client._discover_ollama_model()
        assert client.model == "missing-model"


# ---------------------------------------------------------------------------
# Disk cache helpers
# ---------------------------------------------------------------------------


class TestDiskCache:
    def test_write_then_read_round_trip(self):
        GenericLLMClient._write_disk_cache(["model/a", "model/b"])
        result = GenericLLMClient._read_disk_cache()
        assert result == ["model/a", "model/b"]

    def test_read_missing_file_returns_none(self):
        assert GenericLLMClient._read_disk_cache() is None

    def test_read_expired_cache_returns_none(self):
        payload = {
            "fetched_at": (datetime.now() - timedelta(days=2)).timestamp(),
            "models": ["model/a"],
        }
        with open(llm_client._MODEL_CACHE_FILE, "w") as f:
            json.dump(payload, f)
        assert GenericLLMClient._read_disk_cache() is None

    def test_read_non_list_models_returns_none(self):
        payload = {"fetched_at": datetime.now().timestamp(), "models": "not-a-list"}
        with open(llm_client._MODEL_CACHE_FILE, "w") as f:
            json.dump(payload, f)
        assert GenericLLMClient._read_disk_cache() is None

    def test_read_empty_models_returns_none(self):
        payload = {"fetched_at": datetime.now().timestamp(), "models": []}
        with open(llm_client._MODEL_CACHE_FILE, "w") as f:
            json.dump(payload, f)
        assert GenericLLMClient._read_disk_cache() is None

    def test_read_non_string_model_entries_returns_none(self):
        payload = {"fetched_at": datetime.now().timestamp(), "models": ["ok", 123]}
        with open(llm_client._MODEL_CACHE_FILE, "w") as f:
            json.dump(payload, f)
        assert GenericLLMClient._read_disk_cache() is None

    def test_read_corrupt_json_returns_none(self):
        with open(llm_client._MODEL_CACHE_FILE, "w") as f:
            f.write("not valid json {{{")
        assert GenericLLMClient._read_disk_cache() is None

    def test_write_failure_logged_not_raised(self, monkeypatch):
        with patch("builtins.open", side_effect=OSError("disk full")):
            # Should not raise.
            GenericLLMClient._write_disk_cache(["x"])


# ---------------------------------------------------------------------------
# Model ranking
# ---------------------------------------------------------------------------


class TestIsFreeTextModel:
    def test_free_text_model_true(self):
        m = {"pricing": {"prompt": "0", "completion": "0"}, "architecture": {"output_modalities": ["text"]}}
        assert GenericLLMClient._is_free_text_model(m) is True

    def test_non_zero_prompt_price_false(self):
        m = {"pricing": {"prompt": "0.01", "completion": "0"}}
        assert GenericLLMClient._is_free_text_model(m) is False

    def test_non_zero_completion_price_false(self):
        m = {"pricing": {"prompt": "0", "completion": "0.02"}}
        assert GenericLLMClient._is_free_text_model(m) is False

    def test_non_text_output_modality_false(self):
        m = {"pricing": {"prompt": "0", "completion": "0"}, "architecture": {"output_modalities": ["image"]}}
        assert GenericLLMClient._is_free_text_model(m) is False

    def test_invalid_pricing_value_false(self):
        m = {"pricing": {"prompt": "not-a-number", "completion": "0"}}
        assert GenericLLMClient._is_free_text_model(m) is False

    def test_missing_pricing_defaults_to_non_free(self):
        assert GenericLLMClient._is_free_text_model({}) is False


class TestRankModels:
    def test_priority_models_ranked_first(self):
        models = [
            {"id": "b/model", "pricing": {"prompt": "0", "completion": "0"}, "created": 100},
            {"id": "a/priority", "pricing": {"prompt": "0", "completion": "0"}, "created": 50},
        ]
        ranked = GenericLLMClient._rank_models(models, priority_ids={"a/priority"})
        assert ranked[0] == "a/priority"

    def test_newest_first_when_no_priority(self):
        models = [
            {"id": "old", "pricing": {"prompt": "0", "completion": "0"}, "created": 10},
            {"id": "new", "pricing": {"prompt": "0", "completion": "0"}, "created": 100},
        ]
        ranked = GenericLLMClient._rank_models(models, priority_ids=set())
        assert ranked == ["new", "old"]

    def test_smallest_context_length_tiebreak(self):
        models = [
            {"id": "big", "pricing": {"prompt": "0", "completion": "0"}, "created": 1, "context_length": 100000},
            {"id": "small", "pricing": {"prompt": "0", "completion": "0"}, "created": 1, "context_length": 4096},
        ]
        ranked = GenericLLMClient._rank_models(models, priority_ids=set())
        assert ranked == ["small", "big"]

    def test_dedup_by_id(self):
        models = [
            {"id": "dup", "pricing": {"prompt": "0", "completion": "0"}, "created": 1},
            {"id": "dup", "pricing": {"prompt": "0", "completion": "0"}, "created": 2},
        ]
        ranked = GenericLLMClient._rank_models(models, priority_ids=set())
        assert ranked == ["dup"]

    def test_non_free_models_excluded(self):
        models = [
            {"id": "paid", "pricing": {"prompt": "0.5", "completion": "0"}, "created": 1},
        ]
        assert GenericLLMClient._rank_models(models, priority_ids=set()) == []

    def test_missing_id_skipped(self):
        models = [{"pricing": {"prompt": "0", "completion": "0"}}]
        assert GenericLLMClient._rank_models(models, priority_ids=set()) == []


class TestFetchAndRankModels:
    def test_success_merges_priority_and_all(self, monkeypatch):
        priority_resp = MagicMock()
        priority_resp.json.return_value = {"data": [{"id": "priority/one", "pricing": {"prompt": "0", "completion": "0"}, "created": 5}]}
        priority_resp.raise_for_status = MagicMock()
        all_resp = MagicMock()
        all_resp.json.return_value = {"data": [
            {"id": "priority/one", "pricing": {"prompt": "0", "completion": "0"}, "created": 5},
            {"id": "other/two", "pricing": {"prompt": "0", "completion": "0"}, "created": 1},
        ]}
        all_resp.raise_for_status = MagicMock()

        def fake_get(url, headers=None, timeout=None):
            if "category=" in url:
                return priority_resp
            return all_resp

        with patch("requests.get", side_effect=fake_get):
            ranked = GenericLLMClient._fetch_and_rank_models("fake-key")
        assert ranked[0] == "priority/one"
        assert "other/two" in ranked

        # Verify the disk cache got written as a side effect.
        cached = GenericLLMClient._read_disk_cache()
        assert cached == ranked

    def test_all_models_fetch_failure_raises(self, monkeypatch):
        def fake_get(url, headers=None, timeout=None):
            raise Exception("network unreachable")

        with patch("requests.get", side_effect=fake_get):
            with pytest.raises(RuntimeError, match="Failed to fetch OpenRouter models"):
                GenericLLMClient._fetch_and_rank_models("fake-key")

    def test_no_eligible_models_raises(self, monkeypatch):
        resp = MagicMock()
        resp.json.return_value = {"data": [{"id": "paid/one", "pricing": {"prompt": "1", "completion": "1"}}]}
        resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=resp):
            with pytest.raises(RuntimeError, match="No suitable free text-only models"):
                GenericLLMClient._fetch_and_rank_models("fake-key")

    def test_priority_fetch_failure_still_succeeds_via_all(self):
        call_count = {"n": 0}

        def fake_get(url, headers=None, timeout=None):
            if "category=" in url:
                raise Exception("category endpoint down")
            resp = MagicMock()
            resp.json.return_value = {"data": [{"id": "ok/model", "pricing": {"prompt": "0", "completion": "0"}, "created": 1}]}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("requests.get", side_effect=fake_get):
            ranked = GenericLLMClient._fetch_and_rank_models("fake-key")
        assert ranked == ["ok/model"]


# ---------------------------------------------------------------------------
# _discover_openrouter_model / _select_model_from_cache / nightly refresh
# ---------------------------------------------------------------------------


class TestDiscoverOpenrouterModel:
    def test_no_api_key_marks_done_and_returns(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client._openrouter_api_key = ""
        client._discover_openrouter_model()
        assert GenericLLMClient._discovery_done is True

    def test_in_flight_lock_waits_and_returns(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client._openrouter_api_key = "key"
        GenericLLMClient._discovery_event.clear()
        try:
            client._discover_openrouter_model()
        finally:
            GenericLLMClient._discovery_event.set()

    def test_uses_in_memory_cache_first(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client._openrouter_api_key = "key"
        GenericLLMClient._free_models_cache = ["mem/model"]
        client._discover_openrouter_model()
        assert client.model == "mem/model"

    def test_uses_disk_cache_second(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client._openrouter_api_key = "key"
        GenericLLMClient._write_disk_cache(["disk/model"])
        client._discover_openrouter_model()
        assert client.model == "disk/model"
        assert GenericLLMClient._discovery_done is True

    def test_fetches_network_when_no_cache(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client._openrouter_api_key = "key"
        with patch.object(GenericLLMClient, "_fetch_and_rank_models", return_value=["net/model"]), \
             patch.object(GenericLLMClient, "_start_nightly_refresh") as mock_refresh:
            client._discover_openrouter_model()
        assert client.model == "net/model"
        assert GenericLLMClient._discovery_done is True
        mock_refresh.assert_called_once()

    def test_network_failure_marks_done_and_swallows(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client._openrouter_api_key = "key"
        with patch.object(GenericLLMClient, "_fetch_and_rank_models", side_effect=RuntimeError("boom")):
            client._discover_openrouter_model()
        assert GenericLLMClient._discovery_done is True
        # Event released even on failure.
        assert GenericLLMClient._discovery_event.is_set()


class TestSelectModelFromCache:
    def test_respects_explicit_model(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client.model = "explicit/model"
        client._select_model_from_cache(["a", "b"])
        assert client.model == "explicit/model"

    def test_auto_selects_first_of_list(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client.model = "auto"
        client._select_model_from_cache(["first", "second"])
        assert client.model == "first"

    def test_empty_list_falls_back_to_stable(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client.model = "free"
        client._select_model_from_cache([])
        assert client.model == GenericLLMClient.STABLE_FREE_FALLBACKS[0]


class TestNightlyRefresh:
    def test_idempotent_second_call_noop(self):
        GenericLLMClient._nightly_refresh_started = True
        with patch("threading.Thread") as mock_thread:
            GenericLLMClient._start_nightly_refresh()
            mock_thread.assert_not_called()

    def test_starts_daemon_thread(self):
        with patch("threading.Thread") as mock_thread:
            instance = MagicMock()
            mock_thread.return_value = instance
            GenericLLMClient._start_nightly_refresh()
            mock_thread.assert_called_once()
            assert mock_thread.call_args.kwargs.get("daemon") is True
            instance.start.assert_called_once()

    def test_refresh_loop_body_executes_once(self, monkeypatch):
        """Directly exercise the inner _refresh_loop function body for coverage."""
        captured = {}

        class ImmediateThread:
            def __init__(self, target=None, daemon=None, name=None):
                captured["target"] = target

            def start(self):
                pass

        monkeypatch.setattr(threading, "Thread", ImmediateThread)
        monkeypatch.setenv("OPENROUTER_API_KEY", "key123")

        # Patch time.sleep so the while-True loop body runs once then raises
        # StopIteration to break out (caught nowhere -> propagates, but the
        # refresh loop's try/except only wraps the fetch, so let the fetch
        # raise instead to naturally exit after one iteration).
        call_count = {"n": 0}

        def fake_sleep(seconds):
            call_count["n"] += 1
            if call_count["n"] > 1:
                raise KeyboardInterrupt("stop loop")

        with patch.object(GenericLLMClient, "_fetch_and_rank_models", return_value=["refreshed/model"]):
            monkeypatch.setattr(time, "sleep", fake_sleep)
            GenericLLMClient._start_nightly_refresh()
            target = captured["target"]
            with pytest.raises(KeyboardInterrupt):
                target()
        assert GenericLLMClient._free_models_cache == ["refreshed/model"]

    def test_refresh_loop_no_api_key_continues(self, monkeypatch):
        captured = {}

        class ImmediateThread:
            def __init__(self, target=None, daemon=None, name=None):
                captured["target"] = target

            def start(self):
                pass

        monkeypatch.setattr(threading, "Thread", ImmediateThread)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        call_count = {"n": 0}

        def fake_sleep(seconds):
            call_count["n"] += 1
            if call_count["n"] > 1:
                raise KeyboardInterrupt("stop loop")

        monkeypatch.setattr(time, "sleep", fake_sleep)
        GenericLLMClient._start_nightly_refresh()
        target = captured["target"]
        with pytest.raises(KeyboardInterrupt):
            target()

    def test_refresh_loop_fetch_failure_logged(self, monkeypatch):
        captured = {}

        class ImmediateThread:
            def __init__(self, target=None, daemon=None, name=None):
                captured["target"] = target

            def start(self):
                pass

        monkeypatch.setattr(threading, "Thread", ImmediateThread)
        monkeypatch.setenv("OPENROUTER_API_KEY", "key123")

        call_count = {"n": 0}

        def fake_sleep(seconds):
            call_count["n"] += 1
            if call_count["n"] > 1:
                raise KeyboardInterrupt("stop loop")

        monkeypatch.setattr(time, "sleep", fake_sleep)
        with patch.object(GenericLLMClient, "_fetch_and_rank_models", side_effect=RuntimeError("fail")):
            GenericLLMClient._start_nightly_refresh()
            target = captured["target"]
            with pytest.raises(KeyboardInterrupt):
                target()


# ---------------------------------------------------------------------------
# _validate_and_fallback_openrouter
# ---------------------------------------------------------------------------


class TestValidateAndFallbackOpenrouter:
    def _client(self, monkeypatch, api_key="key123"):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", api_key)
        with patch.object(GenericLLMClient, "_discover_openrouter_model"), \
             patch.object(GenericLLMClient, "_validate_and_fallback_openrouter"):
            client = GenericLLMClient()
        return client

    def test_disabled_returns_immediately(self, monkeypatch):
        client = self._client(monkeypatch)
        client.enabled = False
        client._validate_and_fallback_openrouter()
        assert client._available is None

    def test_missing_api_key_returns_immediately(self, monkeypatch):
        client = self._client(monkeypatch)
        client._openrouter_api_key = ""
        client._validate_and_fallback_openrouter()
        assert client._available is None

    def test_primary_model_verified(self, monkeypatch):
        client = self._client(monkeypatch)
        client.model = "primary/model"
        with patch.object(client, "_openrouter_chat_single", return_value="OK"):
            client._validate_and_fallback_openrouter()
        assert client._available is True
        assert client.model == "primary/model"

    def test_primary_fails_finds_dynamic_cache_fallback(self, monkeypatch):
        client = self._client(monkeypatch)
        client.model = "primary/model"
        GenericLLMClient._free_models_cache = ["dynamic/fallback"]

        def fake_chat(model_id, *args, **kwargs):
            if model_id == "dynamic/fallback":
                return "OK response"
            return None

        with patch.object(client, "_openrouter_chat_single", side_effect=fake_chat):
            client._validate_and_fallback_openrouter()
        assert client._available is True
        assert client.model == "dynamic/fallback"

    def test_primary_fails_finds_stable_fallback(self, monkeypatch):
        client = self._client(monkeypatch)
        client.model = "primary/model"

        def fake_chat(model_id, *args, **kwargs):
            if model_id == GenericLLMClient.STABLE_FREE_FALLBACKS[0]:
                return "OK"
            return None

        with patch.object(client, "_openrouter_chat_single", side_effect=fake_chat):
            client._validate_and_fallback_openrouter()
        assert client._available is True
        assert client.model == GenericLLMClient.STABLE_FREE_FALLBACKS[0]

    def test_all_models_fail_disables_client(self, monkeypatch):
        client = self._client(monkeypatch)
        client.model = "primary/model"
        with patch.object(client, "_openrouter_chat_single", return_value=None):
            client._validate_and_fallback_openrouter()
        assert client._available is False
        assert client.enabled is False

    def test_test_one_exception_treated_as_failure(self, monkeypatch):
        client = self._client(monkeypatch)
        client.model = "primary/model"
        with patch.object(client, "_openrouter_chat_single", side_effect=Exception("boom")):
            client._validate_and_fallback_openrouter()
        assert client._available is False

    def test_primary_already_marked_failed_skips_test_one_call(self, monkeypatch):
        """If the primary model is already in the failure-penalty window (e.g. a
        prior validation run marked it), `test_one` short-circuits via
        `_is_model_failed` without invoking `_openrouter_chat_single`."""
        client = self._client(monkeypatch)
        client.model = "primary/model"
        client._mark_model_failed("primary/model", duration_minutes=30)
        with patch.object(client, "_openrouter_chat_single", return_value="OK") as mock_single:
            client._validate_and_fallback_openrouter()
        # Primary was pre-failed, so test_one(primary) returns False without calling
        # _openrouter_chat_single for it; fallback search proceeds instead.
        called_models = [call.args[0] for call in mock_single.call_args_list]
        assert "primary/model" not in called_models

    def test_already_failed_candidate_skipped(self, monkeypatch):
        client = self._client(monkeypatch)
        client.model = "primary/model"
        client._mark_model_failed(GenericLLMClient.STABLE_FREE_FALLBACKS[0], duration_minutes=30)

        calls = []

        def fake_chat(model_id, *args, **kwargs):
            calls.append(model_id)
            return None

        with patch.object(client, "_openrouter_chat_single", side_effect=fake_chat):
            client._validate_and_fallback_openrouter()
        assert GenericLLMClient.STABLE_FREE_FALLBACKS[0] not in calls


# ---------------------------------------------------------------------------
# available() / debug_status()
# ---------------------------------------------------------------------------


class TestAvailable:
    def test_disabled_returns_false_with_reason(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        assert client.available() is False
        assert "disabled" in client._unavailable_reason.lower()

    def test_cached_available_value_short_circuits(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "none")
        client = GenericLLMClient()
        client._available = True
        assert client.available() is True

    def test_ollama_reachable_true(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "some-model")
        client = GenericLLMClient()
        resp = MagicMock(status_code=200)
        with patch("requests.get", return_value=resp):
            assert client.available() is True

    def test_ollama_bad_status_false(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "some-model")
        client = GenericLLMClient()
        resp = MagicMock(status_code=503)
        with patch("requests.get", return_value=resp):
            assert client.available() is False
        assert "status 503" in client._unavailable_reason

    def test_ollama_connection_exception_false(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "some-model")
        client = GenericLLMClient()
        with patch("requests.get", side_effect=Exception("refused")):
            assert client.available() is False
        assert "Failed connecting" in client._unavailable_reason

    def test_openrouter_missing_key_false(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")
        with patch.object(GenericLLMClient, "_discover_openrouter_model"), \
             patch.object(GenericLLMClient, "_validate_and_fallback_openrouter"):
            client = GenericLLMClient()
        client._openrouter_api_key = ""
        assert client.available() is False
        assert "Missing OPENROUTER_API_KEY" in client._unavailable_reason

    def test_openrouter_with_key_true(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        with patch.object(GenericLLMClient, "_discover_openrouter_model"), \
             patch.object(GenericLLMClient, "_validate_and_fallback_openrouter"):
            client = GenericLLMClient()
        client._available = None
        assert client.available() is True

    def test_unknown_provider_false(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "carrier-pigeon")
        client = GenericLLMClient()
        assert client.available() is False
        assert "Unknown provider" in client._unavailable_reason


class TestDebugStatus:
    def test_returns_expected_keys(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        status = client.debug_status()
        assert status["enabled"] is False
        assert status["available"] is False
        assert status["reason"]

    def test_available_true_has_no_reason(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "none")
        client = GenericLLMClient()
        client._available = True
        status = client.debug_status()
        assert status["available"] is True
        assert status["reason"] is None


# ---------------------------------------------------------------------------
# generate_plain / generate_structured dispatch
# ---------------------------------------------------------------------------


class TestGeneratePlain:
    def test_unavailable_returns_none(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        assert client.generate_plain("sys", "user") is None

    def test_ollama_dispatch(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "m")
        client = GenericLLMClient()
        client._available = True
        with patch.object(client, "_ollama_chat", return_value="plain text") as mock_chat:
            result = client.generate_plain("sys", "user")
        mock_chat.assert_called_once_with(system_prompt="sys", user_prompt="user", structured=False)
        assert result == "plain text"

    def test_openrouter_dispatch(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        with patch.object(GenericLLMClient, "_discover_openrouter_model"), \
             patch.object(GenericLLMClient, "_validate_and_fallback_openrouter"):
            client = GenericLLMClient()
        client._available = True
        with patch.object(client, "_openrouter_chat", return_value="or text") as mock_chat:
            result = client.generate_plain("sys", "user")
        mock_chat.assert_called_once_with(system_prompt="sys", user_prompt="user", structured=False)
        assert result == "or text"

    def test_unknown_provider_returns_none(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "smoke-signal")
        client = GenericLLMClient()
        client._available = True
        assert client.generate_plain("sys", "user") is None

    def test_empty_result_returns_none(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "m")
        client = GenericLLMClient()
        client._available = True
        with patch.object(client, "_ollama_chat", return_value=None):
            assert client.generate_plain("sys", "user") is None

    def test_json_looking_response_extracts_description(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "m")
        client = GenericLLMClient()
        client._available = True
        raw = '{"description": "The mynx grooms itself."}'
        with patch.object(client, "_ollama_chat", return_value=raw):
            result = client.generate_plain("sys", "user")
        assert result == "The mynx grooms itself."

    def test_json_looking_response_extracts_action_when_no_description(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "m")
        client = GenericLLMClient()
        client._available = True
        raw = '{"action": "groom"}'
        with patch.object(client, "_ollama_chat", return_value=raw):
            result = client.generate_plain("sys", "user")
        assert result == "groom"

    def test_json_code_fence_but_unparseable_falls_through_to_str(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "m")
        client = GenericLLMClient()
        client._available = True
        raw = "```json\nnot actually json```"
        with patch.object(client, "_ollama_chat", return_value=raw):
            result = client.generate_plain("sys", "user")
        assert result == raw

    def test_plain_text_passthrough(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "m")
        client = GenericLLMClient()
        client._available = True
        with patch.object(client, "_ollama_chat", return_value="The mynx purrs."):
            result = client.generate_plain("sys", "user")
        assert result == "The mynx purrs."


class TestGenerateStructured:
    def test_unavailable_returns_none(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        assert client.generate_structured("sys", "user") is None

    def test_ollama_dispatch(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "m")
        client = GenericLLMClient()
        client._available = True
        with patch.object(client, "_ollama_chat", return_value={"a": 1}) as mock_chat:
            result = client.generate_structured("sys", "user")
        mock_chat.assert_called_once_with(system_prompt="sys", user_prompt="user", structured=True)
        assert result == {"a": 1}

    def test_openrouter_dispatch(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        with patch.object(GenericLLMClient, "_discover_openrouter_model"), \
             patch.object(GenericLLMClient, "_validate_and_fallback_openrouter"):
            client = GenericLLMClient()
        client._available = True
        with patch.object(client, "_openrouter_chat", return_value={"b": 2}) as mock_chat:
            result = client.generate_structured("sys", "user")
        mock_chat.assert_called_once_with(system_prompt="sys", user_prompt="user", structured=True)
        assert result == {"b": 2}

    def test_unknown_provider_returns_none(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "smoke-signal")
        client = GenericLLMClient()
        client._available = True
        assert client.generate_structured("sys", "user") is None

    def test_none_result_logs_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "m")
        client = GenericLLMClient()
        client._available = True
        with patch.object(client, "_ollama_chat", return_value=None):
            result = client.generate_structured("sys", "user")
        assert result is None

    def test_non_dict_result_logs_warning(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "m")
        client = GenericLLMClient()
        client._available = True
        with patch.object(client, "_ollama_chat", return_value=["not", "a", "dict"]):
            result = client.generate_structured("sys", "user")
        assert result == ["not", "a", "dict"]


# ---------------------------------------------------------------------------
# _ollama_chat
# ---------------------------------------------------------------------------


class TestOllamaChat:
    def _client(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "m")
        return GenericLLMClient()

    def test_message_dict_content_string(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"message": {"content": "hello world"}}
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=False)
        assert result == "hello world"

    def test_message_dict_content_list_thinking_stripped(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"message": {"content": [
            {"type": "thinking", "thinking": "..."},
            {"type": "text", "text": "final answer"},
        ]}}
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=False)
        assert result == "final answer"

    def test_choices_path_message_content(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"choices": [{"message": {"content": "from choices"}}]}
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=False)
        assert result == "from choices"

    def test_choices_path_direct_content_key(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"choices": [{"content": "direct content"}]}
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=False)
        assert result == "direct content"

    def test_output_list_path(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"output": [{"content": "part one"}, "part two"]}
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=False)
        assert "part one" in result and "part two" in result

    def test_result_string_path(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"result": "result string content"}
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=False)
        assert result == "result string content"

    def test_result_dict_path(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"result": {"content": "result dict content"}}
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=False)
        assert result == "result dict content"

    def test_content_or_text_top_level(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"text": "top level text"}
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=False)
        assert result == "top level text"

    def test_raw_text_fallback_when_no_content_found(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=200)
        resp.json.side_effect = Exception("not json")
        resp.text = "raw fallback text"
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=False)
        assert result == "raw fallback text"

    def test_structured_true_parses_json(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"message": {"content": '{"action": "groom"}'}}
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=True)
        assert result == {"action": "groom"}

    def test_non_200_status_returns_none(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=404)
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=False)
        assert result is None

    def test_request_exception_returns_none(self, monkeypatch):
        client = self._client(monkeypatch)
        with patch("requests.post", side_effect=Exception("timeout")):
            result = client._ollama_chat("sys", "user", structured=False)
        assert result is None

    def test_non_dict_data_falls_back_to_raw_text(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = MagicMock(status_code=200)
        resp.json.return_value = ["not", "a", "dict"]
        resp.text = "raw text used"
        with patch("requests.post", return_value=resp):
            result = client._ollama_chat("sys", "user", structured=False)
        assert result == "raw text used"


# ---------------------------------------------------------------------------
# OpenRouter — SDK client, headers
# ---------------------------------------------------------------------------


class TestGetSdkClient:
    def test_stub_openai_returns_none(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client._openrouter_api_key = "key"
        # The repo's local `openai` stub sets `_is_stub = True`.
        assert client._get_sdk_client() is None

    def test_non_stub_openai_returns_instance(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client._openrouter_api_key = "key"

        fake_instance = MagicMock()

        class FakeOpenAI:
            _is_stub = False

            def __init__(self, base_url, api_key):
                self.base_url = base_url
                self.api_key = api_key

        import openai
        with patch.object(openai, "OpenAI", FakeOpenAI):
            result = client._get_sdk_client()
        assert isinstance(result, FakeOpenAI)

    def test_import_error_returns_none(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client._openrouter_api_key = "key"
        import openai as openai_mod

        class Boom:
            def __init__(self, *a, **k):
                raise RuntimeError("cannot construct")

        with patch.object(openai_mod, "OpenAI", Boom):
            assert client._get_sdk_client() is None


class TestBuildOpenrouterHeaders:
    def test_no_site_or_title_empty_headers(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client._openrouter_site = None
        client._openrouter_site_title = None
        assert client._build_openrouter_headers() == {}

    def test_site_and_title_included(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        client = GenericLLMClient()
        client._openrouter_site = "https://example.com"
        client._openrouter_site_title = "My Site"
        headers = client._build_openrouter_headers()
        assert headers["HTTP-Referer"] == "https://example.com"
        assert headers["X-Title"] == "My Site"


# ---------------------------------------------------------------------------
# _openrouter_chat (multi-model orchestration)
# ---------------------------------------------------------------------------


class TestOpenrouterChat:
    def _client(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        with patch.object(GenericLLMClient, "_discover_openrouter_model"), \
             patch.object(GenericLLMClient, "_validate_and_fallback_openrouter"):
            client = GenericLLMClient()
        client.model = "primary/model"
        return client

    def test_no_api_key_returns_none(self, monkeypatch):
        client = self._client(monkeypatch)
        client._openrouter_api_key = ""
        assert client._openrouter_chat("sys", "user", structured=False) is None

    def test_primary_model_succeeds(self, monkeypatch):
        client = self._client(monkeypatch)
        with patch.object(client, "_openrouter_chat_single", return_value="primary result") as mock_single:
            result = client._openrouter_chat("sys", "user", structured=False)
        assert result == "primary result"
        mock_single.assert_called_once()
        assert mock_single.call_args[0][0] == "primary/model"

    def test_primary_fails_then_fallback_succeeds(self, monkeypatch):
        client = self._client(monkeypatch)

        def fake_single(model_id, *args, **kwargs):
            if model_id == "primary/model":
                return None
            return "fallback result"

        with patch.object(client, "_openrouter_chat_single", side_effect=fake_single):
            result = client._openrouter_chat("sys", "user", structured=False)
        assert result == "fallback result"

    def test_all_models_fail_returns_none(self, monkeypatch):
        client = self._client(monkeypatch)
        with patch.object(client, "_openrouter_chat_single", return_value=None):
            result = client._openrouter_chat("sys", "user", structured=False)
        assert result is None

    def test_max_attempts_stops_after_two(self, monkeypatch):
        client = self._client(monkeypatch)
        GenericLLMClient._free_models_cache = ["dyn/a", "dyn/b", "dyn/c"]
        calls = []

        def fake_single(model_id, *args, **kwargs):
            calls.append(model_id)
            return None

        with patch.object(client, "_openrouter_chat_single", side_effect=fake_single):
            client._openrouter_chat("sys", "user", structured=False)
        assert len(calls) == 2

    def test_skips_models_marked_failed(self, monkeypatch):
        client = self._client(monkeypatch)
        client._mark_model_failed("primary/model", duration_minutes=30)
        with patch.object(client, "_openrouter_chat_single", return_value="ok") as mock_single:
            result = client._openrouter_chat("sys", "user", structured=False)
        assert result == "ok"
        assert mock_single.call_args[0][0] != "primary/model"


# ---------------------------------------------------------------------------
# _openrouter_chat_single (SDK path + HTTP fallback)
# ---------------------------------------------------------------------------


class TestOpenrouterChatSingle:
    def _client(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        with patch.object(GenericLLMClient, "_discover_openrouter_model"), \
             patch.object(GenericLLMClient, "_validate_and_fallback_openrouter"):
            client = GenericLLMClient()
        return client

    def _fake_sdk_success(self, content):
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content=content))]
        sdk = MagicMock()
        sdk.chat.completions.create.return_value = completion
        return sdk

    def test_sdk_success_plain(self, monkeypatch):
        client = self._client(monkeypatch)
        sdk = self._fake_sdk_success("Hello from SDK")
        with patch.object(client, "_get_sdk_client", return_value=sdk):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        assert result == "Hello from SDK"

    def test_sdk_success_structured(self, monkeypatch):
        client = self._client(monkeypatch)
        sdk = self._fake_sdk_success('{"action": "groom"}')
        with patch.object(client, "_get_sdk_client", return_value=sdk):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=True)
        assert result == {"action": "groom"}

    def test_sdk_no_content_falls_through_to_http(self, monkeypatch):
        client = self._client(monkeypatch)
        sdk = self._fake_sdk_success(None)
        http_resp = MagicMock(status_code=200)
        http_resp.json.return_value = {"choices": [{"message": {"content": "http fallback"}}]}
        with patch.object(client, "_get_sdk_client", return_value=sdk), \
             patch("requests.post", return_value=http_resp):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        assert result == "http fallback"

    def test_sdk_exception_falls_through_to_http(self, monkeypatch):
        client = self._client(monkeypatch)
        sdk = MagicMock()
        sdk.chat.completions.create.side_effect = Exception("sdk exploded")
        http_resp = MagicMock(status_code=200)
        http_resp.json.return_value = {"choices": [{"message": {"content": "http after sdk error"}}]}
        with patch.object(client, "_get_sdk_client", return_value=sdk), \
             patch("requests.post", return_value=http_resp):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        assert result == "http after sdk error"

    def test_no_sdk_client_goes_direct_to_http(self, monkeypatch):
        client = self._client(monkeypatch)
        http_resp = MagicMock(status_code=200)
        http_resp.json.return_value = {"choices": [{"message": {"content": "direct http"}}]}
        with patch.object(client, "_get_sdk_client", return_value=None), \
             patch("requests.post", return_value=http_resp):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        assert result == "direct http"

    def test_http_429_marks_failed_and_returns_none(self, monkeypatch):
        client = self._client(monkeypatch)
        http_resp = MagicMock(status_code=429)
        with patch.object(client, "_get_sdk_client", return_value=None), \
             patch("requests.post", return_value=http_resp):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        assert result is None
        assert client._is_model_failed("model/x") is True

    def test_http_200_with_error_key_returns_none(self, monkeypatch):
        client = self._client(monkeypatch)
        http_resp = MagicMock(status_code=200)
        http_resp.json.return_value = {"error": {"message": "bad request"}}
        with patch.object(client, "_get_sdk_client", return_value=None), \
             patch("requests.post", return_value=http_resp):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        assert result is None

    def test_http_200_reasoning_fallback_when_no_content(self, monkeypatch):
        client = self._client(monkeypatch)
        http_resp = MagicMock(status_code=200)
        http_resp.json.return_value = {"choices": [{"message": {"content": None, "reasoning": "reasoning text"}}]}
        with patch.object(client, "_get_sdk_client", return_value=None), \
             patch("requests.post", return_value=http_resp):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        assert result == "reasoning text"

    def test_http_200_top_level_text_field(self, monkeypatch):
        client = self._client(monkeypatch)
        http_resp = MagicMock(status_code=200)
        http_resp.json.return_value = {"choices": [{"text": "legacy completion text"}]}
        with patch.object(client, "_get_sdk_client", return_value=None), \
             patch("requests.post", return_value=http_resp):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        assert result == "legacy completion text"

    def test_http_200_no_content_anywhere_returns_none(self, monkeypatch):
        client = self._client(monkeypatch)
        http_resp = MagicMock(status_code=200)
        http_resp.json.return_value = {"choices": [{}]}
        with patch.object(client, "_get_sdk_client", return_value=None), \
             patch("requests.post", return_value=http_resp):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        assert result is None

    def test_http_non_200_non_429_returns_none(self, monkeypatch):
        client = self._client(monkeypatch)
        http_resp = MagicMock(status_code=500, text="server error")
        with patch.object(client, "_get_sdk_client", return_value=None), \
             patch("requests.post", return_value=http_resp):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        assert result is None

    def test_http_exception_returns_none(self, monkeypatch):
        client = self._client(monkeypatch)
        with patch.object(client, "_get_sdk_client", return_value=None), \
             patch("requests.post", side_effect=Exception("connection reset")):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        assert result is None

    def test_structured_true_parses_json_from_http(self, monkeypatch):
        client = self._client(monkeypatch)
        http_resp = MagicMock(status_code=200)
        http_resp.json.return_value = {"choices": [{"message": {"content": '{"action": "play"}'}}]}
        with patch.object(client, "_get_sdk_client", return_value=None), \
             patch("requests.post", return_value=http_resp):
            result = client._openrouter_chat_single("model/x", "sys", "user", structured=True)
        assert result == {"action": "play"}

    def test_extra_headers_included_when_site_configured(self, monkeypatch):
        client = self._client(monkeypatch)
        client._openrouter_site = "https://example.com"
        client._openrouter_site_title = "Title"
        http_resp = MagicMock(status_code=200)
        http_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        with patch.object(client, "_get_sdk_client", return_value=None), \
             patch("requests.post", return_value=http_resp) as mock_post:
            client._openrouter_chat_single("model/x", "sys", "user", structured=False)
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["HTTP-Referer"] == "https://example.com"
        assert headers["X-Title"] == "Title"


# ---------------------------------------------------------------------------
# Failure tracking
# ---------------------------------------------------------------------------


class TestModelFailureTracking:
    def _client(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        return GenericLLMClient()

    def test_unmarked_model_not_failed(self, monkeypatch):
        client = self._client(monkeypatch)
        assert client._is_model_failed("never/marked") is False

    def test_marked_model_is_failed(self, monkeypatch):
        client = self._client(monkeypatch)
        client._mark_model_failed("bad/model", duration_minutes=10)
        assert client._is_model_failed("bad/model") is True

    def test_expired_penalty_clears_and_returns_false(self, monkeypatch):
        client = self._client(monkeypatch)
        GenericLLMClient._failed_models["expired/model"] = datetime.now() - timedelta(minutes=1)
        assert client._is_model_failed("expired/model") is False
        assert "expired/model" not in GenericLLMClient._failed_models

    def test_penalty_only_extended_never_shortened(self, monkeypatch):
        client = self._client(monkeypatch)
        client._mark_model_failed("model/x", duration_minutes=30)
        long_expiry = GenericLLMClient._failed_models["model/x"]
        client._mark_model_failed("model/x", duration_minutes=2)
        assert GenericLLMClient._failed_models["model/x"] == long_expiry

    def test_penalty_extended_when_longer(self, monkeypatch):
        client = self._client(monkeypatch)
        client._mark_model_failed("model/x", duration_minutes=2)
        short_expiry = GenericLLMClient._failed_models["model/x"]
        client._mark_model_failed("model/x", duration_minutes=30)
        assert GenericLLMClient._failed_models["model/x"] > short_expiry


# ---------------------------------------------------------------------------
# MynxLLMAdapter
# ---------------------------------------------------------------------------


class TestMynxLLMAdapter:
    def test_loads_real_advisor_file(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        assert "investigate_object" in adapter._allowed_actions
        assert adapter._system_prompt

    def test_load_advisor_missing_file_uses_default(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        with patch("builtins.open", side_effect=FileNotFoundError("no file")):
            adapter = MynxLLMAdapter()
        assert adapter._allowed_actions == {"investigate_object", "groom", "play"}
        assert "mynx" in adapter._system_prompt.lower()

    def test_generate_plain_builds_prompt_and_delegates(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        with patch.object(GenericLLMClient, "generate_plain", return_value="The mynx chitters.") as mock_gen:
            result = adapter.generate_plain("Jean offers a berry.")
        assert result == "The mynx chitters."
        args, kwargs = mock_gen.call_args
        assert kwargs["system_prompt"] == adapter._system_prompt
        assert "Jean offers a berry." in kwargs["user_prompt"]
        assert "PLAIN TEXT" in kwargs["user_prompt"]

    def test_generate_structured_valid_response(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        valid = {
            "action": "groom",
            "intensity": "low",
            "description": "The mynx grooms its fur.",
            "duration_seconds": 2,
            "audible": "soft purr",
        }
        with patch.object(GenericLLMClient, "generate_structured", return_value=valid):
            result = adapter.generate_structured("context")
        assert result["action"] == "groom"

    def test_generate_structured_repairs_invalid_response(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        invalid = {"action": "not_allowed_action", "text": "  'quoted text'  "}
        with patch.object(GenericLLMClient, "generate_structured", return_value=invalid):
            result = adapter.generate_structured("context")
        assert result is not None
        assert result["action"] in adapter._allowed_actions
        assert result["description"] == "quoted text"

    def test_generate_structured_unrepairable_returns_none(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        with patch.object(GenericLLMClient, "generate_structured", return_value="not a dict"):
            result = adapter.generate_structured("context")
        assert result is None

    def test_build_user_prompt_structured_uses_example_struct(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        prompt = adapter._build_user_prompt("some context", structured=True)
        assert "Allowed actions" in prompt
        assert "some context" in prompt

    def test_build_user_prompt_plain(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        prompt = adapter._build_user_prompt("some context", structured=False)
        assert "plain description" in prompt.lower()
        assert "some context" in prompt

    def test_build_user_prompt_structured_falls_back_when_no_example(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        adapter._example_struct = {}
        adapter._allowed_actions = set()
        prompt = adapter._build_user_prompt("ctx", structured=True)
        assert "investigate_object, groom, play" in prompt

    def test_validate_structured_missing_keys_false(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        assert adapter._validate_structured({"action": "groom"}) is False

    def test_validate_structured_action_not_string_false(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        obj = {"action": 123, "intensity": "low", "description": "x", "duration_seconds": 1, "audible": "y"}
        assert adapter._validate_structured(obj) is False

    def test_validate_structured_action_not_allowed_false(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        obj = {"action": "not_a_real_action", "intensity": "low", "description": "x", "duration_seconds": 1, "audible": "y"}
        assert adapter._validate_structured(obj) is False

    def test_validate_structured_description_not_string_false(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        action = next(iter(adapter._allowed_actions))
        obj = {"action": action, "intensity": "low", "description": 123, "duration_seconds": 1, "audible": "y"}
        assert adapter._validate_structured(obj) is False

    def test_validate_structured_sanitizes_description(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        action = next(iter(adapter._allowed_actions))
        obj = {"action": action, "intensity": "low", "description": '"  spaced   text  "', "duration_seconds": 1, "audible": "y"}
        assert adapter._validate_structured(obj) is True
        assert obj["description"] == "spaced text"

    def test_repair_structured_uses_text_key_when_no_description(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        repaired = adapter._repair_structured({"text": "fallback text value"})
        assert repaired["description"] == "fallback text value"

    def test_repair_structured_coerces_non_string_description(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        repaired = adapter._repair_structured({"description": 42})
        assert repaired["description"] == "42"

    def test_repair_structured_defaults_when_no_allowed_actions(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        adapter._allowed_actions = set()
        repaired = adapter._repair_structured({"action": "bogus"})
        assert repaired["action"] == "investigate_object"

    def test_repair_structured_defaults_intensity_duration_audible(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        adapter = MynxLLMAdapter()
        action = next(iter(adapter._allowed_actions))
        repaired = adapter._repair_structured({"action": action})
        assert repaired["intensity"] == "low"
        assert repaired["duration_seconds"] == 2
        assert repaired["audible"] == "soft chitter"


# ---------------------------------------------------------------------------
# NpcChatLLMAdapter
# ---------------------------------------------------------------------------


class TestNpcChatLLMAdapterInit:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        assert adapter.enabled is False

    def test_enabled_via_npc_specific_flag(self, monkeypatch):
        monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "1")
        adapter = NpcChatLLMAdapter()
        assert adapter.enabled is True

    def test_provider_override(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        monkeypatch.setenv("NPC_CHAT_LLM_PROVIDER", "openrouter")
        adapter = NpcChatLLMAdapter()
        assert adapter.provider == "openrouter"

    def test_no_provider_override_keeps_generic_default(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        monkeypatch.delenv("NPC_CHAT_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("MYNX_LLM_PROVIDER", raising=False)
        adapter = NpcChatLLMAdapter()
        assert adapter.provider == "ollama"

    def test_model_override(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        monkeypatch.setenv("NPC_CHAT_LLM_MODEL", "custom-npc-model")
        adapter = NpcChatLLMAdapter()
        assert adapter.model == "custom-npc-model"

    def test_world_facts_loaded_from_real_file(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        assert adapter._world_facts is not None

    def test_world_facts_fallback_on_load_failure(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        with patch("builtins.open", side_effect=FileNotFoundError("missing")):
            adapter = NpcChatLLMAdapter()
        assert adapter._world_facts["world_name"] == "Aurelion"

    def test_get_instance_singleton(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        NpcChatLLMAdapter._instances.clear()
        first = NpcChatLLMAdapter.get_instance()
        second = NpcChatLLMAdapter.get_instance()
        assert first is second
        NpcChatLLMAdapter._instances.clear()


class TestWorldFactsBlock:
    def test_full_world_facts_block(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        adapter._world_facts = {
            "world_name": "Aurelion",
            "brief_description": "A grim place.",
            "geography": ["Badlands", "Caves"],
            "factions_and_peoples": ["Nomads"],
            "world_rules": ["No magic swords."],
            "tone_notes": "Grim.",
        }
        block = adapter._world_facts_block()
        assert "Aurelion" in block
        assert "Badlands" in block
        assert "Nomads" in block

    def test_empty_world_facts_returns_default(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        adapter._world_facts = None
        block = adapter._world_facts_block()
        assert "Aurelion" in block


class TestGeneratePersonality:
    def test_returns_none_when_call_llm_empty(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        with patch.object(adapter, "_call_llm", return_value=None):
            assert adapter.generate_personality("Nomad") is None

    def test_returns_none_on_unparseable_json(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        with patch.object(adapter, "_call_llm", return_value="not json"):
            assert adapter.generate_personality("Nomad") is None

    def test_returns_none_when_missing_required_keys(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        with patch.object(adapter, "_call_llm", return_value='{"given_name": "Tam"}'):
            assert adapter.generate_personality("Nomad") is None

    def test_success_returns_dict(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps({
            "given_name": "Tam",
            "voice": "sparse",
            "knowledge": ["trade", "weather"],
            "attitude_to_strangers": "wary",
            "speech_sample": "Move along.",
            "loquacity_base": 50,
        })
        with patch.object(adapter, "_call_llm", return_value=raw) as mock_call:
            result = adapter.generate_personality("Nomad")
        assert result["given_name"] == "Tam"
        assert mock_call.call_args.kwargs["temperature"] == 0.7


class TestGenerateNpcTurn:
    def test_returns_none_when_no_raw(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        with patch.object(adapter, "_call_llm", return_value=None):
            assert adapter.generate_npc_turn("sys", [], is_opening=True) is None

    def test_returns_none_on_unparseable(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        with patch.object(adapter, "_call_llm", return_value="not json"):
            assert adapter.generate_npc_turn("sys", [], is_opening=True) is None

    def test_returns_none_when_npc_text_missing(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        with patch.object(adapter, "_call_llm", return_value='{"conversation_quality": "neutral"}'):
            assert adapter.generate_npc_turn("sys", [], is_opening=True) is None

    def test_opening_task_used(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps({"npc_text": "Hello there.", "conversation_quality": "positive",
                           "conversation_end": False, "reputation_delta": 2})
        with patch.object(adapter, "_call_llm", return_value=raw) as mock_call:
            result = adapter.generate_npc_turn("sys", [], is_opening=True)
        assert "opening line" in mock_call.call_args[0][1]
        assert result["npc_text"] == "Hello there."
        assert result["reputation_delta"] == 2

    def test_response_task_includes_jean_text(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps({"npc_text": "I see.", "conversation_quality": "neutral",
                           "conversation_end": False, "reputation_delta": 0})
        with patch.object(adapter, "_call_llm", return_value=raw) as mock_call:
            result = adapter.generate_npc_turn("sys", [], is_opening=False, jean_text="Hello.")
        assert "Jean said" in mock_call.call_args[0][1]
        assert result["npc_text"] == "I see."

    def test_invalid_quality_normalized_to_neutral(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps({"npc_text": "Hm.", "conversation_quality": "bogus-quality"})
        with patch.object(adapter, "_call_llm", return_value=raw):
            result = adapter.generate_npc_turn("sys", [], is_opening=True)
        assert result["conversation_quality"] == "neutral"

    def test_reputation_delta_clamped_high(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps({"npc_text": "Hm.", "reputation_delta": 999})
        with patch.object(adapter, "_call_llm", return_value=raw):
            result = adapter.generate_npc_turn("sys", [], is_opening=True)
        assert result["reputation_delta"] == 5

    def test_reputation_delta_clamped_low(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps({"npc_text": "Hm.", "reputation_delta": -999})
        with patch.object(adapter, "_call_llm", return_value=raw):
            result = adapter.generate_npc_turn("sys", [], is_opening=True)
        assert result["reputation_delta"] == -5

    def test_reputation_delta_non_numeric_defaults_zero(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps({"npc_text": "Hm.", "reputation_delta": "not-a-number"})
        with patch.object(adapter, "_call_llm", return_value=raw):
            result = adapter.generate_npc_turn("sys", [], is_opening=True)
        assert result["reputation_delta"] == 0

    def test_conversation_end_defaults_false(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps({"npc_text": "Hm."})
        with patch.object(adapter, "_call_llm", return_value=raw):
            result = adapter.generate_npc_turn("sys", [], is_opening=True)
        assert result["conversation_end"] is False

    def test_history_included_in_prompt(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps({"npc_text": "Hm."})
        history = [{"npc": "Hello", "jean": "Hi"}]
        with patch.object(adapter, "_call_llm", return_value=raw) as mock_call:
            adapter.generate_npc_turn("sys", history, is_opening=False, jean_text="hi")
        assert "Hello" in mock_call.call_args[0][1]


class TestGenerateJeanOptions:
    def test_returns_none_when_no_raw(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        with patch.object(adapter, "_call_llm", return_value=None):
            assert adapter.generate_jean_options("Nomad", "voice", "last", [], 1) is None

    def test_success_returns_three_options(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps([
            {"tone": "direct", "text": "I need to go."},
            {"tone": "guarded", "text": "Maybe. We'll see."},
            {"tone": "open", "text": "Tell me more about this place."},
        ])
        with patch.object(adapter, "_call_llm", return_value=raw):
            result = adapter.generate_jean_options("Nomad", "voice", "last line", [], 1)
        assert len(result) == 3
        assert result[0]["tone"] == "direct"

    def test_code_fence_stripped_before_parse(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = "```json\n" + json.dumps([
            {"tone": "direct", "text": "a"},
            {"tone": "guarded", "text": "b"},
            {"tone": "open", "text": "c"},
        ]) + "\n```"
        with patch.object(adapter, "_call_llm", return_value=raw):
            result = adapter.generate_jean_options("Nomad", "voice", "last", [], 1)
        assert len(result) == 3

    def test_bracket_extraction_fallback(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = 'Sure, here you go: ' + json.dumps([
            {"tone": "direct", "text": "a"},
            {"tone": "guarded", "text": "b"},
            {"tone": "open", "text": "c"},
        ]) + ' hope that helps'
        with patch.object(adapter, "_call_llm", return_value=raw):
            result = adapter.generate_jean_options("Nomad", "voice", "last", [], 1)
        assert len(result) == 3

    def test_bracket_extraction_failure_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = "no brackets here at all"
        with patch.object(adapter, "_call_llm", return_value=raw):
            assert adapter.generate_jean_options("Nomad", "voice", "last", [], 1) is None

    def test_bracket_extraction_invalid_json_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = "prefix [not valid json] suffix"
        with patch.object(adapter, "_call_llm", return_value=raw):
            assert adapter.generate_jean_options("Nomad", "voice", "last", [], 1) is None

    def test_fewer_than_three_items_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps([{"tone": "direct", "text": "a"}])
        with patch.object(adapter, "_call_llm", return_value=raw):
            assert adapter.generate_jean_options("Nomad", "voice", "last", [], 1) is None

    def test_not_a_list_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps({"not": "a list"})
        with patch.object(adapter, "_call_llm", return_value=raw):
            assert adapter.generate_jean_options("Nomad", "voice", "last", [], 1) is None

    def test_item_missing_text_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps([
            {"tone": "direct", "text": "a"},
            {"tone": "guarded"},
            {"tone": "open", "text": "c"},
        ])
        with patch.object(adapter, "_call_llm", return_value=raw):
            assert adapter.generate_jean_options("Nomad", "voice", "last", [], 1) is None

    def test_invalid_tone_replaced_with_expected(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps([
            {"tone": "bogus", "text": "a"},
            {"tone": "guarded", "text": "b"},
            {"tone": "open", "text": "c"},
        ])
        with patch.object(adapter, "_call_llm", return_value=raw):
            result = adapter.generate_jean_options("Nomad", "voice", "last", [], 1)
        assert result[0]["tone"] == "direct"

    def test_text_truncated_to_200_chars(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        long_text = "x" * 300
        raw = json.dumps([
            {"tone": "direct", "text": long_text},
            {"tone": "guarded", "text": "b"},
            {"tone": "open", "text": "c"},
        ])
        with patch.object(adapter, "_call_llm", return_value=raw):
            result = adapter.generate_jean_options("Nomad", "voice", "last", [], 1)
        assert len(result[0]["text"]) == 200

    def test_history_hint_included_when_present(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        raw = json.dumps([
            {"tone": "direct", "text": "a"},
            {"tone": "guarded", "text": "b"},
            {"tone": "open", "text": "c"},
        ])
        history = [{"jean": "I already said this."}]
        with patch.object(adapter, "_call_llm", return_value=raw) as mock_call:
            adapter.generate_jean_options("Nomad", "voice", "last", history, 3)
        assert "I already said this." in mock_call.call_args[0][1]


class TestCallLlmDispatcher:
    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        assert adapter._call_llm("sys", "user") is None

    def test_ollama_dispatch(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "1")
        monkeypatch.setenv("NPC_CHAT_LLM_PROVIDER", "ollama")
        adapter = NpcChatLLMAdapter()
        with patch.object(adapter, "_call_ollama", return_value="ollama says hi") as mock_call:
            result = adapter._call_llm("sys", "user")
        assert result == "ollama says hi"
        mock_call.assert_called_once()

    def test_openrouter_dispatch(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "1")
        monkeypatch.setenv("NPC_CHAT_LLM_PROVIDER", "openrouter")
        adapter = NpcChatLLMAdapter()
        with patch.object(adapter, "_call_openrouter", return_value="openrouter says hi") as mock_call:
            result = adapter._call_llm("sys", "user")
        assert result == "openrouter says hi"
        mock_call.assert_called_once()

    def test_unknown_provider_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "1")
        monkeypatch.setenv("NPC_CHAT_LLM_PROVIDER", "smoke-signal")
        adapter = NpcChatLLMAdapter()
        assert adapter._call_llm("sys", "user") is None


class TestCallOllama:
    def test_requests_none_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        with patch.object(llm_client, "requests", None):
            assert adapter._call_ollama("sys", "user", 100, 0.5) is None

    def test_success_strips_and_returns_content(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"message": {"content": "  hello there  "}}
        with patch("requests.post", return_value=resp):
            result = adapter._call_ollama("sys", "user", 100, 0.5)
        assert result == "hello there"

    def test_empty_content_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"message": {"content": "   "}}
        with patch("requests.post", return_value=resp):
            result = adapter._call_ollama("sys", "user", 100, 0.5)
        assert result is None

    def test_request_exception_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        with patch("requests.post", side_effect=Exception("boom")):
            result = adapter._call_ollama("sys", "user", 100, 0.5)
        assert result is None


class TestCallOpenrouter:
    def test_requests_none_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        adapter._openrouter_api_key = "key"
        with patch.object(llm_client, "requests", None):
            assert adapter._call_openrouter("sys", "user", 100, 0.5) is None

    def test_no_api_key_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        adapter._openrouter_api_key = ""
        assert adapter._call_openrouter("sys", "user", 100, 0.5) is None

    def test_no_model_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        adapter._openrouter_api_key = "key"
        with patch.object(adapter, "_get_openrouter_model", return_value=None):
            assert adapter._call_openrouter("sys", "user", 100, 0.5) is None

    def test_success_with_site_headers(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        adapter._openrouter_api_key = "key"
        adapter.model = "model/x"
        adapter._openrouter_site = "https://example.com"
        adapter._openrouter_site_title = "Title"
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"choices": [{"message": {"content": "  npc reply  "}}]}
        with patch("requests.post", return_value=resp) as mock_post:
            result = adapter._call_openrouter("sys", "user", 100, 0.5)
        assert result == "npc reply"
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["HTTP-Referer"] == "https://example.com"
        assert headers["X-Title"] == "Title"

    def test_empty_content_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        adapter._openrouter_api_key = "key"
        adapter.model = "model/x"
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"choices": [{"message": {"content": "   "}}]}
        with patch("requests.post", return_value=resp):
            result = adapter._call_openrouter("sys", "user", 100, 0.5)
        assert result is None

    def test_request_exception_returns_none(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        adapter._openrouter_api_key = "key"
        adapter.model = "model/x"
        with patch("requests.post", side_effect=Exception("boom")):
            result = adapter._call_openrouter("sys", "user", 100, 0.5)
        assert result is None


class TestGetOpenrouterModel:
    def test_explicit_model_returned(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        adapter.model = "explicit/model"
        assert adapter._get_openrouter_model() == "explicit/model"

    def test_auto_uses_free_cache(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        adapter.model = "auto"
        GenericLLMClient._free_models_cache = ["cached/model"]
        assert adapter._get_openrouter_model() == "cached/model"

    def test_auto_falls_back_to_stable(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")
        adapter = NpcChatLLMAdapter()
        adapter.model = "auto"
        GenericLLMClient._free_models_cache = []
        assert adapter._get_openrouter_model() == GenericLLMClient.STABLE_FREE_FALLBACKS[0]


class TestFormatHistory:
    def test_empty_history(self):
        result = NpcChatLLMAdapter._format_history([])
        assert "None yet" in result

    def test_history_with_npc_and_jean_lines(self):
        history = [{"npc": "Greetings.", "jean": "Hello."}]
        result = NpcChatLLMAdapter._format_history(history)
        assert "NPC: Greetings." in result
        assert "Jean: Hello." in result

    def test_history_truncated_to_last_8(self):
        history = [{"npc": f"line{i}"} for i in range(20)]
        result = NpcChatLLMAdapter._format_history(history)
        assert "line19" in result
        assert "line0" not in result
