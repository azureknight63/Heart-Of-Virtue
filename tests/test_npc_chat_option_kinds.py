"""The two axes on Jean's dialogue options (issue #591).

``tone`` answers "how does Jean look saying it" and is the portrait emotion
vocabulary; ``kind`` answers "what is Jean going to talk about" and is an
editable pool. The option count stays at three, and *kind* now carries the
uniqueness the tone axis used to, because the kind pool is strictly larger than
the option count while the tone tuple no longer is.

Design note: ``docs/development/jean-chat-option-axes-design.md``.
"""

import json
import re
from pathlib import Path

import ai.llm_client as llm_client
from src.npc import _chat_llm
from src.npc._chat_llm import JEAN_KINDS, JEAN_TONES
from tests._npc_fixtures import qc_npc


def _qc_host():
    return qc_npc(allowed_proper_nouns=[])


_FRONTEND_PORTRAITS = (
    Path(__file__).resolve().parents[1] / "frontend" / "src" / "utils" / "portraits.js"
)


class TestToneIsThePortraitEmotionVocabulary:
    """``tone`` selects Jean's portrait, so its values ARE the emotions.

    The three registers used to map onto three of the eight emotions through
    ``TONE_EMOTIONS`` in useNpcChat.js, leaving five portraits Jean has art for
    unreachable from chat. Collapsing the two vocabularies deletes that table.
    """

    def test_the_tones_are_the_frontend_emotion_list(self):
        source = _FRONTEND_PORTRAITS.read_text(encoding="utf-8")
        match = re.search(r"export const EMOTIONS = (\[[^\]]*\])", source)
        assert match, "could not find the EMOTIONS array in utils/portraits.js"
        emotions = json.loads(match.group(1).replace("'", '"'))
        assert sorted(JEAN_TONES) == sorted(emotions)

    def test_neutral_is_available_as_the_default(self):
        # Routes and cleaners fall back to this name rather than to a register.
        assert "neutral" in JEAN_TONES


class TestTheOptionCountIsPinnedToThree:
    """It used to be ``len(JEAN_TONES)``, which silently becomes eight."""

    def test_three_options_regardless_of_the_tone_count(self):
        assert _chat_llm._JEAN_OPTION_COUNT == 3
        assert len(JEAN_TONES) > _chat_llm._JEAN_OPTION_COUNT

    def test_the_pool_offers_more_kinds_than_one_round_can_show(self):
        # Not a correctness constraint any more (nothing draws a "free" kind),
        # but a pool at or below the option count would mean every round shows
        # the whole vocabulary and the axis stops being a choice.
        assert len(JEAN_KINDS) > _chat_llm._JEAN_OPTION_COUNT

    def test_reply_is_in_the_pool(self):
        assert "reply" in JEAN_KINDS


class TestTheOptionsSkeletonAsksForThree:
    """``_JEAN_OPTIONS_SKELETON`` built itself by iterating the tone tuple, so
    widening that tuple asks the model for one option per emotion."""

    def test_exactly_three_slots(self):
        parsed = json.loads(llm_client._JEAN_OPTIONS_SKELETON)
        assert len(parsed) == 3

    def test_every_slot_carries_both_axes(self):
        for slot in json.loads(llm_client._JEAN_OPTIONS_SKELETON):
            assert set(slot) == {"tone", "kind", "text"}


class TestNeitherAxisIsReassigned:
    """Both axes are taken at face value.

    Uniqueness of kinds is asked for in the generation prompt, never imposed
    here: the kind is the label the player reads to choose, so relabelling a
    plain answer as ``ask-lore`` to manufacture variety would misdescribe the
    option. A duller round beats a false one.
    """

    def test_a_repeated_kind_is_left_alone(self):
        options = [
            {"tone": "neutral", "kind": "reply", "text": "Tell me about the river."},
            {"tone": "curious", "kind": "reply", "text": "Who else works this bank?"},
            {"tone": "skeptical", "kind": "reply", "text": "What keeps you here?"},
        ]
        kept = _qc_host()._qc_jean_options(options)
        assert [o["kind"] for o in kept] == ["reply", "reply", "reply"]

    def test_a_stated_kind_survives_a_dropped_sibling(self):
        """The salvage must not shift a label onto the wrong text."""
        kept = _qc_host()._qc_jean_options(
            [
                {"tone": "neutral", "kind": "reply", "text": "x"},
                {"tone": "curious", "kind": "ask-lore", "text": "Who holds the road?"},
            ]
        )
        assert kept == [
            {"tone": "curious", "kind": "ask-lore", "text": "Who holds the road?"}
        ]

    def test_a_repeated_tone_is_left_alone(self):
        options = [
            {"tone": "skeptical", "kind": "reply", "text": "Tell me about the river."},
            {"tone": "skeptical", "kind": "ask-lore", "text": "Who else works this bank?"},
        ]
        kept = _qc_host()._qc_jean_options(options)
        assert [o["tone"] for o in kept] == ["skeptical", "skeptical"]

    def test_an_unknown_tone_falls_back_to_neutral(self):
        options = [{"tone": "smug", "kind": "reply", "text": "Tell me about the river."}]
        kept = _qc_host()._qc_jean_options(options)
        assert kept[0]["tone"] == "neutral"

    def test_an_unknown_kind_falls_back_to_reply(self):
        options = [{"tone": "neutral", "kind": "haggle", "text": "Tell me about the river."}]
        kept = _qc_host()._qc_jean_options(options)
        assert kept[0]["kind"] == "reply"

    def test_a_missing_kind_defaults_to_reply(self):
        """An older adapter, or a fallback entry, stays valid."""
        options = [{"tone": "neutral", "text": "Tell me about the river."}]
        kept = _qc_host()._qc_jean_options(options)
        assert kept[0]["kind"] == "reply"


class TestAtLeastOneReply:
    """Three questions in a row leave the NPC's last line unanswered."""

    def test_an_all_question_set_gains_a_reply(self):
        options = [
            {"tone": "curious", "kind": "ask-lore", "text": "Who holds the eastern road?"},
            {"tone": "neutral", "kind": "ask-npc", "text": "How long have you traded here?"},
            {"tone": "skeptical", "kind": "challenge", "text": "That story has a hole in it."},
        ]
        final = _qc_host()._top_up_jean_options(_qc_host()._qc_jean_options(options))
        assert len(final) == 3
        assert any(o["kind"] == "reply" for o in final)

    def test_a_set_that_already_replies_is_untouched(self):
        options = [
            {"tone": "curious", "kind": "ask-lore", "text": "Who holds the eastern road?"},
            {"tone": "neutral", "kind": "reply", "text": "Then I'll go around."},
            {"tone": "skeptical", "kind": "challenge", "text": "That story has a hole in it."},
        ]
        qc = _qc_host()._qc_jean_options(options)
        assert [o["kind"] for o in qc] == ["ask-lore", "reply", "challenge"]
        assert _qc_host()._top_up_jean_options(qc) == qc


class TestTheFallbackPoolCarriesTheAxes:
    def test_every_fallback_entry_is_a_valid_reply(self):
        for group in _chat_llm._JEAN_FALLBACK_POOL:
            for entry in group:
                assert entry["kind"] == "reply"
                assert entry["tone"] in JEAN_TONES

    def test_a_degraded_round_still_offers_three(self):
        final = _qc_host()._top_up_jean_options([])
        assert len(final) == 3
        assert all(o["kind"] == "reply" for o in final)


class TestBothAxesReachTheWire:
    """The client's read sites and the payload's actual shape, pinned together.

    The rest of this file drives the QC functions directly, which cannot see a
    field dropped on the way OUT — a serializer or a return statement that
    stopped carrying ``kind`` would leave every test above green while the
    player got buttons with a blank label. This is the wire-field-drift guard
    from ``tests/test_wire_field_contract.py`` applied to the chat payload.

    It runs the LLM-disabled path deliberately: that is the branch whose
    options come from the authored fallback pool rather than a mocked adapter,
    so nothing in the assertion is agreeing with a fixture it wrote itself.
    """

    _CLIENT = Path(__file__).resolve().parents[1] / "frontend" / "src"

    def _round(self):
        from tests._npc_fixtures import chat_player, wired_chat_npc

        class _Unavailable:
            """An adapter the mixin will judge unusable, forcing the pool."""

            enabled = False

        return wired_chat_npc(_Unavailable()).chat_open(chat_player())

    def test_every_option_on_a_real_round_carries_both_axes(self):
        result = self._round()
        options = result["jean_options"]
        assert options, "a chat round must always offer options"
        for opt in options:
            assert opt["tone"] in JEAN_TONES, opt
            assert opt["kind"] in JEAN_KINDS, opt

    def test_the_degraded_round_is_all_replies(self):
        assert all(o["kind"] == "reply" for o in self._round()["jean_options"])

    def test_a_generated_round_carries_the_axes_it_was_given(self):
        """The other branch. ``_round`` above exercises the fallback pool, which
        never touches ``_qc_jean_options`` — so on its own it cannot see the QC
        assignment drop a field. This one drives a real ``chat_open`` through
        the generator and the QC pipeline, and asserts the axes the adapter
        stated survive the trip to the payload unchanged.
        """
        from tests._npc_fixtures import StubAdapter, chat_player, make_turn, wired_chat_npc

        options = [
            {"tone": "curious", "kind": "ask-lore", "text": "Who holds the eastern road?"},
            {"tone": "neutral", "kind": "reply", "text": "Then I will go around."},
            {"tone": "concerned", "kind": "counsel", "text": "That is a heavy thing to carry."},
        ]
        adapter = StubAdapter(make_turn("The pass is shut.", jean_options=options))
        result = wired_chat_npc(adapter).chat_open(chat_player())

        assert result["jean_options"] == options

    def test_the_client_reads_the_kind_off_the_option(self):
        """The other half of the contract: a field nothing reads is dead."""
        panel = (self._CLIENT / "components" / "NpcChatPanel.jsx").read_text(
            encoding="utf-8"
        )
        assert "option.kind" in panel, (
            "NpcChatPanel no longer reads option.kind — either the label moved "
            "or the axis stopped reaching the button"
        )

    def test_the_client_labels_every_kind_the_engine_can_emit(self):
        """A kind with no label renders a button with an empty label slot.

        The JS suite pins this from its side too; this is the Python-side
        mirror, so adding a kind without a label fails whichever suite the
        author happens to run.
        """
        hook = (self._CLIENT / "hooks" / "useNpcChat.js").read_text(encoding="utf-8")
        block = re.search(r"export const KIND_LABELS = \{(.*?)\n\}", hook, re.S)
        assert block, "could not find KIND_LABELS in hooks/useNpcChat.js"
        labelled = set(re.findall(r"^\s*'?([a-z-]+)'?\s*:", block.group(1), re.M))
        assert labelled == set(JEAN_KINDS)


class TestTheFallbackRotationOnlyAdvancesWhenUsed:
    """A healthy round must not consume a fallback group.

    ``_get_fallback_jean_options`` is not a pure read: it advances
    ``_chat_fallback_idx`` so successive degraded rounds offer different stock
    phrases. Adding the at-least-one-reply repair moved the pool fetch above
    the early return, so every full, healthy round started spinning that
    counter — invisible in the payload, and it changes which group a later
    degraded round actually gets.
    """

    def _npc(self):
        npc = _qc_host()
        npc._chat_fallback_idx = 0
        return npc

    def test_a_complete_set_does_not_spin_the_counter(self):
        npc = self._npc()
        options = [
            {"tone": "curious", "kind": "ask-lore", "text": "Who holds the eastern road?"},
            {"tone": "neutral", "kind": "reply", "text": "Then I will go around."},
            {"tone": "concerned", "kind": "counsel", "text": "That is a heavy thing."},
        ]
        assert npc._top_up_jean_options(options) == options
        assert npc._chat_fallback_idx == 0

    def test_a_partial_set_does_spin_it(self):
        """The other half: the counter must still advance when the pool is
        genuinely drawn from, or degraded rounds would repeat one group."""
        npc = self._npc()
        npc._top_up_jean_options(
            [{"tone": "neutral", "kind": "reply", "text": "Then I will go around."}]
        )
        assert npc._chat_fallback_idx != 0

    def test_an_all_question_set_spins_it_because_the_repair_needs_the_pool(self):
        npc = self._npc()
        npc._top_up_jean_options(
            [
                {"tone": "curious", "kind": "ask-lore", "text": "Who holds the road?"},
                {"tone": "neutral", "kind": "ask-npc", "text": "How long have you traded?"},
                {"tone": "angry", "kind": "challenge", "text": "That story has a hole."},
            ]
        )
        assert npc._chat_fallback_idx != 0
