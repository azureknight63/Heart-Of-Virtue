"""Combat beat streaming — snapshot transitions → SocketIO emissions (#436).

Kept separate from ``ApiCombatAdapter`` so the snapshot→beat logic is unit
testable with fake snapshots. The adapter instantiates one ``CombatBeatStreamer``
per combat when ``COMBAT_SOCKET_STREAMING`` is on and a ``socketio`` + session
are available, seeds it with the initial combatant snapshot, then hands it each
move's ``beat_states`` (via :meth:`stream_beats`) plus the terminal state
(:meth:`emit_resolved` / :meth:`emit_ended`).

See docs/development/combat-streaming-plan.md.
"""

import logging

from src.api.schemas.combat_beat import (
    BEAT_EVENT,
    ENDED_EVENT,
    RESOLVED_EVENT,
    build_beat,
    diff_combatants,
)

logger = logging.getLogger(__name__)


def _last_animation(log_entries):
    """Return the animation dict of the most recent animated log entry, or None."""
    for entry in reversed(log_entries or []):
        anim = entry.get("animation")
        if anim:
            return anim
    return None


def _last_message(log_entries):
    """Return the most recent non-empty log message, or an empty string."""
    for entry in reversed(log_entries or []):
        message = entry.get("message")
        if message:
            return message
    return ""


def _derive_outcome(anim, hp_changes, killed, target_id):
    """Use the engine-tracked outcome when present; else infer from the diff.

    parry/block/deflect/crit/absorb are only knowable from the engine's own
    outcome tag; the diff can only distinguish a landed hit from a whiff, so the
    fallback is deliberately limited to ``hit`` / ``miss``.
    """
    if anim and anim.get("outcome"):
        return anim["outcome"]
    if killed:
        return "hit"
    for change in hp_changes:
        if change.get("id") == target_id and change.get("delta", 0) < 0:
            return "hit"
    return "miss"


class CombatBeatStreamer:
    """Emits the combat beat protocol from serialized snapshot transitions."""

    def __init__(self, socketio, room, initial_combatants=None):
        self._socketio = socketio
        self._room = room
        self._seq = 0
        self._last = list(initial_combatants or [])

    def _next_seq(self):
        self._seq += 1
        return self._seq

    def _emit(self, event, payload):
        try:
            self._socketio.emit(event, payload, room=self._room)
        except Exception:
            # Streaming must never break combat resolution; log and continue.
            logger.exception("combat beat emit failed for %s", event)

    def stream_beats(self, beat_states):
        """Emit one ``combat:beat`` per visual/audible snapshot transition.

        Snapshots that change nothing observable (pure system-message beats with
        no animation and no HP/status change) advance the baseline silently.
        """
        for snapshot in beat_states or []:
            curr = snapshot.get("combatants", [])
            hp_changes, killed, status_changes = diff_combatants(self._last, curr)
            anim = _last_animation(snapshot.get("log"))

            if anim is None and not hp_changes and not killed and not status_changes:
                self._last = curr
                continue

            actor_id = anim.get("source_id") if anim else None
            target_id = anim.get("target_id") if anim else None
            web_animation = (anim.get("type") if anim else None) or "pulse"
            has_swing = bool(target_id) and target_id != actor_id

            beat = build_beat(
                seq=self._next_seq(),
                actor_id=actor_id,
                target_id=target_id,
                web_animation=web_animation,
                outcome=_derive_outcome(anim, hp_changes, killed, target_id),
                hp_changes=hp_changes,
                killed=killed,
                status_changes=status_changes,
                log_line=_last_message(snapshot.get("log")),
                has_swing=has_swing,
            )
            self._emit(BEAT_EVENT, beat)
            self._last = curr

    def reconcile_final(self, final_combatants, departures=None):
        """Emit a closing beat for exits/changes not captured by a snapshot.

        Some combatants leave the roster without an intervening beat_state — e.g.
        an enemy dying to poison on its own turn, or (in future) fleeing/warping.
        Absence alone can't tell death from an alive-exit, so ``departures`` (an
        engine-recorded ``{id: reason}`` map) classifies each: ``"death"`` →
        ``killed`` (death animation + SFX); any other reason → ``departed`` (drop
        the token, no death sound). Absences with no recorded reason default to a
        non-fatal ``"removed"`` so a death is never fabricated. No-op when
        nothing is outstanding.
        """
        departures = departures or {}
        hp_changes, killed, status_changes = diff_combatants(
            self._last, final_combatants
        )

        final_ids = {c.get("id") for c in (final_combatants or [])}
        departed = []
        for prev in self._last:
            cid = prev.get("id")
            if cid in final_ids or prev.get("hp", 0) <= 0:
                # Still present, or already-dead (its death was already reported).
                continue
            reason = departures.get(cid, "removed")
            if reason == "death":
                hp_changes.append({"id": cid, "delta": -prev.get("hp", 0)})
                killed.append(cid)
            else:
                departed.append({"id": cid, "reason": reason})

        if not (hp_changes or killed or departed or status_changes):
            self._last = list(final_combatants or [])
            return

        beat = build_beat(
            seq=self._next_seq(),
            actor_id=None,
            target_id=killed[0] if killed else None,
            web_animation="death" if killed else "pulse",
            outcome="hit" if killed else "miss",
            hp_changes=hp_changes,
            killed=killed,
            departed=departed,
            status_changes=status_changes,
            log_line="",
            has_swing=False,
        )
        self._emit(BEAT_EVENT, beat)
        self._last = list(final_combatants or [])

    def emit_resolved(self, state):
        """Emit the terminal authoritative state (beats already streamed)."""
        payload = {"seq": self._next_seq()}
        payload.update(state or {})
        payload.pop("beat_states", None)
        self._emit(RESOLVED_EVENT, payload)

    def emit_ended(self, end_state):
        """Emit victory/defeat resolution."""
        payload = {"seq": self._next_seq()}
        payload.update(end_state or {})
        self._emit(ENDED_EVENT, payload)
