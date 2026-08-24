"""Adversarial guard against implied game-state changes in LLM chat output.

Conversations are lore and character exploration only. No hook exists between
anything said in a chat and the engine: an NPC who says "here, take this blade"
does not create an item, one who says "I'll come with you" does not join the
party, and one who says "that sword of yours is failing" is guessing at an
inventory it cannot read. Every such line is a promise the game will not keep,
and the player is the one who discovers that.

This module is the interception layer. It is deliberately split into a cheap
part and an expensive part:

* ``scan_npc_text`` / ``scan_option_text`` are pure regex tripwires that run on
  every turn and cost nothing. Most turns never trip them.
* Only a tripped turn escalates to an LLM revision pass (see
  ``ConversationalNPCMixin._guard_turn``), which is why the patterns below aim
  to be *specific* rather than exhaustive — a false positive costs a real
  round trip and rewrites a line that was fine.
* ``hedge_npc_text`` is the deterministic last resort for when that revision
  call is unavailable or comes back still dirty. It never invents new prose
  beyond a fixed hedge per category.

Four violation classes, in the order they are scanned (the first flag decides
how the turn is described to the reviser):

``transaction``   handing over goods, escorting Jean, teaching, mending
``state_claim``   claims about Jean's gear, wounds, coin, or past deeds
``commitment``    arranging a future meeting or promising a later favour
``solicit``       a Jean *option* that asks the NPC for any of the above
"""

import re
from typing import Dict, Iterable, List, NamedTuple, Sequence, Set, Tuple

CATEGORY_TRANSACTION = "transaction"
CATEGORY_STATE_CLAIM = "state_claim"
CATEGORY_COMMITMENT = "commitment"
CATEGORY_SOLICIT = "solicit"

# Subcategories the allowed-topic whitelist may excuse. A progressing ally is
# *meant* to talk about its own techniques and growth (the combat block in the
# system prompt exists for exactly that), so a teaching line about a whitelisted
# topic is legitimate. Handing over goods and arranging meetings are never
# excusable, however on-topic they are — otherwise a knowledge_scope entry like
# "the ferry crossing" would license "I'll give you a knife for the crossing".
# NOTE: no pattern emits subcategory "growth" today — the entry is reserved
# for a future growth-flavoured pattern; growth talk is currently excused via
# topic words on "teaching" flags.
_EXCUSABLE_SUBCATEGORIES = frozenset({"teaching", "growth"})

# The state_claim patterns are written in the second person because they exist
# to catch an NPC guessing at *Jean's* gear, wounds, coin, or deeds. Inside a
# Jean *option* the second person points the other way — "your" is the NPC —
# so those same patterns fire on perfectly good lore questions ("Where did you
# get your sword?", "You're wounded — should you be working?"). Only the
# subcategories that stay wrong in either mouth are scanned on options.
_OPTION_SKIP_SUBCATEGORIES = frozenset({"belongings", "condition", "deeds", "coin"})

_SENTENCE_PATTERN = re.compile(r"[^.!?]+[.!?]*")

# Topics are matched as whole words: substring containment let a four-letter
# topic like "edge" excuse any sentence containing "knowledge".
_WORD_PATTERN = re.compile(r"[a-z0-9']+")

# First-person offer openers ("I'll", "let me", "shall I", ...). Written once
# and interpolated so every offer pattern accepts the same set of contractions,
# including the typographic apostrophe the models emit about half the time.
# The leading \b is load-bearing: without it, IGNORECASE lets "I'll"/"I'd"
# match the tails of ordinary words ("will" contains "ill", "druid" contains
# "id"), flagging lines like "The ferry will take you across." as offers.
_OFFER = r"\b(?:I(?:['’])?ll|I will|I can|I could|I(?:['’])?d|let me|shall I)"
# Up to two filler words between the opener and the verb ("I'll happily give").
_GAP = r"(?:\w+\s+){0,2}?"

_POSSESSIONS = (
    r"sword|blade|knife|axe|spear|bow|arrows?|armou?r|mail|shield|helm|pack|"
    r"purse|coins?|gold|silver|rations|supplies|provisions|weapons?|gear|"
    r"boots|cloak|map|wounds?|injuries|injury|belongings"
)

_NUMBERS = (
    r"\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"twenty|thirty|forty|fifty|a hundred"
)

# (subcategory, compiled pattern) per category. Subcategories drive both the
# whitelist and the hedge, so they are part of the contract, not a comment.
_PATTERNS: Dict[str, Sequence[Tuple[str, "re.Pattern"]]] = {
    CATEGORY_TRANSACTION: (
        # "Here, take this blade." — imperative handover. The negative
        # lookahead exempts idioms with no object transfer: "Keep that in
        # mind.", "I take it you have come about the ferry."
        (
            "handover",
            re.compile(
                r"\b(?:take|keep|have)\s+(?:this|these|that|those|it|them|my|mine)\b"
                r"(?!\s+(?:in\s+mind\b|you\b))",
                re.IGNORECASE,
            ),
        ),
        # "I'll give you a knife." — offered handover. The object token is
        # required: bare "I can make" or "I'll get" are ordinary speech.
        (
            "handover",
            re.compile(
                _OFFER + r"\s+" + _GAP + r"(?:give|hand|lend|spare|sell|trade|fetch|"
                r"bring|offer|pass|leave)\s+(?:you|it|them|him|her|me|a|an|the|"
                r"some|my|that|this|these|those)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "handover",
            re.compile(
                _OFFER + r"\s+" + _GAP + r"(?:get\s+you\b|make\s+you\s+(?:a|an|one)\b)",
                re.IGNORECASE,
            ),
        ),
        # "She presses a coin into your palm." — third-person handover, the
        # form npc_flavor beats take. The lookahead keeps it to transfers aimed
        # at Jean: "he hands the reins to the boy" is scene-setting, not a gift.
        (
            "handover",
            re.compile(
                r"\b(?:gives?|offers?|hands?|presses|passes|slips|tosses|slides|"
                r"pushes|holds out|sets down)\s+(?:you\s+|jean\s+|him\s+|her\s+)?"
                r"(?:a|an|the|some|his|her|their|it|them)\b"
                r"(?=[^.!?]*\b(?:you|your|jean)\b)",
                re.IGNORECASE,
            ),
        ),
        # "I'll come with you as far as the water." — escort.
        (
            "escort",
            re.compile(
                _OFFER + r"\s+" + _GAP + r"(?:come|go|walk|ride|travel|follow|join|"
                r"accompany|lead|guide|take)\s+(?:with\s+you|you\b|along\b)",
                re.IGNORECASE,
            ),
        ),
        # "I could teach you that grip." — training. Excusable for an ally
        # speaking about a whitelisted technique of its own.
        (
            "teaching",
            re.compile(
                r"\b(?:teach|train)\s+you\b|\bshow\s+you\s+(?:how|the way|where)\b",
                re.IGNORECASE,
            ),
        ),
        # "Let me tend those cuts." — services on Jean's person or gear.
        (
            "service",
            re.compile(
                _OFFER + r"\s+" + _GAP + r"(?:tend|mend|patch|repair|bind|dress|"
                r"heal|stitch|sharpen|forge|fix)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    CATEGORY_STATE_CLAIM: (
        ("belongings", re.compile(r"\byour\s+(?:\w+\s+){0,1}?(?:" + _POSSESSIONS + r")\b", re.IGNORECASE)),
        (
            "belongings",
            re.compile(
                r"\b(?:that|those|the)\s+(?:\w+\s+){0,2}?(?:" + _POSSESSIONS + r")\s+"
                r"(?:of yours|you carry|you(?:['’])?re carrying|you bear|"
                r"you have|you(?:['’])?ve got)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "condition",
            re.compile(
                r"\byou(?:(?:['’])?re|\s+are)\s+(?:\w+\s+){0,1}?(?:wounded|"
                r"bleeding|hurt|injured|carrying|hauling|wearing|armed|starving|"
                r"out of|low on|short of)\b",
                re.IGNORECASE,
            ),
        ),
        ("coin", re.compile(r"\b(?:" + _NUMBERS + r")\s+(?:coins?|gold|silver|pieces?|marks?)\b", re.IGNORECASE)),
        (
            "deeds",
            re.compile(
                r"\bsince you\s+(?:killed|slew|defeated|freed|saved|found|opened|burned|took)\b"
                r"|\byou(?:['’])?ve\s+(?:killed|slain|defeated|freed|saved)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "game_terms",
            re.compile(
                r"\b(?:experience points|hit points|stat points|inventory|equipment slot)\b|\bXP\b",
                re.IGNORECASE,
            ),
        ),
    ),
    CATEGORY_COMMITMENT: (
        # A rendezvous needs both the summons and a time/condition — otherwise
        # "people find me odd" trips it.
        (
            "rendezvous",
            re.compile(
                r"\b(?:come\s+(?:find|see|back)|find|meet|seek)\s+me\b"
                r"(?=[^.!?]*\b(?:at|by|when|after|once|tomorrow|dawn|dusk|nightfall|"
                r"morning|evening|later|then|again)\b)"
                r"|\bcome\s+back\s+(?:when|after|once|tomorrow|at)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "promise",
            re.compile(
                r"\bI(?:['’])?ll\s+(?:be\s+(?:waiting|here|around)\b|"
                r"wait\s+for\s+you\b|see\s+you\s+(?:then|again|tomorrow|at)\b|"
                r"meet\s+you\b|find\s+you\b|"
                r"(?:keep|hold|save|set\s+aside)\s+(?:it|one|that|them|this)\s+"
                r"(?:for\s+you|aside|back|safe)\b)",
                re.IGNORECASE,
            ),
        ),
        ("deferral", re.compile(r"\bask\s+me\s+(?:again|when|once|after)\b", re.IGNORECASE)),
        (
            "deferral",
            re.compile(
                r"\b(?:some\s?day|one day|another time|next time|"
                r"when you (?:return|come back|get back|pass through))\b",
                re.IGNORECASE,
            ),
        ),
    ),
    CATEGORY_SOLICIT: (
        (
            "request",
            re.compile(
                r"\b(?:will|can|could|would)\s+you\s+(?:\w+\s+){0,2}?(?:come|join|"
                r"follow|guide|lead|take|give|lend|spare|sell|teach|show|help|"
                r"carry|escort|mend|fix|forge)\b",
                re.IGNORECASE,
            ),
        ),
        ("request", re.compile(r"\b(?:come|travel|ride|walk|go)\s+with\s+me\b", re.IGNORECASE)),
        (
            "request",
            re.compile(
                r"\b(?:teach|show|give|lend|sell|hand|spare|fetch|bring)\s+me\b",
                re.IGNORECASE,
            ),
        ),
        (
            "payment",
            re.compile(
                r"\bI(?:['’])?ll\s+(?:pay|buy|trade)\b|\bI have coin\b",
                re.IGNORECASE,
            ),
        ),
    ),
}

# Deterministic replacements for when the LLM revision pass is unavailable or
# still dirty. Kept register-neutral so they fit any speaking NPC, and kept
# clean of every pattern above (asserted in tests/test_npc_chat_state_guard.py).
# The commitment hedge defuses into ambient fact rather than refusing outright.
_HEDGES = {
    CATEGORY_TRANSACTION: "That's not mine to give.",
    CATEGORY_STATE_CLAIM: "I'd not presume to know your business.",
    CATEGORY_COMMITMENT: "I'm about most days. The road decides the rest.",
    CATEGORY_SOLICIT: "That's not a thing to ask for here.",
}

# Sent to the reviser only on escalation, so a little prose here is affordable.
_GUIDANCE = {
    CATEGORY_TRANSACTION: (
        "transaction: the character offered to give, lend, sell, mend, teach, or "
        "travel with Jean. Nothing said in conversation reaches the game, so the "
        "offer can never be honoured. Rewrite so such things are spoken of in the "
        "past or in general — what exists, what was done once, what others do — "
        "never as an offer to Jean now. A merchant may say their work exists and "
        "where it sits; they may not price it, promise it, or hand it over."
    ),
    CATEGORY_STATE_CLAIM: (
        "state_claim: the character described Jean's belongings, wounds, coin, or "
        "past deeds. The character cannot see any of that and the conversation "
        "cannot read it. Rewrite with no claim about what Jean carries, wears, or "
        "has done."
    ),
    CATEGORY_COMMITMENT: (
        "commitment: the character arranged a later meeting or promised a future "
        "favour. Nothing will come of it. Recast the promise as an ambient fact "
        "about the character's habits or the world ('I'm here most mornings'), "
        "not an appointment."
    ),
    CATEGORY_SOLICIT: (
        "solicit: one of Jean's replies asked the character for goods, escort, or "
        "training. Replace it with a reply that pursues the same subject as talk — "
        "what it is, where it came from, who else knows — without requesting "
        "anything."
    ),
}

# To add a category: define its CATEGORY_* constant, then give it a row in ALL
# THREE tables above (_PATTERNS, _HEDGES, _GUIDANCE) — hedge_npc_text and
# guidance_for index the latter two directly, so a missing row is a runtime
# KeyError mid-turn. This assert makes the omission fail at import instead.
assert set(_PATTERNS) == set(_HEDGES) == set(_GUIDANCE)


class GuardFlag(NamedTuple):
    """One tripwire hit.

    ``sentence`` is the whole sentence the match sits in — the hedge replaces at
    sentence granularity, since excising a clause leaves grammatical wreckage.
    """

    category: str
    subcategory: str
    match: str
    sentence: str


def _sentences(text: str) -> List[str]:
    return [s for s in _SENTENCE_PATTERN.findall(text or "") if s.strip()]


def _excused(flag: GuardFlag, allowed_topics: Set[str]) -> bool:
    """True when a whitelisted topic licenses this flag.

    Only teaching- and growth-flavoured hits are excusable, and only when the
    sentence actually names an allowed topic.
    """
    if flag.subcategory not in _EXCUSABLE_SUBCATEGORIES:
        return False
    low = flag.sentence.lower()
    words = set(_WORD_PATTERN.findall(low))
    for topic in allowed_topics:
        if not topic:
            continue
        # Multi-word topics (move names like "river cut") are checked as a
        # whole-word phrase; single tokens must match a whole word. Bare
        # substring containment let "river cut" excuse "the driver cutlass".
        if " " in topic:
            if re.search(r"\b" + re.escape(topic) + r"\b", low):
                return True
        elif topic in words:
            return True
    return False


def _scan(
    text: str,
    categories: Sequence[str],
    allowed_topics: Iterable[str] = (),
    skip_subcategories: Iterable[str] = (),
) -> List[GuardFlag]:
    if not text:
        return []
    topics = {str(t).lower() for t in (allowed_topics or ())}
    skip = frozenset(skip_subcategories or ())
    sentences = _sentences(text)
    flags: List[GuardFlag] = []
    for category in categories:
        for subcategory, pattern in _PATTERNS[category]:
            if subcategory in skip:
                continue
            for sentence in sentences:
                match = pattern.search(sentence)
                if not match:
                    continue
                flag = GuardFlag(category, subcategory, match.group(0), sentence)
                if _excused(flag, topics):
                    continue
                flags.append(flag)
    return flags


def scan_npc_text(text: str, allowed_topics: Iterable[str] = ()) -> List[GuardFlag]:
    """Flag state-implying content in an NPC's spoken line or flavor beat."""
    return _scan(
        text,
        (CATEGORY_TRANSACTION, CATEGORY_STATE_CLAIM, CATEGORY_COMMITMENT),
        allowed_topics,
    )


def scan_option_text(text: str, allowed_topics: Iterable[str] = ()) -> List[GuardFlag]:
    """Flag a Jean dialogue option that solicits or assumes a state change."""
    return _scan(
        text,
        (CATEGORY_SOLICIT, CATEGORY_STATE_CLAIM, CATEGORY_COMMITMENT),
        allowed_topics,
        _OPTION_SKIP_SUBCATEGORIES,
    )


def hedge_npc_text(text: str, flags: Sequence[GuardFlag]) -> str:
    """Replace each flagged sentence with the fixed hedge for its category.

    Unflagged sentences survive verbatim, so a three-sentence reply with one bad
    clause keeps two thirds of its character. Consecutive identical hedges
    collapse, so a reply that was bad throughout does not stutter.
    """
    if not flags:
        return text
    hedge_by_sentence = {}
    for flag in flags:
        hedge_by_sentence.setdefault(flag.sentence, _HEDGES[flag.category])

    out: List[str] = []
    for sentence in _sentences(text):
        replacement = hedge_by_sentence.get(sentence)
        piece = replacement if replacement is not None else sentence.strip()
        # A line that ends inside quotes ("... here.'") splits into a trailing
        # fragment of pure punctuation. Keeping it produced visible wreckage
        # ("We'll be here. '.") once the terminal-punctuation fixup ran.
        if not piece or not any(ch.isalnum() for ch in piece):
            continue
        # Collapse only repeated *hedges* — a legitimately repeated sentence
        # ("No. No.") is the author's/model's cadence, not stutter.
        if out and replacement is not None and out[-1] == piece:
            continue
        out.append(piece)

    result = " ".join(out).strip()
    if not result:
        result = _HEDGES[flags[0].category]
    if result[-1] not in ".!?":
        result += "."
    return result


def guidance_for(flags: Iterable[GuardFlag]) -> str:
    """Build the reviser's instruction block from the categories that tripped."""
    seen: List[str] = []
    for flag in flags:
        if flag.category not in seen:
            seen.append(flag.category)
    return "\n".join(_GUIDANCE[category] for category in seen)
