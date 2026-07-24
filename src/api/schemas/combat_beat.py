"""Combat beat streaming protocol — Python source of truth (issue #436).

Defines the payload shapes for the SocketIO events the engine streams during
combat, plus pure builders/validators. The frontend mirror lives at
``frontend/src/utils/combatBeatSchema.js``; ``tests/test_combat_beat_schema.py``
asserts the two stay in parity so the wire contract can't silently drift.

See docs/development/combat-streaming-plan.md.
"""

# Event names.
BEAT_EVENT = "combat:beat"
RESOLVED_EVENT = "combat:resolved"
ENDED_EVENT = "combat:ended"
SUGGESTIONS_EVENT = "combat:suggestions"

# Top-level ``combat:beat`` fields (this tuple documents the shape).
BEAT_FIELDS = (
    "seq",
    "actor_id",
    "target_id",
    "web_animation",
    "outcome",
    "hp_changes",
    "killed",
    "status_changes",
    "log_line",
    "sfx",
)

# Attack/resolution outcomes an ``impact`` SFX emission resolves against.
OUTCOMES = (
    "hit",
    "miss",
    "parry",
    "block",
    "deflect",
    "crit",
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


def build_sfx_chain(
    outcome,
    hp_changes=None,
    killed=None,
    status_changes=None,
    actor_id=None,
    has_swing=True,
):
    """Return the ordered, server-indexed semantic SFX emissions for a beat.

    Causal/sonic order: ``swing`` (windup) → ``impact`` (resolves via
    ``outcome`` + the beat's ``web_animation`` client-side) → one ``status`` per
    landed status → ``heal`` (a positive HP change on the actor, i.e. lifesteal)
    → one ``death`` per id that died. Indices are assigned sequentially so the
    client can play them in this exact order with the 75% partial-stack rule.
    """
    hp_changes = hp_changes or []
    status_changes = status_changes or []
    killed = killed or []

    emissions = []
    if has_swing:
        emissions.append({"kind": "swing"})
    emissions.append({"kind": "impact", "outcome": outcome})
    for change in status_changes:
        emissions.append({"kind": "status", "status": change.get("status")})
    if actor_id is not None and any(
        c.get("id") == actor_id and c.get("delta", 0) > 0 for c in hp_changes
    ):
        emissions.append({"kind": "heal"})
    for _ in killed:
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
    status_changes=None,
    log_line="",
    has_swing=True,
):
    """Build a ``combat:beat`` payload from structured engine facts.

    ``hp_changes`` is a list of ``{"id": <combatant_id>, "delta": <signed int>}``
    (negative = damage, positive = heal) attributed per combatant, so a single
    beat can correctly express lifesteal (target −N, actor +M), recoil, AoE, and
    ally-heals. ``killed`` is a list of combatant ids that died this beat;
    ``status_changes`` is a list of ``{"id", "status"}``.
    """
    hp_changes = list(hp_changes or [])
    killed = list(killed or [])
    status_changes = list(status_changes or [])
    return {
        "seq": seq,
        "actor_id": actor_id,
        "target_id": target_id,
        "web_animation": web_animation,
        "outcome": outcome,
        "hp_changes": hp_changes,
        "killed": killed,
        "status_changes": status_changes,
        "log_line": log_line,
        "sfx": build_sfx_chain(
            outcome,
            hp_changes=hp_changes,
            killed=killed,
            status_changes=status_changes,
            actor_id=actor_id,
            has_swing=has_swing,
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

    for expected_index, emission in enumerate(beat.get("sfx", []) or []):
        if emission.get("index") != expected_index:
            problems.append(
                f"sfx index {emission.get('index')!r} != {expected_index}"
            )
        if emission.get("kind") not in SFX_KINDS:
            problems.append(f"invalid sfx kind: {emission.get('kind')!r}")

    return problems
