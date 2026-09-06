"""
ConversationalNPCMixin — LLM-driven conversational dialogue mixin for speaking NPCs.

Mixed into NPC classes (e.g. class Mara(ConversationalNPCMixin, Friend)).
Provides multi-turn conversational dialogue with dialogue history persistence,
loquacity draining, QC pipeline (slang/anachronism filtering, proper noun validation),
and graceful fallback to deterministic dialogue pools when LLM is unavailable.

Attributes expected on the host class (set before or during __init__):
    self.name                str
    self.charisma            int
    self.keywords            list[str] (must already include "talk")
    self.talk                method -- read through `hasattr` in `chat()`, so
                             strictly it is optional, but all eleven real hosts
                             have it and the fallback is a "nothing to say" line

Optional host attributes, read with a default. Each is absent on at least one
of the eleven real hosts, so the default is the live path there -- see
``_HOST_SPECIFIC`` in tests/test_npc_chat_merchant_and_loquacity.py, which
derives this list from the source and makes every entry carry a reason:
    self.wisdom              int, and only NomadBoy and NomadGirl set it (both
                             to 8). This line used to sit above with the
                             required attributes, claiming wisdom drove
                             loquacity recovery; nine of the eleven hosts do
                             not have it and the term is inert at every value
                             the game contains -- see
                             _LOQUACITY_RECOVERY_WISDOM_DIVISOR.
    self.level               int (allies only; merchants have no progression)
    self.growth_profile      dict (allies only)
    self.always_stock        list (merchants only)
    self.specialties         list (merchants only)

Optional setup (for story NPCs only):
    self._chat_config_path   str | None (path to character JSON config)

Instance attributes (set by _init_chat_attrs):
    self.loquacity_current   int (current conversation stamina)
    self.loquacity_max       int (max stamina for this NPC)
    self.loquacity_threshold int (minimum to start new conversation)
    self.loquacity_recovery  int (per-beat recovery when not in conversation)
    self._chat_history       list[dict] (in-memory exchange log)
    self._chat_personality   dict | None (for generic nomads)
    self._chat_npc_key       str | None (persistence key)
"""

import json
import logging
import re
import time
import zlib
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    TypeGuard,
    TypeVar,
)

from . import _chat_guard
from ._llm import _load_llm_client_module
from src.narration import narrate

# Prompt-injection neutralisation, applied in BOTH directions of the chat.
#
# Player text is neutralised at ingress — before it is handed to the adapter
# *and* before it is written to the history that later prompts replay. Jean's
# line is not merely sent to the provider once: it goes into the persisted
# exchange history, which is replayed into the system prompt on every later
# turn and survives into the save file, so a single crafted line keeps working
# for the rest of the conversation, and a length cap alone (all this used to
# do) does nothing about it.
#
# Model text is neutralised at the end of QC and on every Jean option, because
# an accepted line is written straight back into prompts that are structured by
# newlines and tags (``revise_turn``'s options block, ``_format_history``'s
# speaker-labelled rows).
#
# Both rules live in src/text_safety.py, which ai/llm_client.py imports too.
# There were two implementations of the player half, and the adapter's — the
# one guarding the replayed history — was the weaker of the pair, so this
# module's extra rules protected the live turn and nothing else. That module is
# stdlib-only by design, so unlike the ai.llm_client constants below these
# imports need no fallback: they cannot fail on a box with no AI stack.
from src.text_safety import neutralise_model_text, neutralise_player_text

logger = logging.getLogger(__name__)

# For the pool helpers, which are shared between a pool of NPC lines (str) and
# a pool of Jean option sets (list of dicts).
_T = TypeVar("_T")

# Length caps, tone names and delta bounds belong to ai/llm_client.py — the
# lower layer that *generates* the values this module then filters. They were
# spelled independently in both places and had already drifted: llm_client
# truncated a Jean option at 200 characters while this module dropped it at
# 160, so every option between those lengths survived generation only to be
# silently eaten downstream.
#
# The import is guarded because ai/llm_client.py calls load_dotenv() at import
# time and pulls in the HTTP stack; the game engine must stay importable on a
# box with no AI dependencies configured. The fallback spells the same numbers
# so behaviour is identical either way, and llm_client stays the one place to
# change them.
try:  # pragma: no cover - trivially exercised by importing this module
    from ai.llm_client import (
        JEAN_TONES,
        LOQUACITY_DELTA_BOUNDS,
        LOQUACITY_DELTA_DEFAULT,
        MAX_FLAVOR_CHARS,
        MAX_JEAN_TEXT_CHARS,
        MAX_NPC_SENTENCES,
        MAX_NPC_TEXT_CHARS,
        MAX_OPTION_CHARS,
        MERCHANT_FORBIDDEN_TOPICS,
        MERCHANT_SUBSTITUTE_TOPICS,
        REPUTATION_DELTA_BOUNDS,
    )
except Exception as _constants_import_error:  # pragma: no cover - no AI stack
    # Bare ``Exception`` on purpose: the guard exists to keep the engine
    # importable, and a provider dependency can fail in ways that are not
    # ImportError. But a genuine error *inside* ai.llm_client degrades the chat
    # to hard-coded numbers and used to do it invisibly, so say so once, with
    # the exception type — the fallbacks below are only correct while they
    # agree with llm_client, which tests/test_npc_chat_turn_pipeline.py asserts
    # by reading both halves of this guard out of the source.
    logger.warning(
        "ai.llm_client constants unavailable (%s: %s); falling back to the "
        "literal copies in _chat_llm.",
        type(_constants_import_error).__name__,
        _constants_import_error,
    )
    JEAN_TONES = ("direct", "guarded", "open")
    MAX_NPC_TEXT_CHARS = 300
    MAX_FLAVOR_CHARS = 200
    MAX_OPTION_CHARS = 160
    MAX_JEAN_TEXT_CHARS = 500
    MAX_NPC_SENTENCES = 3
    REPUTATION_DELTA_BOUNDS = (-5, 5)
    LOQUACITY_DELTA_BOUNDS = (-40, 15)
    LOQUACITY_DELTA_DEFAULT = -8
    MERCHANT_FORBIDDEN_TOPICS = (
        "price, budget, inventory, stock, wares, buying, selling, "
        "discounts, or purchase promises"
    )
    MERCHANT_SUBSTITUTE_TOPICS = (
        "craft, fit, maintenance, provenance, or general lore"
    )

_AI_DIR = Path(__file__).resolve().parent.parent.parent / "ai"
_HUMAN_NPC_DIR = _AI_DIR / "npc" / "human"
_WORLD_FACTS_PATH = _HUMAN_NPC_DIR / "world_facts.json"

# Modern slang / anachronism blocklist (regex pattern). Note: "you know?" ends
# in a non-word char, so it must sit OUTSIDE the trailing \b group — inside it,
# \b after "?" only matches when a word character follows, which made that
# alternative dead at end-of-sentence (its only realistic position).
_SLANG_PATTERN = re.compile(
    r"\b(?:okay|hey there|yeah|yep|nope|awesome|literally|basically|"
    r"gonna|wanna|gotta|no worries|guns?|bombs?|bullets?|internet)\b"
    r"|\byou know\?"
    # "cool" is period-correct as a temperature/temperament word. Requiring
    # only a following comma or terminator — as this did — still ate the
    # commonest legitimate use, the sentence-final predicate adjective ("The
    # water was cool.", "Keep your head cool."), and a false positive here
    # costs a real retry. Both slang shapes are clause-final AND either stand
    # alone as their own clause ("Cool.", "It's fine, cool.") or predicate a
    # bare demonstrative ("That's cool.", "It is cool, I suppose."), neither of
    # which a temperature reading ever does: "The water was cool." has a
    # concrete subject, and "That's cool to me." is not clause-final.
    r"|(?:^|(?<=[.!?,;:—]))\s*\bcool\b(?=\s*(?:[,.!?]|$))"
    r"|\b(?:that|this|it)(?:['’]s|\s+is)\s+(?:\w+\s+)?cool\b(?=\s*(?:[,.!?]|$))",
    re.IGNORECASE,
)

# Jean-dialogue guard: reject if NPC text writes Jean's dialogue or narrates
# Jean speaking (past OR present tense — models narrate in both).
_JEAN_DIALOG_PATTERN = re.compile(
    r"\bjean\s+(said|says|replied|replies|asked|asks|answered|answers|"
    r"told|tells)\b|jean:\s*",
    re.IGNORECASE,
)

# Roleplay action asides: models frequently put stage directions inside the
# spoken line as *asterisk actions* ("*nods slowly* Fine.") even though
# npc_flavor is the designated home for physical beats. These are extracted
# and relocated, never shown verbatim.
#
# How wide a span an *asterisk aside* may cover. Unrelated to
# MAX_OPTION_CHARS despite sharing the number: this one bounds a stage
# direction inside one spoken line. Named so a later reader who spots the
# coincidence does not "unify" the two.
_MAX_ACTION_ASIDE_CHARS = 160

_BOLD_MD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
_ACTION_ASIDE_PATTERN = re.compile(
    r"\*([^*\n]{2," + str(_MAX_ACTION_ASIDE_CHARS) + r"})\*"
)

# Terminators and quote characters, owned by _chat_guard (see the rationale
# comment there). Aliased here so this module never hand-spells another
# variant — the class of bug that let a curly-quoted line have its first spoken
# word scrubbed as an invented proper noun while the straight-quoted form was
# fine. The aliases immediately below are the whole of what this module takes
# from _chat_guard's character sets. No count of them is given: the prose here
# used to say "four" and the matching prose in _chat_guard said "all four",
# and both were wrong — the third hand-kept count in this feature to rot — so
# the list, which the reader can already see, is left to speak for itself.
_TERMINATORS = _chat_guard.TERMINATORS
_CLOSING_QUOTES = _chat_guard.CLOSING_QUOTES
_SENTENCE_BOUNDARY_CHARS = _chat_guard.SENTENCE_BOUNDARY_CHARS

# Sentence splitting — _chat_guard owns the definition, the
# terminator-preserving rationale and the displaced-closing-quote repair.
_split_sentences = _chat_guard.split_sentences
_ensure_terminal_punctuation = _chat_guard.ensure_terminal_punctuation

# Capitalized token finder (for invented proper noun scan)
_CAP_TOKEN_PATTERN = re.compile(r"\b([A-Z][A-Za-z\-]{2,})\b")

# Words long enough to carry subject matter, pulled out of a character's
# authored knowledge_scope entries to seed the state guard's topic whitelist.
_TOPIC_WORD_PATTERN = re.compile(r"[a-z]{4,}")

# Common capitalized words that are NOT invented proper nouns. Sentence-initial
# words are skipped positionally; this set catches legitimate capitalized words
# that can appear mid-sentence (pronouns, connectives, setting/religious terms)
# so the invented-noun scrubber never mangles ordinary English.
_COMMON_CAP_WORDS = frozenset(
    w.lower()
    for w in (
        "The",
        "This",
        "That",
        "These",
        "Those",
        "There",
        "Then",
        "Here",
        "What",
        "When",
        "Where",
        "Why",
        "Who",
        "How",
        "But",
        "And",
        "Not",
        "Now",
        "Yes",
        "Well",
        "Come",
        "Look",
        "Listen",
        "Maybe",
        "Perhaps",
        "Nothing",
        "Something",
        "Someone",
        "Anyone",
        "Everyone",
        "Nobody",
        "He",
        "She",
        "His",
        "Her",
        "Him",
        "They",
        "Them",
        "Their",
        "You",
        "Your",
        "We",
        "Our",
        "Its",
        "God",
        "Lord",
        "Heaven",
        "Hell",
        "Father",
        "North",
        "South",
        "East",
        "West",
        "River",
        "Sun",
        "Moon",
        "Storm",
    )
)

# Minimum length for NPC dialogue text to be treated as real content rather
# than empty/near-empty noise. Several NPCs are authored with terse,
# economical voices (Mara: "Says half of what she means") and can
# legitimately reply with "No." or "I see." — a flat 10-character floor
# silently rejected those in-character replies on every single turn, forcing
# unnecessary retries/fallback for exactly the NPCs whose voice most called
# for short answers. This only needs to catch genuinely empty/near-empty
# noise; _has_real_npc_text's alphanumeric check (below) does the actual
# garbage filtering (e.g. "..." or "-").
_MIN_NPC_TEXT_LEN = 2

# "Has word content, not just punctuation" — owned by _chat_guard, which needs
# the identical test to spot punctuation debris while splitting sentences.
# There were three spellings of this rule across the two modules, one of them
# `any(ch.isalnum())`, which is Unicode-aware where the compiled patterns are
# ASCII-only: they disagreed on accented text.
_HAS_ALNUM_PATTERN = _chat_guard.ALNUM_PATTERN


def _has_real_npc_text(text: str) -> bool:
    """True if text is long enough and has actual word content (not just
    punctuation/whitespace noise like "..." or "-")."""
    return len(text) >= _MIN_NPC_TEXT_LEN and bool(_HAS_ALNUM_PATTERN.search(text))


# Span-repair patterns, compiled once at import rather than on every call. The
# text pipeline runs these on every NPC line and every flavor beat, and the
# module's own convention (see _OPTION_META_PATTERN above) is module-level
# compilation.
_WS_RUN_PATTERN = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT_PATTERN = re.compile(r"\s+([,.!?;:])")
_REPEATED_SEPARATOR_PATTERN = re.compile(r"([,;:])(?:\s*\1)+")
_SEPARATOR_BEFORE_TERMINATOR_PATTERN = re.compile(r"[,;:]+(?=[.!?])")
# A run of two or more terminators, which a removed clause-sized span leaves
# glued together ("...at dawn. Okay. Mind the current." -> "...at dawn.. Mind
# the current."). Collapsed by :func:`_collapse_terminator_run`, which spares a
# deliberate ellipsis.
_TERMINATOR_RUN_PATTERN = re.compile(r"[.!?]{2,}")
_LEADING_SEPARATOR_PATTERN = re.compile(r"^[\s,;:]+")
_LEADING_TERMINATOR_PATTERN = re.compile(r"^[.!?]+[\s,;:]*")
_TRAILING_SEPARATOR_PATTERN = re.compile(r"[\s,;:]+$")
_SENTENCE_START_PATTERN = re.compile(r"(^|(?<!\.\.)[.!?]\s+)([a-z])")
# An intentional leading ellipsis plus whatever whitespace followed it. The
# sentence splitter cannot capture either (it needs a non-terminator first, and
# it strips each fragment), so both are re-attached by hand.
_LEADING_ELLIPSIS_PATTERN = re.compile(r"^\.{3,}\s*")


def _collapse_terminator_run(match: "re.Match") -> str:
    """Reduce a run of sentence terminators to the one that ends the sentence.

    A slang or prohibited span removed mid-line takes its own terminator with
    it and leaves the previous sentence's behind, one space away; the space
    fixup then glues the two together and ``_qc_normalise_sentences`` passes
    the result through untouched, so the player reads "at dawn.. Mind the
    current."

    A pure run of dots three or longer is the model's own ellipsis and is kept
    (normalised to three, since the same repair can extend one); ".." never is.
    A mixed run keeps its first character, which is the terminator the
    surviving sentence actually ended on.
    """
    run = match.group(0)
    if run.count(".") == len(run):
        return "..." if len(run) > 2 else "."
    return run[0]


# One provider call's network timeout, used as the size of a stage the gates
# below decide whether to open. The adapter owns the real number
# (``NpcChatLLMAdapter._round_timeout`` reads ``NPC_CHAT_LLM_TIMEOUT``); this
# is the fallback for a test double or an adapter that predates it, and is
# deliberately not another env read — importing ai.llm_client to ask is exactly
# the dependency this module refuses to take at import time.
_DEFAULT_ROUND_TIMEOUT_SECONDS = 6.0


def _coerce_int(value: Any, default: int) -> int:
    """Read an adapter-supplied number defensively.

    Both signed deltas a turn carries (``reputation_delta``,
    ``loquacity_delta``) come off an untrusted adapter and are clamped before
    use, but the clamp itself is arithmetic: a bare ``int()`` on a string or
    None raises one frame later, inside the caller's ``try`` for *provider*
    failures, and loses the whole turn. Only ``reputation_delta`` had this
    guard; ``loquacity_delta`` called ``int()`` bare, two methods apart.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _round_timeout(adapter: Any) -> float:
    """How long one provider call may take, as the deadline gates see it."""
    probe = getattr(adapter, "_round_timeout", None)
    if callable(probe):
        try:
            return float(probe())
        except Exception:  # a test double's attribute, not a contract
            pass
    return _DEFAULT_ROUND_TIMEOUT_SECONDS


def _no_stage_budget(deadline: Optional[float], adapter: Any = None) -> bool:
    """True when the turn cannot afford to open another provider stage.

    Gating on "has the deadline passed?" alone let a stage start with
    milliseconds left and then run a *whole* provider chain — the budget was
    checked but never actually enforced. A stage is only opened when a full
    round timeout still fits inside it, so overrunning costs at most the tail
    of one call rather than the length of a chain walk.

    ``None`` means no budget was set — direct unit-test calls and any caller
    that has not opted in still behave exactly as before.
    """
    if deadline is None:
        return False
    return deadline - time.monotonic() <= _round_timeout(adapter)


# The one round timeout already reported as too wide for the fixed budget.
# Remembered so the warning names a misconfiguration once rather than on every
# turn of every conversation for the life of the process.
_warned_round_timeout: Optional[float] = None


# The provider stages one player message may open, in the order they run:
#
#   1. the NPC turn                  (_run_npc_turn attempt 1)
#   2. the QC retry                  (_run_npc_turn attempt 2)
#   3. the state-guard revision      (_guard_turn — the call _chat_guard
#                                     exists to make)
#   4. the Jean-options call         (_resolve_jean_options, on a legacy
#                                     two-call adapter only)
#
# Named so :func:`_turn_deadline` funds what ``_CHAT_DEADLINE_SECONDS``
# enumerates. The two had drifted: the budget widened to *two* round timeouts
# while the constant's comment listed these four, and since
# :func:`_no_stage_budget` refuses to open a stage unless a whole round timeout
# still fits, a 12s budget stopped admitting stages six seconds in. At the
# 2-4s per call the adapter documents as healthy, that meant any turn which
# spent its QC retry had already lost the guard revision and hedged
# deterministically instead — the failure mode the guard exists to avoid.
_MAX_TURN_STAGES = 4


def _turn_deadline(adapter: Any) -> float:
    """The instant after which this turn may open no further provider stage.

    ``_CHAT_DEADLINE_SECONDS`` is a fixed number, but the per-call timeout
    :func:`_no_stage_budget` measures the remaining budget against is
    ``NPC_CHAT_LLM_TIMEOUT`` — operator-tunable, with no upper bound. So the
    budget scales with the timeout it is compared against: one round timeout
    per stage in :data:`_MAX_TURN_STAGES`, with the constant as the floor.

    That funds every stage at the latencies the feature targets (a healthy call
    returns in 2-4s against a 6s ceiling). If *every* call instead runs to the
    full timeout, the last stage is refused — correctly: there is no longer
    room for it to finish inside the budget, and refusing costs a hedged line
    where admitting it would cost the player another whole round timeout of
    spinner.

    A per-call timeout wider than the 6s the budget is sized around is worth
    saying out loud once, because it multiplies the whole turn.
    """
    round_timeout = _round_timeout(adapter)
    budget = _MAX_TURN_STAGES * round_timeout
    if round_timeout > _DEFAULT_ROUND_TIMEOUT_SECONDS:
        _warn_round_timeout_over_budget(round_timeout, budget)
    return time.monotonic() + max(_CHAT_DEADLINE_SECONDS, budget)


def _warn_round_timeout_over_budget(round_timeout: float, widened: float) -> None:
    """Report a per-call timeout wider than the budget is sized for, once."""
    global _warned_round_timeout
    if _warned_round_timeout == round_timeout:
        return
    _warned_round_timeout = round_timeout
    logger.warning(
        "NPC chat per-call timeout is %.1fs, wider than the %.1fs the turn "
        "budget is sized around, so one conversation round may now run for up "
        "to %.1fs (%d provider stages). Lower NPC_CHAT_LLM_TIMEOUT to keep a "
        "round short.",
        round_timeout,
        _DEFAULT_ROUND_TIMEOUT_SECONDS,
        widened,
        _MAX_TURN_STAGES,
    )


class QcResult(NamedTuple):
    """The verdict of one pass of the NPC-text QC pipeline.

    ``text`` is None exactly when ``reason`` is set; the reason is fed back to
    the model as retry guidance. ``aside`` is any stage direction pulled out of
    the spoken line, for relocation into npc_flavor.
    """

    text: Optional[str]
    reason: Optional[str]
    aside: str


class FilterResult(NamedTuple):
    """What one content-filter stage did to the working text.

    ``reason`` is set only when the stage rejected the line (strict mode, or a
    rewrite that left nothing usable). ``rewrote`` drives the capitalization
    repair the driver runs at the end.
    """

    text: str
    reason: Optional[str]
    rewrote: bool


class Turn(NamedTuple):
    """One assembled conversational turn — what the player actually sees.

    Named rather than a positional 3-tuple so the state guard's input and its
    output read the same at every call site; still unpacks positionally for
    callers that only want the three pieces.
    """

    npc_text: str
    npc_flavor: str = ""
    jean_options: Sequence[Dict[str, str]] = ()


class GuardedTurn(NamedTuple):
    """A :class:`Turn` that has been through the state guard.

    ``tripped`` says whether the tripwire fired at all, which the caller needs
    for more than logging: the model's structured ``reputation_delta`` is one
    of the two fields of a chat response that really does reach the engine
    (see ``_chat_guard``'s module docstring), and a turn the model had to be
    talked out of does not also get to move the player's standing.
    """

    turn: Turn
    tripped: bool = False


class LoquacityOutcome(NamedTuple):
    """What one round's loquacity change asked for, and what it actually did.

    ``requested`` is the bounded delta the model asked for -- the number that
    gets logged and persisted. ``applied`` is what the clamp against
    ``loquacity_max`` really moved. They differ exactly when the NPC was
    already at its ceiling, which is the state every shipped merchant OPENS
    in: ``scale_loquacity(80)`` is 12, so ``current == max`` on turn one.

    Both are carried because the retraction on a tripped turn must undo
    ``applied``, while the log and the save want ``requested``. That
    distinction used to live in an undeclared instance attribute written by
    one method and read by another through ``getattr(..., default)``, with the
    reader's parameter named ``loquacity_delta`` -- the same name the applier
    uses for a DIFFERENT number. The test that covered the pair had already
    absorbed the confusion and called the requested value ``applied``.

    Passing the record instead of an int is what makes the wrong number
    unwritable rather than merely documented.
    """

    requested: int
    applied: int
    ended: bool


class TurnOutcome(NamedTuple):
    """One raw turn as it came back from the adapter, coerced and clamped.

    The mixin used to carry a turn in two live representations at once — this
    normalized dict, mutated in place, *and* a :class:`Turn` assembled beside
    it — so "a turn" meant different things two lines apart and adding one
    clamped field cost ten edit sites. This is the model-facing half (what the
    adapter said, including the fields the player never sees); :class:`Turn` is
    the player-facing half.

    ``loquacity_delta`` is None when the adapter supplied none, which is what
    selects the quality-based drain. ``raw_options`` is None on the legacy
    two-call adapter, which produces options through a separate request.
    """

    npc_text: str
    npc_flavor: str = ""
    conversation_quality: str = "neutral"
    reputation_delta: int = 0
    loquacity_delta: Optional[int] = None
    raw_options: Optional[Any] = None


class CombinedChatAdapter(Protocol):
    """The adapter shape this mixin prefers: one call per turn.

    The contract was previously implicit in ``hasattr`` probes scattered across
    five call sites, with ``hasattr(adapter, "generate_turn")`` re-derived in
    two of them under different handling of a ``None`` adapter. Declaring it
    puts the members a reader has to satisfy in one place. ``enabled``,
    ``revise_turn`` and ``generate_personality`` are shared with the legacy
    two-call shape (which supplies ``generate_npc_turn`` and
    ``generate_jean_options`` in place of ``generate_turn``, at the cost of a
    second round trip); ``generate_turn`` is what tells the two apart.

    Structural, not nominal: ``ai.llm_client.NpcChatLLMAdapter`` does not
    import this module, and test doubles supply whichever subset they need.
    """

    enabled: bool

    def generate_turn(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        is_opening: bool,
        jean_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        ...

    def revise_turn(
        self,
        system_prompt: str,
        npc_text: str,
        jean_options: List[Dict[str, str]],
        guidance: str,
    ) -> Optional[Dict[str, Any]]:
        ...

    def generate_personality(self, npc_class_display: str) -> Optional[Dict[str, Any]]:
        ...


def _is_combined_adapter(adapter: Any) -> TypeGuard[CombinedChatAdapter]:
    """True when ``adapter`` produces the NPC line and Jean's options together.

    One spelling for a probe that was written twice with different null
    handling: the legacy two-call adapter (``generate_npc_turn`` plus
    ``generate_jean_options``) costs a second round trip, so "is this the
    combined shape" decides whether the options path may spend one.
    """
    return adapter is not None and hasattr(adapter, "generate_turn")


# QC pipeline count/similarity thresholds owned by this module. The *length*
# caps and the tone names live in ai/llm_client.py (imported above) because the
# generator has to obey the same numbers the filter enforces.
_JEAN_OPTION_COUNT = len(JEAN_TONES)  # Jean is always offered exactly three
_OPTION_SIMILARITY_MAX = 0.6  # Jaccard ceiling before two options count as duplicates
_NPC_REPEAT_SIMILARITY = 0.7  # Jaccard floor before an NPC line counts as a repeat

# Upper bound on how many invented proper nouns are named back to the model in
# the retry guidance. The list is model-chosen text going into the system
# prompt, so it is bounded like any other untrusted span.
_MAX_NAMED_INVENTED_NOUNS = 8

# Upper bound on how many raw options are inspected. Options past the first
# three are now validated too (a malformed option at index 0 used to make three
# good ones at 1-3 unreachable), but the model's list is untrusted input and
# must not be able to make QC do unbounded work.
_MAX_OPTION_CANDIDATES = 12

# Floor on a Jean option's length. Below this it is not a reply — models emit
# "x", "...", a bare tone name — and there is nothing to salvage.
_MIN_OPTION_CHARS = 5

# A truncation boundary is only worth taking in the second half of the window.
# The backwards scan used to accept the LAST terminator at or below the cap
# wherever it fell, so a 461-character reply opening "Aye. " with no further
# punctuation was amputated to "Aye." — the discard QC policy 2 exists to
# forbid.
_MIN_TRUNCATION_KEEP_RATIO = 0.5

# Bounds how many provider STAGES one player message may open — not, despite
# the name, how long it may take. A turn composes several LLM stages (the four
# enumerated on :data:`_MAX_TURN_STAGES`), and each stage walks the whole
# provider fallback chain, so a single stage can cost
# `chain x models x 2 x round timeout`. Nothing bounded the *sum* at all, and
# the worst case ran well over a minute on a synchronous Flask worker with the
# player watching a spinner.
#
# A stage is opened only while a full round timeout still fits in the remaining
# budget (see :func:`_no_stage_budget`), so the real ceiling is this value plus
# one chain walk — the tail of the last stage to start. Once the budget is
# spent the turn drops to the deterministic fallbacks that already exist
# (_get_fallback_npc_line, _chat_guard.hedge_npc_text, and the rewrite-mode QC
# salvage in _run_npc_turn) rather than opening another stage.
#
# This is the FLOOR of the budget, not the whole rule: the per-call timeout it
# is measured against is operator-tunable and unbounded, so
# :func:`_turn_deadline` sizes the budget at one round timeout per stage in
# :data:`_MAX_TURN_STAGES` and takes whichever is larger.
_CHAT_DEADLINE_SECONDS = 12.0

# Meta-speech markers ("[Option 2]", "As Jean, I...") that mean the model
# broke character while generating one of Jean's dialogue options. Hoisted to
# module level (compiled once) rather than re-built on every option checked
# in _qc_jean_options.
_OPTION_META_PATTERN = re.compile(
    r"\[Option|\bAs Jean\b|I don.t know what to say", re.IGNORECASE
)

# Jean's own name inside one of *Jean's own* dialogue options. The three options
# are lines Jean himself says, so "Jean has walked a long road" or "Ask her about
# Jean's armor fit" hands the player a reply in which he talks about himself in
# the third person — or worse, addresses himself. Models produce these constantly
# because the prompt names Jean on every line of context.
#
# The word boundary is enough to catch the possessive: ``\bjean\b`` matches the
# "Jean" of "Jean's".
_JEAN_NAME_PATTERN = re.compile(r"\bjean\b", re.IGNORECASE)

# The single licensed use of the name in Jean's mouth: introducing himself.
# Deliberately narrow — an explicit self-naming verb phrase, not any first-person
# sentence that happens to contain the name — because "What would Jean know about
# the western road?" is exactly the failure this rule exists to remove, and it is
# both first person in intent and self-referential.
_JEAN_SELF_INTRO_PATTERN = re.compile(
    r"^\s*(?:well\s*,\s*)?(?:i['\u2019]?m|i\s+am|my\s+name\s+is|"
    r"my\s+name['\u2019]?s|they\s+call\s+me|call\s+me)\s+jean"
    r"(?!['\u2019]s)\b",
    re.IGNORECASE,
)

# Shop business, for the merchant rule below. Nothing said in a chat can move an
# item or a coin (the shop UI owns trade), so a question about price or stock is
# a dead end for the player and an invitation for the model to invent numbers.
#
# Money and stock vocabulary. Context detection below still requires a question
# or question-shaped sentence, so ordinary lore such as "Is it worth the risk?"
# remains eligible unless the merchant is clearly being asked to sell, price, or
# inventory something.
#
# The noun list is _chat_guard.MERCHANDISE — the same vocabulary that module's
# possession tripwire reads. Spelled here independently it enumerated armour
# nouns and no weapon nouns, so at Kaelen's arms stall (Shortsword, Spear,
# Dagger) the canonical "How much for the sword?" was not commerce at all.
#
# This constant is a FLOOR, not the whole vocabulary, and the distinction is
# the fix for a defect that outlived being "fixed" once. Sharing one hand-
# written noun list closed the reported instance (weapons) and left the class
# wide open: the list covers arms and armour, and the very same change made
# JamboHealsU conversational, whose entire stock is Restorative, Draught and
# Antidote. Not one of those words was in it. A public constant, a comment
# claiming "the ONE spelling", and a green test named
# TestMerchantVocabularyHasOneSpelling then told every reader the rule was
# unified while an apothecary sold potions no classifier could see — which is
# worse than the duplication it replaced, because the duplication was visible.
#
# So the per-host half is DERIVED from what the merchant actually sells, at
# call time off ``self`` (see ``_host_merchandise_pattern``). No import cycle:
# the roster is an attribute, not an import. A merchant added to the game is
# covered the day it is added, and ``tests/test_npc_chat_merchant_and_loquacity``
# asserts exactly that against the live roster rather than a copied noun list.
_MERCHANT_ITEM_PATTERN = re.compile(
    r"\b(?:" + _chat_guard.MERCHANDISE + r")\b",
    re.IGNORECASE,
)

# ``stock`` and ``for sale`` appear here AND in
# _MERCHANT_ITEM_REQUEST_PATTERN below, deliberately and at two different
# strengths, so do not "unify" them. This pattern is an unconditional
# verdict -- step 2 of :meth:`_is_merchant_commerce_question` returns True
# on it outright -- while the item-request pattern is subject to the
# lore-lead veto in :meth:`_is_stock_request`. "Where do you keep the good
# steel?" has to reach that veto and survive it; "What is for sale?" must
# not. One shared fragment would have to pick one of those two behaviours
# for both, and either choice is a bug that has already shipped once.
_MERCHANT_EXPLICIT_PATTERN = re.compile(
    # "shop" is NOT here. "How long has this shop been in your family?" is
    # provenance — an advertised substitute — and "shop" is absent from
    # MERCHANT_FORBIDDEN_TOPICS too, so suppressing it spent a revision round
    # trip on a sentence the prompt never told the model to avoid.
    r"\b(?:inventory|stock(?:s|ed|ing)?|wares|merchandise|for\s+sale|"
    r"budget|discount\w*|bargain\w*|cheaper)\b",
    re.IGNORECASE,
)
# "What is it worth?" -- the bare valuation question, spelled once and
# interpolated into the two patterns that need it (the anchored
# whole-sentence form below and the item-less form further down). It was
# written out twice in two different spellings, one admitting "which" and
# the other not, which is how a filter comes to answer the same question
# two ways depending on which branch reached it.
# "which is it worth" is not English; the alternative only ever fired on the
# "what" form, and a test had been written asserting a non-sentence is commerce.
_MERCHANT_WORTH_QUESTION = r"what\s+(?:is|are)\s+it\s+worth"

# Deliberately NOT ``^...$`` anchored any more. It was, and so "What have you
# got?" was commerce while "What have you got today?" was not -- one word, and
# the corpus happened to contain only the first.
_MERCHANT_STOCK_REQUEST_PATTERN = re.compile(
    # Deliberately NOT whole-string anchored any more. It was, so
    # "What have you got?" was commerce and "What have you got today?" was
    # not — one word, and the corpus happened to hold only the first.
    r"\bwhat\s+have\s+you\s+got\b|"
    r"\bwhat\s+can\s+you\s+offer\b|"
    r"\bwhat\s+do\s+you\s+(?:carry|have|sell|stock)\b|"
    r"\bis\s+anything\s+available\b|"
    r"\bare\s+any(?:\s+.+)?\s+available\b|"
    r"\bwould\s+you\s+trade\b|"
    + _MERCHANT_WORTH_QUESTION,
    re.IGNORECASE,
)
# Verbs a stock request is built from. They only mean "is this on your counter"
# inside a second-person offer frame: bare, they fired on the very topics the
# TRADE prompt block tells the model to substitute for commerce — provenance
# ("where did you GET that leather") and maintenance ("how do you KEEP the
# chain from rusting") — so the classifier suppressed the substitutes and let
# the price question through.
# Straight or typographic. Models emit U+2019 about half the time, and every
# row of the committed corpus used U+0027 -- which is exactly what hid
# "I\u2019ll take the shortsword." matching nothing at any counter while its
# straight-quoted twin passed green. ``_chat_guard`` has carried its own copy of
# this for the same reason -- though note theirs is OPTIONAL (`(?:['’])?`)
# and this one is REQUIRED, so they are not interchangeable and unifying them
# would silently change what `_OFFER` matches.
#
# `_SLANG_PATTERN` still spells the class inline: it is not part of the merchant
# family and reads better self-contained there. Every merchant pattern uses this
# constant.
_APO = r"['\u2019]"

# The auxiliaries an offer question is framed with, plus the fused
# contraction. Named because ``_MERCHANT_DIRECT_TRADE_PATTERN`` carries TWO
# frames of the identical speech act -- "What <aux> you give me for this?"
# (Jean selling) and "What <aux> you want/take/charge for that?" (Jean buying)
# -- and they were written a round apart with different auxiliary lists: the
# selling frame took four, the buying frame took ``would`` alone. So "What do
# you want for the sword?" and "What will you take for the shield?" -- the
# plainest price questions a player types at a counter -- were not commerce,
# while their `give me` twins were. One fragment, interpolated into both, is
# what stops the two halves of one speech act drifting again;
# ``TestTheOfferFrameTakesEveryAuxiliary`` derives its probes from this string
# rather than restating it.
#
# The contraction is fused to ``what`` ("What'll you take for it?"), not a
# separate word, which is why this fragment starts at the whitespace rather
# than after it.
_MERCHANT_OFFER_AUX = (
    r"(?:\s+(?:will|would|can|could|do)|" + _APO + r"ll)\s+you\s+"
)

#: Regular plural suffix for a noun spelled in the singular. ``e?`` so the
#: sibilant stems ("guess", "pass") pluralise correctly too.
_MERCHANT_PLURAL = r"(?:e?s)?"

#: Exchanges kept in the save.
#:
#: The prompts read at most the last 8 (``_format_history``) and the last 4
#: (the jean-options builder), so this is the larger of those plus room --
#: NOT, as this said when the constant was introduced, "two turns of context
#: is what the prompt uses". Nobody checked that number and it was wrong by
#: four times; ``tests/test_npc_chat_merchant_and_loquacity.py`` now derives
#: the floor from ``ai/llm_client.py`` so the next person cannot be wrong
#: about it quietly. The margin above the floor is transcript history, which
#: the player can read back even though no prompt sees it.
_MAX_PERSISTED_EXCHANGES = 20

_MERCHANT_STOCK_VERB = r"have|carry|keep|stock|offer|sell|got"
_MERCHANT_ITEM_REQUEST_PATTERN = re.compile(
    # "do you have", "have you got any", "would you carry a lighter mail"
    r"\b(?:do|does|did|have|has|would|will|can|could|are)\s+you\b"
    r"(?:\s+\w+){0,3}?\s+\b(?:" + _MERCHANT_STOCK_VERB + r")\b|"
    # "you keep any", "you sell some" — an offer frame without the auxiliary
    r"\byou\s+(?:" + _MERCHANT_STOCK_VERB + r")\s+(?:any|anything|some)\b|"
    r"\b(?:available|in\s+stock|for\s+sale|on\s+offer)\b",
    re.IGNORECASE,
)

# The substitute-topic list lives in ``ai.llm_client.MERCHANT_SUBSTITUTE_TOPICS``
# and arrives through the guarded import above, because a third copy of it sits
# in that module's ``_MERCHANT_OPTION_RULE`` and the two had already drifted.
# The prompt half (:meth:`_build_trade_block`) and the deterministic half (the
# classifier below) have to agree on it: a sentence about one of these topics
# must survive QC, or the model is punished for obeying the instruction it was
# just given.

# Interrogatives that make a stock verb a craft or provenance question instead.
# "How do you keep the chain from rusting?" is maintenance; "Do you keep
# spears?" is inventory. Price questions are matched by
# _MERCHANT_PRICE_PATTERN, which runs separately, so excluding "how" here does
# not let "How much for the sword?" through — and "how many"/"how much" are
# excused anyway, because "How many spears do you have?" really is a stock
# request.
# A manner, place, time or person interrogative ANYWHERE in the sentence, not
# only at its start. The ``^`` anchor this used to carry is what let
# "Do you keep the leather oiled?" be classified as a stock request while
# "How do you keep the leather oiled?" was correctly allowed — the same
# maintenance question, one word apart, on opposite sides of the rule. Both are
# topics ``_build_trade_block`` asks the model to raise.
#
# ``how much``/``how many`` are excused: they open a price or a quantity
# question, not a manner one. The veto applies ONLY to the ambiguous stock
# frame (see :meth:`_is_stock_request`) — a price question stays commerce
# however it is worded, which is why "How much for the sword?" is unaffected.
_MERCHANT_LORE_LEAD_PATTERN = re.compile(
    r"\b(?:how|where|when|who|whom|whose|why)\b(?!\s+(?:many|much)\b)",
    re.IGNORECASE,
)

# What turns the stock frame into a question ABOUT the goods rather than FOR
# them. A stock request ends at its object; a craft, maintenance or provenance
# question predicates something OF the object and keeps going.
#
#   "Do you have any spears?"                 object, then done   -> stock
#   "Do you keep the leather oiled?"          trailing participle -> lore
#   "Do you carry the same harness your       trailing clause     -> lore
#    father did?"
#   "Do you have a trick for keeping mail     "for <gerund>"      -> lore
#    dry?"
_MERCHANT_TRAILING_PREDICATION = re.compile(
    r"\b(?:for|from|against)\s+\w+ing\b"
    # A trailing participle, but NOT when it qualifies an explicit goods
    # reference: "Do you sell anything enchanted?" is a stock request whose
    # object happens to carry an adjective, and the bare `\w+ed$` form vetoed
    # it. The negative lookbehind keeps "Do you keep the leather oiled?".
    r"|(?<!\bany)(?<!\banything)\s\w+ed\s*[?.!]*\s*$"
    # Third-person possessors only. "your best leather" addressed to the
    # merchant is his stock, not somebody else's history, and vetoing it lost
    # "Do you have any of your best leather?".
    r"|\b(?:his|her|their)\s+\w+\s+\w+"
    r"|\ba\s+(?:trick|knack|way|method|secret)\b"
    r"|\bsame\b",
    re.IGNORECASE,
)

# Words that stand in for the goods when no noun is named. This is the ONE
# place a noun list belongs — as a disambiguator inside an ambiguous frame,
# never as a gate on a price question. "Do you have family in the valley?" and
# "Do you have any spears?" are the same frame, and only the object separates
# them.
# A quantifier with a noun after it IS a goods reference, whatever the noun.
# This is the class fix. The ambiguous frame used to return False unless a
# finite vocabulary matched, so "Do you have any longswords?" failed at the
# weaponsmith -- the floor's `\bswords?\b` cannot match inside "longsword" and
# no per-host list contained it. Four rounds widened that list; this stops
# consulting it for the one thing a quantifier already settles.
#
# "Do you have family in the valley?" is unaffected: no quantifier, and the
# locative phrase is what a stock request does not have.
_MERCHANT_QUANTIFIED_GOODS = re.compile(
    r"\b(?:any|anything|some|something|a\s+few|several|more)"
    r"\s+(?:of\s+\w+\s+)?\w{3,}",
    re.IGNORECASE,
)

_MERCHANT_GENERIC_GOODS = re.compile(
    r"\banything\s+(?:else|cheaper|better)\b"
    r"|\banything\b\s*[?.!]*\s*$"
    r"|\bwhat\s+else\b"
    r"|\bbehind\s+the\s+counter\b"
    r"|\bin\s+stock\b",
    re.IGNORECASE,
)
# "does it cost", "would it cost" -- shared verbatim by the price pattern
# and the item-less pattern below, which is why it is a fragment rather
# than two character-identical literals forty lines apart.
_MERCHANT_IT_COST = r"\b(?:does|do|would|will|can)\s+it\s+cost\b"

# THE NOMINAL PRICE FRAME: "the price/cost/worth OF X". Kept separate from the
# transactional frames below because it is the one price wording that is
# routinely metaphorical -- "What is the price of freedom?", "What was the cost
# of the war?", "What is the worth of a vow?" are lore, and a merchant is
# exactly the character who says them. So this frame alone still consults the
# merchandise vocabulary: an abstract object means it is not a shop question.
#
# "How much for X?", by contrast, is a purchase offer whatever X is, and needs
# no noun. That asymmetry is the point -- the earlier design gated BOTH on a
# noun list and so missed every price question about a noun nobody had listed.
_MERCHANT_NOMINAL_PRICE_PATTERN = re.compile(
    r"\b(?:what(?:" + _APO + r"s)?\s+(?:is|are|was|were|does|do)?|"
    r"how\s+much\s+(?:does|do|would|will|can))\b"
    r".{0,80}\b(?:price|cost|worth|value)\b",
    re.IGNORECASE,
)

_MERCHANT_PRICE_PATTERN = re.compile(
    r"\bhow\s+much\s+for\b|"
    # "How much IS the sword?" -- the copula was missing while "how much does"
    # was present, so the commonest spelling of the commonest question at a
    # counter walked straight through, one word away from the row the
    # regression test asserts. That is what a probe list drawn from a bug
    # report buys you: the sentence in the report, and nothing beside it.
    # "How much is left of the garrison?" is a quantity question, not a price
    # one, and the price reading has no other marker to key on.
    r"\bhow\s+much\s+(?:is|are|was|were|would|will|could)\b"
    r"(?!\s+(?:left|further|farther|longer|remains?|remaining))|"
    + _MERCHANT_IT_COST
    + r"|"
    r"\b(?:does|do|would|will|can)\s+(?:it|the|this|that|these|those|any)\s+cost\s+(?:more|less|extra)\b",
    re.IGNORECASE,
)
# "How much gold should I bring?" — an actionable purchasing amount rather
# than the price of a named thing. Interpolated into the item-less pattern
# below rather than spelled twice: it used to be a compiled constant nothing
# read, plus a literal copy inside the classifier.
_MERCHANT_GOLD_ALLOWANCE = (
    r"\bhow\s+much\s+(?:gold|coin)\s+(?:should|would|will|can)\b"
)

# "Anything available?" — a stock request that never names a thing.
_MERCHANT_ANY_AVAILABLE_PATTERN = re.compile(
    r"\b(?:any|anything|something)\s+available\b",
    re.IGNORECASE,
)

# "less coin for the buckles" -- a haggling fragment shared by the item-less
# pattern below and by the transaction pattern's weak half. The transaction
# pattern needs its own copy of the *behaviour* because a lore frame
# short-circuits :meth:`_is_merchant_commerce_question` before the item-less
# pattern is ever consulted; it does not need its own copy of the string.
# "less coin for the buckles" — haggling, which is commerce. But a bare
# "gold for" is not: "Did they trade gold for salt on this road?" is regional
# history, one of the five substitute topics, and it matched. The comparative
# is what makes it an offer, so the comparative is required.
_MERCHANT_COIN_FOR = (
    r"\b(?:less|more|fewer|another|extra|additional)\s+(?:coin|gold|silver)\s+for\b"
    r"|\b(?:pay|paid|paying)\s+(?:you\s+)?\w*\s*(?:coin|gold|silver)\s+for\b"
)

# Trade with no item named. Deliberately narrow: without a noun to anchor it,
# only an explicit purchasing amount or an offer fragment counts. "gold in"/
# "coin in" is excluded — it reads as ordinary lore ("the gold in this region")
# far more often than as an offer, unlike "gold for" ("less coin for the
# buckles").
_MERCHANT_ITEMLESS_TRADE_PATTERN = re.compile(
    _MERCHANT_IT_COST
    + r"|\b"
    + _MERCHANT_WORTH_QUESTION
    + r"\b|"
    + _MERCHANT_GOLD_ALLOWANCE
    + r"|"
    + _MERCHANT_COIN_FOR
    + r"|"
    # "The road west was paid for in blood." is ambient prose in this game's
    # register. Require the money word.
    r"\b(?:pay|paid|paying)\s+(?:\w+\s+){0,2}(?:coin|gold|silver|pieces?)\b",
    re.IGNORECASE,
)

# Every alternative here names the transaction outright, so none needs a noun
# to confirm it. The second group is the shopkeeper's own opening line -- "What
# can I get for you?", "Are you buying or selling today?" -- which is commerce
# with no item in it anywhere, and which the item-anchored branches therefore
# could not see at all.
_MERCHANT_DIRECT_TRADE_PATTERN = re.compile(
    r"\b(?:looking|want|need)\s+to\s+(?:buy|sell)\b|"
    r"\b(?:your|the)\s+(?:selection|variety|assortment)\s+of\b|"
    r"\b(?:haggling?|haggle)\s+(?:over|for|about)\b|"
    r"\b(?:are|is)\s+you\b.{0,20}\b(?:buying|selling|trading)\b|"
    r"\bmake\s+a\s+purchase\b|"
    r"\bwhat\s+can\s+i\s+(?:get|do)\s+for\s+you\b|"
    # Jean offering his own goods: no item noun, no transaction verb, and
    # so invisible to every other branch. "What will you give me for
    # this?" is the plainest sell offer in the language.
    r"\bwhat" + _MERCHANT_OFFER_AUX + r"give\s+me\s+for\b|"
    r"\bin\s+the\s+market\s+for\b|"
    # Frames found by testing against sentences NOBODY had reported — the
    # held-out half of the corpus. Every previous version of this classifier
    # was tuned only on the rows from a bug report, which is why each fix was
    # correct on those rows and wrong one word away.
    r"\bwhat" + _MERCHANT_OFFER_AUX + r"(?:want|take|charge)\s+for\b|"
    r"\b(?:can|could|may)\s+i\s+(?:buy|purchase)\b|"
    r"\bwould\s+you\s+take\s+\w+\s+(?:gold|coin|silver|pieces?)\b|"
    # The same haggling offer with the money noun elided, which is how it is
    # usually said out loud: "Would you take twenty for the dagger?". Tight
    # rather than general, because this tier is consulted before every veto:
    # exactly ONE word between the verb and `for` (so "Would you take the west
    # road for the crossing?" cannot reach it) and a determiner after `for` (so
    # "Would you take him for a fool?" and "Would you take that for granted?"
    # cannot either).
    r"\b(?:would|will)\s+you\s+take\s+\w+\s+for\s+"
    r"(?:the|this|that|these|those|my|your|it)\b|"
    r"\bwould\s+you\s+(?:buy|sell|trade)\s+me\b|"
    r"\bany\s+chance\s+of\s+a\s+(?:discount|deal|bargain)\b|"
    # Declarative commerce. The classifier used to require a question mark or
    # an interrogative prefix, which made every one of these unreachable —
    # including the three alternations directly above, since a purchase is
    # more often announced than asked.
    # NOTE: `can I have X` and `I'll take X` are NOT here. Both are commerce
    # only when X is the goods -- "Can I have a word?", "May I have your name?",
    # "Could I have a look at that harness?" (a fit question, one of the five
    # substitutes) and "I'll take the risk." are not purchases. They are
    # handled in the item-anchored tier, where the object is the evidence.
    # This is the same distinction the nominal price frame draws: a frame whose
    # meaning turns on its object cannot be self-sufficient.
    r"\b(?:yours|mine)\s+for\s+\w+\s+(?:gold|coin|silver|pieces?)\b",
    re.IGNORECASE,
)
# A transaction word beside an item noun. The first alternation names the
# transaction outright and needs no frame; the rest do.
#
# ``trade``, ``coin`` and ``gold`` used to sit in that first list, and bare
# they are not transactions at all -- they are provenance and craft, which
# is to say they are three of the five topics ``_build_trade_block`` tells
# the model to raise INSTEAD of commerce. "Did you trade for that mail?",
# "Do the nomads trade for their gear upriver?" and "Did you learn the
# leather trade here?" were all suppressed, every one of them exactly what
# the prompt had just asked for. So the weak words are admitted only inside
# a second-person offer frame ("WOULD YOU TRADE me that mail") or a
# haggling frame ("less COIN FOR the buckles"), which is what separates an
# offer from a past-tense question about where a thing came from.
#
# Dropping them outright was the other candidate and is wrong: "Would you
# trade me that mail?" is genuine commerce and nothing else in the
# classifier catches it. Numeric price quotes do not depend on this pattern
# either way -- ``_chat_guard``'s ``coin`` state-claim tripwire is the net
# under those.
# Commerce ONLY when the object is the goods, which is why these are not in
# the self-sufficient tier. "Can I have a word?", "May I have your name?",
# "Could I have a look at that harness?" and "I'll take the risk." share these
# frames exactly and are not purchases -- and the third is a fit question, one
# of the five substitutes the TRADE block asks the model to raise.
_MERCHANT_OBJECT_GATED_TRADE_PATTERN = re.compile(
    r"\b(?:can|could|may)\s+i\s+have\b"
    r"|\b(?:i" + _APO + r"?ll|i\s+will)\s+take\b",
    re.IGNORECASE,
)

# The objects that make "I'll take X" / "Can I have X" NOT a purchase.
#
# Note which half is enumerated. "What could a merchant sell" is an OPEN set
# and listing it has failed four times. "What you can idiomatically take or
# have that is not goods" is CLOSED — a word, a look, a moment, a risk, a road.
# Enumerating the closed half is the only kind of list that stays right, and it
# is the same asymmetry the nominal price frame already uses.
# Every noun below is spelled in the singular and suffixed with
# :data:`_MERCHANT_PLURAL`. Without it the list was half a veto: "I'll take my
# chances." -- a stock idiom, and the plural is the ONLY form anybody says it
# in -- classified as a purchase, while its singular twin "I'll take the risk."
# sat in the lore corpus passing green two lines away. A closed set is only
# closed if it is closed under inflection, and this one is checked that way by
# ``TestTheNonGoodsVetoIsClosedUnderInflection``, which derives the nouns from
# this pattern rather than from a list beside it.
_MERCHANT_NON_GOODS_OBJECT = re.compile(
    r"\b(?:word|look|moment|minute|guess|turn|seat|rest|breath)" + _MERCHANT_PLURAL
    + r"\b"
    r"|\b(?:risk|blame|lead|chance|credit|hint|point)" + _MERCHANT_PLURAL + r"\b"
    r"|\b(?:your|his|her|their|my)\s+(?:name|word|leave|meaning|advice)"
    + _MERCHANT_PLURAL + r"\b"
    r"|\b(?:road|path|trail|route|pass|way)" + _MERCHANT_PLURAL + r"\b"
    r"|\bname\s+for\b"
    r"|\bas\s+a\b"
    r"|\bat\s+the\s+(?:siege|war|battle|crossing)" + _MERCHANT_PLURAL + r"\b",
    re.IGNORECASE,
)

# History, ritual and biography vocabulary. The second veto on the ambiguous
# stock frame (see :meth:`_is_stock_request`): "Do you have any memories of
# the old siege?" wears the stock frame around a war story.
#
# Module level, like every sibling above it. This was the module's only
# call-time ``re.search`` against a literal pattern -- recompiled for every
# sentence of every option of every merchant turn, and against the convention
# stated beside the span-repair patterns ("compiled once at import rather than
# on every call"). The two runtime ``re.compile`` calls that remain
# (``_prohibited_patterns`` and ``_host_merchandise_pattern``) build their
# alternation out of per-host DATA and cannot be hoisted; this one was a
# constant string.
_MERCHANT_LORE_FRAME_PATTERN = re.compile(
    r"\b(?:old|war|siege|history|memories?|story|symbolize|symbol|"
    r"rite|region|empire|freedom|learn|learned|taught)\b",
    re.IGNORECASE,
)

_MERCHANT_TRANSACTION_PATTERN = re.compile(
    r"\b(?:buy\w*|sell\w*|purchas\w*|pay\w*)\b|"
    r"\b(?:would|will|can|could|do|are)\s+you\s+(?:\w+\s+){0,2}?trad(?:e|ing)\b|"
    r"\btrade\s+(?:me|with\s+me)\b|"
    r"\b(?:less|more|fewer|any|some|enough)\s+(?:coin|gold)\b|"
    + _MERCHANT_COIN_FOR,
    re.IGNORECASE,
)


# Roles that put an NPC in merchant context when its authored config declares
# one. The duck-typed half of the check (shop attributes on the host) covers a
# merchant whose config failed to load.
_MERCHANT_ROLE_PATTERN = re.compile(
    r"\bmerchant\b|\btrader\b|\bshopkeep\w*\b|\bstall\b", re.IGNORECASE
)
#: Attributes whose PRESENCE-AND-TRUTH means merchant context. An empty
#: ``always_stock`` is a merchant who happens to stock nothing right now, so it
#: does not count on its own.
_MERCHANT_TRUTHY_ATTRS = ("shop_name", "always_stock")

#: Attributes whose mere PRESENCE means it. ``stock_count = 0`` is still a
#: counter -- the number is a capacity, not a stock level -- which is why this
#: cannot share the rule above. That distinction used to be a string compare in
#: the middle of the loop, expressed nowhere else.
_MERCHANT_PRESENCE_ATTRS = ("stock_count",)

#: Verbs that read as trade in a role description.
_MERCHANT_ROLE_VERBS = {"buy", "sell", "trade"}
# Fallback drain amounts keyed by conversation_quality — used only when the LLM
# does not supply an explicit signed loquacity_delta (legacy adapter / fallback).
_LOQUACITY_DRAIN = {"positive": 3, "neutral": 8, "negative": 15, "offensive": 30}

# ---------------------------------------------------------------------------
# Loquacity scale
#
# Conversations ran far too long: an authored base of 60-150 against a typical
# per-turn drain of 3-12 bought a dozen or more turns from every NPC in the
# game, and the player-visible effect was NPCs who would not stop talking.
#
# The whole *stamina pool* is therefore scaled to 15% of its former size by ONE
# rule, applied at the end of the computation so no input can escape it:
#
#     effective value = max(1, round_half_up(raw * 15 / 100))   (0 stays 0)
#
# It is applied to the fully-summed maximum (base plus every modifier), to the
# threshold floor, and to the recovery rate — not to the drains. Scaling the
# drains as well would cancel the change out exactly and leave conversations the
# same length, which is the thing being fixed. Turn counts therefore fall to
# roughly 15% of what they were, while every ratio inside the system (threshold
# at a fifth of maximum, exhaustion below the threshold, recovery per beat)
# keeps its meaning.
#
# 0 is passed through because ``loquacity_max == 0`` is the "not yet computed"
# sentinel (see :meth:`ConversationalNPCMixin.loquacity_tick`), and the floor of
# 1 exists so a small pool can never scale away to nothing — a recovery of 0
# would leave an exhausted NPC permanently mute.
# WHERE THE REST OF LOQUACITY LIVES. Seven places, and nothing pointed
# from any one of them to the others, in a 4,400-line module. By name
# rather than by line, because a symbol survives a move and a number
# does not:
#
#   scale_loquacity                   the 15% rule, applied to every
#                                     quantity below except the drains
#   _compute_loquacity                the pool, once per conversation:
#                                     base + modifiers, then scaled
#   _rescale_persisted_loquacity      a save written at the old scale
#   _apply_loquacity_delta            the per-turn change, and the
#                                     `ended` verdict that follows it
#   _retract_guarded_loquacity_gain   undoing a gain the guard rejected
#   loquacity_tick                    recovery while Jean is elsewhere
#   LOQUACITY_DELTA_BOUNDS            what the model is allowed to ask
#   (on the mixin)                    for in one turn
LOQUACITY_SCALE_PERCENT = 15


def scale_loquacity(value: int) -> int:
    """Scale one loquacity quantity by :data:`LOQUACITY_SCALE_PERCENT`.

    Integer arithmetic with explicit half-up rounding rather than ``round()``:
    ``round()`` is banker's rounding, so ``round(10.5)`` is 10 and ``round(22.5)``
    is 22, which makes the rule unstateable in one sentence and the tests
    surprising.
    """
    try:
        raw = int(value)
    except (TypeError, ValueError):
        return 0
    if raw <= 0:
        return 0
    return max(1, (raw * LOQUACITY_SCALE_PERCENT + 50) // 100)


#: Pre-computation placeholder for ``loquacity_recovery``, at the new scale.
#: ``_compute_loquacity`` overwrites it on the first conversation; it exists so a
#: host that is inspected (or persisted) before then never carries an old-scale
#: number.
_DEFAULT_LOQUACITY_RECOVERY = scale_loquacity(2)

#: The attribute on ``src.player.Player`` that holds Jean's travelling party.
#: Named rather than spelled inline so a test can assert the real Player still
#: has it: this was ``allies``, an attribute no Player has ever carried, which
#: made the Gorran loquacity bonus below permanently zero in the game and
#: reachable only from a test double that invented the attribute.
_PARTY_ATTR = "combat_list_allies"

# What moves an NPC's willingness to talk, in the SAME unscaled units as
# ``loquacity_base``. Every one of these was a bare number inside
# ``_compute_loquacity``, which made the design unreadable in the one place it
# most needed to be: the whole point of scaling the SUM rather than the base
# (see the block above) is that these modifiers are commensurate with the base,
# and you cannot see that when the base is a name and the modifiers are digits.
#
# A stat contributes nothing at :data:`_LOQUACITY_STAT_BASELINE`; the weights
# are per point above or below it. Reputation is a step, not a slope -- it
# applies in full once |reputation| reaches 1 -- which is why it has no weight.

#: Authored default when neither the character config nor the personality
#: declares a ``loquacity_base``.
_LOQUACITY_BASE_DEFAULT = 60

#: The stat value that neither helps nor hurts. Both charisma modifiers and the
#: wisdom-driven recovery measure from here.
_LOQUACITY_STAT_BASELINE = 10

#: Per point of the NPC's own charisma. Weighted above Jean's because it is the
#: NPC's patience being modelled.
_LOQUACITY_NPC_CHARISMA_WEIGHT = 3

#: Per point of Jean's charisma.
_LOQUACITY_JEAN_CHARISMA_WEIGHT = 2

#: Applied in full once reputation reaches +/-1, in the matching direction.
_LOQUACITY_REPUTATION_MOD = 20

#: For visibly religious or road-worn gear -- see
#: :data:`_LOQUACITY_FAVOURABLE_EQUIPMENT`.
_LOQUACITY_EQUIPMENT_MOD = 10

#: For travelling with Gorran.
_LOQUACITY_PARTY_MOD = 10

#: Equipment names that read as trustworthy to an NPC. Substring-matched
#: against the lowercased name of every item Jean has equipped.
#:
#: NOTHING IN THE GAME MATCHES, AND THE FIRST ENTRY CONTRADICTS THE STORY.
#:
#: The read below was broken and is fixed, so the modifier is reachable for the
#: first time -- but there is no crucifix, religious token or nomad gear ITEM in
#: `src/items.py`, and this is not simply content nobody has written yet:
#:
#: * The one crucifix in the game is MARA's, worn at her throat
#:   (`src/npc/_friends.py`). Chapter 3's third beat is Jean noticing HERS and
#:   looking away -- "a wrongness he couldn't place". Jean never gets one.
#:   Granting him an NPC-trust bonus for wearing one would contradict the
#:   character the story is drawing.
#: * Jean's actual devotional object is `Relic` -- a fragment of stone from the
#:   Via Dolorosa, carried from Jerusalem. It is a `Consumable`, so it is not
#:   equippable, so it cannot reach an `isequipped` scan at all no matter what
#:   this tuple says.
#: * His equippable accessories are `JeanWeddingBand`, `DullMedallion` and
#:   `GronditeMarkToken` -- sentimental and factional, not devotional.
#:
#: So this vocabulary is left in place ONLY because deleting a modifier and
#: repointing one are both design decisions, and neither belongs in a scrub.
#: `test_the_favourable_equipment_vocabulary_is_honest` pins the state so it
#: stays a known question rather than a silent dead branch.
#:
#: An earlier version of this note said the chapter 3 beat was Jean noticing
#: "his own" crucifix, and attributed Mara's to "Maribel". Both were wrong, and
#: the second is why the note names the file now.
_LOQUACITY_FAVOURABLE_EQUIPMENT = ("crucifix", "religious token", "nomad gear")

#: Recovery per beat. THE WISDOM TERM IS INERT AT EVERY VALUE THE GAME
#: CONTAINS, and this note used to say the opposite ("Recovery per beat is
#: wisdom-driven"), which is the same kind of false comment that let the
#: crucifix modifier above look alive for four rounds.
#:
#: Two floors, either of which alone would flatten it:
#:
#: * ``wisdom // 8`` only exceeds :data:`_LOQUACITY_RECOVERY_FLOOR` at wisdom
#:   24 and above;
#: * :func:`scale_loquacity` only moves off 1 at an unscaled 10 and above, so
#:   the wisdom term would have to reach 10 -- wisdom 80 -- to change the
#:   number that is actually stored.
#:
#: Authored wisdom in this game is 8, on NomadBoy and NomadGirl; the other nine
#: hosts do not set the attribute at all, so they take
#: :data:`_LOQUACITY_STAT_BASELINE` (10). Every conversational NPC therefore
#: recovers exactly ``scale_loquacity(2) == 1`` per beat, which is
#: :data:`_DEFAULT_LOQUACITY_RECOVERY` -- the "pre-computation placeholder"
#: that computation never moves.
#:
#: LEFT AS IS DELIBERATELY. Making the term live means changing the divisor or
#: the floor, and either doubles or halves how fast every NPC in the game
#: regains patience: at divisor 1 a wisdom-8 NPC recovers 1 and a wisdom-10 NPC
#: recovers 2, so the nine hosts that do not declare wisdom would silently
#: overtake the two that do. That is a balance decision for the designer, not
#: a scrub. Documented instead, the way
#: :data:`_LOQUACITY_FAVOURABLE_EQUIPMENT` above is, and pinned by
#: ``TestTheWisdomTermIsInert`` so that authoring a wise NPC -- or changing
#: either constant -- turns a test red and makes somebody revisit this note.
_LOQUACITY_RECOVERY_FLOOR = 2
_LOQUACITY_RECOVERY_WISDOM_DIVISOR = 8

#: Pre-scale floors, kept as the numbers the design was written in so the scaling
#: rule is visible at the one place it is applied.
_LOQUACITY_MAX_FLOOR = 20
_LOQUACITY_THRESHOLD_FLOOR = 10
_LOQUACITY_THRESHOLD_DIVISOR = 5

# Craft vocabulary a progressing ally is licensed to teach about. The system
# prompt's COMBAT SELF-KNOWLEDGE block exists precisely so an ally can discuss
# its own growth, so these keep the state guard from rewriting intended content.
# They only ever excuse a `teaching` flag — never a handover or a promise.
_ALLY_CRAFT_TOPICS = frozenset(
    {
        "technique",
        "techniques",
        "guard",
        "grip",
        "stance",
        "footwork",
        "swordwork",
        "craft",
        "training",
        "practice",
        "fight",
        "fighting",
    }
)

# Words that carry no subject matter, dropped when knowledge_scope entries are
# reduced to guard topics. A topic only ever excuses a `teaching` flag, but
# it excuses it for the whole sentence, so a generic word slipping through
# switches that half of the guard off for the character entirely: the authored
# scopes yield "will" (Liss), "like"/"wait" (Devet) and "work"/"knows"
# (Vespera), each of which would excuse almost any teaching offer they make.
_TOPIC_STOPWORDS = frozenset(
    {
        # structural
        "that",
        "this",
        "with",
        "from",
        "their",
        "them",
        "they",
        "when",
        "what",
        "which",
        "about",
        "into",
        "over",
        "have",
        "been",
        "some",
        "than",
        "then",
        "there",
        "where",
        "while",
        "would",
        "could",
        "should",
        "because",
        "other",
        "your",
        "yours",
        # generic verbs / adjectives / adverbs with no subject matter
        "anyone",
        "better",
        "everyone",
        "know",
        "knows",
        "like",
        "look",
        "many",
        "more",
        "most",
        "much",
        "need",
        "noticed",
        "people",
        "rather",
        "really",
        "take",
        "tell",
        "things",
        "think",
        "very",
        "wait",
        "want",
        "will",
        "work",
        # Jean is the listener, never a subject the guard should excuse
        "jean",
    }
)

# Jean options fallback pool (rotated to avoid repetition)
_JEAN_FALLBACK_POOL = [
    [
        {"tone": "direct", "text": "What else can you tell me?"},
        {"tone": "guarded", "text": "I'll keep that in mind."},
        {"tone": "open", "text": "That's worth knowing."},
    ],
    [
        {"tone": "direct", "text": "Go on."},
        {"tone": "guarded", "text": "Noted."},
        {"tone": "open", "text": "Tell me more."},
    ],
    [
        {"tone": "direct", "text": "Fair enough."},
        {"tone": "guarded", "text": "I see."},
        {"tone": "open", "text": "I'm listening."},
    ],
]

# Brush-off lines for a generic NPC whose patience is spent, picked by a stable
# digest of its name (see ConversationalNPCMixin._stable_pick). A module
# constant like every sibling pool — this one was an inline literal rebuilt on
# every call, in the one pool small enough for that to look harmless.
_BRUSH_OFF_LINES = (
    "They're not in the mood to talk.",
    "A brief shake of the head.",
    "Not now.",
)


def _validate_restored_personality(raw: Any) -> Optional[Dict[str, Any]]:
    """Re-check a save-restored personality seed, or ``None`` if unusable.

    ``NpcChatLLMAdapter._validate_personality`` is the one definition of a
    usable seed: every field type-checked, the three strings neutralised and
    length-capped, ``attitude_to_strangers`` confined to the four the prompt
    offers, ``loquacity_base`` clamped to its bounds. It lives on the adapter
    because that is where seeds are generated; it is *reached* from here
    through the same shared module loader :meth:`_get_adapter` uses, rather
    than re-implemented, because a second copy of this rule would drift the way
    the merchant vocabulary above did.

    ``None`` is also returned when the AI stack is not importable. That is not
    a hole: a box without ``ai.llm_client`` cannot have generated a seed in the
    first place, and the caller's fallback is the hand-written
    :data:`_GENERIC_FALLBACKS` pool, which is authored rather than restored.
    """
    if not isinstance(raw, dict):
        logger.warning("Saved personality is %s, not a mapping.", type(raw).__name__)
        return None
    module = _load_llm_client_module(_AI_DIR / "llm_client.py")
    validate = getattr(
        getattr(module, "NpcChatLLMAdapter", None), "_validate_personality", None
    )
    if not callable(validate):
        logger.warning(
            "ai.llm_client is unavailable, so a saved personality cannot be "
            "validated; falling back to an authored one."
        )
        return None
    # NOT `getattr(module, "_PERSONALITY_FIELDS", frozenset())`. An empty
    # default is a fail-open table: `frozenset().issubset(anything)` is True
    # for every input, so an authority that had been renamed or removed would
    # not raise, not log, and not reject -- it would silently switch the
    # required-field check off and wave every malformed save through to
    # `validate`, which is a different and much narrower gate. The absence of
    # the authority is exactly the case where the seed CANNOT be trusted, so it
    # is treated like the missing validator above: refuse, and fall back to an
    # authored personality.
    required = getattr(module, "_PERSONALITY_FIELDS", None)
    if not required:
        logger.warning(
            "ai.llm_client does not define _PERSONALITY_FIELDS, so the required "
            "fields of a saved personality cannot be checked; falling back to "
            "an authored one."
        )
        return None
    if not required.issubset(raw.keys()):
        logger.warning(
            "Saved personality is missing %s.", sorted(set(required) - set(raw))
        )
        return None
    try:
        return validate(raw)
    except Exception as e:  # a hand-edited save must never break loading a game
        logger.warning(
            "Saved personality failed validation (%s: %s).", type(e).__name__, e
        )
        return None


# Generic nomad fallbacks (selected via a stable crc32 digest, not the
# built-in hash(), so the pick is deterministic across process restarts)
_GENERIC_FALLBACKS = [
    {
        "given_name": "Ren",
        "voice": "sparse and direct",
        "knowledge": ["river crossings", "camp craft"],
        "attitude_to_strangers": "wary",
        "speech_sample": "River's cold this time of year. Careful at the bend.",
        "loquacity_base": 55,
    },
    {
        "given_name": "Tal",
        "voice": "methodical, speaks in short declaratives",
        "knowledge": ["trade routes", "reading terrain"],
        "attitude_to_strangers": "indifferent",
        "speech_sample": "East road's clear. Not sure about the west.",
        "loquacity_base": 65,
    },
    {
        "given_name": "Sev",
        "voice": "guarded but not hostile",
        "knowledge": ["weather patterns", "foraging"],
        "attitude_to_strangers": "guarded",
        "speech_sample": "Storm's coming in from the north. Two days, maybe three.",
        "loquacity_base": 50,
    },
    {
        "given_name": "Vael",
        "voice": "curious, observant",
        "knowledge": ["people-reading", "the Badlands by reputation"],
        "attitude_to_strangers": "curious",
        "speech_sample": "Jean's not from around here. Most people who look like that aren't.",
        "loquacity_base": 70,
    },
]


class ConversationalNPCMixin:
    """LLM-driven conversational dialogue mixin for speaking NPCs."""

    # Class-level caches: files are read once per process, not once per NPC instance.
    _world_facts_cache: Optional[Dict[str, Any]] = None
    _char_config_cache: Dict[str, Any] = {}

    @staticmethod
    def _read_json_config(path, label: str) -> Optional[Dict[str, Any]]:
        """Read one JSON config file, or None with a WARNING on any failure.

        Both callers cache what this returns — the failure included — so an
        unreadable file degrades this NPC (or, for the world facts, every NPC
        in the process) until the process restarts. A silent, unrecoverable
        degradation must not sit at DEBUG, which is why the log line is here
        rather than left to each caller: the two copies of this read differed
        only in their message.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Could not load %s from %s: %s", label, path, e)
            return None

    def _init_chat_attrs(self):
        """Initialize all chat-related attributes. Called at end of host __init__."""
        # Config path can be set by subclass before calling this
        self._chat_config_path: Optional[str] = getattr(self, "_chat_config_path", None)

        # Load character config if path provided (class-level cache). The
        # failure is cached too, so this NPC runs with no character config for
        # the rest of the process.
        self._chat_char_config: Optional[Dict[str, Any]] = None
        if self._chat_config_path:
            if self._chat_config_path not in ConversationalNPCMixin._char_config_cache:
                ConversationalNPCMixin._char_config_cache[self._chat_config_path] = (
                    self._read_json_config(self._chat_config_path, "chat config")
                )
            self._chat_char_config = ConversationalNPCMixin._char_config_cache[
                self._chat_config_path
            ]

        # Load world facts (class-level cache). Also cached on failure, and the
        # empty dict matters: every NPC in the process then runs with an empty
        # allow-list, which silently turns the invented proper-noun scrubber
        # into a scrubber of *all* proper nouns.
        if ConversationalNPCMixin._world_facts_cache is None:
            ConversationalNPCMixin._world_facts_cache = (
                self._read_json_config(_WORLD_FACTS_PATH, "world facts") or {}
            )
        self._chat_world_facts: Optional[Dict[str, Any]] = (
            ConversationalNPCMixin._world_facts_cache
        )

        # For generic nomads: generated on first talk
        self._chat_personality: Optional[Dict[str, Any]] = None

        # In-memory exchange history
        self._chat_history: List[Dict[str, Any]] = []

        # Persistence key (lazy-loaded)
        self._chat_npc_key: Optional[str] = None

        # LLM adapter (lazy-loaded)
        self._chat_adapter: Optional[Any] = None

        # Memo for _allowed_noun_tokens / _guard_allowed_topics — both rebuild
        # a set from static config that only changes when the NPC's own name,
        # personality or world facts do. Declared here rather than sprung into
        # existence inside the accessors, so the instance's attribute surface
        # is readable in one place (the accessors still use getattr, for hosts
        # that skip this initializer).
        self._allowed_noun_cache: Optional[Tuple[Any, Set[str]]] = None
        self._guard_topic_cache: Optional[Tuple[Any, Set[str]]] = None

        # Fallback rotation index (Jean's options pool)
        self._chat_fallback_idx: int = 0

        # Fallback rotation index (NPC line pool — separate counter so the two
        # rotations don't lock-step and repeat in tandem)
        self._chat_npc_fallback_idx: int = 0

        # Pre-compile prohibited phrase regexes for story NPCs
        self._prohibited_patterns: List[Any] = []
        if self._chat_char_config:
            self._prohibited_patterns = [
                re.compile(re.escape(phrase), re.IGNORECASE)
                for phrase in self._chat_char_config.get("prohibited_phrases", [])
            ]

        # Loquacity system
        self.loquacity_current: int = 0
        self.loquacity_max: int = 0
        self.loquacity_threshold: int = 0
        self.loquacity_recovery: int = _DEFAULT_LOQUACITY_RECOVERY

        # "talk" is already present on every host class's base keywords
        # (Friend, Merchant); it alone opens the LLM chat panel client-side,
        # so we deliberately do not also add "chat" as a second, redundant
        # button (see chat()/InteractPanel.jsx — both keywords route to the
        # same panel, and InteractPanel renders one button per keyword with no
        # dedupe, so NPCs showed two buttons for one action).
        #
        # Dropping it here was not enough on its own: src/universe.py setattrs
        # a map payload's props over whatever __init__ produced, and
        # eastern-descent-nomad-camp.json pinned ["talk", "chat"] on all 22 of
        # its conversational NPCs — so the duplicate button survived for
        # exactly the NPCs that have anything to say. Those entries have been
        # stripped to ["talk"] too.
        if not hasattr(self, "keywords"):
            self.keywords = []

    # Sentinel distinguishing "load failed" from "not yet attempted"
    _ADAPTER_FAILED = object()

    def _get_adapter(self) -> Optional[Any]:
        """Lazy-load NpcChatLLMAdapter via importlib. Return None on failure."""
        if self._chat_adapter is self._ADAPTER_FAILED:
            return None
        if self._chat_adapter is not None:
            return self._chat_adapter

        try:
            # Load through the shared loader so this mixin, the Mynx mixin, and
            # ai.combat_strategist all share ONE ai.llm_client module object
            # registered in sys.modules (issue #380) — the adapter's singleton
            # state is no longer split across mutually-unaware module copies.
            module = _load_llm_client_module(_AI_DIR / "llm_client.py")
            if module is not None:
                self._chat_adapter = module.NpcChatLLMAdapter.get_instance()
            else:
                self._chat_adapter = self._ADAPTER_FAILED
        except Exception as e:
            # _ADAPTER_FAILED is sticky for the instance's lifetime, so this NPC
            # never speaks with the LLM again — worth a warning and a traceback,
            # not a DEBUG line nobody sees at the default level.
            logger.warning(
                "ConversationalNPCMixin: could not load adapter: %s", e, exc_info=True
            )
            self._chat_adapter = self._ADAPTER_FAILED

        return (
            self._chat_adapter
            if self._chat_adapter is not self._ADAPTER_FAILED
            else None
        )

    def _memoised(self, attr: str, key: Any, build) -> Any:
        """Return ``build()``'s result, cached on ``self.<attr>`` under ``key``.

        Three accessors (:meth:`_allowed_noun_tokens`,
        :meth:`_guard_allowed_topics`, :meth:`_host_merchandise_pattern`) each
        rebuild a value from static authored config on every turn, and each had
        its own hand-rolled "unpack the tuple, compare the parts, maybe
        rebuild" block. One shape, written three times -- and the third was
        still written out by hand for a while AFTER this helper existed to
        replace it, which is why the count is spelled here rather than left as
        "several".

        A ``None`` result caches correctly: the guard tests the stored TUPLE,
        not the value, so a merchant with no declared stock is not rebuilt on
        every turn. ``_host_merchandise_pattern`` depends on that.

        The key is compared with ``==``, which is what the callers want even
        where they mean identity: tuple comparison goes through
        ``PyObject_RichCompareBool``, which short-circuits on identity, so a
        key holding the very same config dict costs a pointer compare rather
        than a deep one. A *different but equal* dict then compares equal too —
        which the previous ``is`` checks would have rejected, and which is
        harmless, since an equal config builds an equal set.

        ``getattr`` with a default rather than a direct attribute read: minimal
        test doubles and hosts that skip ``_init_chat_attrs`` must still work.
        """
        cached = getattr(self, attr, None)
        if cached is not None and cached[0] == key:
            return cached[1]
        value = build()
        setattr(self, attr, (key, value))
        return value

    def _story(self, player) -> Dict[str, Any]:
        """Get story dict from player.universe, or empty dict."""
        return getattr(getattr(player, "universe", None), "story", None) or {}

    def _get_chapter(self, player) -> str:
        """Get current chapter as string."""
        return str(self._story(player).get("chapter", "1"))

    @staticmethod
    def _game_tick(player) -> int:
        """Current world tick, or 0 when the player has no universe yet.

        The `or 0` matters as much as the getattr chain: a universe whose tick
        is None must still stamp an exchange with a number.
        """
        return getattr(getattr(player, "universe", None), "game_tick", 0) or 0

    def _compute_loquacity(self, player):
        """Compute and set loquacity_max, threshold, and recovery. Only on first call.

        Every number this produces is passed through :func:`scale_loquacity`
        (15%) — see the module-level block above for why the drains are not.
        The scale is applied to the *sum*, after the floor, rather than to the
        base alone: a modifier left at the old scale (+20 for reputation, +10
        for a crucifix) would otherwise dwarf the pool it modifies and reputation
        alone would more than triple an NPC's patience.
        """
        if self.loquacity_max != 0:
            return  # Already computed

        # Base loquacity
        base = (
            (self._chat_char_config or {}).get("loquacity_base")
            or (self._chat_personality or {}).get("loquacity_base")
            or _LOQUACITY_BASE_DEFAULT
        )

        # NPC charisma bonus
        npc_charisma_bonus = (
            getattr(self, "charisma", _LOQUACITY_STAT_BASELINE)
            - _LOQUACITY_STAT_BASELINE
        ) * _LOQUACITY_NPC_CHARISMA_WEIGHT

        # Reputation modifier
        rep = getattr(player, "reputation", {}).get(self.name, 0)
        story_mod = (
            _LOQUACITY_REPUTATION_MOD
            if rep >= 1
            else (-_LOQUACITY_REPUTATION_MOD if rep <= -1 else 0)
        )

        # Jean's charisma modifier
        jean_stat_mod = (
            getattr(player, "charisma", _LOQUACITY_STAT_BASELINE)
            - _LOQUACITY_STAT_BASELINE
        ) * _LOQUACITY_JEAN_CHARISMA_WEIGHT

        # Equipment check.
        #
        # THIS READ WAS DEAD. It was `getattr(player, "equipped", {})`, and
        # there is no `player.equipped` -- not on a fresh Player, not as a
        # class attribute, not set anywhere in src/. The engine models
        # equipment as `isequipped` on the items in `player.inventory`
        # (`src/player/_combat.py` recomputes protection that way, and
        # `src/api/serializers/combat.py` says so outright, citing issue #430:
        # "there is no `combatant.equipped` dict"). The only assignments to it
        # anywhere are five test fixtures that invented the attribute, one of
        # which says as much in its own docstring -- so the modifier looked
        # covered while never once firing in the game.
        #
        # This is the SAME BUG as `player.allies` fifteen lines below, whose
        # comment describes it at length. Fixing that one did not prompt
        # anybody to check its neighbour, which is why the contract guard in
        # `tests/test_npc_chat_merchant_and_loquacity.py` now derives every
        # attribute this mixin reads off `player` and checks each against a
        # real Player rather than trusting the next reader to notice.
        equip_text = " ".join(
            str(getattr(item, "name", "") or "").lower()
            for item in getattr(player, "inventory", None) or []
            if getattr(item, "isequipped", False)
        )
        equip_mod = (
            _LOQUACITY_EQUIPMENT_MOD
            if any(x in equip_text for x in _LOQUACITY_FAVOURABLE_EQUIPMENT)
            else 0
        )

        # Party check (Gorran travelling with Jean). The attribute is
        # :data:`_PARTY_ATTR` — ``Player.combat_list_allies``, which
        # ``Player.__init__`` sets and ``CombatAdapter`` reads throughout.
        # (Named, not pathed: the previous note cited ``src/player.py``, and
        # ``src/player`` is a package. A symbol survives a file move; a path
        # does not, and a wrong path is worse than none.) This was
        # ``player.allies``, which nothing in src/ has ever set, so the modifier
        # was structurally unreachable and every test that "covered" it fed the
        # double an attribute the real Player does not have. The list's first
        # entry is the player himself; the name check skips him harmlessly.
        allies = getattr(player, _PARTY_ATTR, None) or []
        party_mod = (
            _LOQUACITY_PARTY_MOD
            if any(getattr(a, "name", "") == "Gorran" for a in allies)
            else 0
        )

        unscaled_max = max(
            _LOQUACITY_MAX_FLOOR,
            base
            + npc_charisma_bonus
            + story_mod
            + jean_stat_mod
            + equip_mod
            + party_mod,
        )
        loquacity_max = scale_loquacity(unscaled_max)

        self.loquacity_max = loquacity_max
        # The threshold keeps its meaning — a fifth of the pool — and its floor
        # is scaled with everything else; an unscaled floor of 10 against a
        # scaled maximum of 12 would end every conversation on its first turn.
        self.loquacity_threshold = max(
            scale_loquacity(_LOQUACITY_THRESHOLD_FLOOR),
            loquacity_max // _LOQUACITY_THRESHOLD_DIVISOR,
        )
        # The wisdom half of this is currently dead in both directions --
        # nine of the eleven hosts have no `wisdom` at all, and neither the
        # baseline nor the two authored 8s can clear either floor. The long
        # note beside `_LOQUACITY_RECOVERY_WISDOM_DIVISOR` says why it is
        # written out rather than folded away, and `TestTheWisdomTermIsInert`
        # fails if that stops being true.
        self.loquacity_recovery = scale_loquacity(
            max(
                _LOQUACITY_RECOVERY_FLOOR,
                getattr(self, "wisdom", _LOQUACITY_STAT_BASELINE)
                // _LOQUACITY_RECOVERY_WISDOM_DIVISOR,
            )
        )

        if self.loquacity_current == 0:
            self.loquacity_current = loquacity_max

    def _get_npc_key(self, player) -> str:
        """Get or generate persistence key for this NPC instance."""
        if self._chat_npc_key:
            return self._chat_npc_key

        # Story NPCs use their name
        if self._chat_char_config:
            self._chat_npc_key = self.name
            return self._chat_npc_key

        # Generic nomads use class name + instance count. player.npc_chat_histories
        # doesn't exist on a fresh Player (same gotcha as player.reputation —
        # see CLAUDE.md); initialize it in place so the counter below actually
        # persists instead of being written to a throwaway dict every call.
        if getattr(player, "npc_chat_histories", None) is None:
            player.npc_chat_histories = {}
        hists = player.npc_chat_histories
        meta = hists.setdefault("__meta__", {})
        class_name = type(self).__name__
        instance_count = meta.get(class_name, 0)

        self._chat_npc_key = f"{class_name}_{instance_count}"
        meta[class_name] = instance_count + 1

        return self._chat_npc_key

    def _load_history_from_persistence(self, player):
        """Load chat history and personality from player persistence.

        A restored personality is re-validated rather than trusted. It reaches
        this method out of a save file, and it is spliced verbatim into every
        later system prompt by :meth:`_build_character_block` — so a hand-edited
        or corrupted save was, until this check, a permanent prompt injection
        and a permanent crash source ("knowledge": "a string" makes
        ``", ".join(...)`` spell the value out one character at a time).
        Generation-time validation already refuses exactly these shapes; the
        restore path skipped it, which meant the only value in the system that
        outlives the process was the one value nobody checked.
        """
        hists = getattr(player, "npc_chat_histories", {})
        key = self._chat_npc_key
        if not key or key not in hists:
            return

        entry = hists[key]
        self._chat_history = entry.get("exchanges", [])
        if entry.get("personality"):
            restored = _validate_restored_personality(entry["personality"])
            if restored is None:
                # _ensure_personality's deterministic pool is a better character
                # than a half-invented one, and it is what an NPC with no saved
                # personality gets anyway.
                logger.warning(
                    "Discarding an unusable saved personality for npc_key=%s; "
                    "the deterministic fallback will be used instead.",
                    key,
                )
            self._chat_personality = restored

        # Use None (absent) rather than 0 as the "never persisted" sentinel —
        # a persisted 0 (patience exhausted) must be restored as 0, not
        # confused with "no stored value yet" and reset back to full.
        stored_loquacity = entry.get("loquacity_current")
        if stored_loquacity is not None:
            self.loquacity_current = self._rescale_persisted_loquacity(
                stored_loquacity,
                entry.get("loquacity_max"),
                entry.get("loquacity_scale"),
            )

    def _rescale_persisted_loquacity(
        self, stored_current, stored_max, stored_scale=None
    ) -> int:
        """Bring a persisted ``loquacity_current`` onto the current scale.

        Saves written before the 15% scale (see :func:`scale_loquacity`) hold
        old-scale numbers — a current of 72 against a stored maximum of 80 —
        and restoring one verbatim would hand the player a full old-scale
        conversation out of a pool of 12, which is exactly the generosity the
        scale exists to remove.

        THE MARKER IS ``loquacity_scale``, not the size of the stored maximum.
        This used to migrate whenever ``stored_max`` exceeded the maximum
        computed now, and that comparison is true for a second reason that has
        nothing to do with the migration: the computed maximum MOVES with
        reputation. Vespera computes 18 at reputation +1 and 12 at −1, so a
        save written on good terms and loaded on bad ones was treated as an
        old-scale row — 9 of 18 came back as 6 of 12 rather than the flat 9,
        re-proportioning the player's remaining patience for a reputation swing.

        ``game_service._recover_npc_loquacity`` already keyed on the marker
        this module WRITES (``_save_exchange_to_persistence``) and this method
        did not read, so one persisted field had two rescalers keyed two ways.
        Now both ask the marker, and an unmarked row is migrated exactly once.

        A migrated row carries its remaining patience across as the same
        *fraction* of the new pool, so an NPC halfway to exhaustion stays
        halfway. Everything else is clamped into ``[0, loquacity_max]``.
        ``loquacity_max`` is read with ``getattr`` and a 0 default because this
        also runs for hosts that never called ``_compute_loquacity`` (the
        mixin's own ``_load_turn_state`` computes first, but tests and API
        fallbacks load directly), and with no computed pool there is nothing to
        rescale against.
        """
        current = _coerce_int(stored_current, 0)
        max_now = _coerce_int(getattr(self, "loquacity_max", 0), 0)
        if max_now <= 0:
            return current
        old_max = _coerce_int(stored_max, 0)
        already_current_scale = stored_scale == LOQUACITY_SCALE_PERCENT
        if not already_current_scale and old_max > max_now and current > 0:
            # Half-up rounding, integer arithmetic (same rule as scale_loquacity).
            current = (current * max_now + old_max // 2) // old_max
        return max(0, min(max_now, current))

    def _save_exchange_to_persistence(
        self, player, npc_text: str, jean_text: str, game_tick: int, chapter: str
    ):
        """Save exchange to player persistence.

        player.npc_chat_histories doesn't exist on a fresh Player instance
        (same gotcha as player.reputation — see CLAUDE.md); a real Player
        (as opposed to the MinimalPlayer API fallback, which does set this in
        __init__) previously hit this every single call and silently
        no-opped, so no chat history, loquacity, or personality ever
        persisted, and even the opening line was invisible to
        self._chat_history on the very next turn.
        """
        # None covers both "attribute never set" and "explicitly set to
        # None" defensively.
        if getattr(player, "npc_chat_histories", None) is None:
            player.npc_chat_histories = {}
        hists = player.npc_chat_histories

        key = self._chat_npc_key
        if key not in hists:
            hists[key] = {
                "personality": None,
                "loquacity_current": self.loquacity_current,
                "loquacity_max": self.loquacity_max,
                "loquacity_recovery": getattr(
                    self, "loquacity_recovery", _DEFAULT_LOQUACITY_RECOVERY
                ),
                "loquacity_scale": LOQUACITY_SCALE_PERCENT,
                "exchanges": [],
                "last_talked_tick": 0,
                "conversation_count": 0,
            }

        entry = hists[key]
        entry["exchanges"].append(
            {
                "npc": npc_text,
                "jean": jean_text,
                "game_tick": game_tick,
                "chapter": chapter,
            }
        )

        if len(entry["exchanges"]) > _MAX_PERSISTED_EXCHANGES:
            entry["exchanges"] = entry["exchanges"][-_MAX_PERSISTED_EXCHANGES:]

        entry["loquacity_current"] = self.loquacity_current
        entry["loquacity_max"] = self.loquacity_max
        entry["loquacity_recovery"] = getattr(
            self, "loquacity_recovery", _DEFAULT_LOQUACITY_RECOVERY
        )
        entry["loquacity_scale"] = LOQUACITY_SCALE_PERCENT
        entry["last_talked_tick"] = game_tick

        # Store personality for generics
        if self._chat_personality:
            entry["personality"] = self._chat_personality

    def _bump_conversation_count(self, player) -> None:
        """Increment conversation_count for a completed respond round.

        Both call sites of _save_exchange_to_persistence pass jean_text="" —
        chat_open always has (there is no Jean line at the opening) and
        chat_respond persists its new row with jean_text="" (see its call
        site) so the row shape matches chat_open's and next round's history
        fill-in works correctly. A jean_text-truthy increment inside
        _save_exchange_to_persistence itself would therefore never fire for
        either caller, so this method is the single, explicit owner of the
        counter, called right after a call that is guaranteed to have already
        created the persisted entry.
        """
        hists = getattr(player, "npc_chat_histories", None)
        key = self._chat_npc_key
        if hists is not None and key in hists:
            hists[key]["conversation_count"] = (
                hists[key].get("conversation_count", 0) + 1
            )

    def _is_merchant_chat(self) -> bool:
        """Whether this NPC's chat is backed by the shop interface.

        The mixin cannot import ``_merchants`` without creating an import cycle,
        so merchant context is deliberately duck-typed. Authored roles cover
        story merchants, while shop attributes and trade verbs cover concrete
        merchants whose character JSON is absent or failed to load.
        """
        config = getattr(self, "_chat_char_config", None)
        role = config.get("role", "") if isinstance(config, dict) else ""
        if _MERCHANT_ROLE_PATTERN.search(str(role)):
            return True
        if any(getattr(self, attr, None) for attr in _MERCHANT_TRUTHY_ATTRS):
            return True
        if any(
            getattr(self, attr, None) is not None
            for attr in _MERCHANT_PRESENCE_ATTRS
        ):
            return True
        keywords = getattr(self, "keywords", ()) or ()
        return any(
            str(keyword).strip().lower() in _MERCHANT_ROLE_VERBS
            for keyword in keywords
        )

    @staticmethod
    def _is_genuine_jean_introduction(text: str) -> bool:
        """True only for a narrow first-person introduction containing Jean's name."""
        text = str(text).strip()
        if not _JEAN_SELF_INTRO_PATTERN.match(text):
            return False
        # Do not let an introductory prefix smuggle a later third-person
        # reference through ("My name is Jean. Jean has seen worse roads.").
        return sum(1 for _ in _JEAN_NAME_PATTERN.finditer(text)) == 1

    def _build_trade_block(self) -> str:
        """Tell merchant-context models that chat cannot perform transactions."""
        if not self._is_merchant_chat():
            return ""
        return (
            "TRADE: Buying, selling, and stock belong to the shop interface, not "
            "conversation. Do not raise, quote, negotiate, list, or promise "
            + MERCHANT_FORBIDDEN_TOPICS
            + ", and do not ask Jean what he wants to buy. If commerce comes "
            "up, steer toward " + MERCHANT_SUBSTITUTE_TOPICS + " instead."
        )

    def _build_system_prompt(self, player) -> str:
        """Assemble the system prompt out of its blocks, in order.

        Every block is a named builder returning "" when it has nothing to say,
        so this reads as the prompt's table of contents. World facts and
        character used to sit inline here — forty-odd lines and an if/else —
        while the combat and Jean-context blocks beside them were already
        methods.
        """
        chapter = self._get_chapter(player)
        blocks = [
            self._build_world_facts_block(),
            self._build_character_block(),
            self._build_trade_block(),
            # Combat self-knowledge (progressing allies only) — the chat is the
            # sole surface for ally growth (no UI elements by design), so the
            # NPC must be able to speak about its own techniques and experience.
            self._build_combat_knowledge_block(),
            self._build_conduct_block(chapter),
            # Jean's own knowledge boundary — governs Jean's dialogue OPTIONS,
            # generated in the same call as the NPC's line.
            self._build_jean_context_block(player, chapter),
        ]
        return "\n\n".join(block for block in blocks if block)

    def _build_world_facts_block(self) -> str:
        """The shared setting: places, peoples, world rules, tone."""
        facts = self._chat_world_facts
        if not facts:
            return ""
        geo = ", ".join(facts.get("geography", []))
        factions = ", ".join(facts.get("factions_and_peoples", []))
        rules = " ".join(facts.get("world_rules", []))
        tone = facts.get("tone_notes", "")
        return (
            f"WORLD: {facts.get('world_name', 'Aurelion')}. "
            f"{facts.get('brief_description', '')}\n"
            f"Places: {geo}.\nPeoples: {factions}.\n{rules}\nTone: {tone}"
        )

    def _build_character_block(self) -> str:
        """Who this NPC is — from authored config, or from a generated persona."""
        cfg = self._chat_char_config
        if cfg:
            # Story NPC: system_prompt_snippet plus the richer config fields
            # (role/knowledge/personality) that ground the model in-character.
            snippet = cfg.get("system_prompt_snippet", "")
            extras = []
            role = cfg.get("role")
            if role:
                extras.append(f"Role: {role}.")
            knowledge = cfg.get("knowledge_scope") or []
            if knowledge:
                extras.append("You can speak to: " + "; ".join(knowledge) + ".")
            notes = cfg.get("personality_notes") or []
            if notes:
                extras.append("About you: " + " ".join(notes))
            if extras:
                return (snippet + "\n" + "\n".join(extras)).strip()
            return snippet

        # Generic NPC: synthesize from personality
        pers = self._chat_personality or {}
        given_name = pers.get("given_name", "Nomad")
        voice = pers.get("voice", "terse")
        knowledge_list = pers.get("knowledge", [])
        knowledge = ", ".join(knowledge_list) if knowledge_list else "survival"
        return (
            f"You are {given_name}, a nomad. {voice}. "
            f"You know about {knowledge}. You speak in first person. "
            f"Keep responses to 1-{MAX_NPC_SENTENCES} sentences."
        )

    def _build_conduct_block(self, chapter: str) -> str:
        """What the NPC may not write, and how far into the story it may see."""
        return (
            "Jean is he/him. Do not write Jean's dialogue. Do not describe Jean's "
            "internal state.\n"
            # Prevention half of the state guard: nothing said in a chat reaches
            # the engine, so an offer or an appointment is a promise the game
            # cannot keep. Cheaper to not generate one than to catch and revise
            # it. Rendered from _chat_guard.PROMPT_RULES, which the import-time
            # assert there keeps in step with the tripwire tables — hand-written
            # here, this clause had already lost the `solicit` category, so
            # every soliciting option had to be caught and revised at the cost
            # of a real round trip the other three categories avoided.
            + _chat_guard.prompt_rules_line() + "\n"
            f"It is currently chapter {chapter}. Only reference things your character "
            "would plausibly know by now. Never reveal or hint at events, places, "
            "people, or revelations from later in the story."
        )

    def _build_jean_context_block(self, player, chapter: str) -> str:
        """Describe what Jean himself has actually experienced so far.

        Gates Jean's generated dialogue OPTIONS (as opposed to the NPC's own
        chapter guard above, which gates the NPC's line). Without an explicit
        anchor for what Jean personally knows, generated options default to
        generic small talk or, worse, reference events Jean hasn't lived
        through yet. Built from the same story-flag dict the rest of the
        engine reads (``player.universe.story``), so it tracks real narrative
        progress instead of needing separate authoring per NPC.
        """
        story = self._story(player)
        experienced: List[str] = []

        gorran_stage = str(story.get("gorran_language_stage", "0"))
        if gorran_stage != "0":
            experienced.append(
                "Gorran, his Golemite companion, has begun communicating in "
                "words rather than only gesture."
            )

        known = (
            " ".join(experienced)
            if experienced
            else "Nothing unusual beyond ordinary travel and the people he has directly met."
        )
        return (
            f"JEAN'S KNOWN CONTEXT (chapter {chapter}): Jean only knows what he "
            f"has personally witnessed. {known} When generating Jean's dialogue "
            "OPTIONS, never let him reference people, places, events, or "
            "revelations beyond this context, the WORLD facts above, and this "
            "conversation's history — no foreshadowing, no spoilers, nothing "
            "only the NPC or narrator would know."
        )

    def _build_combat_knowledge_block(self) -> str:
        """Describe this ally's combat experience and techniques for the system prompt.

        Empty string for NPCs without ally progression (no growth_profile) —
        generic nomads and non-combat NPCs get no combat block.
        """
        if not getattr(self, "growth_profile", None):
            return ""
        level = int(getattr(self, "level", 1) or 1)
        if level < 3:
            tier = "a capable fighter, still early in the journey"
        elif level < 7:
            tier = "a seasoned fighter, noticeably hardened by recent battles"
        elif level < 13:
            tier = "a veteran of many battles at Jean's side"
        else:
            tier = "a master combatant, honed by long campaigning with Jean"
        techniques = []
        for m in getattr(self, "known_moves", []):
            name = getattr(m, "name", "")
            desc = getattr(m, "description", "")
            # Internal AI actions (NpcAttack/NpcRest/NpcIdle/GorranClub, ...)
            # all ship empty descriptions — a described move is by contract a
            # nameable technique, so new internal moves stay hidden without
            # maintaining a name list here.
            if not name or not desc:
                continue
            techniques.append(f"{name} ({desc})")
        technique_text = (
            "; ".join(techniques) if techniques else "none beyond basic fighting"
        )
        # No game-terms clause here. It used to be hand-written into this
        # block, which is emitted ONLY for NPCs with a growth_profile, while
        # _chat_guard's `game_terms` tripwire scans every NPC — so for every
        # non-ally the rule was detected but never prevented, costing a
        # revision round trip the other categories avoid. The two halves had
        # also drifted to one term in common. Both now come off
        # _chat_guard._GAME_TERMS, rendered into every system prompt by
        # prompt_rules_line() above.
        return (
            f"COMBAT SELF-KNOWLEDGE: You fight alongside Jean and you are {tier}. "
            f"Techniques you have mastered: {technique_text}. "
            "If Jean asks about your combat abilities, how you have grown, or your "
            "techniques, answer naturally from this list in your own voice, the "
            "way a fighter speaks of a craft."
        )

    def _ensure_personality(self, player):
        """For generics: generate personality on first talk, or use fallback."""
        if self._chat_char_config or self._chat_personality:
            return  # Already set (story NPC or already generated)

        adapter = self._get_adapter()
        class_name = type(self).__name__

        if adapter and adapter.enabled:
            try:
                self._chat_personality = adapter.generate_personality(class_name)
            except Exception as e:  # provider errors must never cost the player a turn
                logger.warning(
                    "_ensure_personality generate_personality failed (%s); "
                    "using the deterministic fallback personality.",
                    e,
                )

        # Fallback if LLM unavailable.
        if not self._chat_personality:
            key = self._chat_npc_key or self.name
            self._chat_personality = self._stable_pick(key, _GENERIC_FALLBACKS).copy()

    @staticmethod
    def _stable_pick(key: str, pool: Sequence[_T]) -> _T:
        """Pick one entry from ``pool``, deterministically for a given ``key``.

        crc32 rather than the built-in ``hash()``: hash() is salted per
        process, so a "deterministic" pick would change on every restart and
        the same NPC would brush the player off with a different line each time
        the server came up. The idiom and that rationale were written out
        twice, a thousand lines apart.
        """
        return pool[zlib.crc32(key.encode("utf-8")) % len(pool)]

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        """Word-level tokens for similarity comparison."""
        return set(text.lower().split())

    @staticmethod
    def _jaccard_tokens(set_a: Set[str], set_b: Set[str]) -> float:
        """Jaccard similarity of two already-tokenized texts.

        Split out from :meth:`_jaccard` so a loop comparing one text against
        many (the repetition guard walks eight history rows) tokenizes that one
        text once instead of once per row.
        """
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        union = len(set_a | set_b)
        return len(set_a & set_b) / union if union > 0 else 0.0

    def _jaccard(self, text_a: str, text_b: str) -> float:
        """Compute Jaccard similarity of two texts (word-level tokenization)."""
        return self._jaccard_tokens(self._tokenize(text_a), self._tokenize(text_b))

    def _is_near_duplicate(self, text: str, kept_texts: Iterable[str]) -> bool:
        """True when ``text`` reads too close to an option already kept.

        "Is this option too close to one we are keeping" was written out three
        times — twice as "skip it if *any* kept option is too similar" and once,
        inverted, as "keep it if *every* kept option is far enough". Two
        spellings of one rule, one negation apart, is how a dedup silently stops
        deduping; this is the only spelling now.

        Re-tokenizes ``text`` per comparison rather than taking the
        :meth:`_jaccard_tokens` shortcut ``_qc_check_repetition`` needs: an
        option set is at most three long, so the shortcut buys nothing and
        costs the reader a second way to spell the same comparison.
        """
        return any(
            self._jaccard(text, kept) > _OPTION_SIMILARITY_MAX for kept in kept_texts
        )

    # ------------------------------------------------------------------
    # NPC-text QC pipeline
    # ------------------------------------------------------------------

    @staticmethod
    def _cleanup_removed_spans(text: str) -> str:
        """Repair the holes left by removing a span from a sentence.

        Collapses whitespace, closes gaps before punctuation, deduplicates
        commas and terminators, and strips orphan leading/trailing punctuation
        — so removing "cool" from "that's cool, okay" yields "that's" rather
        than "that's  , ".
        """
        text = _WS_RUN_PATTERN.sub(" ", text)
        text = _SPACE_BEFORE_PUNCT_PATTERN.sub(r"\1", text)
        text = _REPEATED_SEPARATOR_PATTERN.sub(r"\1", text)
        # A removed sentence-final span leaves its comma glued to the
        # terminator ("It's fine, cool." -> "It's fine,."): drop it.
        text = _SEPARATOR_BEFORE_TERMINATOR_PATTERN.sub("", text)
        # A removed clause-sized span leaves the previous sentence's terminator
        # touching its own ("at dawn.. Mind the current."). Runs before the
        # leading-ellipsis check below, so ".." at the head of a line is
        # correctly stripped as an orphan while "..." is kept as hesitation.
        text = _TERMINATOR_RUN_PATTERN.sub(_collapse_terminator_run, text)
        # Strip leading separators — but a leading ellipsis is intentional
        # hesitation ("...fine."), not an orphan, so keep it.
        text = _LEADING_SEPARATOR_PATTERN.sub("", text)
        if not text.startswith("..."):
            text = _LEADING_TERMINATOR_PATTERN.sub("", text)
        text = _TRAILING_SEPARATOR_PATTERN.sub("", text)
        return text.strip()

    @staticmethod
    def _capitalize_sentence_starts(text: str) -> str:
        """Upper-case the first letter at text start or after `.`/`!`/`?`.

        The lookbehind keeps an ellipsis from counting as a sentence end, so
        "Well... maybe." is not rewritten to "Well... Maybe.".
        """
        return _SENTENCE_START_PATTERN.sub(
            lambda m: m.group(1) + m.group(2).upper(),
            text,
        )

    def _extract_action_asides(self, text: str) -> Tuple[str, str]:
        """Pull *asterisk action* stage directions out of spoken text.

        Returns ``(text_without_asides, aside_text)``. Markdown bold markers are
        unwrapped (the words stay); a single-asterisk span at a sentence
        boundary is a stage direction and is extracted for relocation into
        npc_flavor; one embedded mid-sentence is markdown emphasis and is
        unwrapped in place ("I would *never* sell" keeps "never"); stray
        markers are dropped.

        Two rules here were learned from real model output:

        * A span sitting *after a terminator* only counts as a stage direction
          when what follows it starts afresh. "Fine. *never* again." is
          emphasis inside one sentence — treating it as a beat deleted the word
          and spoke "Fine. again."
        * An odd asterisk count means the model never closed its marker
          ("*nods slowly Fine, then."). No pair matches, so the lone marker used
          to be replaced with a space and the stage direction was SPOKEN. The
          run from the lone marker to the next terminator is treated as the
          aside instead. The repair used to fire only when the unclosed marker
          opened the text, which left the two commonest shapes speaking their
          stage direction anyway: "Fine. *nods slowly and turns away" and
          "*nods* Fine. *shrugs" — the latter because the first, *closed* aside
          moves the lone marker off the front.
        """
        if "*" not in text:
            return text, ""
        text = _BOLD_MD_PATTERN.sub(r"\1", text)
        asides: List[str] = []

        # Bound to the pre-substitution string: re.sub rebinds ``text`` only
        # after the whole walk, but reading the name the loop is about to
        # replace is a trap worth closing explicitly.
        source = text

        def _classify(match: "re.Match") -> str:
            before = source[: match.start()].rstrip()
            after = source[match.end() :].lstrip()
            if not before or before[-1] == "*" or not after:
                # Start of text, straight after another aside (so consecutive
                # asides are both extracted), or end of text.
                at_boundary = True
            elif before[-1] in _SENTENCE_BOUNDARY_CHARS:
                at_boundary = (
                    after[0] == "*" or not after[0].isalpha() or after[0].isupper()
                )
            else:
                at_boundary = False
            if at_boundary:
                inner = match.group(1).strip()
                if inner:
                    asides.append(inner)
                return " "
            return match.group(1)

        text = _ACTION_ASIDE_PATTERN.sub(_classify, source)
        if text.count("*") % 2 == 1:
            text = self._take_unclosed_aside(text, asides)
        text = text.replace("*", " ")
        return self._cleanup_removed_spans(text), " ".join(asides)

    @staticmethod
    def _take_unclosed_aside(text: str, asides: List[str]) -> str:
        """Consume an unterminated ``*stage direction`` from anywhere in ``text``.

        Appends what it took to ``asides`` and returns the spoken text with
        that span removed — everything *before* the lone marker is left intact,
        so "Fine. *nods slowly" keeps "Fine." instead of losing the whole line.
        The direction runs from the marker to the next sentence terminator (or
        to the end of the text), since that is where the model's unclosed beat
        reliably ends. When the marker opens the text there is nothing before
        it, so a reply that was *entirely* an unclosed stage direction still
        leaves nothing spoken and correctly fails QC.
        """
        start = text.find("*")
        if start < 0:
            return text
        body = text[start + 1 :]
        cut = len(body)
        for index, char in enumerate(body):
            if char in _TERMINATORS:
                cut = index + 1
                break
        inner = body[:cut].strip().strip(_TERMINATORS).strip()
        if inner:
            asides.append(inner)
        return text[:start] + body[cut:]

    def _allowed_noun_tokens(self) -> Set[str]:
        """Lowercased single-word tokens the proper-noun scan must not touch.

        Multi-word allowlist entries ("Echoing Caves", "Pillar Readers") are
        split into their component tokens — the scan matches token-by-token, so
        checking tokens against the full-string allowlist rejected every word
        of a legitimate multi-word name ("the Echoing Caves" used to come out
        as "the they they"). Also includes this NPC's own name and, for
        generics, the generated given_name — an NPC must be able to say its
        own name.
        """
        facts = getattr(self, "_chat_world_facts", None)
        name = str(getattr(self, "name", "") or "")
        personality = getattr(self, "_chat_personality", None) or {}
        given = str(personality.get("given_name") or "")

        # Memoised: the scan calls this for every NPC line and every flavor
        # beat, and it rebuilt the same set from the same class-level world
        # facts each time. The cache holds a strong reference to the facts
        # object it was built from, so comparing on it is meaningful.
        def build() -> Set[str]:
            tokens: Set[str] = set()
            sources: List[str] = list((facts or {}).get("allowed_proper_nouns", []))
            sources.extend(["Jean", "Gorran", name])
            if given:
                sources.append(given)
            for noun in sources:
                for part in str(noun).replace("-", " ").split():
                    tokens.add(part.lower())
            return tokens

        return self._memoised("_allowed_noun_cache", (facts, name, given), build)

    @staticmethod
    def _is_allowed_noun(low: str, allowed: Set[str]) -> bool:
        """Token-level allowlist check with light inflection tolerance.

        Accepts exact matches, singular/plural variants (Golemite/Golemites),
        and adjectival extensions of an allowed stem of 5+ chars
        (Grondia -> Grondian).
        """
        if low in allowed:
            return True
        if low.endswith("s") and low[:-1] in allowed:
            return True
        if low + "s" in allowed:
            return True
        return any(len(a) >= 5 and low.startswith(a) for a in allowed)

    def _find_invented_nouns(self, text: str) -> Dict[str, str]:
        """Map each invented proper noun in ``text`` to its safe replacement.

        Skips allowed nouns, common English capitalized words, and tokens that
        merely begin a sentence. Replacements are grammatical in both subject
        and object position: "someone" for people/groups, "that place" for
        place-shaped endings ("he met they" was the old failure mode).
        """
        allowed = self._allowed_noun_tokens()

        def _is_sentence_initial(match_start: int) -> bool:
            # Curly quotes count. Omitting them made the first word of curly-
            # quoted speech look mid-sentence, so `He only said, "Leave it."`
            # came out as `"someone it."` — and in strict mode was rejected as
            # "names not in the allowed list: Leave", burning a retry.
            j = match_start - 1
            while j >= 0 and text[j].isspace():
                j -= 1
            return j < 0 or text[j] in _SENTENCE_BOUNDARY_CHARS

        def _is_known(low: str) -> bool:
            return low in _COMMON_CAP_WORDS or self._is_allowed_noun(low, allowed)

        replacements: Dict[str, str] = {}
        for match in _CAP_TOKEN_PATTERN.finditer(text):
            token = match.group(1)
            if token in replacements:
                continue
            # Hyphenated tokens: a descriptive compound ("East-bank") has a
            # known first part and a lowercase remainder; an invented compound
            # ("Kel-Thar") capitalizes its parts. Plain tokens just need to
            # be known.
            raw_parts = [p for p in token.split("-") if p]
            if len(raw_parts) > 1:
                if _is_known(raw_parts[0].lower()) and all(
                    p == p.lower() for p in raw_parts[1:]
                ):
                    continue
            if all(_is_known(p.lower()) for p in raw_parts):
                continue
            if _is_sentence_initial(match.start()):
                continue
            replacements[token] = (
                "that place" if token.endswith(("ia", "on", "or")) else "someone"
            )
        return replacements

    @staticmethod
    def _replace_tokens(text: str, replacements: Dict[str, str]) -> str:
        """Apply every invented-noun substitution in a single pass.

        One alternation rather than a compiled pattern plus a full walk of the
        string per token. Longest first so a shorter token can never shadow a
        longer one that starts with it.
        """
        if not replacements:
            return text
        alternation = "|".join(
            re.escape(token) for token in sorted(replacements, key=len, reverse=True)
        )
        return re.sub(
            r"\b(" + alternation + r")\b",
            lambda match: replacements[match.group(1)],
            text,
        )

    # ------------------------------------------------------------------
    # QC pipeline stages
    #
    # Each stage takes the working text and reports back what it did: the text,
    # a rejection reason (None when it is happy) and whether it rewrote
    # anything. The ORDER lives in one place — _qc_npc_text's body and
    # _apply_content_filters' `stages` tuple — and deliberately not in these
    # docstrings: they used to be hand-numbered "Stage 1..8", which inserting a
    # filter renumbered up to four of, and which _apply_content_filters (owner
    # of three of the numbers) never carried at all.
    # ------------------------------------------------------------------

    def _qc_strip_and_check(self, text: str) -> QcResult:
        """Pull out stage directions, then reject empty/noise text."""
        text, aside = self._extract_action_asides(text.strip())
        text = text.strip()
        if not _has_real_npc_text(text):
            return QcResult(None, "the reply had no spoken text", aside)
        if aside and text[0].islower():
            # The spoken line started after a leading aside ("*shrugs* fine.")
            text = text[0].upper() + text[1:]
        return QcResult(text, None, aside)

    @staticmethod
    def _truncate_at_sentence_boundary(text: str, limit: int) -> str:
        """Cut ``text`` to ``limit`` characters, preferring a boundary.

        The boundary must fall in the second half of the window. The old
        backwards scan took the last terminator at or below the cap wherever it
        landed, so a 461-character reply opening "Aye. " with no further
        punctuation was amputated to "Aye." — discarding everything the
        character actually said, the outcome QC policy 2 exists to forbid.
        Below that floor the text is cut at the last whole word instead and the
        dangling fragment is handled by :meth:`_qc_normalise_sentences`.

        Shared with the flavor path, which used to cut mid-word.
        """
        if len(text) <= limit:
            return text
        floor = int(limit * _MIN_TRUNCATION_KEEP_RATIO)
        for index in range(limit - 1, floor - 1, -1):
            if text[index] in _TERMINATORS:
                end = index + 1
                # Keep a closing quote with the sentence it closes.
                while end < len(text) and text[end] in _CLOSING_QUOTES:
                    end += 1
                return text[:end].strip()
        window = text[:limit]
        return (window.rsplit(" ", 1)[0] if " " in window else window).strip()

    @staticmethod
    def _qc_check_jean_dialogue(text: str) -> Optional[str]:
        """Reject a line that speaks for Jean.

        Always a rejection, in both modes — the NPC must never write Jean's
        dialogue and there is no safe rewrite.
        """
        if _JEAN_DIALOG_PATTERN.search(text):
            logger.debug("_qc_npc_text rejected: Jean-dialogue pattern. text=%r", text)
            return "it wrote Jean's dialogue or narrated Jean speaking"
        return None

    def _qc_invented_nouns(self, text: str, allow_rewrite: bool) -> FilterResult:
        """Substitute or reject names that are not in the world allow-list.

        Rejects in strict mode so the retry can name the offending tokens back
        to the model; substitutes in place on the final attempt so one invented
        word never costs an otherwise good line.
        """
        replacements = self._find_invented_nouns(text)
        if not replacements:
            return FilterResult(text, None, False)
        if not allow_rewrite:
            logger.debug(
                "_qc_npc_text rejected: invented nouns %s. text=%r",
                sorted(replacements),
                text,
            )
            # This list is spliced into the [RETRY GUIDANCE] block of the
            # *system* prompt, and every token in it was chosen by the model.
            # The character class (\b[A-Z][A-Za-z\-]{2,}\b) makes structural
            # forgery impossible — no newline, colon, or angle bracket can get
            # in — but an unbounded list can still crowd the real instructions
            # out of the retry, so name at most the first few.
            named = sorted(replacements)[:_MAX_NAMED_INVENTED_NOUNS]
            return FilterResult(
                text,
                "it used names not in the allowed list: " + ", ".join(named),
                False,
            )
        return FilterResult(self._replace_tokens(text, replacements), None, True)

    def _qc_slang(self, text: str, allow_rewrite: bool) -> FilterResult:
        """Substitute or reject modern slang and anachronisms."""
        if not _SLANG_PATTERN.search(text):
            return FilterResult(text, None, False)
        if not allow_rewrite:
            logger.debug("_qc_npc_text rejected: slang. text=%r", text)
            return FilterResult(
                text, "it used modern slang or anachronistic wording", False
            )
        text = self._cleanup_removed_spans(_SLANG_PATTERN.sub(" ", text))
        if not _has_real_npc_text(text):
            logger.debug(
                "_qc_npc_text rejected: no real text after slang filter. text=%r", text
            )
            return FilterResult(text, "nothing remained after removing slang", True)
        return FilterResult(text, None, True)

    def _qc_prohibited(self, text: str, allow_rewrite: bool) -> FilterResult:
        """Remove phrases this character must never say.

        Removed cleanly — the old "[...]" placeholder was a visible artifact in
        player-facing dialogue. The emptiness check below is guarded by whether
        a pattern actually fired: unconditional, it reported *every other*
        failure (a truncated reply included) to the model as "nothing remained
        after removing prohibited phrasing", even for the many NPCs that have
        no prohibited patterns at all — and that string is spliced verbatim
        into the retry guidance block.
        """
        removed = False
        for pattern in getattr(self, "_prohibited_patterns", ()):
            if not pattern.search(text):
                continue
            if not allow_rewrite:
                logger.debug("_qc_npc_text rejected: prohibited phrase. text=%r", text)
                return FilterResult(
                    text, "it used a phrase this character must never say", False
                )
            text = self._cleanup_removed_spans(pattern.sub(" ", text))
            removed = True
        if removed and not _has_real_npc_text(text):
            logger.debug(
                "_qc_npc_text rejected: no real text after prohibited filter. text=%r",
                text,
            )
            return FilterResult(
                text, "nothing remained after removing prohibited phrasing", True
            )
        return FilterResult(text, None, removed)

    #: Per-instance cache for :meth:`_host_merchandise_pattern`. Keyed on the
    #: the declared stock's CLASS NAMES. Not an id: a restock that swaps
    #: instances of the same classes deliberately does not rebuild, because
    #: the vocabulary those instances yield is identical.
    _host_merchandise_cache = None

    def _host_merchandise_pattern(self):
        """The nouns THIS merchant's own stock puts on the counter.

        Derived from ``always_stock`` (each item's name, subtype and declared
        aliases) and ``specialties`` (the item classes), because those are what
        the game already says the merchant sells. ``Restorative`` alone
        contributes "restorative", "potion", "vial" and "vials" -- every one of
        which a player would actually type at an apothecary, and none of which
        any hand-written list in this module contained.

        Returns ``None`` for a host with no declared stock, so the caller falls
        back to the shared floor vocabulary alone.
        """
        stock = list(getattr(self, "always_stock", None) or [])
        specialties = list(getattr(self, "specialties", None) or [])
        cache_key = (
            tuple(type(item).__name__ for item in stock),
            tuple(getattr(cls, "__name__", str(cls)) for cls in specialties),
        )
        return self._memoised(
            "_host_merchandise_cache",
            cache_key,
            lambda: self._build_merchandise_pattern(stock, specialties),
        )

    def _build_merchandise_pattern(self, stock, specialties):
        """The uncached half of :meth:`_host_merchandise_pattern`."""
        words = set()
        for item in stock:
            # `_shop.py` documents `always_stock` as `list[Item | type[Item]]`
            # and `_create_always_stock_item` accepts the type form — but
            # `Item.name`/`subtype` are bare ANNOTATIONS, so `getattr` on the
            # class returns None and a class-form entry contributed nothing at
            # all. The roster guard skipped past the Nones silently and
            # reported green. Instantiate what we are given.
            if isinstance(item, type):
                try:
                    item = item()
                except Exception:  # pragma: no cover - defensive
                    continue
            for raw in (
                getattr(item, "name", None),
                getattr(item, "subtype", None),
            ):
                if isinstance(raw, str) and raw.strip():
                    words.add(raw.strip().lower())
            for alias in getattr(item, "aliases", None) or []:
                if isinstance(alias, str) and alias.strip():
                    words.add(alias.strip().lower())
        for cls in specialties:
            name = getattr(cls, "__name__", None)
            if isinstance(name, str) and name.strip():
                words.add(name.strip().lower())

        # A multi-word name ("Leather Armor", "small glass vial") is worth
        # matching whole, and its head noun is already carried by the floor
        # vocabulary or by the subtype, so no splitting is needed here.
        # Trailing "s?" so a plural question ("Do you have any restoratives?")
        # matches the singular the item declares.
        alternatives = sorted(
            (re.escape(word) for word in words if len(word) > 2),
            key=len,
            reverse=True,
        )
        if not alternatives:
            return None
        return re.compile(
            r"\b(?:" + "|".join(alternatives) + r")s?\b",
            re.IGNORECASE,
        )

    def _names_merchandise(self, text: str) -> bool:
        """Does ``text`` name a thing this merchant trades in?

        The shared floor plus whatever this host actually stocks. Split in two
        so neither half can quietly become the whole answer again.
        """
        if _MERCHANT_ITEM_PATTERN.search(text):
            return True
        host = self._host_merchandise_pattern()
        return bool(host and host.search(text))

    #: Frames that settle the question on their own, with no noun consulted.
    #:
    #: This tuple is the correction of a defect that survived three fixes. The
    #: classifier used to gate almost every commerce verdict behind
    #: ``has_item`` — a noun list — so "How much for the longsword?" was not a
    #: price question, because "longsword" was not in the list. Each round
    #: widened the list and the next round found the noun it had missed:
    #: weapons, then an apothecary's whole stock, then everything
    #: ``_fill_remaining_stock`` puts on the counter from the item catalogue.
    #:
    #: The list was never going to be complete, because it was answering the
    #: wrong question. "How much for X?" is a price question WHATEVER X is —
    #: the frame carries the speech act and the object does not. So these
    #: patterns are consulted first and alone, and the merchandise vocabulary
    #: is demoted to what it is actually good for: telling "Do you have any
    #: spears?" from "Do you have family in the valley?", one ambiguous frame
    #: where the object genuinely is the deciding evidence.
    _MERCHANT_SELF_SUFFICIENT = (
        _MERCHANT_PRICE_PATTERN,
        _MERCHANT_EXPLICIT_PATTERN,
        _MERCHANT_STOCK_REQUEST_PATTERN,
        _MERCHANT_ANY_AVAILABLE_PATTERN,
        _MERCHANT_ITEMLESS_TRADE_PATTERN,
        _MERCHANT_DIRECT_TRADE_PATTERN,
    )

    def _is_merchant_commerce_question(self, text: str) -> bool:
        """True when a merchant line asks about shop transactions or stock.

        Two tiers, per sentence:

        1. a self-sufficient commerce frame — a price question, an explicit
           shop noun, a stock request, an offer. No noun is consulted, because
           none of these needs one to mean what it means.
        2. the one ambiguous frame, ``do you have|carry|keep X``, resolved by
           :meth:`_is_stock_request`.

        Per SENTENCE rather than per option: a Jean option is routinely two
        sentences, and a commerce question in the second used to be excused by
        a lore word in the first.

        There is deliberately no question-mark gate. There used to be, and it
        made declarative commerce structurally unreachable — "I'll take the
        shortsword." and "The cuirass is yours for eighty gold." were never
        classified at all, which also made three alternations of
        ``_MERCHANT_DIRECT_TRADE_PATTERN`` dead, since a purchase is more often
        announced than asked.
        """
        if not self._is_merchant_chat():
            return False
        for sentence in _split_sentences(text) or [text]:
            if any(p.search(sentence) for p in self._MERCHANT_SELF_SUFFICIENT):
                return True
            if self._is_stock_request(sentence):
                return True
            # The two frames that legitimately need the goods vocabulary,
            # because both are metaphorical or idle without it:
            #   "What is the price of freedom?"   nominal price, abstract
            #   "Did you learn the leather trade?" transaction word, no offer
            if self._names_goods(sentence):
                if _MERCHANT_NOMINAL_PRICE_PATTERN.search(sentence):
                    return True
                if _MERCHANT_TRANSACTION_PATTERN.search(sentence):
                    return True
            # "I'll take X" / "Can I have X" are purchases unless X is one of
            # the idioms. Checked OUTSIDE the goods tier deliberately: the
            # object is usually a noun no vocabulary lists ("I'll take the
            # shortsword."), which is exactly the gate that has failed four
            # times. The closed set of non-goods objects is what decides it.
            if _MERCHANT_OBJECT_GATED_TRADE_PATTERN.search(
                sentence
            ) and not _MERCHANT_NON_GOODS_OBJECT.search(sentence):
                return True
        return False

    def _names_goods(self, sentence: str) -> bool:
        """Does this sentence's object read as the merchant's goods?

        Three kinds of evidence, in the order they are cheap:

        * the shared floor plus this host's derived vocabulary
          (:meth:`_names_merchandise`);
        * a QUANTIFIED noun -- "any longswords", "some mail" -- which is a
          goods reference whatever the noun is. This is the one that stops the
          vocabulary being a gate: the floor's ``swords?`` cannot match inside
          "longsword", no per-host list contained it, and four rounds of
          widening lists never would have;
        * a generic stand-in: "anything else", "behind the counter".

        Deliberately still evidence rather than proof. "Do you have a favourite
        blade?" satisfies it and is really a character question -- see
        ``KNOWN_AMBIGUOUS`` in the merchant tests, where that limitation is
        stated rather than left to be discovered.
        """
        return bool(
            self._names_merchandise(sentence)
            or _MERCHANT_QUANTIFIED_GOODS.search(sentence)
            or _MERCHANT_GENERIC_GOODS.search(sentence)
        )

    def _is_stock_request(self, sentence: str) -> bool:
        """True when this sentence asks whether something is on the counter.

        The frame alone cannot decide it. ``do you have|carry|keep X`` is a
        stock request when X is the goods and the sentence ends there, and a
        maintenance or provenance question when the sentence predicates
        something OF X and continues:

            "Do you have any spears?"              -> stock request
            "Do you keep the leather oiled?"       -> maintenance
            "Do you carry the same harness your    -> provenance
             father did?"
            "Do you have family in the valley?"    -> not about goods at all

        Three things separate them, and none is a longer noun list:

        * a manner/place/person interrogative anywhere in the sentence
          (``_MERCHANT_LORE_LEAD_PATTERN``);
        * trailing predication — a participle, a relative clause, a
          ``for <gerund>`` (``_MERCHANT_TRAILING_PREDICATION``);
        * an object that is plausibly merchandise, either by this host's own
          derived vocabulary or by a generic stand-in ("anything else",
          "behind the counter").

        The last is the only place the noun list is consulted, and it is
        consulted as evidence rather than as a gate — which is the whole
        difference between this and the three versions before it.
        """
        if not _MERCHANT_ITEM_REQUEST_PATTERN.search(sentence):
            return False
        if _MERCHANT_LORE_LEAD_PATTERN.search(sentence):
            return False
        if _MERCHANT_TRAILING_PREDICATION.search(sentence):
            return False
        # The same closed set the object-gated frames use. "Did you have armor
        # at the siege?" and "Do you have a name for that sword?" are the stock
        # frame with a non-goods object, and both are character questions the
        # TRADE block wants kept.
        if _MERCHANT_NON_GOODS_OBJECT.search(sentence):
            return False
        # `_is_lore_frame` already knows the history/biography vocabulary and
        # had become an orphan in the redesign — defined, referenced nowhere.
        # This is the veto it was written to be: "Do you have any memories of
        # the old siege?" is the stock frame wrapped round a war story.
        if self._is_lore_frame(sentence):
            return False
        if not self._names_goods(sentence):
            return False
        return True

    def _is_lore_frame(self, text: str) -> bool:
        """True when the sentence reads as history, ritual, or biography."""
        return bool(_MERCHANT_LORE_FRAME_PATTERN.search(text))

    def _qc_merchant_commerce(
        self, text: str, allow_rewrite: bool
    ) -> FilterResult:
        """Reject or remove merchant price/inventory questions from NPC prose."""
        sentences = _split_sentences(text)
        offending = {
            sentence
            for sentence in sentences
            if self._is_merchant_commerce_question(sentence)
        }
        if not offending:
            return FilterResult(text, None, False)
        if not allow_rewrite:
            return FilterResult(
                text,
                "it asked about price, inventory, stock, or purchasing in merchant chat",
                False,
            )
        kept = [sentence for sentence in sentences if sentence not in offending]
        cleaned = self._cleanup_removed_spans(" ".join(kept))
        if not _has_real_npc_text(cleaned):
            return FilterResult(
                cleaned,
                "nothing remained after removing a merchant price or inventory question",
                True,
            )
        return FilterResult(cleaned, None, True)

    #: Every content-filter stage, in the order it runs. The registration, not
    #: a description of one: :meth:`_apply_content_filters` resolves these off
    #: ``self`` and runs them all, and the prose that used to enumerate them
    #: said "three stages" while the tuple held four. Nothing rots silently now
    #: — ``tests/test_npc_chat_qc_hardening.py`` rediscovers the stages by
    #: signature (``(self, text, allow_rewrite) -> FilterResult``) and fails if
    #: this tuple and the class disagree in either direction.
    _CONTENT_FILTER_STAGES = (
        "_qc_invented_nouns",
        "_qc_slang",
        "_qc_prohibited",
        "_qc_merchant_commerce",
    )

    def _apply_content_filters(self, text: str, allow_rewrite: bool) -> FilterResult:
        """Run the content filters in order, stopping at the first rejection.

        Shared by the NPC-line pipeline and the flavor pipeline. Flavor used to
        carry a reduced copy of this and had drifted three ways — most of all,
        it skipped the prohibited-phrase patterns entirely, so a phrase a
        character must never say was blocked in the spoken line and printed in
        the beat right beside it. Every caller therefore runs every stage in
        :data:`_CONTENT_FILTER_STAGES`; there is no way to opt out of the
        prohibited-phrase pass, because wanting to is what caused the drift.
        """
        rewrote = False
        stages = tuple(getattr(self, name) for name in self._CONTENT_FILTER_STAGES)
        for stage in stages:
            text, reason, stage_rewrote = stage(text, allow_rewrite)
            rewrote = rewrote or stage_rewrote
            if reason:
                return FilterResult(text, reason, rewrote)
        return FilterResult(text, None, rewrote)

    def _qc_check_repetition(
        self, text: str, history: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Reject a line already said earlier in this conversation.

        The caller's retry loop handles the second attempt. ``text`` is
        tokenized once for the whole scan, and the similarity score is computed
        once rather than recomputed inside an eagerly-evaluated log argument.
        """
        tokens = self._tokenize(text)
        for prior in history[-8:]:
            prior_npc = prior.get("npc", "")
            if not prior_npc:
                continue
            score = self._jaccard_tokens(tokens, self._tokenize(prior_npc))
            if score > _NPC_REPEAT_SIMILARITY:
                logger.debug(
                    "_qc_npc_text rejected: repetition guard. "
                    "jaccard=%.2f text=%r prior=%r",
                    score,
                    text,
                    prior_npc,
                )
                return "it repeated a line already said earlier in this conversation"
        return None

    @staticmethod
    def _split_dropping_dangling_fragment(text: str) -> List[str]:
        """QC policy 2 at the prose level: split, minus a cut-off tail.

        A reply that arrives cut off mid-clause ("The ferry runs at dawn. The
        man who keeps it is") used to be handed a cosmetic period, manufacturing
        a sentence the character never finished. The dangling fragment is
        dropped when the complete sentences before it carry at least as much of
        the reply, and kept — and closed by the caller — otherwise. That second
        half matters: discarding it unconditionally is the *inverse* failure of
        the same policy, and would amputate a 461-character reply that opens
        "Aye. " and then runs on with no further punctuation down to "Aye.".

        Shared by the spoken line and the flavor beat, which used to truncate at
        a word boundary and then add the cosmetic period this rule exists to
        forbid. Sentence splitting (including the displaced-closing-quote
        repair) comes from _chat_guard.
        """
        sentences = _split_sentences(text)
        # Re-attach intentional hesitation, *with* the whitespace that followed
        # it: the splitter strips the front of each fragment, so re-prefixing a
        # bare "..." turned "... Fine." into "...Fine.".
        lead = _LEADING_ELLIPSIS_PATTERN.match(text.lstrip())
        if sentences and lead:
            sentences[0] = lead.group(0) + sentences[0]
        if len(sentences) > 1:
            tail = sentences[-1].rstrip(_CLOSING_QUOTES)
            if (not tail or tail[-1] not in _TERMINATORS) and len(
                " ".join(sentences[:-1])
            ) >= len(sentences[-1]):
                sentences.pop()
        return sentences

    def _qc_normalise_sentences(self, text: str) -> str:
        r"""Cap the reply at MAX_NPC_SENTENCES sentences and close it properly.

        Drops a cut-off trailing fragment first (see
        :meth:`_split_dropping_dangling_fragment`), then applies the quote-aware
        terminal punctuation from _chat_guard.

        The closing ``neutralise_model_text`` is a containment step, not
        cosmetics: the accepted line is written back into prompts that are
        structured by newlines and tags (``revise_turn``'s options block,
        ``_format_history``'s speaker-labelled rows), so a newline or a
        ``</player_input>`` surviving QC would let model output forge a row or
        close the fence. This used to be a bare ``\s+`` collapse — the exact
        spelling ``ai/llm_client.py``'s ``sanitize_text`` documents as
        INSUFFICIENT, since it leaves ``\x1b``, ``\x00-\x08``, ``\x7f`` and the
        tag itself exactly where they were. The production adapter happens to
        neutralise upstream; the legacy adapter path this module still supports
        does not, so the guarantee belongs here, at the last point every line
        passes. ``neutralise_model_text`` subsumes the whitespace collapse.
        """
        sentences = self._split_dropping_dangling_fragment(text)
        joined = " ".join(sentences[:MAX_NPC_SENTENCES])
        return _ensure_terminal_punctuation(neutralise_model_text(joined))

    def _qc_npc_text(
        self, text: str, history: List[Dict[str, Any]], allow_rewrite: bool = True
    ) -> QcResult:
        """Run the QC pipeline over one raw NPC line.

        Policy (per design decision): content violations — invented proper
        nouns, modern slang, prohibited phrases — REJECT the line when
        ``allow_rewrite`` is False so the caller can retry with guidance, and
        are repaired in place on the final attempt so a good line is never
        discarded over one word. Structural problems (Jean-dialogue, repetition,
        empty text) always reject; mechanical normalization (length caps,
        punctuation) always applies.
        """
        original = text
        # FIRST, while the line breaks are still here.
        #
        # `src/text_safety.py` promises that on the model path "the
        # line-LEADING label strip stays... it still stops a model that opens a
        # line with `NPC:` from forging a second turn". That promise was void
        # inside this pipeline, because every step below runs before the only
        # call that kept it: `_qc_normalise_sentences` splits on sentence
        # boundaries and rejoins with `" "`, so by the time the neutraliser saw
        # the text there was no line start left for `(?im)^` to anchor to, and
        # `_INLINE_SPEAKER_PREFIX_PATTERN` is disabled for model text by design.
        #
        # Measured before this line existed:
        #
        #     _qc_npc_text("She sets the ledger down.\nNPC: take the blade,"
        #                  " it is yours.", [])
        #     -> "She sets the ledger down. NPC: take the blade, it is yours."
        #
        # -- a live forged turn, written verbatim into `exchanges[-1]["npc"]`
        # and replayed by `_format_history` into every later prompt and into
        # the save file. `_qc_check_jean_dialogue` catches the `Jean:` half and
        # nothing caught this one; `_chat_guard`'s handover tripwire does not
        # fire on "take the blade" either.
        #
        # The closing pass further down stays: this is the layer that needs the
        # line structure, that one is the layer that needs the final text.
        text, reason, aside = self._qc_strip_and_check(text)
        if reason:
            logger.debug(
                "_qc_npc_text rejected: no real text after strip. original=%r", original
            )
            return QcResult(None, reason, aside)

        text = self._truncate_at_sentence_boundary(text, MAX_NPC_TEXT_CHARS)
        reason = self._qc_check_jean_dialogue(text)
        if reason:
            return QcResult(None, reason, aside)

        # AFTER the Jean-dialogue rejection and BEFORE `_qc_normalise_sentences`,
        # which joins sentences with " " and so destroys the line starts
        # `(?im)^` needs. Both halves of that sentence are load-bearing:
        # neutralising earlier strips a forged `Jean:` before `_qc_check_jean_dialogue`
        # can reject on it, which would silently accept the line Jean was
        # supposed to say with its attribution removed; neutralising later sees
        # no line structure at all, which is the defect this fixes.
        text = neutralise_model_text(text)

        text, reason, rewrote = self._apply_content_filters(text, allow_rewrite)
        if reason:
            return QcResult(None, reason, aside)

        reason = self._qc_check_repetition(text, history)
        if reason:
            return QcResult(None, reason, aside)

        text = self._qc_normalise_sentences(text)
        if not _has_real_npc_text(text):
            # Distinct from the content filters' own emptiness checks: this is
            # what a reply that was nothing but a cut-off fragment leaves.
            logger.debug(
                "_qc_npc_text rejected: nothing survived truncation repair. "
                "original=%r",
                original,
            )
            return QcResult(
                None, "the reply was cut off before it said anything", aside
            )
        if rewrote:
            text = self._capitalize_sentence_starts(text)
        logger.debug(
            "_qc_npc_text passed. cleaned_chars=%s original_chars=%s",
            len(text),
            len(original),
        )
        return QcResult(text, None, aside)

    def _qc_flavor_text(self, flavor: str) -> str:
        """Rewrite-only QC for npc_flavor. Returns cleaned flavor or "".

        Flavor is decorative — never worth failing a whole *turn* over — so
        content violations are repaired rather than rejected, and anything left
        unusable simply drops the beat.

        The Jean-dialogue rule is the exception, and it is why this is not just
        ``_apply_content_filters``. "Do not write Jean's dialogue" is a hard
        rule the spoken path always rejects on, but flavor is also where an
        extracted stage direction is *relocated* — and an aside carries across
        a retry — so a model beat like ``*Jean said, "Leave it."*`` used to be
        pulled out of the line the rule protects and printed verbatim in the
        channel beside it. There is no safe rewrite for a line that speaks for
        Jean, and no turn to fail here, so the beat is dropped.
        """
        if not flavor:
            return ""
        # Before `_cleanup_removed_spans`, which runs `_WS_RUN_PATTERN.sub(" ")`
        # and so destroys the line starts the label strip anchors to. Same
        # defect as the spoken path above, same reason, and the test asserts
        # both from one derived population.
        flavor = neutralise_model_text(str(flavor))
        flavor = self._cleanup_removed_spans(
            _BOLD_MD_PATTERN.sub(r"\1", flavor).replace("*", " ")
        )
        if self._qc_check_jean_dialogue(flavor):
            logger.debug("_qc_flavor_text dropped: it wrote Jean's dialogue.")
            return ""
        flavor, _reason, _rewrote = self._apply_content_filters(
            flavor, allow_rewrite=True
        )
        if not _has_real_npc_text(flavor):
            return ""
        flavor = self._truncate_at_sentence_boundary(flavor, MAX_FLAVOR_CHARS)
        # QC policy 2 applies to the beat as well as the line: truncating at a
        # word boundary and then adding a period manufactured a sentence the
        # model never finished ("She sets down the ledger and looks at the.").
        flavor = " ".join(self._split_dropping_dangling_fragment(flavor))
        # Containment, at the same point in the pipeline the spoken line gets it
        # (see :meth:`_qc_normalise_sentences`). This was the one model-authored
        # channel with no neutralisation gate at all: the beat is model text
        # that reaches the player's screen through the chat payload, and a
        # surviving ``</player_input>``, C0 escape or ANSI sequence forges
        # structure just as well from npc_flavor as from npc_text.
        # ``neutralise_model_text`` subsumes the whitespace collapse.
        flavor = neutralise_model_text(flavor)
        if not _has_real_npc_text(flavor):
            return ""
        flavor = _ensure_terminal_punctuation(flavor)
        if flavor[0].islower():
            flavor = flavor[0].upper() + flavor[1:]
        return flavor

    def _qc_jean_options(self, options: Any) -> List[Dict[str, str]]:
        """QC Jean dialogue options. Return the salvageable subset, possibly empty.

        Per design decision this salvages rather than rejecting wholesale: each
        option is validated independently, near-duplicates drop only the later
        member of the pair, and the caller tops the set back up to three from
        the fallback pool.

        The whole list is validated *before* it is cut to three. Slicing first
        meant a malformed option at index 0 made a perfectly good option at
        index 3 unreachable — the salvage this exists to provide, defeated by
        the first line of its own loop. Tones are re-keyed over the KEPT list
        (see below), so a dropped option cannot leave the player two replies
        labelled the same and none "guarded".
        """
        if not isinstance(options, list) or not options:
            return []

        validated: List[Tuple[Optional[str], str]] = []
        for opt in options[:_MAX_OPTION_CANDIDATES]:
            if not isinstance(opt, dict) or "text" not in opt:
                continue

            # Neutralised, not merely stripped. This text is spliced into
            # ``revise_turn``'s newline-delimited options block, so the same
            # containment ``_qc_normalise_sentences`` applies to the spoken
            # line is owed to an option — the comment below already calls it
            # "unbounded untrusted text" and the code then trusted it.
            # ``neutralise_model_text`` subsumes the strip and the collapse.
            text = neutralise_model_text(opt.get("text", ""))
            # Over-length options are DROPPED, not clipped. ai/llm_client.py
            # trims to the same `MAX_OPTION_CHARS` at a word boundary before
            # this ever runs, so anything still over-length came from an
            # adapter that does not apply the cap (the legacy shape, a test
            # double) and is unbounded untrusted text; the top-up refills the
            # slot from the authored pool. Clipping it here instead would ship
            # the mid-word amputation the shared cap exists to prevent.
            if not (_MIN_OPTION_CHARS <= len(text) <= MAX_OPTION_CHARS):
                continue

            # No meta-speech
            if _OPTION_META_PATTERN.search(text):
                continue

            # Jean speaks in the first person. His name is allowed only when he
            # is genuinely introducing himself; all other self-references are
            # third-person or self-address and do not make a usable option.
            if _JEAN_NAME_PATTERN.search(text) and not self._is_genuine_jean_introduction(
                text
            ):
                continue

            # A merchant's chat cannot answer a shop question; the shop UI owns
            # prices and stock. Keep the rule scoped so useful armor/craft lore
            # questions remain available for the player.
            if self._is_merchant_commerce_question(text):
                continue

            tone = str(opt.get("tone", "")).lower()
            validated.append((tone if tone in JEAN_TONES else None, text))

        # Dedup: keep the earlier of any too-similar pair, and stop as soon as
        # three survive — the cut to three happens *after* validation and
        # dedup, which is the whole point of scanning past the first three.
        kept: List[Tuple[Optional[str], str]] = []
        for tone, text in validated:
            if self._is_near_duplicate(text, [t for _tone, t in kept]):
                continue
            kept.append((tone, text))
            if len(kept) >= _JEAN_OPTION_COUNT:
                break

        # Tones are assigned last, over the final kept list, so neither a
        # malformed option nor a near-duplicate can leave a hole in the
        # direct/guarded/open cycle the UI colours its three buttons from.
        #
        # A model tone survives only while it is still free. `tone or <default>`
        # — what this was — is inert on the production path, because
        # ai/llm_client.py already assigns every option a valid tone, so nothing
        # here was ever None; a mid-list drop therefore shipped whatever
        # positional default llm_client had given the option that moved up, and
        # that is how two "direct" replies and no "guarded" one reached the
        # player. Reassignment draws from the tones nothing claimed, which
        # cannot run out: `kept` is capped at _JEAN_OPTION_COUNT == len(
        # JEAN_TONES), so duplicates and holes always balance.
        free = [t for t in JEAN_TONES if t not in {tone for tone, _text in kept}]
        assigned: List[Dict[str, str]] = []
        seen: Set[str] = set()
        for tone, text in kept:
            if tone is None or tone in seen:
                tone = (
                    free.pop(0)
                    if free
                    else JEAN_TONES[len(assigned) % len(JEAN_TONES)]
                )
            seen.add(tone)
            assigned.append({"tone": tone, "text": text})
        return assigned

    def _top_up_jean_options(
        self, options: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Fill a partial option set up to three from the fallback pool.

        Prefers pool entries whose tone is not already covered, skips any that
        read too close to a kept option, and pads unconditionally as a last
        resort so the player always sees three choices.
        """
        options = [dict(o) for o in options[:_JEAN_OPTION_COUNT]]
        if len(options) >= _JEAN_OPTION_COUNT:
            return options
        pool = self._get_fallback_jean_options()
        used_tones = {o["tone"] for o in options}
        for fb in pool:
            if len(options) >= _JEAN_OPTION_COUNT:
                break
            if fb["tone"] in used_tones:
                continue
            if self._is_near_duplicate(fb["text"], [o["text"] for o in options]):
                continue
            options.append(dict(fb))
            used_tones.add(fb["tone"])
        for fb in pool:
            if len(options) >= _JEAN_OPTION_COUNT:
                break
            if any(fb["text"] == o["text"] for o in options):
                continue
            options.append(dict(fb))
        return options

    # ------------------------------------------------------------------
    # Adversarial state-implication guard
    # ------------------------------------------------------------------

    def _guard_allowed_topics(self) -> Set[str]:
        """Subject matter this NPC is deliberately licensed to speak about.

        Some real game state is fed into the system prompt on purpose: a
        progressing ally's own techniques and growth (COMBAT SELF-KNOWLEDGE),
        Gorran's speech stage (JEAN'S KNOWN CONTEXT), and a story character's
        authored ``knowledge_scope``. Naming those here keeps intended content
        out of the reviser's way. The licence is narrow by construction — a
        topic can only excuse a `teaching` flag, never a handover or an
        appointment (see ``_chat_guard._EXCUSABLE_SUBCATEGORIES``), so a
        knowledge_scope entry like "the ferry crossing" can never license
        "I'll give you a knife for the crossing".

        Memoised for the same reason as :meth:`_allowed_noun_tokens`: it runs on
        every turn and rebuilds the same set by re-scanning static authored
        config with a regex.

        The cache key is the move *names*, not the ``known_moves`` list object.
        An ally that learns a technique appends to that list in place
        (``_combat.py``'s ``learn_move``), so an identity check would go on
        answering with the stale set and the guard would start rewriting the
        very talk the whitelist exists to permit. The config dict is keyed by
        identity: it comes from the class-level JSON cache and is never mutated.
        The *raw* attribute is what is cached, not ``config or {}`` — an NPC
        with no character config would otherwise build a fresh empty dict on
        every call and never match its own cache, which is every generic nomad.
        """
        config = getattr(self, "_chat_char_config", None)
        move_names: Tuple[str, ...] = ()
        if getattr(self, "growth_profile", None):
            move_names = tuple(
                str(getattr(move, "name", "")).lower()
                for move in (getattr(self, "known_moves", None) or ())
                if getattr(move, "name", "")
            )

        def build() -> Set[str]:
            topics = {"gorran"}
            if getattr(self, "growth_profile", None):
                topics |= set(_ALLY_CRAFT_TOPICS)
                topics |= set(move_names)
            for entry in (config or {}).get("knowledge_scope") or []:
                for word in _TOPIC_WORD_PATTERN.findall(str(entry).lower()):
                    if word not in _TOPIC_STOPWORDS:
                        topics.add(word)
            return topics

        return self._memoised("_guard_topic_cache", (config, move_names), build)

    def _request_guard_revision(
        self, adapter, system: str, npc_text: str, options: List[Dict[str, str]], flags
    ) -> Optional[Dict[str, Any]]:
        """Ask the model to steer a flagged turn away from what tripped the guard.

        The only place the guard spends an LLM call, and only on a tripped turn.
        Returns None when there is no reviser or the call fails, which drops the
        caller onto the deterministic hedge.
        """
        if adapter is None or not hasattr(adapter, "revise_turn"):
            logger.info(
                "_guard_turn no reviser available (adapter=%s); using deterministic hedge.",
                type(adapter).__name__ if adapter is not None else None,
            )
            return None
        try:
            revision = adapter.revise_turn(
                system, npc_text, options, _chat_guard.guidance_for(flags)
            )
            # A nonconforming adapter returning a truthy non-dict would crash
            # the caller's .get() outside any guard — treat it as no revision.
            return revision if isinstance(revision, dict) else None
        except Exception as e:  # provider errors must never cost the player a turn
            logger.warning("_request_guard_revision revise_turn failed: %s", e)
            return None

    def _resolve_guarded_text(
        self,
        npc_text: str,
        text_flags: List[_chat_guard.GuardFlag],
        revision: Optional[Dict[str, Any]],
        topics: Set[str],
    ) -> str:
        """Return a clean NPC line after the tripwire fired on the original.

        Prefers the reviser's line and falls back to the deterministic hedge of
        the original, which is at least a known quantity. Extracted for the same
        reason the options path already was: the two are structurally identical
        (take the revision if it survives a re-scan, else repair
        deterministically) and this one sat inline inside a hundred-line
        orchestrator while its twin was a method.
        """
        # The revision comes straight off the provider and has never been
        # through the normal QC pipeline, so it can carry invented proper
        # nouns, slang, or a prohibited phrase that _run_npc_turn would have
        # caught. Clean it the same way before re-scanning it.
        candidate = (revision or {}).get("npc_text")
        if isinstance(candidate, str) and candidate.strip():
            candidate = self._qc_npc_text(
                candidate, self._chat_history, allow_rewrite=True
            ).text
        else:
            candidate = None
        if candidate and not _chat_guard.scan_npc_text(candidate, topics):
            logger.info("_guard_turn accepted revised npc_text.")
            return candidate
        logger.info("_guard_turn hedged npc_text deterministically.")
        return _chat_guard.hedge_npc_text(npc_text, text_flags)

    def _guard_turn(
        self,
        adapter,
        system: str,
        turn: Turn,
        deadline: Optional[float] = None,
    ) -> GuardedTurn:
        """Strip implied game-state changes from a turn before the player sees it.

        Conversations are lore only — nothing an NPC *says* is wired to the
        engine — so an offered blade, an offered escort, a claim about Jean's
        pack, or a meeting arranged for dawn is a promise the game cannot keep.

        Costs nothing when the tripwire stays quiet, which is the common case. A
        tripped turn spends at most one extra call; if that call is unavailable,
        out of time, or comes back still dirty, the deterministic hedge ships
        instead, so the player always gets a turn.

        Returns the cleaned turn *and* whether the tripwire fired, because the
        same response's ``reputation_delta`` — one of the two structured fields
        that really does reach the engine — is the caller's to zero when it did.
        """
        npc_text = turn.npc_text
        npc_flavor = turn.npc_flavor
        options = [dict(o) for o in (turn.jean_options or [])]
        topics = self._guard_allowed_topics()
        text_flags: List[_chat_guard.GuardFlag] = _chat_guard.scan_npc_text(
            npc_text or "", topics
        )
        flavor_flags: List[_chat_guard.GuardFlag] = _chat_guard.scan_npc_text(
            npc_flavor or "", topics
        )
        option_flags: List[List[_chat_guard.GuardFlag]] = [
            _chat_guard.scan_option_text(o.get("text", ""), topics) for o in options
        ]

        # Only the line and the options can be *repaired*; flagged flavor is
        # dropped outright below. Escalating on flavor alone would spend a real
        # round trip whose answer is then thrown away, so the guidance — and the
        # decision to call at all — is built from the repairable flags only. Both
        # sets come out of one walk: the escalation set used to be a second loop
        # re-accumulating a subset of the first.
        escalation_flags = list(text_flags)
        for flags in option_flags:
            escalation_flags.extend(flags)
        all_flags = escalation_flags + list(flavor_flags)
        if not all_flags:
            return GuardedTurn(Turn(npc_text, npc_flavor, options), False)

        logger.info(
            "_guard_turn tripwire hit npc=%s categories=%s line_flags=%s flavor_flags=%s option_flags=%s",
            getattr(self, "name", "?"),
            sorted({f.category for f in all_flags}),
            len(text_flags),
            len(flavor_flags),
            sum(len(f) for f in option_flags),
        )

        revision = None
        if escalation_flags:
            if _no_stage_budget(deadline, adapter):
                logger.warning(
                    "_guard_turn skipping revision: the turn's provider budget is "
                    "spent; hedging deterministically instead."
                )
            else:
                revision = self._request_guard_revision(
                    adapter, system, npc_text, options, escalation_flags
                )

        final_text = npc_text
        if text_flags:
            final_text = self._resolve_guarded_text(
                npc_text, text_flags, revision, topics
            )

        # Flavor is decorative (same policy as _qc_flavor_text) — a flagged beat
        # is dropped rather than rewritten. It is never worth a turn.
        final_flavor = "" if flavor_flags else npc_flavor

        # Options: prefer clean revised options; otherwise drop the soliciting
        # ones and top the set back up from the deterministic pool.
        final_options = options
        if any(option_flags):
            final_options = self._rebuild_guarded_options(
                options, option_flags, revision, topics
            )

        return GuardedTurn(Turn(final_text, final_flavor, final_options), True)

    def _rebuild_guarded_options(
        self,
        options: List[Dict[str, str]],
        option_flags: List[List[_chat_guard.GuardFlag]],
        revision: Optional[Dict[str, Any]],
        topics: Set[str],
    ) -> List[Dict[str, str]]:
        """Return three clean Jean options after at least one was flagged."""
        rebuilt: List[Dict[str, str]] = []
        revised = (revision or {}).get("jean_options")
        if isinstance(revised, list):
            # Same QC the generated options get (length caps, meta-speech
            # filter, tone defaulting, near-duplicate dedup) — the reviser's
            # output has never seen it.
            for opt in self._qc_jean_options(revised):
                if _chat_guard.scan_option_text(opt["text"], topics):
                    continue
                rebuilt.append(dict(opt))
        # Salvage policy: clean ORIGINAL options are context-aware and beat
        # generic pool fillers — keep them alongside any clean revised ones
        # (skipping near-duplicates) rather than all-or-nothing replacement.
        for opt, flags in zip(options, option_flags):
            if flags:
                continue
            if self._is_near_duplicate(opt["text"], [k["text"] for k in rebuilt]):
                continue
            rebuilt.append(dict(opt))
        return self._top_up_jean_options(rebuilt)

    def _generate_turn(
        self, adapter, system: str, is_opening: bool, jean_text: Optional[str]
    ) -> Optional[TurnOutcome]:
        """Dispatch one raw NPC turn to the adapter.

        Prefers the combined ``generate_turn`` (NPC reply + Jean options in one
        call — the round-latency budget depends on this), and falls back to the
        legacy two-method adapter interface for backwards compatibility.

        Returns a :class:`TurnOutcome` with the adapter's fields coerced and
        clamped, or None on failure — including a provider that raises, which
        must never escape past the retry loop and the deterministic fallback
        into the catch-all "Conversation failed" error.
        """
        combined = _is_combined_adapter(adapter)
        if combined:
            method, label = adapter.generate_turn, "combined"
        else:
            # Legacy two-call adapter (kept for compatibility with older adapters).
            method, label = adapter.generate_npc_turn, "legacy"
            logger.info(
                "_generate_turn using legacy two-call adapter. is_opening=%s",
                is_opening,
            )
        try:
            if is_opening:
                res = method(system, self._chat_history, is_opening=True)
            else:
                res = method(
                    system, self._chat_history, is_opening=False, jean_text=jean_text
                )
        except Exception as e:  # provider errors must never cost the player a turn
            logger.warning("_generate_turn %s adapter raised: %s", label, e)
            return None
        if not res or not res.get("npc_text"):
            logger.warning(
                "_generate_turn %s adapter returned no npc_text. is_opening=%s keys=%s",
                label,
                is_opening,
                sorted((res or {}).keys()),
            )
            return None
        logger.info(
            "_generate_turn %s adapter succeeded. is_opening=%s npc_text_chars=%s",
            label,
            is_opening,
            len(res.get("npc_text") or ""),
        )
        # Defence in depth: production adapters already coerce and clamp the
        # delta, but a nonconforming value must not raise one frame later in
        # chat_respond's arithmetic.
        rep_low, rep_high = REPUTATION_DELTA_BOUNDS
        return TurnOutcome(
            npc_text=res.get("npc_text"),
            npc_flavor=res.get("npc_flavor", "") or "",
            conversation_quality=res.get("conversation_quality", "neutral"),
            reputation_delta=max(
                rep_low, min(rep_high, _coerce_int(res.get("reputation_delta"), 0))
            ),
            loquacity_delta=res.get("loquacity_delta"),
            raw_options=res.get("jean_options") if combined else None,
        )

    def _run_npc_turn(
        self,
        adapter,
        system: str,
        llm_available: bool,
        is_opening: bool,
        jean_text,
        deadline: Optional[float] = None,
    ) -> Optional[TurnOutcome]:
        """Produce a QC'd NPC turn, or None if the caller should fall back.

        Attempt 1 runs QC in strict mode: content violations (invented nouns,
        slang, prohibited phrases) reject the line, and the retry carries the
        rejection reason back to the model as corrective guidance — resending
        the identical prompt at the same temperature mostly reproduced the same
        violation. The final attempt runs QC in rewrite mode so a usable line is
        salvaged in place rather than dropping to the deterministic fallback.
        Successful calls are still a single round trip.

        When the turn's provider budget runs out before that final attempt, the
        rewrite is applied to the line already in hand rather than cancelled
        along with the retry. The deadline used to take both, so a line rejected
        only for a *content* violation — exactly what rewrite mode exists to
        salvage — was discarded for a generic deterministic fallback, and the
        carried aside went with it. The salvage costs no provider call, which is
        why it is allowed to run after the budget is spent.

        Roleplay *action asides* extracted from the spoken text are relocated
        into npc_flavor (the designated home for physical beats) when the model
        did not supply flavor of its own. An aside carries across attempts: a
        reply that was *entirely* a stage direction fails QC with nothing
        spoken, and its beat used to be thrown away with it.
        """
        if not llm_available or adapter is None:
            logger.debug(
                "_run_npc_turn skipped: llm_available=%s has_adapter=%s",
                llm_available,
                adapter is not None,
            )
            return None
        max_attempts = 2
        reject_reason: Optional[str] = None
        carried_aside = ""
        last_rejected: Optional[TurnOutcome] = None
        for attempt in range(1, max_attempts + 1):
            if attempt > 1 and _no_stage_budget(deadline, adapter):
                logger.warning(
                    "_run_npc_turn abandoning retry after attempt=%s: the turn's "
                    "provider budget is spent.",
                    attempt - 1,
                )
                return self._salvage_rejected_turn(last_rejected, carried_aside)
            logger.info(
                "_run_npc_turn attempt=%s/%s is_opening=%s",
                attempt,
                max_attempts,
                is_opening,
            )
            sys_prompt = system
            if reject_reason:
                sys_prompt = (
                    system + "\n\n[RETRY GUIDANCE] Your previous reply was rejected by "
                    "quality control because " + reject_reason + ". Write a "
                    "fresh reply that avoids this problem."
                )
            model_turn = self._generate_turn(adapter, sys_prompt, is_opening, jean_text)
            if model_turn and model_turn.npc_text:
                cleaned, reason, aside = self._qc_npc_text(
                    model_turn.npc_text,
                    self._chat_history,
                    allow_rewrite=(attempt == max_attempts),
                )
                if aside:
                    carried_aside = aside
                if cleaned:
                    logger.info(
                        "_run_npc_turn QC passed on attempt=%s/%s",
                        attempt,
                        max_attempts,
                    )
                    return self._finish_turn(
                        model_turn, cleaned, aside or carried_aside
                    )
                last_rejected = model_turn
                reject_reason = reason or "it was unusable"
                logger.warning(
                    "_run_npc_turn QC rejected npc_text on attempt=%s/%s reason=%s text=%r",
                    attempt,
                    max_attempts,
                    reject_reason,
                    # WARNING is default-visible and LOG_FILE-persisted; the
                    # full raw line (which can echo player text) stays on the
                    # DEBUG records inside _qc_npc_text.
                    (model_turn.npc_text or "")[:80],
                )
            else:
                logger.warning(
                    "_run_npc_turn generate_turn returned no npc_text on attempt=%s/%s",
                    attempt,
                    max_attempts,
                )
        logger.error(
            "_run_npc_turn exhausted attempts=%s; caller should use deterministic fallback.",
            max_attempts,
        )
        return None

    def _finish_turn(
        self, model_turn: TurnOutcome, npc_text: str, aside: str
    ) -> TurnOutcome:
        """Put the QC'd line and relocated beat back on the adapter's turn.

        The model's own ``npc_flavor`` wins when it supplied one; an extracted
        stage direction fills the channel only when it did not.
        """
        return model_turn._replace(
            npc_text=npc_text,
            npc_flavor=self._qc_flavor_text(model_turn.npc_flavor or aside),
        )

    def _salvage_rejected_turn(
        self, last_rejected: Optional[TurnOutcome], carried_aside: str
    ) -> Optional[TurnOutcome]:
        """Re-run QC in rewrite mode on the last line strict mode rejected.

        Rewrite mode is what turns "it used one name that is not in the world
        allow-list" from a discarded turn into a repaired one. When the budget
        expires before the attempt that would have run it, running it here
        recovers exactly those lines without opening a provider stage.
        Structural rejections (Jean's dialogue, repetition, nothing spoken) fail
        in rewrite mode too, so they still fall through to None and the
        deterministic fallback.
        """
        if last_rejected is None:
            return None
        cleaned, _reason, aside = self._qc_npc_text(
            last_rejected.npc_text, self._chat_history, allow_rewrite=True
        )
        if not cleaned:
            return None
        logger.info(
            "_run_npc_turn salvaged the rejected line in rewrite mode after the "
            "provider budget expired."
        )
        return self._finish_turn(last_rejected, cleaned, aside or carried_aside)

    def _resolve_jean_options(
        self,
        turn: Optional[TurnOutcome],
        adapter,
        npc_line: str,
        turn_number: int,
        deadline: Optional[float] = None,
    ) -> List[Dict[str, str]]:
        """Return three QC'd Jean options.

        Uses options already returned by a combined turn; otherwise requests them
        from a legacy adapter (unless the turn's provider budget is spent);
        otherwise falls back to the deterministic pool. Never makes a second LLM
        call on the combined path (protects the budget).
        """
        if turn is not None and _is_combined_adapter(adapter):
            return self._top_up_jean_options(
                self._qc_jean_options(turn.raw_options or [])
            )
        if (
            turn is not None
            and adapter is not None
            and not _no_stage_budget(deadline, adapter)
        ):
            voice = (self._chat_char_config or {}).get("voice_summary") or (
                self._chat_personality or {}
            ).get("voice", "")
            try:
                raw = adapter.generate_jean_options(
                    self._display_name(),
                    voice,
                    npc_line,
                    self._chat_history,
                    turn_number,
                )
            except Exception as e:  # provider errors must never cost the player a turn
                logger.warning(
                    "_resolve_jean_options generate_jean_options failed: %s", e
                )
                raw = None
            if raw:
                options = self._qc_jean_options(raw)
                if options:
                    return self._top_up_jean_options(options)
        return self._get_fallback_jean_options()

    # ------------------------------------------------------------------
    # Turn assembly shared by both chat entry points
    # ------------------------------------------------------------------

    def _load_turn_state(self, player) -> str:
        """Loquacity, persistence key and stored history.

        The identical opening three steps of chat_open and chat_respond.
        """
        self._compute_loquacity(player)
        npc_key = self._get_npc_key(player)
        self._load_history_from_persistence(player)
        return npc_key

    def _prepare_turn_context(self, player) -> Tuple[str, Any, bool]:
        """Personality, system prompt and adapter.

        The identical closing three steps of both entry points' setup. Returns
        ``(system_prompt, adapter, llm_available)``.
        """
        self._ensure_personality(player)
        system = self._build_system_prompt(player)
        adapter = self._get_adapter()
        return system, adapter, adapter is not None and adapter.enabled

    def _record_jean_line(self, player, jean_text: str) -> None:
        """Attach Jean's line to the open history row, or start one.

        The row persisted at the end of a round is ``{npc: <line>, jean: ""}``,
        so the normal path fills it in place; the append branch only covers a
        conversation whose first stored row is Jean's.
        """
        if self._chat_history and not self._chat_history[-1].get("jean"):
            self._chat_history[-1]["jean"] = jean_text
            return
        self._chat_history.append(
            {
                "npc": "",
                "jean": jean_text,
                "game_tick": self._game_tick(player),
                "chapter": self._get_chapter(player),
            }
        )

    def _apply_loquacity_delta(
        self, loquacity_delta: Optional[int], conversation_quality: str
    ) -> LoquacityOutcome:
        """Apply the round's loquacity change; report whether the talk is over.

        The LLM may signal a signed delta (usually a drain, occasionally a GAIN
        when Jean raises a topic the NPC finds interesting). When no explicit
        delta is supplied (legacy adapter or deterministic fallback), the
        quality-based drain applies so conversations still wind down.

        The "ended" verdict is resolved here rather than separately for the
        fallback-line decision and the response payload, so the two can never
        drift out of sync.
        """
        if loquacity_delta is None:
            drain = _LOQUACITY_DRAIN.get(conversation_quality)
            loquacity_delta = -drain if drain is not None else LOQUACITY_DELTA_DEFAULT
        low, high = LOQUACITY_DELTA_BOUNDS
        loquacity_delta = max(
            low, min(high, _coerce_int(loquacity_delta, LOQUACITY_DELTA_DEFAULT))
        )
        before = self.loquacity_current
        self.loquacity_current = max(
            0, min(self.loquacity_max, self.loquacity_current + loquacity_delta)
        )
        # `applied` is what the clamp actually moved, which is not what was
        # asked for whenever the NPC was already at the ceiling. It is RETURNED
        # rather than stashed on self: the retraction needs it, and an
        # attribute written by this method and read by that one through a
        # `getattr` default is a data dependency the signatures do not admit
        # to. See LoquacityOutcome.
        return LoquacityOutcome(
            requested=loquacity_delta,
            applied=self.loquacity_current - before,
            ended=self.loquacity_current < self.loquacity_threshold,
        )

    def _resolve_fallback_response(
        self, player, conversation_ended: bool
    ) -> Tuple[str, bool]:
        """Deterministic reply for a turn the LLM could not produce.

        Called only after loquacity is resolved, so the line can tell whether
        this exchange is actually ending the conversation (use the authored
        "done talking" closing lines) or is just a mid-conversation LLM hiccup
        (use in-character filler instead of a false goodbye).

        Authored fallback pools are small (often three lines), so a conversation
        that leans on fallback for several turns in a row will otherwise cycle
        back to a line already said in THIS conversation. Rotation alone cannot
        prevent that once the pool wraps, so once it does, the conversation ends
        gracefully instead of visibly repeating.

        Every row in ``self._chat_history`` is a genuinely prior statement at
        this point — including the last one, which was completed with Jean's
        current line before this fallback was generated, while this round's own
        response has not been persisted yet. So the comparison set is the full
        list: slicing off the last entry would blind the check to a duplicate of
        the single most recent line, which is visible whenever an authored pool
        has only one entry (rotation itself only guarantees that no two
        *consecutive* draws collide, and only for pools of two or more).
        """
        response = self._get_fallback_npc_line(
            is_opening=False, player=player, exhausted=conversation_ended
        )
        logger.warning(
            "chat_respond using deterministic fallback response. npc=%s response_chars=%s",
            self.name,
            len(response or ""),
        )
        already_said = {
            entry.get("npc") for entry in self._chat_history if entry.get("npc")
        }
        if not conversation_ended and response in already_said:
            conversation_ended = True
            response = self._get_fallback_npc_line(
                is_opening=False, player=player, exhausted=True
            )
            logger.info(
                "chat_respond fallback pool exhausted; forcing conversation_ended. npc=%s",
                self.name,
            )
        return response, conversation_ended

    def _retract_guarded_loquacity_gain(
        self, outcome: "LoquacityOutcome"
    ) -> None:
        """Take back a loquacity *gain* granted by a turn the guard had to fix.

        ``outcome.requested`` is the second structured field of a chat response
        that reaches the engine (see ``_chat_guard``'s module docstring): it
        persists in the save file, and a positive value RESTORES the NPC's
        willingness to talk. A turn the model had to be talked out of therefore
        does not also get to buy itself more conversation — and more provider
        spend — which is the same reasoning that zeroes ``reputation_delta``.

        Only a gain is retracted. Cancelling a drain would let a conversation
        that trips the guard on every turn run forever, which is the opposite
        of what this protects. ``conversation_ended`` is deliberately NOT
        re-derived: it has already decided whether Jean gets options this
        round, and a retraction can only lower loquacity, so the worst case is
        that the conversation ends one turn later than the strict number says —
        the same slack any drain landing on the threshold has.

        THE AMOUNT RETRACTED IS ``outcome.applied``, not the one the model
        asked for, and the difference is the whole correctness of this method.
        Taking the whole :class:`LoquacityOutcome` rather than an int is what
        stops the two being confused again: there is no longer a number to
        pass wrongly.
        ``_apply_loquacity_delta`` clamps the addition to ``loquacity_max``, and
        a real merchant opens a conversation at the ceiling —
        ``scale_loquacity(80)`` is 12, so ``current == max == 12`` on turn one.
        Subtracting the requested delta there charged the NPC for a gain it had
        never received: a tripped turn carrying the prompt's own suggested +8
        moved 12 -> 12 -> 4, and the +15 clamp ceiling ended the conversation on
        the first turn. The docstring above used to promise the error ran the
        other way, "ends one turn later than the strict number says".

        The tests could not see it: the fixture opened at current=80 against
        max=100, twenty points of headroom, so the saturating case the shipped
        NPCs are always in was structurally unreachable.
        """
        if outcome.applied <= 0:
            return
        self.loquacity_current = max(0, self.loquacity_current - outcome.applied)
        logger.info(
            "chat_respond retracting loquacity applied=+%s (model asked +%s): "
            "the state guard tripped on this turn. npc=%s current=%s",
            outcome.applied,
            outcome.requested,
            self.name,
            self.loquacity_current,
        )

    def _apply_reputation(self, player, reputation_delta: int) -> int:
        """Apply the NPC's in-character reaction to Jean's reputation."""
        if not hasattr(player, "reputation"):
            player.reputation = {}
        old_reputation = player.reputation.get(self.name, 0)
        new_reputation = max(-100, min(100, old_reputation + reputation_delta))
        player.reputation[self.name] = new_reputation
        return new_reputation

    def _guard_and_persist(
        self,
        player,
        adapter,
        system: str,
        assembled: Turn,
        guardable: bool,
        deadline: Optional[float],
        on_tripped=None,
    ) -> GuardedTurn:
        """Run the state guard over an assembled turn, then persist it.

        The identical closing block of both entry points, in the order that
        order matters: the guard runs BEFORE the persist because
        ``_load_history_from_persistence`` hands the saved rows straight back to
        the model next round, so persisting the raw line would feed the
        implication back in and breed more of them. Only guarded text is ever
        written.

        ``on_tripped`` is the same argument for state the tripped verdict
        invalidates. It runs between the guard and the persist because the
        persist writes ``self.loquacity_current`` into the save file, so a
        caller correcting that number afterwards would leave the file holding
        the value the guard had just disallowed. ``chat_open`` passes none —
        an opening line never moves loquacity.

        ``guardable`` is False when the line is authored rather than generated
        (an LLM turn that failed, so the fallback pools supplied both the line
        and the options). The tripwire is not a judge of hand-written prose:
        Mara's chapter-1 starter says "inventory, not greeting" and Kaelen's
        closing line says "come back when you need something sharpened", and it
        would replace both with a generic hedge — after spending a revision call
        to do it.
        """
        guarded = GuardedTurn(assembled, False)
        if guardable:
            guarded = self._guard_turn(adapter, system, assembled, deadline)
        if guarded.tripped and on_tripped is not None:
            on_tripped()
        self._save_exchange_to_persistence(
            player,
            guarded.turn.npc_text,
            "",
            self._game_tick(player),
            self._get_chapter(player),
        )
        return guarded

    def _base_payload(
        self,
        npc_key: str,
        player,
        turn: Turn,
        *,
        llm_available: bool,
        conversation_ended: bool,
    ) -> Dict[str, Any]:
        """The nine fields every chat response carries, whatever happened.

        ``chat_open`` used to build two twelve-key dicts inline while
        ``chat_respond`` had been given a builder — which is how the brush-off
        payload came to be spelled out a third time, one edit away from
        disagreeing with its sibling about what a response looks like.

        Everything past ``turn`` is keyword-only on all three payload builders.
        The two adjacent bools here were passed POSITIONALLY by both wrappers,
        which is the exact transposition hazard ``_respond_payload``'s docstring
        claims was fixed — it had only moved one frame down. A convention the
        signature enforces beats a convention a docstring asks for.
        """
        return {
            "success": True,
            "npc_key": npc_key,
            "npc_flavor": turn.npc_flavor,
            "jean_options": list(turn.jean_options),
            "loquacity_current": self.loquacity_current,
            "loquacity_max": self.loquacity_max,
            "llm_available": llm_available,
            "conversation_ended": conversation_ended,
            "reputation": getattr(player, "reputation", {}).get(self.name, 0),
        }

    def _open_payload(
        self,
        npc_key: str,
        player,
        turn: Turn,
        *,
        llm_available: bool,
        conversation_ended: bool,
    ) -> Dict[str, Any]:
        """Assemble the /open response body.

        The exchange count is always 0: this IS the first exchange. The
        brush-off path passes a bare :class:`Turn` (no flavor, no options) and
        ``conversation_ended=True``.
        """
        payload = self._base_payload(
            npc_key,
            player,
            turn,
            llm_available=llm_available,
            conversation_ended=conversation_ended,
        )
        payload.update(
            {
                "npc_name": self._display_name(),
                "npc_opening": turn.npc_text,
                "turn": 0,
            }
        )
        return payload

    def _respond_payload(
        self,
        npc_key: str,
        player,
        turn: Turn,
        *,
        conversation_quality: str,
        conversation_ended: bool,
        llm_available: bool,
        reputation_delta: int,
    ) -> Dict[str, Any]:
        """Assemble the /respond response body.

        Call after the round has been persisted and the reputation applied: the
        exchange count reads ``self._chat_history``, which aliases the persisted
        list, and the ``reputation`` total ``_base_payload`` reads off the
        player is the post-application one. It used to be passed in as well and
        then written over the identical value — one parameter for a number the
        base builder already had, and one more chance for the two to disagree.

        Everything past ``turn`` is keyword-only (see :meth:`_base_payload`).
        """
        payload = self._base_payload(
            npc_key,
            player,
            turn,
            llm_available=llm_available,
            conversation_ended=conversation_ended,
        )
        payload.update(
            {
                "npc_response": turn.npc_text,
                "conversation_quality": conversation_quality,
                "turn": len(self._chat_history),
                "reputation_delta": reputation_delta,
            }
        )
        return payload

    def chat(self, player):
        """Interact-system entry point for the 'chat' keyword.

        When the frontend's LLM-chat routing is active (llm_chat_enabled), the
        'chat' and 'talk' keywords are intercepted client-side and open the
        NpcChatPanel via the /api/npc-chat endpoints — this method is never
        called.  If those checks are ever bypassed (disabled env, older
        frontend), fall back to the NPC's static talk dialogue so the player
        still gets a response instead of an AttributeError.
        """
        if hasattr(self, "talk"):
            self.talk(player)
        else:
            narrate(self._display_name() + " has nothing to say.")

    def chat_open(self, player) -> Dict[str, Any]:
        """Start conversation. Returns opening line + 3 Jean options."""
        try:
            npc_key = self._load_turn_state(player)

            # Loquacity cutoff
            if self.loquacity_current < self.loquacity_threshold:
                logger.info(
                    "chat_open loquacity cutoff. npc=%s current=%s threshold=%s",
                    self.name,
                    self.loquacity_current,
                    self.loquacity_threshold,
                )
                return self._open_payload(
                    npc_key,
                    player,
                    Turn(self._get_brush_off_line()),
                    llm_available=False,
                    conversation_ended=True,
                )

            system, adapter, llm_available = self._prepare_turn_context(player)
            # Set once the adapter is known: the budget is sized against that
            # adapter's per-call timeout (see :func:`_turn_deadline`), and the
            # brush-off path above never opens a provider stage at all.
            deadline = _turn_deadline(adapter)
            logger.info(
                "chat_open start npc=%s llm_available=%s has_adapter=%s history_len=%s",
                self.name,
                llm_available,
                adapter is not None,
                len(self._chat_history),
            )

            # Generate the NPC opening (and, on a combined adapter, Jean's options
            # in the same call). Opening lines never drain loquacity.
            model_turn = self._run_npc_turn(
                adapter,
                system,
                llm_available,
                is_opening=True,
                jean_text=None,
                deadline=deadline,
            )
            if model_turn is not None:
                npc_opening = model_turn.npc_text
                logger.info(
                    "chat_open LLM opening succeeded. npc=%s npc_text_chars=%s",
                    self.name,
                    len(npc_opening),
                )
            else:
                npc_opening = self._get_fallback_npc_line(
                    is_opening=True, player=player
                )
                llm_available = False
                logger.warning(
                    "chat_open using deterministic fallback opening. npc=%s", self.name
                )

            jean_options = self._resolve_jean_options(
                model_turn, adapter, npc_opening, 0, deadline=deadline
            )
            logger.info(
                "chat_open resolved jean_options count=%s llm_available=%s",
                len(jean_options),
                llm_available,
            )

            # The state guard runs on the assembled turn (line + flavor +
            # options) so one escalation call covers all three; see
            # _guard_and_persist for why it runs before the persist, and why an
            # authored fallback opening is exempt.
            assembled = Turn(
                npc_opening,
                model_turn.npc_flavor if model_turn else "",
                jean_options,
            )
            guarded = self._guard_and_persist(
                player,
                adapter,
                system,
                assembled,
                guardable=model_turn is not None,
                deadline=deadline,
            )

            return self._open_payload(
                npc_key,
                player,
                guarded.turn,
                llm_available=llm_available,
                conversation_ended=False,
            )
        except Exception as e:
            # Detail stays server-side (the logger call above); the client
            # never sees raw exception text, which can leak internals.
            logger.error("ConversationalNPCMixin.chat_open error: %s", e, exc_info=True)
            return {"success": False, "error": "Conversation failed — try again."}

    def chat_respond(self, player, jean_text: str, jean_tone: str) -> Dict[str, Any]:
        """Process Jean's response. Returns NPC reply + 3 new Jean options.

        ``jean_tone`` is accepted for API shape only and deliberately unused.
        The tone the player picked is already carried by the *text* of the
        option they picked — which is what reaches the model, verbatim, as
        Jean's line — so re-stating it in the prompt would tell the model
        nothing the line does not, and telling it "Jean is being guarded" while
        handing it a warm line is worse than silent. The route still validates
        and forwards it (see ``src/api/routes/npc_chat.py``) so a client can
        keep sending it and a future prompt change can start reading it without
        a contract change.
        """
        try:
            # Bound first, then sanitize. This text is not merely sent to the
            # provider once: it is written into the persisted history that every
            # later prompt in the conversation replays, and that history reaches
            # the save file — so a crafted line keeps working for the rest of the
            # conversation and beyond.
            #
            # The cap goes FIRST because src/text_safety.py's convergence bound
            # (a budget derived from the string's own length, then fail
            # closed) was reasoned about a 500-character payload
            # payload, and the route only caps the field at _MAX_FIELD_LEN =
            # 4000. Capping afterwards — as this did — handed the neutraliser
            # eight times the input its bound was sized for, on the one path
            # where an attacker chooses the length. Bounding first also bounds
            # the replayed rows, which multiply token spend for the rest of the
            # conversation; 500 is generous next to the 300-char NPC lines and
            # 160-char options.
            jean_text = neutralise_player_text(jean_text[:MAX_JEAN_TEXT_CHARS])

            npc_key = self._load_turn_state(player)
            self._record_jean_line(player, jean_text)
            system, adapter, llm_available = self._prepare_turn_context(player)
            deadline = _turn_deadline(adapter)
            logger.info(
                "chat_respond start npc=%s llm_available=%s history_len=%s jean_text_chars=%s",
                self.name,
                llm_available,
                len(self._chat_history),
                len(jean_text or ""),
            )

            # Generate NPC response (combined adapters also return Jean's options)
            model_turn = self._run_npc_turn(
                adapter,
                system,
                llm_available,
                is_opening=False,
                jean_text=jean_text,
                deadline=deadline,
            )
            # The defaults come off TurnOutcome rather than being re-spelled
            # here, thousands of lines below where it declares them.
            # conversation_quality keys _LOQUACITY_DRAIN, so a divergence
            # between the two copies would silently change how fast every
            # fallback conversation winds down.
            outcome = model_turn if model_turn is not None else TurnOutcome(npc_text="")
            npc_flavor = outcome.npc_flavor
            conversation_quality = outcome.conversation_quality
            reputation_delta = outcome.reputation_delta
            loquacity_delta = outcome.loquacity_delta
            # The one field that is not a TurnOutcome default: None is the
            # sentinel selecting the deterministic fallback line below, where
            # TurnOutcome's own default for npc_text is "".
            npc_response = model_turn.npc_text if model_turn is not None else None

            if model_turn is not None:
                logger.info(
                    "chat_respond LLM turn succeeded. npc=%s npc_text_chars=%s quality=%s",
                    self.name,
                    len(npc_response or ""),
                    conversation_quality,
                )
            else:
                logger.warning(
                    "chat_respond LLM turn failed; will use deterministic fallback. npc=%s",
                    self.name,
                )

            loquacity = self._apply_loquacity_delta(
                loquacity_delta, conversation_quality
            )
            loquacity_delta = loquacity.requested
            conversation_ended = loquacity.ended
            logger.info(
                "chat_respond loquacity resolved. npc=%s delta=%s current=%s threshold=%s ended=%s",
                self.name,
                loquacity_delta,
                self.loquacity_current,
                self.loquacity_threshold,
                conversation_ended,
            )

            if npc_response is None:
                npc_response, conversation_ended = self._resolve_fallback_response(
                    player, conversation_ended
                )
                llm_available = False

            # Jean's options for the next round. Once loquacity is spent the
            # options are omitted so the NPC's own (lore- and context-aware) reply
            # stands as the graceful closing line, with nothing left to say back.
            # Resolved before the guard so it can review the line, the flavor and
            # the options in a single pass.
            jean_options: List[Dict[str, str]] = []
            if not conversation_ended:
                turn_number = len(self._chat_history) + 1
                jean_options = self._resolve_jean_options(
                    model_turn, adapter, npc_response, turn_number, deadline=deadline
                )

            guarded = self._guard_and_persist(
                player,
                adapter,
                system,
                Turn(npc_response, npc_flavor, jean_options),
                guardable=model_turn is not None,
                deadline=deadline,
                on_tripped=lambda: self._retract_guarded_loquacity_gain(
                    loquacity
                ),
            )
            self._bump_conversation_count(player)

            # Reputation is applied AFTER the guard, and only if the guard stayed
            # quiet. reputation_delta is one of the two structured fields of a
            # chat response that really does reach the engine (ShopSerializer
            # turns player.reputation into charged prices), so a turn whose prose
            # had to be hedged or rewritten does not also get to move Jean's
            # standing on the strength of the same model response.
            if guarded.tripped and reputation_delta:
                logger.info(
                    "chat_respond zeroing reputation_delta=%s: the state guard "
                    "tripped on this turn. npc=%s",
                    reputation_delta,
                    self.name,
                )
                reputation_delta = 0
            # Called for the write, not the return value: _base_payload reads
            # the same post-application total straight off the player.
            self._apply_reputation(player, reputation_delta)

            return self._respond_payload(
                npc_key,
                player,
                guarded.turn,
                conversation_quality=conversation_quality,
                conversation_ended=conversation_ended,
                llm_available=llm_available,
                reputation_delta=reputation_delta,
            )
        except Exception as e:
            # Detail stays server-side (the logger call above); the client
            # never sees raw exception text, which can leak internals.
            logger.error(
                "ConversationalNPCMixin.chat_respond error: %s", e, exc_info=True
            )
            return {"success": False, "error": "Conversation failed — try again."}

    def loquacity_tick(self):
        """Recover loquacity each game beat (called outside active conversation)."""
        if self.loquacity_max == 0:
            return  # Not yet initialised; skip until first conversation
        self.loquacity_current = min(
            self.loquacity_max,
            self.loquacity_current + self.loquacity_recovery,
        )

    def _display_name(self) -> str:
        """Return display name for this NPC."""
        if self._chat_char_config:
            return self.name
        # Generic: use generated name if available
        if self._chat_personality and "given_name" in self._chat_personality:
            return self._chat_personality["given_name"]
        return self.name

    def _get_brush_off_line(self) -> str:
        """Get brush-off when loquacity exhausted."""
        if self._chat_char_config:
            lines = self._chat_char_config.get("closing_lines_when_exhausted", [])
            if lines:
                return lines[0]
        return self._stable_pick(self.name, _BRUSH_OFF_LINES)

    def _next_from_pool(
        self, pool: Sequence[_T], counter_attr: str = "_chat_npc_fallback_idx"
    ) -> Optional[_T]:
        """Return the next entry from ``pool``, rotating via ``counter_attr``.

        Two rotations exist and must not lock-step: the NPC's fallback lines
        and Jean's fallback option sets keep separate counters, which is the
        only thing the two callers ever differed by. The second one carried a
        docstring saying "same rationale as ``_next_from_pool``", which is a
        good sign the two should have been one function.

        Always advances the counter (even for a single-entry pool) so repeated
        fallback calls stay predictable and never silently reset. Uses
        ``getattr``/instance-``setattr`` rather than assuming the counter was
        set by ``_init_chat_attrs`` — minimal NPC test doubles and any future
        caller that skips full init still rotate correctly instead of raising
        ``AttributeError``.
        """
        if not pool:
            return None
        idx = getattr(self, counter_attr, 0)
        entry = pool[idx % len(pool)]
        setattr(self, counter_attr, idx + 1)
        return entry

    def _get_fallback_npc_line(
        self, is_opening: bool, player, exhausted: bool = False
    ) -> str:
        """Get fallback NPC line (no LLM).

        Rotates through the NPC's authored line pool instead of always
        returning the first entry — a stalled/unavailable LLM used to make
        every fallback turn (opening AND every mid-conversation reply) return
        the exact same string, which read as the NPC repeating itself.

        ``exhausted`` distinguishes a genuinely ending conversation (loquacity
        below threshold — use the authored "done talking" closing lines) from
        a mid-conversation LLM hiccup (conversation continues — reusing a
        closing line here would falsely tell the player the NPC is done).
        """
        if self._chat_char_config:
            chapter = self._get_chapter(player)
            starters = self._chat_char_config.get(
                "conversation_starters_by_chapter", {}
            ).get(chapter, [])
            closing = self._chat_char_config.get("closing_lines_when_exhausted", [])

            if is_opening:
                line = self._next_from_pool(starters)
                if line:
                    return line
            elif exhausted:
                line = self._next_from_pool(closing) or self._next_from_pool(starters)
                if line:
                    return line
            else:
                # Mid-conversation and not exhausted: chapter-flavor starters
                # read as plausible filler without implying the NPC is done.
                line = self._next_from_pool(starters) or self._next_from_pool(closing)
                if line:
                    return line
        else:
            # Generic nomad: rotate through a small pool derived from the
            # generated personality so the same speech sample doesn't repeat
            # verbatim on every fallback turn.
            pers = self._chat_personality or {}
            speech = pers.get("speech_sample")
            knowledge = pers.get("knowledge") or []
            given_name = pers.get("given_name", "They")
            pool = [
                text
                for text in (
                    speech,
                    (
                        f"{given_name} falls quiet a moment, considering."
                        if speech
                        else None
                    ),
                    f"Ask again about {knowledge[0]}, maybe." if knowledge else None,
                )
                if text
            ]
            line = self._next_from_pool(pool)
            if line:
                return line

        return "Nothing to say right now."

    def _get_fallback_jean_options(self) -> List[Dict[str, str]]:
        """Return fallback Jean options, cycling through the pool.

        Returns copies (not the shared module-level dicts) so callers can
        never mutate the pool.
        """
        pool = self._next_from_pool(
            _JEAN_FALLBACK_POOL, counter_attr="_chat_fallback_idx"
        )
        return [dict(o) for o in (pool or ())]
