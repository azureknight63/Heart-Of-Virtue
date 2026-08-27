"""The shared chat payload, and the metering every transport owes the digest.

Two invariants live here, both of which had a hole in them:

1. One payload builder. Four transports each spelled model / messages /
   temperature / top_p / max_tokens / reasoning out by hand, and only two of
   them sent ``response_format`` -- so ``generate_structured``, the
   CombatStrategist's only path, demanded JSON in prose and never once asked
   the API to enforce it, while ``_rank_models`` was filtering the whole model
   pool on ``_supports_structured_output`` for exactly that field.

2. No call site spends quota invisibly. ``_openrouter_attempt``'s docstring
   states it; ``_ollama_chat`` and ``_call_openai_compatible``'s transport
   failures did not honour it.

Plus the third OpenRouter candidate loop, ``_validate_and_fallback_openrouter``,
which the 429 work never reached.
"""

import pytest

import ai.llm_client as llm
from ai.llm_client import GenericLLMClient, NpcChatLLMAdapter


class _Resp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {
            "choices": [{"message": {"content": '{"npc_text": "Fine."}'}}]
        }
        self.text = text
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %s" % self.status_code)


@pytest.fixture(autouse=True)
def _isolate_class_state(monkeypatch, tmp_path):
    """Process-wide counters, benches and the disk cache, per test."""
    GenericLLMClient.reset_class_state()
    monkeypatch.setattr(llm, "_MODEL_CACHE_FILE", str(tmp_path / ".model_cache.json"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    yield
    GenericLLMClient.reset_class_state()


def _openrouter_client():
    c = GenericLLMClient.__new__(GenericLLMClient)
    c.enabled = True
    c.provider = "openrouter"
    c.model = "some/model"
    c._openrouter_api_key = "k"
    c._openrouter_site = ""
    c._openrouter_site_title = ""
    c._sdk_client = None
    c._available = True
    return c


class TestSharedChatPayload:
    def _payload_from_http(self, monkeypatch, structured):
        seen = {}

        def post(url, payload, headers, timeout):
            seen.update(payload)
            return _Resp()

        monkeypatch.setattr(llm, "_post_chat_completion", post)
        # No SDK: _try_sdk would otherwise open a real socket to openrouter.ai
        # with a junk key, take the 401 as a deterministic refusal, and settle
        # the attempt before the HTTP payload under test is ever built.
        monkeypatch.setattr(
            GenericLLMClient, "_get_sdk_client", lambda self: None
        )
        _openrouter_client()._openrouter_chat_single(
            "m/x", "sys", "user", structured=structured
        )
        return seen

    def test_a_structured_request_asks_the_api_for_json(self, monkeypatch):
        payload = self._payload_from_http(monkeypatch, structured=True)
        assert payload["response_format"] == {"type": "json_object"}

    def test_a_plain_request_does_not(self, monkeypatch):
        """A plain reply is prose. Pinning it to a JSON object would make every
        Mynx line either an escaped blob or a 400."""
        payload = self._payload_from_http(monkeypatch, structured=False)
        assert "response_format" not in payload

    def test_the_token_budget_comes_from_the_named_constants(self, monkeypatch):
        structured = self._payload_from_http(monkeypatch, structured=True)
        plain = self._payload_from_http(monkeypatch, structured=False)
        assert structured["max_tokens"] == llm._STRUCTURED_MAX_TOKENS
        assert plain["max_tokens"] == llm._PLAIN_MAX_TOKENS

    def test_the_openrouter_reasoning_dialect_travels_with_it(self, monkeypatch):
        payload = self._payload_from_http(monkeypatch, structured=True)
        assert payload["reasoning"] == {"effort": "low", "exclude": True}

    def test_the_sdk_path_carries_json_mode_too(self, monkeypatch):
        """The SDK takes typed kwargs and rejects unknown ones, so the reasoning
        block has to move into extra_body -- but response_format is a real SDK
        parameter and must still be sent."""
        seen = {}

        class _Completions:
            def create(self, **kwargs):
                seen.update(kwargs)
                raise RuntimeError("the payload is what is under test")

        class _Chat:
            completions = _Completions()

        class _Client:
            chat = _Chat()

        _openrouter_client()._try_sdk(_Client(), "m/x", "sys", "user", True, 5)

        assert seen["response_format"] == {"type": "json_object"}
        assert seen["max_tokens"] == llm._STRUCTURED_MAX_TOKENS
        assert "reasoning" not in seen, "the SDK would reject an unknown kwarg"
        assert seen["extra_body"] == {"reasoning": {"effort": "low", "exclude": True}}

    def test_a_skip_reasoning_retry_still_asks_for_json(self, monkeypatch):
        """skip_reasoning drops the block the endpoint has already refused. It
        must not take response_format with it."""
        seen = {}

        def post(url, payload, headers, timeout):
            seen.update(payload)
            return _Resp()

        monkeypatch.setattr(llm, "_post_chat_completion", post)
        _openrouter_client()._try_http(
            "m/x", "sys", "user", True, 5, skip_reasoning=True
        )
        assert "reasoning" not in seen
        assert seen["response_format"] == {"type": "json_object"}

    def test_the_chat_adapter_still_pins_json_on_every_openrouter_attempt(
        self, monkeypatch
    ):
        seen = {}

        def post(url, payload, headers, timeout):
            seen.update(payload)
            return _Resp()

        monkeypatch.setattr(llm, "_post_chat_completion", post)
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "openrouter"
        a.model = "some/model"
        a._openrouter_api_key = "k"
        a._openrouter_site = ""
        a._openrouter_site_title = ""

        assert a._call_openrouter("sys", "user", 321, 0.55)
        assert seen["response_format"] == {"type": "json_object"}
        # The adapter's own per-call settings survive the shared builder.
        assert seen["max_tokens"] == 321
        assert seen["temperature"] == 0.55


class TestOllamaTransportIsMetered:
    """R5: ``GenericLLMClient._ollama_chat`` was the last unmetered transport,
    while its sibling ``NpcChatLLMAdapter._call_ollama`` metered. Every Mynx and
    CombatStrategist Ollama call was invisible to the digest."""

    def _client(self):
        c = GenericLLMClient.__new__(GenericLLMClient)
        c.enabled = True
        c.provider = "ollama"
        c.model = "m"
        c.base_url = "http://localhost:11434"
        c._available = True
        return c

    def _stats(self):
        return GenericLLMClient.provider_saturation()["providers"].get("ollama", {})

    def test_a_successful_call_is_counted(self, monkeypatch):
        payload = {"message": {"content": "the mynx chitters"}}
        monkeypatch.setattr(
            llm.requests, "post", lambda *a, **k: _Resp(200, payload=payload)
        )
        assert self._client()._ollama_chat("s", "u", False)
        assert self._stats()["requests"] == 1
        assert self._stats()["successes"] == 1

    def test_a_non_200_is_counted_as_an_error(self, monkeypatch):
        monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _Resp(500))
        assert self._client()._ollama_chat("s", "u", False) is None
        assert self._stats()["errors"] == 1

    def test_a_transport_exception_is_counted_as_an_error(self, monkeypatch):
        def boom(*a, **k):
            raise OSError("no local host")

        monkeypatch.setattr(llm.requests, "post", boom)
        assert self._client()._ollama_chat("s", "u", False) is None
        assert self._stats()["errors"] == 1

    def test_an_ollama_only_window_does_not_report_no_calls(self, monkeypatch):
        payload = {"message": {"content": "chitter"}}
        monkeypatch.setattr(
            llm.requests, "post", lambda *a, **k: _Resp(200, payload=payload)
        )
        client = self._client()
        client._ollama_chat("s", "u", False)
        client._ollama_chat("s", "u", False)
        snap = GenericLLMClient.snapshot_and_reset()
        assert snap["providers"]["ollama"]["requests"] == 2


class TestOpenAiCompatibleFailuresAreCounted:
    """S5: ``_post_chat_completion`` and ``response.json()`` sat outside any
    try, so a socket error or a non-JSON 200 escaped without ever reaching
    ``_record_provider_usage`` -- a groq or cerebras outage was invisible in the
    digest, and ``_call_llm``'s broad except was quietly load-bearing for this
    method's documented "yields None, the chain moves on" contract."""

    def _adapter(self):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "groq"
        a.model = "m"
        return a

    def test_a_transport_failure_yields_none_and_is_recorded(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "g")

        def boom(*a, **k):
            raise OSError("connection reset")

        monkeypatch.setattr(llm, "_post_chat_completion", boom)

        assert self._adapter()._call_openai_compatible("groq", "s", "u", 10, 0.5) is None
        assert GenericLLMClient.provider_saturation()["providers"]["groq"]["errors"] == 1

    def test_an_unreadable_200_body_is_recorded_too(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "g")

        class _Garbage(_Resp):
            def json(self):
                raise ValueError("not JSON at all")

        monkeypatch.setattr(llm, "_post_chat_completion", lambda *a, **k: _Garbage())

        assert self._adapter()._call_openai_compatible("groq", "s", "u", 10, 0.5) is None
        assert GenericLLMClient.provider_saturation()["providers"]["groq"]["errors"] == 1


class TestValidationRespectsTheAccountQuota:
    """S2: ``_validate_and_fallback_openrouter`` was the third OpenRouter loop
    and the one the 429 work never reached -- 1 primary + 5 fallback dials, all
    guaranteed 429s, at prewarm on a spent account -- and it then latched
    ``self.enabled = False``, disabling the WHOLE chain (groq and cerebras
    included) for the life of the process over one spent free tier."""

    def _client(self):
        c = GenericLLMClient.__new__(GenericLLMClient)
        c.enabled = True
        c.provider = "openrouter"
        c.model = "primary/model"
        c._openrouter_api_key = "k"
        c._available = None
        c._unavailable_reason = None
        return c

    def test_a_spent_account_is_not_dialled_at_all(self, monkeypatch):
        GenericLLMClient._record_provider_usage("openrouter", _Resp(429), "rate_limited")
        assert GenericLLMClient._provider_available("openrouter") is False

        dialled = []
        monkeypatch.setattr(
            GenericLLMClient,
            "_openrouter_chat_single",
            lambda self, *a, **k: dialled.append(a[0]),
        )
        client = self._client()
        client._validate_and_fallback_openrouter()

        assert dialled == []
        assert client.enabled is True, "a wall with a clock on it is not a misconfig"

    def test_a_429_mid_walk_stops_the_rotation(self, monkeypatch):
        monkeypatch.setattr(
            GenericLLMClient,
            "_free_models_cache",
            ["a/one", "b/two", "c/three", "d/four", "e/five"],
        )
        dialled = []

        def dial(self, model_id, *a, **k):
            dialled.append(model_id)
            GenericLLMClient._record_provider_usage(
                "openrouter", _Resp(429), "rate_limited"
            )
            return None

        monkeypatch.setattr(GenericLLMClient, "_openrouter_chat_single", dial)
        client = self._client()
        client._validate_and_fallback_openrouter()

        # The primary plus the one fallback that records the wall -- not six.
        assert len(dialled) == 2
        assert client._available is False
        assert client.enabled is True, "a rate limit must not disable the chain"

    def test_a_genuinely_broken_configuration_still_disables_the_adapter(
        self, monkeypatch
    ):
        """The latch is right for the case it was written for: every candidate
        failing while the account still reports headroom means the setup is
        wrong, not throttled."""
        monkeypatch.setattr(GenericLLMClient, "_free_models_cache", ["a/one"])
        monkeypatch.setattr(
            GenericLLMClient, "_openrouter_chat_single", lambda self, *a, **k: None
        )
        client = self._client()
        client._validate_and_fallback_openrouter()

        assert client._available is False
        assert client.enabled is False
