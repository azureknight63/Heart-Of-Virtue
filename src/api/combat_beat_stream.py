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
    DEFAULT_ANIMATION,
    ENDED_EVENT,
    RESOLVED_EVENT,
    build_beat,
    diff_combatants,
)

logger = logging.getLogger(__name__)


def _beat_animations(log_entries):
    """Every animation dict in a beat's log, in the order the engine emitted it.

    This used to return only the LAST one, which lost two different things.
    A multi-target swing resolves once per enemy and appends one animation
    carrier per resolution, so "last" was the last enemy's — the move's own
    animation and every other landing were dropped on this channel. And because
    a beat's log holds the player's move *and* the NPC turns that follow it, the
    last animation in an ordinary beat is usually an NPC's, so even a plain
    one-target swing was reported under the wrong actor and the wrong animation.

    The first animation is the one that opened the beat and names the headline
    actor. The rest are a mix: some are that actor's further resolutions, but
    in an ordinary beat many are OTHER combatants' animations from the turns
    that followed — which is exactly why ``stream_beats`` filters this list by
    ``source_id`` before treating anything in it as the swing's resolutions.
    """
    return [
        entry["animation"]
        for entry in (log_entries or [])
        if entry.get("animation")
    ]


def _last_message(log_entries):
    """Return the most recent non-empty log message, or an empty string."""
    for entry in reversed(log_entries or []):
        message = entry.get("message")
        if message:
            return message
    return ""


def _derive_outcome(anim, hp_changes, killed, target_id):
    """Use the engine-tracked outcome when present; else infer from the diff.

    The engine tag is authoritative and is what the client resolves its impact
    cue and strike flash from. The HP/kill diff below is only a fallback for
    beats that carry no tagged animation at all, and it can distinguish nothing
    finer than a landed hit from a whiff — so it is deliberately limited to
    ``hit`` / ``miss``.

    Every other member of ``OUTCOMES`` is knowable only from the tag, because
    none of them is visible in an HP delta: ``glance`` (landed, but deflected
    for half damage) and ``absorb`` (fully shrugged off) both produce an HP
    change the diff would read as a plain hit or a plain miss, and
    ``parry``/``block``/``deflect``/``crit`` are engine decisions with no
    distinguishing footprint in the snapshot either. Do not enumerate the
    vocabulary here — ``OUTCOMES`` in src/api/schemas/combat_beat.py is the list,
    and this docstring has already gone stale against it once by omitting
    ``glance``.
    """
    if anim and anim.get("outcome"):
        return anim["outcome"]
    # Only the resolution's OWN target counts. Answering "hit" whenever
    # anything at all died in the beat made a whiffed second landing read as a
    # hit the moment the first landing killed.
    if target_id is not None and target_id in killed:
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
            animations = _beat_animations(snapshot.get("log"))
            anim = animations[0] if animations else None

            if anim is None and not hp_changes and not killed and not status_changes:
                self._last = curr
                continue

            actor_id = anim.get("source_id") if anim else None
            target_id = anim.get("target_id") if anim else None
            web_animation = (
                anim.get("type") if anim else None
            ) or DEFAULT_ANIMATION
            has_swing = bool(target_id) and target_id != actor_id

            # A beat's log holds the headline actor's move AND the other
            # combatants' turns, so only the animations sharing the headline
            # ``actor_id`` are this swing's resolutions: one per target it
            # reached, each carrying the outcome AND the combatant it resolved
            # against so the client can fan a full animation per landing. The
            # other actors' animations are deliberately excluded — folding
            # them in would replay their outcomes under this actor's animation.
            own_animations = [
                animation
                for animation in animations
                if animation.get("source_id") == actor_id
            ]
            resolutions = [
                {
                    "outcome": _derive_outcome(
                        animation, hp_changes, killed, animation.get("target_id")
                    ),
                    "target_id": animation.get("target_id"),
                }
                for animation in own_animations
            ] or [
                {
                    "outcome": _derive_outcome(
                        anim, hp_changes, killed, target_id
                    ),
                    "target_id": target_id,
                }
            ]

            beat = build_beat(
                seq=self._next_seq(),
                actor_id=actor_id,
                target_id=target_id,
                web_animation=web_animation,
                # The headline outcome is derived by build_beat from the first
                # resolution — passing it here too keeps the call self-evident.
                outcome=resolutions[0]["outcome"],
                hp_changes=hp_changes,
                killed=killed,
                status_changes=status_changes,
                log_line=_last_message(snapshot.get("log")),
                has_swing=has_swing,
                outcomes=resolutions,
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
            web_animation="death" if killed else DEFAULT_ANIMATION,
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
        payload = dict(state or {})
        payload.pop("beat_states", None)
        # Assign seq last so the streamer's authoritative sequence number always
        # wins over any stray "seq" key that might appear in the state payload.
        payload["seq"] = self._next_seq()
        self._emit(RESOLVED_EVENT, payload)

    def emit_ended(self, end_state):
        """Emit victory/defeat resolution."""
        payload = dict(end_state or {})
        # Assign seq last so it can't be clobbered by an incoming "seq" key.
        payload["seq"] = self._next_seq()
        self._emit(ENDED_EVENT, payload)
