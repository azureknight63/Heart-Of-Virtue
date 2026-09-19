"""A chat turn is bounded server-side, end to end (#618 scrub).

The turn deadline gated only whether a new provider STAGE may open; each stage
then walked the whole provider chain (OpenRouter's rotation, then every other
provider) with no clock at all, and generic NPCs generated their personality
before the deadline was even set. A turn could run well past the 45s client
deadline, and the Procfile's single sync gunicorn worker (30s timeout, sessions
in memory) is killed by anything over 30s -- taking every player's session
with it.

Maintainer decisions (2026-09-19): bound the turn server-side, keep it under
~25s, and size the client deadline from the engine's budget. So:

* the deadline reaches the adapter (``bounded_by``), which clips every network
  call to what the turn has left and stops walking the chain once it is spent;
* ``_round_timeout()`` stays NOMINAL -- the stage gate sizes a stage by it, and
  a clipped value would refuse every stage;
* personality generation runs inside the same budget;
* the budget is capped at ``_TURN_CEILING_SECONDS`` whatever the per-call
  timeout is configured to.
"""

import re
import time
from pathlib import Path

import pytest

import src.npc._chat_llm as chat_llm
from ai.llm_client import NpcChatLLMAdapter
from tests._gs_fixtures import live_world
from tests._npc_fixtures import ScriptedAdapter, ready_npc

_ROOT = Path(__file__).resolve().parent.parent


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


def _adapter(chain):
    """An adapter with a scripted chain and no environment behind it."""
    adapter = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
    adapter.enabled = True
    adapter.provider = chain[0]
    adapter.model = "test-model"
    adapter._provider_chain = lambda: list(chain)
    return adapter


def _wire(adapter, clock, calls, openrouter_cost):
    def openrouter(*_args):
        calls.append("openrouter")
        clock.now += openrouter_cost
        return None

    def compatible(provider, *_args):
        calls.append(provider)
        return '{"ok": 1}'

    adapter._call_openrouter = openrouter
    adapter._call_openai_compatible = compatible


def test_the_chain_walk_stops_once_the_turn_budget_is_spent(clock):
    adapter = _adapter(["openrouter", "groq"])
    calls = []
    _wire(adapter, clock, calls, openrouter_cost=7.0)

    with adapter.bounded_by(clock.now + 5.0):
        assert adapter._call_llm("system", "user") is None

    assert calls == ["openrouter"], "the next provider was dialled after the budget ran out"


def test_without_a_budget_the_chain_walks_as_before(clock):
    """Control: outside a turn (tests, other callers) nothing changes."""
    adapter = _adapter(["openrouter", "groq"])
    calls = []
    _wire(adapter, clock, calls, openrouter_cost=7.0)

    assert adapter._call_llm("system", "user") == '{"ok": 1}'
    assert calls == ["openrouter", "groq"]


def test_a_call_timeout_is_clipped_to_what_the_turn_has_left(clock, monkeypatch):
    monkeypatch.setenv("NPC_CHAT_LLM_TIMEOUT", "6")
    adapter = _adapter(["openrouter"])

    with adapter.bounded_by(clock.now + 2.5):
        assert adapter._call_timeout() == pytest.approx(2.5)
        # Nominal, not clipped: the stage gate sizes a stage by this, and a
        # clipped value would make every remaining stage look unaffordable.
        assert adapter._round_timeout() == 6.0
    assert adapter._call_timeout() == 6.0


def test_the_budget_is_released_when_the_turn_ends(clock):
    adapter = _adapter(["openrouter"])
    with adapter.bounded_by(clock.now - 1.0):
        pass
    assert adapter._call_timeout() == adapter._round_timeout()


def test_the_turn_deadline_is_capped_whatever_the_call_timeout(clock):
    class _WideAdapter:
        @staticmethod
        def _round_timeout():
            return 10.0  # an operator-raised NPC_CHAT_LLM_TIMEOUT

    deadline = chat_llm._turn_deadline(_WideAdapter())

    assert deadline - clock.now == pytest.approx(chat_llm._TURN_CEILING_SECONDS)


class _BudgetAwareAdapter(ScriptedAdapter):
    """A scripted adapter that records what ran inside the turn's budget."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.budget = None
        self.personality_budget = "never called"

    def bounded_by(self, deadline):
        adapter = self

        class _Scope:
            def __enter__(self):
                adapter.budget = deadline

            def __exit__(self, *exc):
                adapter.budget = None
                return False

        return _Scope()

    def generate_personality(self, _class_name):
        self.personality_budget = self.budget
        return {"given_name": "Tal", "voice": "methodical"}


@pytest.mark.parametrize("entry", ["chat_open", "chat_respond"])
def test_personality_generation_spends_the_same_budget(entry):
    """``_ensure_personality`` made a whole chain walk BEFORE the deadline was
    set, so a generic NPC's first turn could run a full turn past it."""
    adapter = _BudgetAwareAdapter()
    npc = ready_npc(adapter, _chat_char_config=None, _chat_personality=None)
    player = live_world()[0]

    if entry == "chat_open":
        npc.chat_open(player)
    else:
        npc.chat_respond(player, "Who are you?", "neutral")

    assert isinstance(adapter.personality_budget, float), adapter.personality_budget
    assert adapter.budget is None, "the budget outlived the turn"


def _procfile_worker_timeout():
    """gunicorn's worker timeout as the Procfile runs it (default 30s)."""
    procfile = (_ROOT / "Procfile").read_text(encoding="utf-8")
    match = re.search(r"--timeout[ =](\d+)", procfile)
    return int(match.group(1)) if match else 30


def test_a_turn_fits_inside_the_production_worker_timeout():
    """The Procfile's single sync worker is killed past its timeout, and with
    it every in-memory session. A turn may overrun its deadline by at most one
    clipped call, so budget plus one nominal call must stay inside."""
    worst = chat_llm._TURN_CEILING_SECONDS + chat_llm._DEFAULT_ROUND_TIMEOUT_SECONDS
    assert worst < _procfile_worker_timeout()


def test_the_client_waits_at_least_as_long_as_a_turn_can_run():
    """``NPC_CHAT_TIMEOUT_MS`` is derived here from the engine's own numbers,
    not restated: a client that gives up first abandons a turn the server
    still commits."""
    js = (_ROOT / "frontend" / "src" / "api" / "npcChat.js").read_text(encoding="utf-8")
    match = re.search(r"export const NPC_CHAT_TIMEOUT_MS = ([\d_]+)", js)
    assert match is not None, "NPC_CHAT_TIMEOUT_MS is no longer an exported number literal"
    client_seconds = int(match.group(1).replace("_", "")) / 1000
    worst = chat_llm._TURN_CEILING_SECONDS + chat_llm._DEFAULT_ROUND_TIMEOUT_SECONDS
    assert client_seconds >= worst
    assert client_seconds < _procfile_worker_timeout(), (
        "past the worker timeout the client never gets to time out: the worker "
        "is killed first"
    )
