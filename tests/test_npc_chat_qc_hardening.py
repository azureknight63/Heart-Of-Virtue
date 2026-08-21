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

import re

from src.npc._chat_llm import ConversationalNPCMixin
from ai.llm_client import _JSONTools


def _npc(allowed_nouns=None, personality=None, prohibited=None):
    class QCNPC(ConversationalNPCMixin):
        def __init__(self):
            self.name = "TestNPC"
            self._chat_world_facts = {
                "allowed_proper_nouns": allowed_nouns or []
            }
            self._chat_personality = personality
            self._prohibited_patterns = [
                re.compile(re.escape(p), re.IGNORECASE) for p in (prohibited or [])
            ]

    return QCNPC()


# ---------------------------------------------------------------------------
# Invented-noun scan: allowlist matching
# ---------------------------------------------------------------------------


class TestAllowlistMatching:
    def test_multiword_allowed_noun_survives(self):
        npc = _npc(allowed_nouns=["Wailing Badlands", "Echoing Caves"])
        result = npc._qc_npc_text(
            "You'll find shelter in the Echoing Caves before nightfall.", []
        )
        assert "Echoing Caves" in result
        assert "they" not in result.split()

    def test_singular_of_allowed_plural_survives(self):
        npc = _npc(allowed_nouns=["Golemites"])
        result = npc._qc_npc_text("I once traded with a Golemite patrol.", [])
        assert "Golemite" in result

    def test_plural_of_allowed_singular_survives(self):
        npc = _npc(allowed_nouns=["Grondite"])
        result = npc._qc_npc_text("Two of the Grondites passed through camp.", [])
        assert "Grondites" in result

    def test_adjectival_extension_of_allowed_stem_survives(self):
        npc = _npc(allowed_nouns=["Grondia"])
        result = npc._qc_npc_text("He wore a fine Grondian cloak.", [])
        assert "Grondian" in result

    def test_generic_npc_own_given_name_survives(self):
        npc = _npc(personality={"given_name": "Ren"})
        result = npc._qc_npc_text("Folk out here call me Ren, nothing more.", [])
        assert "Ren" in result

    def test_invented_noun_replaced_grammatically(self):
        npc = _npc()
        result = npc._qc_npc_text("I met Kessa near the ford.", [])
        assert "Kessa" not in result
        assert "someone" in result
        # Old bug: object-position "they" ("I met they")
        assert "met they" not in result

    def test_invented_place_replaced_with_that_place(self):
        npc = _npc()
        result = npc._qc_npc_text("The caravan set out for Vetheria at dawn.", [])
        assert "Vetheria" not in result
        assert "that place" in result


# ---------------------------------------------------------------------------
# Punctuation preservation
# ---------------------------------------------------------------------------


class TestPunctuationPreservation:
    def test_questions_and_exclamations_survive_sentence_cap(self):
        npc = _npc()
        result = npc._qc_npc_text("What do you want? Stay back! I mean it.", [])
        assert "?" in result
        assert "!" in result

    def test_ellipsis_preserved(self):
        npc = _npc()
        result = npc._qc_npc_text("Well... maybe you're right.", [])
        assert "..." in result

    def test_sentence_cap_still_three(self):
        npc = _npc()
        result = npc._qc_npc_text("One! Two? Three. Four. Five.", [])
        assert "Four" not in result
        assert result.startswith("One!")


# ---------------------------------------------------------------------------
# Slang and prohibited-phrase rewrites
# ---------------------------------------------------------------------------


class TestRewriteCleanup:
    def test_slang_removal_leaves_no_orphan_comma(self):
        npc = _npc()
        result = npc._qc_npc_text("Yeah, I know the road well.", [])
        assert result is not None
        assert "Yeah" not in result
        assert not result.startswith(",")
        assert "  " not in result

    def test_you_know_question_form_removed(self):
        # The old pattern's trailing \b made "you know?" unmatchable at the
        # end of a sentence — its only realistic position.
        npc = _npc()
        result = npc._qc_npc_text("The road gets rough out west, you know?", [])
        assert result is not None
        assert "you know" not in result.lower()

    def test_cool_as_temperature_is_not_slang(self):
        npc = _npc()
        cleaned, reason, _aside = npc._qc_npc_text_ex(
            "The water runs cool under the bridge.", [], allow_rewrite=False
        )
        assert cleaned is not None, reason
        assert "cool" in cleaned

    def test_cool_as_interjection_is_slang(self):
        npc = _npc()
        cleaned, reason, _aside = npc._qc_npc_text_ex(
            "That's cool, I suppose.", [], allow_rewrite=False
        )
        assert cleaned is None
        assert "slang" in reason

    def test_hyphenated_allowed_token_survives(self):
        npc = _npc(allowed_nouns=["Badlands"])
        result = npc._qc_npc_text("We camped on the East-bank side of the river.", [])
        assert "East-bank" in result

    def test_prohibited_phrase_removed_without_artifact(self):
        npc = _npc(prohibited=["forbidden"])
        result = npc._qc_npc_text("This forbidden word is gone now.", [])
        assert result is not None
        assert "[...]" not in result
        assert "forbidden" not in result


# ---------------------------------------------------------------------------
# Strict mode (attempt 1) vs rewrite mode (final attempt)
# ---------------------------------------------------------------------------


class TestStrictMode:
    def test_strict_rejects_invented_noun_with_reason(self):
        npc = _npc()
        cleaned, reason, _aside = npc._qc_npc_text_ex(
            "I saw Xanthor by the river.", [], allow_rewrite=False
        )
        assert cleaned is None
        assert "Xanthor" in reason

    def test_strict_rejects_slang_with_reason(self):
        npc = _npc()
        cleaned, reason, _aside = npc._qc_npc_text_ex(
            "Yeah, the road is long.", [], allow_rewrite=False
        )
        assert cleaned is None
        assert "slang" in reason

    def test_rewrite_mode_salvages_same_text(self):
        npc = _npc()
        cleaned, reason, _aside = npc._qc_npc_text_ex(
            "I saw Xanthor by the river.", [], allow_rewrite=True
        )
        assert cleaned is not None
        assert "Xanthor" not in cleaned
        assert reason is None

    def test_jean_dialogue_present_tense_rejected(self):
        npc = _npc()
        assert npc._qc_npc_text("Jean says he wants to leave.", []) is None

    def test_jean_dialogue_rejected_in_both_modes(self):
        npc = _npc()
        for allow in (False, True):
            cleaned, _r, _a = npc._qc_npc_text_ex(
                "Jean said hello to me today.", [], allow_rewrite=allow
            )
            assert cleaned is None


# ---------------------------------------------------------------------------
# Asterisk action asides
# ---------------------------------------------------------------------------


class TestActionAsides:
    def test_asides_stripped_from_spoken_text(self):
        npc = _npc()
        result = npc._qc_npc_text("*nods slowly* Fine. Have it your way.", [])
        assert "*" not in result
        assert "nods slowly" not in result
        assert result.startswith("Fine.")

    def test_extract_returns_aside_text(self):
        npc = _npc()
        cleaned, _reason, aside = npc._qc_npc_text_ex(
            "*shrugs* The road decides, not me.", []
        )
        assert aside == "shrugs"
        assert cleaned.startswith("The road")

    def test_markdown_bold_unwrapped_not_extracted(self):
        npc = _npc()
        result = npc._qc_npc_text("That is **not** a good idea.", [])
        assert "*" not in result
        assert "not" in result

    def test_mid_sentence_emphasis_is_unwrapped_not_extracted(self):
        # Single-asterisk emphasis embedded between words is markdown
        # emphasis, not a stage direction — the word must stay in place.
        npc = _npc()
        cleaned, _reason, aside = npc._qc_npc_text_ex(
            "I would *never* sell to them.", []
        )
        assert cleaned == "I would never sell to them."
        assert aside == ""

    def test_trailing_aside_extracted(self):
        npc = _npc()
        cleaned, _reason, aside = npc._qc_npc_text_ex(
            "Suit yourself. *turns back to the fire*", []
        )
        assert cleaned == "Suit yourself."
        assert aside == "turns back to the fire"

    def test_spoken_text_capitalized_after_leading_aside(self):
        npc = _npc()
        cleaned, _reason, _aside = npc._qc_npc_text_ex("*shrugs* fine, go.", [])
        assert cleaned.startswith("Fine")

    def test_run_npc_turn_relocates_aside_into_empty_flavor(self):
        class FakeAdapter:
            enabled = True

            def generate_turn(self, system, history, is_opening=False, jean_text=None):
                return {
                    "npc_text": "*studies the horizon* Storm's coming.",
                    "npc_flavor": "",
                    "conversation_quality": "neutral",
                    "reputation_delta": 0,
                    "loquacity_delta": -5,
                    "jean_options": [],
                }

        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            FakeAdapter(), "sys", llm_available=True, is_opening=True, jean_text=None
        )
        assert turn is not None
        assert "*" not in turn["npc_text"]
        # The relocated aside is capitalized by the flavor QC pass.
        assert "studies the horizon" in turn["npc_flavor"].lower()

    def test_model_supplied_flavor_takes_priority_over_aside(self):
        class FakeAdapter:
            enabled = True

            def generate_turn(self, system, history, is_opening=False, jean_text=None):
                return {
                    "npc_text": "*sighs* So be it.",
                    "npc_flavor": "She turns away toward the fire.",
                    "conversation_quality": "neutral",
                    "reputation_delta": 0,
                    "loquacity_delta": -5,
                    "jean_options": [],
                }

        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            FakeAdapter(), "sys", llm_available=True, is_opening=True, jean_text=None
        )
        assert turn["npc_flavor"] == "She turns away toward the fire."


# ---------------------------------------------------------------------------
# Retry guidance
# ---------------------------------------------------------------------------


class TestRetryGuidance:
    def test_second_attempt_carries_rejection_reason(self):
        calls = []

        class FakeAdapter:
            enabled = True

            def generate_turn(self, system, history, is_opening=False, jean_text=None):
                calls.append(system)
                if len(calls) == 1:
                    text = "I saw Xanthor by the river."
                else:
                    text = "The river runs cold this season."
                return {
                    "npc_text": text,
                    "npc_flavor": "",
                    "conversation_quality": "neutral",
                    "reputation_delta": 0,
                    "loquacity_delta": -5,
                    "jean_options": [],
                }

        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            FakeAdapter(), "base system", llm_available=True,
            is_opening=True, jean_text=None,
        )
        assert turn["npc_text"].startswith("The river")
        assert len(calls) == 2
        assert "[RETRY GUIDANCE]" not in calls[0]
        assert "[RETRY GUIDANCE]" in calls[1]
        assert "Xanthor" in calls[1]

    def test_final_attempt_rewrites_instead_of_falling_back(self):
        class FakeAdapter:
            enabled = True

            def generate_turn(self, system, history, is_opening=False, jean_text=None):
                # Both attempts return the same invented-noun line.
                return {
                    "npc_text": "I saw Xanthor by the river.",
                    "npc_flavor": "",
                    "conversation_quality": "neutral",
                    "reputation_delta": 0,
                    "loquacity_delta": -5,
                    "jean_options": [],
                }

        npc = _npc()
        npc._chat_history = []
        turn = npc._run_npc_turn(
            FakeAdapter(), "sys", llm_available=True, is_opening=True, jean_text=None
        )
        # Salvaged in place on the final attempt — not dropped to fallback.
        # ("Xanthor" ends in -or, so the place-shaped replacement applies.)
        assert turn is not None
        assert "Xanthor" not in turn["npc_text"]
        assert "that place" in turn["npc_text"]


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
