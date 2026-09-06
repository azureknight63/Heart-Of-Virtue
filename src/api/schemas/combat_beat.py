"""Combat beat streaming protocol — Python source of truth (issue #436).

Defines the payload shapes for the SocketIO events the engine streams during
combat, the machine-readable codes its ``error`` event carries, plus pure
builders/validators. The frontend mirror lives at
``frontend/src/utils/combatBeatSchema.js``; ``tests/test_combat_beat_schema.py``
asserts the two stay in parity so the wire contract can't silently drift.

See docs/development/combat-streaming-plan.md.
"""

# ── Event names ─────────────────────────────────────────────────────────────
#
# EVERY socket event name that crosses the Python/JS boundary belongs here, not
# just the beat stream. A constants module holding *some* of them is worse than
# one holding none: it tells the reader the parity guard is complete when it is
# not. Each constant must be declared on its own line -- the guard in
# tests/test_combat_beat_schema.py walks module-level ``ast.Assign`` nodes with
# an ``ast.Name`` target, so ``A, B = "x", "y"`` would slip past it silently.
#
# Defining a name here is only half the job: the guard checks that a constant
# exists and that its value matches the mirror, never that anybody uses it. A
# constant nobody imports is decoration. Replace the literal at the emit/listen
# site too.

# The ordered beat stream (server -> client).
BEAT_EVENT = "combat:beat"
RESOLVED_EVENT = "combat:resolved"
ENDED_EVENT = "combat:ended"
SUGGESTIONS_EVENT = "combat:suggestions"
ERROR_EVENT = "error"

# Room membership handshake. ``JOINED_EVENT`` is what resets the client's
# re-handshake budget (``rehandshakes = 0`` in useCombatSocket.js), so renaming
# it server-side does not fail loudly -- the client simply never hears the ack,
# burns its three retries and degrades to the 8s HTTP poll for the rest of the
# session, which looks like "streaming is a bit laggy" rather than a break.
JOIN_EVENT = "join_combat"
JOINED_EVENT = "joined_combat"

# Legacy recovery channel: a full serialized battle state, emitted only when no
# beat streamer is attached. It carries at least as much as a beat does, so it
# is as much a contract as BEAT_EVENT is.
UPDATE_EVENT = "combat:update"

# Server-only emitters and handlers below. Nothing in frontend/src listens for
# or emits any of these today; they are named here anyway so this module is the
# whole vocabulary rather than a subset, and they are listed in that test's
# _PY_ONLY_CONSTANTS with the same reason. If a client consumer ever appears,
# mirror the constant in combatBeatSchema.js and drop it from that set.
STARTED_EVENT = "combat:started"
LOG_EVENT = "combat:log"
TURN_EVENT = "combat:turn"
LEAVE_EVENT = "leave_combat"
LEFT_EVENT = "left_combat"
PING_EVENT = "ping_combat"
PONG_EVENT = "pong_combat"

# ── ``error`` payload codes ─────────────────────────────────────────────────
#
# The socket ``error`` payload carries BOTH a human-readable ``message`` and
# one of these codes; the client keys its behaviour off the code and never off
# the prose. It used to have no choice but the prose, and substring-matching it
# conflated two conditions that call for opposite responses:
#
# * ``ERROR_SESSION_MISSING`` — the handshake carried no credential at all.
#   That is a *transport* failure, not an authentication one: the cookie is
#   ``Path=/`` precisely because the handshake is served from ``/socket.io/``
#   outside the SPA's base path (see src/api/session_cookie.py), so a path
#   scoping regression, a proxy that drops the header, or a cross-origin dev
#   setup where SameSite withholds it all produce this while every HTTP request
#   keeps working. Logging the player out over it would throw them to the login
#   screen out of a live fight for a fault that costs nothing but animation.
# * ``ERROR_SESSION_INVALID`` — a credential arrived and names no live session
#   (expired, or dropped by a server restart). The player really is signed out.
#
# Before the codes existed, the two messages were "Missing or invalid session
# credentials" (since reworded) and "Invalid session" (still the wording for
# ERROR_SESSION_INVALID). Note that the FIRST contains the substring "invalid
# session", so the client's prose test matched it through the wrong clause.
# Keep any future wording free of that kind of accident — but the codes, not
# the wording, are the contract.
ERROR_SESSION_MISSING = "session_missing"
ERROR_SESSION_INVALID = "session_invalid"

# Top-level ``combat:beat`` fields (this tuple documents the shape).
BEAT_FIELDS = (
    "seq",
    "actor_id",
    "target_id",
    "web_animation",
    "outcome",
    "hp_changes",
    "killed",
    "departed",
    "status_changes",
    "log_line",
    "sfx",
)

# Reasons a combatant leaves the battlefield. ``death`` is the only fatal one
# (drives the death animation + SFX via ``killed``); the rest are alive-exits
# that remove the token without a death animation/sound.
DEPARTURE_REASONS = (
    "death",
    "fled",
    "warped",
    "removed",
)

# Attack/resolution outcomes an ``impact`` SFX emission resolves against.
# ``glance`` is a blow that landed but deflected for half damage; it is a
# distinct sonic and visual event from a solid ``hit``, and ``absorb`` (a blow
# the target shrugged off entirely) must never play the flesh-impact cue.
OUTCOMES = (
    "hit",
    "miss",
    "parry",
    "block",
    "deflect",
    "crit",
    "glance",
    "absorb",
)

# Semantic SFX emission kinds. The client maps each to a concrete cue; the
# engine only asserts what happened and in what order (see plan decision #4).
SFX_KINDS = (
    "swing",
    "impact",
    "status",
    "heal",
    "death",
)

#: Ceiling on the per-target emissions one beat may fan out into — applied
#: server-side to each per-target loop of the SFX chain (the impact
#: resolutions, the landed statuses, and the deaths) and client-side when
#: ``beatToAnimations`` fans one animation per resolution and one burst per
#: kill. 16 comfortably covers the largest real arc (every combatant a
#: dynamic grid can hold); anything beyond it is a degenerate/adversarial
#: payload that would otherwise become an unbounded animation/SFX storm.
#: Mirrored in frontend/src/utils/combatBeatSchema.js.
MAX_BEAT_RESOLUTIONS = 16

#: Animation the API layer picks for a targeted, damaging move that declares
#: no ``web_animation`` of its own, and the generic fallback for everything
#: else (including a beat that carries no tagged animation at all). Both must
#: be keys of ANIMATION_CONFIGS in frontend/src/utils/animationConfigs.js --
#: an unknown type there degrades silently to ``pulse`` client-side, which is
#: exactly how wire-name drift hides in this codebase. Defined here, in the
#: wire-protocol home, because both the combat adapter and the beat streamer
#: substitute them; guarded by tests/test_move_web_animations.py.
DEFAULT_DAMAGE_ANIMATION = "attack"
DEFAULT_ANIMATION = "pulse"


def _normalize_resolution(resolution):
    """One resolution as ``{"outcome", "target_id"}``.

    A resolution may arrive as a plain outcome string (the legacy single-target
    shape) or as a dict pairing the outcome with the combatant it resolved
    against. The impact emission needs both together — an outcome without its
    target cannot be fanned into a per-target animation client-side.
    """
    if isinstance(resolution, dict):
        return {
            "outcome": resolution.get("outcome"),
            "target_id": resolution.get("target_id"),
        }
    return {"outcome": resolution, "target_id": None}


def build_sfx_chain(
    outcome,
    hp_changes=None,
    killed=None,
    status_changes=None,
    actor_id=None,
    has_swing=True,
    outcomes=None,
):
    """Return the ordered, server-indexed semantic SFX emissions for a beat.

    Causal/sonic order: ``swing`` (windup) → one ``impact`` per resolution
    (each resolving via its own ``outcome`` + the beat's ``web_animation``
    client-side) → one ``status`` per landed status → ``heal`` (a positive HP
    change on the actor, i.e. lifesteal) → one ``death`` per id that died.
    Indices are assigned sequentially so the client can play them in this exact
    order with the 75% partial-stack rule.

    ``outcomes`` carries the per-target resolutions of a single swing: one arc
    catching four enemies parries off one and lands on three, and each of those
    is its own audible AND visible event. Each entry is an outcome string or a
    ``{"outcome", "target_id"}`` dict (see ``_normalize_resolution``); the
    resulting ``impact`` emission carries both, so the client can fan one full
    animation per resolution (``beatToAnimations``) as well as play one cue per
    landing (``cueForEmission`` prefers ``emission.outcome`` over the beat's).
    Omit it and the chain falls back to the single ``outcome``, which is what a
    one-target swing needs. The fan-out is capped at ``MAX_BEAT_RESOLUTIONS``.
    """
    hp_changes = hp_changes or []
    status_changes = status_changes or []
    killed = killed or []

    emissions = []
    if has_swing:
        emissions.append({"kind": "swing"})
    for resolution in (outcomes or [outcome])[:MAX_BEAT_RESOLUTIONS]:
        normalized = _normalize_resolution(resolution)
        emissions.append(
            {
                "kind": "impact",
                "outcome": normalized["outcome"],
                "target_id": normalized["target_id"],
            }
        )
    # The same per-target cap bounds every fan-out loop, not just the impacts:
    # a crafted/degenerate beat with hundreds of status_changes or killed ids
    # must not become an unbounded SFX storm either.
    for change in status_changes[:MAX_BEAT_RESOLUTIONS]:
        emissions.append({"kind": "status", "status": change.get("status")})
    if actor_id is not None and any(
        c.get("id") == actor_id and c.get("delta", 0) > 0 for c in hp_changes
    ):
        emissions.append({"kind": "heal"})
    for _ in killed[:MAX_BEAT_RESOLUTIONS]:
        emissions.append({"kind": "death"})

    for index, emission in enumerate(emissions):
        emission["index"] = index
    return emissions


def build_beat(
    seq,
    actor_id,
    target_id,
    web_animation,
    outcome,
    hp_changes=None,
    killed=None,
    departed=None,
    status_changes=None,
    log_line="",
    has_swing=True,
    outcomes=None,
):
    """Build a ``combat:beat`` payload from structured engine facts.

    ``hp_changes`` is a list of ``{"id": <combatant_id>, "delta": <signed int>}``
    (negative = damage, positive = heal) attributed per combatant, so a single
    beat can correctly express lifesteal (target −N, actor +M), recoil, AoE, and
    ally-heals. ``killed`` is a list of combatant ids that died this beat.
    ``departed`` is a list of ``{"id", "reason"}`` for combatants that LEFT the
    battlefield alive (flee/warp/scripted removal) — the client drops the token
    without a death animation/sound. ``status_changes`` is ``{"id", "status"}``.

    ``outcome`` is the beat's headline resolution (the one the client falls back
    to); ``outcomes`` is every resolution the beat contained, one per target of
    a multi-target swing. When ``outcomes`` is non-empty the headline is
    DERIVED from its first entry rather than trusted from the caller — the
    invariant "``outcome`` == the first own resolution" is structural here, not
    a convention the streamer has to remember. See ``build_sfx_chain``.
    """
    hp_changes = list(hp_changes or [])
    killed = list(killed or [])
    departed = list(departed or [])
    status_changes = list(status_changes or [])
    if outcomes:
        outcome = _normalize_resolution(outcomes[0])["outcome"]
    return {
        "seq": seq,
        "actor_id": actor_id,
        "target_id": target_id,
        "web_animation": web_animation,
        "outcome": outcome,
        "hp_changes": hp_changes,
        "killed": killed,
        "departed": departed,
        "status_changes": status_changes,
        "log_line": log_line,
        "sfx": build_sfx_chain(
            outcome,
            hp_changes=hp_changes,
            killed=killed,
            status_changes=status_changes,
            actor_id=actor_id,
            has_swing=has_swing,
            outcomes=outcomes,
        ),
    }


def diff_combatants(prev_combatants, curr_combatants):
    """Diff two serialized-combatant snapshots into structured beat facts.

    Each combatant is a dict with ``id``, ``hp``, and ``status_effects`` (a list
    of ``{"name": ...}``). Matching is by ``id``. Returns a tuple
    ``(hp_changes, killed, status_changes)`` in the shapes ``build_beat`` expects:

    - ``hp_changes``: ``[{"id", "delta"}]`` for every combatant whose HP changed
      (signed; negative = damage, positive = heal).
    - ``killed``: ids whose HP crossed from ``> 0`` to ``<= 0`` this beat.
    - ``status_changes``: ``[{"id", "status"}]`` for statuses newly present.

    Combatants absent from ``prev`` (e.g. reinforcements appearing this beat)
    have no baseline and are skipped for HP/kill diffing.
    """
    prev_by_id = {c.get("id"): c for c in (prev_combatants or [])}
    hp_changes = []
    killed = []
    status_changes = []

    for curr in curr_combatants or []:
        cid = curr.get("id")
        prev = prev_by_id.get(cid)
        if prev is None:
            continue
        prev_hp = prev.get("hp", 0)
        curr_hp = curr.get("hp", 0)
        if curr_hp != prev_hp:
            hp_changes.append({"id": cid, "delta": curr_hp - prev_hp})
        if prev_hp > 0 and curr_hp <= 0:
            killed.append(cid)
        prev_statuses = {
            s.get("name") for s in (prev.get("status_effects") or [])
        }
        for effect in curr.get("status_effects") or []:
            name = effect.get("name")
            if name not in prev_statuses:
                status_changes.append({"id": cid, "status": name})

    # NOTE: a combatant present in prev but ABSENT from curr is deliberately NOT
    # classified here — absence alone cannot distinguish a death from an alive
    # exit (flee, warp, scripted removal). Departures are resolved by the caller
    # using an engine-recorded reason (see CombatBeatStreamer.reconcile_final).
    return hp_changes, killed, status_changes


def validate_beat(beat):
    """Return a list of contract problems with a beat dict (empty = valid)."""
    problems = []
    for field in BEAT_FIELDS:
        if field not in beat:
            problems.append(f"missing field: {field}")

    if beat.get("outcome") not in OUTCOMES:
        problems.append(f"invalid outcome: {beat.get('outcome')!r}")

    for change in beat.get("hp_changes", []) or []:
        if "id" not in change or "delta" not in change:
            problems.append(f"hp_change missing id/delta: {change!r}")

    for change in beat.get("status_changes", []) or []:
        if "id" not in change or "status" not in change:
            problems.append(f"status_change missing id/status: {change!r}")

    for exit_ in beat.get("departed", []) or []:
        if "id" not in exit_ or "reason" not in exit_:
            problems.append(f"departed missing id/reason: {exit_!r}")
        elif exit_.get("reason") not in DEPARTURE_REASONS:
            problems.append(f"invalid departure reason: {exit_.get('reason')!r}")

    for expected_index, emission in enumerate(beat.get("sfx", []) or []):
        if emission.get("index") != expected_index:
            problems.append(
                f"sfx index {emission.get('index')!r} != {expected_index}"
            )
        if emission.get("kind") not in SFX_KINDS:
            problems.append(f"invalid sfx kind: {emission.get('kind')!r}")
        # Every impact resolves against the outcome vocabulary, not just the
        # beat's headline: the client fans an animation per impact, so a bad
        # per-target outcome fails exactly as silently as a bad top-level one.
        if (
            emission.get("kind") == "impact"
            and emission.get("outcome") not in OUTCOMES
        ):
            problems.append(
                f"invalid impact outcome: {emission.get('outcome')!r}"
            )

    return problems
