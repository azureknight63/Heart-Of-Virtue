"""
Characterization tests for the NPC chat prompts against a real LLM provider.

These tests make actual network calls and are EXCLUDED from the standard
pytest run. Run them explicitly:

    HOV_LIVE_LLM=1 python -m pytest tests/integration/test_npc_chat_live.py -v

(Without HOV_LIVE_LLM=1 the same command collects and SKIPS every test —
a green run proves nothing.)

HOV_LIVE_LLM=1 is the opt-in; the provider itself is read from .env by the
live_env fixture in conftest.py (which also undoes the default suite's
MYNX_LLM_ENABLED=0 pin for the duration of this module). Without the opt-in
the tests skip, so a configured .env alone never spends free-tier quota.

Why characterization and not TDD
────────────────────────────────
These exist to A/B prompt edits: they must pass against the *current* prompts
before a rewrite lands, and pass again after. "The compressed prompt did not
lose quality" has no meaningful red state, so there is no failing-first step
here. A test that fails at baseline is reporting a pre-existing weakness in the
prompt, not a bug in the change -- record it, do not tune the assertion until
it goes green.

What these validate
───────────────────
- generate_turn returns the full schema with every field in range
- jean_options are three distinctly-toned, correctly-sized replies
- the opening line honours its extra constraints (zero deltas, no greeting)
- loquacity_delta is negative for an ordinary exchange (conversation costs)
- an offensive line is actually scored as offensive and costs reputation
- options do not echo the conversation history back at the player
- generate_personality returns a usable, in-world personality seed

Live calls are expensive against a rate-limited free tier, so each scenario is
a module-scoped fixture making ONE call that many assertions then read.
"""

import os
import time

import pytest

# ---------------------------------------------------------------------------
# Skip entire module if NPC chat LLM is not configured
# ---------------------------------------------------------------------------


# Opt-in gate. Duplicated (rather than imported from conftest) because
# tests/integration has no __init__.py, so a relative import fails at
# collection; a two-line env read is not worth adding a package for.
def _live_llm_enabled() -> bool:
    return os.getenv("HOV_LIVE_LLM", "0") in ("1", "true", "True")


# real_sleep: the suite-wide autouse fixture no-ops time.sleep, which would
# silently collapse _retry's widening backoff into a hammer against a
# rate-limited free tier.
pytestmark = [
    pytest.mark.real_sleep,
    pytest.mark.skipif(
        not _live_llm_enabled(),
        reason="set HOV_LIVE_LLM=1 to run live NPC chat tests",
    ),
]

TONES = ["direct", "guarded", "open"]
QUALITIES = {"positive", "neutral", "negative", "offensive"}


# ---------------------------------------------------------------------------
# Fixtures — one live call each, shared across the assertions below
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def adapter():
    from ai.llm_client import NpcChatLLMAdapter
    a = NpcChatLLMAdapter()
    if not a.enabled or not a.available():
        pytest.skip("NPC chat LLM provider is not reachable")
    return a


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHAT_CONFIG = os.path.join(REPO_ROOT, "ai", "npc", "human", "mara.json")


@pytest.fixture(scope="module")
def system_prompt():
    """The real system prompt for a story NPC, built by the real builder."""
    from src.npc._chat_llm import ConversationalNPCMixin

    class _Universe:
        def __init__(self):
            self.story = {"chapter": "3", "gorran_language_stage": "0"}

    class _Player:
        def __init__(self):
            self.universe = _Universe()

    class _NPC(ConversationalNPCMixin):
        pass

    npc = _NPC()
    npc._chat_config_path = CHAT_CONFIG
    npc._init_chat_attrs()
    return npc._build_system_prompt(_Player())


HISTORY = [
    {"npc": "You're not from the east bank. The boots give it away.",
     "jean": "They've carried me further than I'd like. Is there water near here?"},
    {"npc": "Three days east, if the spring hasn't turned. If it has, you walk.",
     "jean": "And if I don't have three days in me?"},
]


def _retry(method, *args, retries=3, **kwargs):
    """Call a bound adapter method, retrying an empty response (models are flaky).

    A free-tier model intermittently returns nothing at all; that is a provider
    hiccup, not a prompt regression, and failing the suite on it would make
    these tests useless as an A/B signal. Observed once in four full runs, where
    three back-to-back attempts all came back empty -- and because these are
    module-scoped fixtures, that one hiccup errored every test downstream of it.
    Hence four attempts on a widening backoff (3s, 6s, 12s), which is only ever
    paid on the failing path.
    """
    for attempt in range(retries + 1):
        res = method(*args, **kwargs)
        if res:
            return res
        if attempt < retries:
            time.sleep(3 * 2 ** attempt)
    pytest.fail("%s returned nothing after %d attempts"
                % (method.__name__, retries + 1))


@pytest.fixture(scope="module")
def opening(adapter, system_prompt):
    return _retry(adapter.generate_turn, system_prompt, [], is_opening=True)


@pytest.fixture(scope="module")
def normal(adapter, system_prompt):
    return _retry(adapter.generate_turn, system_prompt, HISTORY, is_opening=False,
                  jean_text="I can pay for a guide, if you know anyone willing.")


@pytest.fixture(scope="module")
def offensive(adapter, system_prompt):
    return _retry(adapter.generate_turn, system_prompt, HISTORY, is_opening=False,
                  jean_text="You people are filthy scavengers and I wouldn't trust "
                            "a word out of your mouth.")


@pytest.fixture(scope="module")
def personality(adapter):
    return _retry(adapter.generate_personality, "weathered nomad herder")


# ---------------------------------------------------------------------------
# Structural contract — must hold for every turn regardless of scenario
# ---------------------------------------------------------------------------

class TestTurnStructure:
    """generate_turn must return the full schema, correctly typed and in range."""

    @pytest.mark.parametrize("scenario", ["opening", "normal", "offensive"])
    def test_required_keys_present(self, scenario, request):
        turn = request.getfixturevalue(scenario)
        for key in ("npc_text", "conversation_quality", "reputation_delta",
                    "loquacity_delta", "jean_options"):
            assert key in turn, "Missing %s in %s: %s" % (key, scenario, turn)

    @pytest.mark.parametrize("scenario", ["opening", "normal", "offensive"])
    def test_npc_text_is_nonempty_prose(self, scenario, request):
        text = request.getfixturevalue(scenario)["npc_text"]
        assert isinstance(text, str) and text.strip(), "Empty npc_text in %s" % scenario
        assert not text.strip().startswith("{"), "npc_text leaked JSON: %r" % text

    @pytest.mark.parametrize("scenario", ["opening", "normal", "offensive"])
    def test_quality_in_allowed_set(self, scenario, request):
        q = request.getfixturevalue(scenario)["conversation_quality"]
        assert q in QUALITIES, "Bad conversation_quality in %s: %r" % (scenario, q)

    @pytest.mark.parametrize("scenario", ["opening", "normal", "offensive"])
    def test_deltas_are_ints_in_range(self, scenario, request):
        turn = request.getfixturevalue(scenario)
        rep = turn["reputation_delta"]
        assert isinstance(rep, int), "reputation_delta not int: %r" % rep
        assert -5 <= rep <= 5, "reputation_delta out of range in %s: %s" % (scenario, rep)
        # Bounds come from the prompt itself: it caps positives at +8 and
        # floors deep offense at -25..-35, so -40 is that floor plus slack.
        loq = turn.get("loquacity_delta", 0)
        assert isinstance(loq, int), "loquacity_delta not int: %r" % loq
        assert -40 <= loq <= 8, "loquacity_delta out of range in %s: %s" % (scenario, loq)

    @pytest.mark.parametrize("scenario", ["opening", "normal", "offensive"])
    def test_flavor_is_not_dialogue(self, scenario, request):
        """npc_flavor is third-person staging, never the spoken line repeated."""
        turn = request.getfixturevalue(scenario)
        flavor = turn.get("npc_flavor") or ""
        assert isinstance(flavor, str)
        if flavor.strip():
            assert '"' not in flavor, "npc_flavor contains quoted speech: %r" % flavor
            assert flavor.strip() != turn["npc_text"].strip(), \
                "npc_flavor duplicates npc_text"


class TestJeanOptions:
    """The three player replies carry the bulk of this prompt's instructions."""

    @pytest.mark.parametrize("scenario", ["opening", "normal", "offensive"])
    def test_exactly_three_options(self, scenario, request):
        opts = request.getfixturevalue(scenario)["jean_options"]
        assert isinstance(opts, list), "jean_options is not a list: %r" % type(opts)
        assert len(opts) == 3, "Expected 3 options in %s, got %d" % (scenario, len(opts))

    @pytest.mark.parametrize("scenario", ["opening", "normal", "offensive"])
    def test_tones_are_the_three_expected(self, scenario, request):
        opts = request.getfixturevalue(scenario)["jean_options"]
        assert sorted(o.get("tone") for o in opts) == sorted(TONES), \
            "Tones drifted in %s: %s" % (scenario, [o.get("tone") for o in opts])

    @pytest.mark.parametrize("scenario", ["opening", "normal", "offensive"])
    def test_option_lengths_are_reasonable(self, scenario, request):
        """Prompt asks for 8-20 words; allow slack but catch one-word or essays."""
        for o in request.getfixturevalue(scenario)["jean_options"]:
            words = len(str(o.get("text", "")).split())
            assert 4 <= words <= 32, \
                "Option in %s is %d words: %r" % (scenario, words, o.get("text"))

    @pytest.mark.parametrize("scenario", ["opening", "normal", "offensive"])
    def test_options_are_distinct(self, scenario, request):
        texts = [str(o.get("text", "")).strip().lower()
                 for o in request.getfixturevalue(scenario)["jean_options"]]
        assert len(set(texts)) == 3, "Duplicate options in %s: %s" % (scenario, texts)

    def test_options_do_not_echo_history(self, normal):
        """'no option may echo a line from the history above'."""
        prior = {ex["jean"].strip().lower() for ex in HISTORY}
        for o in normal["jean_options"]:
            assert str(o.get("text", "")).strip().lower() not in prior, \
                "Option echoed a history line: %r" % o.get("text")


# ---------------------------------------------------------------------------
# Behavioural contract — the parts of the prompt that carry game mechanics
# ---------------------------------------------------------------------------

class TestOpeningLineRules:
    """The opening turn has constraints no other turn has."""

    def test_deltas_are_zero(self, opening):
        """'For the opening line set reputation_delta and loquacity_delta to 0.'"""
        assert opening["reputation_delta"] == 0, \
            "Opening reputation_delta should be 0, got %s" % opening["reputation_delta"]
        assert opening.get("loquacity_delta", 0) == 0, \
            "Opening loquacity_delta should be 0, got %s" % opening.get("loquacity_delta")

    def test_does_not_open_with_a_greeting(self, opening):
        """'do not begin with Hello or Greetings'."""
        first = opening["npc_text"].strip().lstrip('"“').lower()
        assert not first.startswith(("hello", "greetings")), \
            "Opening began with a banned greeting: %r" % opening["npc_text"]


class TestConversationCosts:
    """loquacity and reputation are game resources, not decoration."""

    def test_ordinary_exchange_costs_loquacity(self, normal):
        """'Conversation costs energy, so it is USUALLY NEGATIVE (-3 to -12).'"""
        loq = normal.get("loquacity_delta", 0)
        assert loq < 0, "Ordinary exchange did not cost loquacity: %s" % loq

    def test_offensive_input_is_scored_as_hostile(self, offensive):
        assert offensive["conversation_quality"] in ("negative", "offensive"), \
            "Insult scored as %r" % offensive["conversation_quality"]

    def test_offensive_input_costs_reputation(self, offensive):
        assert offensive["reputation_delta"] < 0, \
            "Insult did not cost reputation: %s" % offensive["reputation_delta"]

    def test_offensive_input_costs_more_loquacity_than_a_civil_one(
            self, offensive, normal):
        """Deliberately <=, not <.

        Two sampled generations landing on the same delta is ordinary variance,
        not a prompt defect; a strict < would make this flaky for no signal. The
        assertion catches the case that matters -- an insult scored as *less*
        costly than a civil exchange.
        """
        assert offensive.get("loquacity_delta", 0) <= normal.get("loquacity_delta", 0), \
            "Insult (%s) cost no more loquacity than a civil line (%s)" % (
                offensive.get("loquacity_delta"), normal.get("loquacity_delta"))


class TestPersonalityGeneration:
    """One-shot seeding for generic nomads."""

    def test_has_every_required_key(self, personality):
        for key in ("given_name", "voice", "knowledge", "attitude_to_strangers",
                    "speech_sample", "loquacity_base"):
            assert key in personality, "Missing %s: %s" % (key, personality)

    def test_attitude_in_allowed_set(self, personality):
        assert personality["attitude_to_strangers"] in (
            "wary", "indifferent", "curious", "guarded"), \
            "Bad attitude: %r" % personality["attitude_to_strangers"]

    def test_loquacity_base_in_range(self, personality):
        base = personality["loquacity_base"]
        assert isinstance(base, int), "loquacity_base not int: %r" % base
        assert 40 <= base <= 90, "loquacity_base out of range: %s" % base

    def test_knowledge_is_two_topics(self, personality):
        k = personality["knowledge"]
        assert isinstance(k, list) and len(k) == 2, "Expected 2 topics, got %r" % k

    def test_speech_sample_is_a_line_not_a_description(self, personality):
        sample = str(personality["speech_sample"])
        assert 4 <= len(sample.split()) <= 30, "Odd speech_sample: %r" % sample


# ---------------------------------------------------------------------------
# State-implication guard — against a real model, not crafted strings
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def guard_npc():
    """A real story NPC wired for the guard, not just for prompt building."""
    from src.npc._chat_llm import ConversationalNPCMixin

    class _NPC(ConversationalNPCMixin):
        pass

    npc = _NPC()
    npc._chat_config_path = CHAT_CONFIG
    npc._init_chat_attrs()
    return npc


def _guarded(npc, adapter, system_prompt, turn):
    return npc._guard_turn(
        adapter,
        system_prompt,
        turn.get("npc_text", ""),
        turn.get("npc_flavor", "") or "",
        [dict(o) for o in (turn.get("jean_options") or [])],
    )


@pytest.fixture(scope="module")
def guarded_normal(guard_npc, adapter, system_prompt, normal):
    """One guard pass over the ``normal`` turn, shared by every assertion.

    Module-scoped on purpose: a tripped guard spends a real revise_turn call,
    and the free tier is 50 requests a day for the whole account. Per-test
    guarding burned four of those to answer one question.
    """
    return _guarded(guard_npc, adapter, system_prompt, normal)


@pytest.fixture(scope="module")
def guarded_offensive(guard_npc, adapter, system_prompt, offensive):
    return _guarded(guard_npc, adapter, system_prompt, offensive)


class TestStateImplicationGuard:
    """Nothing said in a chat reaches the engine, so nothing may imply it did.

    The unit suite proves the tripwire fires on strings we wrote. This proves
    the whole path holds on strings a real free-tier model wrote, including the
    escalation call, against a prompt deliberately fishing for an offer:
    ``normal`` asks "I can pay for a guide, if you know anyone willing."
    """

    def test_guarded_reply_implies_no_state_change(self, guard_npc, guarded_normal):
        from src.npc import _chat_guard as guard

        text, _flavor, _options = guarded_normal
        assert text.strip(), "guard returned an empty reply"
        flags = guard.scan_npc_text(text, guard_npc._guard_allowed_topics())
        assert flags == [], "state implication survived the guard: %r -> %s" % (
            text,
            [(f.category, f.match) for f in flags],
        )

    def test_guarded_options_solicit_nothing(self, guard_npc, guarded_normal):
        from src.npc import _chat_guard as guard

        _text, _flavor, options = guarded_normal
        assert len(options) == 3, "guard did not return three options: %r" % options
        for opt in options:
            flags = guard.scan_option_text(
                opt["text"], guard_npc._guard_allowed_topics()
            )
            assert flags == [], "soliciting option survived: %r -> %s" % (
                opt["text"],
                [(f.category, f.match) for f in flags],
            )

    def test_guarded_flavor_is_clean(self, guard_npc, guarded_normal):
        from src.npc import _chat_guard as guard

        _text, flavor, _options = guarded_normal
        if flavor:
            assert guard.scan_npc_text(flavor, guard_npc._guard_allowed_topics()) == []

    def test_offensive_turn_is_also_guarded(self, guard_npc, guarded_offensive):
        """A hostile exchange must not become an excuse to offer something."""
        from src.npc import _chat_guard as guard

        text, _flavor, _options = guarded_offensive
        assert guard.scan_npc_text(text, guard_npc._guard_allowed_topics()) == []

    def test_prevention_rule_reaches_the_model(self, system_prompt):
        """The prompt-side half of the guard is actually in the live prompt."""
        low = system_prompt.lower()
        assert "give" in low and "promise" in low
        assert "cannot see" in low


class TestProviderAnalyticsAreLive:
    """The saturation figures must come from real provider headers."""

    def test_usage_was_recorded_for_the_serving_provider(self, adapter, normal):
        from ai.llm_client import GenericLLMClient

        snapshot = GenericLLMClient.provider_saturation()
        providers = snapshot["providers"]
        assert providers, "no provider usage recorded across the live calls"
        assert any(s.get("requests", 0) > 0 for s in providers.values())

    def test_a_reported_limit_is_a_sane_fraction(self, adapter, normal):
        from ai.llm_client import GenericLLMClient

        snapshot = GenericLLMClient.provider_saturation()
        for name, stats in snapshot["providers"].items():
            saturation = stats.get("saturation")
            if saturation is None:
                continue
            assert 0.0 <= saturation <= 1.0, "%s reported %r" % (name, saturation)
            assert stats.get("limit") is None or stats["limit"] > 0

    def test_digest_builds_from_live_numbers(self, adapter, normal):
        import ai.provider_digest as digest
        from ai.llm_client import GenericLLMClient

        embed = digest.build_digest(GenericLLMClient.usage_snapshot())
        assert embed["fields"]
        blob = str(embed)
        assert "No provider calls recorded" not in blob
