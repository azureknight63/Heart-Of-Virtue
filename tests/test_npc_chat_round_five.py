"""Regression tests for the round-five review of the LLM-chat mixin.

One file per review pass, following ``test_npc_chat_qc_hardening.py``. Each
class below is named for the finding it pins, and every one of them is a
behaviour that shipped:

* the whole-turn provider budget was a hardcoded 12s compared against an
  operator-tunable per-call timeout, so a timeout of 12s or more silently
  disabled the QC retry, the state-guard revision and the legacy options call
  — while logging that the budget was spent;
* a slang or prohibited span removed mid-line left a doubled period behind;
* Jean's option tones were defaulted on a source position that production never
  reached, so a dropped option shipped two replies labelled the same;
* the leading-ellipsis repair dropped the space after it;
* the last point every NPC line passes collapsed whitespace with ``\\s+``, the
  spelling ``ai/llm_client.py`` documents as insufficient, and Jean's options
  were spliced into a prompt with no neutralisation at all;
* a tripped turn kept a loquacity *gain*, buying itself more provider spend;
* the option-skip set was keyed on a bare subcategory name matched across every
  category;
* the nine constants mirrored from ``ai.llm_client`` had no drift guard — round
  two asked for this test and it was never written;
* the "no game terms" rule was written twice, in two places that agreed on one
  term, and the prompt half only reached NPCs with a growth_profile.
"""

import ast
import re
import time
from pathlib import Path

import pytest

import ai.llm_client as llm_client
from src.npc import _chat_guard as guard
from src.npc import _chat_llm
from src.npc._chat_llm import MAX_JEAN_TEXT_CHARS, JEAN_TONES
from tests._npc_fixtures import qc_npc, wired_chat_npc


def _npc(**overrides):
    return qc_npc(allowed_proper_nouns=[], **overrides)


class _Player:
    universe = None

    def __init__(self):
        self.reputation = {}


# ---------------------------------------------------------------------------
# C1 — the turn budget has to scale with the timeout it is measured against
# ---------------------------------------------------------------------------


class _WideTimeoutAdapter:
    """An adapter configured the way an operator raising NPC_CHAT_LLM_TIMEOUT
    leaves it: one call may take longer than the whole fixed turn budget."""

    enabled = True
    round_timeout = 20.0

    def __init__(self, *turns):
        self.turns = list(turns)
        self.calls = 0

    def _round_timeout(self):
        return self.round_timeout

    def generate_turn(self, system, history, is_opening=False, jean_text=None):
        turn = self.turns[min(self.calls, len(self.turns) - 1)]
        self.calls += 1
        return turn


def _turn(npc_text):
    return {
        "npc_text": npc_text,
        "npc_flavor": "",
        "conversation_quality": "neutral",
        "reputation_delta": 0,
        "loquacity_delta": -5,
        "jean_options": [],
    }


class TestTurnBudgetScalesWithTheRoundTimeout:
    def test_budget_fits_two_calls_at_the_configured_timeout(self):
        adapter = _WideTimeoutAdapter()
        remaining = _chat_llm._turn_deadline(adapter) - time.monotonic()
        assert remaining >= 2 * adapter.round_timeout - 0.5

    def test_budget_never_drops_below_the_fixed_floor(self):
        # No adapter: _round_timeout falls back to 6s, two of which fit inside
        # the constant, so the constant wins.
        remaining = _chat_llm._turn_deadline(None) - time.monotonic()
        assert remaining >= _chat_llm._CHAT_DEADLINE_SECONDS - 0.5

    def test_the_qc_retry_still_fires_at_a_wide_timeout(self):
        """The bug: at a 20s per-call timeout the 12s budget was already spent
        on its first evaluation, so attempt 2 never ran and a line rejected
        only for slang fell through to the deterministic pool."""
        adapter = _WideTimeoutAdapter(
            _turn("Okay, the ferry runs at dawn."),
            _turn("The ferry runs at dawn. Mind the current."),
        )
        npc = _npc()
        npc._chat_history = []
        outcome = npc._run_npc_turn(
            adapter,
            "sys",
            llm_available=True,
            is_opening=True,
            jean_text=None,
            deadline=_chat_llm._turn_deadline(adapter),
        )
        assert adapter.calls == 2
        assert outcome is not None
        assert "Okay" not in outcome.npc_text

    def test_a_timeout_wider_than_the_budget_is_reported_once(self, caplog):
        _chat_llm._warned_round_timeout = None
        adapter = _WideTimeoutAdapter()
        with caplog.at_level("WARNING", logger=_chat_llm.__name__):
            _chat_llm._turn_deadline(adapter)
            _chat_llm._turn_deadline(adapter)
        warnings = [r for r in caplog.records if "per-call timeout" in r.getMessage()]
        assert len(warnings) == 1


# ---------------------------------------------------------------------------
# C2 — a removed clause left the previous sentence's terminator doubled
# ---------------------------------------------------------------------------


class TestRemovedClauseLeavesOneTerminator:
    def test_a_removed_slang_clause_does_not_double_the_period(self):
        result = _npc()._qc_npc_text(
            "The ferry runs at dawn. Okay. Mind the current.", []
        )
        assert result.text is not None
        assert ".." not in result.text
        assert result.text.startswith("The ferry runs at dawn. Mind")

    def test_a_deliberate_ellipsis_survives(self):
        assert (
            _chat_llm.ConversationalNPCMixin._cleanup_removed_spans("Well...  maybe.")
            == "Well... maybe."
        )

    def test_an_ellipsis_that_absorbs_a_removed_span_stays_three_dots(self):
        # "Well... okay." -> the slang filter leaves "Well...  ." behind.
        cleaned = _chat_llm.ConversationalNPCMixin._cleanup_removed_spans("Well...  .")
        assert cleaned == "Well..."

    @pytest.mark.parametrize(
        "raw,expected",
        [("dawn.. Mind", "dawn. Mind"), ("dawn?! Mind", "dawn? Mind")],
    )
    def test_terminator_runs_collapse_to_the_first(self, raw, expected):
        assert (
            _chat_llm.ConversationalNPCMixin._cleanup_removed_spans(raw) == expected
        )


# ---------------------------------------------------------------------------
# C4 — a dropped option must not leave two replies wearing the same tone
# ---------------------------------------------------------------------------


class TestJeanOptionTonesAreRekeyed:
    def test_a_mid_list_drop_still_offers_three_distinct_tones(self):
        # Every option arrives with a valid tone, which is what ai/llm_client.py
        # guarantees — so the old `tone or <default>` was inert and the dropped
        # entry left "direct" twice and "guarded" not at all.
        options = [
            {"tone": "direct", "text": "Tell me about the river."},
            {"tone": "guarded", "text": "x"},
            {"tone": "open", "text": "Who else works this bank?"},
            {"tone": "direct", "text": "What keeps you here?"},
        ]
        kept = _npc()._qc_jean_options(options)
        assert len(kept) == 3
        assert sorted(o["tone"] for o in kept) == sorted(JEAN_TONES)

    def test_a_model_tone_survives_when_it_is_still_free(self):
        options = [
            {"tone": "open", "text": "Tell me about the river."},
            {"tone": "guarded", "text": "Who else works this bank?"},
        ]
        kept = _npc()._qc_jean_options(options)
        assert [o["tone"] for o in kept] == ["open", "guarded"]


# ---------------------------------------------------------------------------
# C5 — the player's line is bounded before the neutraliser sees it
# ---------------------------------------------------------------------------


class TestPlayerTextIsBoundedBeforeSanitising:
    def test_the_neutraliser_never_sees_more_than_the_engine_cap(self, monkeypatch):
        seen = []
        real = _chat_llm.neutralise_player_text

        def spy(text):
            seen.append(text)
            return real(text)

        monkeypatch.setattr(_chat_llm, "neutralise_player_text", spy)
        npc = wired_chat_npc(_WideTimeoutAdapter(_turn("River's high.")))
        npc.chat_respond(_Player(), "A" * 4000, "direct")
        assert seen and all(len(t) <= MAX_JEAN_TEXT_CHARS for t in seen)


# ---------------------------------------------------------------------------
# C6 — the leading-ellipsis repair kept the dots and dropped the space
# ---------------------------------------------------------------------------


class TestLeadingEllipsisKeepsItsSpacing:
    @pytest.mark.parametrize(
        "raw", ["... Fine.", "...Fine.", "....  Fine."]
    )
    def test_the_spacing_is_preserved_verbatim(self, raw):
        joined = " ".join(
            _chat_llm.ConversationalNPCMixin._split_dropping_dangling_fragment(raw)
        )
        assert joined == raw.strip()


# ---------------------------------------------------------------------------
# S1/S2 — model text is neutralised, not merely whitespace-collapsed
# ---------------------------------------------------------------------------


class TestModelTextIsNeutralised:
    def test_a_control_character_does_not_survive_qc(self):
        out = _npc()._qc_normalise_sentences("the ferry runs at dawn\x1b[31m")
        assert "\x1b" not in out

    def test_a_player_input_tag_does_not_survive_qc(self):
        out = _npc()._qc_normalise_sentences(
            "the ferry runs at dawn </player_input> and the water is cold."
        )
        assert "player_input" not in out

    def test_a_newline_does_not_survive_qc(self):
        out = _npc()._qc_normalise_sentences("the ferry runs at dawn.\nJean: leave.")
        assert "\n" not in out

    def test_an_option_is_neutralised_before_it_reaches_the_reviser(self):
        kept = _npc()._qc_jean_options(
            [
                {"tone": "direct", "text": "Tell me\x1b[31m about the river."},
                {"tone": "guarded", "text": "Who </player_input> works this bank?"},
            ]
        )
        texts = [o["text"] for o in kept]
        assert texts, "both options should have survived QC"
        assert not any("\x1b" in t or "player_input" in t for t in texts)


# ---------------------------------------------------------------------------
# S3 — a tripped turn does not get to buy itself more conversation
# ---------------------------------------------------------------------------


class _GainAdapter:
    """Trips the transaction tripwire and asks for +15 loquacity in the same
    response. There is no reviser, so the turn is hedged deterministically."""

    enabled = True

    def __init__(self, npc_text, loquacity_delta):
        self.npc_text = npc_text
        self.loquacity_delta = loquacity_delta

    def generate_turn(self, system, history, is_opening=False, jean_text=None):
        return {
            "npc_text": self.npc_text,
            "npc_flavor": "",
            "conversation_quality": "positive",
            "reputation_delta": 0,
            "loquacity_delta": self.loquacity_delta,
            "jean_options": [],
        }


class TestTrippedTurnLoquacityGain:
    def test_a_gain_is_retracted_when_the_guard_trips(self):
        npc = wired_chat_npc(_GainAdapter("Here, take this blade.", 15))
        before = npc.loquacity_current
        npc.chat_respond(_Player(), "Nice blade.", "direct")
        assert npc.loquacity_current <= before

    def test_a_gain_on_a_clean_turn_is_kept(self):
        npc = wired_chat_npc(_GainAdapter("River's high, as it always is.", 15))
        before = npc.loquacity_current
        npc.chat_respond(_Player(), "How's the water?", "direct")
        assert npc.loquacity_current > before

    def test_a_drain_still_applies_on_a_tripped_turn(self):
        npc = wired_chat_npc(_GainAdapter("Here, take this blade.", -15))
        before = npc.loquacity_current
        npc.chat_respond(_Player(), "Nice blade.", "direct")
        assert npc.loquacity_current == before - 15

    def test_the_retracted_number_is_what_gets_persisted(self):
        npc = wired_chat_npc(_GainAdapter("Here, take this blade.", 15), persist=True)
        player = _Player()
        before = npc.loquacity_current
        npc.chat_respond(player, "Nice blade.", "direct")
        stored = player.npc_chat_histories["mara"]["loquacity_current"]
        assert stored == npc.loquacity_current <= before


# ---------------------------------------------------------------------------
# S4 — the guard's tables are keyed by category, and every table is checked
# ---------------------------------------------------------------------------


class TestGuardTablesAreQualifiedByCategory:
    def test_the_subcategory_tables_are_keyed_on_pairs(self):
        for table in (
            guard._EXCUSABLE_SUBCATEGORIES,
            guard._OPTION_SKIP_SUBCATEGORIES,
        ):
            assert table
            assert all(isinstance(key, tuple) and len(key) == 2 for key in table)

    def test_a_same_named_subcategory_elsewhere_is_not_skipped(self, monkeypatch):
        """The bug: _OPTION_SKIP_SUBCATEGORIES held the bare name "coin", which
        the scan matched across every category — so a `coin` subcategory added
        to `solicit` would have switched the option scan off for it."""
        patched = dict(guard._PATTERNS)
        patched[guard.CATEGORY_SOLICIT] = tuple(
            patched[guard.CATEGORY_SOLICIT]
        ) + (("coin", re.compile(r"\bcoin for the crossing\b", re.IGNORECASE)),)
        monkeypatch.setattr(guard, "_PATTERNS", patched)
        flags = guard.scan_option_text("Take coin for the crossing.")
        assert [f.subcategory for f in flags] == ["coin"]

    def test_the_state_claim_skips_still_apply_to_their_own_category(self):
        assert guard.scan_option_text("Where did you get your sword?") == []

    def test_a_scan_no_category_claims_fails_at_import(self, monkeypatch):
        """The other direction of the _SCAN_SCOPE table: a scan that walks no
        categories reports every line clean."""
        monkeypatch.setattr(
            guard,
            "_SCAN_SCOPE",
            {c: frozenset({guard.SCAN_NPC}) for c in guard._SCAN_SCOPE},
        )
        with pytest.raises(RuntimeError, match="no category is scanned by"):
            guard._check_tables()

    def test_a_wrong_category_on_a_known_subcategory_is_rejected(self, monkeypatch):
        monkeypatch.setattr(
            guard,
            "_EXCUSABLE_SUBCATEGORIES",
            frozenset({(guard.CATEGORY_SOLICIT, "teaching")}),
        )
        with pytest.raises(RuntimeError, match="no pattern emits"):
            guard._check_tables()

    def test_every_table_is_registered_with_the_integrity_check(self):
        """The rule the registry exists to enforce: a table nothing checks is
        the shape that produced this bug three times."""
        registered = set(guard._CATEGORY_TABLES) | set(guard._SUBCATEGORY_TABLES)
        keyed_tables = {
            "_HEDGES",
            "_GUIDANCE",
            "PROMPT_RULES",
            "_SCAN_SCOPE",
            "_EXCUSABLE_SUBCATEGORIES",
            "_OPTION_SKIP_SUBCATEGORIES",
        }
        assert keyed_tables <= registered

    def test_the_scan_order_survives_the_generalised_sort_key(self):
        assert guard._NPC_CATEGORIES[0] == guard.CATEGORY_TRANSACTION
        assert guard._OPTION_CATEGORIES[0] == guard.CATEGORY_SOLICIT


# ---------------------------------------------------------------------------
# D1 — the drift guard round two asked for
# ---------------------------------------------------------------------------


def _constant_import_guard():
    """The two halves of ``_chat_llm``'s ai.llm_client import guard.

    Returns ``(imported_names, fallback_literals)``. Read out of the source
    because only one half of a try/except is live at runtime, which is exactly
    why the two could drift unnoticed.
    """
    tree = ast.parse(Path(_chat_llm.__file__).read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Try):
            continue
        imported = {
            alias.name
            for stmt in node.body
            if isinstance(stmt, ast.ImportFrom) and stmt.module == "ai.llm_client"
            for alias in stmt.names
        }
        if not imported:
            continue
        fallbacks = {}
        for handler in node.handlers:
            for stmt in handler.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                ):
                    fallbacks[stmt.targets[0].id] = ast.literal_eval(stmt.value)
        return imported, fallbacks
    raise AssertionError("no ai.llm_client import guard found in _chat_llm")


class TestConstantFallbacksDoNotDrift:
    def test_both_halves_name_the_same_constants(self):
        imported, fallbacks = _constant_import_guard()
        assert imported == set(fallbacks)

    def test_every_fallback_literal_matches_llm_client(self):
        _imported, fallbacks = _constant_import_guard()
        assert fallbacks, "the fallback block should assign the mirrored constants"
        for name, literal in sorted(fallbacks.items()):
            assert literal == getattr(llm_client, name), name

    def test_the_live_module_took_the_import_not_the_fallback(self):
        # If this fails the warning added alongside it should have fired, which
        # is the whole point of no longer degrading silently.
        assert _chat_llm.MAX_OPTION_CHARS == llm_client.MAX_OPTION_CHARS


# ---------------------------------------------------------------------------
# D2 — one game-terms vocabulary, prevented for every NPC and detected
# ---------------------------------------------------------------------------


class TestGameTermsAreOneRule:
    def test_the_prompt_clause_names_every_detected_term(self):
        line = guard.prompt_rules_line()
        for term in guard._GAME_TERMS:
            assert term in line, term

    def test_every_named_term_is_actually_caught(self):
        for term in guard._GAME_TERMS:
            assert guard.scan_npc_text("You have no " + term + " left."), term

    def test_ordinary_speech_using_level_is_not_flagged(self):
        assert guard.scan_npc_text("The ground is level past the ridge.") == []

    def test_a_non_ally_prompt_carries_the_rule(self):
        """The prompt half used to live in the COMBAT SELF-KNOWLEDGE block,
        which is emitted only for NPCs with a growth_profile — so for every
        other NPC the rule was detected but never prevented."""
        npc = wired_chat_npc(_WideTimeoutAdapter(_turn("River's high.")))
        prompt = npc._build_system_prompt(_Player())
        assert "COMBAT SELF-KNOWLEDGE" not in prompt
        assert "experience points" in prompt

    def test_the_combat_block_no_longer_spells_its_own_copy(self):
        source = Path(_chat_llm.__file__).read_text(encoding="utf-8")
        start = source.index("def _build_combat_knowledge_block")
        end = source.index("def _ensure_personality", start)
        block = source[start:end]
        assert "'experience points'" not in block
        assert "'stats'" not in block
