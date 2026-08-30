"""Engine-asserted combat outcomes (glancing blows, absorbs) reach the adapter.

The adapter used to *infer* the animation/SFX outcome by string-matching the
narration text ("struck" + "damage" -> hit, "parried" -> parry, "missed" ->
miss).  ``Move.hit()`` narrates a glancing blow as "just barely hit ... for N
damage!", which matched none of those, so a glance -- roughly 10% of all landed
hits -- produced no impact animation and no SFX at all.  A fully absorbed blow
("struck X but did no damage!") matched the *hit* branch and played the
flesh-impact cue for zero damage.

The engine already knows exactly what happened (``Move.hit(damage, glance)``
receives ``glance``), so it now publishes the outcome onto the acting entity's
pending animation and the adapter reads that structured fact directly.
"""

import pytest

from src.api.combat_adapter import CombatOutputCapture
from src.api.schemas.combat_beat import OUTCOMES
from src.moves import _base
from src.moves._base import Move
from src.narration import capture_narration


class _Combatant:
    """Minimal stand-in for a combat entity (never named 'Jean').

    Keeping the name off "Jean" skips the player-only heat/experience
    bookkeeping in hit()/miss()/parry() without stubbing any of it.
    """

    def __init__(self, name):
        self.name = name
        self.hp = 100
        self.maxhp = 100
        self.states = []

    def clamp_hp(self):
        self.hp = max(0, min(self.hp, self.maxhp))


def _make_move(user, target):
    """A bare Move wired up with just what hit()/miss()/parry() touch."""
    move = Move.__new__(Move)
    move.user = user
    move.target = target
    move.usercolor = "magenta"
    move.targetcolor = "green"
    move.stage_beat = [0, 0, 0, 0]
    return move


@pytest.fixture
def rig():
    """Return (move, attacker, capture) with a pending animation on the attacker.

    The capture is wired as a live narration listener exactly as
    ``ApiCombatAdapter._capture_output`` does it, so these tests exercise the
    real engine -> narration -> adapter path rather than a paraphrase of it.
    """
    attacker = _Combatant("Slime")
    defender = _Combatant("Gorran")
    move = _make_move(attacker, defender)
    attacker._pending_animation = {
        "type": "attack",
        "source_id": "enemy_1",
        "target_id": "ally_2",
        "move_name": "Attack",
        "outcome": None,
    }
    capture = CombatOutputCapture()
    capture.active_entity = attacker
    return move, attacker, capture


def _run(capture, fn):
    """Run ``fn`` with ``capture`` listening on the narration sink."""
    with capture_narration(listener=lambda e: capture.write(e.get("text", ""))):
        fn()
    return capture.get_log()


def _impact_entries(entries):
    return [e for e in entries if e.get("trigger_animation")]


# ── the bug: a glancing blow is silent ──────────────────────────────────────

def test_glancing_blow_publishes_glance_outcome_and_an_impact(rig):
    move, attacker, capture = rig

    entries = _run(capture, lambda: move.hit(9, True))

    # The narration stays -- it is the explanation of the halved number.
    assert any("just barely hit" in e["message"] for e in entries), entries
    impacts = _impact_entries(entries)
    assert len(impacts) == 1, f"expected exactly one impact, got {impacts}"
    assert impacts[0]["animation_data"]["outcome"] == "glance"


def test_glance_narration_is_the_real_engine_string(rig):
    """Guard the exact wording hit() emits for a glance, not a paraphrase."""
    move, attacker, capture = rig

    entries = _run(capture, lambda: move.hit(9, True))

    assert entries[0]["message"] == "Slime just barely hit Gorran for 9 damage!"


# ── absorb must be distinguishable from hit ─────────────────────────────────

def test_zero_damage_blow_publishes_absorb_not_hit(rig):
    move, attacker, capture = rig

    entries = _run(capture, lambda: move.hit(0, False))

    assert entries[0]["message"] == "Slime struck Gorran but did no damage!"
    impacts = _impact_entries(entries)
    assert len(impacts) == 1
    assert impacts[0]["animation_data"]["outcome"] == "absorb"


def test_negative_damage_blow_publishes_absorb(rig):
    move, attacker, capture = rig

    entries = _run(capture, lambda: move.hit(-4, False))

    assert "absorbed" in entries[0]["message"]
    impacts = _impact_entries(entries)
    assert len(impacts) == 1
    assert impacts[0]["animation_data"]["outcome"] == "absorb"


# ── every branch resolves to exactly one valid outcome ──────────────────────

@pytest.mark.parametrize(
    "call, expected",
    [
        (lambda m: m.hit(12, False), "hit"),
        (lambda m: m.hit(9, True), "glance"),
        (lambda m: m.hit(0, False), "absorb"),
        (lambda m: m.hit(-4, False), "absorb"),
        (lambda m: m.miss(), "miss"),
        (lambda m: m.parry(), "parry"),
    ],
)
def test_every_branch_emits_exactly_one_outcome_from_the_vocabulary(
    rig, call, expected
):
    move, attacker, capture = rig

    entries = _run(capture, lambda: call(move))

    impacts = _impact_entries(entries)
    assert len(impacts) == 1, f"expected exactly one impact, got {impacts}"
    outcome = impacts[0]["animation_data"]["outcome"]
    assert outcome == expected
    assert outcome in OUTCOMES

    # Fires exactly once. The pending animation is deliberately RETAINED after a
    # resolution (an arc swing publishes one outcome per enemy and needs
    # somewhere to publish the next), so "once" is enforced by clearing the
    # outcome rather than by deleting the animation: a further narration line
    # must not re-fire the same resolution, and the end-of-move fallback must
    # see it as already reported.
    capture.write("Dust settles over the floor.")
    assert len(_impact_entries(capture.get_log())) == 1
    assert attacker._pending_animation["outcome"] is None
    assert "_reported_beat" in attacker._pending_animation


# ── regression guard: text must not drive the outcome ───────────────────────

def test_rewording_the_narration_cannot_change_the_outcome(rig, monkeypatch):
    """The whole regression class: prose is not a wire protocol.

    Every impact line is rewritten to text containing none of the old trigger
    words ("struck"/"damage"/"parried"/"missed"). If the adapter still inferred
    outcomes from prose, these would resolve to nothing at all.
    """
    move, attacker, capture = rig
    real_narrate = _base.narrate
    monkeypatch.setattr(
        _base,
        "narrate",
        lambda *a, **kw: real_narrate("Something happened in the fight.", **{
            k: v for k, v in kw.items() if k != "color"
        }),
    )

    entries = _run(capture, lambda: move.hit(9, True))

    assert entries[0]["message"] == "Something happened in the fight."
    impacts = _impact_entries(entries)
    assert len(impacts) == 1
    assert impacts[0]["animation_data"]["outcome"] == "glance"


def test_prose_alone_never_triggers_an_impact(rig):
    """A line that merely *reads* like an impact must not fire an animation."""
    move, attacker, capture = rig

    capture.write("Slime struck Gorran for 12 damage!")

    assert _impact_entries(capture.get_log()) == []
    assert attacker._pending_animation["outcome"] is None


# ── multi-combatant attribution ─────────────────────────────────────────────

def test_two_entities_acting_in_one_beat_get_their_own_outcomes():
    player = _Combatant("Jean-like")
    npc = _Combatant("Slime")
    player_move = _make_move(player, npc)
    npc_move = _make_move(npc, player)
    player._pending_animation = {"move_name": "Slash", "outcome": None}
    npc._pending_animation = {"move_name": "NPC_Attack", "outcome": None}

    capture = CombatOutputCapture(player=player)

    with capture_narration(listener=lambda e: capture.write(e.get("text", ""))):
        capture.active_entity = player
        player_move.hit(9, True)
        capture.active_entity = npc
        npc_move.miss()
        capture.active_entity = None

    impacts = _impact_entries(capture.get_log())
    assert [
        (i["animation_data"]["move_name"], i["animation_data"]["outcome"])
        for i in impacts
    ] == [("Slash", "glance"), ("NPC_Attack", "miss")]


def test_outcome_is_never_written_to_a_bystanders_animation():
    """A third combatant that did not act keeps an unresolved animation."""
    attacker = _Combatant("Slime")
    defender = _Combatant("Gorran")
    bystander = _Combatant("Cave Bat")
    bystander._pending_animation = {"move_name": "Bite", "outcome": None}
    attacker._pending_animation = {"move_name": "Attack", "outcome": None}
    move = _make_move(attacker, defender)

    capture = CombatOutputCapture(player=bystander)
    capture.active_entity = attacker
    _run(capture, lambda: move.hit(9, True))

    assert bystander._pending_animation == {"move_name": "Bite", "outcome": None}


# ── vocabulary parity ───────────────────────────────────────────────────────

def test_engine_outcome_vocabulary_is_a_subset_of_the_wire_vocabulary():
    assert set(_base.MOVE_OUTCOMES) <= set(OUTCOMES)
    assert "glance" in _base.MOVE_OUTCOMES


# ── end to end through the real attack pipeline ─────────────────────────────

def test_real_glancing_blow_through_standard_execute_attack():
    """The whole path: a roll inside the glance band -> 'glance' at the adapter.

    The unit tests above call ``hit(damage, glance)`` directly. This one drives
    ``standard_execute_attack`` -- the shared resolution path for every ordinary
    weapon attack -- with a roll deliberately placed inside the glancing band
    (``hit_chance >= roll`` and ``hit_chance - roll < 10``), so it also pins that
    ``glance`` actually reaches ``hit()`` from the resolver.
    """
    from unittest.mock import patch

    attacker = _Combatant("Slime")
    attacker.combat_position = None
    attacker.fatigue = 100
    attacker.heat = 1.0
    attacker.eq_weapon = None
    attacker.combat_exp = {"Basic": 0}
    defender = _Combatant("Gorran")
    defender.combat_position = None
    defender.protection = 0

    move = _make_move(attacker, defender)
    move.stage_announce = ["", "Slime lunges!", "", ""]
    move.fatigue_cost = 0
    attacker._pending_animation = {"move_name": "Attack", "outcome": None}

    capture = CombatOutputCapture()
    capture.active_entity = attacker

    with patch("src.moves._base.to_hit_chance", return_value=90), \
            patch(
                "src.moves._base._apply_to_hit_modifiers",
                side_effect=lambda u, t, chance: chance,
            ), \
            patch("src.moves._base.random.randint", return_value=85), \
            patch("src.moves._base.random.uniform", return_value=1.0), \
            patch("src.moves._base.functions.check_parry", return_value=False), \
            patch("src.moves._base.functions.combat_resistance", return_value=1.0), \
            patch.object(Move, "viable", return_value=True):
        entries = _run(
            capture,
            lambda: move.standard_execute_attack(
                attacker, power=100, base_damage_type="crushing"
            ),
        )

    # 100 power, halved by the glance.
    assert "Slime just barely hit Gorran for 50 damage!" in [
        e["message"] for e in entries
    ], entries
    assert defender.hp == 50
    impacts = _impact_entries(entries)
    assert len(impacts) == 1
    assert impacts[0]["animation_data"]["outcome"] == "glance"


# ── per-target outcomes: one animation is not enough ────────────────────────
#
# An area move resolves independently against every enemy in its arc. The
# pending animation carries ONE outcome, so consuming-and-deleting it on the
# first narration line reported the first enemy's result for the whole swing
# and dropped every later one. write() now re-arms the animation after each
# consumption so a swing can report as many resolutions as it actually made.


def test_a_second_published_outcome_fires_a_second_impact(rig):
    move, attacker, capture = rig

    entries = _run(
        capture,
        lambda: (move.hit(12, False), move.parry()),
    )

    impacts = _impact_entries(entries)
    assert [i["animation_data"]["outcome"] for i in impacts] == ["hit", "parry"], (
        entries
    )


def test_each_impact_names_the_combatant_the_outcome_happened_to(rig):
    """An arc swing reassigns ``self.target`` per enemy; each impact must
    follow it rather than keep the id the animation was stamped with at cast.
    """
    from src.api.serializers.combat import CombatantSerializer

    move, attacker, capture = rig
    first = move.target
    second = _Combatant("Cave Bat")

    def _swing():
        move.hit(12, False)
        move.target = second
        move.miss()

    entries = _run(capture, _swing)

    impacts = _impact_entries(entries)
    assert [i["animation_data"]["target_id"] for i in impacts] == [
        CombatantSerializer.stream_id(first),
        CombatantSerializer.stream_id(second),
    ], impacts


def test_the_end_of_move_fallback_does_not_re_emit_a_consumed_animation(rig):
    """The fallback exists for animations that never found an impact line.

    Retaining the pending animation so it can be re-armed means the fallback
    must be able to tell "already reported" from "never reported" — otherwise
    every attack would gain a phantom trailing animation entry.
    """
    from src.api.combat_adapter import ApiCombatAdapter

    move, attacker, capture = rig
    _run(capture, lambda: move.hit(12, False))

    adapter = ApiCombatAdapter.__new__(ApiCombatAdapter)
    emitted = []
    adapter._emit_animation_log = lambda beat, data: emitted.append(data)
    adapter.player = attacker
    attacker.combat_beat = 1
    adapter._all_combatants = lambda: [attacker]

    adapter._flush_pending_animations()

    assert emitted == []
    assert not hasattr(attacker, "_pending_animation")


def test_the_fallback_still_emits_an_animation_that_never_resolved():
    from src.api.combat_adapter import ApiCombatAdapter

    attacker = _Combatant("Slime")
    attacker.combat_beat = 1
    attacker._pending_animation = {"move_name": "Sweep", "outcome": None}

    adapter = ApiCombatAdapter.__new__(ApiCombatAdapter)
    emitted = []
    adapter._emit_animation_log = lambda beat, data: emitted.append(data)
    adapter.player = attacker
    adapter._all_combatants = lambda: [attacker]

    adapter._flush_pending_animations()

    assert [e["move_name"] for e in emitted] == ["Sweep"]
    assert not hasattr(attacker, "_pending_animation")


def test_an_unconsumed_resolution_never_reaches_the_wire_holding_a_combatant():
    """The end-of-move fallback must sanitize, not emit the raw pending dict.

    ``publish_outcome`` stores the *combatant object* on ``_pending_animation``
    so the adapter can map it to a stream id. ``_take_resolution`` pops that
    object off before the animation goes out. The fallback path did not: it
    passed ``entity._pending_animation`` straight to the log, so an outcome the
    engine published but no narration line consumed shipped a live NPC into
    ``player.combat_log`` -- which is jsonify'd on every combat poll (a 500,
    measured as "Object of type Slime is not JSON serializable") and pickled
    into every save, dragging the enemy's whole object graph in with it.
    """
    import json

    from src.api.combat_adapter import ApiCombatAdapter, CombatOutputCapture
    from src.api.serializers.combat import CombatantSerializer
    import src.npc as npc
    from src.player import Player

    player = Player()
    player.combat_log = []
    player.combat_beat = 1
    enemy = npc.Slime()
    enemy.name = "Slime"

    adapter = ApiCombatAdapter.__new__(ApiCombatAdapter)
    adapter.player = player
    adapter.session_id = None
    adapter.current_beat_state_index = 0
    adapter.output_capture = CombatOutputCapture(player=player)
    adapter._all_combatants = lambda: [player]

    player._pending_animation = {
        "type": "sweep",
        "move_name": "Sweep",
        "move_display_name": "Sweep",
        "outcome": "hit",
        "outcome_target": enemy,
    }
    adapter._flush_pending_animations()

    emitted = [e["animation"] for e in player.combat_log if e.get("animation")]
    assert len(emitted) == 1, "the unresolved animation must still be emitted once"
    animation = emitted[0]
    assert "outcome_target" not in animation, (
        "the raw combatant object reached the wire: "
        f"{type(animation.get('outcome_target')).__name__}"
    )
    assert "_reported" not in animation, "internal bookkeeping leaked to the client"
    assert "_reported_beat" not in animation, "beat bookkeeping leaked to the client"
    assert animation.get("target_id") == CombatantSerializer.stream_id(enemy), (
        "the fallback must map the target to its stream id like _take_resolution"
    )
    json.dumps(player.combat_log)


def test_a_non_dict_pending_animation_cannot_crash_the_move_loop():
    """A degraded ``_pending_animation`` must be discarded, not dereferenced.

    The flush guarded its ``_reported`` read with ``isinstance(..., dict)`` --
    conceding a non-dict is possible -- and then handed that same value to
    ``_emit_animation_log``, which calls ``.get()`` on it. That AttributeError
    escapes into the combat loop, which the project's error-handling rule says
    must degrade silently rather than wedge the fight.
    """
    from src.api.combat_adapter import ApiCombatAdapter, CombatOutputCapture
    from src.player import Player

    player = Player()
    player.combat_log = []
    player.combat_beat = 1

    adapter = ApiCombatAdapter.__new__(ApiCombatAdapter)
    adapter.player = player
    adapter.session_id = None
    adapter.current_beat_state_index = 0
    adapter.output_capture = CombatOutputCapture(player=player)
    adapter._all_combatants = lambda: [player]

    player._pending_animation = "not a dict"
    adapter._flush_pending_animations()

    assert not hasattr(player, "_pending_animation")
    assert not [e for e in player.combat_log if e.get("animation")]


#: A hand-rolled wire id is any f-string that interpolates ``id(...)`` next to
#: an ally/enemy discriminator. Keying on ``id(`` rather than on a literal
#: ``enemy_``/``ally_`` prefix is deliberate: the prefix can be spelled as a
#: conditional, and the first version of this guard missed a real site that
#: did exactly that.
_HANDROLLED_ID = r'f"[^"]*(?:ally|enemy)[^"]*\{id\([^)]*\)\}[^"]*"'


def test_no_animation_payload_hardcodes_a_combatant_wire_id():
    """Wire ids come from ``stream_id``, never from an inline f-string.

    ``CombatantSerializer.stream_id`` is the single source of truth for the
    ``player`` / ``ally_<id>`` / ``enemy_<id>`` scheme. Three animation payloads
    hand-rolled ``f"enemy_{id(x)}"`` instead, which is simply wrong for an ally:
    a move aimed at Gorran was announced as ``enemy_140...`` at cast time and
    resolved as ``ally_140...``, and ``BattlefieldGrid`` matches an animation to
    a cell by ``target_id === entityId`` -- so the two spellings matched nothing
    and the animation landed on no one.

    A structural check rather than a behavioural one: the failure is invisible
    at runtime unless a test happens to aim an animated move at an ally, which
    is exactly why it survived. Derived by scanning the source so a fourth site
    cannot be added without this failing.
    """
    import pathlib
    import re

    source = pathlib.Path("src/api/combat_adapter.py").read_text()
    offenders = re.findall(_HANDROLLED_ID, source)
    assert not offenders, (
        "these hand-rolled combatant ids bypass CombatantSerializer.stream_id "
        f"and mislabel allies: {offenders}"
    )


def test_the_hardcoded_id_scan_can_actually_find_something():
    """A guard that matches nothing passes forever -- and this one already did.

    The first version of this scan looked for the literal prefixes
    ``f"enemy_{id(...)}"`` / ``f"ally_{id(...)}"``. A fifth site spelled the
    same thing as a conditional -- ``f"{'ally' if npc.friend else 'enemy'}_{id(npc)}"``
    -- and sailed straight past it, which is the enumeration-shaped guard this
    codebase keeps rediscovering. The pattern now keys on the ``id(...)``
    interpolation, which is what actually makes an id hand-rolled, and every
    known spelling is pinned below as a positive control.
    """
    import re

    known_spellings = [
        '        "source_id": f"enemy_{id(npc)}",',
        '        "target_id": f"ally_{id(target)}",',
        '        "source_id": f"{\'ally\' if npc.friend else \'enemy\'}_{id(npc)}",',
        '        label = f"enemy_{id(move.target)}" if x else "player"',
    ]
    for spelling in known_spellings:
        assert re.findall(_HANDROLLED_ID, spelling), (
            f"the offender pattern no longer matches a known shape: {spelling}"
        )

    # ...and does not fire on a legitimate stream_id call.
    assert not re.findall(
        _HANDROLLED_ID, '        "source_id": CombatantSerializer.stream_id(npc),'
    )


# ── TASK 1/2/3/4 (see report): per-target animations, beat scoping, streaming,
#    and the combat log as a bounded recap ────────────────────────────────────


def _adapter_with_player(player):
    """A bare adapter wired to ``player`` with no __init__ side effects."""
    from src.api.combat_adapter import ApiCombatAdapter, CombatOutputCapture

    adapter = ApiCombatAdapter.__new__(ApiCombatAdapter)
    adapter.player = player
    adapter.session_id = None
    adapter.current_beat_state_index = 0
    adapter.output_capture = CombatOutputCapture(player=player)
    adapter._all_combatants = lambda: [player]
    return adapter


# ── TASK 1: every target gets the move's full animation ─────────────────────


def test_every_resolution_replays_the_full_move_animation(rig):
    """One swing, several landings — every landing plays the move in full.

    The client plays a beat's animations concurrently/layered (owner decision),
    so four enemies caught by one arc each get the arc, each with its own
    ``target_id`` and its own SFX emission. The old behaviour downgraded every
    resolution after the first to a 200 ms ``impact`` flash because the client
    played them sequentially and four sweeps read as four swings.
    """
    move, attacker, capture = rig

    entries = _run(
        capture,
        lambda: (move.hit(12, False), move.miss(), move.parry()),
    )

    impacts = _impact_entries(entries)
    assert [i["animation_data"]["type"] for i in impacts] == [
        "attack",
        "attack",
        "attack",
    ], entries


def test_the_adapter_no_longer_downgrades_follow_up_animations():
    """The impact-downgrade constant and its substitution are gone for good."""
    import src.api.combat_adapter as combat_adapter

    assert not hasattr(combat_adapter, "FOLLOW_UP_IMPACT_ANIMATION"), (
        "the follow-up downgrade constant is still defined"
    )


# ── TASK 2: the reported flag is scoped to a beat, not to a dict lifetime ───


def test_a_resolution_records_the_beat_it_happened_in(rig):
    """``_reported`` was a lifetime boolean; it is now a per-beat record."""
    move, attacker, capture = rig

    class _P:
        combat_beat = 7

    capture.player = _P()

    _run(capture, lambda: move.hit(12, False))

    assert attacker._pending_animation["_reported_beat"] == 7
    assert "_reported" not in attacker._pending_animation


def test_the_beat_marker_never_reaches_the_client(rig):
    move, attacker, capture = rig

    entries = _run(capture, lambda: move.hit(12, False))

    animation = _impact_entries(entries)[0]["animation_data"]
    assert "_reported_beat" not in animation
    assert "_reported" not in animation


def test_a_move_still_in_flight_keeps_its_animation_channel():
    """The flush must not disarm a move that has not swung yet.

    ``_flush_pending_animations`` ran at the end of every *player* move and
    deleted every combatant's pending animation unconditionally. An NPC three
    beats into a five-beat wind-up therefore lost the channel its impact would
    have published to, and ``publish_outcome`` became a silent no-op for the
    swing that was still coming.
    """
    from src.player import Player

    player = Player()
    player.combat_log = []
    player.combat_beat = 4
    player.current_move = None

    npc = _Combatant("Slime")
    npc.current_move = object()  # still winding up
    npc._pending_animation = {"move_name": "Telegraphed Surge", "outcome": None}

    adapter = _adapter_with_player(player)
    adapter._all_combatants = lambda: [player, npc]
    adapter._flush_pending_animations()

    assert hasattr(npc, "_pending_animation"), (
        "the in-flight move's animation channel was destroyed"
    )
    assert not [e for e in player.combat_log if e.get("animation")], (
        "a phantom animation was emitted for a move that has not landed"
    )


def test_initialize_combat_flushes_animations_left_by_the_initial_turns():
    """A first-strike NPC's unresolved animation must not leak into beat 2.

    ``initialize_combat`` -> ``_process_initial_turns`` processes a whole NPC
    beat and never flushed, so an animation that never found an impact line sat
    on the NPC until the end of the player's *next* move and was emitted a beat
    or more late.
    """
    import inspect

    from src.api.combat_adapter import ApiCombatAdapter

    source = inspect.getsource(ApiCombatAdapter.initialize_combat)
    assert "_flush_pending_animations" in source, (
        "initialize_combat never flushes the animations _process_initial_turns "
        "leaves behind"
    )


# ── TASK 3: the streaming channel must not collapse a multi-target swing ────


def _snap(combatants, log):
    return {"combatants": combatants, "log": log}


def _c(cid, hp, statuses=()):
    return {
        "id": cid,
        "hp": hp,
        "status_effects": [{"name": s} for s in statuses],
    }


def _anim_entry(source, target, atype, outcome):
    return {
        "message": f"{source} -> {target}",
        "animation": {
            "type": atype,
            "source_id": source,
            "target_id": target,
            "outcome": outcome,
        },
    }


def test_stream_beats_keeps_the_moves_own_animation_for_a_multi_target_swing():
    from src.api.combat_beat_stream import CombatBeatStreamer

    emitted = []

    class _Socket:
        def emit(self, event, payload, room=None):
            emitted.append((event, payload))

    streamer = CombatBeatStreamer(
        _Socket(),
        "room",
        initial_combatants=[_c("enemy_1", 20), _c("enemy_2", 20)],
    )
    streamer.stream_beats(
        [
            _snap(
                [_c("enemy_1", 12), _c("enemy_2", 20)],
                [
                    _anim_entry("player", "enemy_1", "sweep", "hit"),
                    _anim_entry("player", "enemy_2", "sweep", "parry"),
                    # A beat's log holds the NPC turns that follow the player's
                    # move too, so the LAST animation in an ordinary beat is an
                    # NPC's — which is what the old walk-backwards returned.
                    _anim_entry("enemy_2", "player", "pierce", "miss"),
                ],
            )
        ]
    )

    assert len(emitted) == 1
    beat = emitted[0][1]
    assert beat["web_animation"] == "sweep", "the beat was attributed to the NPC"
    assert beat["actor_id"] == "player"
    assert beat["target_id"] == "enemy_1"
    assert beat["outcome"] == "hit"
    impacts = [e for e in beat["sfx"] if e["kind"] == "impact"]
    # The NPC's own animation rides in this beat's log but is NOT one of the
    # swing's resolutions -- attributing its "miss" to Jean's sweep is the
    # actor-conflation this filter removes. Two targets, two impacts.
    assert [e["outcome"] for e in impacts] == ["hit", "parry"], beat["sfx"]
    assert [e["index"] for e in beat["sfx"]] == list(range(len(beat["sfx"])))


def test_build_sfx_chain_emits_one_impact_per_resolution():
    from src.api.schemas.combat_beat import build_sfx_chain, validate_beat, build_beat

    chain = build_sfx_chain("hit", outcomes=["hit", "miss", "glance"])
    assert [e["kind"] for e in chain] == ["swing", "impact", "impact", "impact"]
    assert [e.get("outcome") for e in chain[1:]] == ["hit", "miss", "glance"]
    assert [e["index"] for e in chain] == [0, 1, 2, 3]

    beat = build_beat(
        1, "player", "enemy_1", "sweep", "hit", outcomes=["hit", "miss"]
    )
    assert validate_beat(beat) == []


# ── TASK 4: the combat log is a bounded recap ───────────────────────────────


def test_the_dedup_does_not_rescan_the_whole_log():
    """The duplicate check must be a hash membership test, not a linear scan."""
    import inspect

    from src.api.combat_adapter import ApiCombatAdapter

    source = inspect.getsource(ApiCombatAdapter._add_log_entry)
    assert "for existing in self.player.combat_log" not in source, (
        "_add_log_entry still scans the whole cumulative log per insert"
    )


def test_dedup_still_collapses_a_repeated_narration_line():
    from src.player import Player

    player = Player()
    player.combat_log = []
    adapter = _adapter_with_player(player)

    adapter._add_log_entry(1, "Jean swings wildly.", "combat")
    adapter._add_log_entry(1, "Jean swings wildly.", "combat")
    adapter._add_log_entry(2, "Jean swings wildly.", "combat")

    assert [e["round"] for e in player.combat_log] == [1, 2]


def test_dedup_recovers_when_the_log_is_replaced_underneath_it():
    """``combat_log`` lives on the pickled player and outlives the adapter."""
    from src.player import Player

    player = Player()
    player.combat_log = []
    adapter = _adapter_with_player(player)

    adapter._add_log_entry(1, "A line.", "combat")
    player.combat_log = []  # e.g. a new fight, or a reloaded save
    adapter._add_log_entry(1, "A line.", "combat")

    assert len(player.combat_log) == 1, "a stale key set swallowed a real entry"


def test_the_combat_log_is_bounded_and_keeps_the_recap():
    """Animation carriers are trimmed first; the visible recap survives."""
    from src.api.combat_adapter import (
        COMBAT_LOG_TRIM_SLACK,
        MAX_ANIMATION_LOG_ENTRIES,
        MAX_VISIBLE_LOG_ENTRIES,
    )
    from src.player import Player

    player = Player()
    player.combat_log = []
    adapter = _adapter_with_player(player)

    total = (MAX_ANIMATION_LOG_ENTRIES + MAX_VISIBLE_LOG_ENTRIES) * 2
    for i in range(total):
        adapter._add_log_entry(i, f"line {i}", "combat")
        adapter._emit_animation_log(i, {"move_name": "Sweep", "type": "sweep"})

    log = player.combat_log
    animations = [e for e in log if e["type"] == "animation"]
    visible = [e for e in log if e["type"] != "animation"]

    # The trim fires only once the log has overshot by the slack (so the key
    # index rebuild is amortized), which is the slack's whole point; the cap is
    # therefore a steady-state floor, not a per-insert hard ceiling.
    assert len(log) <= (
        MAX_ANIMATION_LOG_ENTRIES + MAX_VISIBLE_LOG_ENTRIES + COMBAT_LOG_TRIM_SLACK
    )
    assert len(animations) <= MAX_ANIMATION_LOG_ENTRIES + COMBAT_LOG_TRIM_SLACK
    assert len(visible) <= MAX_VISIBLE_LOG_ENTRIES + COMBAT_LOG_TRIM_SLACK
    # The newest entries are the ones kept — the recap ends where the fight is.
    assert visible[-1]["message"] == f"line {total - 1}"
    # ...and it is still a useful recap, not a stub.
    assert len(visible) >= MAX_VISIBLE_LOG_ENTRIES // 2
    # Chronological order is preserved across the trim.
    assert [e["round"] for e in visible] == sorted(e["round"] for e in visible)


def test_trimming_preserves_the_combat_log_list_identity():
    """``combat_log`` is read through ``player.combat_log`` everywhere and is
    pickled with the player; rebinding it would strand any held reference."""
    from src.api.combat_adapter import (
        MAX_ANIMATION_LOG_ENTRIES,
        MAX_VISIBLE_LOG_ENTRIES,
    )
    from src.player import Player

    player = Player()
    player.combat_log = []
    held = player.combat_log
    adapter = _adapter_with_player(player)

    for i in range((MAX_ANIMATION_LOG_ENTRIES + MAX_VISIBLE_LOG_ENTRIES) * 2):
        adapter._add_log_entry(i, f"line {i}", "combat")

    assert player.combat_log is held


def test_a_beat_keeps_its_own_log_window_even_when_the_trim_fires():
    """The beat window is an identity, not an index into a list that shrinks.

    ``execute_player_move`` records ``log_len_before = len(player.combat_log)``
    and later slices ``combat_log[log_len_before:]`` to scope one beat's
    entries. ``_trim_combat_log`` rewrites that same list IN PLACE, dropping
    entries off the FRONT -- so a trim firing mid-beat shifts every position
    down and the slice returns the wrong window, usually empty. The beat then
    carries no animations, and CombatBeatStreamer emits nothing for it: a
    silent loss of the whole beat protocol for that beat, reachable only in a
    long fight, which is exactly the kind that would never be reproduced.
    """
    from src.api.combat_adapter import (
        ApiCombatAdapter,
        COMBAT_LOG_TRIM_SLACK,
        MAX_ANIMATION_LOG_ENTRIES,
        MAX_VISIBLE_LOG_ENTRIES,
    )
    from src.player import Player

    player = Player()
    player.combat_beat = 1
    ceiling = (
        MAX_ANIMATION_LOG_ENTRIES + MAX_VISIBLE_LOG_ENTRIES + COMBAT_LOG_TRIM_SLACK
    )
    # A fight already at the ceiling: the next entry trips the trim.
    player.combat_log = [
        {"round": 1, "type": "combat", "message": f"old {i}"} for i in range(ceiling)
    ]

    adapter = ApiCombatAdapter.__new__(ApiCombatAdapter)
    adapter.player = player
    adapter._log_key_count = None
    adapter._log_keys = set()
    adapter._log_key_source = None

    log_len_before = len(player.combat_log)
    this_beat = {"round": 2, "type": "combat", "message": "this beat's only line"}
    player.combat_log.append(this_beat)
    removed = adapter._trim_combat_log()

    assert isinstance(removed, int), (
        "_trim_combat_log must report how many entries it dropped so callers "
        "holding a position can correct it"
    )
    assert removed > 0, "the fixture did not actually trip the trim"

    window = player.combat_log[max(0, log_len_before - removed):]
    assert this_beat in window, (
        "the beat's own entry fell outside its window after the trim shifted "
        f"positions by {removed}"
    )
