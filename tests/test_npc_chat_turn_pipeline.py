"""Regression tests for the LLM-chat turn pipeline (2026-08-28 review pass).

The pipeline is one chat turn's journey through ``src/npc/_chat_llm.py``: the
provider budget it is given, the QC passes that repair or reject the model's
text, the option list it hands back, the loquacity it charges for, and the
``ai.llm_client`` constants the whole thing is measured against. Each class
below is named for the behaviour it pins, and every one of them shipped broken:

* the whole-turn provider budget was a hardcoded 12s compared against an
  operator-tunable per-call timeout, so a timeout of 12s or more silently
  disabled the QC retry, the state-guard revision and the legacy options call
  — while logging that the budget was spent;
* a slang or prohibited span removed mid-line left a doubled period behind;
* Jean's option tones were defaulted on a source position that production never
  reached, so a dropped option shipped two replies labelled the same;
* the player's line reached the neutraliser unbounded;
* the leading-ellipsis repair dropped the space after it;
* the last point every NPC line passes collapsed whitespace with ``\\s+``, the
  spelling ``ai/llm_client.py`` documents as insufficient, and Jean's options
  were spliced into a prompt with no neutralisation at all;
* a tripped turn kept a loquacity *gain*, buying itself more provider spend;
* the constants ``_chat_llm`` mirrors from ``ai.llm_client`` for the no-AI-stack
  install had nothing holding the two copies together.

The same review's two findings against ``src/npc/_chat_guard.py`` — the
subcategory tables keyed on a bare name, and the game-terms vocabulary written
twice — are pinned in ``tests/test_npc_chat_state_guard.py``, beside the rest
of that module's table-integrity tests. Its one remaining finding was a
map-data correction, which has no code path to pin and so has no test here.
"""

import ast
import time
from pathlib import Path

import pytest

import ai.llm_client as llm_client
from src.npc import _chat_llm
from src.npc._chat_llm import MAX_JEAN_TEXT_CHARS, JEAN_TONES
from tests._npc_fixtures import chat_player, make_turn, qc_npc, wired_chat_npc


def _npc(**overrides):
    return qc_npc(allowed_proper_nouns=[], **overrides)


# ---------------------------------------------------------------------------
# The turn budget scales with the timeout it is measured against
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
            make_turn("Okay, the ferry runs at dawn."),
            make_turn("The ferry runs at dawn. Mind the current."),
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
# A removed clause leaves one sentence terminator behind, not two
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
# A dropped option must not leave two replies wearing the same tone
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
# The player's line is bounded before the neutraliser sees it
# ---------------------------------------------------------------------------


class TestPlayerTextIsBoundedBeforeSanitising:
    def test_the_neutraliser_never_sees_more_than_the_engine_cap(self, monkeypatch):
        seen = []
        real = _chat_llm.neutralise_player_text

        def spy(text):
            seen.append(text)
            return real(text)

        monkeypatch.setattr(_chat_llm, "neutralise_player_text", spy)
        npc = wired_chat_npc(_WideTimeoutAdapter(make_turn("River's high.")))
        npc.chat_respond(chat_player(), "A" * 4000, "direct")
        assert seen and all(len(t) <= MAX_JEAN_TEXT_CHARS for t in seen)


# ---------------------------------------------------------------------------
# The leading-ellipsis repair keeps the dots AND the space after them
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
# Model text is neutralised, not merely whitespace-collapsed
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
# A tripped turn does not get to buy itself more conversation
# ---------------------------------------------------------------------------


class _GainAdapter:
    """Trips the transaction tripwire and asks for +15 loquacity in the same
    response. There is no reviser, so the turn is hedged deterministically."""

    enabled = True

    def __init__(self, npc_text, loquacity_delta):
        self.npc_text = npc_text
        self.loquacity_delta = loquacity_delta

    def generate_turn(self, system, history, is_opening=False, jean_text=None):
        return make_turn(
            self.npc_text,
            conversation_quality="positive",
            loquacity_delta=self.loquacity_delta,
        )


class TestTrippedTurnLoquacityGain:
    def test_a_gain_is_retracted_when_the_guard_trips(self):
        npc = wired_chat_npc(_GainAdapter("Here, take this blade.", 15))
        before = npc.loquacity_current
        npc.chat_respond(chat_player(), "Nice blade.", "direct")
        assert npc.loquacity_current <= before

    def test_a_gain_on_a_clean_turn_is_kept(self):
        npc = wired_chat_npc(_GainAdapter("River's high, as it always is.", 15))
        before = npc.loquacity_current
        npc.chat_respond(chat_player(), "How's the water?", "direct")
        assert npc.loquacity_current > before

    def test_a_drain_still_applies_on_a_tripped_turn(self):
        npc = wired_chat_npc(_GainAdapter("Here, take this blade.", -15))
        before = npc.loquacity_current
        npc.chat_respond(chat_player(), "Nice blade.", "direct")
        assert npc.loquacity_current == before - 15

    def test_the_retracted_number_is_what_gets_persisted(self):
        npc = wired_chat_npc(_GainAdapter("Here, take this blade.", 15), persist=True)
        player = chat_player(persist=True)
        before = npc.loquacity_current
        npc.chat_respond(player, "Nice blade.", "direct")
        stored = player.npc_chat_histories["mara"]["loquacity_current"]
        assert stored == npc.loquacity_current <= before


# ---------------------------------------------------------------------------
# The mirrored ai.llm_client constants cannot drift from their source
# ---------------------------------------------------------------------------


def _constant_import_guard():
    """The two halves of ``_chat_llm``'s ai.llm_client import guard.

    Returns ``(imported_names, fallback_literals)``. Read out of the source
    because only one half of a try/except is live at runtime, which is exactly
    why the two could drift unnoticed.
    """
    tree = ast.parse(Path(_chat_llm.__file__).read_text(encoding="utf-8"))
    # Module level only: the guarded import is a top-level try/except, and
    # walking the whole tree also picks up ordinary error handling inside
    # methods (``raw = None`` in _resolve_jean_options, for one).
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
    """``_chat_llm`` re-spells every conversation constant as a literal in its
    ``except ImportError`` block, which softens llm_client's claim that the
    prompt text and the clamp "cannot drift apart again". The guard is
    deliberate — the engine must import on a box with no AI stack — so these
    pin the two copies together instead of arguing for removing it.
    """

    def test_both_halves_name_the_same_constants(self):
        imported, fallbacks = _constant_import_guard()
        assert imported == set(fallbacks), (
            "every guarded import needs a fallback and vice versa; "
            "missing={} extra={}".format(
                sorted(imported - set(fallbacks)), sorted(set(fallbacks) - imported)
            )
        )

    def test_every_fallback_literal_matches_llm_client(self):
        _imported, fallbacks = _constant_import_guard()
        assert fallbacks, "the fallback block should assign the mirrored constants"
        for name, literal in sorted(fallbacks.items()):
            assert literal == getattr(llm_client, name), name

    def test_the_live_module_took_the_import_not_the_fallback(self):
        # If this fails the warning added alongside it should have fired, which
        # is the whole point of no longer degrading silently.
        assert _chat_llm.MAX_OPTION_CHARS == llm_client.MAX_OPTION_CHARS
