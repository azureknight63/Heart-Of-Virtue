"""Player-facing journal: standing objectives plus a transcript of scripted scenes.

The journal answers the two questions a text game leaves a returning player with:
*what am I supposed to be doing* and *what did that scene actually say*. Both were
previously unanswerable — objectives existed only as prose inside a modal the
player had already dismissed, and ``useEventManager`` discarded its event history
the moment the queue drained (issue #538, item 4).

State lives on :class:`~src.universe.Universe` and therefore rides along in the
save pickle for free; nothing here needs its own serializer. Because old saves
predate the attribute, ``Universe.journal`` is a lazily-created property rather
than an ``__init__`` assignment — see that class.

Story code sets objectives through the module-level helpers, which take the
player explicitly in the same style as the existing ``universe.story`` gate
lookups. The key is always one of the ``OBJ_*`` constants below, never a bare
string — see their comment for why, and
``test_no_objective_key_is_written_as_a_bare_string`` for the guard::

    set_objective(self.player, OBJ_CH03_FERRY_LANDING, "Meet Mara at the landing.")
    ...
    complete_objective(self.player, OBJ_CH03_FERRY_LANDING)

Deliberately NOT routed through :mod:`src.narration`: narration is a display
channel, drained only inside a ``capture_narration`` context, so an objective
emitted that way would be silently lost on any path that does not wrap the call
in one — every direct ``game_service`` call in the test suite, for a start.
Objectives are game state, so they are written to game state directly.
"""

from typing import Any, Dict, List, Optional

#: Scenes retained in the transcript. A playthrough has far fewer scripted
#: scenes than this, so the cap is a ceiling against pathological sessions
#: (and against a repeatable event looping) rather than a routine trim — but it
#: is enforced on every append, because the log is inside the save pickle.
LOG_CAP = 300

#: Total transcript characters retained, enforced alongside :data:`LOG_CAP`.
#:
#: The entry cap alone bounds the wrong quantity: a scene is a list of prose
#: lines with no length limit, so 300 of them is unbounded in bytes — and this
#: structure is pickled into the save, which ``secure_pickle`` refuses to load
#: past its own size ceiling. A transcript that grew until the save would not
#: load is a worse failure than a transcript that forgets its oldest scene.
LOG_CHAR_CAP = 150_000

#: Fallback scene title. Owned here rather than at the call site so there is one
#: answer to "what is a scene with no room called".
DEFAULT_SCENE_TITLE = "Story"

STATUS_ACTIVE = "active"
STATUS_DONE = "done"

# --- objective keys ---------------------------------------------------------
#
# Declared here, not spelled at each call site, because an objective's set and
# complete calls routinely live in DIFFERENT chapter modules (``ch01_follow_gorran``
# is set in ch01 and closed in ch02; ``ch02_head_east`` and ``ch02_find_mara``
# are set in ch02 and closed in ch03) and :meth:`Journal.complete_objective`
# ignores an unknown key by design. A typo is therefore silent, and its symptom
# is an objective that stays on the player's list forever. Names, unlike
# strings, are checked at import time.
#
# These constants are also the roster itself:
# ``tests/test_journal_story_integration.py`` enumerates this module's
# ``OBJ_``-prefixed names (via ``vars()``) and asserts the story sets and
# completes exactly that set — so a constant declared here and never used, or
# used and never declared, fails there. Keep the prefix on any new one or it
# drops out of that scan silently.

OBJ_CH01_ESCAPE_GROTTO = "ch01_escape_grotto"
OBJ_CH01_FOLLOW_GORRAN = "ch01_follow_gorran"

OBJ_CH02_EXPLORE_GRONDIA = "ch02_explore_grondia"
OBJ_CH02_KING_SLIME = "ch02_king_slime"
OBJ_CH02_VOTHA_KRR = "ch02_votha_krr"
OBJ_CH02_HEAD_EAST = "ch02_head_east"
OBJ_CH02_FIND_MARA = "ch02_find_mara"

OBJ_CH03_CANVASS_CAMP = "ch03_canvass_camp"
OBJ_CH03_WALK_THE_CAMP = "ch03_walk_the_camp"
OBJ_CH03_FERRY_LANDING = "ch03_ferry_landing"


class Journal:
    """Objectives and scene transcript for a single playthrough.

    Both collections are plain dicts/lists of primitives on purpose: they are
    pickled with the player, and a bare data shape survives refactoring of this
    module in a way that pickled instances of a richer class would not.
    """

    def __init__(self):
        #: ``key -> {"key", "text", "status", "chapter", "tick"}``, insertion
        #: ordered. A completed objective is kept (status ``"done"``) rather
        #: than deleted, so the journal can show what was accomplished.
        self.objectives: Dict[str, Dict[str, Any]] = {}
        #: Newest-last list of ``{"title", "lines", "tick"}`` scene records.
        self.log: List[Dict[str, Any]] = []

    # --- objectives ---------------------------------------------------------

    def set_objective(self, key, text, chapter=None, tick=0):
        """Add or update the objective stored under ``key``.

        Re-setting an existing key rewrites its text and reactivates it while
        keeping its position in the list — an objective that is re-issued (a
        gate re-opened, a deadline moved) belongs where the player last saw it,
        not at the bottom.
        """
        if not key or not (text or "").strip():
            return None
        existing = self.objectives.get(key)
        entry = {
            "key": key,
            "text": text.strip(),
            "status": STATUS_ACTIVE,
            "chapter": chapter if chapter is not None else (existing or {}).get("chapter"),
            "tick": (existing or {}).get("tick", tick),
        }
        self.objectives[key] = entry
        return entry

    def complete_objective(self, key):
        """Mark ``key`` done. Unknown keys are ignored, not an error.

        Silent on a miss because objective keys are authored in story files and
        cleared from event handlers that may run in an order the author did not
        anticipate (a gate skipped, a scene replayed after a load). Raising here
        would turn a narrative bookkeeping slip into a crashed game loop.
        """
        entry = self.objectives.get(key)
        if entry is None:
            return None
        entry["status"] = STATUS_DONE
        return entry

    def active_objectives(self):
        """Active objectives in insertion order."""
        return [o for o in self.objectives.values() if o.get("status") == STATUS_ACTIVE]

    def completed_objectives(self):
        """Completed objectives in insertion order."""
        return [o for o in self.objectives.values() if o.get("status") == STATUS_DONE]

    # --- transcript ---------------------------------------------------------

    def record_scene(self, title, lines, tick=0):
        """Append one scene to the transcript, then trim it (see :meth:`_trim`,
        which enforces both :data:`LOG_CAP` and :data:`LOG_CHAR_CAP`).

        ``lines`` is a list of ``{"speaker": str|None, "text": str}`` so the
        transcript keeps the attribution the staged conversation showed;
        speaker-less entries are narration. Empty scenes are dropped rather
        than recorded as blank rows.

        A scene identical to the one before it is not recorded twice: this runs
        on the per-beat combat path too, where a repeatable event re-emitting
        the same prose would otherwise file one copy per beat and evict real
        story scenes.
        """
        kept = [
            {"speaker": ln.get("speaker") or None, "text": (ln.get("text") or "").strip()}
            for ln in (lines or [])
            if (ln.get("text") or "").strip()
        ]
        if not kept:
            return None
        entry = {"title": title or DEFAULT_SCENE_TITLE, "lines": kept, "tick": tick}
        if self.log and self.log[-1]["title"] == entry["title"] and self.log[-1]["lines"] == kept:
            return None
        self.log.append(entry)
        self._trim()
        return entry

    def _trim(self):
        """Enforce both caps, oldest-first. See :data:`LOG_CHAR_CAP`."""
        if len(self.log) > LOG_CAP:
            del self.log[: len(self.log) - LOG_CAP]
        total = sum(_scene_chars(entry) for entry in self.log)
        while len(self.log) > 1 and total > LOG_CHAR_CAP:
            total -= _scene_chars(self.log[0])
            del self.log[0]

    def to_dict(self):
        """Serialize for the API. Objectives are split by status so the client
        renders two sections without re-deriving the split."""
        return {
            "objectives": list(self.active_objectives()),
            "completed": list(self.completed_objectives()),
            "log": list(self.log),
        }


def _scene_chars(entry) -> int:
    """Characters a recorded scene contributes to the transcript budget."""
    return sum(len(line.get("text") or "") for line in entry.get("lines", ()))


def existing_journal(player) -> Optional[Journal]:
    """Return ``player``'s journal WITHOUT creating one.

    The read path's accessor. ``Universe.journal`` is a lazy property, so
    merely reading it attaches a fresh ``Journal`` that then rides into the next
    save — which would make ``GET /api/journal`` a writer. Callers that only
    want to display what exists use this; callers that are about to write use
    :func:`journal_for`.
    """
    universe = getattr(player, "universe", None)
    if universe is None:
        return None
    return universe.__dict__.get("_journal")


def journal_for(player) -> Optional[Journal]:
    """Return ``player``'s journal, or ``None`` when there is no universe.

    Every helper below funnels through this, so a player detached from a
    universe (unit-test doubles, a half-built session) degrades to a no-op
    instead of raising inside a story event.
    """
    universe = getattr(player, "universe", None)
    if universe is None:
        return None
    return getattr(universe, "journal", None)


def set_objective(player, key, text, chapter=None):
    """Set an objective on ``player``'s journal. No-op without a universe."""
    journal = journal_for(player)
    if journal is None:
        return None
    tick = getattr(getattr(player, "universe", None), "game_tick", 0) or 0
    return journal.set_objective(key, text, chapter=chapter, tick=tick)


def complete_objective(player, key):
    """Mark an objective done on ``player``'s journal. No-op without a universe."""
    journal = journal_for(player)
    if journal is None:
        return None
    return journal.complete_objective(key)
