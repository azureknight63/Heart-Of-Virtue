"""Regression tests for three conversational-system defects (punchlist 2026-08-30).

1. **Merchant commerce questions.** Vespera (and any merchant-context NPC) kept
   asking Jean for pricing/inventory information — "What are you looking to buy?",
   "What's your budget?" — and the generated Jean options kept asking her the
   price of stock. The chat panel cannot transact (the shop UI does), so every
   such question is a dead end. Suppressed by a prompt rule plus a deterministic
   QC drop, scoped to merchant context so ordinary armor/craft questions survive.

2. **Jean's name inside Jean's own options.** The three generated options are
   *Jean's* replies, so "Jean has walked a long road" / "Ask about Jean's fit"
   put his name in his own mouth in the third person. Only a genuine
   self-introduction ("My name is Jean") may carry the name.

3. **Loquacity was far too generous.** Every conversational NPC's stamina pool
   is now scaled to 15% of its previous value by one rule
   (:func:`scale_loquacity`), applied to the computed maximum, the threshold
   floor and the recovery rate, with old-scale persisted values rescaled on load.

No provider calls: every test drives the deterministic QC/prompt/loquacity paths.
"""

import pytest

from src.npc._chat_llm import (
    LOQUACITY_SCALE_PERCENT,
    _JEAN_FALLBACK_POOL,
    scale_loquacity,
)
from tests._npc_fixtures import chat_npc, chat_player, qc_npc
from tests.llm_doubles import make_chat_adapter

# A character config whose role puts the NPC in merchant context, the way
# ai/npc/human/vespera.json does.
MERCHANT_CONFIG = {
    "character_name": "Vespera",
    "role": "armor specialist, merchant, co-proprietor of Iron & Oath",
    "loquacity_base": 80,
    "knowledge_scope": ["armor fit, coverage, and ergonomics"],
    "system_prompt_snippet": "You are Vespera, an armorer.",
}

FRIEND_CONFIG = {
    "character_name": "Mara",
    "role": "scavenger, ferry operator, guide",
    "loquacity_base": 60,
    "system_prompt_snippet": "You are Mara, a ferry operator.",
}


def _merchant(**overrides):
    return chat_npc(name="Vespera", _chat_char_config=MERCHANT_CONFIG, **overrides)


def _friend(**overrides):
    return chat_npc(name="Mara", _chat_char_config=FRIEND_CONFIG, **overrides)


def _opts(*texts):
    tones = ("direct", "guarded", "open")
    return [
        {"tone": tones[i % 3], "text": text} for i, text in enumerate(texts)
    ]


def _texts(options):
    return [o["text"] for o in options]


# ---------------------------------------------------------------------------
# 1. Merchant pricing / inventory questions
# ---------------------------------------------------------------------------


class TestMerchantContextDetection:
    def test_merchant_role_is_merchant_context(self):
        assert _merchant()._is_merchant_chat() is True

    def test_shop_attributes_are_merchant_context(self):
        # A merchant host whose config never loaded still trades.
        npc = chat_npc(_chat_char_config=None, shop_name="Iron & Oath")
        assert npc._is_merchant_chat() is True

    def test_non_merchant_role_is_not_merchant_context(self):
        assert _friend()._is_merchant_chat() is False

    def test_generic_nomad_is_not_merchant_context(self):
        assert chat_npc()._is_merchant_chat() is False


class TestMerchantOptionSuppression:
    @pytest.mark.parametrize(
        "text",
        [
            "How much for the boiled leather cuirass?",
            "What do you have in stock for river damp?",
            "Can I see your inventory of harnesses?",
            "Do you sell anything lighter than chain?",
            "Would you take less coin for the buckles?",
            "Any discount if I take two sets?",
            "What are your wares worth these days?",
            "What have you got in stock?",
            "Do you carry helmets in stock?",
            "What is your selection of buckles?",
            "How much gold should I bring?",
            "Does it cost more to reinforce?",
            "How much does that cuirass cost?",
            "What is the price of this cuirass?",
            "Do you have any helmets?",
            "What is the price of the cuirass?",
            "How much for the leather armor?",
        ],
    )
    def test_pricing_or_inventory_question_dropped(self, text):
        npc = _merchant()
        kept = _texts(npc._qc_jean_options(_opts(text, "Go on, then.")))
        assert text not in kept
        assert "Go on, then." in kept

    @pytest.mark.parametrize(
        "text",
        [
            "Which armor holds up best in river damp?",
            "How does boiled leather compare with chain for a long march?",
            "Who taught you to read a harness seam like that?",
            "Did Kaelen forge the steel on those brass buckles?",
            "What fails first on a cuirass that has been soaked?",
            "How much lighter is boiled leather than chain?",
        ],
    )
    def test_useful_armor_and_craft_questions_survive(self, text):
        npc = _merchant()
        assert text in _texts(npc._qc_jean_options(_opts(text)))

    def test_non_merchant_keeps_a_cost_question(self):
        # The rule is scoped to merchant context; a ferry fare is not shop stock.
        text = "How much for the crossing?"
        npc = _friend()
        assert text in _texts(npc._qc_jean_options(_opts(text)))

    @pytest.mark.parametrize(
        "text",
        [
            "Do you have any memories of the old siege?",
            "Do you have a story about the old forge?",
            "What does this coin symbolize?",
            "What was the cost of the war?",
            "What is the price of freedom?",
            "Can you explain why gold matters in the rite?",
            "How did you learn to haggle?",
            "Can gold buy passage through the mountains?",
            "What variety of leather is traditional here?",
            "What selection of techniques do you teach?",
            "Does the gold in this region come from the river?",
            "Do you have family?",
            "What is the cost of war?",
        ],
    )
    def test_merchant_lore_questions_survive(self, text):
        """Only shop-directed commerce belongs behind the trade UI."""
        npc = _merchant()
        assert text in _texts(npc._qc_jean_options(_opts(text)))

    @pytest.mark.parametrize(
        "text",
        [
            "What have you got?",
            "What can you offer?",
            "Is anything available?",
            "Are any helmets available?",
            "Have you got any armor?",
            "What do you carry?",
            "What is it worth?",
            "Would you trade?",
        ],
    )
    def test_common_shop_questions_are_dropped(self, text):
        npc = _merchant()
        assert text not in _texts(npc._qc_jean_options(_opts(text)))

    def test_dropped_options_are_topped_up_to_three(self):
        npc = _merchant()
        options = npc._top_up_jean_options(
            npc._qc_jean_options(
                _opts(
                    "How much for the cuirass?",
                    "What else do you have in stock?",
                    "Name a price and I will consider it, what is it?",
                )
            )
        )
        assert len(options) == 3
        assert {o["tone"] for o in options} == {"direct", "guarded", "open"}


class TestMerchantNpcLineSuppression:
    LINE = (
        "The straps on that cuirass are sound. "
        "What is the price of this shield?"
    )

    def test_commerce_question_removed_from_npc_line(self):
        npc = qc_npc(
            allowed_proper_nouns=["Jean", "Vespera", "Kaelen"],
            name="Vespera",
            _chat_char_config=MERCHANT_CONFIG,
        )
        cleaned = npc._qc_npc_text(self.LINE, [], allow_rewrite=True).text
        assert cleaned
        assert "price" not in cleaned.lower()
        assert "straps" in cleaned

    def test_commerce_question_rejects_on_first_attempt(self):
        npc = qc_npc(
            allowed_proper_nouns=["Jean", "Vespera", "Kaelen"],
            name="Vespera",
            _chat_char_config=MERCHANT_CONFIG,
        )
        result = npc._qc_npc_text(self.LINE, [], allow_rewrite=False)
        assert result.text is None
        assert result.reason and "price" in result.reason.lower()

    def test_non_merchant_line_untouched(self):
        npc = qc_npc(
            allowed_proper_nouns=["Jean", "Mara"],
            name="Mara",
            _chat_char_config=FRIEND_CONFIG,
        )
        cleaned = npc._qc_npc_text(self.LINE, [], allow_rewrite=True).text
        assert "price" in cleaned.lower()


class TestWeaponMerchantCommerceQuestions:
    """The classifier was inverted at Kaelen's stall, in both directions.

    Kaelen is the arms half of Iron & Oath — his ``always_stock`` is a
    Shortsword, a Spear and a Dagger (``src/npc/_merchants.py``). The chat-side
    item vocabulary enumerated armour nouns and no weapon nouns, so the
    canonical price question at his counter was not commerce at all; and the
    stock-request pattern fired on a bare ``get``/``keep`` anywhere in the
    sentence, so provenance and maintenance — two of the topics
    ``_build_trade_block`` tells the model to raise *instead* — were suppressed.

    Both directions are asserted here on purpose. A parametrised list of things
    that must be dropped, with no list of things that must survive, cannot
    distinguish a working filter from one that returns True unconditionally,
    and it is what let the inversion ship.
    """

    KAELEN_CONFIG = {
        "character_name": "Kaelen",
        "role": "weaponsmith, merchant, co-proprietor of Iron & Oath",
        "knowledge_scope": ["metallurgy, edge geometry, weapon balance"],
        "system_prompt_snippet": "You are Kaelen, a weaponsmith.",
    }

    def _kaelen(self):
        return chat_npc(name="Kaelen", _chat_char_config=self.KAELEN_CONFIG)

    @pytest.mark.parametrize(
        "text",
        [
            # Kaelen's own stock, priced.
            "How much for the sword?",
            "How much for the spear?",
            "How much for the dagger?",
            "What is the price of this sword?",
            "Do you have any bows?",
            "Would you carry a lighter blade?",
            # Vespera's half, so the armour nouns are not lost in the fix.
            "How much for the leather armor?",
            "Do you have any helmets?",
            # The string this feature's own module docstring names first.
            "What are you looking to buy?",
        ],
    )
    def test_commerce_at_the_arms_stall_is_suppressed(self, text):
        assert self._kaelen()._is_merchant_commerce_question(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            # Provenance, maintenance, craft, lore — the substitutes the TRADE
            # block asks the model for. Suppressing these is how the pool of
            # generic filler ended up in Kaelen's and Vespera's mouths.
            "Where did you get that leather?",
            "How do you keep the chain from rusting?",
            "Who taught you to work leather?",
            "How does a spear hold its edge?",
            "What is the story behind that blade?",
            "How long have you worked the forge?",
            "Where do you keep the good steel?",
            "How do you carry a blade that long?",
        ],
    )
    def test_craft_and_provenance_questions_survive(self, text):
        assert self._kaelen()._is_merchant_commerce_question(text) is False

    def test_the_rule_is_still_scoped_to_merchant_context(self):
        friend = _friend()
        assert friend._is_merchant_commerce_question("How much for the sword?") is False


class TestMerchantVocabularyHasOneSpelling:
    """Finding 4: the item half of the rule must not be spelled twice."""

    def test_the_item_pattern_is_built_from_the_guard_vocabulary(self):
        from src.npc import _chat_guard, _chat_llm

        assert _chat_guard.MERCHANDISE in _chat_llm._MERCHANT_ITEM_PATTERN.pattern

    @pytest.mark.parametrize(
        "noun", ["sword", "spear", "dagger", "leather", "chain", "helmet", "cuirass"]
    )
    def test_both_readers_of_the_vocabulary_agree(self, noun):
        """A noun a merchant sells is a noun the guard calls a possession."""
        import re

        from src.npc import _chat_guard, _chat_llm

        possessions = re.compile(
            r"\b(?:" + _chat_guard._POSSESSIONS + r")\b", re.IGNORECASE
        )
        assert _chat_llm._MERCHANT_ITEM_PATTERN.search(noun)
        assert possessions.search(noun)

    def test_coin_words_are_deliberately_not_merchandise(self):
        """"The gold in this region" is lore, not a price question."""
        from src.npc import _chat_llm

        for word in ("gold", "coin", "silver"):
            assert not _chat_llm._MERCHANT_ITEM_PATTERN.search(word)

    def test_the_prompt_and_the_classifier_name_the_same_substitutes(self):
        """All three spellings of the substitute list are one string.

        There were three: this module's ``TRADE`` block, the classifier's
        exclusions, and ``ai.llm_client._MERCHANT_OPTION_RULE`` -- and two of
        them had drifted ("or lore" against "or general lore") before they were
        consolidated onto ``MERCHANT_SUBSTITUTE_TOPICS``. Asserting only that
        the block contains the constant it is built from would pass for any
        value of the constant, so reach across to the other module too: that
        edge is the one that actually rotted.
        """
        from ai.llm_client import MERCHANT_SUBSTITUTE_TOPICS, _MERCHANT_OPTION_RULE
        from src.npc import _chat_llm

        assert _chat_llm.MERCHANT_SUBSTITUTE_TOPICS is MERCHANT_SUBSTITUTE_TOPICS
        assert MERCHANT_SUBSTITUTE_TOPICS in _merchant()._build_trade_block()
        assert MERCHANT_SUBSTITUTE_TOPICS in _MERCHANT_OPTION_RULE

    def test_the_substitute_topics_survive_the_classifier(self):
        """The list the model is handed must not be what QC then punishes.

        The round-nine defect was exactly this: the prompt told the model to
        steer toward provenance and maintenance, and the classifier suppressed
        provenance and maintenance. A guard on the shared string alone would
        not have caught it, because both halves named the same topics and only
        the regex disagreed.
        """
        from ai.llm_client import MERCHANT_SUBSTITUTE_TOPICS

        merchant = _merchant()

        topics = [
            t.strip()
            for t in MERCHANT_SUBSTITUTE_TOPICS.replace(" or ", ", ").split(",")
            if t.strip()
        ]
        assert len(topics) >= 4, topics
        probes = {
            "craft": "Did you craft this yourself?",
            "fit": "Would this fit a taller man?",
            "maintenance": "How do you keep the chain from rusting?",
            "provenance": "Where did you learn the trade?",
            "general lore": "What do the nomads say about the pass?",
        }
        for topic in topics:
            probe = probes.get(topic)
            assert probe is not None, (
                f"substitute topic {topic!r} has no probe; add one so the "
                "classifier is checked against every topic the prompt names"
            )
            assert not merchant._is_merchant_commerce_question(probe), (
                f"{topic!r} is advertised to the model but suppressed by QC: "
                f"{probe!r}"
            )


class TestMerchantPromptRule:
    def test_merchant_system_prompt_forbids_price_and_stock_talk(self):
        prompt = _merchant()._build_system_prompt(chat_player())
        assert "TRADE" in prompt
        low = prompt.lower()
        assert "price" in low and "stock" in low

    def test_non_merchant_prompt_has_no_trade_rule(self):
        prompt = _friend()._build_system_prompt(chat_player())
        assert "TRADE" not in prompt

    def test_vespera_config_does_not_advertise_price_negotiation(self):
        import json
        from pathlib import Path

        cfg = json.loads(
            Path("ai/npc/human/vespera.json").read_text(encoding="utf-8")
        )
        blob = " ".join(cfg.get("knowledge_scope", [])).lower()
        assert "pricing" not in blob
        assert "negotiation" not in blob


# ---------------------------------------------------------------------------
# 2. Jean's name in Jean's own options
# ---------------------------------------------------------------------------


class TestJeanNameInOptions:
    @pytest.mark.parametrize(
        "text",
        [
            "Jean has walked a long road to get here.",
            "Ask her about Jean's armor fit.",
            "What would Jean know about the western road?",
            "Jean nods and waits for her to continue.",
            "Tell Jean what the river took from you.",
        ],
    )
    def test_third_person_jean_option_dropped(self, text):
        npc = chat_npc()
        kept = _texts(npc._qc_jean_options(_opts(text, "Go on, then.")))
        assert text not in kept
        assert "Go on, then." in kept

    @pytest.mark.parametrize(
        "text",
        [
            "I'm Jean's guide through the eastern pass.",
            "My name is Jean. Jean has seen worse roads.",
        ],
    )
    def test_name_in_a_non_introduction_is_dropped(self, text):
        npc = chat_npc()
        assert text not in _texts(npc._qc_jean_options(_opts(text)))

    @pytest.mark.parametrize(
        "text",
        [
            "My name is Jean. I came down from the north.",
            "I'm Jean, and I could use directions.",
            "I am Jean Claire, late of the crusade.",
            "They call me Jean.",
            "Call me Jean, that is enough for now.",
        ],
    )
    def test_self_introduction_survives(self, text):
        npc = chat_npc()
        assert text in _texts(npc._qc_jean_options(_opts(text)))

    def test_ordinary_self_reference_survives(self):
        npc = chat_npc()
        texts = [
            "I have seen worse roads than this one.",
            "You would know better than me.",
            "What did you do before the camp?",
        ]
        assert _texts(npc._qc_jean_options(_opts(*texts))) == texts

    def test_fallback_pool_carries_no_jean_and_no_commerce(self):
        npc = _merchant()
        for pool in _JEAN_FALLBACK_POOL:
            for option in pool:
                assert "jean" not in option["text"].lower()
        # And the pool survives its own QC in merchant context.
        for pool in _JEAN_FALLBACK_POOL:
            assert len(npc._qc_jean_options([dict(o) for o in pool])) == 3


# ---------------------------------------------------------------------------
# 3. Loquacity scaled to 15%
# ---------------------------------------------------------------------------


class TestLoquacityScalingRule:
    def test_scale_is_fifteen_percent(self):
        assert LOQUACITY_SCALE_PERCENT == 15

    @pytest.mark.parametrize(
        "raw,scaled",
        [
            (0, 0),      # a zero pool stays zero (the "not computed" sentinel)
            (1, 1),      # floor: a positive pool never scales away to nothing
            (2, 1),
            (10, 2),     # 1.5 -> 2 (half up)
            (20, 3),
            (60, 9),
            (80, 12),
            (100, 15),
            (150, 23),   # 22.5 -> 23 (half up)
        ],
    )
    def test_scale_loquacity_rounds_half_up_with_floor_of_one(self, raw, scaled):
        assert scale_loquacity(raw) == scaled


class TestComputeLoquacityScaled:
    def _player(self, **overrides):
        base = {"charisma": 10, "equipped": {}, "allies": []}
        base.update(overrides)
        return chat_player(**base)

    def test_config_base_scaled_to_fifteen_percent(self):
        npc = _merchant()
        npc._compute_loquacity(self._player())
        assert npc.loquacity_max == scale_loquacity(80)
        assert npc.loquacity_current == npc.loquacity_max

    def test_default_base_scaled(self):
        npc = chat_npc()
        npc._compute_loquacity(self._player())
        assert npc.loquacity_max == scale_loquacity(60)

    def test_personality_base_scaled(self):
        npc = chat_npc(_chat_personality={"loquacity_base": 40})
        npc._compute_loquacity(self._player())
        assert npc.loquacity_max == scale_loquacity(40)

    def test_modifiers_are_scaled_too(self):
        """A modifier left at the old scale would dominate the new pool."""
        npc = chat_npc(charisma=15)  # +15 NPC charisma bonus
        npc._compute_loquacity(
            self._player(
                charisma=15,  # +10 Jean charisma
                reputation={"TestNPC": 1},  # +20
                equipped={"neck": {"name": "Crucifix"}},  # +10
            )
        )
        assert npc.loquacity_max == scale_loquacity(60 + 15 + 20 + 10 + 10)

    def test_floor_is_scaled_not_twenty(self):
        npc = chat_npc(charisma=1)
        npc._compute_loquacity(self._player(charisma=1, reputation={"TestNPC": -1}))
        assert npc.loquacity_max == scale_loquacity(20)

    def test_threshold_keeps_one_fifth_ratio_with_scaled_floor(self):
        npc = _merchant()
        npc._compute_loquacity(self._player())
        assert npc.loquacity_threshold == max(
            scale_loquacity(10), npc.loquacity_max // 5
        )
        assert 1 <= npc.loquacity_threshold <= npc.loquacity_max

    def test_recovery_scaled_but_never_zero(self):
        npc = chat_npc(wisdom=16)
        npc._compute_loquacity(self._player())
        assert npc.loquacity_recovery == scale_loquacity(16 // 8)
        assert npc.loquacity_recovery >= 1

    def test_init_default_recovery_is_scaled(self):
        assert chat_npc().loquacity_recovery == scale_loquacity(2)

    def test_tick_still_tops_up_to_the_scaled_max(self):
        npc = _merchant()
        npc._compute_loquacity(self._player())
        npc.loquacity_current = 0
        for _ in range(200):
            npc.loquacity_tick()
        assert npc.loquacity_current == npc.loquacity_max


class TestPersistedLoquacityRescaled:
    def _npc(self, computed_max):
        return chat_npc(
            init=False,
            _chat_history=[],
            _chat_personality=None,
            loquacity_current=0,
            loquacity_max=computed_max,
            _chat_npc_key="test_key",
        )

    def _load(self, npc, entry):
        player = chat_player(npc_chat_histories={"test_key": entry})
        npc._load_history_from_persistence(player)
        return npc.loquacity_current

    def test_old_scale_current_rescaled_proportionally(self):
        npc = self._npc(scale_loquacity(80))  # 12
        restored = self._load(
            npc, {"exchanges": [], "loquacity_current": 72, "loquacity_max": 80}
        )
        assert restored == 11  # 72/80 of 12, half up
        assert restored <= npc.loquacity_max

    def test_old_scale_current_without_stored_max_is_clamped(self):
        npc = self._npc(scale_loquacity(80))
        assert self._load(npc, {"exchanges": [], "loquacity_current": 99}) == 12

    def test_exhausted_stays_exhausted(self):
        npc = self._npc(scale_loquacity(80))
        assert (
            self._load(
                npc, {"exchanges": [], "loquacity_current": 0, "loquacity_max": 80}
            )
            == 0
        )

    def test_new_scale_value_restored_verbatim(self):
        npc = self._npc(scale_loquacity(80))
        assert (
            self._load(
                npc, {"exchanges": [], "loquacity_current": 8, "loquacity_max": 12}
            )
            == 8
        )

    def test_uncomputed_max_leaves_stored_value_alone(self):
        """``_load_history_from_persistence`` is called directly by tests and by
        hosts that skip ``_compute_loquacity``; with no computed max there is
        nothing to rescale against."""
        npc = self._npc(0)
        assert self._load(npc, {"exchanges": [], "loquacity_current": 42}) == 42

    def test_saved_entry_carries_new_scale_values(self):
        npc = _merchant()
        player = chat_player(npc_chat_histories={})
        npc._compute_loquacity(chat_player(charisma=10, equipped={}, allies=[]))
        npc._chat_npc_key = "Vespera"
        npc._save_exchange_to_persistence(player, "Line.", "", 1, "1")
        entry = player.npc_chat_histories["Vespera"]
        assert entry["loquacity_max"] == scale_loquacity(80)
        assert entry["loquacity_recovery"] == npc.loquacity_recovery


# ---------------------------------------------------------------------------
# 4. Provider prompt reinforcement (still no live calls)
# ---------------------------------------------------------------------------


def _captured_adapter(raw):
    captured = []

    def call(system, user, **kwargs):
        captured.append({"system": system, "user": user, "kwargs": kwargs})
        return raw

    return make_chat_adapter(provider=None, api_key=None, _call_llm=call), captured


class TestProviderPromptReinforcement:
    def test_combined_prompt_prohibits_jean_third_person_and_merchant_trade(self):
        adapter, captured = _captured_adapter(
            '{"npc_text":"The straps are sound.","jean_options":[]}'
        )
        adapter.generate_turn(
            "SYSTEM\nTRADE: shop UI handles price and stock.", [], is_opening=True
        )
        user = captured[0]["user"].lower()
        assert "third person" in user
        assert "genuine self-introduction" in user
        assert "price" in user and "inventory" in user

    def test_legacy_options_prompt_prohibits_jean_third_person(self):
        adapter, captured = _captured_adapter(
            '{"options":[{"tone":"direct","text":"Go on, then."},'
            '{"tone":"guarded","text":"I see."},'
            '{"tone":"open","text":"Tell me more."}]}'
        )
        adapter.generate_jean_options(
            "Vespera", "warm", "The straps are sound.", [], 1
        )
        user = captured[0]["user"].lower()
        assert "third person" in user
        assert "genuine self-introduction" in user
