"""Regression tests for the LLM-chat QC hardening pass (2026-08-21).

Covers the confirmed player-visible failure modes found in the QC review:

* Multi-word allowlist entries ("Echoing Caves") were checked token-by-token
  against full strings, mangling legitimate lore names into "the they they".
* The sentence cap flattened every "!" and "?" into a period.
* Slang removal left grammatical holes (", I know") and the "you know?"
  blocklist alternative could never match at end of sentence.
* Prohibited phrases surfaced as a visible "[...]" artifact.
* Invented-noun substitution used "they" in object position ("he met they").
* Roleplay *asterisk actions* inside npc_text reached the player verbatim.
* A max_tokens-truncated JSON payload lost the entire turn.
* generate_plain leaked raw JSON to the caller when extraction failed.
* An unmatched mid-text <think> opener leaked chain-of-thought.

Policy changes under test (user-approved design decisions):

* Content violations reject on attempt 1 (retry carries corrective guidance to
  the model) and are rewritten in place on the final attempt.
* _qc_jean_options salvages valid options; _top_up_jean_options fills the set
  back to three from the fallback pool.
"""

import json
import re
import time

from src.npc._chat_llm import MAX_OPTION_CHARS, ConversationalNPCMixin
from ai.llm_client import NpcChatLLMAdapter, _JSONTools
from tests._npc_fixtures import chat_player, make_turn, qc_npc, wired_chat_npc


def _npc(allowed_nouns=None, personality=None, prohibited=None):
    """Thin adapter onto the shared ``qc_npc`` harness.

    Kept as a local name only because ~90 call sites in this file spell it, and
    because the harness takes ``allowed_proper_nouns=None`` to mean "no
    allow-list key at all" where this file has always meant "an empty one".
    """
    return qc_npc(
        allowed_proper_nouns=allowed_nouns or [],
        prohibited=[re.escape(p) for p in (prohibited or [])],
        _chat_personality=personality,
    )


# ---------------------------------------------------------------------------
# Invented-noun scan: allowlist matching
# ---------------------------------------------------------------------------


class TestAllowlistMatching:
    def test_multiword_allowed_noun_survives(self):
        npc = _npc(allowed_nouns=["Wailing Badlands", "Echoing Caves"])
        result = npc._qc_npc_text(
            "You'll find shelter in the Echoing Caves before nightfall.", []
        ).text
        assert "Echoing Caves" in result
        assert "they" not in result.split()

    def test_singular_of_allowed_plural_survives(self):
        npc = _npc(allowed_nouns=["Golemites"])
        result = npc._qc_npc_text("I once traded with a Golemite patrol.", []).text
        assert "Golemite" in result

    def test_plural_of_allowed_singular_survives(self):
        npc = _npc(allowed_nouns=["Grondite"])
        result = npc._qc_npc_text("Two of the Grondites passed through camp.", []).text
        assert "Grondites" in result

    def test_adjectival_extension_of_allowed_stem_survives(self):
        npc = _npc(allowed_nouns=["Grondia"])
        result = npc._qc_npc_text("He wore a fine Grondian cloak.", []).text
        assert "Grondian" in result

    def test_generic_npc_own_given_name_survives(self):
        npc = _npc(personality={"given_name": "Ren"})
        result = npc._qc_npc_text("Folk out here call me Ren, nothing more.", []).text
        assert "Ren" in result

    def test_invented_noun_replaced_grammatically(self):
        npc = _npc()
        result = npc._qc_npc_text("I met Kessa near the ford.", []).text
        assert "Kessa" not in result
        assert "someone" in result
        # Old bug: object-position "they" ("I met they")
        assert "met they" not in result

    def test_invented_place_replaced_with_that_place(self):
        npc = _npc()
        result = npc._qc_npc_text("The caravan set out for Vetheria at dawn.", []).text
        assert "Vetheria" not in result
        assert "that place" in result


# ---------------------------------------------------------------------------
# Punctuation preservation
# ---------------------------------------------------------------------------


class TestPunctuationPreservation:
    def test_questions_and_exclamations_survive_sentence_cap(self):
        npc = _npc()
        result = npc._qc_npc_text("What do you want? Stay back! I mean it.", []).text
        assert "?" in result
        assert "!" in result

    def test_ellipsis_preserved(self):
        npc = _npc()
        result = npc._qc_npc_text("Well... maybe you're right.", []).text
        assert "..." in result

    def test_sentence_cap_still_three(self):
        npc = _npc()
        result = npc._qc_npc_text("One! Two? Three. Four. Five.", []).text
        assert "Four" not in result
        assert result.startswith("One!")


# ---------------------------------------------------------------------------
# Slang and prohibited-phrase rewrites
# ---------------------------------------------------------------------------


class TestRewriteCleanup:
    def test_slang_removal_leaves_no_orphan_comma(self):
        npc = _npc()
        result = npc._qc_npc_text("Yeah, I know the road well.", []).text
        assert result is not None
        assert "Yeah" not in result
        assert not result.startswith(",")
        assert "  " not in result

    def test_you_know_question_form_removed(self):
        # The old pattern's trailing \b made "you know?" unmatchable at the
        # end of a sentence — its only realistic position.
        npc = _npc()
        result = npc._qc_npc_text("The road gets rough out west, you know?", []).text
        assert result is not None
        assert "you know" not in result.lower()

    def test_cool_as_temperature_is_not_slang(self):
        npc = _npc()
        cleaned, reason, _aside = npc._qc_npc_text(
            "The water runs cool under the bridge.", [], allow_rewrite=False
        )
        assert cleaned is not None, reason
        assert "cool" in cleaned

    def test_cool_as_interjection_is_slang(self):
        npc = _npc()
        cleaned, reason, _aside = npc._qc_npc_text(
            "That's cool, I suppose.", [], allow_rewrite=False
        )
        assert cleaned is None
        assert "slang" in reason

    def test_hyphenated_allowed_token_survives(self):
        # A hyphenated ALLOWLIST entry is split on "-" by _allowed_noun_tokens;
        # both halves must license the compound (a descriptive compound like
        # "East-bank" is separately covered by the _COMMON_CAP_WORDS rule).
        npc = _npc(allowed_nouns=["Kel-Thar"])
        result = npc._qc_npc_text("We crossed below Kel-Thar before dawn.", []).text
        assert "Kel-Thar" in result

    def test_descriptive_compound_survives_without_allowlist(self):
        npc = _npc()
        result = npc._qc_npc_text("We camped on the East-bank side of the river.", []).text
        assert "East-bank" in result

    def test_prohibited_phrase_removed_without_artifact(self):
        npc = _npc(prohibited=["forbidden"])
        result = npc._qc_npc_text("This forbidden word is gone now.", []).text
        assert result is not None
        assert "[...]" not in result
        assert "forbidden" not in result


# ---------------------------------------------------------------------------
# Strict mode (attempt 1) vs rewrite mode (final attempt)
# ---------------------------------------------------------------------------


class TestStrictMode:
    def test_strict_rejects_invented_noun_with_reason(self):
        npc = _npc()
        cleaned, reason, _aside = npc._qc_npc_text(
            "I saw Xanthor by the river.", [], allow_rewrite=False
        )
        assert cleaned is None
        assert "Xanthor" in reason

    def test_strict_rejects_slang_with_reason(self):
        npc = _npc()
        cleaned, reason, _aside = npc._qc_npc_text(
            "Yeah, the road is long.", [], allow_rewrite=False
        )
        assert cleaned is None
        assert "slang" in reason

    def test_rewrite_mode_salvages_same_text(self):
        npc = _npc()
        cleaned, reason, _aside = npc._qc_npc_text(
            "I saw Xanthor by the river.", [], allow_rewrite=True
        )
        assert cleaned is not None
        assert "Xanthor" not in cleaned
        assert reason is None

    def test_jean_dialogue_present_tense_rejected(self):
        npc = _npc()
        assert npc._qc_npc_text("Jean says he wants to leave.", []).text is None

    def test_jean_dialogue_rejected_in_both_modes(self):
        npc = _npc()
        for allow in (False, True):
            cleaned, _r, _a = npc._qc_npc_text(
                "Jean said hello to me today.", [], allow_rewrite=allow
            )
            assert cleaned is None


# ---------------------------------------------------------------------------
# Asterisk action asides
# ---------------------------------------------------------------------------


class TestActionAsides:
    def test_asides_stripped_from_spoken_text(self):
        npc = _npc()
        result = npc._qc_npc_text("*nods slowly* Fine. Have it your way.", []).text
        assert "*" not in result
        assert "nods slowly" not in result
        assert result.startswith("Fine.")

    def test_extract_returns_aside_text(self):
        npc = _npc()
        cleaned, _reason, aside = npc._qc_npc_text(
            "*shrugs* The road decides, not me.", []
        )
        assert aside == "shrugs"
        assert cleaned.startswith("The road")

    def test_markdown_bold_unwrapped_not_extracted(self):
        npc = _npc()
        result = npc._qc_npc_text("That is **not** a good idea.", []).text
        assert "*" not in result
        assert "not" in result

    def test_mid_sentence_emphasis_is_unwrapped_not_extracted(self):
        # Single-asterisk emphasis embedded between words is markdown
        # emphasis, not a stage direction — the word must stay in place.
        npc = _npc()
        cleaned, _reason, aside = npc._qc_npc_text(
            "I would *never* sell to them.", []
        )
        assert cleaned == "I would never sell to them."
        assert aside == ""

    def test_trailing_aside_extracted(self):
        npc = _npc()
        cleaned, _reason, aside = npc._qc_npc_text(
            "Suit yourself. *turns back to the fire*", []
        )
        assert cleaned == "Suit yourself."
        assert aside == "turns back to the fire"

    def test_spoken_text_capitalized_after_leading_aside(self):
        npc = _npc()
        cleaned, _reason, _aside = npc._qc_npc_text("*shrugs* fine, go.", [])
        assert cleaned.startswith("Fine")

    def test_run_npc_turn_relocates_aside_into_empty_flavor(self):
        class FakeAdapter:
            def generate_turn(self, system, history, is_opening=False, jean_text=None):
                return make_turn("*studies the horizon* Storm's coming.")

        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            FakeAdapter(), "sys", llm_available=True, is_opening=True, jean_text=None
        )
        assert turn is not None
        assert "*" not in turn.npc_text
        # The relocated aside is capitalized by the flavor QC pass.
        assert "studies the horizon" in turn.npc_flavor.lower()

    def test_model_supplied_flavor_takes_priority_over_aside(self):
        class FakeAdapter:
            def generate_turn(self, system, history, is_opening=False, jean_text=None):
                return make_turn(
                    "*sighs* So be it.",
                    npc_flavor="She turns away toward the fire.",
                )

        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            FakeAdapter(), "sys", llm_available=True, is_opening=True, jean_text=None
        )
        assert turn.npc_flavor == "She turns away toward the fire."


# ---------------------------------------------------------------------------
# Retry guidance
# ---------------------------------------------------------------------------


class TestRetryGuidance:
    def test_second_attempt_carries_rejection_reason(self):
        calls = []

        class FakeAdapter:
            def generate_turn(self, system, history, is_opening=False, jean_text=None):
                calls.append(system)
                if len(calls) == 1:
                    text = "I saw Xanthor by the river."
                else:
                    text = "The river runs cold this season."
                return make_turn(text)

        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            FakeAdapter(), "base system", llm_available=True,
            is_opening=True, jean_text=None,
        )
        assert turn.npc_text.startswith("The river")
        assert len(calls) == 2
        assert "[RETRY GUIDANCE]" not in calls[0]
        assert "[RETRY GUIDANCE]" in calls[1]
        assert "Xanthor" in calls[1]

    def test_final_attempt_rewrites_instead_of_falling_back(self):
        class FakeAdapter:
            def generate_turn(self, system, history, is_opening=False, jean_text=None):
                # Both attempts return the same invented-noun line.
                return make_turn("I saw Xanthor by the river.")

        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            FakeAdapter(), "sys", llm_available=True, is_opening=True, jean_text=None
        )
        # Salvaged in place on the final attempt — not dropped to fallback.
        # ("Xanthor" ends in -or, so the place-shaped replacement applies.)
        assert turn is not None
        assert "Xanthor" not in turn.npc_text
        assert "that place" in turn.npc_text


# ---------------------------------------------------------------------------
# Jean-option top-up
# ---------------------------------------------------------------------------


class TestJeanOptionTopUp:
    def test_partial_set_topped_up_to_three(self):
        npc = _npc()
        npc._chat_fallback_idx = 0
        kept = [
            {"tone": "direct", "text": "Where does the road lead?"},
            {"tone": "open", "text": "Tell me about the caves."},
        ]
        result = npc._top_up_jean_options(kept)
        assert len(result) == 3
        # The two salvaged options survive verbatim.
        texts = [o["text"] for o in result]
        assert "Where does the road lead?" in texts
        assert "Tell me about the caves." in texts
        assert all(o["tone"] in ("direct", "guarded", "open") for o in result)

    def test_empty_set_yields_full_fallback_pool(self):
        npc = _npc()
        npc._chat_fallback_idx = 0
        result = npc._top_up_jean_options([])
        assert len(result) == 3

    def test_top_up_prefers_missing_tone(self):
        npc = _npc()
        npc._chat_fallback_idx = 0
        kept = [
            {"tone": "direct", "text": "Where does the road lead?"},
            {"tone": "open", "text": "Tell me about the caves."},
        ]
        result = npc._top_up_jean_options(kept)
        assert {o["tone"] for o in result} == {"direct", "guarded", "open"}


# ---------------------------------------------------------------------------
# Truncated-JSON salvage (_JSONTools)
# ---------------------------------------------------------------------------


class TestTruncatedJsonRepair:
    def test_truncated_mid_string_recovers_complete_fields(self):
        raw = (
            '{"npc_text": "The road is long.", "conversation_quality": "neutral", '
            '"jean_options": [{"tone": "direct", "text": "Go on"}, {"tone": "gua'
        )
        parsed = _JSONTools.try_parse_json(raw)
        assert parsed is not None
        assert parsed["npc_text"] == "The road is long."
        assert parsed["conversation_quality"] == "neutral"

    def test_truncated_after_key_recovers_prior_fields(self):
        raw = '{"npc_text": "Storm tonight.", "loquacity_delta":'
        parsed = _JSONTools.try_parse_json(raw)
        assert parsed is not None
        assert parsed["npc_text"] == "Storm tonight."

    def test_garbage_braces_still_return_none(self):
        assert _JSONTools.try_parse_json("prefix { not json at all } suffix") is None

    def test_intact_json_unaffected(self):
        assert _JSONTools.try_parse_json('{"a": 1}') == {"a": 1}

    def test_json_on_same_line_as_opening_fence(self):
        assert _JSONTools.try_parse_json('```json {"a": 1}```') == {"a": 1}

    def test_strip_code_fences_handles_trailing_same_line_fence(self):
        assert _JSONTools.strip_code_fences("```\nhello there```") == "hello there"


# ---------------------------------------------------------------------------
# Thinking-token stripping
# ---------------------------------------------------------------------------


class TestThinkingTokenStripping:
    def test_unmatched_mid_text_opener_dropped(self):
        text = 'The answer is ready. <think>wait, let me reconsider the'
        result = _JSONTools._strip_thinking_tokens(text)
        assert result == "The answer is ready."
        assert "reconsider" not in result

    def test_unmatched_opener_at_start_yields_empty(self):
        assert _JSONTools._strip_thinking_tokens("<think>never closed") == ""

    def test_matched_blocks_removed(self):
        text = "<think>hidden</think>Visible answer."
        assert _JSONTools._strip_thinking_tokens(text) == "Visible answer."

    def test_thinking_tag_variant_removed(self):
        text = "<thinking>hidden</thinking>Visible answer."
        assert _JSONTools._strip_thinking_tokens(text) == "Visible answer."


# ---------------------------------------------------------------------------
# generate_plain: no raw-JSON leak
# ---------------------------------------------------------------------------


class TestGeneratePlainNoJsonLeak:
    def _client(self, monkeypatch, raw):
        from unittest.mock import patch as mock_patch
        from ai.llm_client import GenericLLMClient

        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "m")
        # Fail fast if a future edit lets a real request slip past the
        # _ollama_chat patch: nothing listens on this port.
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
        client = GenericLLMClient()
        client._available = True
        return client, mock_patch.object(client, "_ollama_chat", return_value=raw)

    def test_unknown_key_json_salvages_first_string_value(self, monkeypatch):
        client, patcher = self._client(
            monkeypatch, '{"dialogue": "The mynx tilts its head."}'
        )
        with patcher:
            result = client.generate_plain("sys", "user")
        assert result == "The mynx tilts its head."

    def test_unparseable_brace_response_returns_none(self, monkeypatch):
        # Repair salvages {"unterminated": [1, 2]} — a dict with no string
        # value — so there is nothing to show; the caller must get None, never
        # the raw braces.
        client, patcher = self._client(monkeypatch, '{"unterminated": [1, 2, oops')
        with patcher:
            result = client.generate_plain("sys", "user")
        assert result is None

    def test_bare_fence_without_language_tag_never_leaks_backticks(self, monkeypatch):
        client, patcher = self._client(monkeypatch, "```\nThe mynx yawns.\n```")
        with patcher:
            result = client.generate_plain("sys", "user")
        assert result == "The mynx yawns."


# ---------------------------------------------------------------------------
# Scrub regressions — span cleanup, capitalization, asides, sentence cap
# ---------------------------------------------------------------------------


class TestCleanupRegressions:
    def test_sentence_final_removal_leaves_no_orphan_comma(self):
        # Removing a sentence-final span used to leave "It's fine,."
        npc = _npc()
        result = npc._qc_npc_text("It's fine, cool.", []).text
        assert result == "It's fine."

    def test_cleanup_drops_comma_glued_to_terminator(self):
        assert (
            ConversationalNPCMixin._cleanup_removed_spans("I will go, okay,.")
            == "I will go, okay."
        )

    def test_cleanup_keeps_leading_ellipsis(self):
        assert ConversationalNPCMixin._cleanup_removed_spans("...fine.") == "...fine."

    def test_capitalization_skips_ellipsis(self):
        assert (
            ConversationalNPCMixin._capitalize_sentence_starts(
                "well... maybe you're right. so it goes."
            )
            == "Well... maybe you're right. So it goes."
        )

    def test_consecutive_asides_are_both_extracted(self):
        npc = _npc()
        cleaned, aside = npc._extract_action_asides("*nods* *smiles* Fine.")
        assert cleaned == "Fine."
        assert aside == "nods smiles"

    def test_trailing_quote_gains_no_stray_period(self):
        npc = _npc()
        result = npc._qc_npc_text('He called it "the long road."', []).text
        assert result == 'He called it "the long road."'

    def test_leading_ellipsis_survives_the_sentence_cap(self):
        npc = _npc()
        result = npc._qc_npc_text("...fine. Have it your way.", []).text
        assert result.startswith("...fine.")


class TestFlavorQCDirect:
    def test_flavor_is_capitalized_and_terminated(self):
        npc = _npc()
        assert npc._qc_flavor_text("studies the horizon") == "Studies the horizon."

    def test_flavor_substitutes_invented_nouns(self):
        npc = _npc()
        result = npc._qc_flavor_text("Watches Xanthor pass by.")
        assert "Xanthor" not in result
        assert result != ""

    def test_unusable_flavor_drops_to_empty(self):
        npc = _npc()
        assert npc._qc_flavor_text("???") == ""


# ---------------------------------------------------------------------------
# Unclosed asterisk asides anywhere in the line
# ---------------------------------------------------------------------------


class TestUnclosedAsideAnywhereInTheLine:
    """An odd asterisk count means the model never closed a stage direction.

    The repair used to fire only when the lone marker opened the text, so the
    two commonest shapes fell through to ``text.replace("*", " ")`` and SPOKE
    the direction — the exact bug class this branch exists to close.
    """

    def test_an_unclosed_aside_after_speech_keeps_the_speech(self):
        npc = _npc()
        spoken, aside = npc._extract_action_asides(
            "Fine. *nods slowly and turns away"
        )
        assert spoken == "Fine."
        assert aside == "nods slowly and turns away"

    def test_a_closed_aside_does_not_hide_a_later_unclosed_one(self):
        """The first, closed aside moves the lone marker off the front, which
        is what defeated the leading-only repair."""
        npc = _npc()
        spoken, aside = npc._extract_action_asides("*nods* Fine. *shrugs")
        assert spoken == "Fine."
        assert aside == "nods shrugs"

    def test_the_unclosed_aside_ends_at_the_next_terminator(self):
        npc = _npc()
        spoken, aside = npc._extract_action_asides(
            "Fine. *turns away. And that was that."
        )
        assert spoken == "Fine. And that was that."
        assert aside == "turns away"

    def test_a_reply_that_is_only_an_unclosed_aside_still_fails_qc(self):
        """Unchanged from the leading-only repair: nothing is spoken, so the
        turn is correctly rejected rather than narrating the direction."""
        npc = _npc()
        cleaned, reason, aside = npc._qc_npc_text("*nods slowly Fine, then.", [])
        assert cleaned is None
        assert reason
        assert aside == "nods slowly Fine, then"

    def test_the_stage_direction_never_reaches_the_spoken_line(self):
        npc = _npc()
        cleaned = npc._qc_npc_text(
            "The ferry runs at dawn. *she does not look up", []
        ).text
        assert cleaned == "The ferry runs at dawn."


# ---------------------------------------------------------------------------
# The flavor channel is not a way around the "never write Jean" rule
# ---------------------------------------------------------------------------


class TestFlavorObeysTheJeanDialogueRule:
    def test_flavor_that_speaks_for_jean_is_dropped(self):
        npc = _npc()
        assert npc._qc_flavor_text('Jean said, "Leave it."') == ""

    def test_flavor_that_narrates_jean_speaking_is_dropped(self):
        npc = _npc()
        assert npc._qc_flavor_text("Jean asks about the crossing.") == ""

    def test_a_relocated_aside_cannot_smuggle_jeans_dialogue_into_flavor(self):
        """The whole point: the aside is EXTRACTED from the line the rule
        protects and then relocated into the channel beside it."""

        class FakeAdapter:
            enabled = True

            def generate_turn(self, system, history, is_opening=False, jean_text=None):
                return make_turn(
                    '*Jean said, "Leave it."* The ferry runs at dawn.'
                )

        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            FakeAdapter(), "sys", llm_available=True, is_opening=True, jean_text=None
        )
        assert turn is not None
        assert turn.npc_text == "The ferry runs at dawn."
        assert turn.npc_flavor == ""

    def test_ordinary_flavor_still_survives(self):
        npc = _npc()
        assert npc._qc_flavor_text("She studies the far bank.") == (
            "She studies the far bank."
        )


class TestFlavorObeysTheDanglingFragmentPolicy:
    """QC policy 2 applied to the beat: flavor used to truncate at a word
    boundary and then add the cosmetic period the policy exists to forbid."""

    def test_a_cut_off_beat_is_dropped_rather_than_closed_with_a_period(self):
        npc = _npc()
        complete = "She sets the ledger down and looks a long while at the water."
        result = npc._qc_flavor_text(complete + " The man who keeps it is")
        assert result == complete

    def test_a_beat_that_is_only_a_fragment_is_still_closed(self):
        """The inverse failure: discarding unconditionally would amputate a
        beat that never had a terminator to begin with."""
        npc = _npc()
        assert npc._qc_flavor_text("She sets the ledger down") == (
            "She sets the ledger down."
        )


# ---------------------------------------------------------------------------
# The deadline cancels the retry, not the rewrite
# ---------------------------------------------------------------------------


class _CountingAdapter:
    enabled = True

    def __init__(self, npc_text):
        self.npc_text = npc_text
        self.calls = 0

    def generate_turn(self, system, history, is_opening=False, jean_text=None):
        self.calls += 1
        return make_turn(self.npc_text)


class TestExpiredBudgetStillRewrites:
    """Attempt 1 always runs strict, so a content violation is *meant* to be
    repaired by the final attempt's rewrite mode. The deadline used to cancel
    the retry and the rewrite together, discarding a salvageable line."""

    def _spent(self):
        return time.monotonic() - 1.0

    def test_a_content_violation_is_repaired_without_a_second_call(self):
        adapter = _CountingAdapter("I saw Xanthor by the river.")
        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            adapter,
            "sys",
            llm_available=True,
            is_opening=True,
            jean_text=None,
            deadline=self._spent(),
        )
        assert turn is not None
        assert "Xanthor" not in turn.npc_text
        assert "that place" in turn.npc_text
        assert adapter.calls == 1, "the salvage must not open a provider stage"

    def test_the_carried_aside_survives_the_salvage(self):
        adapter = _CountingAdapter("*sets down the ledger* I saw Xanthor here.")
        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            adapter,
            "sys",
            llm_available=True,
            is_opening=True,
            jean_text=None,
            deadline=self._spent(),
        )
        assert turn is not None
        assert turn.npc_flavor == "Sets down the ledger."

    def test_a_structural_rejection_is_not_salvaged(self):
        """Rewrite mode repairs content, never structure — a line that speaks
        for Jean has no safe rewrite and must still reach the fallback."""
        adapter = _CountingAdapter('Jean said, "I will go."')
        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            adapter,
            "sys",
            llm_available=True,
            is_opening=True,
            jean_text=None,
            deadline=self._spent(),
        )
        assert turn is None
        assert adapter.calls == 1

    def test_a_stage_is_not_opened_without_room_for_a_full_round_timeout(self):
        """Gating on "has the deadline passed?" let a stage start with
        milliseconds left and then run a whole provider chain."""
        adapter = _CountingAdapter("I saw Xanthor by the river.")
        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            adapter,
            "sys",
            llm_available=True,
            is_opening=True,
            jean_text=None,
            # Not expired — but nowhere near enough left for another call.
            deadline=time.monotonic() + 0.05,
        )
        assert turn is not None
        assert adapter.calls == 1


# ---------------------------------------------------------------------------
# Prompt containment of model-chosen text
# ---------------------------------------------------------------------------


class TestRetryGuidanceIsBounded:
    def test_at_most_eight_invented_nouns_are_named_back_to_the_model(self):
        """The list is spliced into the [RETRY GUIDANCE] block of the SYSTEM
        prompt and every token in it was chosen by the model."""
        names = [
            "Aardor", "Baldor", "Caldor", "Daldor", "Ealdor", "Faldor",
            "Galdor", "Haldor", "Ialdor", "Jaldor", "Kaldor", "Laldor",
        ]
        npc = _npc()
        reason = npc._qc_npc_text(
            "He met " + ", ".join(names) + " by the water.", [], allow_rewrite=False
        ).reason
        prefix = "it used names not in the allowed list: "
        assert reason.startswith(prefix)
        named = reason[len(prefix):].split(", ")
        assert named == sorted(names)[:8]


class TestAcceptedLineIsSingleLine:
    def test_a_newline_never_survives_qc(self):
        """The accepted line is written back into prompts that are STRUCTURED
        by newlines (revise_turn's options block, the replayed history rows).
        The production adapter happens to collapse whitespace upstream; the
        legacy adapter path this module still supports does not."""
        npc = _npc()
        cleaned = npc._qc_npc_text("The ferry runs\nat dawn.", []).text
        assert cleaned == "The ferry runs at dawn."


# ---------------------------------------------------------------------------
# Option salvage, end to end: real adapter -> mixin
# ---------------------------------------------------------------------------


class _ScriptedRealAdapter(NpcChatLLMAdapter):
    """The REAL production adapter with only the network call replaced.

    ``_clean_jean_options``, ``_clean_option_text`` and the whole parse path run
    for real. Testing the mixin in isolation is what let the option salvage sit
    unreachable in production for a whole round: ``_clean_jean_options`` cut the
    list to three before the mixin ever saw it, so the mixin's "validate
    everything, slice after dedup" logic passed its own unit tests while a
    malformed option at index 0 still cost a good option at index 3.
    """

    enabled = True

    def __init__(self, payload):
        self._raw = json.dumps(payload)
        self.prompts = []

    def _call_llm(self, system_prompt, user_prompt, **kwargs):
        self.prompts.append(system_prompt)
        return self._raw

    def generate_personality(self, npc_class_display):
        return None


class TestOptionSalvageEndToEnd:
    def _payload(self, options):
        return make_turn("The ferry runs at dawn.", jean_options=options)

    def test_a_good_option_at_index_three_reaches_the_player(self):
        """Three malformed options ahead of it used to make it unreachable."""
        adapter = _ScriptedRealAdapter(
            self._payload(
                [
                    {"tone": "direct", "text": "x"},
                    {"tone": "guarded", "text": "y"},
                    {"tone": "open", "text": "z"},
                    {"tone": "direct", "text": "Who keeps the ferry these days?"},
                    {"tone": "open", "text": "What is the crossing like in winter?"},
                ]
            )
        )
        result = wired_chat_npc(adapter).chat_open(chat_player())
        texts = [o["text"] for o in result["jean_options"]]
        assert "Who keeps the ferry these days?" in texts
        assert "What is the crossing like in winter?" in texts
        assert len(result["jean_options"]) == 3

    def test_a_dropped_option_does_not_cost_the_player_a_tone(self):
        """Tone defaulting happens on BOTH sides of the boundary: the adapter
        assigns by kept position, the mixin drops what the adapter could not
        judge, and the top-up refills the tone that went with it."""
        adapter = _ScriptedRealAdapter(
            self._payload(
                [
                    {"text": "x"},
                    {"text": "Who keeps the ferry these days?"},
                    {"text": "What is the crossing like in winter?"},
                ]
            )
        )
        result = wired_chat_npc(adapter).chat_open(chat_player())
        assert len(result["jean_options"]) == 3
        assert {o["tone"] for o in result["jean_options"]} == {
            "direct",
            "guarded",
            "open",
        }

    def test_a_long_option_is_trimmed_at_a_word_boundary_and_survives(self):
        """The two layers agree on the NUMBER and now on the ACTION: the
        adapter trims back to a word boundary, so the trimmed option lands
        inside the mixin's inclusive bound instead of being dropped — and the
        player never sees the mid-word amputation ('...the eastern chan')."""
        long_option = (
            "The ferryman keeps to the eastern channel because the western one "
            "silts up every spring and nobody has dredged it since the old "
            "warden died, which is why the crossing takes so long these days."
        )
        assert len(long_option) > MAX_OPTION_CHARS
        adapter = _ScriptedRealAdapter(
            self._payload(
                [
                    {"tone": "direct", "text": long_option},
                    {"tone": "guarded", "text": "Why does it silt up?"},
                    {"tone": "open", "text": "Tell me about the old warden."},
                ]
            )
        )
        result = wired_chat_npc(adapter).chat_open(chat_player())
        kept = [o["text"] for o in result["jean_options"]]
        trimmed = [t for t in kept if t.startswith("The ferryman keeps")]
        assert trimmed, "the trimmed option must survive the mixin's length bound"
        assert len(trimmed[0]) <= MAX_OPTION_CHARS
        assert long_option.startswith(trimmed[0])
        # Word boundary: the next character in the source is a space, so no
        # word was cut in half.
        assert long_option[len(trimmed[0])] == " "
