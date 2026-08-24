"""Adversarial state-implication guard for LLM chat output.

Chat is lore and character exploration only: nothing said in a conversation is
wired to the engine. A line that hands Jean an item, promises an escort, claims
to see his belongings, or arranges a future meeting therefore writes a cheque
the game cannot cash, and the player is the one who finds out.

Design decisions under test (user-approved, 2026-08-21):

* Cheap tripwire on every turn; a real LLM revision call only when it trips.
* Four violation classes: hard transactions, trackable-state claims, soft
  future commitments, and Jean options that solicit any of the three.
* Deliberately injected state (the ally's own techniques and growth, Gorran's
  speech stage, the character's authored knowledge_scope) is whitelisted by
  explicit topic, not flagged.
* Soft commitments are defused into ambient fact rather than refused.
* When the revision call is unavailable or fails, a deterministic in-character
  hedge is spliced over the offending sentence — the turn still ships.
"""

import re

import pytest

from src.npc import _chat_guard as guard
from src.npc._chat_llm import ConversationalNPCMixin


def _npc(char_config=None, personality=None, growth=None, moves=None, world=None):
    class GuardNPC(ConversationalNPCMixin):
        def __init__(self):
            self.name = "Mara"
            self._chat_world_facts = world or {"allowed_proper_nouns": ["Mara", "Jean"]}
            self._chat_char_config = char_config
            self._chat_personality = personality
            self._chat_history = []
            self._prohibited_patterns = []
            self.growth_profile = growth
            self.known_moves = moves or []

    return GuardNPC()


class _Move:
    def __init__(self, name, description):
        self.name = name
        self.description = description


class _Adapter:
    """Minimal combined adapter double with a revise_turn hook."""

    enabled = True

    def __init__(self, revision=None, raises=False):
        self.revision = revision
        self.raises = raises
        self.calls = []

    def generate_turn(self, *a, **kw):  # presence marks a combined adapter
        raise AssertionError("generate_turn must not be called by the guard")

    def revise_turn(self, system_prompt, npc_text, jean_options, guidance):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "npc_text": npc_text,
                "jean_options": jean_options,
                "guidance": guidance,
            }
        )
        if self.raises:
            raise RuntimeError("provider exploded")
        return self.revision


def _opts(*texts):
    tones = ["direct", "guarded", "open"]
    return [{"tone": tones[i % 3], "text": t} for i, t in enumerate(texts)]


# ---------------------------------------------------------------------------
# Tripwire — hard transactions
# ---------------------------------------------------------------------------


class TestTransactionTripwire:
    @pytest.mark.parametrize(
        "line",
        [
            "Here, take this blade. It has served me well enough.",
            "I'll give you a knife for the crossing.",
            "Let me hand you some rope before you go.",
            "I can spare a little coin, if it helps.",
            "I'll come with you as far as the water.",
            "I'll follow you east and watch the ridge.",
            "Let me guide you through the caves.",
            "I could teach you that grip, if you like.",
            "Let me tend those cuts before you move on.",
        ],
    )
    def test_offers_are_flagged(self, line):
        flags = guard.scan_npc_text(line)
        assert flags, "expected a flag for: " + line
        assert flags[0].category == guard.CATEGORY_TRANSACTION

    def test_flag_reports_the_offending_sentence(self):
        line = "The river runs high this season. Here, take this blade."
        flags = guard.scan_npc_text(line)
        assert flags[0].sentence.strip() == "Here, take this blade."


# ---------------------------------------------------------------------------
# Tripwire — trackable-state claims
# ---------------------------------------------------------------------------


class TestStateClaimTripwire:
    @pytest.mark.parametrize(
        "line",
        [
            "That sword of yours has seen better days.",
            "Your armour is a poor fit for this country.",
            "You're wounded. Sit before you fall over.",
            "You're carrying too much for that crossing.",
            "Twelve coins is a fair price anywhere but here.",
            "You're low on rations, by the look of that pack.",
        ],
    )
    def test_claims_about_jeans_state_are_flagged(self, line):
        flags = guard.scan_npc_text(line)
        assert flags, "expected a flag for: " + line
        assert flags[0].category == guard.CATEGORY_STATE_CLAIM


# ---------------------------------------------------------------------------
# Tripwire — soft future commitments
# ---------------------------------------------------------------------------


class TestCommitmentTripwire:
    @pytest.mark.parametrize(
        "line",
        [
            "Come find me at dawn and we'll talk properly.",
            "Meet me by the ferry when the light goes.",
            "I'll be waiting when you come back this way.",
            "Ask me again once you've been east.",
            "Someday I could show you how it's done.",
        ],
    )
    def test_promises_are_flagged(self, line):
        flags = guard.scan_npc_text(line)
        assert flags, "expected a flag for: " + line
        assert flags[0].category in (
            guard.CATEGORY_COMMITMENT,
            guard.CATEGORY_TRANSACTION,
        )


# ---------------------------------------------------------------------------
# Tripwire — Jean options that solicit a state change
# ---------------------------------------------------------------------------


class TestSolicitTripwire:
    @pytest.mark.parametrize(
        "text",
        [
            "Will you come with me across the river?",
            "Can you spare a blade? Mine is failing.",
            "Teach me that grip before I go.",
            "Come with me. I could use the company.",
            "Give me the rope and I'll manage the rest.",
        ],
    )
    def test_soliciting_options_are_flagged(self, text):
        flags = guard.scan_option_text(text)
        assert flags, "expected a flag for: " + text
        assert flags[0].category == guard.CATEGORY_SOLICIT

    @pytest.mark.parametrize(
        "text",
        [
            "How long have you worked this crossing?",
            "You said the caves echo. Echo with what?",
            "That's a hard way to live. Why stay?",
        ],
    )
    def test_lore_options_pass(self, text):
        assert guard.scan_option_text(text) == []


# ---------------------------------------------------------------------------
# False positives — ordinary lore dialogue must survive untouched
# ---------------------------------------------------------------------------


class TestNoFalsePositives:
    @pytest.mark.parametrize(
        "line",
        [
            "The river's been high since the thaw. It takes people every spring.",
            "My father worked this bank before me, and his before that.",
            "Golemites don't sleep. That's the part that unsettles people.",
            "I gave a man a blade once. He used it badly.",
            "There's stew in the pot. There usually is.",
            "The Pillar Readers came through last winter, measuring stones.",
            "I've no love for the Conclave, but they keep records.",
            # _OFFER without a leading  matched word tails under
            # IGNORECASE ("will" contains "ill", "druid" contains "id").
            "The ferry will take you across.",
            "This path will lead you to the caves.",
            "Prayer will bring you peace.",
            "Time will mend it.",
            "Rest will heal you.",
            # Imperative-handover idioms with no object transfer.
            "Keep that in mind.",
            "I take it you have come about the ferry.",
        ],
    )
    def test_clean_lines_are_not_flagged(self, line):
        assert guard.scan_npc_text(line) == [], "false positive on: " + line


# ---------------------------------------------------------------------------
# Whitelist — deliberately injected state is legal
# ---------------------------------------------------------------------------


class TestAllowedTopics:
    def test_ally_own_techniques_are_not_flagged(self):
        npc = _npc(
            growth={"tier": "ally"},
            moves=[_Move("Rivercut", "a low sweeping strike")],
        )
        topics = npc._guard_allowed_topics()
        line = "I could teach you Rivercut, though it took me years to learn."
        assert guard.scan_npc_text(line, topics) == []

    def test_same_line_is_flagged_without_the_whitelist(self):
        line = "I could teach you Rivercut, though it took me years to learn."
        assert guard.scan_npc_text(line) != []

    def test_ally_growth_talk_is_not_flagged(self):
        npc = _npc(growth={"tier": "ally"})
        topics = npc._guard_allowed_topics()
        line = "I could teach you the way I hold a guard now."
        assert guard.scan_npc_text(line, topics) == []

    def test_knowledge_scope_topics_are_whitelisted(self):
        npc = _npc(char_config={"knowledge_scope": ["the ferry crossing and its tolls"]})
        topics = npc._guard_allowed_topics()
        assert any("ferry" in t for t in topics)

    def test_generic_npc_has_no_combat_topics(self):
        npc = _npc()
        topics = npc._guard_allowed_topics()
        assert not any("technique" in t for t in topics)


# ---------------------------------------------------------------------------
# Deterministic hedge — the guard-unavailable path
# ---------------------------------------------------------------------------


class TestDeterministicHedge:
    def test_offending_sentence_is_replaced_and_the_rest_kept(self):
        line = "The river runs high this season. Here, take this blade."
        flags = guard.scan_npc_text(line)
        hedged = guard.hedge_npc_text(line, flags)
        assert "The river runs high this season." in hedged
        assert "take this blade" not in hedged

    def test_commitment_hedge_is_ambient_not_a_refusal(self):
        line = "Come find me at dawn."
        flags = guard.scan_npc_text(line)
        hedged = guard.hedge_npc_text(line, flags)
        assert hedged != line
        assert "dawn" not in hedged.lower()

    def test_hedged_output_is_clean(self):
        for line in (
            "Here, take this blade.",
            "That sword of yours has seen better days.",
            "Come find me at dawn.",
            "I'll come with you.",
        ):
            flags = guard.scan_npc_text(line)
            hedged = guard.hedge_npc_text(line, flags)
            assert guard.scan_npc_text(hedged) == [], "hedge re-trips on: " + line
            assert hedged and hedged[-1] in ".!?"

    def test_hedge_without_flags_is_a_no_op(self):
        line = "The river runs high this season."
        assert guard.hedge_npc_text(line, []) == line


# ---------------------------------------------------------------------------
# _guard_turn — orchestration
# ---------------------------------------------------------------------------


class TestGuardTurn:
    def test_clean_turn_makes_no_llm_call(self):
        npc = _npc()
        adapter = _Adapter()
        text, flavor, options = npc._guard_turn(
            adapter,
            "SYSTEM",
            "The river runs high this season.",
            "She watches the far bank.",
            _opts(
                "How long have you worked this crossing?",
                "Why stay?",
                "Tell me about the water.",
            ),
        )
        assert adapter.calls == []
        assert text == "The river runs high this season."
        assert flavor == "She watches the far bank."
        assert len(options) == 3

    def test_dirty_turn_escalates_once_and_takes_the_revision(self):
        npc = _npc()
        adapter = _Adapter(
            revision={
                "npc_text": "The blade on that rack was my father's work.",
                "jean_options": _opts(
                    "Who taught him the trade?",
                    "That's a long time at one bench.",
                    "What happened to him?",
                ),
            }
        )
        text, _flavor, options = npc._guard_turn(
            adapter,
            "SYSTEM",
            "Here, take this blade.",
            "",
            _opts(
                "Will you come with me?",
                "Why stay here?",
                "Tell me about the river.",
            ),
        )
        assert len(adapter.calls) == 1
        assert text == "The blade on that rack was my father's work."
        assert all(guard.scan_option_text(o["text"]) == [] for o in options)

    def test_guidance_names_the_violated_categories(self):
        npc = _npc()
        adapter = _Adapter(revision=None)
        npc._guard_turn(
            adapter,
            "SYSTEM",
            "Here, take this blade.",
            "",
            _opts("Why stay?", "Go on.", "And then?"),
        )
        guidance = adapter.calls[0]["guidance"]
        assert guard.CATEGORY_TRANSACTION in guidance

    def test_revision_that_is_still_dirty_falls_back_to_the_hedge(self):
        npc = _npc()
        adapter = _Adapter(
            revision={"npc_text": "Fine — I'll give you my knife instead."}
        )
        text, _flavor, _options = npc._guard_turn(
            adapter,
            "SYSTEM",
            "Here, take this blade.",
            "",
            _opts("Why stay?", "Go on.", "And then?"),
        )
        assert guard.scan_npc_text(text) == []
        assert "knife" not in text
        # ONE escalation even when the revision comes back still dirty.
        assert len(adapter.calls) == 1

    def test_adapter_failure_falls_back_to_the_hedge(self):
        npc = _npc()
        adapter = _Adapter(raises=True)
        text, _flavor, _options = npc._guard_turn(
            adapter,
            "SYSTEM",
            "Here, take this blade.",
            "",
            _opts("Why stay?", "Go on.", "And then?"),
        )
        assert guard.scan_npc_text(text) == []
        # ONE escalation even when the reviser raises.
        assert len(adapter.calls) == 1

    def test_adapter_without_revise_turn_uses_the_hedge(self):
        npc = _npc()

        class Legacy:
            enabled = True

        text, _flavor, _options = npc._guard_turn(
            Legacy(),
            "SYSTEM",
            "Here, take this blade.",
            "",
            _opts("Why stay?", "Go on.", "And then?"),
        )
        assert guard.scan_npc_text(text) == []

    def test_no_adapter_at_all_still_guards(self):
        npc = _npc()
        text, _flavor, _options = npc._guard_turn(
            None,
            "SYSTEM",
            "Here, take this blade.",
            "",
            _opts("Why stay?", "Go on.", "And then?"),
        )
        assert guard.scan_npc_text(text) == []

    def test_soliciting_option_is_dropped_and_topped_up(self):
        npc = _npc()
        options = _opts(
            "Will you come with me across the river?",
            "How long have you worked this crossing?",
            "Why stay somewhere this hard?",
        )
        _text, _flavor, out = npc._guard_turn(
            None, "SYSTEM", "The river runs high.", "", options
        )
        assert len(out) == 3
        assert all(guard.scan_option_text(o["text"]) == [] for o in out)
        assert "come with me" not in " ".join(o["text"].lower() for o in out)

    def test_flavor_implying_a_transfer_is_dropped(self):
        npc = _npc()
        _text, flavor, _options = npc._guard_turn(
            None,
            "SYSTEM",
            "The river runs high.",
            "She presses a coin into your palm.",
            _opts("Why stay?", "Go on.", "And then?"),
        )
        assert flavor == ""

    def test_whitelisted_ally_line_does_not_escalate(self):
        npc = _npc(
            growth={"tier": "ally"},
            moves=[_Move("Rivercut", "a low sweeping strike")],
        )
        adapter = _Adapter()
        text, _flavor, _options = npc._guard_turn(
            adapter,
            "SYSTEM",
            "I could teach you Rivercut, though it took me years to learn.",
            "",
            _opts("Why that grip?", "Go on.", "And then?"),
        )
        assert adapter.calls == []
        assert "Rivercut" in text


# ---------------------------------------------------------------------------
# Prompt-side prevention
# ---------------------------------------------------------------------------


class TestPromptPrevention:
    def test_system_prompt_forbids_transactions(self, monkeypatch):
        npc = _npc()
        monkeypatch.setattr(npc, "_get_chapter", lambda player: "01")
        monkeypatch.setattr(
            npc, "_build_jean_context_block", lambda player, chapter: "CTX"
        )
        prompt = npc._build_system_prompt(object())
        low = prompt.lower()
        assert "give" in low and "promise" in low
        assert "cannot see" in low

# ---------------------------------------------------------------------------
# Adapter — the escalation call itself
# ---------------------------------------------------------------------------


class TestAdapterReviseTurn:
    def _adapter(self, raw, captured=None):
        import ai.llm_client as llm

        adapter = llm.NpcChatLLMAdapter.__new__(llm.NpcChatLLMAdapter)
        adapter.enabled = True

        def _call(system, user, **kw):
            if captured is not None:
                captured.append({"system": system, "user": user, "kw": kw})
            return raw

        adapter._call_llm = _call
        return adapter

    def test_parses_revision(self):
        adapter = self._adapter(
            '{"npc_text": "The rack by the door holds my work.", '
            '"jean_options": [{"tone":"direct","text":"Who taught you the trade?"},'
            '{"tone":"guarded","text":"Long time at one bench."},'
            '{"tone":"open","text":"What happened to him?"}]}'
        )
        result = adapter.revise_turn("sys", "Here, take this blade.", _opts("a", "b", "c"), "g")
        assert result["npc_text"] == "The rack by the door holds my work."
        assert len(result["jean_options"]) == 3
        assert result["jean_options"][0]["tone"] == "direct"

    def test_none_raw_returns_none(self):
        assert self._adapter(None).revise_turn("sys", "x", [], "g") is None

    def test_unparseable_returns_none(self):
        assert self._adapter("sorry, I cannot").revise_turn("sys", "x", [], "g") is None

    def test_guidance_and_draft_reach_the_prompt(self):
        captured = []
        adapter = self._adapter('{"npc_text": "Fine."}', captured)
        adapter.revise_turn(
            "SYSTEM",
            "Here, take this blade.",
            _opts("Will you come with me?", "b", "c"),
            "transaction: the character offered to give something.",
        )
        user = captured[0]["user"]
        assert "Here, take this blade." in user
        assert "Will you come with me?" in user
        assert "transaction:" in user

    def test_malformed_options_are_dropped_not_fatal(self):
        adapter = self._adapter(
            '{"npc_text": "Fine.", "jean_options": ["nope", {"text":"Go on."}]}'
        )
        result = adapter.revise_turn("sys", "x", [], "g")
        assert result["jean_options"] == [{"tone": "direct", "text": "Go on."}]


# ---------------------------------------------------------------------------
# Wiring — the guard actually runs on the player-facing path
# ---------------------------------------------------------------------------


class _WiredAdapter:
    enabled = True

    def __init__(self, npc_text, options, revision=None):
        self.npc_text = npc_text
        self.options = options
        self.revision = revision

    def generate_turn(self, system, history, is_opening=False, jean_text=None):
        return {
            "npc_text": self.npc_text,
            "npc_flavor": "",
            "conversation_quality": "neutral",
            "reputation_delta": 0,
            "loquacity_delta": -5,
            "jean_options": self.options,
        }

    def revise_turn(self, system, npc_text, jean_options, guidance):
        return self.revision


def _wired_npc(adapter):
    """An NPC with persistence and loquacity stubbed out, but the real chat path."""

    class WiredNPC(ConversationalNPCMixin):
        def __init__(self):
            self.name = "Mara"
            self._chat_world_facts = {"allowed_proper_nouns": ["Mara", "Jean"]}
            self._chat_char_config = None
            self._chat_personality = {"given_name": "Mara", "voice": "terse"}
            self._chat_history = []
            self._chat_npc_key = "mara"
            self._prohibited_patterns = []
            self.growth_profile = None
            self.known_moves = []
            self.loquacity_current = 80
            self.loquacity_max = 100
            self.loquacity_threshold = 10

        def _compute_loquacity(self, player):
            return None

        def _get_npc_key(self, player):
            return "mara"

        def _get_chapter(self, player):
            return "01"

        def _load_history_from_persistence(self, player):
            return None

        def _save_exchange_to_persistence(self, player, npc, jean, tick, chapter):
            return None

        def _ensure_personality(self, player):
            return None

        def _get_adapter(self):
            return adapter

    return WiredNPC()


class _Player:
    universe = None

    def __init__(self):
        self.reputation = {}


class TestChatPathWiring:
    def test_chat_open_hedges_a_state_implying_opening(self):
        adapter = _WiredAdapter(
            "You look half-dead. Here, take this blade.",
            _opts("Will you come with me?", "Why stay?", "Tell me about the river."),
        )
        result = _wired_npc(adapter).chat_open(_Player())
        assert result["success"] is True
        assert "take this blade" not in result["npc_opening"]
        assert guard.scan_npc_text(result["npc_opening"]) == []
        assert len(result["jean_options"]) == 3
        assert all(guard.scan_option_text(o["text"]) == [] for o in result["jean_options"])

    def test_chat_open_leaves_a_clean_opening_alone(self):
        adapter = _WiredAdapter(
            "River's high. It usually is, this time of year.",
            _opts("How long have you worked it?", "Why stay?", "Tell me about the water."),
        )
        result = _wired_npc(adapter).chat_open(_Player())
        assert result["npc_opening"] == "River's high. It usually is, this time of year."

    def test_chat_respond_hedges_a_state_implying_reply(self):
        adapter = _WiredAdapter(
            "I'll come with you across the water.",
            _opts("Why stay?", "Go on.", "Tell me about the river."),
        )
        result = _wired_npc(adapter).chat_respond(_Player(), "What's across the river?", "direct")
        assert result["success"] is True
        assert guard.scan_npc_text(result["npc_response"]) == []

    def test_chat_respond_prefers_a_clean_revision_over_the_hedge(self):
        adapter = _WiredAdapter(
            "Here, take this blade.",
            _opts("Why stay?", "Go on.", "Tell me about the river."),
            revision={"npc_text": "The rack by the door holds my father's work."},
        )
        result = _wired_npc(adapter).chat_respond(_Player(), "Nice blade.", "direct")
        assert result["npc_response"] == "The rack by the door holds my father's work."

# ---------------------------------------------------------------------------
# Feedback loop — the guarded text is what re-enters the next prompt
# ---------------------------------------------------------------------------


class _HistoryCapturingAdapter(_WiredAdapter):
    """Records the history list handed to each generate_turn call."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.histories = []

    def generate_turn(self, system, history, is_opening=False, jean_text=None):
        self.histories.append([dict(row) for row in history])
        return super().generate_turn(system, history, is_opening, jean_text)


def _persisting_npc(adapter):
    """Like _wired_npc but with the real persistence read/write path."""

    class PersistingNPC(ConversationalNPCMixin):
        def __init__(self):
            self.name = "Mara"
            self._chat_world_facts = {"allowed_proper_nouns": ["Mara", "Jean"]}
            self._chat_char_config = None
            self._chat_personality = {"given_name": "Mara", "voice": "terse"}
            self._chat_history = []
            self._chat_npc_key = "mara"
            self._prohibited_patterns = []
            self.growth_profile = None
            self.known_moves = []
            self.loquacity_current = 80
            self.loquacity_max = 100
            self.loquacity_threshold = 10
            self.loquacity_recovery = 2

        def _compute_loquacity(self, player):
            return None

        def _get_npc_key(self, player):
            return self._chat_npc_key

        def _get_chapter(self, player):
            return "01"

        def _ensure_personality(self, player):
            return None

        def _get_adapter(self):
            return adapter

    return PersistingNPC()


class _PersistPlayer:
    def __init__(self):
        self.npc_chat_histories = {}
        self.reputation = {}
        self.universe = None


class TestGuardedTextIsWhatPersists:
    def test_persisted_row_holds_the_guarded_line_not_the_raw_one(self):
        adapter = _WiredAdapter(
            "Here, take this blade.",
            _opts("Why stay?", "Go on.", "Tell me about the river."),
        )
        npc = _persisting_npc(adapter)
        player = _PersistPlayer()

        result = npc.chat_open(player)

        saved = player.npc_chat_histories["mara"]["exchanges"][-1]["npc"]
        assert saved == result["npc_opening"]
        assert "take this blade" not in saved
        assert guard.scan_npc_text(saved) == []

    def test_next_turn_prompt_never_sees_the_raw_line(self):
        adapter = _HistoryCapturingAdapter(
            "Here, take this blade.",
            _opts("Why stay?", "Go on.", "Tell me about the river."),
        )
        npc = _persisting_npc(adapter)
        player = _PersistPlayer()

        npc.chat_open(player)
        npc.chat_respond(player, "Where does the road go?", "direct")

        # Two generation calls; the second must have been handed the hedged
        # opening, never the offer that was intercepted.
        assert len(adapter.histories) == 2
        replayed = " ".join(
            row.get("npc", "") for row in adapter.histories[1]
        )
        assert "take this blade" not in replayed
        assert guard.scan_npc_text(replayed) == []

    def test_persisted_reply_is_guarded_too(self):
        adapter = _WiredAdapter(
            "I'll come with you as far as the water.",
            _opts("Why stay?", "Go on.", "Tell me about the river."),
        )
        npc = _persisting_npc(adapter)
        player = _PersistPlayer()

        npc.chat_open(player)
        result = npc.chat_respond(player, "What is across the water?", "direct")

        rows = player.npc_chat_histories["mara"]["exchanges"]
        assert result["npc_response"] == rows[-1]["npc"]
        assert all(guard.scan_npc_text(row.get("npc", "")) == [] for row in rows)


# ---------------------------------------------------------------------------
# Review-gate regressions (2026-08-21 code-review pass)
#
# Each test below pins a defect the review found in the first cut of the guard.
# They are the "fails without the fix" half of the review-gate carve-out.
# ---------------------------------------------------------------------------


class TestTopicMatchingIsWholeWord:
    """A short topic must not excuse any word that merely contains it.

    knowledge_scope entries are reduced to their content words, so a scope
    mentioning "a good edge" yielded the topic "edge" — which, matched as a
    substring, excused every sentence containing "knowledge" and disabled the
    teaching tripwire for that character entirely.
    """

    def test_substring_of_a_longer_word_does_not_excuse(self):
        line = "I could teach you knowledge of the old roads."
        assert guard.scan_npc_text(line, {"edge"}) != []

    def test_whole_word_topic_still_excuses(self):
        line = "I could teach you the Rivercut, given years."
        assert guard.scan_npc_text(line, {"rivercut"}) == []

    def test_multiword_topic_still_excuses_as_a_phrase(self):
        line = "I could teach you the river cut, given years."
        assert guard.scan_npc_text(line, {"river cut"}) == []

    def test_generic_knowledge_scope_words_are_not_topics(self):
        npc = _npc(
            char_config={"knowledge_scope": ["what people will and will not tell you"]}
        )
        topics = npc._guard_allowed_topics()
        assert "will" not in topics
        assert "people" not in topics
        assert "tell" not in topics

    def test_jean_is_never_a_topic(self):
        npc = _npc(char_config={"knowledge_scope": ["how Jean carries himself"]})
        assert "jean" not in npc._guard_allowed_topics()


class TestOptionScanIgnoresSecondPersonStateClaims:
    """In Jean's mouth "you/your" means the NPC, not Jean.

    The state_claim patterns exist to catch an NPC guessing at Jean's gear and
    wounds; applied to Jean's own options they fired on ordinary lore questions
    and got them dropped and replaced with generic pool filler.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "Where did you get your sword?",
            "You're wounded. Should you be working at all?",
            "That armour of yours is old work. Who made it?",
            "You're carrying more than a ferryman needs.",
        ],
    )
    def test_questions_about_the_npcs_own_things_pass(self, text):
        assert guard.scan_option_text(text) == []

    def test_the_same_lines_still_flag_in_the_npcs_mouth(self):
        assert guard.scan_npc_text("You're wounded. Sit down.") != []

    def test_game_terms_are_still_caught_in_an_option(self):
        assert guard.scan_option_text("How many experience points was that?") != []


class TestHedgeDropsPunctuationOnlyFragments:
    def test_trailing_quote_fragment_is_not_kept(self):
        line = "Here, take this blade.’"
        hedged = guard.hedge_npc_text(line, guard.scan_npc_text(line))
        assert "’" not in hedged
        assert hedged == "That's not mine to give."

    def test_interior_fragment_does_not_produce_stray_punctuation(self):
        line = "We will be here.’ Here, take this blade."
        hedged = guard.hedge_npc_text(line, guard.scan_npc_text(line))
        assert " ’." not in hedged
        assert hedged.endswith(".")


class TestAuthoredFallbackLinesAreNotGuarded:
    """Hand-written fallback dialogue is canon; the tripwire does not judge it.

    An authored closing line like "come back when you need something sharpened"
    trips the tripwire, and replacing an author's line with a generic hedge is
    strictly worse than letting it stand.
    """

    def _authored_npc(self, adapter):
        npc = _wired_npc(adapter)
        npc._chat_char_config = {
            "conversation_starters_by_chapter": {
                "01": ["Come back when you need something sharpened."]
            },
            "closing_lines_when_exhausted": ["Mind the forge."],
        }
        return npc

    def test_authored_opening_survives_verbatim(self):
        class DeadAdapter:
            enabled = True

            def __init__(self):
                self.revise_calls = 0

            def generate_turn(self, *a, **kw):
                return None

            def revise_turn(self, *a, **kw):
                self.revise_calls += 1
                return None

        adapter = DeadAdapter()
        result = self._authored_npc(adapter).chat_open(_Player())

        assert result["npc_opening"] == "Come back when you need something sharpened."
        assert adapter.revise_calls == 0
        # Proof the line really would have tripped the guard.
        assert guard.scan_npc_text(result["npc_opening"]) != []


class TestRevisionGoesThroughTheNormalQC:
    """The reviser's output has never seen the QC pipeline the generator's has."""

    def test_invented_noun_in_a_revision_is_repaired(self):
        npc = _npc()
        adapter = _Adapter(revision={"npc_text": "The rack was forged by Xanthus."})
        text, _flavor, _options = npc._guard_turn(
            adapter,
            "SYSTEM",
            "Here, take this blade.",
            "",
            _opts("Why stay?", "Go on.", "And then?"),
        )
        assert "Xanthus" not in text
        assert guard.scan_npc_text(text) == []

    def test_meta_speech_in_a_revised_option_is_dropped(self):
        npc = _npc()
        adapter = _Adapter(
            revision={
                "npc_text": "The rack by the door holds my work.",
                "jean_options": [
                    {"tone": "direct", "text": "[Option 1] Who taught you?"},
                    {"tone": "guarded", "text": "That is a long time at one bench."},
                    {"tone": "open", "text": "What happened to him?"},
                ],
            }
        )
        _text, _flavor, options = npc._guard_turn(
            adapter,
            "SYSTEM",
            "Here, take this blade.",
            "",
            _opts("Will you come with me?", "Go on.", "And then?"),
        )
        assert len(options) == 3
        assert not any("[Option" in o["text"] for o in options)

    def test_overlong_revised_option_is_dropped(self):
        npc = _npc()
        adapter = _Adapter(
            revision={
                "npc_text": "The rack by the door holds my work.",
                "jean_options": [{"tone": "direct", "text": "x" * 200}],
            }
        )
        _text, _flavor, options = npc._guard_turn(
            adapter,
            "SYSTEM",
            "The river runs high.",
            "",
            _opts("Will you come with me?", "Go on.", "And then?"),
        )
        assert len(options) == 3
        assert all(len(o["text"]) <= 160 for o in options)


class TestFlavorOnlyFlagDoesNotEscalate:
    """Flagged flavor is dropped, never rewritten — so it is not worth a call."""

    def test_no_llm_call_when_only_the_flavor_trips(self):
        npc = _npc()
        adapter = _Adapter()
        text, flavor, options = npc._guard_turn(
            adapter,
            "SYSTEM",
            "The river runs high this season.",
            "She presses a coin into your palm.",
            _opts("Why stay?", "Go on.", "And then?"),
        )
        assert adapter.calls == []
        assert flavor == ""
        assert text == "The river runs high this season."
        assert len(options) == 3

    def test_a_line_flag_alongside_a_flavor_flag_still_escalates(self):
        npc = _npc()
        adapter = _Adapter(revision=None)
        npc._guard_turn(
            adapter,
            "SYSTEM",
            "Here, take this blade.",
            "She presses a coin into your palm.",
            _opts("Why stay?", "Go on.", "And then?"),
        )
        assert len(adapter.calls) == 1


# ---------------------------------------------------------------------------
# Scrub regressions — whitelist limits, hedge fidelity, reviser hardening
# ---------------------------------------------------------------------------


class TestWhitelistNeverExcusesTransactions:
    def test_whitelisted_topic_does_not_license_a_handover(self):
        # The module docstring's own example: a knowledge_scope entry must
        # never excuse "I'll give you a knife for the crossing".
        topics = {"the ferry crossing", "crossing", "ferry"}
        assert guard.scan_npc_text(
            "I'll give you a knife for the crossing.", topics
        ) != []

    def test_whitelisted_topic_does_not_license_a_rendezvous(self):
        topics = {"the ferry crossing", "crossing"}
        assert guard.scan_npc_text(
            "Meet me at the crossing at dawn.", topics
        ) != []


class TestMultiwordTopicWholeWord:
    def test_phrase_topic_does_not_excuse_a_substring(self):
        # "river cut" must not excuse "driver cutlass".
        line = "I could teach you about the driver cutlass trick."
        assert guard.scan_npc_text(line, ["river cut"]) != []

    def test_phrase_topic_still_excuses_the_phrase(self):
        line = "I could teach you the river cut."
        assert guard.scan_npc_text(line, ["river cut"]) == []


class TestHedgePreservesLegitimateRepeats:
    def test_repeated_clean_sentence_survives_hedging(self):
        text = "No. No. Here, take this blade."
        flags = guard.scan_npc_text(text)
        assert guard.hedge_npc_text(text, flags) == (
            "No. No. That's not mine to give."
        )


class TestReviserReturnHardening:
    def test_non_dict_revision_falls_back_to_the_hedge(self):
        class WeirdAdapter(_Adapter):
            def revise_turn(self, system_prompt, npc_text, jean_options, guidance):
                self.calls.append({"guidance": guidance})
                return "not a dict at all"

        npc = _npc()
        adapter = WeirdAdapter()
        text, _flavor, options = npc._guard_turn(
            adapter,
            "SYSTEM",
            "Here, take this blade.",
            "",
            _opts("Why stay?", "Go on.", "And then?"),
        )
        assert guard.scan_npc_text(text) == []
        assert len(options) == 3


class TestGuardedOptionsSalvageOriginals:
    def test_clean_originals_survive_a_partial_revision(self):
        # One soliciting option trips the guard; the reviser returns a single
        # clean replacement. The two clean ORIGINAL options are context-aware
        # and must survive alongside it instead of generic pool fillers.
        npc = _npc()
        adapter = _Adapter(
            revision={
                "npc_text": "The river takes what it takes.",
                "jean_options": [
                    {"tone": "direct", "text": "What does the river take?"}
                ],
            }
        )
        options = _opts(
            "Will you give me your blade?",
            "Tell me about the river's moods.",
            "Who else works this bank with you?",
        )
        _text, _flavor, rebuilt = npc._guard_turn(
            adapter, "SYSTEM", "Here, take this blade.", "", options
        )
        texts = [o["text"] for o in rebuilt]
        assert len(rebuilt) == 3
        assert "Tell me about the river's moods." in texts
        assert "Who else works this bank with you?" in texts
