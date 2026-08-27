"""Neutralisation of player-authored text before it enters an LLM prompt.

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
"""

import re

# One line-leading ``NPC:`` / ``Jean:`` label. The conversation history block is
# newline-delimited with exactly these two prefixes marking whose turn it is, so
# a player who types one forges a turn that never happened and then answers it.
_SPEAKER_PREFIX_PATTERN = re.compile(r"(?im)^[ \t]*(?:NPC|Jean)[ \t]*:[ \t]*")

# The same label once the text has been collapsed to a single line. Anchored to
# the start of the string *or* to a preceding space, because a U+2028 or a
# control character can push a forged label off a line start where the pattern
# above can no longer see it, and collapsing whitespace then leaves it mid-string
# on the one history line this speaker gets. The cost is that a player writing
# "I asked Jean: why?" loses two characters; the alternative is letting them
# write the NPC's next line.
_INLINE_SPEAKER_PREFIX_PATTERN = re.compile(
    r"(?i)(?:^|(?<=\s))(?:NPC|Jean)\s*:\s*"
)

# The delimiter ``_wrap_player_text`` opens around player text. A literal
# closing tag inside the text would end the block early and put everything after
# it back in instruction position. Whitespace is tolerated on both sides of the
# slash: a model reads ``< / player_input >`` as the same tag, and both previous
# copies of this pattern allowed it only after the slash.
_PLAYER_INPUT_TAG_PATTERN = re.compile(r"<\s*/?\s*player_input\s*>", re.IGNORECASE)

# C0 controls and DEL, plus the two Unicode line/paragraph separators. ``str``
# whitespace splitting knows about U+2028/2029 in some contexts and not others,
# and a bare ``\x08`` is nobody's idea of player input.
_CONTROL_CHAR_PATTERN = re.compile("[\x00-\x1f\x7f\u2028\u2029]+")

_WS_RUN_PATTERN = re.compile(r"\s+")


def _strip_speaker_labels(text: str, pattern=_SPEAKER_PREFIX_PATTERN) -> str:
    """Remove speaker labels matching ``pattern`` until none is left.

    Looped on purpose: a single pass over ``"NPC: NPC: hello"`` removes only the
    outer label and leaves the forged one behind, which is precisely the input
    someone probing this would try second. Substituting once is not idempotent;
    substituting to a fixed point is.
    """
    while True:
        stripped = pattern.sub("", text)
        if stripped == text:
            return text
        text = stripped


def neutralise_player_text(text) -> str:
    """Strip a string of everything that can forge prompt structure.

    Returns ``""`` for None or an empty value. Nothing is rejected and nothing
    is rewritten beyond the structural characters below: this is prompt-assembly
    hardening, not a content filter — the NPC-chat QC pipeline does its own, and
    editing the player's words here would show up in the transcript.

    Removed, in order:

    1. line-leading ``NPC:`` / ``Jean:`` labels (to a fixed point, see above);
    2. ``<player_input>`` / ``</player_input>`` tags, replaced by a **space**
       rather than removed — deleting them lets an inner tag's neighbours
       rejoin into a fresh outer one (``<player<player_input>_input>``);
    3. C0/DEL control characters and U+2028/2029, replaced by a space;
    4. whitespace runs, collapsed to a single space, then stripped.

    Step 1 then runs again over the collapsed single line, anchored to a space
    rather than a line start: by that point the whole string is one history line,
    and a label a separator had pushed off a line start would otherwise survive
    in the middle of it.
    """
    if not text:
        return ""
    cleaned = _strip_speaker_labels(str(text))
    cleaned = _PLAYER_INPUT_TAG_PATTERN.sub(" ", cleaned)
    cleaned = _CONTROL_CHAR_PATTERN.sub(" ", cleaned)
    cleaned = _WS_RUN_PATTERN.sub(" ", cleaned).strip()
    return _strip_speaker_labels(cleaned, _INLINE_SPEAKER_PREFIX_PATTERN).strip()
