"""Structured-output capability filtering and JSON mode for the chat path.

Every NPC chat call parses its response as JSON, but model selection ranked on
price, modality, and intelligence alone — never on whether the model can be
pinned to JSON output at all. That put `nvidia/nemotron-3.5-lightning:free`
(which advertises only `reasoning`/`include_reasoning`, no `response_format`)
at the top of the ranked list, where it spent its whole completion budget
narrating deliberation in plain content and got truncated mid-JSON. Parsing
failed 10/10 and every chat turn silently fell back to canned dialogue.

Two changes under test:

1. `_rank_models` prefers models that advertise structured output, and drops
   the ones that cannot — degrading to the unfiltered list rather than to
   nothing, so a shrinking free catalogue can never leave the game mute.
2. The chat payload actually asks for JSON (`response_format`), with a 400
   retry that strips it — the same escape hatch the reasoning block already
   has, for a model whose advertised capability turns out to be stale.
"""

from datetime import datetime, timedelta, timezone

import pytest

import ai.llm_client as llm
from ai.llm_client import GenericLLMClient, NpcChatLLMAdapter


@pytest.fixture(autouse=True)
def _reset_llm_class_state(tmp_path, monkeypatch):
    """Isolate class-level shared state and the disk cache per test.

    The same fixture ``tests/test_llm_client_coverage.py`` uses. This file had
    none: nine of its classes hand-rolled a ``setup_method``/``teardown_method``
    pair, three more called ``reset_class_state()`` inline in one test body, and
    the rest -- ``TestMergeUsage`` among them -- reset nothing at all and left
    ``_provider_usage["openrouter"]`` sitting at three requests for whichever
    file the xdist worker picked up next. ``TestProviderChain`` and
    ``TestCallLlmFallsThrough`` passed only because they sit ABOVE
    ``TestProviderSaturation`` in file order, which is not a property a test
    file should depend on.
    """
    GenericLLMClient.reset_class_state()
    GenericLLMClient._nightly_refresh_started = False
    monkeypatch.setattr(llm, "_MODEL_CACHE_FILE", str(tmp_path / ".model_cache.json"))
    # Clean baseline; individual tests override as needed.
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


def _model(mid, params=None, intelligence=None, created=1):
    m = {
        "id": mid,
        "pricing": {"prompt": "0", "completion": "0"},
        "created": created,
    }
    if params is not None:
        m["supported_parameters"] = params
    if intelligence is not None:
        m["benchmarks"] = {"artificial_analysis": {"intelligence_index": intelligence}}
    return m


# ---------------------------------------------------------------------------
# The capability predicate
# ---------------------------------------------------------------------------


class TestSupportsStructuredOutput:
    def test_response_format_counts(self):
        assert GenericLLMClient._supports_structured_output(
            _model("m", ["reasoning", "response_format"])
        )

    def test_structured_outputs_counts(self):
        assert GenericLLMClient._supports_structured_output(
            _model("m", ["structured_outputs"])
        )

    def test_reasoning_only_does_not_count(self):
        assert not GenericLLMClient._supports_structured_output(
            _model("m", ["reasoning", "include_reasoning"])
        )

    def test_missing_parameters_does_not_count(self):
        assert not GenericLLMClient._supports_structured_output(_model("m"))

    def test_junk_shape_is_not_fatal(self):
        assert not GenericLLMClient._supports_structured_output({})
        assert not GenericLLMClient._supports_structured_output(
            {"id": "m", "supported_parameters": "response_format"}
        )


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


class TestStructuredCapabilityFilter:
    def test_incapable_model_is_dropped(self):
        models = [
            _model("chatty", ["reasoning"]),
            _model("json-capable", ["response_format"]),
        ]
        assert GenericLLMClient._rank_models(models) == ["json-capable"]

    def test_incapable_model_is_dropped_even_when_smarter(self):
        """The real case: the highest-ranked free model could not do JSON."""
        models = [
            _model("chatty-genius", ["reasoning"], intelligence=90.0),
            _model("json-plodder", ["response_format"], intelligence=20.0),
        ]
        assert GenericLLMClient._rank_models(models) == ["json-plodder"]

    def test_ranking_order_survives_inside_the_capable_set(self):
        models = [
            _model("dumber", ["response_format"], intelligence=20.0),
            _model("smarter", ["structured_outputs"], intelligence=52.6),
            _model("chatty", ["reasoning"], intelligence=99.0),
        ]
        assert GenericLLMClient._rank_models(models) == ["smarter", "dumber"]

    def test_degrades_to_unfiltered_when_nothing_is_capable(self):
        """A shrinking catalogue must never leave the game with no models."""
        models = [
            _model("chatty-a", ["reasoning"], intelligence=50.0),
            _model("chatty-b", ["reasoning"], intelligence=10.0),
        ]
        assert GenericLLMClient._rank_models(models) == ["chatty-a", "chatty-b"]

    def test_legacy_entries_without_capability_data_still_rank(self):
        """Catalogue rows that predate supported_parameters are not punished."""
        models = [_model("old-a", created=100), _model("old-b", created=10)]
        assert GenericLLMClient._rank_models(models) == ["old-a", "old-b"]

    def test_paid_models_still_excluded(self):
        models = [
            {
                "id": "paid",
                "pricing": {"prompt": "0.5", "completion": "0.5"},
                "supported_parameters": ["response_format"],
            },
            _model("free", ["response_format"]),
        ]
        assert GenericLLMClient._rank_models(models) == ["free"]


# ---------------------------------------------------------------------------
# JSON mode on the wire
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {
            "choices": [{"message": {"content": '{"npc_text": "Fine."}'}}]
        }
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %s" % self.status_code)


def _adapter():
    a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
    a.enabled = True
    a.provider = "openrouter"
    a.model = "json-capable"
    a._openrouter_api_key = "test-key"
    a._openrouter_site = ""
    a._openrouter_site_title = ""
    return a


class TestChatPayloadRequestsJson:
    def test_response_format_is_sent(self, monkeypatch):
        seen = {}

        def fake_post(url, payload, headers, timeout):
            seen.update(payload)
            return _Resp()

        monkeypatch.setattr(llm, "_post_chat_completion", fake_post)
        monkeypatch.setattr(GenericLLMClient, "_free_models_cache", [])
        out = _adapter()._call_openrouter("sys", "user", 500, 0.7)

        assert out == '{"npc_text": "Fine."}'
        assert seen.get("response_format") == {"type": "json_object"}


# ---------------------------------------------------------------------------
# The 400 escape hatch
# ---------------------------------------------------------------------------


class TestPostChatCompletionRetry:
    def _payload(self):
        return {
            "model": "m",
            "messages": [],
            "response_format": {"type": "json_object"},
            "reasoning": {"effort": "low"},
        }

    def test_retries_without_response_format_when_rejected(self, monkeypatch):
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append(json)
            if len(calls) == 1:
                return _Resp(400, text="response_format is not supported")
            return _Resp()

        monkeypatch.setattr(llm.requests, "post", fake_post)
        resp = llm._post_chat_completion("u", self._payload(), {}, 5)

        assert resp.status_code == 200
        assert len(calls) == 2
        assert "response_format" not in calls[1]
        # The reasoning block was not implicated, so it survives.
        assert "reasoning" in calls[1]

    def test_still_retries_without_reasoning_when_rejected(self, monkeypatch):
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append(json)
            if len(calls) == 1:
                return _Resp(400, text="Reasoning is mandatory for this endpoint")
            return _Resp()

        monkeypatch.setattr(llm.requests, "post", fake_post)
        resp = llm._post_chat_completion("u", self._payload(), {}, 5)

        assert resp.status_code == 200
        assert len(calls) == 2
        assert "reasoning" not in calls[1]
        assert "response_format" in calls[1]

    def test_drops_both_when_both_are_implicated(self, monkeypatch):
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append(json)
            if len(calls) == 1:
                return _Resp(
                    400, text="reasoning and response_format are not supported"
                )
            return _Resp()

        monkeypatch.setattr(llm.requests, "post", fake_post)
        llm._post_chat_completion("u", self._payload(), {}, 5)

        assert "reasoning" not in calls[1]
        assert "response_format" not in calls[1]

    def test_no_retry_when_the_400_blames_something_else(self, monkeypatch):
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append(json)
            return _Resp(400, text="reason: invalid model")

        monkeypatch.setattr(llm.requests, "post", fake_post)
        resp = llm._post_chat_completion("u", self._payload(), {}, 5)

        assert resp.status_code == 400
        assert len(calls) == 1

    def test_no_retry_on_success(self, monkeypatch):
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append(json)
            return _Resp()

        monkeypatch.setattr(llm.requests, "post", fake_post)
        llm._post_chat_completion("u", self._payload(), {}, 5)

        assert len(calls) == 1


# ---------------------------------------------------------------------------
# Ranking for THIS workload: a ~160-token JSON reply, not a reasoning problem
# ---------------------------------------------------------------------------


def _rmodel(mid, params=("response_format",), reasoning=None, intelligence=None, ctx=1000):
    m = {
        "id": mid,
        "pricing": {"prompt": "0", "completion": "0"},
        "created": 1,
        "context_length": ctx,
        "supported_parameters": list(params),
    }
    if reasoning is not None:
        m["reasoning"] = reasoning
    if intelligence is not None:
        m["benchmarks"] = {"artificial_analysis": {"intelligence_index": intelligence}}
    return m


class TestReasoningAwareRanking:
    """Reasoning models burn the completion budget narrating and truncate.

    The observed failure was a model spending ~675 tokens deliberating before
    starting a ~160-token answer and being cut off mid-JSON. OpenRouter
    advertises this per model, so rank on it: quiet models first, then
    reason-by-default, then reason-always.
    """

    def test_quiet_model_outranks_reason_by_default(self):
        models = [
            _rmodel("default-on", reasoning={"mandatory": False, "default_enabled": True}),
            _rmodel("quiet", reasoning={"mandatory": False}),
        ]
        assert GenericLLMClient._rank_models(models) == ["quiet", "default-on"]

    def test_mandatory_reasoning_ranks_last(self):
        models = [
            _rmodel("always-reasons", reasoning={"mandatory": True}),
            _rmodel("default-on", reasoning={"mandatory": False, "default_enabled": True}),
            _rmodel("quiet", reasoning={"mandatory": False}),
        ]
        assert GenericLLMClient._rank_models(models) == [
            "quiet",
            "default-on",
            "always-reasons",
        ]

    def test_reasoning_beats_intelligence(self):
        """The whole point: smarts no longer outrank finishing the answer."""
        models = [
            _rmodel("genius-that-rambles", reasoning={"mandatory": True}, intelligence=99.0),
            _rmodel("quiet-plodder", reasoning={"mandatory": False}, intelligence=10.0),
        ]
        assert GenericLLMClient._rank_models(models)[0] == "quiet-plodder"

    def test_intelligence_still_breaks_ties_within_a_reasoning_class(self):
        models = [
            _rmodel("dimmer", reasoning={"mandatory": False}, intelligence=20.0),
            _rmodel("brighter", reasoning={"mandatory": False}, intelligence=60.0),
        ]
        assert GenericLLMClient._rank_models(models) == ["brighter", "dimmer"]

    def test_absent_reasoning_metadata_is_treated_as_quiet(self):
        models = [
            _rmodel("unknown", reasoning=None),
            _rmodel("default-on", reasoning={"mandatory": False, "default_enabled": True}),
        ]
        assert GenericLLMClient._rank_models(models) == ["unknown", "default-on"]

    def test_null_reasoning_does_not_crash(self):
        models = [_rmodel("nullish")]
        models[0]["reasoning"] = None
        assert GenericLLMClient._rank_models(models) == ["nullish"]


# ---------------------------------------------------------------------------
# A model that cannot produce parseable output must take itself out of rotation
# ---------------------------------------------------------------------------


class TestUnparseablePenalty:
    """A pinned or top-ranked model returning garbage should self-correct.

    Rotation only triggers on transport failures (429/404/timeout). A model
    that answers HTTP 200 with prose where JSON was demanded looked like a
    success to every layer, so it stayed primary and every chat turn fell
    through to canned dialogue — indefinitely, and silently.
    """

    def _minutes_left(self, model_id):
        """Bench expiries are aware UTC (Sec-A#4), so this must be too --
        subtracting a naive ``datetime.now()`` from one raises TypeError."""
        from datetime import datetime, timezone

        expiry = GenericLLMClient._failed_models.get(model_id)
        assert expiry is not None, "model was not penalized at all"
        assert expiry.tzinfo is not None, "bench expiry must be timezone-aware"
        return (expiry - datetime.now(timezone.utc)).total_seconds() / 60.0

    def test_first_offence_is_a_short_penalty(self):
        GenericLLMClient._penalize_unparseable("chatty")
        assert 5 <= self._minutes_left("chatty") <= 60

    def test_repeat_offence_escalates_to_a_longer_penalty(self):
        GenericLLMClient._penalize_unparseable("chatty")
        first = self._minutes_left("chatty")
        GenericLLMClient._penalize_unparseable("chatty")
        assert self._minutes_left("chatty") > first

    def test_the_repeat_penalty_is_hours_not_the_rest_of_the_day(self):
        """S3: this bench is process-wide state shared by every player, and the
        output that trips it is shaped by whatever the player typed. At 720
        minutes two crafted turns took the primary free model out for everyone
        until the next morning, repeatably down the ranked list."""
        GenericLLMClient._penalize_unparseable("chatty")
        GenericLLMClient._penalize_unparseable("chatty")
        assert self._minutes_left("chatty") <= 4 * 60

    def test_strikes_decay_so_two_stumbles_hours_apart_are_not_a_repeat(self):
        """S3: the strike count used to be cleared only by a later parse
        success ON THAT MODEL. A model nothing happened to call again carried
        its strike for the life of the process and took the escalated penalty
        on its next stumble, however long afterwards."""
        GenericLLMClient._penalize_unparseable("chatty")
        # Age the strike past the decay window, and clear the first bench so
        # the next penalty's expiry is the one being measured.
        GenericLLMClient._unparseable_strike_at["chatty"] = (
            datetime.now(timezone.utc)
            - timedelta(minutes=llm._UNPARSEABLE_STRIKE_DECAY_MINUTES + 1)
        )
        GenericLLMClient._failed_models.pop("chatty", None)

        GenericLLMClient._penalize_unparseable("chatty")

        assert GenericLLMClient._unparseable_strikes["chatty"] == 1
        assert self._minutes_left("chatty") <= 60

    def test_strikes_inside_the_decay_window_still_escalate(self):
        GenericLLMClient._penalize_unparseable("chatty")
        GenericLLMClient._unparseable_strike_at["chatty"] = (
            datetime.now(timezone.utc)
            - timedelta(minutes=llm._UNPARSEABLE_STRIKE_DECAY_MINUTES - 1)
        )
        GenericLLMClient._penalize_unparseable("chatty")
        assert GenericLLMClient._unparseable_strikes["chatty"] == 2

    def test_a_good_response_clears_the_strike_count(self):
        GenericLLMClient._penalize_unparseable("flaky")
        assert GenericLLMClient._unparseable_strikes["flaky"] == 1
        GenericLLMClient._note_parse_success("flaky")
        assert "flaky" not in GenericLLMClient._unparseable_strikes
        # Only the bench expiry is cleared here, not the strike book, so the
        # next offence proves the count really was reset rather than merely
        # being wiped along with everything else.
        GenericLLMClient._failed_models.pop("flaky", None)
        GenericLLMClient._penalize_unparseable("flaky")
        # Back to a first offence, not an escalation.
        assert self._minutes_left("flaky") <= 60

    def test_penalized_model_is_skipped(self):
        GenericLLMClient._penalize_unparseable("chatty")
        assert GenericLLMClient()._is_model_failed("chatty") is True

    def test_no_served_model_is_not_fatal(self):
        GenericLLMClient._penalize_unparseable(None)
        GenericLLMClient._penalize_unparseable("")
        assert GenericLLMClient._failed_models == {}

    def test_reset_class_state_clears_strikes(self):
        GenericLLMClient._penalize_unparseable("chatty")
        assert GenericLLMClient._unparseable_strikes  # precondition
        GenericLLMClient.reset_class_state()
        assert GenericLLMClient._unparseable_strikes == {}


class TestAdapterPenalizesOnParseFailure:
    """The penalty must actually be wired to the chat call sites."""

    def _adapter_returning(self, raw):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "openrouter"
        a.model = "chatty"
        a._last_served_model = "chatty"
        a._call_llm = lambda *args, **kw: raw
        return a

    def test_generate_turn_penalizes_unparseable_output(self):
        adapter = self._adapter_returning("Here's a thinking process: 1. Analyze...")
        assert adapter.generate_turn("sys", [], is_opening=True) is None
        assert "chatty" in GenericLLMClient._failed_models

    def test_revise_turn_penalizes_unparseable_output(self):
        adapter = self._adapter_returning("Let me think about this instead.")
        assert adapter.revise_turn("sys", "line", [], "guidance") is None
        assert "chatty" in GenericLLMClient._failed_models

    def test_good_output_is_not_penalized(self):
        adapter = self._adapter_returning('{"npc_text": "The river is high."}')
        assert adapter.generate_turn("sys", [], is_opening=True) is not None
        assert GenericLLMClient._failed_models == {}


# ---------------------------------------------------------------------------
# Provider fallback chain
# ---------------------------------------------------------------------------


class TestProviderChain:
    """One provider's quota wall must not silence the game for the day.

    OpenRouter's free tier is 50 requests/day account-wide: once it is spent,
    every model 429s and the old flat `if provider == ...` dispatch had nowhere
    to go, so chat fell back to canned dialogue until UTC midnight. Groq and
    Cerebras already had reasoning params defined and free-tier limits
    documented, but no call path ever existed.
    """

    def _adapter(self, provider="openrouter"):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = provider
        a.model = "m"
        a._openrouter_api_key = "or-key"
        a._openrouter_site = ""
        a._openrouter_site_title = ""
        return a

    def test_configured_provider_leads(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "g")
        chain = self._adapter("groq")._provider_chain()
        assert chain[0] == "groq"

    def test_providers_without_credentials_are_never_contacted(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        chain = self._adapter("openrouter")._provider_chain()
        assert chain == ["openrouter"]

    def test_credentialed_providers_join_the_chain(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.setenv("CEREBRAS_API_KEY", "c")
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        chain = self._adapter("openrouter")._provider_chain()
        assert chain[0] == "openrouter"
        assert set(chain) == {"openrouter", "groq", "cerebras"}

    def test_blank_key_does_not_count_as_configured(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "   ")
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        assert self._adapter("openrouter")._provider_chain() == ["openrouter"]

    def test_local_ollama_joins_when_configured(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        chain = self._adapter("openrouter")._provider_chain()
        assert chain == ["openrouter", "ollama"]

    def test_no_duplicate_when_configured_provider_also_has_a_key(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        chain = self._adapter("groq")._provider_chain()
        assert chain.count("groq") == 1


class TestProviderChainNeedsAnExplicitProvider:
    """A credential in the environment is not consent to dial its host.

    ``.env`` is loaded process-wide, so keys belonging to Mynx and to the
    combat strategist are sitting in the environment of every other feature.
    The chain used to seed itself with ``self.provider`` and append every
    provider whose key merely existed -- and ``self.provider`` is a *default*
    (``... or "ollama"``) when nobody set one. So ``NPC_CHAT_LLM_ENABLED=1``
    and nothing else produced [ollama, openrouter, groq, cerebras], and a box
    with no Ollama running shipped player-authored conversation text to a
    remote host the operator never nominated for chat.

    These build real adapters rather than ``__new__`` stand-ins: the whole
    point is what the *environment* implies, so the environment has to be what
    drives them. ``NPC_CHAT_LLM_ENABLED`` stays 0 throughout, which keeps
    ``__init__`` off the network without weakening the assertions --
    ``_provider_chain`` never consults the gate.
    """

    @staticmethod
    def _all_credentials(monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or")
        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.setenv("CEREBRAS_API_KEY", "c")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "0")

    def test_a_defaulted_provider_gets_no_remote_fallbacks(self, monkeypatch):
        self._all_credentials(monkeypatch)
        monkeypatch.delenv("NPC_CHAT_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("MYNX_LLM_PROVIDER", raising=False)

        adapter = NpcChatLLMAdapter()

        assert adapter.provider == llm.DEFAULT_PROVIDER
        assert adapter._provider_explicit is False
        # The local default stays dialable -- it needs no credential and never
        # leaves the machine. Everything remote is withheld.
        assert adapter._provider_chain() == ["ollama"]

    def test_an_explicit_provider_arms_the_whole_chain(self, monkeypatch):
        self._all_credentials(monkeypatch)
        monkeypatch.setenv("NPC_CHAT_LLM_PROVIDER", "openrouter")

        adapter = NpcChatLLMAdapter()

        assert adapter._provider_explicit is True
        chain = adapter._provider_chain()
        assert chain[0] == "openrouter"
        assert set(chain) == {"openrouter", "groq", "cerebras", "ollama"}

    def test_naming_ollama_keeps_player_text_on_the_box(self, monkeypatch):
        """S1: naming the local host is a consent statement, not just routing.

        The rule used to distinguish NAMED from DEFAULTED only, so
        ``NPC_CHAT_LLM_PROVIDER=ollama`` -- the strongest "keep this on the
        machine" statement an operator can make -- still armed
        ``[ollama, openrouter, groq, cerebras]``, and player free-text went to
        whichever remote key happened to be in ``.env`` for another feature the
        moment the local host was down.
        """
        self._all_credentials(monkeypatch)
        monkeypatch.setenv("NPC_CHAT_LLM_PROVIDER", "ollama")
        monkeypatch.delenv("NPC_CHAT_LLM_FALLBACK", raising=False)

        chain = NpcChatLLMAdapter()._provider_chain()

        assert chain == ["ollama"]

    def test_an_ollama_pin_can_opt_back_into_the_remote_chain(self, monkeypatch):
        """"Which host" and "may this leave the box" are two decisions, so they
        have two settings. NPC_CHAT_LLM_FALLBACK=1 is the second one."""
        self._all_credentials(monkeypatch)
        monkeypatch.setenv("NPC_CHAT_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("NPC_CHAT_LLM_FALLBACK", "1")

        chain = NpcChatLLMAdapter()._provider_chain()

        assert chain[0] == "ollama"
        assert set(chain) == {"ollama", "openrouter", "groq", "cerebras"}

    def test_the_fallback_opt_in_fails_closed(self, monkeypatch):
        """Anything but a true value means no. A gate on real network spend
        does not get to be generous about typos."""
        self._all_credentials(monkeypatch)
        monkeypatch.setenv("NPC_CHAT_LLM_PROVIDER", "ollama")
        for value in ("0", "no", "yes", "", "  ", "TRUE!"):
            monkeypatch.setenv("NPC_CHAT_LLM_FALLBACK", value)
            assert NpcChatLLMAdapter()._provider_chain() == ["ollama"], value

    def test_naming_a_remote_provider_still_arms_the_whole_chain(self, monkeypatch):
        """The narrowing above is about ollama specifically: an operator who
        names a remote host has already agreed the text leaves the machine, and
        the fallback chain is the whole point of naming one."""
        self._all_credentials(monkeypatch)
        monkeypatch.setenv("NPC_CHAT_LLM_PROVIDER", "groq")
        monkeypatch.delenv("NPC_CHAT_LLM_FALLBACK", raising=False)

        chain = NpcChatLLMAdapter()._provider_chain()

        assert chain[0] == "groq"
        assert set(chain) == {"ollama", "openrouter", "groq", "cerebras"}

    def test_the_mynx_provider_still_counts_as_explicit_for_chat(self, monkeypatch):
        """NPC chat falls back to MYNX_LLM_PROVIDER by design (a one-model
        deployment configures one place), and a value read through that
        fallback was still typed by the operator."""
        self._all_credentials(monkeypatch)
        monkeypatch.delenv("NPC_CHAT_LLM_PROVIDER", raising=False)
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "groq")

        adapter = NpcChatLLMAdapter()

        assert adapter.provider == "groq"
        assert adapter._provider_explicit is True
        assert len(adapter._provider_chain()) > 1

    def test_the_disabled_sentinel_still_yields_nothing(self, monkeypatch):
        self._all_credentials(monkeypatch)
        monkeypatch.setenv("NPC_CHAT_LLM_PROVIDER", llm.PROVIDER_DISABLED)

        assert NpcChatLLMAdapter()._provider_chain() == []

    def test_assigning_the_provider_is_itself_a_choice(self, monkeypatch):
        """The flag lives on the ``provider`` setter, not in ``__init__``.

        Subclasses and tests both pin a provider by assignment; a flag set only
        during ``__init__`` would read False for every one of them.
        """
        self._all_credentials(monkeypatch)
        adapter = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        adapter.provider = "groq"

        assert adapter._provider_explicit is True
        assert len(adapter._provider_chain()) > 1

    def test_an_uninitialised_adapter_defaults_to_no_fallbacks(self, monkeypatch):
        """``__new__`` skips ``__init__``; the class-level defaults have to be
        the conservative answer, not an AttributeError and not consent."""
        self._all_credentials(monkeypatch)
        adapter = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)

        assert adapter.provider == llm.DEFAULT_PROVIDER
        assert adapter._provider_chain() == ["ollama"]


class TestCallLlmFallsThrough:
    def _adapter(self, monkeypatch, calls, results):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "openrouter"
        a.model = "m"
        a._openrouter_api_key = "or-key"
        a._openrouter_site = ""
        a._openrouter_site_title = ""

        def _or(*args, **kw):
            calls.append("openrouter")
            return results.get("openrouter")

        def _compat(provider, *args, **kw):
            calls.append(provider)
            return results.get(provider)

        a._call_openrouter = _or
        a._call_openai_compatible = _compat
        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.setenv("CEREBRAS_API_KEY", "c")
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        return a

    def test_exhausted_provider_falls_through_to_the_next(self, monkeypatch):
        calls = []
        a = self._adapter(monkeypatch, calls, {"openrouter": None, "groq": '{"a": 1}'})
        out = a._call_llm("sys", "user")
        assert out == '{"a": 1}'
        assert calls == ["openrouter", "groq"]

    def test_first_usable_response_wins(self, monkeypatch):
        calls = []
        a = self._adapter(monkeypatch, calls, {"openrouter": '{"a": 1}'})
        assert a._call_llm("sys", "user") == '{"a": 1}'
        assert calls == ["openrouter"]

    def test_a_raising_provider_does_not_abort_the_chain(self, monkeypatch):
        calls = []
        a = self._adapter(monkeypatch, calls, {"groq": '{"ok": 1}'})

        def _boom(*args, **kw):
            calls.append("openrouter")
            raise RuntimeError("provider exploded")

        a._call_openrouter = _boom
        assert a._call_llm("sys", "user") == '{"ok": 1}'
        assert calls[0] == "openrouter"

    def test_all_providers_down_returns_none(self, monkeypatch):
        calls = []
        a = self._adapter(monkeypatch, calls, {})
        assert a._call_llm("sys", "user") is None
        assert calls == ["openrouter", "groq", "cerebras"]

    def test_thinking_only_response_is_skipped_not_returned(self, monkeypatch):
        calls = []
        a = self._adapter(
            monkeypatch, calls, {"openrouter": "<think>hmm", "groq": '{"a": 1}'}
        )
        assert a._call_llm("sys", "user") == '{"a": 1}'
        assert calls == ["openrouter", "groq"]

    def test_disabled_adapter_contacts_nobody(self, monkeypatch):
        calls = []
        a = self._adapter(monkeypatch, calls, {"openrouter": '{"a": 1}'})
        a.enabled = False
        assert a._call_llm("sys", "user") is None
        assert calls == []


class TestOpenAiCompatibleCall:
    def _adapter(self):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "groq"
        a.model = "m"
        return a

    def test_missing_key_makes_no_request(self, monkeypatch):
        called = []
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setattr(
            llm, "_post_chat_completion", lambda *a, **k: called.append(1)
        )
        assert self._adapter()._call_openai_compatible("groq", "sys", "u", 100, 0.5) is None
        assert called == []

    def test_payload_carries_json_mode_and_provider_reasoning(self, monkeypatch):
        seen = {}

        def fake_post(url, payload, headers, timeout):
            seen["url"] = url
            seen["payload"] = payload
            seen["headers"] = headers
            return _Resp()

        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.setattr(llm, "_post_chat_completion", fake_post)
        out = self._adapter()._call_openai_compatible("groq", "sys", "u", 100, 0.5)

        assert out == '{"npc_text": "Fine."}'
        assert "groq.com" in seen["url"]
        assert seen["payload"]["response_format"] == {"type": "json_object"}
        # _REASONING_PARAMS already carried Groq's quirks; they must be used.
        assert seen["payload"].get("reasoning_format") == "hidden"
        assert seen["headers"]["Authorization"] == "Bearer g"

    def test_rate_limited_provider_returns_none_for_the_chain(self, monkeypatch):
        monkeypatch.setenv("CEREBRAS_API_KEY", "c")
        monkeypatch.setattr(
            llm, "_post_chat_completion", lambda *a, **k: _Resp(429, text="slow down")
        )
        assert self._adapter()._call_openai_compatible("cerebras", "s", "u", 10, 0.5) is None

    def test_served_model_is_recorded_with_its_provider(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.setenv("GROQ_MODEL", "some-fast-model")
        monkeypatch.setattr(llm, "_post_chat_completion", lambda *a, **k: _Resp())
        a = self._adapter()
        a._call_openai_compatible("groq", "sys", "u", 100, 0.5)
        assert a._last_served_model == "groq:some-fast-model"

    # The bench keyed on "<provider>:<model>" was only ever *written* on a
    # successful call (via _last_served_model), so a transport failure marked
    # nothing. A retired slug therefore 404'd on every turn forever, paying the
    # full round-trip each time -- and, because the chain silently moved on,
    # looking exactly like a healthy provider from the outside. This is the
    # mechanism that let two dead providers pass as 46/47 green for days.
    @pytest.mark.parametrize("status", [401, 402, 404])
    def test_permanent_client_error_benches_the_model(self, status, monkeypatch):
        """C4: an HTTP failure now yields None like every other chain method.

        This used to assert ``pytest.raises(RuntimeError)`` -- the one method in
        the chain that re-raised, which is why ``_call_llm`` needed a broad
        ``except`` just to absorb it. The bench still has to land, or a retired
        slug is re-dialled on every single turn.
        """
        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.setenv("GROQ_MODEL", "retired-slug")
        monkeypatch.setattr(
            llm, "_post_chat_completion", lambda *a, **k: _Resp(status, text="nope")
        )
        a = self._adapter()
        assert a._call_openai_compatible("groq", "sys", "u", 100, 0.5) is None
        assert a._is_model_failed("groq:retired-slug")

    def test_benched_model_is_not_re_dialled(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.setenv("GROQ_MODEL", "retired-slug")
        posts = []

        def counting_post(*a, **k):
            posts.append(1)
            return _Resp(404, text="model_not_found")

        monkeypatch.setattr(llm, "_post_chat_completion", counting_post)
        a = self._adapter()
        assert a._call_openai_compatible("groq", "sys", "u", 100, 0.5) is None

        # Second turn: the guard at the top of the method must short-circuit.
        assert a._call_openai_compatible("groq", "sys", "u", 100, 0.5) is None
        assert len(posts) == 1, "benched model was dialled again"

    def test_transient_server_error_is_not_benched(self, monkeypatch):
        # 5xx says nothing about the slug's validity; benching it would take a
        # healthy provider out of the chain over one bad minute.
        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.setenv("GROQ_MODEL", "fine-slug")
        monkeypatch.setattr(
            llm, "_post_chat_completion", lambda *a, **k: _Resp(503, text="try later")
        )
        a = self._adapter()
        assert a._call_openai_compatible("groq", "sys", "u", 100, 0.5) is None
        assert not a._is_model_failed("groq:fine-slug")


# ---------------------------------------------------------------------------
# Free-tier saturation analytics
# ---------------------------------------------------------------------------


class _HeaderResp(_Resp):
    def __init__(self, status=200, headers=None, **kw):
        super().__init__(status=status, **kw)
        self.headers = headers or {}


class TestProviderSaturation:
    """Per-provider headroom, so a quota wall is visible before it bites.

    Every provider in the chain reports its own limits in response headers, in
    its own dialect. Reading them turns "chat went quiet" into a number that can
    be watched in the logs, in dev and after deployment.
    """

    def test_request_style_headers_are_read(self):
        GenericLLMClient._record_provider_usage(
            "openrouter",
            _HeaderResp(headers={"X-RateLimit-Limit": "50", "X-RateLimit-Remaining": "0"}),
        )
        sat = GenericLLMClient.provider_saturation()
        assert sat["providers"]["openrouter"]["saturation"] == 1.0
        assert sat["providers"]["openrouter"]["limit"] == 50.0
        assert sat["providers"]["openrouter"]["remaining"] == 0.0

    def test_token_style_headers_are_read(self):
        GenericLLMClient._record_provider_usage(
            "groq",
            _HeaderResp(
                headers={
                    "x-ratelimit-limit-tokens": "6000",
                    "x-ratelimit-remaining-tokens": "1500",
                }
            ),
        )
        assert GenericLLMClient.provider_saturation()["providers"]["groq"][
            "saturation"
        ] == pytest.approx(0.75)

    def test_worst_dimension_wins(self):
        """Requests near-empty and tokens plentiful still means saturated."""
        GenericLLMClient._record_provider_usage(
            "groq",
            _HeaderResp(
                headers={
                    "x-ratelimit-limit-requests": "100",
                    "x-ratelimit-remaining-requests": "1",
                    "x-ratelimit-limit-tokens": "6000",
                    "x-ratelimit-remaining-tokens": "6000",
                }
            ),
        )
        assert GenericLLMClient.provider_saturation()["providers"]["groq"][
            "saturation"
        ] == pytest.approx(0.99)

    def test_counters_track_outcomes(self):
        GenericLLMClient._record_provider_usage("groq", _HeaderResp(), outcome="ok")
        GenericLLMClient._record_provider_usage("groq", _HeaderResp(), outcome="ok")
        GenericLLMClient._record_provider_usage(
            "groq", _HeaderResp(429), outcome="rate_limited"
        )
        stats = GenericLLMClient.provider_saturation()["providers"]["groq"]
        assert stats["requests"] == 3
        assert stats["successes"] == 2
        assert stats["rate_limited"] == 1

    def test_missing_headers_are_not_fatal(self):
        GenericLLMClient._record_provider_usage("cerebras", _HeaderResp())
        stats = GenericLLMClient.provider_saturation()["providers"]["cerebras"]
        assert stats["saturation"] is None
        assert stats["requests"] == 1

    def test_junk_header_values_are_ignored(self):
        GenericLLMClient._record_provider_usage(
            "groq",
            _HeaderResp(headers={"x-ratelimit-limit": "lots", "x-ratelimit-remaining": "?"}),
        )
        assert GenericLLMClient.provider_saturation()["providers"]["groq"]["saturation"] is None

    def test_zero_limit_does_not_divide_by_zero(self):
        GenericLLMClient._record_provider_usage(
            "groq", _HeaderResp(headers={"x-ratelimit-limit": "0", "x-ratelimit-remaining": "0"})
        )
        assert GenericLLMClient.provider_saturation()["providers"]["groq"]["saturation"] is None

    def test_no_response_object_still_counts_the_attempt(self):
        GenericLLMClient._record_provider_usage("groq", None, outcome="error")
        stats = GenericLLMClient.provider_saturation()["providers"]["groq"]
        assert stats["requests"] == 1
        assert stats["errors"] == 1


class TestTotalSaturation:
    """The headline number: is there capacity left anywhere in the chain?"""

    def _usage(self, provider, limit, remaining):
        GenericLLMClient._record_provider_usage(
            provider,
            _HeaderResp(
                headers={"x-ratelimit-limit": str(limit), "x-ratelimit-remaining": str(remaining)}
            ),
        )

    def test_one_exhausted_provider_does_not_exhaust_the_chain(self):
        self._usage("openrouter", 50, 0)
        self._usage("groq", 100, 90)
        total = GenericLLMClient.provider_saturation()
        assert total["effective_saturation"] == pytest.approx(0.10)
        assert total["providers_exhausted"] == 1

    def test_all_exhausted_reports_full_saturation(self):
        self._usage("openrouter", 50, 0)
        self._usage("groq", 100, 0)
        total = GenericLLMClient.provider_saturation()
        assert total["effective_saturation"] == 1.0
        assert total["providers_exhausted"] == 2

    def test_total_is_none_when_nothing_reported_limits(self):
        GenericLLMClient._record_provider_usage("groq", _HeaderResp())
        assert GenericLLMClient.provider_saturation()["effective_saturation"] is None

    def test_the_deprecated_total_saturation_alias_is_gone(self):
        """It said the opposite of what it held (the *least* saturated
        provider, not a total), and every consumer renamed it at the point of
        use. Kept alive only by these assertions; they have moved."""
        assert "total_saturation" not in GenericLLMClient.provider_saturation()

    def test_reset_clears_usage(self):
        self._usage("groq", 100, 5)
        assert GenericLLMClient.provider_saturation()["providers"]  # precondition
        GenericLLMClient.reset_class_state()
        assert GenericLLMClient.provider_saturation()["providers"] == {}


class TestSaturationLogging:
    def test_saturation_line_is_logged_at_info(self, caplog):
        GenericLLMClient._record_provider_usage(
            "openrouter",
            _HeaderResp(headers={"x-ratelimit-limit": "50", "x-ratelimit-remaining": "0"}),
        )
        with caplog.at_level("INFO", logger="ai.llm_client"):
            GenericLLMClient.log_provider_saturation()
        blob = " ".join(r.getMessage() for r in caplog.records)
        assert "SATURATION" in blob
        assert "openrouter" in blob
        assert "100" in blob

    def test_epoch_millisecond_reset_is_rendered_readably(self):
        assert GenericLLMClient.format_reset("1787443200000").startswith("2026-")

    def test_epoch_second_reset_is_rendered_readably(self):
        assert GenericLLMClient.format_reset("1787443200").startswith("2026-")

    def test_human_reset_value_is_passed_through(self):
        assert GenericLLMClient.format_reset("2m59s") == "2m59s"

    def test_empty_reset_is_blank(self):
        assert GenericLLMClient.format_reset("") == ""

    def test_absurd_reset_does_not_raise(self):
        assert GenericLLMClient.format_reset("999999999999999999999")

    def test_logging_with_no_data_does_not_raise(self, caplog):
        with caplog.at_level("INFO", logger="ai.llm_client"):
            GenericLLMClient.log_provider_saturation()

    def test_seconds_until_reset_is_not_rendered_as_1970(self):
        assert "1970" not in GenericLLMClient.format_reset("60")


# ---------------------------------------------------------------------------
# Consequences of JSON mode elsewhere on the adapter
# ---------------------------------------------------------------------------


class TestJeanOptionsUnderJsonMode:
    """``response_format: json_object`` forbids a top-level array.

    ``generate_jean_options`` asks for three options and used to require a bare
    JSON array back. Once the payload started demanding JSON mode, a model that
    honours it must wrap them in an object — which the list check rejected, so
    every turn silently fell back to canned player options.
    """

    def _adapter(self, raw):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "openrouter"
        a.model = "json-capable"
        a._last_served_model = "json-capable"
        a._call_llm = lambda *args, **kw: raw
        return a

    ARRAY = (
        '[{"tone": "direct", "text": "a"},'
        ' {"tone": "guarded", "text": "b"},'
        ' {"tone": "open", "text": "c"}]'
    )
    OBJECT = '{"options": %s}' % ARRAY

    def _options(self, raw):
        return self._adapter(raw).generate_jean_options("Ned", "gruff", "hello", [], 1)

    def test_json_mode_object_wrapper_is_accepted(self):
        opts = self._options(self.OBJECT)
        assert opts is not None and len(opts) == 3

    def test_bare_array_still_works(self):
        opts = self._options(self.ARRAY)
        assert opts is not None and len(opts) == 3

    def test_object_wrapper_buried_in_prose_is_recovered(self):
        opts = self._options("Sure, here you go: " + self.OBJECT)
        assert opts is not None and len(opts) == 3

    def test_unusable_output_still_returns_none(self):
        assert self._options("I would rather not.") is None

    def test_object_without_any_list_returns_none(self):
        assert self._options('{"note": "no options here"}') is None


class TestBenchedProviderModelIsSkipped:
    """A benched non-OpenRouter model must actually leave the chain.

    ``_penalize_unparseable`` records these under ``provider:model``; if the
    call path never consults ``_failed_models`` the bench is an entry nothing
    reads, and the same host is re-dialled on every turn forever.
    """

    def test_benched_model_makes_no_request(self, monkeypatch):
        called = []
        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.setenv("GROQ_MODEL", "chatty")
        monkeypatch.setattr(
            llm, "_post_chat_completion", lambda *a, **k: called.append(1)
        )
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "groq"
        a.model = "m"

        GenericLLMClient._penalize_unparseable("groq:chatty")
        assert a._call_openai_compatible("groq", "sys", "u", 100, 0.5) is None
        assert called == []


class TestOllamaAttributesItsOwnOutput:
    """Ollama answering must not leave another provider holding the penalty."""

    def test_served_model_is_namespaced_to_ollama(self, monkeypatch):
        class _R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": '{"npc_text": "Aye."}'}}

        monkeypatch.setattr(llm.requests, "post", lambda *a, **k: _R())
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "ollama"
        a.model = "local-llama"
        a.base_url = "http://localhost:11434"
        a._last_served_model = "some/openrouter-model:free"

        assert a._call_ollama("sys", "u", 100, 0.5)
        assert a._last_served_model == "ollama:local-llama"


class TestInferredSaturationDoesNotStick:
    """A 429-inferred 100% must clear once the host serves again.

    OpenRouter sends no rate-limit headers on chat completions, so the only
    saturation ever recorded for it is the 1.0 guessed from a 429. Left in
    place, the log would report the provider exhausted for the life of the
    process, long past the daily reset.
    """

    def test_success_after_a_headerless_429_clears_the_guess(self):
        GenericLLMClient._record_provider_usage(
            "openrouter", _HeaderResp(429), "rate_limited"
        )
        # A headerless 429 is a GUESS, not a figure the provider stood behind,
        # and it is as often a per-minute bucket as a spent day. It used to be
        # counted in `providers_exhausted` with the same weight as a reported
        # one, in the single number an operator reads to decide whether the
        # chain is finished for the day.
        snapshot = GenericLLMClient.provider_saturation()
        assert snapshot["providers_exhausted"] == 0
        assert snapshot["providers_exhausted_inferred"] == 1

        GenericLLMClient._record_provider_usage("openrouter", _HeaderResp(), "ok")
        snapshot = GenericLLMClient.provider_saturation()
        assert snapshot["providers_exhausted"] == 0
        assert snapshot["providers_exhausted_inferred"] == 0
        assert snapshot["effective_saturation"] is None

    def test_a_reported_exhaustion_still_counts(self):
        """The narrowing must not hide a provider that really did say it is
        spent -- that is the case the number exists for."""
        GenericLLMClient._record_provider_usage(
            "groq",
            _HeaderResp(
                headers={"x-ratelimit-limit": "10", "x-ratelimit-remaining": "0"}
            ),
        )
        snapshot = GenericLLMClient.provider_saturation()
        assert snapshot["providers_exhausted"] == 1
        assert snapshot["providers_exhausted_inferred"] == 0

    def test_a_reported_figure_is_never_overwritten_by_a_later_success(self):
        GenericLLMClient._record_provider_usage(
            "groq",
            _HeaderResp(
                headers={"x-ratelimit-limit": "10", "x-ratelimit-remaining": "2"}
            ),
            "ok",
        )
        GenericLLMClient._record_provider_usage("groq", _HeaderResp(), "ok")
        assert GenericLLMClient.provider_saturation()["providers"]["groq"][
            "saturation"
        ] == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Pre-emptive cutoff: stop dialling a provider that is already spent
# ---------------------------------------------------------------------------


class TestSaturationCutoff:
    """Don't spend a round trip discovering a wall we were already told about.

    Every provider reports its remaining headroom in the headers of the calls we
    already make, so a provider at or past the cutoff is skipped outright until
    its reset passes. There is nothing to poll: OpenRouter's /api/v1/key reports
    dollar credit, which stays at zero on a free tier no matter how much of the
    50/day request cap is spent, so response headers are the only real signal.
    """

    def _seen(self, provider, limit, remaining, reset=None):
        headers = {
            "x-ratelimit-limit": str(limit),
            "x-ratelimit-remaining": str(remaining),
        }
        if reset is not None:
            headers["x-ratelimit-reset"] = str(reset)
        GenericLLMClient._record_provider_usage("x", None)  # noise
        GenericLLMClient._record_provider_usage(provider, _HeaderResp(headers=headers))

    def test_provider_with_headroom_is_available(self):
        self._seen("groq", 100, 50)
        assert GenericLLMClient._provider_available("groq") is True

    def test_provider_at_the_cutoff_is_skipped(self):
        self._seen("openrouter", 50, 5)  # 90% saturated
        assert GenericLLMClient._provider_available("openrouter") is False

    def test_exhausted_provider_is_skipped(self):
        self._seen("openrouter", 50, 0)
        assert GenericLLMClient._provider_available("openrouter") is False

    def test_unknown_provider_is_available(self):
        assert GenericLLMClient._provider_available("never-called") is True

    def test_cutoff_is_configurable(self, monkeypatch):
        self._seen("groq", 100, 20)  # 80% saturated
        assert GenericLLMClient._provider_available("groq") is True
        monkeypatch.setenv("LLM_SATURATION_CUTOFF", "0.75")
        assert GenericLLMClient._provider_available("groq") is False

    def test_availability_returns_after_the_reset_passes(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        self._seen("openrouter", 50, 0, reset=int(past.timestamp() * 1000))
        assert GenericLLMClient._provider_available("openrouter") is True

    def test_still_blocked_before_the_reset(self):
        future = datetime.now(timezone.utc) + timedelta(hours=3)
        self._seen("openrouter", 50, 0, reset=int(future.timestamp() * 1000))
        assert GenericLLMClient._provider_available("openrouter") is False

    def test_a_duration_reset_is_honoured_rather_than_the_hour_cooldown(self):
        """Groq meters per minute and says so in words: "2m59s"."""
        GenericLLMClient._record_provider_usage(
            "groq",
            _HeaderResp(
                headers={
                    "x-ratelimit-limit-tokens": "6000",
                    "x-ratelimit-remaining-tokens": "400",
                    "x-ratelimit-reset-tokens": "2m59s",
                }
            ),
        )
        reset_at = GenericLLMClient._provider_usage["groq"]["reset_at"]
        assert reset_at is not None
        ahead = (reset_at - datetime.now(timezone.utc)).total_seconds()
        assert 170 < ahead <= 180  # three minutes, not the blind hour
        assert GenericLLMClient._provider_available("groq") is False

        # Once the provider's own window has passed, so has the block.
        with GenericLLMClient._state_lock:
            GenericLLMClient._provider_usage["groq"]["reset_at"] = datetime.now(
                timezone.utc
            ) - timedelta(seconds=1)
        assert GenericLLMClient._provider_available("groq") is True

    def test_a_headerless_429_clears_an_expired_reset(self):
        """A stale reset must not answer for a refusal happening right now."""
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        self._seen("openrouter", 50, 0, reset=int(past.timestamp() * 1000))
        assert GenericLLMClient._provider_available("openrouter") is True

        GenericLLMClient._record_provider_usage(
            "openrouter", _HeaderResp(429), "rate_limited"
        )
        assert GenericLLMClient._provider_usage["openrouter"]["reset_at"] is None
        assert GenericLLMClient._provider_available("openrouter") is False

    def test_a_guessed_saturation_gets_a_pause_not_a_bench(self):
        """A headerless 429 is a guess; it must not bench a host for an hour."""
        GenericLLMClient._record_provider_usage(
            "openrouter", _HeaderResp(429), "rate_limited"
        )
        assert GenericLLMClient._provider_available("openrouter") is False
        with GenericLLMClient._state_lock:
            GenericLLMClient._provider_usage["openrouter"]["observed_at"] = (
                datetime.now(timezone.utc) - timedelta(minutes=6)
            )
        assert GenericLLMClient._provider_available("openrouter") is True

    def test_saturated_without_a_reset_uses_a_cooldown(self):
        self._seen("groq", 100, 0)
        assert GenericLLMClient._provider_available("groq") is False
        # Age the observation past the blind cooldown.
        with GenericLLMClient._state_lock:
            GenericLLMClient._provider_usage["groq"]["observed_at"] = (
                datetime.now(timezone.utc) - timedelta(hours=2)
            )
        assert GenericLLMClient._provider_available("groq") is True


class TestChainSkipsSaturatedProviders:
    def _adapter(self):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "openrouter"
        a.model = "m"
        a._openrouter_api_key = "or-key"
        a._openrouter_site = ""
        a._openrouter_site_title = ""
        return a

    def test_spent_provider_drops_out_of_the_chain(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        GenericLLMClient._record_provider_usage(
            "openrouter",
            _HeaderResp(headers={"x-ratelimit-limit": "50", "x-ratelimit-remaining": "0"}),
        )
        assert self._adapter()._provider_chain() == ["groq"]

    def test_chain_is_not_emptied_when_everything_is_spent(self, monkeypatch):
        """A spent chain still tries: a stale reading must not mute the game."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        GenericLLMClient._record_provider_usage(
            "openrouter",
            _HeaderResp(headers={"x-ratelimit-limit": "50", "x-ratelimit-remaining": "0"}),
        )
        assert self._adapter()._provider_chain() == ["openrouter"]


class TestDuplicateJsonKeys:
    """A restated key must not silently erase the good value that came first.

    Observed live from nvidia/nemotron-nano-9b-v2:free, which closed its object
    and then appended a second, empty `jean_options`. json.loads keeps the LAST
    duplicate, so three usable dialogue options became zero — parsed cleanly,
    no warning, no strike against the model, and the player got pool filler.
    """

    def test_first_occurrence_wins(self):
        raw = '{"npc_text": "Five copper.", "jean_options": [{"tone": "direct", "text": "Fine."}], "jean_options": []}'
        parsed = llm._JSONTools.try_parse_json(raw)
        assert parsed["jean_options"] == [{"tone": "direct", "text": "Fine."}]

    def test_scalar_duplicates_also_keep_the_first(self):
        parsed = llm._JSONTools.try_parse_json('{"npc_text": "Real line.", "npc_text": ""}')
        assert parsed["npc_text"] == "Real line."

    def test_the_observed_live_payload_survives(self):
        raw = (
            '{"npc_text":"I can help you find a guide.","jean_options":'
            '[{"tone":"direct","text":"What is the cost?"},'
            '{"tone":"guarded","text":"Who would you ask?"},'
            '{"tone":"open","text":"Tell me about them."}]'
            + "\n ,\n"
            + '"jean_options":[]}'
        )
        parsed = llm._JSONTools.try_parse_json(raw)
        assert parsed is not None
        assert len(parsed["jean_options"]) == 3

    def test_ordinary_json_is_unaffected(self):
        parsed = llm._JSONTools.try_parse_json('{"a": 1, "b": [2, 3]}')
        assert parsed == {"a": 1, "b": [2, 3]}

    def test_nested_duplicates_are_handled(self):
        parsed = llm._JSONTools.try_parse_json('{"outer": {"k": "keep", "k": "drop"}}')
        assert parsed["outer"]["k"] == "keep"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])


class TestNoneSentinelDisarmsChain:
    """provider="none" means nobody configured chat — keys are not consent.

    The repo .env holds real credentials and is loaded at import for other
    features; before this pin, an enabled adapter with the "none" sentinel
    still built a live chain out of whatever keys happened to be present, so
    the default unit suite could dial OpenRouter for real.
    """

    def _adapter(self, provider):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = provider
        a.model = "m"
        a._openrouter_api_key = "or-key"
        a._openrouter_site = ""
        a._openrouter_site_title = ""
        return a

    def test_none_provider_yields_empty_chain_despite_keys(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "real-looking-key")
        monkeypatch.setenv("GROQ_API_KEY", "g")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        assert self._adapter("none")._provider_chain() == []

    def test_empty_provider_yields_empty_chain(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "real-looking-key")
        assert self._adapter("")._provider_chain() == []

    def test_call_llm_makes_no_request_with_none_provider(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "real-looking-key")

        def _bomb(*a, **kw):  # pragma: no cover - the point is it never runs
            raise AssertionError("network dial attempted with provider=none")

        monkeypatch.setattr(llm.requests, "post", _bomb)
        assert self._adapter("none")._call_llm("sys", "user") is None


class TestOpenrouterFallbackUsesItsOwnDialect:
    """A chain fallback to OpenRouter must not carry Groq/Cerebras keys.

    _call_openrouter used to splat _reasoning_params(self.provider): as a
    fallback while provider=groq that sent Groq's reasoning_effort dialect to
    openrouter.ai, and while provider=ollama it omitted the reasoning block
    entirely — letting reasoning models spend the completion budget narrating.
    """

    def test_payload_carries_openrouter_reasoning_block(self, monkeypatch):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "groq"  # configured for groq; openrouter is the fallback
        a.model = "some/model:free"
        a._openrouter_api_key = "or-key"
        a._openrouter_site = ""
        a._openrouter_site_title = ""
        payloads = []

        def _capture(url, payload, headers, timeout):
            payloads.append(payload)

            class _R:
                status_code = 200
                text = ""

                @staticmethod
                def raise_for_status():
                    return None

                @staticmethod
                def json():
                    return {"choices": [{"message": {"content": "{}"}}]}

                headers = {}

            return _R()

        monkeypatch.setattr(llm, "_post_chat_completion", _capture)
        a._call_openrouter("sys", "user", 100, 0.5)
        assert payloads, "no request captured"
        expected = llm._reasoning_params("openrouter")
        for key, value in expected.items():
            assert payloads[0].get(key) == value
        assert "reasoning_effort" not in payloads[0]


class TestOllamaTrafficIsMetered:
    """Ollama calls must appear in the usage picture and honour the bench."""

    def _adapter(self):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "ollama"
        a.model = "local-llama"
        a.base_url = "http://127.0.0.1:11434"
        return a

    def test_success_records_ollama_usage(self, monkeypatch):
        class _R:
            status_code = 200
            headers = {}

            @staticmethod
            def raise_for_status():
                return None

            @staticmethod
            def json():
                return {"message": {"content": "{}"}}

        monkeypatch.setattr(llm.requests, "post", lambda *a, **kw: _R())
        self._adapter()._call_ollama("sys", "user", 100, 0.5)
        snap = GenericLLMClient.usage_snapshot()
        ollama = snap["providers"].get("ollama")
        assert ollama and ollama["requests"] >= 1 and ollama["successes"] >= 1

    def test_benched_ollama_model_is_skipped(self, monkeypatch):
        def _bomb(*a, **kw):  # pragma: no cover
            raise AssertionError("benched ollama model was dialled")

        monkeypatch.setattr(llm.requests, "post", _bomb)
        GenericLLMClient._bench_model("ollama:local-llama", duration_minutes=15)
        assert self._adapter()._call_ollama("sys", "user", 100, 0.5) is None


class TestResetHeaderHardening:
    """Provider-controlled reset headers must not crash or forge output."""

    def test_absurd_duration_is_clamped_not_overflowed(self):
        reset = GenericLLMClient._parse_reset_at("3000000d")
        assert reset is not None
        horizon = datetime.now(timezone.utc) + timedelta(days=31)
        assert reset < horizon

    def test_huge_integer_duration_does_not_raise(self):
        assert GenericLLMClient._parse_reset_at("99999999999d") is not None

    def test_format_reset_strips_newlines_and_markdown(self):
        rendered = GenericLLMClient.format_reset("2m59s\nFORGED **bold**")
        assert "\n" not in rendered
        assert "*" not in rendered
        assert rendered.startswith("2m59s")

    def test_format_reset_keeps_plain_durations(self):
        assert GenericLLMClient.format_reset("2m59s") == "2m59s"


class TestMergeUsage:
    """A failed digest post must give its window counters back."""

    def test_merged_counts_return_to_the_live_window(self):
        GenericLLMClient._record_provider_usage("openrouter", None, "ok")
        GenericLLMClient._record_provider_usage("openrouter", None, "error")
        snap = GenericLLMClient.snapshot_and_reset()
        assert GenericLLMClient.usage_snapshot()["providers"].get(
            "openrouter", {}
        ).get("requests", 0) == 0
        GenericLLMClient._record_provider_usage("openrouter", None, "ok")
        GenericLLMClient.merge_usage(snap)
        live = GenericLLMClient.usage_snapshot()["providers"]["openrouter"]
        assert live["requests"] == 3
        assert live["successes"] == 2
        assert live["errors"] == 1


# ---------------------------------------------------------------------------
# 429 -> metering, end to end
# ---------------------------------------------------------------------------


class Test429ReachesTheMeter:
    """The whole reason the provider chain exists, asserted end to end.

    Every other 429 test in this file either asserts only ``is None`` or calls
    ``_record_provider_usage`` *directly*. Neither proves the path that matters:
    a provider refusing a real call has to make that provider *unavailable*, or
    the chain re-dials a host that has already said no -- against an
    account-wide 50/day free tier, on a synchronous request the player is
    watching a spinner on.
    """

    def _adapter(self, provider="openrouter"):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = provider
        a.model = "m"
        a._openrouter_api_key = "or-key"
        a._openrouter_site = ""
        a._openrouter_site_title = ""
        return a

    def test_an_openai_compatible_429_marks_the_provider_spent(self, monkeypatch):
        monkeypatch.setenv("CEREBRAS_API_KEY", "c")
        monkeypatch.setattr(
            llm, "_post_chat_completion", lambda *a, **k: _Resp(429, text="slow down")
        )

        assert (
            self._adapter("cerebras")._call_openai_compatible(
                "cerebras", "s", "u", 10, 0.5
            )
            is None
        )

        usage = GenericLLMClient._provider_usage["cerebras"]
        assert usage["rate_limited"] == 1
        assert usage["requests"] == 1
        # The refusal has to survive the call, or the next turn dials it again.
        assert GenericLLMClient._provider_available("cerebras") is False

    def test_a_second_provider_is_untouched_by_the_first_ones_429(self, monkeypatch):
        monkeypatch.setenv("CEREBRAS_API_KEY", "c")
        monkeypatch.setattr(
            llm, "_post_chat_completion", lambda *a, **k: _Resp(429, text="slow down")
        )
        self._adapter("cerebras")._call_openai_compatible("cerebras", "s", "u", 10, 0.5)
        assert GenericLLMClient._provider_available("groq") is True


class TestOpenrouterAttempt:
    """``_openrouter_attempt`` is the single metered OpenRouter transport.

    Both OpenRouter call paths funnel through it (C1), so this is where a 429
    has to become saturation and a bench -- and where a success has to clear a
    stale inferred guess. The base client's own HTTP path used to record
    nothing, so a combat 429 could not raise saturation and a combat success
    could not clear NPC chat's guess.
    """

    def _adapter(self):
        a = NpcChatLLMAdapter.__new__(NpcChatLLMAdapter)
        a.enabled = True
        a.provider = "openrouter"
        a.model = "primary/model"
        a._openrouter_api_key = "or-key"
        a._openrouter_site = ""
        a._openrouter_site_title = ""
        return a

    def test_a_429_meters_the_provider_and_benches_the_model(self, monkeypatch):
        monkeypatch.setattr(GenericLLMClient, "_free_models_cache", [])
        monkeypatch.setattr(
            llm, "_post_chat_completion", lambda *a, **k: _Resp(429, text="slow down")
        )
        a = self._adapter()

        assert a._call_openrouter("sys", "user", 100, 0.5) is None

        usage = GenericLLMClient._provider_usage["openrouter"]
        assert usage["rate_limited"] == 1
        assert GenericLLMClient._provider_available("openrouter") is False
        assert a._is_model_failed("primary/model") is True

    def test_a_429_stops_the_candidate_loop(self, monkeypatch):
        """C3: the free tier is metered per ACCOUNT, so once one model has been
        refused every remaining candidate is a guaranteed 429 too. Walking the
        rest only spends the player's latency budget proving what the first
        refusal already said."""
        monkeypatch.setattr(
            GenericLLMClient, "_free_models_cache", ["second/model", "third/model"]
        )
        dialled = []

        def counting_post(url, payload, headers, timeout):
            dialled.append(payload["model"])
            return _Resp(429, text="slow down")

        monkeypatch.setattr(llm, "_post_chat_completion", counting_post)
        assert self._adapter()._call_openrouter("sys", "user", 100, 0.5) is None
        assert dialled == ["primary/model"]

    def test_a_non_429_failure_does_advance_to_the_next_candidate(self, monkeypatch):
        """A 404 says the *slug* is dead, not that the account is spent, so the
        chain must keep walking -- the distinction the 429 short-circuit rests
        on."""
        monkeypatch.setattr(GenericLLMClient, "_free_models_cache", ["second/model"])
        dialled = []

        def post(url, payload, headers, timeout):
            dialled.append(payload["model"])
            if payload["model"] == "second/model":
                return _Resp()
            return _Resp(404, text="model_not_found")

        monkeypatch.setattr(llm, "_post_chat_completion", post)
        out = self._adapter()._call_openrouter("sys", "user", 100, 0.5)

        assert out == '{"npc_text": "Fine."}'
        assert "second/model" in dialled
        assert GenericLLMClient._provider_available("openrouter") is True

    def test_a_success_clears_a_stale_inferred_saturation(self, monkeypatch):
        """OpenRouter sends no rate-limit headers on chat completions, so the
        only saturation ever recorded for it is the 1.0 guessed from a 429. If
        a later success could not clear it, the provider would read as spent for
        the life of the process, long past the daily reset."""
        monkeypatch.setattr(GenericLLMClient, "_free_models_cache", [])
        GenericLLMClient._record_provider_usage("openrouter", _Resp(429), "rate_limited")
        assert GenericLLMClient._provider_available("openrouter") is False

        monkeypatch.setattr(llm, "_post_chat_completion", lambda *a, **k: _Resp())
        a = self._adapter()
        a.model = "fresh/model"
        assert a._call_openrouter("sys", "user", 100, 0.5)
        assert GenericLLMClient._provider_available("openrouter") is True
