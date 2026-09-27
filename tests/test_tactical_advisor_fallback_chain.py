"""The Tactical Advisor falls back through Groq/Cerebras like NPC chat (#729).

``CombatLLMAdapter`` used to dispatch through ``GenericLLMClient._dispatch_chat``,
which routes ollama and openrouter only: an OpenRouter wall (the 50/day free
bucket, or a bench cascade) sent every beat to the deterministic scorer while a
Groq key sat unused in ``.env``. It now shares NPC chat's fallback chain through
``ProviderChainMixin`` -- one implementation, parametrised by env var names --
under the same consent rule: the chain is armed only when ``COMBAT_LLM_PROVIDER``
is named explicitly, and ``COMBAT_LLM_FALLBACK=0`` pins the named host.

The advisor answers once per beat, so the chain has a total budget
(``CombatLLMAdapter._CHAIN_BUDGET_SECONDS``): a stalled fallback host must not
hold the suggestion past it. No test here reaches the network --
``isolate_llm_class_state`` refuses every ``requests`` verb, and each transport
is replaced by a scripted fake.
"""

import time

import pytest
import requests
from unittest.mock import patch

import ai.llm_client as llm
from ai.combat_strategist import CombatLLMAdapter, CombatStrategist
from ai.llm_client import GenericLLMClient, NpcChatLLMAdapter
from tests.llm_doubles import Resp, isolate_llm_class_state  # noqa: F401

_GROQ_REPLY = (
    '{"suggestions": [{"move_name": "Slash", "target_id": null, '
    '"score": 90, "reasoning": "served by groq"}]}'
)


def _ctx():
    return {
        "player": {"hp": 80, "max_hp": 100, "fatigue": 80, "max_fatigue": 100,
                   "heat": 1.0, "name": "Jean"},
        "enemies": [],
        "history": [],
        "available_moves": [
            {"name": "Slash", "available": True, "category": "Offensive"},
            {"name": "Rest", "available": True, "category": "Miscellaneous"},
        ],
    }


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr(time, "monotonic", fake)
    return fake


def _total(timeout):
    return sum(timeout) if isinstance(timeout, tuple) else timeout


@pytest.fixture
def keys(monkeypatch):
    """OpenRouter and Groq credentialed; Cerebras and Ollama absent."""
    monkeypatch.setenv("COMBAT_LLM_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("CEREBRAS_API_KEY", "")
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    monkeypatch.delenv("COMBAT_LLM_FALLBACK", raising=False)
    monkeypatch.delenv("NPC_CHAT_LLM_FALLBACK", raising=False)


def _adapter():
    """A real CombatLLMAdapter, with OpenRouter discovery kept off the wire."""
    with patch.object(GenericLLMClient, "_discover_openrouter_model"), patch.object(
        GenericLLMClient, "_validate_and_fallback_openrouter"
    ):
        return CombatLLMAdapter()


def _openrouter_fails(adapter, calls, cost=0.0, clock=None):
    def dead(system_prompt, user_prompt, structured):
        calls.append("openrouter")
        if clock is not None:
            clock.now += cost
        return None

    adapter._openrouter_chat = dead


def _groq_posts(calls, reply=_GROQ_REPLY):
    def post(url, payload, headers, timeout, on_discarded=None):
        calls.append(("post", url, payload.get("model")))
        return Resp(200, {"choices": [{"message": {"content": reply}}]})

    return post


class TestTheChainServesTheAdvisor:
    def test_openrouter_failing_and_groq_serving_returns_groqs_suggestion(
        self, monkeypatch, keys
    ):
        monkeypatch.setenv("COMBAT_LLM_PROVIDER", "openrouter")
        adapter = _adapter()
        calls = []
        _openrouter_fails(adapter, calls)
        monkeypatch.setattr(llm, "_post_chat_completion", _groq_posts(calls))

        out = CombatStrategist(client=adapter).get_suggestions(_ctx())

        assert calls[0] == "openrouter"
        assert calls[1][1] == llm._OPENAI_COMPATIBLE_PROVIDERS["groq"]["url"]
        assert [s["reasoning"] for s in out] == ["served by groq"]

    def test_the_fallback_keeps_json_mode(self, monkeypatch, keys):
        monkeypatch.setenv("COMBAT_LLM_PROVIDER", "openrouter")
        adapter = _adapter()
        seen = {}
        _openrouter_fails(adapter, [])

        def post(url, payload, headers, timeout, on_discarded=None):
            seen.update(payload)
            return Resp(200, {"choices": [{"message": {"content": _GROQ_REPLY}}]})

        monkeypatch.setattr(llm, "_post_chat_completion", post)
        adapter.generate_structured("sys", "user")

        assert seen.get("response_format") == {"type": "json_object"}

    def test_a_named_groq_is_dispatchable_not_an_unknown_provider(self, monkeypatch, keys):
        """.env.example used to warn that naming groq made the advisor report
        "Unknown provider" and fall to the scorer every beat."""
        monkeypatch.setenv("COMBAT_LLM_PROVIDER", "groq")
        adapter = _adapter()
        calls = []
        monkeypatch.setattr(llm, "_post_chat_completion", _groq_posts(calls))

        assert adapter.available() is True
        assert adapter.generate_structured("sys", "user")["suggestions"][0]["reasoning"] == (
            "served by groq"
        )

    def test_every_provider_failing_still_ends_on_the_deterministic_scorer(
        self, monkeypatch, keys
    ):
        monkeypatch.setenv("COMBAT_LLM_PROVIDER", "openrouter")
        adapter = _adapter()
        _openrouter_fails(adapter, [])
        monkeypatch.setattr(llm, "_post_chat_completion", lambda *a, **k: Resp(503))
        strategist = CombatStrategist(client=adapter)

        out = strategist.get_suggestions(_ctx())

        assert out == strategist._get_fallback_suggestions(_ctx(), 1)


class TestConsent:
    def test_the_chain_is_not_armed_without_an_explicit_combat_provider(
        self, monkeypatch, keys
    ):
        """MYNX_LLM_PROVIDER routes the advisor but is not consent to fan out."""
        monkeypatch.delenv("COMBAT_LLM_PROVIDER", raising=False)
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "openrouter")
        adapter = _adapter()
        calls = []
        _openrouter_fails(adapter, calls)
        monkeypatch.setattr(llm, "_post_chat_completion", _groq_posts(calls))

        assert adapter.provider == "openrouter"
        assert adapter._provider_chain() == ["openrouter"]
        assert adapter.generate_structured("sys", "user") is None
        assert calls == ["openrouter"]

    def test_combat_fallback_zero_pins_the_named_provider(self, monkeypatch, keys):
        monkeypatch.setenv("COMBAT_LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("COMBAT_LLM_FALLBACK", "0")
        adapter = _adapter()
        calls = []
        _openrouter_fails(adapter, calls)
        monkeypatch.setattr(llm, "_post_chat_completion", _groq_posts(calls))

        assert adapter._provider_chain() == ["openrouter"]
        assert adapter.generate_structured("sys", "user") is None
        assert calls == ["openrouter"]

    def test_the_two_features_read_their_own_fallback_setting(self, monkeypatch, keys):
        """Each adapter's opt-out is its own: pinning chat must not pin combat,
        and pinning combat must not pin chat."""
        monkeypatch.setenv("COMBAT_LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("NPC_CHAT_LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")

        monkeypatch.setenv("NPC_CHAT_LLM_FALLBACK", "0")
        assert _adapter()._provider_chain() == ["openrouter", "groq"]
        assert NpcChatLLMAdapter()._provider_chain() == ["openrouter"]

        monkeypatch.delenv("NPC_CHAT_LLM_FALLBACK")
        monkeypatch.setenv("COMBAT_LLM_FALLBACK", "0")
        assert _adapter()._provider_chain() == ["openrouter"]
        assert NpcChatLLMAdapter()._provider_chain() == ["openrouter", "groq"]


class TestTheBeatBudget:
    def test_a_stalled_fallback_cannot_hold_the_beat_past_the_budget(
        self, monkeypatch, keys, clock
    ):
        """OpenRouter burns most of the budget, then Groq stalls for as long as
        its timeout lets it. Unbounded, Groq's nominal call alone would carry
        the beat past the budget; bounded, it gets only what is left."""
        monkeypatch.setenv("COMBAT_LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("CEREBRAS_API_KEY", "c")
        adapter = _adapter()
        budget = CombatLLMAdapter._CHAIN_BUDGET_SECONDS
        start = clock.now
        dialled = []
        _openrouter_fails(adapter, dialled, cost=budget - 3.0, clock=clock)

        def stall(url, payload, headers, timeout, on_discarded=None):
            dialled.append(url)
            clock.now += _total(timeout)
            raise requests.exceptions.ReadTimeout("stalled")

        monkeypatch.setattr(llm, "_post_chat_completion", stall)

        assert adapter.generate_structured("sys", "user") is None
        assert clock.now - start <= budget + 1e-6
        assert len(dialled) >= 2, "groq was never tried"

    def test_nothing_is_started_once_the_budget_is_spent(self, monkeypatch, keys, clock):
        monkeypatch.setenv("COMBAT_LLM_PROVIDER", "openrouter")
        adapter = _adapter()
        dialled = []
        _openrouter_fails(
            adapter, dialled, cost=CombatLLMAdapter._CHAIN_BUDGET_SECONDS, clock=clock
        )
        monkeypatch.setattr(llm, "_post_chat_completion", _groq_posts(dialled))

        assert adapter.generate_structured("sys", "user") is None
        assert dialled == ["openrouter"]


class TestOneImplementation:
    def test_chat_and_combat_share_the_chain_rather_than_copy_it(self):
        from ai.llm_client import ProviderChainMixin

        for name in ("_provider_chain", "_call_openai_compatible", "available"):
            impl = ProviderChainMixin.__dict__[name]
            assert name not in NpcChatLLMAdapter.__dict__, name
            assert name not in CombatLLMAdapter.__dict__ or name == "available", name
            assert getattr(NpcChatLLMAdapter, name) is getattr(ProviderChainMixin, name), impl
