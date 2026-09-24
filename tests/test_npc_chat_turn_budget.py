"""A chat turn is bounded server-side, end to end (#618 scrub).

The turn deadline gated only whether a new provider STAGE may open; each stage
then walked the whole provider chain (OpenRouter's rotation, then every other
provider) with no clock at all, and generic NPCs generated their personality
before the deadline was even set. A turn could run well past the 45s client
deadline, with a player watching a spinner the whole time.

The budget was first sized against the Procfile: one sync gunicorn worker,
30s, sessions in memory, so an overrun killed the worker and every session.
Production runs an eventlet worker with --timeout 120 instead
(deploy/heart-of-virtue.service, read from the server 2026-09-19), where a
long request holds a greenlet and the timeout bounds a STALLED worker. The
numbers stayed -- a player should not wait half a minute for one reply -- and
these tests now read the unit rather than the Procfile.

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


def _total(timeout):
    """Wall-clock bound of a ``requests`` timeout: a (connect, read) pair
    applies each phase in turn, so the pair costs the sum."""
    return sum(timeout) if isinstance(timeout, tuple) else timeout


def test_a_call_timeout_is_clipped_to_what_the_turn_has_left(clock, monkeypatch):
    monkeypatch.setenv("NPC_CHAT_LLM_TIMEOUT", "6")
    adapter = _adapter(["openrouter"])

    with adapter.bounded_by(clock.now + 2.5):
        assert _total(adapter._call_timeout()) == pytest.approx(2.5)
        # Nominal, not clipped: the stage gate sizes a stage by this, and a
        # clipped value would make every remaining stage look unaffordable.
        assert adapter._round_timeout() == 6.0
    assert adapter._call_timeout() == 6.0


@pytest.mark.parametrize("left", [0.5, 2.5, 6.0, 9.0, 21.0])
def test_connect_and_read_together_fit_what_the_turn_has_left(
    clock, monkeypatch, left
):
    """#637: ``requests`` applies a float timeout to EACH phase -- connect,
    then read -- so ``timeout=left`` let one call run to twice what the turn
    had left. Inside a turn the call gets a (connect, read) pair instead."""
    monkeypatch.setenv("NPC_CHAT_LLM_TIMEOUT", "6")
    adapter = _adapter(["openrouter"])

    with adapter.bounded_by(clock.now + left):
        timeout = adapter._call_timeout()

    assert isinstance(timeout, tuple) and len(timeout) == 2, timeout
    connect, read = timeout
    assert connect > 0 and read > 0
    assert connect + read <= left + 1e-9
    assert read <= 6.0


def test_a_turn_with_room_keeps_the_nominal_read(clock, monkeypatch):
    """Splitting must not shorten a healthy call: with the turn's budget
    ahead of it, the read phase is still the whole nominal timeout."""
    monkeypatch.setenv("NPC_CHAT_LLM_TIMEOUT", "6")
    adapter = _adapter(["openrouter"])

    with adapter.bounded_by(clock.now + 21.0):
        assert adapter._call_timeout()[1] == 6.0


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


#: The unit this repo mirrors from the server (read 2026-09-19). Production
#: runs gunicorn from systemd, NOT the Procfile: an eventlet worker with
#: --timeout 120, where the Procfile said sync and the 30s default. The budget
#: was sized against the Procfile, and these tests were pinned to it -- a guard
#: reading a file production ignores.
_UNIT = _ROOT / "deploy" / "heart-of-virtue.service"


def _gunicorn_flags(text, source):
    """``{worker_class, workers, timeout}`` from a gunicorn command line.

    Read rather than asserted, so one spelling of the process model serves
    every test here. Absent flags fall back to gunicorn's own defaults.
    """
    joined = " ".join(text.replace("\\\n", " ").split())
    match = re.search(r"gunicorn (.*?) ?wsgi:app", joined)
    assert match, f"no gunicorn command found in {source}"
    argv = match.group(1)
    timeout = re.search(r"--timeout[ =](\d+)", argv)
    worker_class = re.search(r"--worker-class[ =](\S+)", argv)
    workers = re.search(r"(?:-w|--workers)[ =](\d+)", argv)
    return {
        "worker_class": worker_class.group(1) if worker_class else "sync",
        "workers": int(workers.group(1)) if workers else 1,
        "timeout": int(timeout.group(1)) if timeout else 30,
    }


def _production_gunicorn():
    return _gunicorn_flags(_UNIT.read_text(encoding="utf-8"), _UNIT.name)


def test_the_procfile_says_what_the_unit_says():
    """Two files describing one process model is how the budget came to be
    sized against a worker production does not run. The Procfile is kept as a
    convenience copy of the unit's command, so it has to agree with it."""
    unit = _production_gunicorn()
    procfile = _gunicorn_flags((_ROOT / "Procfile").read_text(encoding="utf-8"), "Procfile")

    assert unit["timeout"] > 0 and unit["worker_class"], "read nothing off the unit"
    assert procfile == unit, (
        "the Procfile and deploy/heart-of-virtue.service disagree about how "
        f"production runs: {procfile} vs {unit}"
    )


def test_the_worker_class_production_runs_is_installed_by_requirements():
    """``--worker-class eventlet`` needs eventlet in the venv, or gunicorn
    refuses to boot. It was installed on the server by hand and pinned
    nowhere, so a rebuilt venv would have taken the API down."""
    worker_class = _production_gunicorn()["worker_class"]
    requirements = (_ROOT / "requirements-api.txt").read_text(encoding="utf-8")

    if worker_class in {"eventlet", "gevent"}:
        assert re.search(rf"^{worker_class}\b", requirements, re.M), (
            f"production runs the {worker_class} worker, which "
            "requirements-api.txt does not install"
        )


#: Worker classes gunicorn has dropped, and the release that dropped them.
#: An external fact, so it is written down rather than derived: gunicorn
#: 25.x's ``workers/geventlet.py`` says the eventlet worker "will be removed in
#: Gunicorn 26.0", and 26.x's ``SUPPORTED_WORKERS`` has no ``eventlet`` (#653).
_WORKER_REMOVED_IN = {"eventlet": "26.0"}

#: The worker's own dependency floor across the gunicorn releases the
#: requirements admit: gunicorn 24.x and 25.x refuse to start the eventlet
#: worker below eventlet 0.40.3 (``geventlet.py`` raises RuntimeError, and the
#: ``[eventlet]`` extra declares ``eventlet>=0.40.3``).
_WORKER_NEEDS = {"eventlet": ("eventlet", "0.40.3")}


def _requirement(name):
    """The ``packaging`` Requirement for ``name`` in requirements-api.txt."""
    from packaging.requirements import Requirement

    text = (_ROOT / "requirements-api.txt").read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and Requirement(line).name.lower() == name:
            return Requirement(line)
    pytest.fail(f"requirements-api.txt does not declare {name}")


def test_requirements_cannot_install_a_gunicorn_without_the_units_worker():
    """#653: gunicorn 26.0 removed the eventlet worker while the requirements
    said ``gunicorn>=20.1``, so a rebuilt venv installed a gunicorn that cannot
    boot the worker class the unit names. The class is read off the unit, so
    switching the unit to another worker re-aims this check."""
    worker_class = _production_gunicorn()["worker_class"]
    removed_in = _WORKER_REMOVED_IN.get(worker_class)
    if removed_in is None:
        return
    spec = _requirement("gunicorn").specifier
    major = int(removed_in.split(".")[0])
    for probe in (removed_in, f"{major}.2.0", f"{major + 1}.0", "99.0"):
        assert not spec.contains(probe), (
            f"requirements-api.txt admits gunicorn {probe}, which has no "
            f"{worker_class} worker (removed in {removed_in}); "
            f"{_UNIT.name} runs --worker-class {worker_class}"
        )


def test_the_worker_dependency_meets_the_floor_gunicorn_enforces():
    """``eventlet>=0.40`` admitted 0.40.0-0.40.2, which every gunicorn from
    24.0 on refuses to start its eventlet worker with."""
    from packaging.version import Version

    worker_class = _production_gunicorn()["worker_class"]
    if worker_class not in _WORKER_NEEDS:
        return
    package, floor = _WORKER_NEEDS[worker_class]
    v = Version(floor)
    just_below = f"{v.major}.{v.minor}.{v.micro - 1}"
    assert not _requirement(package).specifier.contains(just_below), (
        f"requirements-api.txt admits {package} {just_below}; gunicorn's "
        f"{worker_class} worker needs {floor} or later"
    )


def _widest_call():
    """The longest one provider call may be, however it is configured.

    The adapter clamps NPC_CHAT_LLM_TIMEOUT (#637), so the worst-case sums
    below are taken against that clamp -- not the 6s default, which an
    operator can raise.
    """
    import ai.llm_client as llm

    return llm._ROUND_TIMEOUT_CEILING_SECONDS


def _client_timeout_seconds():
    js = (_ROOT / "frontend" / "src" / "api" / "npcChat.js").read_text(encoding="utf-8")
    match = re.search(r"export const NPC_CHAT_TIMEOUT_MS = ([\d_]+)", js)
    assert match is not None, "NPC_CHAT_TIMEOUT_MS is no longer an exported number literal"
    return int(match.group(1).replace("_", "")) / 1000


@pytest.mark.parametrize("configured", ["6", "10", "60", "1e9", "inf", "nan"])
def test_a_raised_call_timeout_still_ends_inside_the_client_deadline(
    configured, monkeypatch
):
    """#637: ``_round_timeout`` had no upper bound, so NPC_CHAT_LLM_TIMEOUT=10
    made the worst turn 21s + 10s -- past the client's 28s, which then gave up
    on a turn the server still went on to commit."""
    monkeypatch.setenv("NPC_CHAT_LLM_TIMEOUT", configured)
    worst = chat_llm._TURN_CEILING_SECONDS + NpcChatLLMAdapter._round_timeout()
    assert worst <= _client_timeout_seconds()


def test_a_turn_fits_inside_the_production_worker_timeout():
    """A turn must not outlive the worker.

    For the eventlet worker production runs, ``--timeout`` is a LIVENESS
    heartbeat rather than a per-request deadline: a long request does not kill
    the worker, but one that blocks the event loop does. For a sync worker it
    is a hard per-request kill, and with sessions in memory that kill takes
    every player's game with it. One bound covers both, so switching the unit
    back to sync cannot quietly invalidate the budget.

    Inside a turn each call's (connect, read) timeout pair is sized to fit
    what the turn has left, but ``requests``' read timeout bounds the gap
    between bytes, not the whole body, so a trickling response can still run
    past the deadline. The margin kept for that is one whole call at the
    clamp: budget plus the widest call must stay inside.
    """
    worst = chat_llm._TURN_CEILING_SECONDS + _widest_call()
    assert worst < _production_gunicorn()["timeout"]


def test_the_client_waits_at_least_as_long_as_a_turn_can_run():
    """``NPC_CHAT_TIMEOUT_MS`` is derived here from the engine's own numbers,
    not restated: a client that gives up first abandons a turn the server
    still commits."""
    client_seconds = _client_timeout_seconds()
    worst = chat_llm._TURN_CEILING_SECONDS + _widest_call()
    assert client_seconds >= worst
    assert client_seconds < _production_gunicorn()["timeout"], (
        "past the worker timeout the client never gets to time out: the worker "
        "is gone first"
    )


# ---------------------------------------------------------------------------
# Re-review of the budget (#618 scrub, round 2)
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_bench():
    """Model benches are class-level and shared by every client; start and
    end clean so a bench planted here cannot leak into another test."""
    from ai.llm_client import GenericLLMClient

    GenericLLMClient.reset_class_state()
    yield
    GenericLLMClient.reset_class_state()


def _openrouter_ready(adapter, monkeypatch, outcome):
    """Wire ``_call_openrouter`` to one candidate whose POST does ``outcome``."""
    import ai.llm_client as llm

    adapter._openrouter_api_key = "test-key"
    adapter._get_openrouter_model = lambda: "vendor/model:free"
    adapter._openrouter_candidates = lambda primary: [primary]
    adapter._build_openrouter_headers = lambda: {}
    adapter._chat_payload = lambda **_kw: {"model": "vendor/model:free"}
    monkeypatch.setattr(llm, "_post_chat_completion", outcome)


def test_a_clipped_call_that_times_out_does_not_bench_the_model(
    clock, monkeypatch, fresh_bench
):
    """Clipping is the turn running out, not the model failing. Benching on it
    took healthy models out of the rotation for ten minutes -- for every
    player, and for the combat and Mynx clients that share the bench."""
    import requests

    monkeypatch.setenv("NPC_CHAT_LLM_TIMEOUT", "6")
    adapter = _adapter(["openrouter"])

    def clipped_out(*_args, **_kwargs):
        raise requests.exceptions.ReadTimeout("read timed out (3.0s)")

    _openrouter_ready(adapter, monkeypatch, clipped_out)
    with adapter.bounded_by(clock.now + 3.0):
        assert adapter._call_openrouter("system", "user", 64, 0.5) is None

    assert not adapter._is_model_failed("vendor/model:free")


def test_a_full_length_timeout_still_benches_the_model(
    clock, monkeypatch, fresh_bench
):
    """Control: a model that cannot answer inside its NOMINAL timeout is slow,
    and the rotation should stop dialling it."""
    import requests

    monkeypatch.setenv("NPC_CHAT_LLM_TIMEOUT", "6")
    adapter = _adapter(["openrouter"])

    def timed_out(*_args, **_kwargs):
        raise requests.exceptions.ReadTimeout("read timed out (6.0s)")

    _openrouter_ready(adapter, monkeypatch, timed_out)
    assert adapter._call_openrouter("system", "user", 64, 0.5) is None

    assert adapter._is_model_failed("vendor/model:free")


class _Response:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


def test_the_400_retry_is_held_to_what_the_turn_has_left(clock, monkeypatch):
    """``_post_chat_completion`` retried with the timeout it computed before
    the first POST, so a retry could end a whole clipped timeout past the
    deadline -- past the worker timeout with a raised NPC_CHAT_LLM_TIMEOUT."""
    import ai.llm_client as llm

    sent = []

    def post(_url, json, headers, timeout):
        sent.append(timeout)
        clock.now += 4.0
        return _Response(400, "reasoning is mandatory for this endpoint")

    monkeypatch.setattr(llm.requests, "post", post)
    adapter = _adapter(["openrouter"])
    with adapter.bounded_by(clock.now + 5.0):
        llm._post_chat_completion("url", {"model": "m", "reasoning": {}}, {}, 5.0)

    assert sent[0] == 5.0
    assert _total(sent[1]) == pytest.approx(1.0)


def test_the_400_retry_is_not_sent_once_the_turn_is_spent(clock, monkeypatch):
    import ai.llm_client as llm

    sent = []

    def post(_url, json, headers, timeout):
        sent.append(timeout)
        clock.now += 5.0
        return _Response(400, "reasoning is mandatory for this endpoint")

    monkeypatch.setattr(llm.requests, "post", post)
    adapter = _adapter(["openrouter"])
    with adapter.bounded_by(clock.now + 5.2):
        response = llm._post_chat_completion("url", {"model": "m", "reasoning": {}}, {}, 5.2)

    assert sent == [5.2], "a retry was dialled with no turn left to run it"
    assert response.status_code == 400


def test_an_inner_scope_never_widens_the_turn(clock, monkeypatch):
    """``bounded_by`` restores on exit, so scopes nest -- but an inner scope
    with a later deadline, or none, used to REPLACE the outer one."""
    monkeypatch.setenv("NPC_CHAT_LLM_TIMEOUT", "6")
    adapter = _adapter(["openrouter"])

    with adapter.bounded_by(clock.now + 2.0):
        with adapter.bounded_by(clock.now + 10.0):
            assert _total(adapter._call_timeout()) == pytest.approx(2.0)
        with adapter.bounded_by(None):
            assert _total(adapter._call_timeout()) == pytest.approx(2.0)
        with adapter.bounded_by(clock.now + 1.0):
            assert _total(adapter._call_timeout()) == pytest.approx(1.0)
        assert _total(adapter._call_timeout()) == pytest.approx(2.0)


def test_the_turn_clock_starts_before_the_adapter_is_built(clock):
    """A cold ``get_instance()`` discovers and validates models on the request
    path. That time is the turn's too: the deadline is counted from before it,
    not after."""

    class _Adapter:
        @staticmethod
        def _round_timeout():
            return chat_llm._DEFAULT_ROUND_TIMEOUT_SECONDS

    class _ColdNpc:
        def _get_adapter(self):
            clock.now += 15.0  # model discovery on a cold singleton
            return _Adapter()

    started = clock.now
    deadline, _scope = chat_llm.ConversationalNPCMixin._turn_budget(_ColdNpc())

    assert deadline == pytest.approx(started + chat_llm._TURN_CEILING_SECONDS)
