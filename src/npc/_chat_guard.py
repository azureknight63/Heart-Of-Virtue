"""Adversarial guard against implied game-state changes in LLM chat output.

Conversations are lore and character exploration only. Nothing an NPC *says*
is wired to the engine: an NPC who says "here, take this blade" does not create
an item, one who says "I'll come with you" does not join the party, and one who
says "that sword of yours is failing" is guessing at an inventory it cannot
read. Every such line is a promise the game will not keep, and the player is
the one who discovers that.

Two *structured* fields of the same model response DO reach the engine, so the
prose above is about the prose only:

* ``reputation_delta`` is clamped and then written to ``player.reputation`` by
  ``ConversationalNPCMixin._apply_reputation``, and ``ShopSerializer`` turns
  that number into real charged prices (up to +/-15% at +/-100). A turn that
  trips this guard therefore has its ``reputation_delta`` zeroed by
  ``_guard_turn``'s caller — a line the model had to be talked out of does not
  also get to move the player's standing.
* ``loquacity_delta`` is the second channel: it drains (or restores) the NPC's
  willingness to keep talking and persists in the save file. It is clamped, and
  it can only end a conversation early, so it is left alone.

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

Four violation classes. Which of the two scans covers each is a table
(``_SCAN_SCOPE``), not a hand-written tuple per scan, and within a scan they are
walked in the order below — the first flag decides how the turn is described to
the reviser, so the category a scan exists to catch leads it:

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
# Talk about an ally's own growth is excused via topic words on "teaching"
# flags; there is no separate "growth" subcategory (an entry naming one sat
# here unreachable, and the integrity check below now makes that class of typo
# fail at import instead of failing *open* — an unmatched name silently
# excuses nothing).
_EXCUSABLE_SUBCATEGORIES = frozenset({"teaching"})

# The state_claim patterns are written in the second person because they exist
# to catch an NPC guessing at *Jean's* gear, wounds, coin, or deeds. Inside a
# Jean *option* the second person points the other way — "your" is the NPC —
# so those same patterns fire on perfectly good lore questions ("Where did you
# get your sword?", "You're wounded — should you be working?"). Only the
# subcategories that stay wrong in either mouth are scanned on options.
_OPTION_SKIP_SUBCATEGORIES = frozenset({"belongings", "condition", "deeds", "coin"})

# Sentence splitter that KEEPS each sentence's own terminator ("Stay back!"
# stays an exclamation; "What do you want?" stays a question; "Well... maybe."
# keeps its ellipsis). Splitting on [.!?] and re-joining with ". " — the old
# approach — flattened every ! and ? in NPC dialogue into a period. Private to
# this module: _chat_llm consumes the split through :func:`split_sentences`
# rather than re-deriving it from the pattern.
_SENTENCE_PATTERN = re.compile(r"[^.!?]+[.!?]*")

# Sentence terminators and quote characters, spelled once. These were
# hand-written seven times across this module and _chat_llm in four mutually
# inconsistent variants (`".!?"`, `'.!?"''`, `'"'”’'`, `'.!?"'*'`), which is
# exactly how curly quotes came to be handled at one site and not its
# neighbour. _QUOTE_CHARS covers both directions because a token can open a
# quotation as well as close one; _CLOSING_QUOTES is the subset that can
# legitimately trail a terminator.
_TERMINATORS = ".!?"
_CLOSING_QUOTES = "\"'”’»"
_QUOTE_CHARS = "\"'“”‘’«»"
_SENTENCE_BOUNDARY_CHARS = _TERMINATORS + _QUOTE_CHARS

_ALNUM_PATTERN = re.compile(r"[A-Za-z0-9]")

# Topics are matched as whole words: substring containment let a four-letter
# topic like "edge" excuse any sentence containing "knowledge".
_WORD_PATTERN = re.compile(r"[a-z0-9']+")

# Curly vs straight apostrophe: models emit both about equally, so every
# pattern that needs a contraction interpolates this instead of hand-spelling
# the alternation.
_APO = r"(?:['’])?"

# First-person offer openers ("I'll", "let me", "shall I", ...). Written once
# and interpolated so every offer pattern accepts the same set of contractions,
# including the typographic apostrophe the models emit about half the time.
# The leading \b is load-bearing: without it, IGNORECASE lets "I'll"/"I'd"
# match the tails of ordinary words ("will" contains "ill", "druid" contains
# "id"), flagging lines like "The ferry will take you across." as offers.
_OFFER = r"\b(?:I" + _APO + r"ll|I will|I can|I could|I" + _APO + r"d|let me|shall I)"
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
_PATTERNS: Dict[str, Sequence[Tuple[str, re.Pattern]]] = {
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
        (
            "belongings",
            re.compile(
                r"\byour\s+(?:\w+\s+){0,1}?(?:" + _POSSESSIONS + r")\b",
                re.IGNORECASE,
            ),
        ),
        (
            "belongings",
            re.compile(
                r"\b(?:that|those|the)\s+" + _GAP + r"(?:" + _POSSESSIONS + r")\s+"
                r"(?:of yours|you carry|you" + _APO + r"re carrying|you bear|"
                r"you have|you" + _APO + r"ve got)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "condition",
            re.compile(
                r"\byou(?:" + _APO + r"re|\s+are)\s+(?:\w+\s+){0,1}?(?:wounded|"
                r"bleeding|hurt|injured|carrying|hauling|wearing|armed|starving|"
                r"out of|low on|short of)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "coin",
            re.compile(
                r"\b(?:" + _NUMBERS + r")\s+(?:coins?|gold|silver|pieces?|marks?)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "deeds",
            re.compile(
                r"\bsince you\s+(?:killed|slew|defeated|freed|saved|found|opened|burned|took)\b"
                r"|\byou" + _APO + r"ve\s+(?:killed|slain|defeated|freed|saved)\b",
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
                r"\bI" + _APO + r"ll\s+(?:be\s+(?:waiting|here|around)\b|"
                r"wait\s+for\s+you\b|see\s+you\s+(?:then|again|tomorrow|at)\b|"
                r"meet\s+you\b|find\s+you\b|"
                r"(?:keep|hold|save|set\s+aside)\s+(?:it|one|that|them|this)\s+"
                r"(?:for\s+you|aside|back|safe)\b)",
                re.IGNORECASE,
            ),
        ),
        (
            "deferral",
            re.compile(
                r"\bask\s+me\s+(?:again|when|once|after)\b",
                re.IGNORECASE,
            ),
        ),
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
                r"\b(?:will|can|could|would)\s+you\s+" + _GAP + r"(?:come|join|"
                r"follow|guide|lead|take|give|lend|spare|sell|teach|show|help|"
                r"carry|escort|mend|fix|forge)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "request",
            re.compile(
                r"\b(?:come|travel|ride|walk|go)\s+with\s+me\b",
                re.IGNORECASE,
            ),
        ),
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
                r"\bI" + _APO + r"ll\s+(?:pay|buy|trade)\b|\bI have coin\b",
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

# The *prevention* half of the guard: one clause per category, interpolated
# into the system prompt by :func:`prompt_rules_line`. It lived as hand-written
# prose in ``_chat_llm._build_system_prompt`` and had already drifted — it
# covered transaction, state_claim and commitment but omitted CATEGORY_SOLICIT
# entirely, so every soliciting Jean option the model produced had to trip the
# tripwire and pay a real revision round trip that the other three categories
# were cheap enough to avoid. Written in the second person, addressed to the
# NPC, and terse: this block is static and re-sent every round.
PROMPT_RULES: Dict[str, str] = {
    CATEGORY_TRANSACTION: (
        "never give, lend, sell, mend, or hand anything over, and never travel "
        "with Jean"
    ),
    CATEGORY_STATE_CLAIM: (
        "never describe his belongings, wounds, or coin — you cannot see them"
    ),
    CATEGORY_COMMITMENT: (
        "never promise to meet him later or to do him a favour another day"
    ),
    CATEGORY_SOLICIT: (
        "never write a reply for Jean that asks you for goods, escort, or training"
    ),
}

SCAN_NPC = "npc"
SCAN_OPTION = "option"
_SCANS = frozenset({SCAN_NPC, SCAN_OPTION})

# Which of the two scans each category takes part in. ``scan_npc_text`` and
# ``scan_option_text`` used to hand-spell their own category tuples, which put
# them *outside* the integrity check below: a category could be given a row in
# all four tables above — prevented in the prompt, hedged, and explained to the
# reviser — and still never be scanned for. That is the identical fail-open
# shape as the CATEGORY_SOLICIT bug this module already closed, one table
# further along. Both scans are derived from this table instead.
#
# The second-person state_claim patterns fire on legitimate lore questions when
# they sit in a Jean option ("Where did you get your sword?"), which is what
# _OPTION_SKIP_SUBCATEGORIES trims — the category itself still belongs to both
# scans.
_SCAN_SCOPE: Dict[str, frozenset] = {
    CATEGORY_TRANSACTION: frozenset({SCAN_NPC}),
    CATEGORY_STATE_CLAIM: frozenset({SCAN_NPC, SCAN_OPTION}),
    CATEGORY_COMMITMENT: frozenset({SCAN_NPC, SCAN_OPTION}),
    CATEGORY_SOLICIT: frozenset({SCAN_OPTION}),
}

# To add a category: define its CATEGORY_* constant, then give it a row in ALL
# FIVE tables above (_PATTERNS, _HEDGES, _GUIDANCE, PROMPT_RULES, _SCAN_SCOPE).
# hedge_npc_text, guidance_for and prompt_rules_line index three of them
# directly, so a missing row is a runtime KeyError mid-turn (or, for
# PROMPT_RULES, a silently unprevented category); a missing _SCAN_SCOPE row is
# a category that is prevented and hedged but never actually scanned for.
# :func:`_check_tables` makes every such omission fail at import instead.
#
# Every subcategory any pattern can actually emit is derived from _PATTERNS
# rather than restated. The two subcategory allow/skip sets above are matched
# by *name* at scan time, so a typo in either of them fails OPEN — the flag is
# simply never excused or never skipped, with nothing to notice it. Deriving
# the universe and checking containment turns that into an import error too.
SUBCATEGORIES = frozenset(
    subcategory for rows in _PATTERNS.values() for subcategory, _pattern in rows
)


def _check_tables() -> None:
    """Fail at import if the category/subcategory tables have drifted apart.

    Deliberately ``raise`` rather than ``assert``: these are integrity guards,
    not debugging aids, and ``python -O`` strips ``assert`` — which would
    restore the exact silent fail-open (a missing table row, a mistyped
    subcategory) they exist to prevent, in the one configuration nobody tests.
    """
    categories = set(_PATTERNS)
    for name, table in (
        ("_HEDGES", _HEDGES),
        ("_GUIDANCE", _GUIDANCE),
        ("PROMPT_RULES", PROMPT_RULES),
        ("_SCAN_SCOPE", _SCAN_SCOPE),
    ):
        if set(table) != categories:
            raise RuntimeError(
                "_chat_guard: {} does not cover the same categories as _PATTERNS "
                "(missing={}, extra={})".format(
                    name,
                    sorted(categories - set(table)),
                    sorted(set(table) - categories),
                )
            )
    for category, scans in _SCAN_SCOPE.items():
        if not scans or not scans <= _SCANS:
            raise RuntimeError(
                "_chat_guard: _SCAN_SCOPE[{!r}]={} must be a non-empty subset of "
                "{}".format(category, sorted(scans), sorted(_SCANS))
            )
    for name, subcategories in (
        ("_EXCUSABLE_SUBCATEGORIES", _EXCUSABLE_SUBCATEGORIES),
        ("_OPTION_SKIP_SUBCATEGORIES", _OPTION_SKIP_SUBCATEGORIES),
    ):
        unknown = subcategories - SUBCATEGORIES
        if unknown:
            raise RuntimeError(
                "_chat_guard: {} names subcategories no pattern emits: {}".format(
                    name, sorted(unknown)
                )
            )


_check_tables()


def _scan_categories(scan: str) -> Tuple[str, ...]:
    """Categories ``scan`` covers, in the order :func:`_scan` walks them.

    ``_scan`` appends flags category by category and the first flag decides how
    the turn is described to the reviser, so the category a scan exists to
    catch has to lead. That is exactly the category scoped to this scan alone
    (``transaction`` for an NPC line, ``solicit`` for a Jean option); the
    categories shared with the other scan follow in declaration order. Derived
    rather than written out, so adding a category cannot leave one scan behind.
    """
    scoped = [c for c in _PATTERNS if scan in _SCAN_SCOPE[c]]
    return tuple(sorted(scoped, key=lambda c: len(_SCAN_SCOPE[c]) > 1))


_NPC_CATEGORIES = _scan_categories(SCAN_NPC)
_OPTION_CATEGORIES = _scan_categories(SCAN_OPTION)


def prompt_rules_line() -> str:
    """Render :data:`PROMPT_RULES` as the system prompt's prevention clause.

    Built from the same table the tripwire is checked against, so a category
    can never again be scanned for but not prevented.
    """
    return (
        "Talk changes nothing here: "
        + "; ".join(PROMPT_RULES.values())
        + ". Speak of such things in the past or in general instead."
    )


class GuardFlag(NamedTuple):
    """One tripwire hit.

    ``sentence`` is the whole sentence the match sits in — the hedge replaces at
    sentence granularity, since excising a clause leaves grammatical wreckage.
    """

    category: str
    subcategory: str
    match: str
    sentence: str


def split_sentences(text: str) -> List[str]:
    """Split ``text`` into sentences, each keeping its own terminator.

    ``_SENTENCE_PATTERN`` cuts immediately after ``.!?``, which strands the
    closing quote of a quoted sentence at the head of the *next* fragment:
    ``He said "no." Fine by me.`` split as ``['He said "no.', '" Fine by me.']``
    and the re-join then inserted a space before the quote, shipping
    ``He said "no. " Fine by me.`` to the player. A leading run of closing
    quotes belongs to the sentence before it, so it is re-attached and whatever
    follows stays a sentence of its own — the old repair only handled a
    fragment with no alphanumerics at all, i.e. only at end of text.

    The run must be followed by whitespace or end-of-fragment; ``'Tis`` opens a
    sentence with an apostrophe and must not be dismembered.
    """
    out: List[str] = []
    for raw in _SENTENCE_PATTERN.findall(text or ""):
        piece = raw.strip()
        if not piece:
            # Load-bearing for the two `out[-1][-1]`/`piece[0]` indexings
            # below: every element appended past this point is non-empty, so
            # neither can raise. Reordering this skip breaks that.
            continue
        if out and out[-1][-1] in _TERMINATORS and piece[0] in _CLOSING_QUOTES:
            run = len(piece) - len(piece.lstrip(_CLOSING_QUOTES))
            if run == len(piece) or piece[run].isspace():
                out[-1] += piece[:run]
                rest = piece[run:].strip()
                if rest:
                    out.append(rest)
                continue
        if out and not _ALNUM_PATTERN.search(piece):
            # Pure punctuation debris (an orphaned dash, a stray bracket).
            out[-1] += piece
            continue
        out.append(piece)
    return out


def ensure_terminal_punctuation(text: str) -> str:
    """Append a period unless ``text`` already ends a sentence.

    Looks *through* a trailing closing quote, so ``... the long road."`` is
    already terminated and does not gain a stray period after the quote.
    """
    if not text:
        return text
    last = text.rstrip(_CLOSING_QUOTES)[-1:]
    if last and last not in _TERMINATORS:
        return text + "."
    return text


def _excused(flag: GuardFlag, allowed_topics: Set[str]) -> bool:
    """True when a whitelisted topic licenses this flag.

    Only ``teaching`` hits are excusable (see _EXCUSABLE_SUBCATEGORIES), and
    only when the sentence actually names an allowed topic.
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
    """Return every tripwire hit in ``text`` for the given ``categories``.

    The one routine both public scans go through. Runs each category's patterns
    over each sentence in declaration order — the first flag is what names the
    violation to the reviser (see :func:`_scan_categories`) — skipping any
    subcategory in ``skip_subcategories`` and dropping any hit a whitelisted
    topic excuses. Pure and allocation-light: it is on every turn, and only a
    non-empty result costs a round trip.
    """
    if not text:
        return []
    topics = {str(t).lower() for t in (allowed_topics or ())}
    skip = frozenset(skip_subcategories or ())
    sentences = split_sentences(text)
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
    return _scan(text, _NPC_CATEGORIES, allowed_topics)


def scan_option_text(text: str, allowed_topics: Iterable[str] = ()) -> List[GuardFlag]:
    """Flag a Jean dialogue option that solicits or assumes a state change."""
    return _scan(
        text, _OPTION_CATEGORIES, allowed_topics, _OPTION_SKIP_SUBCATEGORIES
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
    for sentence in split_sentences(text):
        replacement = hedge_by_sentence.get(sentence)
        piece = replacement if replacement is not None else sentence.strip()
        # A line that ends inside quotes ("... here.'") splits into a trailing
        # fragment of pure punctuation. Keeping it produced visible wreckage
        # ("We'll be here. '.") once the terminal-punctuation fixup ran. The
        # same "has word content" test as split_sentences', and deliberately
        # the same spelling: str.isalnum() is Unicode-aware where
        # _ALNUM_PATTERN is ASCII-only, so writing it by hand here (as this
        # did) made two copies of one rule disagree on accented text.
        if not piece or not _ALNUM_PATTERN.search(piece):
            continue
        # Collapse only repeated *hedges* — a legitimately repeated sentence
        # ("No. No.") is the author's/model's cadence, not stutter.
        if out and replacement is not None and out[-1] == piece:
            continue
        out.append(piece)

    result = " ".join(out).strip()
    if not result:
        result = _HEDGES[flags[0].category]
    return ensure_terminal_punctuation(result)


def guidance_for(flags: Iterable[GuardFlag]) -> str:
    """Build the reviser's instruction block from the categories that tripped."""
    seen: List[str] = []
    for flag in flags:
        if flag.category not in seen:
            seen.append(flag.category)
    return "\n".join(_GUIDANCE[category] for category in seen)
