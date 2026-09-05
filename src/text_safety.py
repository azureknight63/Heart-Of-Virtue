"""Neutralisation of text before it enters an LLM prompt or a terminal.

Deliberately dependency-free — standard library only, no imports from ``src.``
or ``ai.`` — following the ``src/env_bootstrap.py`` precedent. ``ai/llm_client``
must be importable without dragging in the game engine, and ``src/npc`` must be
importable without dragging in the provider stack, so the one rule they share
can only live somewhere that depends on neither.

There used to be two implementations of that rule: ``_sanitize_player_text`` in
``src/npc/_chat_llm.py`` (ingress) and ``_neutralise_player_text`` in
``ai/llm_client.py`` (prompt assembly). They diverged — the adapter's copy
never learned about line-leading speaker labels or the U+2028/2029 separators —
and the adapter's copy is the one guarding the *replayed history*, so the extra
rules protected the live turn and nothing else. This module is the union of
both, and both now import it.

Applying it at two layers is deliberate defence in depth, not redundancy. The
ingress call decides what is written into the saved history; the prompt-assembly
call decides what is interpolated into a prompt, and it also has to cover text
that never passed through ingress at all (model output replayed as an NPC line,
a save file edited by hand, a caller that skips the API route). Either layer
alone leaves a real path uncovered.

Two entry points, because the two kinds of text are not the same kind of threat:

* :func:`neutralise_player_text` — text the player typed. Everything below.
* :func:`neutralise_model_text` — text the model wrote. Everything except the
  space-anchored speaker-label strip; see that function for why.

Both converge. The first version of this module ran each rule exactly once, in
an order that let one rule manufacture work for a rule that had already run —
see :func:`_neutralise` for the two payloads that exploited it.
"""

import hashlib
import logging
import re

logger = logging.getLogger(__name__)

# A line-leading run of ``NPC:`` / ``Jean:`` labels. The conversation history
# block is newline-delimited with exactly these two prefixes marking whose turn
# it is, so a player who types one forges a turn that never happened and then
# answers it.
#
# The trailing ``+`` buys nothing for the fixed point and everything for the
# pass bound. ``re.sub`` resumes past its own replacement, so without it a chain
# — ``NPC:NPC:NPC:`` — loses one label per pass and costs one pass per four
# characters, which is the cheapest amplifier in this module. With it the whole
# run goes in a single substitution. See :func:`_pass_budget`.
_SPEAKER_PREFIX_PATTERN = re.compile(r"(?im)^[ \t]*(?:(?:NPC|Jean)[ \t]*:[ \t]*)+")

# The same label once the text has been collapsed to a single line. Anchored to
# the start of the string *or* to a preceding space, because a U+2028 or a
# control character can push a forged label off a line start where the pattern
# above can no longer see it, and collapsing whitespace then leaves it mid-string
# on the one history line this speaker gets.
#
# This one is player-text only. It cannot tell a forged label from an ordinary
# vocative, so "Careful, Jean: the bridge is out." loses the name and the colon.
# That is a cost the player's own text pays to stop the player writing the NPC's
# next line — but the consolidation briefly charged it to *model* output too,
# where it bought nothing (the model is not the attacker; the tag fence is what
# guards that path) and silently ate authored NPC dialogue. See
# :func:`neutralise_model_text`.
#
# The ``+`` is the pass-bound fix, and this is the pattern that needed it most.
# The lookbehind reads the *input* string, so in ``x NPC:NPC:NPC:`` only the
# first label is preceded by whitespace when the scan arrives and a single
# ``re.sub`` deleted exactly one label. Repeating the group inside one match
# consumes the whole chain instead. See :func:`_pass_budget`.
_INLINE_SPEAKER_PREFIX_PATTERN = re.compile(
    r"(?i)(?:^|(?<=\s))(?:(?:NPC|Jean)\s*:\s*)+"
)

# The delimiter ``_wrap_player_text`` opens around player text. A literal
# closing tag inside the text would end the block early and put everything after
# it back in instruction position. Whitespace is tolerated on both sides of the
# slash: a model reads ``< / player_input >`` as the same tag, and both previous
# copies of this pattern allowed it only after the slash.
_PLAYER_INPUT_TAG_PATTERN = re.compile(r"<\s*/?\s*player_input\s*>", re.IGNORECASE)

# Every code point that is invisible in a transcript and not invisible to a
# tokenizer. A bare ``\x08`` is nobody's idea of player input, and the rest are
# worse than noise.
#
# DERIVED, NOT ENUMERATED, and that distinction is the whole point. This was a
# hand-written list of the families someone thought of, described by the very
# sentence above as covering "every Unicode family that is invisible in a
# transcript" -- and it did not. It missed 89 code points, including U+00AD
# SOFT HYPHEN, U+061C ARABIC LETTER MARK and the entire C1 block
# U+0080-U+009F, so a player could type ``<\u00ad/player_input>`` and close
# the prompt fence through both neutralisation layers untouched. The guard that
# was supposed to catch that parametrised over fifteen characters drawn from
# the same list it was testing, so it could not have failed.
#
# The set below is now the Unicode general categories Cc, Cf, Zl and Zp --
# "control", "format", "line separator", "paragraph separator" -- which is the
# standard's own answer to "is this invisible", plus one deliberate addition
# noted below. ``tests/test_text_safety.py`` regenerates it from
# ``unicodedata.category`` across the whole code space and fails if the two
# disagree, so a new Unicode release cannot silently reopen the hole.
#
# The families worth naming, because each is a live attack rather than noise:
#
# * U+2028/2029, the line and paragraph separators. ``str`` whitespace
#   splitting knows about them in some contexts and not others, and ``re``'s
#   MULTILINE ``^`` does not treat them as line starts at all — which is
#   exactly how a forged label gets past the line-anchored pattern above.
# * U+200B–U+200F, U+2060 and U+FEFF: the zero-width family. Inserted inside a
#   forged ``NPC:`` they split it into fragments no pattern here can see,
#   while the model reads the label unchanged.
# * U+202A–U+202E and U+2066–U+2069: the bidi overrides and isolates. They
#   reorder what a human reviewing a transcript reads without touching the
#   byte order the model receives, so the visible text and the sent text can
#   be made to disagree completely.
# * U+E0000–U+E007F, the tag block: "ASCII smuggling". A whole instruction is
#   encoded one tag character per ASCII byte, rendering as nothing anywhere in
#   the UI, and several tokenizers decode it straight back to text.
#
# Replacing with a space rather than deleting, for the same reason the tag pass
# does: a deletion lets the neighbours of a removed character join up. The one
# real cost is U+200D, the emoji zero-width joiner — a family emoji arrives as
# its separate members. Cheap next to leaving a hole shaped like precisely the
# character an attacker would reach for.
#: Categories Cc/Cf/Zl/Zp, plus the whole of the tag block. The tag block's
#: unassigned tail (U+E0000, U+E0002-U+E001F) is category Cn, not Cf, so
#: deriving from category alone would have dropped 31 code points out of the
#: middle of an ASCII-smuggling range -- an unassigned code point still round
#: trips through a tokenizer that decodes the block. Kept as a union for that
#: reason, and the test asserts both halves.
_CONTROL_CHAR_TAG_BLOCK = (0xE0000, 0xE0080)
_CONTROL_CHAR_PATTERN = re.compile(
    "["
    "\x00-\x1f\x7f-\x9f\xad\u0600-\u0605\u061c\u06dd\u070f"
    "\u0890-\u0891\u08e2\u180e\u200b-\u200f\u2028-\u202e"
    "\u2060-\u2064\u2066-\u206f\ufeff\ufff9-\ufffb\U000110bd"
    "\U000110cd\U00013430-\U0001343f\U0001bca0-\U0001bca3"
    "\U0001d173-\U0001d17a\U000e0000-\U000e007f"
    "]+"
)

_WS_RUN_PATTERN = re.compile(r"\s+")

# The fail-closed hammer: with no angle brackets left in the string, no
# substitution below can produce a tag, which is what lets :func:`_fail_closed`
# run the remaining rules to convergence without a pass bound of its own.
_ANGLE_BRACKET_PATTERN = re.compile(r"[<>]")

#: The length past which :func:`_pass_budget` stops scaling and the ceiling
#: bites. Not a truncation and not an unchecked precondition — the ``min()`` in
#: :func:`_pass_budget` is the check.
#:
#: 4000 is ``_MAX_FIELD_LEN`` in ``src/api/routes/npc_chat.py``, the widest door
#: into this module. Everything real is far inside it: ``src/npc/_chat_llm.py``
#: cuts player text to its 500-character ``MAX_JEAN_TEXT_CHARS`` *before*
#: calling in, and model text is bounded by the request that produced it — the
#: largest ``max_tokens`` configured anywhere in ``ai/llm_client.py`` is
#: ``_STRUCTURED_MAX_TOKENS`` = 1024, with the chat paths at 400–800.
#:
#: Truncating here instead was considered and rejected on the measurements. It
#: would have to cut model text too — several ``ai/llm_client.py`` call sites
#: neutralise a provider response *before* their own length cap — and it would
#: buy nothing, because length is not what drives the pass count. Prose of any
#: size settles in one or two passes; 100 000 characters of it needs exactly
#: one. Reaching the ceiling takes 15 030 characters of *pure* nested
#: ``</player_input>``, roughly 3750 tokens against a 1024-token budget. So the
#: trade would be real dialogue lost at 4000 characters, to prevent nothing.
_MAX_INPUT_CHARS = 4000

#: The ceiling on :func:`_pass_budget` — a time guard, not a correctness one.
#:
#: Work is ``O(passes x length)``, so an unbounded budget on an unbounded input
#: is quadratic: 100 000 characters of nesting takes 3.6s against this ceiling
#: and 13.8s without one (measured). Past the ceiling :func:`_fail_closed`
#: takes over, and it is safe *and* non-destructive — on benign prose it
#: returns the string byte-identical; the most it ever does is delete angle
#: brackets. Nothing is discarded, which is why letting the guard bite beats
#: truncating the input to avoid it.
_MAX_NEUTRALISE_PASSES = _MAX_INPUT_CHARS // 4 + 2


def _pass_budget(text: str) -> int:
    """Passes to allow for *this* string, computed from the string itself.

    **Any pass after the first that changes the string shortens it by at least
    four characters:**

    * pass 1's control strip replaces every control and invisible character
      with a space, and no rule here emits a character in that class, so from
      pass 2 onwards the control strip is the identity;
    * the two label strips delete, and the shortest thing they can delete is
      ``NPC:`` — four characters;
    * the tag strip replaces a match of at least fourteen characters with one;
    * the whitespace collapse cannot be the only change on a later pass. The
      previous pass ended with that same collapse and a ``strip()``, so its
      input carries no run; only the tag strip can manufacture one, and that
      change is already counted above.

    Four characters a pass, plus the first pass and the confirming pass that
    sees no change, is ``len(text) // 4 + 2``. Deriving it per call rather than
    from a fixed number is the point: the budget is then provably sufficient
    for the string in hand, with no precondition for anyone to check or
    violate, and a 500-character input gets 127 passes instead of a thousand it
    could never spend.

    The bound used to be a flat 64, taken from the 15 characters a nested
    ``</player_input>`` costs per pass. That was the wrong denominator and wrong
    in the unsafe direction: a chain of labels cost *four*, so
    ``"x " + "NPC:" * 124`` — 498 characters, inside even the engine's
    500-character cap — exhausted the budget and failed closed. Both label
    patterns now collapse such a chain in one pass, leaving the nesting as the
    cheapest amplifier that survives, and four is what the arithmetic is done
    with because four is what is *provable*.
    """
    return min(len(text) // 4 + 2, _MAX_NEUTRALISE_PASSES)


def _apply_once(text: str, strip_inline_labels: bool) -> str:
    """Every rule, once, in the one order that does not re-arm the others.

    Split out so :func:`_neutralise` and :func:`_fail_closed` cannot drift:
    the fail-closed path used to keep its own copy of this sequence, and a
    second copy of an order-sensitive pipeline is how it ended up applying the
    label rules exactly once. See :func:`_neutralise` for why the order is
    what it is.
    """
    # Line-anchored labels first, while the real newlines are still here: the
    # control strip below turns them into spaces, after which ``^`` only ever
    # matches position 0.
    cleaned = _SPEAKER_PREFIX_PATTERN.sub("", text)
    cleaned = _CONTROL_CHAR_PATTERN.sub(" ", cleaned)
    if strip_inline_labels:
        cleaned = _INLINE_SPEAKER_PREFIX_PATTERN.sub("", cleaned)
    # After both label strips and the control strip, so a tag either of them
    # just exposed is seen on this pass rather than the next one.
    cleaned = _PLAYER_INPUT_TAG_PATTERN.sub(" ", cleaned)
    return _WS_RUN_PATTERN.sub(" ", cleaned).strip()


def _digest(text: str) -> str:
    """A short, stable fingerprint of a string, for a log that must not carry it.

    ``surrogatepass`` because a lone surrogate can reach this module inside a
    JSON body, and a diagnostic that raises from the failure path would be
    worse than no diagnostic at all.
    """
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:16]


def _fail_closed(text: str, strip_inline_labels: bool) -> str:
    """Defang a string that would not converge inside the pass bound.

    Deleting every angle bracket is blunt and it is *provably* enough against
    the tag: the tag pattern cannot match without them, and nothing else here
    inserts one. The alternative — returning the half-neutralised string the
    loop gave up on — is the one outcome that must never happen, because a
    half-neutralised string is exactly a live tag in instruction position.

    The rules then run to a fixed point rather than once each. Once was the
    same hole :func:`_neutralise` exists to close, in the branch that is
    supposed to be the safe one: ``re.sub`` resumes past its own replacement,
    so a nesting loses one layer per pass and one call leaves the rest live.
    Chained labels leaked the same way — ``_INLINE_SPEAKER_PREFIX_PATTERN``'s
    lookbehind reads the *input* string, so in ``NPC:NPC:NPC:`` only the first
    label was preceded by whitespace when the scan arrived. Measured, at 70
    nestings and 140 chained labels — 1618 characters, well inside the 4000 the
    route allows — that was 75 live labels out of the ingress call and 10
    surviving both layers. Both label patterns now match a whole run in one go,
    so the chain costs a single substitution; the nesting still needs the loop.

    This loop needs no pass bound. With every ``<`` and ``>`` already gone no
    substitution can build a tag; the control strip replaces with a space and
    so cannot match its own output; and every other rule that changes the
    string deletes from it. So after the first pass any change strictly
    shortens, and the fixed point is reached in at most ``len(text)`` steps.

    ``strip_inline_labels`` is threaded through rather than assumed, because
    running the space-anchored strip to a fixed point on *model* text would
    amplify the one cost :func:`neutralise_model_text` exists to refuse.
    """
    cleaned = _ANGLE_BRACKET_PATTERN.sub(" ", text)
    while True:
        before = cleaned
        cleaned = _apply_once(cleaned, strip_inline_labels)
        if cleaned == before:
            return cleaned


def _neutralise(text, strip_inline_labels: bool) -> str:
    """Apply the rules repeatedly until the string stops changing.

    Running each rule once, in a fixed order, is not enough, because two of
    them can hand work back to a rule that has already run:

    * the speaker-label strip *manufactures tags*. ``"<< NPC: /player_input>"``
      matches no tag pattern until ``NPC: `` is removed from between the
      brackets — and the label strip used to be the last step, so the caller
      got ``"<</player_input>"`` back and the next layer's single tag pass ate
      only the inner one, leaving a live ``"< /player_input>"``;
    * a control character *hides* a tag. ``"</player_input\\x01>"`` is not a
      tag until ``\\x01`` becomes a space, and the control strip used to run
      after the tag pass, so the tag was reassembled behind it.

    Both are the same bug: a fixed pipeline with a state the pipeline can no
    longer see. :func:`_apply_once` puts the control strip before the tag pass
    so the second one cannot happen at all, and the loop covers the first — and
    any variant of it, at any nesting depth, since the exit condition is a full
    pass that changed nothing rather than a pass count someone has to predict.

    ``re.sub`` scanning past its own replacement is what makes depth matter:
    ``"<</player_input>/player_input>"`` has its inner tag replaced and the
    scan resumes beyond it, so the leftover ``<`` pairs up with the trailing
    ``/player_input>`` only on the *next* pass. N nestings need N passes, which
    is why :func:`_fail_closed` loops too rather than applying each rule once.
    The same scan rule used to apply to a chain of labels, at four characters a
    pass instead of fifteen; both label patterns now match the whole run in one
    substitution, and :func:`_pass_budget` records what that cost.
    """
    cleaned = str(text)
    budget = _pass_budget(cleaned)
    for _ in range(budget):
        before = cleaned
        cleaned = _apply_once(cleaned, strip_inline_labels)
        if cleaned == before:
            return cleaned
    # A length and a digest, not the text. This line used to carry ``head=%r``
    # — eighty characters of the string it gave up on, which on the player path
    # is chat content, at ERROR, in whatever operational log the deployment
    # ships. The digest is the whole diagnostic value: it identifies the same
    # payload across the ingress and prompt-assembly layers, across sessions and
    # across both entry points, which is what "is this one attacker or a bug?"
    # actually asks. The characters answer nothing that the length does not.
    logger.error(
        "text_safety: %d passes did not converge — failing closed. "
        "chars=%d sha256=%s",
        budget,
        len(cleaned),
        _digest(cleaned),
    )
    return _fail_closed(cleaned, strip_inline_labels)


def neutralise_player_text(text) -> str:
    """Strip player-authored text of everything that can forge prompt structure.

    Returns ``""`` for None or an empty value. Nothing is rejected and nothing
    is rewritten beyond the structural characters below: this is prompt-assembly
    hardening, not a content filter — the NPC-chat QC pipeline does its own, and
    editing the player's words here would show up in the transcript.

    Removed, to a fixed point (see :func:`_neutralise`):

    1. line-leading ``NPC:`` / ``Jean:`` labels;
    2. C0/DEL control characters and the invisible Unicode families — the
       line/paragraph separators, the zero-width and bidi families and the
       U+E0000 tag block — each replaced by a space;
    3. the same labels again, anchored to a space rather than a line start,
       since by this point the whole string is one history line;
    4. ``<player_input>`` / ``</player_input>`` tags, replaced by a **space**
       rather than removed — deleting them lets an inner tag's neighbours
       rejoin into a fresh outer one (``<player<player_input>_input>``);
    5. whitespace runs, collapsed to a single space, then stripped.
    """
    if not text:
        return ""
    return _neutralise(text, strip_inline_labels=True)


def neutralise_model_text(text) -> str:
    """Strip model-authored text of everything that can forge prompt structure.

    :func:`neutralise_player_text` minus rule 3, the space-anchored speaker
    label. That rule is deliberately over-broad — it cannot distinguish a
    forged ``NPC:`` turn from an NPC addressing Jean by name — and the trade is
    only worth making against text the *player* wrote. Applied to model output
    it deletes authored dialogue for no gain: an NPC line reading "Careful,
    Jean: the bridge is out." reached the player as "Careful, the bridge is
    out." The model is not the attacker here; the player's influence on it is
    laundered through a prompt that already fences their words, and what
    actually guards this path is the tag pass, which stays.

    The line-*leading* label strip stays too. It is anchored to a real line
    start, so it costs authored prose nothing, and it still stops a model that
    opens a line with ``NPC:`` from forging a second turn inside the one line
    the history block gives it.
    """
    if not text:
        return ""
    return _neutralise(text, strip_inline_labels=False)
