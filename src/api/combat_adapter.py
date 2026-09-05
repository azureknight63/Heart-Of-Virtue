"""
API Combat Adapter

This module adapts the existing terminal-based combat system for API use.
It captures output, manages state between API calls, and processes commands
without blocking for user input.
"""

import contextlib
import uuid
import threading
import logging
import re
import random
from datetime import datetime
from types import SimpleNamespace
from typing import Dict, Any, List, Optional, TYPE_CHECKING

import src.positions as positions  # type: ignore
import src.moves as moves  # type: ignore
from src.api.serializers.combat import (
    CombatStateSerializer,
    CombatantSerializer,
)
from src.api.constants import ITEM_USE_RANGE, ALLY_HEAL_THRESHOLD
from src.api.schemas.combat_beat import (
    DEFAULT_ANIMATION,
    DEFAULT_DAMAGE_ANIMATION,
    SUGGESTIONS_EVENT,
)
from src.api.combat_beat_stream import CombatBeatStreamer
from ai.combat_strategist import CombatStrategist
from src.combatant import (
    OUTCOME_KEY,
    OUTCOME_TARGET_KEY,
    PENDING_ANIMATION_ATTR,
    REPORTED_BEAT_KEY,
)
from src.moves._base import select_weighted_target, display_name_of
from src.events import purge_orphaned_combat_events
from src.story import gorran_flavor

if TYPE_CHECKING:
    from src.player import Player

#: Reach, in feet, above which a move earns a drawn range ring in the client.
#: Every melee swing reaches about 5 ft, so a ring at that distance is drawn on
#: essentially every move and tells the player nothing; only a move that
#: genuinely outreaches a sword (spear, polearm, bow) gets one.
MELEE_REACH_FT = 6

# Compiled once at module level for performance
_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\_-]|\[[0-?]*[ -/]*[@-~])")

# Shortest prep stage that earns an abort affordance. Below this a move is over
# before a player could react to anything, and offering a bail-out would only add
# a decision to every swing. Above it the commitment is long enough that the
# battlefield can change while you are still winding up: ShootBow (10),
# ShootCrossbow / BroadheadBolt / PinningBolt (15), AimedShot (25),
# BloodOfMartyrs (40).
ABORTABLE_MIN_PREP_BEATS = 8

logger = logging.getLogger(__name__)


def _strip_combatant_prefix(target_id: str) -> str:
    """Strip 'enemy_' or 'ally_' prefix and return the raw Python id string."""
    for prefix in ("enemy_", "ally_"):
        if target_id.startswith(prefix):
            return target_id[len(prefix):]
    return target_id


#: ── The ``_pending_animation`` lifecycle, in one place ──────────────────────
#:
#: ``entity._pending_animation`` (``PENDING_ANIMATION_ATTR``) is the
#: per-combatant animation channel: a dict created at cast time and mutated as
#: the move resolves. Every writer and both deletion points are listed here --
#: the sites themselves point back at this block instead of restating fragments
#: of it.
#:
#: The attribute name and the key names below are NOT spelled as literals in
#: this module: they are minted once in ``src/combatant.py`` and imported above,
#: because the channel is written on one side of the engine/API boundary and
#: read on the other. A bare literal that drifts on one side fails silently --
#: the channel simply stops resolving.
#:
#: Keys:
#:   type, source_id, target_id,      -- the wire payload, built once at cast
#:   move_name, move_display_name        by ``_build_animation_data``
#:   outcome                          -- the engine-published resolution now
#:   (OUTCOME_KEY)                       awaiting emission (None = nothing armed)
#:   outcome_target                   -- the combatant OBJECT that resolution
#:   (OUTCOME_TARGET_KEY)                happened to; mapped to a stream id and
#:                                       stripped by ``_wire_animation``
#:   _reported_beat                   -- bookkeeping marking that this channel
#:   (REPORTED_BEAT_KEY)                 has published at least one resolution.
#:                                       Only its PRESENCE is read --
#:                                       ``_flush_pending_animations`` uses it to
#:                                       tell "never resolved" (emit the fallback
#:                                       animation) from "already shown" (drop
#:                                       silently). The stored value, the beat
#:                                       the latest resolution happened in, is
#:                                       diagnostic only: nothing branches on it,
#:                                       but it names the beat when a pending
#:                                       dict is inspected in a debugger or a
#:                                       bug report.
#:   seq                              -- stamped by ``_emit_animation_log`` on
#:                                       the emitted COPY only, never on the
#:                                       channel itself
#:
#: Writers:
#:   * the player cast site (``_execute_move_inner``) and the NPC cast site
#:     (``_process_npc``) -- create the dict via ``_build_animation_data``
#:   * ``src.moves._base.publish_outcome`` -- stamps ``outcome`` +
#:     ``outcome_target`` immediately before the narrating line
#:   * ``_take_resolution`` -- snapshots one resolution off the dict, records
#:     ``_reported_beat`` and re-arms ``outcome``/``outcome_target`` to None
#:
#: Deletion points (exactly three):
#:   * ``_flush_pending_animations`` -- end of each player move (and after the
#:     initial NPC turns): retires every channel whose move ran to completion,
#:     emitting a fallback only if the channel never resolved
#:   * ``_detach_current_move`` -- a move CANCELLED mid-wind-up (abort, event
#:     interrupt, roster emptied under it): clears ``current_move`` and
#:     discards that entity's channel as one operation. Never a fallback
#:     emission -- the cancelled swing never happened, so emitting its
#:     animation would play a phantom swing
#:   * ``_discard_pending_animations`` -- combat teardown
#:     (``_teardown_combat_roster``): drops every channel unconditionally as
#:     post-fight reference hygiene (a pending dict can hold a live
#:     ``outcome_target`` nothing will ever consume)
#:
#: Pickle safety is NOT what the deletions provide: ``Combatant.__getstate__``
#: (extended by ``Player.__getstate__``) strips ``_pending_animation`` at
#: pickle time, so a channel that survives to a save is never serialized.
#: The teardown discard is defense-in-depth on top of that guard.

#: How much of ``player.combat_log`` survives a trim, per kind of entry.
#:
#: The log is the player's RECAP, not the load-bearing combat UI -- the
#: battlefield is where a fight is read -- but it is also returned in full on
#: every client poll and pickled into every save under a 5 MB cap, and it was
#: never trimmed at all. Per-target resolutions made that worse: one arc now
#: appends one animation carrier per enemy it reaches instead of one per swing.
#:
#: The two kinds are capped separately because they are consumed completely
#: differently. Animation carriers (``type == "animation"``) are drained by the
#: battlefield within a poll or two of being written and are filtered out of
#: the visible log by CombatLog, so almost their whole population is dead
#: weight; their budget exists only for reload-recovery replay, and 96 still
#: covers ~20 multi-target swings of that (at one carrier per landing) against
#: a sub-second consume latency -- 400 was two hundred swings of backlog
#: nothing ever read. Visible entries are what the player scrolls back
#: through, so they keep their own 400-line budget (far more recap than any
#: fight's readable history) and are never sacrificed to make room for
#: carriers. The recap is untouched by this cap.
#:
#: Together they bound the pickled log at ~500 entries, and the trim only runs
#: once the log has overshot by ``COMBAT_LOG_TRIM_SLACK``, so rebuilding the
#: dedup key index afterwards is amortized over that many inserts rather than
#: paid on each one.
MAX_ANIMATION_LOG_ENTRIES = 96
MAX_VISIBLE_LOG_ENTRIES = 400
COMBAT_LOG_TRIM_SLACK = 100

#: Sanity ceiling for the per-fight animation carrier sequence restored from a
#: save. The seq is only client-side carrier identity, so the bound needs no
#: precision — it just has to dwarf any real fight (a marathon at one carrier
#: per beat-target for hours stays far below it) while rejecting the absurd
#: values a crafted save could plant. Out-of-range restarts the sequence at 0;
#: see _next_animation_seq.
MAX_ANIMATION_SEQ = 1_000_000


def _dedup_key(message, round_num, source_id):
    """The identity ``_add_log_entry`` collapses duplicate log entries on.

    Message and round alone are not enough: two distinct combatants using
    identically-named moves in the same beat would collide, and the second
    entry's animation would be dropped from the log the client reads.
    """
    return (message, round_num, source_id)


#: The documented wire payload of a pending animation -- the key set
#: ``_build_animation_data`` creates plus the ``outcome`` that
#: ``publish_outcome`` stamps. ``_wire_animation`` copies exactly these, so a
#: crafted key smuggled onto a restored pending dict never ships.
_WIRE_ANIMATION_KEYS = (
    "type",
    "source_id",
    "target_id",
    "move_name",
    "move_display_name",
    OUTCOME_KEY,
)


def _wire_animation(pending: dict) -> dict:
    """The client-safe copy of a pending animation.

    Built as an ALLOW-list over ``_WIRE_ANIMATION_KEYS`` rather than by
    stripping known-bad keys from a full copy: the pending dict rides in the
    pickled save, so a crafted save can stamp arbitrary extra keys onto it,
    and a deny-list would ship every one of them verbatim into the combat log
    the client reads. (The deny-list era had to enumerate ``REPORTED_BEAT_KEY``,
    its pre-rename ``"_reported"`` spelling, and ``outcome_target`` one by one
    -- and anything it forgot leaked.)

    ``publish_outcome`` stores the resolved combatant *object* under
    ``outcome_target`` so the adapter can name it; it is mapped to a stream id
    here and never copied. The combat log is jsonified on every poll and
    pickled into every save, so a live combatant in the copy is a 500 and a
    save that drags the enemy's object graph with it.

    Every path that emits an animation goes through this -- both the
    per-resolution path and the end-of-move fallback. They built the payload
    two different ways before, and only one of them sanitized.
    """
    animation = {k: pending[k] for k in _WIRE_ANIMATION_KEYS if k in pending}
    target = pending.get(OUTCOME_TARGET_KEY)
    if target is not None:
        animation["target_id"] = CombatantSerializer.stream_id(target)
    return animation


def _take_resolution(pending: dict, beat: Optional[int] = None) -> dict:
    """Snapshot one published resolution off a pending animation and re-arm it.

    The engine publishes an outcome per *target*, not per swing, so a pending
    animation can be resolved several times before the move ends. Each call
    returns the animation to emit for the resolution now on ``pending`` and
    clears the outcome so the next narration line can't re-fire it; ``pending``
    itself is deliberately left in place so a later resolution -- in this beat
    or in a later one -- still has somewhere to publish to.

    **Every resolution carries the move's own animation, in full.** An arc that
    catches four enemies emits the arc four times, once per ``target_id``, and
    the client plays them concurrently, layered with their SFX, rather than
    end to end. This used to downgrade every landing after the first to a short
    ``impact`` flash -- a workaround for sequential client playback that cost
    the later targets their real animation. Removing that downgrade (emitting
    the full animation for every resolution) is the whole of the multi-target
    fix; recording ``beat`` under ``REPORTED_BEAT_KEY`` is separate
    bookkeeping for the end-of-move fallback, whose presence-only contract is
    documented in the lifecycle block at the top of this module.
    """
    animation = _wire_animation(pending)
    pending[REPORTED_BEAT_KEY] = beat
    pending[OUTCOME_KEY] = None
    pending[OUTCOME_TARGET_KEY] = None
    return animation


class CombatOutputCapture:
    """Captures print statements and stores them in a combat log."""

    def __init__(self, player=None):
        self.log_entries = []
        self.current_round = 1
        self.player = player  # Reference to player for animation tracking
        # Set by the adapter around each entity's advance() call so write() knows
        # exactly which combatant's pending animation to match against impact text.
        self.active_entity = None

    def write(self, text):
        """Capture text output."""
        if text and text.strip():
            # Clean ANSI codes
            clean_text = _ANSI_ESCAPE.sub("", text).strip()

            if clean_text:
                # Skip technical debug lines and animation errors
                if (
                    clean_text.startswith("DEBUG:")
                    or "Animation not found" in clean_text
                ):
                    return

                trigger_anim_data = None
                # Read the outcome the ENGINE published; never infer it from the
                # prose. Move.hit()/miss()/parry() stamp the resolved outcome
                # onto the acting entity's pending animation immediately before
                # they narrate (see src/moves/_base.publish_outcome), so by the
                # time the impact line reaches us the fact is already there.
                #
                # This used to string-match the narration ("struck" + "damage" ->
                # hit, "parried" -> parry, "missed" -> miss). A glancing blow
                # narrates "just barely hit ... for N damage!" and matched none
                # of them, so ~10% of all landed hits played no animation and no
                # sound at all; a fully absorbed blow ("struck X but did no
                # damage!") matched the *hit* branch and played the flesh-impact
                # cue for zero damage. Prose is not a wire protocol -- do not
                # reintroduce a text branch here.
                #
                # Only the entity whose move is currently advancing is consulted,
                # so an outcome is never misattributed to a different combatant
                # that also has an animation pending in the same beat.
                entity = (
                    self.active_entity
                    if self.active_entity is not None
                    else self.player
                )
                if entity is not None:
                    pending = getattr(entity, PENDING_ANIMATION_ATTR, None)
                    if isinstance(pending, dict) and pending.get(OUTCOME_KEY):
                        # combat_beat is the shared per-beat counter and lives
                        # on the player, so it dates the resolution the same way
                        # for an NPC's swing as for Jean's.
                        trigger_anim_data = _take_resolution(
                            pending, getattr(self.player, "combat_beat", None)
                        )

                entry = {
                    "round": self.current_round,
                    "message": clean_text,
                    "type": "combat",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                }
                if trigger_anim_data:
                    entry["trigger_animation"] = True
                    entry["animation_data"] = trigger_anim_data

                self.log_entries.append(entry)

    def flush(self):
        """Required for file-like object."""
        pass

    def get_log(self):
        """Get all captured log entries."""
        return self.log_entries

    def clear(self):
        """Clear the log."""
        self.log_entries = []


class ApiCombatAdapter:
    """
    Adapts the terminal combat system for API use.

    This class manages combat state between API calls and processes
    player commands without blocking for input.
    """

    # Class-level defaults for the dedup-index cache and the per-beat trim
    # counter, so an adapter built without __init__ (tests construct bare
    # instances via __new__ throughout the suite) still reads coherent state.
    # _reset_log_index_state is the one shared definition of this baseline;
    # keep these four values in lockstep with it.
    _log_keys = None
    _log_key_source = None
    _log_key_count = None
    _log_trimmed_since_beat = 0

    def _reset_log_index_state(self):
        """The single definition of the dedup-index/trim-counter baseline.

        Mirrored by the class-level defaults above so bare ``__new__``
        instances read the same state without running __init__.
        """
        # Dedup key index for player.combat_log — rebuilt lazily whenever the
        # list is rebound or mutated behind this adapter's back (see
        # _log_key_index). _log_key_source/_log_key_count bind the cached key
        # set to the exact list object and its length.
        self._log_keys = None
        self._log_key_source = None
        self._log_key_count = None
        # Entries the in-place front-trim dropped since the current beat's log
        # window opened; _execute_move_inner resets it per beat and corrects
        # the beat's window start by it.
        self._log_trimmed_since_beat = 0

    def __init__(
        self,
        player: "Player",
        session_id: str = None,
        on_event_callback: callable = None,
    ):
        self.player = player
        self.session_id = session_id
        self.on_event_callback = on_event_callback
        self.output_capture = CombatOutputCapture(player)
        self.current_beat_state_index = (
            0  # Track which beat state we're currently building
        )
        self.strategist = CombatStrategist()

        # Engine-driven beat streaming (issue #436). Created per combat by
        # _maybe_init_streamer when COMBAT_SOCKET_STREAMING is on; None otherwise.
        self._beat_streamer = None
        # Per-move {stream_id: reason} for combatants removed from the roster, so
        # streaming can tell a death from an alive-exit (flee/warp/scripted).
        self._departures = {}
        # Prevent concurrent status polls or duplicate cleanup paths from
        # emitting the terminal SocketIO event more than once per combat.
        self._terminal_event_emitted = False
        # The combatants whose arrival has already been announced in the
        # current fight. Holds the objects themselves, not their id()s: a
        # combatant that dies mid-fight can be freed and a later reinforcement
        # allocated at the same address, which would silently swallow that
        # reinforcement's announcement. Per-fight, in-memory only (object
        # identity does not survive a save), reset with combat_id in
        # initialize_combat.
        self._announced_enemies = set()

        # True while _execute_move_inner is driving a beat loop. A reinit that
        # arrives from inside a beat (an enemy move or a combat event that
        # calls functions.add_enemies_to_combat) must not resume the player's
        # in-flight move a second time — see initialize_combat.
        self._executing_move = False

        self._reset_log_index_state()

        # combat_log rides in the pickled save, so a tampered or legacy save
        # can hand this adapter anything at all — a non-list log (a str would
        # be iterated char by char, raising in _log_key_index on every
        # insert), a log with non-dict entries (which would raise from inside
        # the narration listener on every insert — the dedup key reads .get on
        # each entry — again in the trim, and again in move_logs), or a dict
        # entry whose "animation" value is not a dict (the index rebuild calls
        # .get on it per entry). Sanitize ONCE here at attach; everything
        # downstream may then assume a list of dicts with dict-or-absent
        # animations. In place, so held references survive.
        log = getattr(self.player, "combat_log", None)
        if log is not None and not isinstance(log, list):
            self.player.combat_log = []
        elif isinstance(log, list):
            if any(not isinstance(entry, dict) for entry in log):
                log[:] = [entry for entry in log if isinstance(entry, dict)]
            for entry in log:
                animation = entry.get("animation")
                if animation is not None and not isinstance(animation, dict):
                    del entry["animation"]

        # Initialize persistent state if missing; the properties below read
        # these keys back through .get with the same defaults.
        state = self._adapter_state()
        state.setdefault("awaiting_input", False)
        state.setdefault("input_type", None)
        state.setdefault("pending_move_index", None)
        state.setdefault("available_options", [])

        # Track async suggestion loading state
        self.player.suggestions_loading = False
        self._suggestion_thread = None
        self._suggestion_generation = (
            0  # Generation counter for race condition prevention
        )
        self._suggestion_lock = (
            threading.Lock()
        )  # Guards generation counter and result writes

        # Suppress terminal animations in API mode.
        try:
            import src.animations as _animations

            _animations.set_api_mode(True)
        except Exception:
            pass

    def _maybe_init_streamer(self, initial_state):
        """Create a beat streamer when COMBAT_SOCKET_STREAMING is on (#436).

        Captures the socketio instance up front so later emits (including from
        the async suggestion thread) never touch current_app off-request.
        """
        self._beat_streamer = None
        if not self.session_id:
            return
        try:
            from flask import current_app

            if not current_app.config.get("COMBAT_SOCKET_STREAMING"):
                return
            socketio = getattr(current_app, "socketio", None)
            if socketio is None:
                return
            self._beat_streamer = CombatBeatStreamer(
                socketio,
                f"combat_{self.session_id}",
                initial_combatants=(
                    (initial_state or {}).get("battle_state") or {}
                ).get("combatants", []),
            )
            self._departures = {}
            self._terminal_event_emitted = False
        except Exception:
            logger.exception("failed to init combat beat streamer")
            self._beat_streamer = None

    def _ensure_streamer(self):
        """Attach the beat streamer after a late session id becomes available.

        Some API paths create/reuse an adapter before the request session id is
        attached. The legacy ``combat:log`` and ``combat:turn`` emitters use the
        later id, but the beat streamer used to remain permanently disabled.
        Reconcile that late binding at the first safe request boundary.
        """
        if self._beat_streamer is not None or not self.session_id:
            return
        self._maybe_init_streamer(self.get_combat_state())

    def _record_departure(self, combatant, reason):
        """Note why a combatant left the roster this move (issue #436).

        Keyed by ``CombatantSerializer.stream_id`` — the single source of the
        wire-id scheme — so the streamer and the serializer can never drift.
        """
        try:
            self._departures[CombatantSerializer.stream_id(combatant)] = reason
        except Exception:
            logger.exception("failed to record combat departure")

    def _stream_combat_result(self, result, beat_states, ended=False):
        """Stream this move's beats + terminal event when streaming is on (#436).

        No-op unless a streamer exists (flag off / no socket). Never raises —
        streaming must not break combat resolution.
        """
        streamer = self._beat_streamer
        # Consume-and-clear this move's departure reasons regardless of path.
        departures = self._departures
        self._departures = {}
        if streamer is None:
            return
        # Mark the response as carried by the socket. This is the ONLY funnel
        # that streams, so a response without this flag reached the client with
        # nothing on the socket behind it, and the HTTP body is its only
        # carrier. The client keys its "apply or defer" decision on this rather
        # than on the action name, because the same action goes both ways:
        # a target selection that completes a move streams beats, while one
        # that only opens a further prompt (a number/direction step) does not.
        if isinstance(result, dict):
            result["response_streamed"] = True
        try:
            streamer.stream_beats(beat_states)
            # Surface any exit/change the per-snapshot stream missed (e.g. an
            # enemy removed on death without an intervening beat_state), using the
            # recorded reason so an alive-exit is never rendered as a death.
            streamer.reconcile_final(
                ((result or {}).get("battle_state") or {}).get("combatants", []),
                departures,
            )
            end_state = (result or {}).get("end_state")
            if ended or end_state:
                if getattr(self, "_terminal_event_emitted", False):
                    return
                self._terminal_event_emitted = True
                # Stream the full result, not just the bare end_state: the
                # client's applyCombatState() falls back to a synthesized
                # shape with log hardcoded to [] when battle_state/log are
                # absent, which was wiping the killing-blow's log entry and
                # letting the victory dialog's "no pending logs" gate pass
                # before the death animation ever played.
                streamer.emit_ended(result)
            else:
                streamer.emit_resolved(result)
        except Exception:
            logger.exception("combat beat streaming failed")

    def _adapter_state(self) -> dict:
        """``player.combat_adapter_state``, created empty when missing.

        The single home of the lazy init that five sites used to carry as
        their own ``if not hasattr(...)`` copy. The dict lives on the player
        (not on ``self``) because the adapter object is not the fight's
        lifetime — see the ``combat_id`` property.
        """
        state = getattr(self.player, "combat_adapter_state", None)
        if not isinstance(state, dict):
            state = self.player.combat_adapter_state = {}
        return state

    @property
    def combat_id(self):
        """Stable identity for the current fight.

        Stored on the player rather than on `self` because the adapter object
        is not the fight's lifetime. `GameService.get_combat_status`'s
        deferred-level-up resume constructs a replacement ApiCombatAdapter
        immediately after `_initialize_combat` minted the id; an instance
        attribute would be discarded there and every poll for the rest of that
        fight would publish `combat_id: None`.
        """
        return self.player.combat_adapter_state.get("combat_id", None)

    @combat_id.setter
    def combat_id(self, value):
        self.player.combat_adapter_state["combat_id"] = value

    @property
    def combat_grid_size(self):
        """Arena dimensions for the current fight, as (width, height).

        On player state for the same reason as combat_id: the adapter object is
        not the fight's lifetime. get_combat_status's deferred-level-up resume
        builds a replacement adapter mid-fight, and an instance attribute would
        silently revert to the legacy 13x13 default there — while
        get_dynamic_grid_size actually returns 9 for a two-combatant fight and
        18 for five, never 13. Since map_size is now published to the client
        (it used to be dropped by transformCombatData's whitelist, so the grid
        always fell back to deriving the arena from positions), a stale 13 is
        no longer harmless: at 18 wide, any combatant past index 12 renders
        outside Battlefield's overflow:hidden container — an invisible enemy in
        an active fight.
        """
        return self.player.combat_adapter_state.get("combat_grid_size", (13, 13))

    @combat_grid_size.setter
    def combat_grid_size(self, value):
        self.player.combat_adapter_state["combat_grid_size"] = value

    @property
    def awaiting_input(self):
        return self.player.combat_adapter_state.get("awaiting_input", False)

    @awaiting_input.setter
    def awaiting_input(self, value):
        self.player.combat_adapter_state["awaiting_input"] = value

    @property
    def input_type(self):
        return self.player.combat_adapter_state.get("input_type", None)

    @input_type.setter
    def input_type(self, value):
        self.player.combat_adapter_state["input_type"] = value

    @property
    def pending_move_index(self):
        return self.player.combat_adapter_state.get("pending_move_index", None)

    @pending_move_index.setter
    def pending_move_index(self, value):
        self.player.combat_adapter_state["pending_move_index"] = value

    @property
    def available_options(self):
        return self.player.combat_adapter_state.get("available_options", [])

    @available_options.setter
    def available_options(self, value):
        self.player.combat_adapter_state["available_options"] = value

    @staticmethod
    def _log_entry_key(entry):
        """The dedup identity of an already-stored log entry.

        Same spelling as the key ``_add_log_entry`` builds for the entry it is
        about to insert -- deliberately one function, because an index keyed one
        way and probed another silently swallows real entries.
        """
        return _dedup_key(
            entry.get("message"),
            entry.get("round"),
            (entry.get("animation") or {}).get("source_id"),
        )

    def _invalidate_log_key_index(self):
        """Force ``_log_key_index`` to rebuild on its next call.

        Named rather than a magic ``_log_key_count = None`` at the call site:
        the None is not data, it is the invalidation signal the length check
        can never match.
        """
        self._log_key_count = None

    def _log_key_index(self):
        """The dedup key index for ``player.combat_log``, rebuilt when stale.

        Also the single home of the lazy ``combat_log`` init: every insert path
        runs through here before touching the list.

        ``combat_log`` lives on the pickled *player*, so it outlives this
        adapter and is replaced outright by ``initialize_combat`` (and by
        loading a save). The index is therefore bound to the exact list object
        and its length. That detects a rebinding and any mutation that changes
        the length; a same-length in-place rewrite by a third party would slip
        past it, but no such writer runs while an adapter is attached -- the
        adapter's own trim (the one length-preserving-ish rewriter) explicitly
        invalidates via ``_invalidate_log_key_index``, and the only other
        in-place rewriter, ``GameService._log_item_use_to_combat``'s fallback
        trim, runs exclusively when the player has NO adapter (it prefers
        ``_add_log_entry`` whenever one is attached), so no live index can be
        stale against it.

        A trim invalidates the index outright rather than un-counting what it
        dropped: ``allow_duplicate`` entries share a key by design (see
        ``_emit_animation_log``), so per-entry removal would need multiplicities,
        and a rebuild after a trim is both simpler and cheap -- the trim only
        fires once per COMBAT_LOG_TRIM_SLACK inserts.
        """
        log = getattr(self.player, "combat_log", None)
        if not isinstance(log, list):
            # Missing, None, or a non-list a crafted save smuggled past the
            # attach sanitize (e.g. rebound after __init__): a str here would
            # be iterated char by char below and raise on every insert.
            log = self.player.combat_log = []
        if self._log_key_source is not log or self._log_key_count != len(log):
            self._log_keys = {self._log_entry_key(e) for e in log}
            self._log_key_source = log
            self._log_key_count = len(log)
        return self._log_keys

    def _trim_combat_log(self):
        """Bound the combat log, newest-first, per kind of entry.

        Rewrites the list IN PLACE: ``player.combat_log`` is read through the
        player everywhere and pickled with it, so rebinding would strand any
        held reference. Relative order is preserved, so the recap still reads
        chronologically across the seam.

        Returns the number of entries dropped off the FRONT, because callers
        hold positions into this list: ``execute_player_move`` records
        ``log_len_before`` and slices the tail to scope one beat's entries, and
        an in-place front-trim shifts every position under it. Ignoring the
        return means that beat's window comes back wrong -- usually empty -- and
        the beat protocol silently emits nothing for it.

        See MAX_ANIMATION_LOG_ENTRIES / MAX_VISIBLE_LOG_ENTRIES for the policy.
        ``GameService._log_item_use_to_combat`` keeps a sibling no-adapter
        fallback cap over the same list -- a policy change here likely needs
        mirroring there.
        """
        log = self.player.combat_log
        ceiling = (
            MAX_ANIMATION_LOG_ENTRIES
            + MAX_VISIBLE_LOG_ENTRIES
            + COMBAT_LOG_TRIM_SLACK
        )
        if len(log) <= ceiling:
            return 0

        before = len(log)
        animation_budget = MAX_ANIMATION_LOG_ENTRIES
        visible_budget = MAX_VISIBLE_LOG_ENTRIES
        kept = []
        for entry in reversed(log):
            if entry.get("type") == "animation":
                if animation_budget <= 0:
                    continue
                animation_budget -= 1
            else:
                if visible_budget <= 0:
                    continue
                visible_budget -= 1
            kept.append(entry)
        kept.reverse()
        log[:] = kept
        # Force the lazy rebuild in _log_key_index rather than recomputing here.
        self._invalidate_log_key_index()
        return before - len(kept)

    def _add_log_entry(
        self,
        round_num: int,
        message: str,
        entry_type: str = "combat",
        beat_index: int = 0,
        animation_data: dict = None,
        timestamp: str = None,
        allow_duplicate: bool = False,
    ):
        """Add a log entry with deduplication check.

        Args:
            round_num: Combat round number
            message: Log message text
            entry_type: Type of log entry (combat, system, etc.)
            beat_index: Index of the beat state this log entry corresponds to (for map sync)
            animation_data: Optional animation metadata for frontend
                Format: {
                    "type": "attack",  # Animation type
                    "source_id": "enemy_123",  # Entity performing move
                    "target_id": "enemy_456",  # Target entity (if targeted)
                    "outcome": "hit",  # "hit", "miss", "parry", etc.
                    "move_name": "Attack"
                }
        """
        # Check for duplicate.
        # We key on (message, round) plus the acting entity's id so that two
        # distinct combatants using identically-named moves in the same beat
        # (e.g. two same-species NPCs) don't collide — otherwise the second
        # entry's animation would be silently dropped from the frontend log.
        # For non-animation entries source_id is None on both sides, preserving
        # the original (message, round) dedup behaviour.
        # ``allow_duplicate`` opts an entry out entirely — see _emit_animation_log.
        #
        # Membership in a hash index, not a scan of the whole cumulative log:
        # the scan was O(n) per insert and therefore O(n²) over a fight, and
        # per-target resolutions raised n by a factor of however many enemies an
        # arc reaches.
        key = _dedup_key(
            message, round_num, (animation_data or {}).get("source_id")
        )
        # Resolve the index unconditionally: `and` would short-circuit past it
        # for an allow_duplicate entry, leaving the index unbuilt for the very
        # insert that is about to update it. This call is also what lazily
        # creates a missing player.combat_log (its single home).
        index = self._log_key_index()
        is_duplicate = not allow_duplicate and key in index
        if not is_duplicate:
            entry = {
                "round": round_num,
                "message": message,
                "type": entry_type,
                "timestamp": timestamp or datetime.now().strftime("%H:%M:%S"),
                "beat_index": beat_index,  # For syncing with beat_states array
            }

            # Add animation metadata if provided
            if animation_data:
                entry["animation"] = animation_data

            self.player.combat_log.append(entry)
            index.add(key)
            self._log_key_count = len(self.player.combat_log)
            self._log_trimmed_since_beat = (
                self._log_trimmed_since_beat + self._trim_combat_log()
            )

            # Emit socket event if session is known
            if self.session_id:
                try:
                    from flask import current_app

                    if hasattr(current_app, "socketio"):
                        room = f"combat_{self.session_id}"
                        current_app.socketio.emit("combat:log", entry, room=room)
                except Exception as e:
                    print(f"[SOCKET ERROR] Failed to emit log: {e}")

    def _reset_animation_seq(self):
        """Start the per-fight animation sequence over (new combat only).

        Lives on ``combat_adapter_state`` for the same reason ``combat_id``
        does: the adapter object is not the fight's lifetime, and a
        replacement adapter built mid-fight must keep the sequence monotonic.
        """
        self._adapter_state()["animation_seq"] = 0

    def _next_animation_seq(self) -> int:
        """The next per-fight animation sequence number (1-based, monotonic).

        ``animation_seq`` rides in ``combat_adapter_state`` on the pickled
        player, so a crafted save controls the stored value: a str/list would
        raise out of ``int()`` and brick every move of the loaded fight, and a
        negative or absurd int would ship as client-side carrier identity.
        Anything non-numeric or out of ``[0, MAX_ANIMATION_SEQ]`` restarts the
        sequence at 0 instead.
        """
        state = self._adapter_state()
        try:
            seq = int(state.get("animation_seq", 0) or 0)
        except (TypeError, ValueError):
            seq = 0
        if not 0 <= seq <= MAX_ANIMATION_SEQ:
            seq = 0
        seq += 1
        state["animation_seq"] = seq
        return seq

    def _emit_animation_log(self, beat, animation_data):
        """Add the carrier log entry for one animation.

        Each emitted payload is stamped with ``seq`` — a per-fight,
        monotonically increasing number (reset in ``initialize_combat``'s
        non-reinit branch). The client prefers ``entry.animation.seq`` as the
        carrier's identity when present, falling back to its positional
        scheme, which is what keeps carrier identity stable across a
        front-trim of the log.

        ``allow_duplicate`` is not optional here. One swing can resolve several
        times — an arc catching four enemies, Chip Away's three strikes — and
        every one of those carriers shares its message, round and acting entity
        with the first, so the deduplicator in ``_add_log_entry`` (which exists
        to collapse a repeated *narration* line) would silently throw away every
        landing after the first and undo the whole per-target outcome channel.
        Two resolutions can even be identical on the wire (Chip Away landing
        twice on one target for the same outcome), so no message-mangling scheme
        distinguishes them; the emission itself is the fact, and by the time we
        are here the decision to emit has already been made exactly once.

        The message is a carrier, not player-facing text: CombatLog filters
        ``type === 'animation'`` entries out of the visible log.
        """
        animation_data = dict(animation_data)
        animation_data["seq"] = self._next_animation_seq()
        self._add_log_entry(
            beat,
            f"{animation_data.get('move_display_name', animation_data.get('move_name', 'Move'))} animation",
            "animation",
            beat_index=self.current_beat_state_index,
            animation_data=animation_data,
            allow_duplicate=True,
        )

    def _detach_current_move(self, entity):
        """Clear ``entity.current_move`` AND discard its animation channel.

        The deletion point for a move CANCELLED mid-wind-up -- an abort, an
        event interrupt, or the roster emptying under it (see the
        ``_pending_animation`` lifecycle block at the top of this module).
        The end-of-move flush's fallback emission is right for a move that ran
        to completion without resolving; for a cancelled wind-up it is a
        phantom: the swing never happened, and emitting the full move
        animation would play the very attack the player just broke off (or an
        event just reset). A channel that DID resolve mid-flight is dropped
        just as silently -- its resolutions were already emitted, and nothing
        is left to publish to it.

        Detach and discard are one operation on purpose: a site that clears
        ``current_move`` and leaves the channel armed leaks it (nothing will
        ever publish again), and one that flushes instead emits the phantom.
        Stage bookkeeping (cooldown charge, stage reset) stays with each call
        site -- the three cancellation paths legitimately differ there.
        """
        entity.current_move = None
        if hasattr(entity, PENDING_ANIMATION_ATTR):
            delattr(entity, PENDING_ANIMATION_ATTR)

    def _discard_pending_animations(self):
        """Drop every combatant's animation channel, in flight or not.

        The teardown deletion point in the ``_pending_animation`` lifecycle
        (see the block at the top of this module). The end-of-move flush
        deliberately leaves a mid-wind-up move's channel armed so its impact
        still has somewhere to publish. That is right while the fight
        continues and wrong the moment it ends: nothing will ever publish
        again, and the dict can still hold ``outcome_target`` -- a live
        combatant nothing will consume. Dropping it here is reference hygiene
        and defense-in-depth; the actual pickle guard is
        ``Combatant.__getstate__``, which strips ``_pending_animation`` from
        every save regardless.

        Both endings need this, not just victory: on defeat the player's own
        channel can be the armed one.
        """
        for entity in self._all_combatants():
            if hasattr(entity, PENDING_ANIMATION_ATTR):
                delattr(entity, PENDING_ANIMATION_ATTR)

    def _flush_pending_animations(self):
        """Retire the pending animation of every combatant whose move is over.

        The end-of-move deletion point in the ``_pending_animation`` lifecycle
        (see the block at the top of this module) — for moves that RAN TO
        COMPLETION. A move cancelled mid-wind-up goes through
        ``_detach_current_move`` instead, which discards rather than emits.

        Emits a fallback log entry only for animations that never resolved —
        a move that dealt no damage and narrated nothing the capture paired an
        outcome with. An animation that reported in ANY beat (once, or once per
        enemy for an arc swing) is dropped silently: re-emitting it would append
        a phantom trailing animation to every attack in the game.

        A combatant still mid-move is skipped entirely. This flush runs at the
        end of each *player* move, which is not the end of everyone else's: an
        NPC three beats into a five-beat wind-up would otherwise have the very
        channel its impact publishes to deleted out from under it, turning
        ``publish_outcome`` into a silent no-op for the swing still to come —
        and, on the way out, emitting a fallback animation for a move that had
        not landed yet.
        """
        for entity in self._all_combatants():
            if not hasattr(entity, PENDING_ANIMATION_ATTR):
                continue
            animation_data = getattr(entity, PENDING_ANIMATION_ATTR)
            if not isinstance(animation_data, dict):
                # publish_outcome tolerates a non-dict placeholder; emitting it
                # would raise AttributeError on .get() inside the move loop.
                delattr(entity, PENDING_ANIMATION_ATTR)
                continue
            if getattr(entity, "current_move", None) is not None:
                continue
            if REPORTED_BEAT_KEY not in animation_data:
                self._emit_animation_log(
                    self.player.combat_beat, _wire_animation(animation_data)
                )
            delattr(entity, PENDING_ANIMATION_ATTR)

    @staticmethod
    def _reset_idle_move_stages(combatant) -> None:
        """Rewind a combatant's moves to stage 0, sparing the one in flight.

        Used by the reinit path of :meth:`initialize_combat`. The combatant's
        ``current_move`` is skipped: rewinding a move that is mid-``advance``
        traps ``Move.advance``'s stage loop, which only terminates once the
        stage counter passes 3.
        """
        active = getattr(combatant, "current_move", None)
        for move in getattr(combatant, "known_moves", []):
            if move is active:
                continue
            move.current_stage = 0
            move.beats_left = 0

    def initialize_combat(
        self, enemies: List[Any], reinit: bool = False
    ) -> Dict[str, Any]:
        """
        Initialize combat with the given enemies.

        Args:
            enemies: List of enemy NPCs
            reinit: If True, this is a mid-combat update (reinforcements)

        Returns:
            Initial or updated combat state

        Side effect: on a non-reinit call this is the sole minting site for
        `combat_id` (see the property), alongside the beat and log reset.
        """
        try:
            # Import here to avoid circular dependencies

            if not reinit:
                self.player.combat_beat = 1  # Start at beat 1 for synchronization
                self._terminal_event_emitted = False
                self.player.combat_log = []  # Clear log for new combat
                # Stable identity for this fight, minted alongside the beat/log
                # reset so it changes exactly when a genuinely new combat starts
                # — not on a reinit (wave transition, reinforcement spawn).
                # get_combat_state publishes it on every poll so the client can
                # tell "new fight" from "same fight, next beat".
                self.combat_id = str(uuid.uuid4())
                # Animation carrier seq restarts with the fight (it is
                # per-fight identity, like combat_id — see _emit_animation_log).
                self._reset_animation_seq()
                # Who has been announced is per-fight state too.
                self._announced_enemies = set()
                # Defence in depth for issue #506: a combat-effect event armed
                # in another room must not get a chance to fire in this fight.
                purge_orphaned_combat_events(self.player)
                # Clear any prior end-of-combat summary/drops from previous encounters
                self.player.combat_end_summary = None
                self.player.combat_drops = []
                self.output_capture.clear()  # Clear captured output
                self.current_beat_state_index = 0  # Reset beat state tracking

            # Initialize combat_proximity if it doesn't exist
            if not hasattr(self.player, "combat_proximity"):
                self.player.combat_proximity = {}

            if not reinit:
                self.player.heat = 1.0

            # Initialize positions. A CombatEventConfig-scripted encounter may
            # have stashed an explicit scenario_type override (issue #427) —
            # honor it in place of the usual heuristic, then clear it so it
            # doesn't leak into the next (unrelated) combat. isinstance-checked
            # (rather than a plain truthiness check) so test doubles that don't
            # set this attribute at all (e.g. MagicMock, which auto-vivifies
            # any attribute access) can't accidentally trip the override.
            pending_scenario_type = getattr(
                self.player, "_pending_scenario_type", None
            )
            if isinstance(pending_scenario_type, str) and pending_scenario_type:
                scenario_type = pending_scenario_type
                del self.player._pending_scenario_type
            else:
                scenario_type = "standard"
                if len(self.player.combat_list) > 1 and len(
                    self.player.combat_list_allies
                ) < len(self.player.combat_list):
                    scenario_type = "pincer"
                elif (
                    len(self.player.combat_list_allies) == 1
                    and len(self.player.combat_list) == 1
                ):
                    scenario_type = "boss_arena"

            try:
                pending_grid_override = getattr(
                    self.player, "_pending_grid_size_override", None
                )
                if (
                    isinstance(pending_grid_override, (tuple, list))
                    and len(pending_grid_override) == 2
                ):
                    grid_w, grid_h = pending_grid_override
                    del self.player._pending_grid_size_override
                else:
                    from src.coordinate_config import CoordinateSystemConfig

                    coord_config = CoordinateSystemConfig(self.player)
                    total_combatants = len(self.player.combat_list_allies) + len(
                        self.player.combat_list
                    )
                    grid_w, grid_h = coord_config.get_dynamic_grid_size(
                        total_combatants
                    )
                self.combat_grid_size = (grid_w, grid_h)

                positions.initialize_combat_positions(
                    allies=self.player.combat_list_allies,
                    enemies=self.player.combat_list,
                    scenario_type=scenario_type,
                    grid_width=grid_w,
                    grid_height=grid_h,
                )
            except Exception as e:
                print(f"Warning: Position initialization failed: {e}")
                # Fallback to old proximity system
                for ally in self.player.combat_list_allies:
                    if not hasattr(ally, "combat_proximity"):
                        ally.combat_proximity = {}
                    for enemy in self.player.combat_list:
                        if not hasattr(enemy, "combat_proximity"):
                            enemy.combat_proximity = {}
                        if not hasattr(enemy, "default_proximity"):
                            enemy.default_proximity = (
                                10  # Default distance - enemies start in striking range
                            )
                        if enemy not in ally.combat_proximity:
                            distance = int(
                                enemy.default_proximity * random.uniform(0.75, 1.25)
                            )
                            ally.combat_proximity[enemy] = distance
                            enemy.combat_proximity[ally] = distance

            if not reinit:
                # Reset moves only for new combat
                for ally in self.player.combat_list_allies:
                    ally.in_combat = True
                    for move in ally.known_moves:
                        move.current_stage = 0
                        move.beats_left = 0

                for enemy in self.player.combat_list:
                    # Provide a back-reference for API-mode drop/loot tracking
                    try:
                        enemy.player_ref = self.player
                    except Exception:
                        logger.warning(
                            "Could not set player_ref on enemy %s",
                            getattr(enemy, "name", enemy),
                        )
                    for move in enemy.known_moves:
                        move.current_stage = 0
                        move.beats_left = 0
            else:
                # For re-init, ensure ALL combatants are properly flagged and
                # reset move stages so prior cooldowns don't block new combat.
                #
                # A combatant's *in-flight* move is exempt. Rewinding it to
                # stage 0 with beats_left 0 while Move.advance is inside its
                # `while self.beats_left == 0` stage loop pushes that loop back
                # to the start on every pass, so it never reaches the
                # current_stage > 3 exit: the engine spins forever. That is
                # reachable from normal play — any move or combat effect that
                # spawns reinforcements mid-execute (functions.
                # add_enemies_to_combat -> initialize_combat(reinit=True))
                # re-enters here from inside its own advance().
                #
                # Exempting it is also what the resume path below wants: it
                # deliberately continues player.current_move from its stored
                # stage (issue #344), which a reset to 0 had already destroyed.
                for ally in self.player.combat_list_allies:
                    ally.in_combat = True
                    self._reset_idle_move_stages(ally)
                for enemy in self.player.combat_list:
                    enemy.in_combat = True
                    try:
                        enemy.player_ref = self.player
                    except Exception:
                        logger.warning(
                            "Could not set player_ref on enemy %s",
                            getattr(enemy, "name", enemy),
                        )
                    self._reset_idle_move_stages(enemy)

            # Initialize combat lists for all participants (Enemies and Allies)
            # This ensures collision detection works correctly for everyone

            # For Player's Allies:
            # - Their enemies are the Player's enemies
            # - Their allies are the Player's allies
            for ally in self.player.combat_list_allies:
                if ally == self.player:
                    continue
                ally.combat_list = self.player.combat_list
                ally.combat_list_allies = self.player.combat_list_allies

            # For Enemies:
            # - Their enemies are the Player's allies (including Player)
            # - Their allies are the Player's enemies (other enemies)
            for enemy in self.player.combat_list:
                enemy.combat_list = self.player.combat_list_allies
                enemy.combat_list_allies = self.player.combat_list

            # Add initial log entry for each enemy that has not been announced
            # in THIS fight. A reinit re-enters here with a roster that can
            # include combatants already on the battlefield (GameService's
            # reinit path assigns the whole new roster, not just the arrivals),
            # and re-announcing them told the player that enemies they were
            # already fighting had just shown up. `_add_log_entry`'s
            # (message, round, source_id) dedup masked it only until
            # `_trim_combat_log` dropped the round-1 entries it compares
            # against — a long fight got the duplicates anyway (issue #506).
            for enemy in enemies:
                if enemy in self._announced_enemies:
                    continue
                self._announced_enemies.add(enemy)
                name = getattr(enemy, "name", "Enemy")
                alert = getattr(enemy, "alert_message", "appears!")
                self._add_log_entry(1, f"{name} {alert}", "system")

            # A reinit raised from *inside* an in-flight move — an enemy move
            # or a combat event that spawns reinforcements during a beat —
            # must stop here. _execute_move is already on the stack and will
            # keep driving the beat loop; falling through to the resume branch
            # below re-entered it on the same player.current_move, and the
            # fresh beat loop gave the summoning NPC another turn, which
            # summoned again: unbounded recursion that pinned the request
            # thread and grew the enemy roster without limit. The roster,
            # positions and arrival announcements are already updated above,
            # so the arrivals join the fight mid-beat exactly as intended.
            if reinit and self._executing_move:
                return self.get_combat_state()

            # Process initial NPC turns only for new combats
            if not reinit:
                self._process_initial_turns()
                # A first-strike NPC gets a whole beat here, outside any move
                # loop. Without a flush its pending animation survives until the
                # end of the player's FIRST move and is emitted a beat or more
                # late; moves still winding up are skipped by the flush and keep
                # their channel.
                self._flush_pending_animations()

            # Set up for player's move selection OR resume existing move
            if reinit and self.player.current_move is not None:
                # RESUME the current move if we were mid-combat.
                # Pass resume=True so the beat loop continues the move's
                # recoil/cooldown from its stored stage WITHOUT re-casting —
                # cast() would reset current_stage to 0 and re-apply one-shot
                # cast effects, restarting the move instead. See issue #344.
                return self._execute_move(self.player.current_move, resume=True)

            self.awaiting_input = True
            self.input_type = "move_selection"
            self.available_options = self._get_available_moves()
            # Start async suggestion fetch (non-blocking)
            self.refresh_suggestions()

            result = self.get_combat_state()

            # Set up beat streaming for this combat (issue #436). Only on a fresh
            # start — a reinit (reinforcements) keeps the existing streamer so
            # seq stays monotonic across the whole encounter.
            if not reinit:
                self._maybe_init_streamer(result)

            # Emit combat started event
            if self.session_id:
                try:
                    from flask import current_app

                    serialized_state = result
                    if hasattr(current_app, "socketio"):
                        current_app.socketio.emit(
                            "combat:started",
                            {"battle_state": serialized_state},
                            room=f"combat_{self.session_id}",
                        )
                except Exception:
                    import traceback

                    traceback.print_exc()
            return result

        except Exception as e:
            import traceback

            error_msg = (
                f"Combat initialization error: {str(e)}\n{traceback.format_exc()}"
            )
            print(error_msg)
            return {
                "error": "Failed to initialize combat",
                "details": str(e),
                "combat_active": False,
            }

    def process_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a command from the frontend.

        Args:
            command: Dictionary with command type and parameters
                Examples:
                - {"type": "select_move", "move_index": 2}
                - {"type": "select_target", "target_id": "enemy_0"}
                - {"type": "select_direction", "direction": "north"}

        Returns:
            Updated combat state
        """

        if not isinstance(command, dict):
            return {"error": "Invalid command: expected an object"}

        if not self.awaiting_input:
            return {"error": "Not awaiting input"}

        command_type = command.get("type")

        if command_type == "select_move":
            return self._handle_move_selection(command.get("move_index"))
        elif command_type == "select_target":
            return self._handle_target_selection(command.get("target_id"))
        elif command_type == "select_direction":
            return self._handle_direction_selection(command.get("direction"))
        elif command_type == "select_number":
            return self._handle_number_selection(command.get("value"))
        elif command_type == "select_move_and_target":
            return self._handle_combined_selection(
                command.get("move_name"), command.get("target_id")
            )
        elif command_type == "cancel_selection":
            return self._handle_cancel_selection()
        else:
            return {"error": f"Unknown command type: {command_type}"}

    def _handle_cancel_selection(self) -> Dict[str, Any]:
        """
        Handle canceling the current selection (target/direction/number).
        Reverts back to move selection.
        """
        if self.input_type == "move_selection":
            # Can't cancel back further than move selection
            return {"error": "Cannot cancel selection at this stage"}

        # Reverting to move selection
        self.pending_move_index = None
        self.input_type = "move_selection"
        self.available_options = self._get_available_moves()

        # Log cancellation (optional, but good for debugging)

        return self.get_combat_state()

    def _lookup_combatant(self, target_id: str):
        """Return the combatant whose id() matches target_id, or None.

        The prefix (``enemy_``/``ally_``) is stripped before comparison so
        either form resolves against the raw Python id string.
        """
        target_obj_id = _strip_combatant_prefix(target_id)
        for combatant in self.player.combat_list + self.player.combat_list_allies:
            if str(id(combatant)) == target_obj_id:
                return combatant
        return None

    def _resolve_target_from_options(
        self, move, target_id: str, options: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Validate a client-supplied ``target_id`` against ``move``'s option set.

        ``_lookup_combatant`` answers "is this anybody in the fight?", which is
        not the question the API needs to ask: a combat command arrives from the
        client, so the only targets a move may legally act on are the ones the
        adapter itself published for it -- i.e. exactly what
        :meth:`_get_available_targets` returns (alive, inside the move's
        effective ``mvrange``, and friendly only when the move sets
        ``accepts_ally_target``). Without that check a crafted ``select_target``
        turned every targeted move into an unlimited-range, friendly-fire-capable
        one: ``Disrupt`` (``mvrange=(0, 5)``, load-bearing per its own docstring)
        landed on an enemy 40 tiles away and on a friendly NPC.

        This is the **single** place that check lives. Both entry points --
        :meth:`_resolve_move_target` (``select_move`` / ``select_move_and_target``)
        and :meth:`_handle_target_selection` (``select_target``) -- route through
        it, because each previously carried its own copy of the raw lookup and
        that duplication is why neither validated.

        Returns:
            ``{"target": <combatant>}`` — the id names a currently legal target
            ``{"error": <str>}``        — the id names a real combatant this move
                                          may not act on (out of range, dead, or
                                          an ally on a move that does not accept
                                          ally targets)
            ``{}``                      — the id names nobody in this fight; the
                                          caller falls back to its own
                                          no-explicit-target handling
        """
        if not isinstance(target_id, str) or not target_id:
            return {}

        candidate = self._lookup_combatant(target_id)
        if candidate is None:
            return {}

        if options is None:
            options = self._get_available_targets(move)

        allowed_ids = {
            _strip_combatant_prefix(option["id"])
            for option in options
            if isinstance(option, dict) and isinstance(option.get("id"), str)
        }

        if str(id(candidate)) not in allowed_ids:
            return {
                "error": (
                    f"{getattr(candidate, 'name', 'That target')} is not a valid "
                    f"target for {display_name_of(move)}"
                )
            }

        return {"target": candidate}

    def _check_move_preconditions(self, move) -> Optional[Dict[str, Any]]:
        """Return an error dict if the player may not start ``move`` right now.

        Every precondition that must hold before a move is assigned to
        ``player.current_move`` lives here, because the adapter has **two**
        entry points into move selection -- ``select_move``
        (:meth:`_handle_move_selection`) and ``select_move_and_target``
        (:meth:`_handle_combined_selection`) -- and the client sends the second
        one for essentially every combat action. Each used to carry its own
        copy of the guards and they drifted: the combined path never checked
        ``current_stage``, so a move still in recoil or cooldown could be
        re-selected, and ``cast()`` unconditionally resets ``current_stage`` to
        0 -- erasing the remaining cooldown and making any move free to spam
        through the primary UI path. (The same duplication is why neither path
        validated its target; see :meth:`_resolve_target_from_options`.)

        Returns ``None`` when the move may proceed. Callers must run this
        *before* mutating any combat state, so a rejection is a clean no-op.
        """
        if not move.viable():
            return {"error": "Move is not currently available"}

        # Only check fatigue for moves that actually cost some.
        if move.fatigue_cost > 0 and self.player.fatigue < move.fatigue_cost:
            return {"error": "Not enough fatigue"}

        # A move that is mid-cycle (execute/recoil/cooldown) is not selectable.
        if move.current_stage != 0:
            return {"error": "Move not ready yet"}

        # A move already winding up must be paid for, not walked away from.
        # A prep longer than the per-request beat cap hands control back while
        # the move is still in stage 0, and selecting anything else used to
        # simply reassign player.current_move -- orphaning 20 beats of Aimed
        # Shot at no cost and leaving it instantly re-castable. That made the
        # costed abort below pointless, since the free path sat right beside
        # it. Switching now requires an explicit abort first.
        in_flight = self._abortable_move()
        if in_flight is not None and in_flight is not move:
            return {
                "error": (
                    f"{display_name_of(in_flight)} is already winding up. "
                    "Abort it first to act on something else."
                ),
                "requires_abort": True,
            }

        return None

    def _resolve_move_target(
        self, move, move_index: int, target_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Resolve the target for a targeted move (shared by both selection flows).

        Resolution order: an explicit ``target_id``, single-viable-target
        auto-resolution, or multi-target selection setup.

        Returns one of:
            {"target": <combatant>} — target found; caller assigns and executes
            {"await": True}         — multiple targets; adapter state is set for
                                      target_selection, caller returns combat state
            {"error": <str>}        — no viable target could be resolved
        """
        viable_targets = self._get_available_targets(move)
        target = None

        if target_id:
            # An explicitly named target must be one the adapter published for
            # this move; an id that names nobody falls through to the
            # auto-resolution path below, exactly as before.
            resolution = self._resolve_target_from_options(
                move, target_id, viable_targets
            )
            if "error" in resolution:
                return resolution
            target = resolution.get("target")

        if target is None:
            if len(viable_targets) == 1:
                single_id = (
                    viable_targets[0].get("id")
                    if isinstance(viable_targets[0], dict)
                    else None
                )
                if not isinstance(single_id, str):
                    return {"error": "Invalid target"}
                target = self._lookup_combatant(single_id)
                if target is None:
                    return {"error": "Failed to resolve single target"}
            elif len(viable_targets) > 1:
                # Multiple viable targets — request explicit target selection.
                self.input_type = "target_selection"
                self.available_options = viable_targets
                self.pending_move_index = move_index
                return {"await": True}
            else:
                return {"error": "No valid targets available for this move"}

        return {"target": target}

    def _handle_combined_selection(
        self, move_name: str, target_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle player selecting a move and target in one command."""
        if not isinstance(move_name, str) or not move_name.strip():
            return {"error": "Invalid move name"}

        if target_id is not None and not isinstance(target_id, str):
            return {"error": "Invalid target"}

        if self.input_type != "move_selection":
            return {"error": "Not expecting move selection"}

        # Find move by name (case-insensitive)
        move_index = -1
        for i, m in enumerate(self.player.known_moves):
            if m.name.strip().lower() == move_name.strip().lower():
                move_index = i
                break

        if move_index == -1:
            # Try partial match if no exact match
            for i, m in enumerate(self.player.known_moves):
                if move_name.strip().lower() in m.name.strip().lower():
                    move_index = i
                    break

        if move_index == -1:
            return {"error": f"Move '{move_name}' not found"}

        selected_move = self.player.known_moves[move_index]

        # Same preconditions the select_move path enforces -- viability,
        # fatigue, readiness (current_stage) and the winding-up abort guard.
        # This path is the one the React client actually uses, so a guard that
        # lives only in _handle_move_selection guards almost nothing.
        precondition_error = self._check_move_preconditions(selected_move)
        if precondition_error is not None:
            return precondition_error

        # If move is targeted, resolve the target via the shared helper
        if selected_move.targeted:
            resolution = self._resolve_move_target(
                selected_move, move_index, target_id
            )
            if "error" in resolution:
                return {"error": resolution["error"]}
            if resolution.get("await"):
                return self.get_combat_state()
            selected_move.target = resolution["target"]
        else:
            selected_move.target = self.player

        self.player.current_move = selected_move
        self.player.current_move.user = self.player
        self._add_log_entry(
            self.output_capture.current_round,
            f"{self.player.name} uses {display_name_of(selected_move)}!",
            "player_action",
        )

        return self._execute_move(selected_move)

    def _handle_move_selection(self, move_index: int) -> Dict[str, Any]:
        """Handle player selecting a move."""

        if self.input_type != "move_selection":
            return {"error": "Not expecting move selection"}

        # Reject non-integer indices (bool included — bool is an int subclass and
        # would otherwise slip through as 0/1, corrupting pending_move_index).
        if not isinstance(move_index, int) or isinstance(move_index, bool):
            return {"error": "Invalid move index"}

        # Use all known moves, not just viable ones
        all_moves = self.player.known_moves

        if move_index < 0 or move_index >= len(all_moves):
            return {"error": "Invalid move index"}

        selected_move = all_moves[move_index]

        # Viability, fatigue, readiness and the winding-up abort guard all live
        # in _check_move_preconditions so this path and select_move_and_target
        # cannot drift apart again.
        precondition_error = self._check_move_preconditions(selected_move)
        if precondition_error is not None:
            return precondition_error

        self.player.current_move = selected_move
        self.player.current_move.user = self.player

        self._add_log_entry(
            self.output_capture.current_round,
            f"{self.player.name} uses {display_name_of(selected_move)}!",
            "player_action",
        )

        # Check if move needs targeting — resolve via the shared helper
        if selected_move.targeted:
            resolution = self._resolve_move_target(selected_move, move_index)
            if "error" in resolution:
                return {"error": resolution["error"]}
            if resolution.get("await"):
                # Multiple targets — keep awaiting_input True so the frontend
                # knows to send a target selection.
                return self.get_combat_state()
            selected_move.target = resolution["target"]
            self.pending_move_index = None
            return self._execute_move(selected_move)

        # Check if move needs duration input (e.g., Wait move)
        if hasattr(selected_move, "needs_duration") and selected_move.needs_duration:
            self.input_type = "number_input"
            self.available_options = {
                "prompt": "How many beats do you want to wait?",
                "min": 3,
                "max": 10,
                "default": 5,
            }
            self.pending_move_index = move_index
            # Keep awaiting_input True so frontend knows to send number
            return self.get_combat_state()

        # Check if move needs direction (Turn move)
        if selected_move.name == "Turn":
            self.input_type = "direction_selection"
            self.available_options = ["north", "south", "east", "west"]
            self.pending_move_index = move_index
            # Keep awaiting_input True so frontend knows to send direction
            return self.get_combat_state()

        # Non-targeted move - execute immediately
        selected_move.target = self.player
        return self._execute_move(selected_move)

    def _handle_target_selection(self, target_id: str) -> Dict[str, Any]:
        """Handle player selecting a target."""
        if self.input_type != "target_selection":
            return {"error": "Not expecting target selection"}

        if not isinstance(target_id, str) or not target_id:
            return {"error": "Invalid target"}

        # Reconstruct pending move
        if self.pending_move_index is None:
            return {"error": "No pending move"}

        all_moves = self.player.known_moves
        if self.pending_move_index >= len(all_moves):
            return {"error": "Invalid pending move index"}

        pending_move = all_moves[self.pending_move_index]
        pending_move.user = self.player

        # Find target in the option set published for the pending move. The
        # comment above this block used to be the only thing that said so --
        # the lookup underneath it scanned every combatant in the fight, which
        # let a crafted command act out of range or on an ally.
        resolution = self._resolve_target_from_options(pending_move, target_id)
        if "error" in resolution:
            # Reject without touching combat state: input_type stays
            # "target_selection", pending_move_index and available_options are
            # untouched, and no stage of the move has run, so the client can
            # simply re-send a legal target.
            return resolution

        target = resolution.get("target")
        if target is None:
            return {"error": "Invalid target"}

        pending_move.target = target

        # Check if move needs distance input (e.g., Tactical Positioning)
        if hasattr(pending_move, "needs_distance_input") and pending_move.needs_distance_input:
            self.input_type = "number_input"
            self.awaiting_input = True
            self.available_options = {
                "prompt": "Enter the desired distance (0-100):",
                "min": pending_move.mvrange[0] if hasattr(pending_move, "mvrange") else 0,
                "max": pending_move.mvrange[1] if hasattr(pending_move, "mvrange") else 100,
                "default": 10,
            }
            # Keep pending_move_index so we can access the move later
            return self.get_combat_state()

        # Clear pending move index
        self.pending_move_index = None

        return self._execute_move(pending_move)

    def _handle_direction_selection(self, direction: str) -> Dict[str, Any]:
        """Handle player selecting a direction."""
        if self.input_type != "direction_selection":
            return {"error": "Not expecting direction selection"}

        if direction not in self.available_options:
            return {"error": "Invalid direction"}

        # Reconstruct pending move
        if self.pending_move_index is None:
            return {"error": "No pending move"}

        all_moves = self.player.known_moves
        if self.pending_move_index >= len(all_moves):
            return {"error": "Invalid pending move index"}

        pending_move = all_moves[self.pending_move_index]
        pending_move.user = self.player

        # Set direction on the move
        if hasattr(pending_move, "target_direction"):
            # Convert string to Direction enum
            direction_map = {
                "north": positions.Direction.N,
                "south": positions.Direction.S,
                "east": positions.Direction.E,
                "west": positions.Direction.W,
            }
            # Fallback to N if mapping fails (though validation above catches it)
            enum_dir = direction_map.get(direction.lower(), positions.Direction.N)
            pending_move.target_direction = enum_dir

        # Clear pending move index
        self.pending_move_index = None

        return self._execute_move(pending_move)

    def _handle_number_selection(self, value: int) -> Dict[str, Any]:
        """Handle player entering a numeric value."""
        if self.input_type != "number_input":
            return {"error": "Not expecting number input"}

        # Ensure value is an integer
        if not isinstance(value, int) or isinstance(value, bool):
            return {"error": "Invalid numeric value"}

        # Reconstruct pending move
        if self.pending_move_index is None:
            return {"error": "No pending move"}

        all_moves = self.player.known_moves
        if self.pending_move_index >= len(all_moves):
            return {"error": "Invalid pending move index"}

        pending_move = all_moves[self.pending_move_index]
        pending_move.user = self.player

        # Validate the number is within acceptable range
        if isinstance(self.available_options, dict):
            min_val = self.available_options.get("min", 1)
            max_val = self.available_options.get("max", 100)

            if value < min_val or value > max_val:
                return {"error": f"Value must be between {min_val} and {max_val}"}

        # Set the duration on the move (for Wait move)
        if hasattr(pending_move, "duration"):
            pending_move.duration = value

        # Set the distance on the move (for Tactical Positioning)
        if hasattr(pending_move, "distance"):
            pending_move.distance = value

        # Clear pending move index
        self.pending_move_index = None

        return self._execute_move(pending_move)

    def _synchronize_distances(self):
        """
        Synchronize distances between combatants.
        Updates combat_proximity based on combat_position, and handles legacy fallback.
        Mirrors logic from combat.py.
        """
        player = self.player

        # Calculate proximity from coordinates for units with combat_position set
        all_combatants = player.combat_list_allies + player.combat_list
        for unit in all_combatants:
            if hasattr(unit, "combat_position") and unit.combat_position is not None:
                unit.combat_proximity = positions.recalculate_proximity_dict(
                    unit, all_combatants
                )

        # Original proximity synchronization logic for backward compatibility/fallback
        # Logic adapted from combat.py
        for each_ally in player.combat_list_allies:
            remove_these = []
            for each_enemy in each_ally.combat_proximity:
                if not each_enemy.is_alive():
                    remove_these.append(each_enemy)
            for each_enemy in remove_these:
                del each_ally.combat_proximity[each_enemy]

            for each_enemy in player.combat_list:
                remove_these = []
                for each_ally_in_prox in each_enemy.combat_proximity:
                    if not each_ally_in_prox.is_alive():
                        remove_these.append(each_ally_in_prox)
                for each_ally_that_died in remove_these:
                    del each_enemy.combat_proximity[each_ally_that_died]

                if each_enemy in each_ally.combat_proximity:
                    each_enemy.combat_proximity[each_ally] = each_ally.combat_proximity[
                        each_enemy
                    ]
                else:
                    # Enemy not in list (legacy/fallback), add with random distance
                    # But ONLY if we don't have positions (which would have handled it above)
                    if not (
                        hasattr(each_enemy, "combat_position")
                        and each_enemy.combat_position is not None
                        and hasattr(each_ally, "combat_position")
                        and each_ally.combat_position is not None
                    ):

                        default = getattr(each_enemy, "default_proximity", 20)
                        each_distance = int(default * random.uniform(0.75, 1.25))
                        each_ally.combat_proximity[each_enemy] = each_distance
                        each_enemy.combat_proximity[each_ally] = each_distance

        # Ensure reverse mapping for enemies
        for each_enemy in player.combat_list:
            for each_ally in player.combat_list_allies:
                if each_ally not in each_enemy.combat_proximity:
                    # If missed above, sync
                    if each_enemy in each_ally.combat_proximity:
                        each_enemy.combat_proximity[each_ally] = (
                            each_ally.combat_proximity[each_enemy]
                        )

    def _move_deals_damage(self, move) -> bool:
        """Check if a move deals damage (for animation fallback logic).

        Args:
            move: The move to check

        Returns:
            True if the move is likely to deal damage, False otherwise
        """
        # Check move category
        if hasattr(move, "category"):
            damage_categories = ["Attack", "Offensive", "Special"]
            if move.category in damage_categories:
                return True

        # Check move name patterns
        damage_keywords = [
            "attack",
            "strike",
            "slash",
            "stab",
            "smash",
            "crush",
            "punch",
            "kick",
        ]
        move_name_lower = move.name.lower()
        if any(keyword in move_name_lower for keyword in damage_keywords):
            return True

        return False

    def _build_animation_data(self, source, move) -> Dict[str, Any]:
        """The pending-animation payload for ``source`` casting ``move``.

        The SINGLE builder behind every cast site — the player cast in
        ``_execute_move_inner``, the NPC cast in ``_process_npc``, and the NPC
        item-heal in ``_npc_try_heal_ally`` (which passes a lightweight
        pseudo-move). The payload was previously hand-built at each site and
        the target gate drifted: the NPC site shipped ``npc.target`` even for
        a non-targeted move (a rest, a self-buff), so the streaming layer's
        ``has_swing`` (``bool(target_id)``) read a rest as a swing. The gate
        here is the player site's: **a target ships only when the move is
        targeted and has one** — otherwise ``target_id`` is None.

        The type fallback ladder (declared ``web_animation`` →
        ``DEFAULT_DAMAGE_ANIMATION`` for a targeted damaging move →
        ``DEFAULT_ANIMATION``) lives here for the same reason: it was
        duplicated per site.

        For the payload's full key set and lifecycle, see the
        ``_pending_animation`` block at the top of this module.
        """
        animation_type = getattr(move, "web_animation", None)
        targeted = getattr(move, "targeted", False)
        if animation_type is None:
            if targeted and self._move_deals_damage(move):
                animation_type = DEFAULT_DAMAGE_ANIMATION
            else:
                animation_type = DEFAULT_ANIMATION

        target = getattr(move, "target", None)
        return {
            "type": animation_type,
            # stream_id everywhere, never a hand-rolled prefix: an ally target
            # is ally_<id> on the resolution path too, and a mismatch means
            # the client matches the animation to no entity at all.
            "source_id": CombatantSerializer.stream_id(source),
            "target_id": (
                CombatantSerializer.stream_id(target)
                if targeted and target
                else None
            ),
            "move_name": move.name,
            "move_display_name": display_name_of(move),
        }

    def _execute_move(self, move, resume: bool = False) -> Dict[str, Any]:
        """Execute a move and process the combat beat(s).

        When ``resume`` is True the initial ``cast()`` is skipped so an
        already-in-progress move continues from its stored stage instead of
        being restarted (used by the reinit/reinforcement path).
        """
        # Mark the beat loop as running so a mid-beat reinforcement spawn
        # (functions.add_enemies_to_combat -> initialize_combat(reinit=True))
        # does not recursively resume this same move. Saved/restored rather
        # than simply cleared so the guard survives legitimate nesting.
        was_executing = self._executing_move
        self._executing_move = True
        try:
            return self._execute_move_inner(move, resume=resume)
        except Exception as e:
            logger.exception(
                "Unhandled exception in _execute_move for move '%s'",
                getattr(move, "name", "?"),
            )
            # Reset to a consistent baseline so subsequent moves are not blocked
            self.input_type = "move_selection"
            self.pending_move_index = None
            self.awaiting_input = True
            try:
                self.available_options = self._get_available_moves()
            except Exception:
                self.available_options = []
            return {"error": f"Move execution failed: {e}"}
        finally:
            self._executing_move = was_executing

    def _execute_move_inner(self, move, resume: bool = False) -> Dict[str, Any]:
        """Inner move execution — called only via _execute_move which handles state recovery.

        When ``resume`` is True the cast phase is skipped: the move is already
        mid-execution (current_stage > 0) and re-casting would reset its stage
        and re-apply one-shot cast effects. See issue #344.
        """
        # Reset beat state index for this move execution
        self.current_beat_state_index = 0

        is_instant = hasattr(move, "instant") and move.instant
        beat_states = []

        # Cast the move (capture output for initial cast message).
        # Skipped when resuming an already-cast, in-progress move (issue #344).
        if not resume:
            with self._capture_output():
                # Store for repeat functionality
                self.player.last_move_name = move.name

                self.player.last_move_target_id = (
                    CombatantSerializer.stream_id(move.target)
                    if getattr(move, "target", None)
                    else None
                )

                # Store for outcome tracking (updated when combat output is
                # captured). One builder for every cast site — see
                # _build_animation_data.
                setattr(
                    self.player,
                    PENDING_ANIMATION_ATTR,
                    self._build_animation_data(self.player, move),
                )
                # Tag the active entity so write() can find the right pending animation
                self.output_capture.active_entity = self.player

                move.cast()

            self.output_capture.active_entity = None

        # For instant moves, process all stages immediately without advancing beats
        if is_instant:
            with self._capture_output():
                self.output_capture.active_entity = self.player
                while self.player.current_move == move:
                    move.advance(self.player)
                    if self.player.current_move is None:
                        break
                self.output_capture.active_entity = None
        else:
            # Loop until player is ready for input again
            # This handles multi-beat moves like Wait
            max_beats = 20  # Safety break
            beats_processed = 0

            while beats_processed < max_beats:
                # Synchronize distances at start of beat (just like combat.py)
                self._synchronize_distances()

                # Set the beat state index for this beat BEFORE processing
                # so all log messages get tagged with the correct index
                current_beat_index = len(beat_states)
                self.current_beat_state_index = current_beat_index

                # Snapshot the log length before this beat's output is captured, so
                # beat_state["log"] below can be scoped to just this beat's entries
                # (issue #436 — CombatBeatStreamer reads a beat's animations out of
                # the beat's own log window via _beat_animations; a cumulative log
                # let a quiet beat pick up a stale animation from several beats ago,
                # misattributing e.g. a Whirl Attack wind-up beat to the enemy's
                # last attack).
                log_len_before = len(getattr(self.player, "combat_log", []))
                # The trim rewrites combat_log in place from the front, so this
                # position can move under us mid-beat. Count what it drops and
                # correct the slice below rather than losing the whole beat.
                self._log_trimmed_since_beat = 0

                # Capture output for THIS beat only
                with self._capture_output():
                    # Advance all player moves — tag so write() matches the right animation
                    self.output_capture.active_entity = self.player
                    for m in self.player.known_moves:
                        m.advance(self.player)
                    self.output_capture.active_entity = None

                    # Process NPC turns (each NPC sets active_entity internally)
                    self._process_npc_turns()

                    # Cycle states
                    self.player.cycle_states()

                    # Update heat
                    self._update_heat()

                    # Increment beat
                    self.player.combat_beat += 1

                # Check for combat events after each beat
                if self.on_event_callback:
                    events = self.on_event_callback(self.player)
                    if events:
                        # Narrative pause: record events and stop processing beats for now
                        self._adapter_state()["events_triggered"] = events

                        # Stop processing beats
                        break

                # Capture state for this beat AFTER processing
                beat_state = CombatStateSerializer.serialize_combat_state(
                    self.player,
                    self.player.combat_list,
                    round_number=self.player.combat_beat,
                    allies=self.player.combat_list_allies[1:],
                )

                # Add log to beat state — only entries added during THIS beat, not
                # the full cumulative combat log (see log_len_before above).
                beat_window_start = max(
                    0, log_len_before - self._log_trimmed_since_beat
                )
                beat_state["log"] = list(
                    getattr(self.player, "combat_log", [])[beat_window_start:]
                )
                beat_states.append(beat_state)

                beats_processed += 1

                # Check win/loss conditions inside loop
                if not self.player.is_alive() or len(self.player.combat_list) == 0:
                    break

                # Check if the current move has finished executing (entered cooldown or
                # completed). Return control as soon as at least one move is back at
                # stage 0 — meaning the player has something they can do. Only keep
                # advancing if every move is still in cooldown (player would have no
                # available actions), to avoid leaving the player with zero options.
                if self.player.current_move is None:
                    # Guard: no moves at all — don't burn remaining max_beats
                    if not self.player.known_moves:
                        break
                    if any(m.current_stage == 0 for m in self.player.known_moves):
                        break
                    # All moves still cooling — re-check survival before the next drain beat
                    if not self.player.is_alive() or len(self.player.combat_list) == 0:
                        break
                    # Keep advancing beats until one opens up

        # Capture last move summary from the log entries of this move
        move_logs = [
            s["message"]
            for s in self.player.combat_log
            if s.get("type") in ("combat", "player_action")
        ][
            -5:
        ]  # Last 5 relevant entries
        self.player.last_move_summary = " ".join(move_logs)

        self._flush_pending_animations()

        # Move execution finished

        # Check win/loss conditions
        if not self.player.is_alive() and not self.player.check_revive():
            self.player.in_combat = False
            self.awaiting_input = False
            self._add_log_entry(
                self.player.combat_beat, "You have been defeated!", "system"
            )

            # Set end-of-combat summary for defeat so frontend can show a
            # game-over dialog. Built plainly — the try/except that used to
            # wrap this also wrapped the pending-animation discard, so a raise
            # rebuilt the identical summary and silently skipped the discard.
            self.player.combat_end_summary = {
                "id": str(uuid.uuid4()),
                "status": "defeat",
                "message": "You have been defeated.",
                "game_over": True,
            }

            result = self.get_combat_state()
            result["beat_states"] = beat_states
            self._stream_combat_result(result, beat_states, ended=True)

            # Tear the roster down only after the state snapshot, so the defeat
            # payload shows who killed the player rather than an empty
            # battlefield.
            self._teardown_combat_roster()

            return result

        # Evaluate all combat events one final time when enemies are defeated
        # This allows events (like reinforcement spawners) to inject new enemies before victory
        if len(self.player.combat_list) == 0:
            # All enemies defeated — the move is done regardless of remaining cooldown beats.
            # Clearing current_move prevents initialize_combat(reinit=True), called later by
            # story events like Ch01PostRumbler, from re-executing a stale attack against the
            # newly spawned reinforcements.
            #
            # The main flush above ran while current_move was still attached and
            # deliberately skipped it. A wind-up cancelled because an ally kill
            # or a DoT felled the last enemy under it is discarded, never
            # flush-emitted — the swing never happened, and the fallback would
            # play a phantom attack over the empty battlefield. (If events
            # below spawn reinforcements, the fight continues and
            # _handle_victory's teardown never runs for it.)
            self._detach_current_move(self.player)
            if self.on_event_callback:
                # Use the bridge to GameService so results are consistent
                new_events = self.on_event_callback(self.player)
                if new_events:
                    state = self._adapter_state()
                    existing = state.get("events_triggered", [])
                    state["events_triggered"] = existing + new_events

            # After event callbacks run, any newly-spawned enemies that were added via
            # combat_engage() won't have a combat_position (they only got a legacy proximity
            # entry).  Initialize positions for them now so _synchronize_distances() won't
            # drop them from Jean's proximity dict on the next beat.
            new_enemies_without_position = [
                e
                for e in self.player.combat_list
                if not hasattr(e, "combat_position") or e.combat_position is None
            ]
            if new_enemies_without_position:
                try:
                    from src.coordinate_config import CoordinateSystemConfig

                    # Only pass the new (unpositioned) enemies — initialize_combat_positions
                    # unconditionally overwrites combat_position on every unit it receives,
                    # so passing the full combat_list would teleport already-placed combatants.
                    total = len(self.player.combat_list_allies) + len(
                        new_enemies_without_position
                    )
                    coord_config = CoordinateSystemConfig(self.player)
                    grid_w, grid_h = coord_config.get_dynamic_grid_size(total)
                    self.combat_grid_size = (grid_w, grid_h)
                    positions.initialize_combat_positions(
                        allies=[],
                        enemies=new_enemies_without_position,
                        scenario_type="standard",
                        grid_width=grid_w,
                        grid_height=grid_h,
                    )
                except Exception as e:
                    logger.warning("Position init for reinforcements failed: %s", e)
                # Immediately sync proximity so Attack.viable() can see new enemies on
                # the next get_available_moves() call without waiting for the next beat.
                try:
                    self._synchronize_distances()
                except Exception:
                    pass

        # Check if events triggered (BEFORE calling get_combat_state which consumes them)
        event_just_triggered = "events_triggered" in self._adapter_state()

        # ALWAYS handle victory when all enemies are defeated
        # (even if post-combat events like Ch01PostRumbler3 are firing).
        # Events should not suppress the victory state — the frontend needs
        # combat_end_summary to know when combat has ended.
        if len(self.player.combat_list) == 0 and self.player.in_combat:
            self._handle_victory()

            # Publish the terminal stream even when a post-combat event is
            # queued. The event dialog and victory state are independent; the
            # old path only streamed when no event was pending.
            result = self.get_combat_state()
            result["beat_states"] = beat_states
            self._stream_combat_result(result, beat_states, ended=True)
            # get_combat_state() consumes events_triggered; restore them so the
            # normal tail below can still return the pending event to the API.
            triggered_events = result.get("events_triggered")
            if triggered_events:
                self.player.combat_adapter_state["events_triggered"] = triggered_events

            # Return the terminal state immediately. If a post-combat event is
            # pending, its payload was restored above and travels with this result;
            # do not fall through and replay the same beat stream a second time.
            return result

        # Set up for next move selection if battle continues and no event is blocking
        if not event_just_triggered:
            self.awaiting_input = True
            self.input_type = "move_selection"
            self.available_options = self._get_available_moves()
            self.pending_move_index = None
            # Start async suggestion fetch (non-blocking)
            self.refresh_suggestions()
        else:
            # Events just fired (e.g., reinforcement wave spawned). Clear stale
            # pending-move state so when the player dismisses events and returns
            # to combat they get a fresh move_selection prompt instead of a
            # phantom target_selection loop with 0-damage attacks.
            #
            # Also reset any in-progress move (stages 1-2 = execute/recoil) back to
            # stage 0. When the beat loop breaks early on an event, the selected move
            # is left mid-execution. _handle_move_selection checks current_stage != 0
            # and returns "Move not ready yet", creating a permanent deadlock where the
            # interrupted move can never be selected again.
            if self.player.current_move is not None:
                try:
                    self.player.current_move.current_stage = 0
                    self.player.current_move.beats_left = 0
                except Exception:
                    pass
                # The main flush ran BEFORE this clear and skipped the
                # then-attached move. The event-interrupted move is cancelled,
                # not completed: its channel is discarded, never flush-emitted
                # — the fallback would play the reset move's full animation as
                # a phantom swing over the event dialog. (A channel that
                # resolved mid-recoil is dropped just as silently, as before.)
                self._detach_current_move(self.player)
            if self.player.in_combat:
                self.awaiting_input = True
                self.input_type = "move_selection"
                self.pending_move_index = None
                try:
                    self.available_options = self._get_available_moves()
                except Exception:
                    self.available_options = []
            else:
                # A post-victory event may still be pending, but combat input is
                # no longer valid. Do not advertise a phantom move-selection turn.
                self.awaiting_input = False
                self.input_type = None
                self.pending_move_index = None
                self.available_options = []

        # Final state capture (consumes events_triggered)
        result = self.get_combat_state()
        result["beat_states"] = beat_states
        self._stream_combat_result(result, beat_states)

        # Emit final state update
        if self.session_id:
            try:
                from flask import current_app

                if hasattr(current_app, "socketio"):
                    room = f"combat_{self.session_id}"
                    # combat:update is the legacy recovery channel. When a beat
                    # streamer exists, its seq-guarded resolved/ended event is
                    # authoritative and the duplicate unsequenced update could
                    # arrive late and clobber terminal state.
                    if self._beat_streamer is None:
                        current_app.socketio.emit("combat:update", result, room=room)

                    # If awaiting input, also emit turn notification
                    if self.awaiting_input:
                        current_app.socketio.emit(
                            "combat:turn",
                            {
                                "input_type": self.input_type,
                                "available_options_count": len(self.available_options),
                            },
                            room=room,
                        )
            except Exception as e:
                logger.warning("Failed to emit socket update after process_move: %s", e)

        return result

    def _process_initial_turns(self):
        """Process NPC turns if they go first."""
        # Simple speed check - if any enemy is faster, they go first
        player_speed = getattr(self.player, "speed", 10)

        # Sync distances before start
        self._synchronize_distances()

        for enemy in self.player.combat_list:
            enemy_speed = getattr(enemy, "speed", 5)
            if enemy_speed > player_speed:
                with self._capture_output():
                    self._process_npc_turns()
                break

    def _process_npc_turns(self):
        """Process all NPC turns (allies and enemies)."""
        from src.functions import refresh_stat_bonuses

        # Refresh stats
        for friendly in self.player.combat_list_allies:
            refresh_stat_bonuses(friendly)
        for enemy in self.player.combat_list:
            refresh_stat_bonuses(enemy)

        # Process friendly NPCs
        for ally in self.player.combat_list_allies:
            if ally != self.player and ally.is_alive():
                self._process_npc(ally)

        # Gorran's ambient combat flavor text (issue #367) — no-op when Gorran
        # isn't in the party. The cooldown must persist across beats, so it's
        # carried on the player between calls (mirrors the module's own
        # _prev_hp_for_flavor dynamic-attribute pattern on the NPC side). Never
        # let flavor text take down NPC turn processing — wrapped the same way
        # move_player() wraps game_tick_events()/recall_friends().
        try:
            cooldown = int(getattr(self.player, "_gorran_flavor_cooldown", 0) or 0)
            self.player._gorran_flavor_cooldown = gorran_flavor.maybe_combat_flavor(
                self.player, self.player.combat_beat, cooldown
            )
        except Exception as e:
            logger.warning("gorran_flavor combat hook failed: %s", e)
            self.player._gorran_flavor_cooldown = 0

        # Process enemies
        # Use a copy of the list because we might modify it (remove dead enemies)
        enemies_to_process = self.player.combat_list[:]

        for enemy in enemies_to_process:
            # If enemy is alive, process their turn
            if enemy.is_alive():
                self._process_npc(enemy)

            # Check if enemy died (was dead before or died during turn/recoil)
            # This check must happen regardless of whether they took a turn.
            # Consult check_revive() first (mirrors the player path above) so a
            # combatant carrying a revive state is not silently denied.
            if not enemy.is_alive() and not enemy.check_revive():
                enemy.die()
                if not enemy.is_alive():
                    # Death message is handled by enemy.die() -> print() -> captured by output capture
                    # Explicit logging removed to avoid duplication/mismatch

                    if enemy in self.player.current_room.npcs_here:
                        self.player.current_room.npcs_here.remove(enemy)

                    if enemy in self.player.combat_list:
                        self.player.combat_list.remove(enemy)

                    # Record the departure reason so beat streaming animates a
                    # death (not a silent/false exit) for combatants removed
                    # without an intervening snapshot (issue #436).
                    self._record_departure(enemy, "death")

                    # CleaveInstinct: mark that player killed an enemy (for next move's prep boost)
                    self.player._cleave_instinct_pending = True

                    for ally in self.player.combat_list_allies:
                        if enemy in ally.combat_proximity:
                            del ally.combat_proximity[enemy]

                    # Cleanup from player proximity as well to be safe
                    if (
                        hasattr(self.player, "combat_proximity")
                        and enemy in self.player.combat_proximity
                    ):
                        del self.player.combat_proximity[enemy]

    def _process_npc(self, npc):
        """Process a single NPC's turn."""
        npc.cycle_states()

        # Initialize combat_delay if it doesn't exist
        if not hasattr(npc, "combat_delay"):
            npc.combat_delay = 0

        if npc.combat_delay > 0:
            npc.combat_delay -= 1
        else:
            if npc.current_move is None:
                # Select target
                if not npc.friend:
                    npc.target = select_weighted_target(self.player.combat_list_allies)
                else:
                    npc.target = select_weighted_target(self.player.combat_list)

                if npc.is_stunned():
                    # Stunned NPCs (e.g. War Cry) skip move selection entirely for
                    # this beat, regardless of whether their class overrides
                    # select_move().
                    npc.current_move = moves.NpcRest(npc)
                elif self._npc_try_heal_ally(npc):
                    # Ally-healing check: use a consumable on a nearby friendly below threshold
                    return
                else:
                    # Select and cast move
                    npc.select_move()
                if npc.current_move:
                    npc.current_move.target = npc.target

                    # Store pending animation on the NPC; write() will pair it
                    # with the impact line printed during a future advance()
                    # call. Built by the same builder as the player cast, so a
                    # non-targeted NPC move (rest, self-buff) ships
                    # target_id: None instead of the beat-target the NPC
                    # happened to be holding.
                    setattr(
                        npc,
                        PENDING_ANIMATION_ATTR,
                        self._build_animation_data(npc, npc.current_move),
                    )

                    with self._capture_output():
                        # Tag entity so write() matches the cast prep text correctly
                        self.output_capture.active_entity = npc
                        if hasattr(npc.current_move, "cast") and callable(
                            npc.current_move.cast
                        ):
                            npc.current_move.cast()
                        self.output_capture.active_entity = None

        # Advance moves — tag active_entity so write() resolves the impact animation
        # to this NPC rather than any other combatant that also has _pending_animation.
        moves_to_advance = list(getattr(npc, "known_moves", []))
        if npc.current_move is not None and npc.current_move not in moves_to_advance:
            moves_to_advance.append(npc.current_move)

        self.output_capture.active_entity = npc
        try:
            for move in moves_to_advance:
                move.advance(npc)
        finally:
            # Always clear so a subsequent entity doesn't inherit this NPC's context
            self.output_capture.active_entity = None

    def _npc_try_heal_ally(self, npc) -> bool:
        """Check whether this NPC should spend its turn healing a nearby ally.

        Applies to any NPC that has consumable items in its inventory.  Returns
        True and executes the heal (consuming the item) if a valid target was
        found; returns False so normal move-selection proceeds otherwise.
        """
        import src.items as items_module

        inventory = getattr(npc, "inventory", [])
        consumables = [
            it
            for it in inventory
            if isinstance(it, items_module.Consumable) and hasattr(it, "use")
        ]
        if not consumables:
            return False

        # Build list of friendlies (allies share the same faction)
        if npc.friend:
            # Friendly NPC: allies are player + other friends; enemies are combat_list
            friendlies = list(getattr(self.player, "combat_list_allies", []))
        else:
            # Enemy NPC: allies are other enemies
            friendlies = list(getattr(self.player, "combat_list", []))

        # Find a living friendly below the heal threshold that is within range
        heal_target = None
        for friendly in friendlies:
            if friendly is npc or not friendly.is_alive():
                continue
            maxhp = getattr(friendly, "maxhp", 1) or 1
            hp_frac = getattr(friendly, "hp", maxhp) / maxhp
            if hp_frac >= ALLY_HEAL_THRESHOLD:
                continue
            dist = npc.combat_proximity.get(friendly, 9999)
            if dist > ITEM_USE_RANGE:
                continue
            # Prefer the most-injured friendly
            if heal_target is None:
                heal_target = friendly
            elif (getattr(friendly, "hp", 0) / maxhp) < (
                getattr(heal_target, "hp", 0) / (getattr(heal_target, "maxhp", 1) or 1)
            ):
                heal_target = friendly

        if heal_target is None:
            return False

        item = consumables[0]
        item_name = getattr(item, "name", "item")
        try:
            with self._capture_output():
                item.use(heal_target, user=npc)
        except Exception:
            logger.exception(
                "%s failed to use %s on %s", npc.name, item_name, heal_target.name
            )
            return False

        # Stacked consumables self-remove via the user= parameter when count
        # hits zero. This guard handles any item type that does NOT remove
        # itself inside use() (e.g. a future reusable NPC consumable).
        if item in inventory:
            inventory.remove(item)

        self._add_log_entry(
            self.player.combat_beat,
            f"{npc.name} uses {item_name} on {heal_target.name}!",
            "combat",
        )
        # An item use is not a Move, but its animation payload must obey the
        # same contract as every other cast, so it goes through the shared
        # builder with a pseudo-move targeted at the healed ally. The
        # animation type is pinned explicitly rather than left to the
        # builder's fallback ladder: the ladder's damaging-move branch keys on
        # name keywords, so a heal item whose name happens to contain one
        # ("...Strike Salve") would ship the attack animation for a heal.
        # stream_id inside the builder cannot mislabel the player or an ally.
        pseudo_move = SimpleNamespace(
            name=f"Use {item_name}",
            targeted=True,
            target=heal_target,
            web_animation=DEFAULT_ANIMATION,
        )
        self._emit_animation_log(
            self.player.combat_beat,
            self._build_animation_data(npc, pseudo_move),
        )
        return True

    def _update_heat(self):
        """Update the heat multiplier."""
        if self.player.heat < 1:
            amt = (1 - self.player.heat) / 20
            if amt < 0.001:
                amt = 0.001
            self.player.heat += amt
        elif self.player.heat > 1:
            amt = (self.player.heat - 1) / 20
            if amt < 0.001:
                amt = 0.001
            self.player.heat -= amt

    def refresh_suggestions(self):
        """Fetch tactical suggestions asynchronously without blocking combat."""
        import logging

        logger = logging.getLogger(__name__)

        if getattr(self.player, "suggestions_paused", False):
            return

        # Set loading state
        self.player.suggestions_loading = True
        self.player.suggested_moves = []  # Clear previous suggestions while loading

        # Increment generation counter to invalidate any in-flight requests
        with self._suggestion_lock:
            self._suggestion_generation += 1
            current_gen = self._suggestion_generation

        # Get flask app to pass to the thread
        try:
            from flask import current_app

            flask_app = current_app._get_current_object()
            logger.debug(
                f"Flask app context captured for suggestion thread (App: {flask_app})"
            )
        except Exception as e:
            logger.warning(f"Failed to capture flask app context: {e}")
            flask_app = None

        # Create and start a new thread for fetching suggestions
        def fetch_suggestions_worker():
            logger.debug(f"Suggestion worker started (Gen: {current_gen})")

            def run_with_context():
                logger.debug(f"Suggestion fetch started (Gen: {current_gen})")
                try:
                    # Calculate allowed suggestions count
                    count = getattr(self.player, "base_suggested_move_count", 1)
                    for m in self.player.known_moves:
                        if m.name in ["Strategic Insight", "Master Tactician"]:
                            count += 1

                    # Ensure combat_log exists
                    if not hasattr(self.player, "combat_log"):
                        self.player.combat_log = []

                    logger.debug(
                        f"Preparing strategist context: {len(self.player.combat_list)} enemies, {len(self.available_options)} available moves"
                    )
                    # Gather context
                    all_moves = self._get_available_moves()
                    ctx = {
                        "player": CombatantSerializer.serialize_combatant(self.player),
                        "enemies": [
                            CombatantSerializer.serialize_combatant(
                                e, reference=self.player
                            )
                            for e in self.player.combat_list
                        ],
                        # Allies in combat (friendly NPCs); empty list when fighting solo
                        "allies": [
                            CombatantSerializer.serialize_combatant(
                                a, reference=self.player
                            )
                            for a in getattr(self.player, "combat_list_allies", [])
                            if a is not self.player and getattr(a, "friend", False)
                        ],
                        "history": [
                            entry["message"] for entry in self.player.combat_log[-20:]
                        ],
                        "last_move": getattr(self.player, "last_move_summary", "None"),
                        # Only send moves that are available AND (if targeted) have
                        # at least one viable target — prevents TA from suggesting
                        # attacks that cannot resolve at execution time.
                        "available_moves": [
                            m
                            for m in all_moves
                            if isinstance(m, dict)
                            and m.get("available", True)
                            and (
                                not m.get("targeted")
                                or len(m.get("viable_targets", [])) > 0
                            )
                        ],
                        # Cooldown ETAs for key defensive moves that are currently
                        # unavailable — lets the LLM reason about whether to wait.
                        "defensive_cooldowns": {
                            m["name"]: m["cooldown_remaining"]
                            for m in all_moves
                            if isinstance(m, dict)
                            and not m.get("available", True)
                            and m.get("name") in ("Dodge", "Parry", "Withdraw")
                            and m.get("cooldown_remaining", 0) > 0
                        },
                        # Moves Jean cannot pay for at this fatigue. The
                        # strategist needs the *reason* offense is missing:
                        # priced out (only Rest changes that) reads very
                        # differently from out of range (Advance does). The
                        # test is affordability, not the `reason` string —
                        # a move that is both on cooldown and unaffordable
                        # is reported by `reason` as the cooldown only.
                        "fatigue_locked_moves": [
                            {
                                "name": m.get("name"),
                                "category": m.get("category"),
                                "fatigue_cost": m.get("fatigue_cost", 0),
                            }
                            for m in all_moves
                            if isinstance(m, dict)
                            and not m.get("available", True)
                            and (m.get("fatigue_cost") or 0) > self.player.fatigue
                        ],
                    }

                    logger.debug(f"Combat context keys: {list(ctx.keys())}")

                    # Fetch from strategist (this is the slow part)
                    suggestions = self.strategist.get_suggestions(
                        ctx, max_suggestions=count
                    )

                    # Filter out suggestions for moves that are not currently available
                    available_move_names = {
                        m["name"]
                        for m in self._get_available_moves()
                        if m.get("available", True)
                    }
                    suggestions = [
                        s
                        for s in suggestions
                        if s.get("move_name") in available_move_names
                    ]

                    # Store results (only if this generation is still current)
                    with self._suggestion_lock:
                        is_current = current_gen == self._suggestion_generation
                    if is_current:
                        self.player.suggested_moves = suggestions
                        self.player.suggestions_loading = False
                        logger.debug(
                            f"Suggestion fetch complete (Gen: {current_gen}, {len(suggestions)} suggestions)"
                        )

                        # Emit socket event to notify frontend that suggestions are ready
                        if self.session_id:
                            try:
                                if flask_app and hasattr(flask_app, "socketio"):
                                    logger.debug(
                                        f"Emitting {SUGGESTIONS_EVENT} to room combat_{self.session_id} ({len(suggestions)} suggestions)"
                                    )
                                    # Use the shared constant, not a literal:
                                    # both schemas define "combat:suggestions"
                                    # while this site emitted the legacy
                                    # "combat:suggestions_ready", so the client
                                    # listener never fired. Inert today (the
                                    # socket flag is off by default and GamePage
                                    # passes no onSuggestions) but it would have
                                    # failed silently the moment the flag went on
                                    # -- the HTTP path masks the miss.
                                    flask_app.socketio.emit(
                                        SUGGESTIONS_EVENT,
                                        {"suggested_moves": suggestions},
                                        room=f"combat_{self.session_id}",
                                    )
                                else:
                                    logger.warning(
                                        f"Cannot emit suggestions - flask_app is {flask_app} or socketio missing"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Error emitting {SUGGESTIONS_EVENT} event: {e}"
                                )
                        else:
                            logger.warning(
                                "Cannot emit suggestions - session_id is missing"
                            )

                except Exception as e:
                    logger.error(f"Error in async suggestion fetch: {e}", exc_info=True)
                    with self._suggestion_lock:
                        is_current = current_gen == self._suggestion_generation
                    if is_current:
                        self.player.suggested_moves = []
                        self.player.suggestions_loading = False
                        logger.info(
                            f"DEBUG: Reset suggestions_loading after error (Gen: {current_gen})"
                        )

            if flask_app:
                with flask_app.app_context():
                    run_with_context()
            else:
                run_with_context()

        import threading

        threading.Thread(target=fetch_suggestions_worker, daemon=True).start()

    def _handle_victory(self):
        """Handle combat victory."""
        self.player.in_combat = False
        self.awaiting_input = False
        self.player.fatigue = self.player.maxfatigue
        # Recharge single-use equip states (e.g. PhoenixRevive) consumed this battle
        self.player.recharge_equip_states()

        # Snapshot the tile where victory occurred so post-combat events fire on
        # the right tile even if the player moves before the next status poll.
        self._combat_tile = getattr(self.player, "current_room", None)

        # Calculate exp
        exp_summary = []
        exp_gained: Dict[str, int] = {}
        level_ups: List[Dict[str, Any]] = []
        for subtype, value in self.player.combat_exp.items():
            if value > 0:
                gained = int(value)
                exp_gained[subtype] = gained
                exp_summary.append(f"{subtype}: {gained}")
                maybe_events = self.player.gain_exp(gained, exp_type=subtype)
                if isinstance(maybe_events, list) and maybe_events:
                    level_ups.extend(maybe_events)
                self.player.combat_exp[subtype] = 0

        # Ally progression: party members mirror the total exp Jean banked this
        # fight (static, player-uncontrolled growth — see npc/_progression.py).
        # KO'd allies keep their full share by design.
        ally_progression: List[Dict[str, Any]] = []
        total_gained = sum(exp_gained.values())
        if total_gained > 0:
            for ally in self.player.combat_list_allies[1:]:
                try:
                    gain = getattr(ally, "gain_exp", None)
                    if gain is None:
                        continue
                    # The mixin owns the opt-in decision: non-progressing
                    # Friends (no growth_profile) return [] from gain_exp.
                    ally_progression.extend(
                        gain(total_gained, player_level=self.player.level)
                    )
                except Exception as e:
                    logger.warning(
                        "Ally progression failed for %s: %s",
                        getattr(ally, "name", "?"),
                        e,
                    )

        victory_msg = "Victory! "
        if exp_summary:
            victory_msg += "Gained exp: " + ", ".join(exp_summary)

        self._add_log_entry(self.output_capture.current_round, victory_msg, "system")

        for event in ally_progression:
            self._add_log_entry(
                self.output_capture.current_round,
                f"{event['name']} reached level {event['new_level']}!",
                "system",
            )
            for skill_name in event.get("skills_learned", []):
                self._add_log_entry(
                    self.output_capture.current_round,
                    f"{event['name']} has learned {skill_name}!",
                    "system",
                )

        # Aggregate combat drops collected during the encounter (API mode)
        drops_raw = getattr(self.player, "combat_drops", []) or []
        drops_by_name: Dict[str, int] = {}
        for d in drops_raw:
            name = (d or {}).get("name")
            qty = int((d or {}).get("quantity", 1) or 1)
            if not name:
                continue
            drops_by_name[name] = drops_by_name.get(name, 0) + max(0, qty)

        # Build a lookup of item objects on the current tile for detail enrichment
        tile = getattr(self.player, "current_room", None)
        tile_items = getattr(tile, "items_here", []) if tile else []
        tile_by_name: Dict[str, Any] = {}
        for _item in tile_items:
            _name = getattr(_item, "name", None)
            if _name and _name not in tile_by_name:
                tile_by_name[_name] = _item

        def _item_details(name: str) -> Dict[str, Any]:
            obj = tile_by_name.get(name)
            if not obj:
                return {}
            return {
                "type": getattr(obj, "type", getattr(obj, "maintype", "")),
                "subtype": getattr(obj, "subtype", ""),
                "weight": round(float(getattr(obj, "weight", 0.0) or 0.0), 2),
                "value": int(getattr(obj, "value", 0) or 0),
                "description": getattr(obj, "description", ""),
                "enchantment_count": int(getattr(obj, "_enchantment_count", 0) or 0),
            }

        items_dropped = [
            {"name": name, "quantity": qty, **_item_details(name)}
            for name, qty in sorted(drops_by_name.items(), key=lambda kv: kv[0].lower())
            if qty > 0
        ]

        # A CombatEventConfig-scripted encounter may have stashed narration to
        # show as its own conversation dialog immediately before the victory
        # dialog (issue #427). Consumed once so it doesn't leak into the next
        # (unrelated) fight's summary. isinstance-checked so MagicMock test
        # doubles (which auto-vivify any attribute access) can't trip this.
        pending_narrative = getattr(self.player, "_pending_victory_narrative", "")
        pre_victory_narrative = (
            pending_narrative if isinstance(pending_narrative, str) else ""
        )
        if pre_victory_narrative:
            del self.player._pending_victory_narrative

        # Capture a structured end-of-combat summary for the frontend
        self.player.combat_end_summary = {
            "id": str(uuid.uuid4()),
            "status": "victory",
            "message": "Victory!",
            "pre_victory_narrative": pre_victory_narrative,
            "exp_gained": exp_gained,
            "items_dropped": items_dropped,
            "level_ups": level_ups,
            "ally_progression": ally_progression,
            "attribute_points_available": int(
                getattr(self.player, "pending_attribute_points", 0) or 0
            ),
            "exp_to_next_level": int(
                (getattr(self.player, "exp_to_level", 0) or 0)
                - (getattr(self.player, "exp", 0) or 0)
            ),
            "attributes": {
                "strength_base": int(getattr(self.player, "strength_base", 0) or 0),
                "finesse_base": int(getattr(self.player, "finesse_base", 0) or 0),
                "speed_base": int(getattr(self.player, "speed_base", 0) or 0),
                "endurance_base": int(getattr(self.player, "endurance_base", 0) or 0),
                "charisma_base": int(getattr(self.player, "charisma_base", 0) or 0),
                "intelligence_base": int(
                    getattr(self.player, "intelligence_base", 0) or 0
                ),
            },
        }

        # Check for beta end: player just defeated the Lurker in Verdette Caverns.
        # Mirrors AfterDefeatingLurker.check_conditions() — no Lurker on tile,
        # but that tile still carries the AfterDefeatingLurker event marker.
        # Re-read current_room here (not the `tile` used for item lookups above)
        # in case exp processing or level-up callbacks updated the player's location.
        tile = getattr(self.player, "current_room", None)
        if tile:
            # Best-effort: a broken story/npc import must not crash victory
            # handling for unrelated fights.
            try:
                from src.npc import Lurker
                from src.story.ch02 import AfterDefeatingLurker

                has_lurker_event = any(
                    isinstance(e, AfterDefeatingLurker)
                    for e in getattr(tile, "events_here", [])
                )
                lurker_still_present = any(
                    isinstance(n, Lurker) for n in getattr(tile, "npcs_here", [])
                )
                if has_lurker_event and not lurker_still_present:
                    self.player.combat_end_summary["beta_end"] = True
            except Exception:
                pass

        # Reset any surviving tile NPCs that still carry aggro/in_combat flags from
        # this encounter.  Enemies that were defeated are already removed from the
        # tile by their death handler, but NPCs spawned mid-fight (e.g. by
        # PulsingGlandEvent) that were enrolled and defeated leave their flags set.
        # Any NPC still on the tile with aggro=True after victory is stale state
        # that would re-trigger combat on the next get_combat_status() poll.
        if tile:
            for npc in list(getattr(tile, "npcs_here", [])):
                # Leave friendly/merchant NPCs untouched.
                if getattr(npc, "friend", False):
                    continue
                npc.aggro = False
                npc.in_combat = False

        self._teardown_combat_roster()

    def _teardown_combat_roster(self):
        """End-of-combat roster reset, shared by the victory and defeat tails.

        (They previously carried verbatim-duplicated copies of this block —
        and on the defeat path the discard sat inside a try/except that
        swallowed it.)

        Discards every animation channel FIRST, while the roster still names
        everyone who was in the fight: the end-of-move flush deliberately
        leaves an in-flight move's channel armed (see
        _flush_pending_animations); once combat is over nothing will ever
        publish to it, and a pending dict can hold a reference to the
        combatant its last resolution landed on. The discard is post-fight
        reference hygiene and defense-in-depth -- ``Combatant.__getstate__``
        is what actually keeps ``_pending_animation`` out of every pickled
        save.

        Then clears enemies and preserves only living allies, so the party
        roster survives the fight without dead NPCs haunting recall_friends or
        the next combat's grid sizing, and clears in_combat on the survivors
        (the victory path's tile-reset loop only touches non-friend NPCs).
        event_temp_ally combatants (CombatEventConfig.ally_list, issue #427)
        are scoped to their one fight and never carried forward either.
        Invariant: combat_list_allies[0] is always the player.
        """
        self._discard_pending_animations()

        # Drop combat-effect events armed in rooms the player has since left.
        # player.combat_events is process-wide and no teardown path cleared it,
        # so a story chain armed in one fight stayed armed and fired in the
        # next one (issue #506). Scoped by origin room rather than blanket
        # cleared, so an event legitimately mid-chain in THIS room survives.
        purge_orphaned_combat_events(self.player)

        self.player.combat_list = []
        existing_allies = [
            a for a in self.player.combat_list_allies
            if a is not self.player
            and a.is_alive()
            and getattr(a, "event_temp_ally", False) is not True
        ]
        for ally in existing_allies:
            ally.in_combat = False
        self.player.combat_list_allies = [self.player] + existing_allies

    def _abortable_move(self):
        """The in-flight move the player may bail out of, or None.

        Only a move still winding up qualifies. Once it reaches execute there is
        nothing left to abandon -- the blow is being thrown -- and recoil and
        cooldown are the price already being paid.
        """
        move = getattr(self.player, "current_move", None)
        if move is None:
            return None
        if getattr(move, "current_stage", None) != 0:
            return None
        if getattr(move, "beats_left", 0) <= 0:
            return None
        stage_beats = getattr(move, "stage_beat", None) or []
        prep = stage_beats[0] if stage_beats else 0
        if prep < ABORTABLE_MIN_PREP_BEATS:
            return None
        return move

    def abort_current_move(self) -> Dict[str, Any]:
        """Abandon the move the player is winding up, paying its full cooldown.

        Delegates the actual state change to the engine: setting ``interrupted``
        and advancing the move once drives ``Move.advance``'s interrupt branch,
        which sends it to the cooldown stage, charges the whole cooldown and
        detaches it from the player. That branch returns before any beat
        processing, so no other move's cooldown drains here -- cooldowns must
        only tick inside the combat loop.
        """
        move = self._abortable_move()
        if move is None:
            return {"error": "No move in progress that can be aborted"}

        aborted_name = display_name_of(move)
        # What the player gives up is the wind-up already invested, not the
        # wind-up remaining: bailing at beat 20 of a 25-beat aim forfeits 20.
        stage_beats = getattr(move, "stage_beat", None) or [0]
        remaining = int(getattr(move, "beats_left", 0))
        forfeited = max(0, int(stage_beats[0]) - remaining)
        move.interrupted = True
        with self._capture_output():
            self.output_capture.active_entity = self.player
            move.advance(self.player)
            self.output_capture.active_entity = None
        # The interrupt branch detached the move; its never-resolved channel
        # is DISCARDED, not flushed. The flush's fallback emission exists for
        # a move that finished without resolving — here the swing was broken
        # off before it happened, and emitting would play the aborted move's
        # full animation the instant the player cancels it. (Re-clearing
        # current_move is a no-op after the engine's detach.)
        self._detach_current_move(self.player)
        self._add_log_entry(
            getattr(self.player, "combat_beat", 0),
            f"{self.player.name} breaks off {aborted_name}.",
            "system",
        )

        self.awaiting_input = True
        self.input_type = "move_selection"
        self.pending_move_index = None
        self.available_options = self._get_available_moves()

        result = self.get_combat_state()
        result["aborted"] = {
            "move": aborted_name,
            "beats_forfeited": forfeited,
            "beats_remaining_when_aborted": remaining,
            "cooldown_beats": int(getattr(move, "beats_left", 0)),
        }
        return result

    def _range_ring(self, move) -> Optional[int]:
        """Reach in feet for the client's range ring, or None for a melee move.

        ``Move.preview_reach`` owns what "reach" means for each move shape
        (weapon-derived effective range, an area swing's arc, a plain
        ``mvrange``); this only decides whether the number is worth drawing.
        Below ``MELEE_REACH_FT`` it is not -- a ring at 5 ft appears on nearly
        every move and carries no information.
        """
        preview_reach = getattr(move, "preview_reach", None)
        reach = preview_reach() if callable(preview_reach) else None
        if not isinstance(reach, (int, float)) or isinstance(reach, bool):
            return None
        if reach <= MELEE_REACH_FT:
            return None
        return int(reach)

    def _get_available_moves(self) -> List[Dict[str, Any]]:
        """Get list of all moves for the player with availability status."""
        moves = []

        # Get all known moves, not just viable ones
        for i, move in enumerate(self.player.known_moves):
            if getattr(move, "passive", False):
                continue
            is_viable = move.viable()

            is_targeted = getattr(move, "targeted", False)
            viable_targets = []
            if is_targeted and is_viable:
                viable_targets = self._get_available_targets(move)

            # Engine source of truth for the move's full commitment: how many
            # beats it locks the player into before another action can be
            # taken. `stage_beat` is `[prep, execute, recoil, cooldown]` by
            # convention (see Move.__init__ in src/moves/_base.py) — never
            # hardcode these durations here, and never leak the raw list/index
            # convention to the client (see `stage_beats` below). Values can
            # be floats (e.g. 3.5) and can be 0; both are valid and rendered
            # as-is.
            raw_stage_beat = getattr(move, "stage_beat", None)
            if not isinstance(raw_stage_beat, (list, tuple)):
                # Unset/mocked moves (e.g. test doubles that don't configure
                # stage_beat) fall back to "no declared commitment" rather
                # than crashing on len()/indexing a non-sequence.
                raw_stage_beat = []

            def _beat_at(idx, _raw=raw_stage_beat):
                if len(_raw) > idx:
                    val = _raw[idx]
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        return val
                return 0

            move_data = {
                "id": str(i),
                "index": i,
                "name": move.name,
                "display_name": display_name_of(move),
                "description": getattr(move, "description", ""),
                "category": getattr(move, "category", "Miscellaneous"),
                "fatigue_cost": move.fatigue_cost,
                "available": True,
                "reason": None,
                "targeted": is_targeted,
                "viable_targets": viable_targets,
                "requires_target_selection": is_targeted and len(viable_targets) > 1,
                "cooldown_remaining": 0,
                "cooldown_max": 0,
                # Every living candidate, in reach or not, each with its own
                # damage/hit preview and shortfall_ft -- see
                # _get_target_previews. viable_targets above stays the
                # range-filtered allow-list; this one is display-only.
                "target_previews": self._get_target_previews(move),
                # Area swings only (see _get_affected_previews).
                "affected_preview": self._get_affected_previews(move),
                # Reach in feet, drawn as a ring by the client -- but only for
                # a move that actually outreaches a sword; see MELEE_REACH_FT.
                "range_ring": self._range_ring(move),
                # Named fields, not the raw stage_beat list/index convention —
                # the client must never have to know stage_beat[0] means prep.
                "stage_beats": {
                    "prep": _beat_at(0),
                    "execute": _beat_at(1),
                    "recoil": _beat_at(2),
                    "cooldown": _beat_at(3),
                },
            }

            # Check various conditions that might make the move unavailable
            if move.current_stage == 3:
                cd_remaining = move.beats_left + 1 if move.beats_left > 0 else 1
                cd_max = (
                    raw_stage_beat[3] + 1 if len(raw_stage_beat) > 3 else cd_remaining
                )
                move_data["cooldown_remaining"] = cd_remaining
                move_data["cooldown_max"] = max(cd_max, cd_remaining)
                if move.beats_left > 0:
                    move_data["available"] = False
                    move_data["reason"] = f"Available in {move.beats_left + 1} beats"
                else:
                    move_data["available"] = False
                    move_data["reason"] = "Available next beat"
            elif move.fatigue_cost > 0 and self.player.fatigue < move.fatigue_cost:
                move_data["available"] = False
                move_data["reason"] = "Not enough fatigue"
            elif not is_viable:
                # Move is not viable - try to determine why
                move_data["available"] = False

                # Check for common reasons
                if is_targeted:
                    # Check if it's a range issue
                    mvrange = getattr(move, "mvrange", None)
                    if mvrange:
                        range_min, range_max = mvrange
                        enemies_in_range = any(
                            range_min <= dist <= range_max
                            for dist in self.player.combat_proximity.values()
                        )
                        if not enemies_in_range:
                            if range_max <= 5:
                                move_data["reason"] = "Enemy out of range (too far)"
                            else:
                                move_data["reason"] = "No valid target in range"
                        else:
                            move_data["reason"] = "Cannot use this move"
                    else:
                        move_data["reason"] = "No valid target"
                elif move.name == "Attack" and not getattr(
                    self.player, "eq_weapon", None
                ):
                    move_data["reason"] = "No weapon equipped"
                else:
                    move_data["reason"] = "Cannot use this move"

            moves.append(move_data)

        return moves

    def _move_range(self, move):
        """``(min, max)`` reach for ``move`` right now, in feet.

        Moves that compute their range dynamically (ranged weapons whose
        effective range extends past their melee wpnrange via
        range_base/range_decay) override ``get_effective_range_max()`` — see
        ``Move.get_effective_range_max`` in src/moves/_base.py.
        """
        # Default to adjacent when the move declares no usable range. The
        # try/except covers degraded stand-ins whose ``mvrange`` is not a pair
        # at all: this runs for every known move on every poll now, so it meets
        # doubles the old targeted-and-viable-only path never reached.
        range_min, range_max = 0, 5
        mvrange = getattr(move, "mvrange", None)
        try:
            if mvrange is not None and len(mvrange) == 2:
                range_min, range_max = mvrange
        except TypeError:
            pass

        # Resolved through getattr rather than called outright: the preview
        # builders below run this for *every* known move on every poll, not
        # just the targeted-and-viable ones the old target list covered, so it
        # now also meets degraded stand-ins (test doubles, half-built moves)
        # that carry no engine API at all. A missing hook means "no dynamic
        # range", which is exactly what the base Move returns.
        effective_range = getattr(move, "get_effective_range_max", None)
        if callable(effective_range):
            effective_max = effective_range(self.player)
            if effective_max is not None:
                range_max = effective_max
        return range_min, range_max

    def _build_target_entry(
        self, move, combatant, range_min, range_max, is_ally=False, affected=None
    ) -> Dict[str, Any]:
        """One target card: identity, reach, and what the move would do to it.

        The single builder behind both target lists this adapter publishes —
        :meth:`_get_available_targets` (the in-range allow-list a
        ``select_target`` command is validated against) and the wider
        ``target_previews`` set on each move (which *includes* out-of-reach
        enemies so the client can say "3 ft short" instead of greying a move
        out with no explanation). One builder means the two can never disagree
        about a combatant's hit chance, damage or distance.

        Field contract (the client reads these by name — see CLAUDE.md's
        wire-field-drift note):

        * ``in_range``      — bool; whether ``move`` can resolve against it now
        * ``shortfall_ft``  — int feet the target is beyond the move's reach,
                              ``None`` when in range (and also when the target
                              is *too close*, below ``range_min``: "3 ft short"
                              is not the right thing to render for that)
        * ``damage_preview``— ``{"min", "max", "lethal"}`` or ``None``; from
                              ``Move.preview_damage``, recomputed on the spot
        * ``hit_chance``    — integer percent, **omitted** (not null) when the
                              move rolls none, matching the field's pre-existing
                              behaviour on this card
        """
        distance = self.player.combat_proximity.get(combatant, 0)
        in_range = range_min <= distance <= range_max
        entry = {
            "id": CombatantSerializer.stream_id(combatant),
            "name": combatant.name,
            "distance": distance,
            "is_ally": is_ally,
            "health": {
                "current": getattr(combatant, "hp", getattr(combatant, "health", 0)),
                "max": getattr(
                    combatant, "maxhp", getattr(combatant, "max_health", 100)
                ),
            },
            "in_range": in_range,
            "shortfall_ft": (
                int(distance - range_max) if distance > range_max else None
            ),
            # Move.preview_damage (src/moves/_base.py) is the single source of
            # this number for every move, exactly as preview_hit_chance is for
            # the one below it. It reads facing, heat, resistance, protection
            # and hp live, so this is the value for *this* poll -- never a
            # figure frozen when the move was first offered.
            #
            # Gated on in_range because this builder now also describes targets
            # the move cannot reach: a swing that cannot land has no damage and
            # no hit chance, only a shortfall. The engine guards this too (see
            # Move._within_reach) -- both, because most attacks' viable() asks
            # only whether *some* enemy is in range and so cannot answer the
            # per-target question on its own.
            "damage_preview": (
                # The affected set rides down only on the area path, where the
                # four overrides accept it -- it spares each card a fresh
                # hostiles_in_arc scan for a set this adapter already computed.
                # Targeted moves never receive the kwarg, so their unchanged
                # preview_damage(target) signatures are untouched.
                (
                    move.preview_damage(combatant, affected=affected)
                    if affected is not None
                    else move.preview_damage(combatant)
                )
                if in_range and hasattr(move, "preview_damage")
                else None
            ),
        }

        # Add hit chance when the move can estimate one for this target.
        # Move.preview_hit_chance (src/moves/_base.py) is the single
        # source of this number for every targeted move -- it delegates
        # to calculate_hit_chance() for moves that define one (ShootBow)
        # and otherwise mirrors that move's own execute() to-hit path.
        # Previously gated on verbose_targeting, which only ShootBow
        # set, so every other targeted move showed no accuracy estimate
        # at all in the target-selection dialog.
        if in_range and hasattr(move, "preview_hit_chance"):
            hit_chance = move.preview_hit_chance(combatant)
            if hit_chance is not None:
                entry["hit_chance"] = hit_chance
        return entry

    def _candidate_targets(self, move):
        """Every combatant ``move`` may legally be pointed at, range aside.

        Iterates ``combat_list`` rather than ``combat_proximity`` to be sure of
        using the correct enemy instances, and includes allies only when the
        move explicitly accepts them (e.g. Advance for healing setup).
        """
        candidates = [
            enemy
            for enemy in self.player.combat_list
            if enemy is not self.player and enemy.is_alive()
        ]
        allies = []
        if getattr(move, "accepts_ally_target", False):
            allies = [
                ally
                for ally in self.player.combat_list_allies
                if ally is not self.player and ally.is_alive()
            ]
        return candidates, allies

    def _get_available_targets(self, move) -> List[Dict[str, Any]]:
        """Targets ``move`` can act on right now — the adapter's allow-list.

        Deliberately range-filtered: :meth:`_resolve_target_from_options`
        validates every client-supplied ``target_id`` against exactly this
        list, so an out-of-reach combatant must never appear here. The wider,
        unfiltered set lives in ``target_previews`` (see
        :meth:`_get_target_previews`), which is display-only.
        """
        range_min, range_max = self._move_range(move)
        enemies, allies = self._candidate_targets(move)
        targets = [
            entry
            for entry in (
                self._build_target_entry(move, enemy, range_min, range_max)
                for enemy in enemies
            )
            if entry["in_range"]
        ]
        targets += [
            entry
            for entry in (
                self._build_target_entry(move, ally, range_min, range_max, is_ally=True)
                for ally in allies
            )
            if entry["in_range"]
        ]

        # Sort by distance
        targets.sort(key=lambda t: t["distance"])
        return targets

    def _get_target_previews(self, move) -> List[Dict[str, Any]]:
        """Every living candidate for ``move``, in reach or not.

        Display-only, and the reason it exists: a move greyed out because the
        one enemy is a few feet too far is indistinguishable, in
        ``_get_available_targets``, from a move with no target at all — both
        publish an empty list. This one carries the out-of-reach combatants
        with their ``shortfall_ft``, so the client can render the distance the
        player has to close.
        """
        if not getattr(move, "targeted", False):
            return []
        enemies, allies = self._candidate_targets(move)
        if not enemies and not allies:
            return []
        range_min, range_max = self._move_range(move)
        previews = [
            self._build_target_entry(move, enemy, range_min, range_max)
            for enemy in enemies
        ]
        previews += [
            self._build_target_entry(move, ally, range_min, range_max, is_ally=True)
            for ally in allies
        ]
        previews.sort(key=lambda t: t["distance"])
        return previews

    def _get_affected_previews(self, move) -> List[Dict[str, Any]]:
        """The set an *area* move would resolve against, one card each.

        Empty for a targeted move: its affected set is the single target the
        player picks, already published in ``viable_targets``. Area swings have
        no ``self.target`` to preview (it is the user), so without this the
        client has nothing at all to show for a spin or a cone —
        ``Move.preview_affected`` is what makes them previewable.
        """
        if getattr(move, "targeted", False):
            return []
        preview_affected = getattr(move, "preview_affected", None)
        if not callable(preview_affected):
            return []
        affected = preview_affected()
        # The hook's contract is a list of combatants; anything else (a
        # degraded stand-in returning a bare sentinel) is treated as "nothing
        # to preview" rather than iterated blindly.
        if not isinstance(affected, (list, tuple)) or not affected:
            return []
        range_min, range_max = self._move_range(move)
        # One list object, shared: it is both iterated below and passed as the
        # per-card `affected` kwarg (a tuple-returning hook is normalized too).
        affected = list(affected)
        return [
            self._build_target_entry(
                move, combatant, range_min, range_max, affected=affected
            )
            for combatant in affected
        ]

    def _all_combatants(self) -> List[Any]:
        """Return a flat list of every entity currently in combat (player + allies + enemies)."""
        return (
            [self.player]
            + list(getattr(self.player, "combat_list", []))
            + list(getattr(self.player, "combat_list_allies", []))
        )

    @contextlib.contextmanager
    def _capture_output(self):
        """Context manager to capture narration output and sync to player log.

        Engine combat moves emit through the narration sink rather than stdout.
        We register a live listener so each message is handed to the capture
        object the instant it is emitted — preserving per-entity animation
        attribution via ``output_capture.active_entity``.
        """
        from src.narration import capture_narration

        with capture_narration(
            listener=lambda entry: self.output_capture.write(entry.get("text", ""))
        ):
            yield

        # Sync captured entries to player log (with deduplication)
        new_entries = self.output_capture.get_log()
        if new_entries:
            current_beat = getattr(self.player, "combat_beat", 0)
            for entry in new_entries:
                self._add_log_entry(
                    current_beat,
                    entry["message"],
                    "combat",
                    self.current_beat_state_index,
                    timestamp=entry.get("timestamp"),
                )
                if entry.get("trigger_animation") and "animation_data" in entry:
                    animation_data = entry["animation_data"]
                    self._emit_animation_log(current_beat, animation_data)

            # Clear capture for next time
            self.output_capture.clear()

    def get_combat_state(self) -> Dict[str, Any]:
        """
        Get the current combat state for the frontend.
        """
        # Serialize combat state (allies excludes the player who is always index 0)
        battle_state = CombatStateSerializer.serialize_combat_state(
            self.player,
            self.player.combat_list,
            current_turn_index=0,  # Not used in API version
            round_number=getattr(self.player, "combat_beat", 0),
            allies=self.player.combat_list_allies[1:],
        )

        # Add API-specific fields
        # combat_id rides in battle_state (not the top level) so the client's
        # transformCombatData spread carries it through on every poll; a
        # top-level key would be dropped by its whitelist.
        battle_state["combat_id"] = self.combat_id
        # Same reason: emitted top-level, map_size was dropped by
        # transformCombatData's whitelist, so Battlefield's `combat?.map_size`
        # was always undefined and BattlefieldGrid fell back to deriving the
        # arena from the bounding box of current positions — which means a
        # dynamically-sized grid rendered at the wrong size and *resized
        # mid-fight* whenever a combatant moved past the previous extent.
        battle_state["map_size"] = self.combat_grid_size[0]
        battle_state["beat"] = getattr(self.player, "combat_beat", 0)
        # round(), not int(). Binary floats mean 68 of the 951 two-decimal
        # heat values in [0.50, 10.00] land just under their exact product --
        # int(1.15 * 100) is 114, not 115 -- so truncating made this field
        # disagree with the float multiplier the client actually reads for
        # about 7% of heats.
        battle_state["heat"] = round(self.player.heat * 100)
        abortable = self._abortable_move()
        battle_state["abortable_move"] = (
            {
                "name": display_name_of(abortable),
                "beats_left": int(getattr(abortable, "beats_left", 0)),
                "prep_beats": int((getattr(abortable, "stage_beat", None) or [0])[0]),
                "beats_invested": max(
                    0,
                    int((getattr(abortable, "stage_beat", None) or [0])[0])
                    - int(getattr(abortable, "beats_left", 0)),
                ),
                "cooldown_beats": int(
                    (getattr(abortable, "stage_beat", None) or [0, 0, 0, 0])[3]
                ),
            }
            if abortable is not None
            else None
        )
        battle_state["awaiting_input"] = self.awaiting_input
        battle_state["input_type"] = self.input_type
        # Recomputed here rather than served from the stored copy: the move
        # cards carry live previews (damage bounds, lethality, hit chance,
        # shortfall) and the stored list was minted when the player was last
        # asked to choose. Between that moment and this poll the target can
        # have been chipped down, Jean's heat can have moved and the
        # battlefield can have turned -- a frozen preview would keep promising
        # the old numbers. Only the move-selection list is rebuilt; the other
        # input types hold direction/number options with nothing live in them.
        battle_state["available_options"] = self.available_options
        if self.input_type == "move_selection" and isinstance(
            self.available_options, list
        ):
            try:
                battle_state["available_options"] = self._get_available_moves()
            except Exception:
                # Falling back to the stored copy rather than failing the poll:
                # this is the read path the client hits continuously, and a
                # slightly stale preview is a far better outcome than a combat
                # state the client cannot render at all. The execute path
                # guards the same call for the same reason.
                logger.warning(
                    "Failed to refresh move previews; serving the stored "
                    "option list",
                    exc_info=True,
                )

        # Include check_data if available (from Check move)
        adapter_state = self._adapter_state()
        if "check_data" in adapter_state:
            battle_state["check_data"] = adapter_state["check_data"]
            # Clear check_data after including it once
            del adapter_state["check_data"]

        grid_size = self.combat_grid_size
        result: Dict[str, Any] = {
            "combat_active": self.player.in_combat,
            # Retained for any direct consumer of the raw response shape; the
            # copy the web client actually reads lives in battle_state above,
            # because this top-level one never survives transformCombatData.
            "map_size": grid_size[0],
            "battle_state": battle_state,
            "beat_states": [battle_state],  # Initial state as a single beat state
            "log": getattr(self.player, "combat_log", []),
            "suggested_moves": getattr(self.player, "suggested_moves", []),
            "suggestions_loading": getattr(self.player, "suggestions_loading", False),
            "last_move_outcome": getattr(self.player, "last_move_summary", ""),
            "last_move_name": getattr(self.player, "last_move_name", ""),

            "last_move_target_id": getattr(self.player, "last_move_target_id", None),
        }

        # Include triggered events if any (narrative pause)
        if "events_triggered" in adapter_state:
            result["events_triggered"] = adapter_state["events_triggered"]
            # Clear after including
            del adapter_state["events_triggered"]

        # Include end-of-combat summary (victory/defeat) if present
        if not self.player.in_combat and getattr(
            self.player, "combat_end_summary", None
        ):
            summary = self.player.combat_end_summary
            # Refresh dynamic values if it's a victory
            if summary.get("status") == "victory":
                summary["attribute_points_available"] = int(
                    getattr(self.player, "pending_attribute_points", 0) or 0
                )
                summary["exp_to_next_level"] = int(
                    (getattr(self.player, "exp_to_level", 0) or 0)
                    - (getattr(self.player, "exp", 0) or 0)
                )
                summary["attributes"] = {
                    "strength_base": int(getattr(self.player, "strength_base", 0) or 0),
                    "finesse_base": int(getattr(self.player, "finesse_base", 0) or 0),
                    "speed_base": int(getattr(self.player, "speed_base", 0) or 0),
                    "endurance_base": int(
                        getattr(self.player, "endurance_base", 0) or 0
                    ),
                    "charisma_base": int(getattr(self.player, "charisma_base", 0) or 0),
                    "intelligence_base": int(
                        getattr(self.player, "intelligence_base", 0) or 0
                    ),
                }
            result["end_state"] = summary

        return result
