"""Tests for Disrupt — the interrupt verb that makes enemy telegraphs actionable.

Disrupt's whole payoff is conditional: it cancels the target's move only when
it *connects* while that move is still in the prep (wind-up) stage. These tests
cover the window (prep -> cancelled), everything outside it (execute / recoil /
cooldown / no move -> untouched), the roll (a miss or a parry cancels nothing),
the brace rule (a cancelled target can only be staggered by the next read),
its own cooldown gating, and the balance claims the design rests on — that
neither blind spam nor perfect play locks a target out of the fight.

Deliberately asserts *behaviour*, never a specific hit-chance number: the
engine's HIT_CHANCE_BASE is a balance lever and a test that pins it would fail
on every retune. Rolls are forced to a certain hit or a certain miss instead.
"""

import random

import pytest

import src.moves as moves
from src.combatant import (
    Combatant,
    MOVE_STAGE_COOLDOWN,
    MOVE_STAGE_EXECUTE,
    MOVE_STAGE_PREP,
    MOVE_STAGE_RECOIL,
)
from src.moves._base import Move
from src.narration import capture_narration


# ---------------------------------------------------------------------------
# Stubs — hand written rather than MagicMock so an attribute this move does not
# actually set can't silently answer as a truthy Mock.
# ---------------------------------------------------------------------------


class FakeWeapon:
    def __init__(self, subtype="Sword", damage=20, weight=5.0):
        self.name = "test blade"
        self.subtype = subtype
        self.damage = damage
        self.str_mod = 0.5
        self.fin_mod = 0.5
        self.weight = weight
        self.wpnrange = (0, 5)


class FakePlayer:
    """Enough of Jean for Disrupt's execute()/hit()/miss() paths."""

    name = "Jean"

    def __init__(self):
        self.strength = 12
        self.finesse = 12
        self.speed = 10
        self.endurance = 10
        self.intelligence = 10
        self.hp = 100
        self.maxhp = 100
        self.fatigue = 200
        self.maxfatigue = 200
        self.heat = 1.0
        self.protection = 0
        self.states = []
        self.known_moves = []
        self.combat_list = []
        self.combat_list_allies = []
        self.combat_proximity = {}
        self.combat_position = None
        self.combat_exp = {"Basic": 0, "Sword": 0}
        self.skill_exp = {"Basic": 0, "Sword": 0}
        self.eq_weapon = FakeWeapon()
        self.pronouns = {"subject": "he", "object": "him", "possessive": "his"}
        self.resistance = {"slashing": 1.0, "crushing": 1.0, "pure": 1.0}
        self.current_move = None
        self.heat_changes = []

    def change_heat(self, amount):
        self.heat_changes.append(amount)

    def is_alive(self):
        return self.hp > 0


class FakeEnemy:
    def __init__(self, name="Bruiser", hp=500, protection=0, finesse=8):
        self.name = name
        self.hp = hp
        self.maxhp = hp
        self.protection = protection
        self.finesse = finesse
        self.speed = 10
        self.endurance = 10
        self.intelligence = 10
        self.friend = False
        self.states = []
        self.known_moves = []
        self.combat_position = None
        self.combat_proximity = {}
        self.combat_list = []
        self.current_move = None
        self.resistance = {"slashing": 1.0, "crushing": 1.0, "pure": 1.0}
        # 0.3 stun resistance is what every real hostile carries
        # (_STATUS_RESISTANCE_BASELINE_COMMON in src/npc/_base.py); 0.15 for
        # bosses. It defaulted to 0.0 here, so every stagger assertion ran
        # against a value no shipped NPC has and functions.inflict could never
        # fail. The immunity test overrides this to 1.0.
        self.status_resistance = {"generic": 0.3, "stun": 0.3}
        # State.process gates on this; the engine sets it on combat entry.
        self.in_combat = True
        # Needed by the state-EXPIRY path: State.process calls
        # functions.refresh_stat_bonuses on removal, which reads these. Without
        # them a test that lets a state expire dies with an AttributeError
        # instead of failing on its own assertion -- so its failure message was
        # unreachable and it could never report the bug it guards.
        self.resistance_base = dict(self.resistance)
        self.status_resistance_base = dict(self.status_resistance)
        self.inventory = []
        self.states_to_remove = []

    def is_alive(self):
        return self.hp > 0


class CountingMove(Move):
    """A plain engine Move that records how often its execute() actually ran."""

    display_name = "Big Wind-Up"
    web_animation = "attack"

    def __init__(self, user, stage_beat=(6, 1, 2, 4)):
        super().__init__(
            name="Big Wind-Up",
            description="",
            xp_gain=0,
            current_stage=0,
            beats_left=stage_beat[0],
            stage_announce=["", "", "", ""],
            target=None,
            user=user,
            stage_beat=list(stage_beat),
            targeted=False,
        )
        self.executions = 0

    def execute(self, user):
        self.executions += 1


def _engaged(distance=2):
    """A player and an enemy standing in Disrupt's reach, plus the move."""
    player = FakePlayer()
    enemy = FakeEnemy()
    player.combat_list = [enemy]
    player.combat_proximity = {enemy: distance}
    enemy.combat_list = [player]
    enemy.combat_proximity = {player: distance}
    move = moves.Disrupt(player)
    move.target = enemy
    return player, enemy, move


def _winding(enemy, stage=MOVE_STAGE_PREP, beats_left=4, stage_beat=(6, 1, 2, 4)):
    """Give the enemy a move parked at ``stage``."""
    move = CountingMove(enemy, stage_beat=stage_beat)
    move.current_stage = stage
    move.beats_left = beats_left
    in_flight = stage in (MOVE_STAGE_PREP, MOVE_STAGE_EXECUTE)
    enemy.current_move = move if in_flight else None
    return move


def _cast(move, player):
    with capture_narration():
        move.cast()
    player.current_move = move


@pytest.fixture
def always_hits(monkeypatch):
    """Force every to-hit roll to succeed (roll 0 <= any positive chance)."""
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
    # functions.inflict rolls random.random() against partial status
    # resistance; unpinned, the now-realistic 0.3 stun resistance would make
    # every braced-stagger assertion ~70% flaky.
    monkeypatch.setattr(random, "random", lambda: 0.0)


@pytest.fixture
def always_misses(monkeypatch):
    """Roll the top of the die. Paired with an untouchably evasive target.

    The engine's to-hit result is not clamped to 100 without positional data,
    so a maximal roll alone is not a guaranteed miss — tests using this fixture
    also drive the target's evasion past the ``floor=5`` clamp, which holds
    whatever ``HIT_CHANCE_BASE`` is retuned to.
    """
    monkeypatch.setattr(random, "randint", lambda a, b: b)
    monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)


# ---------------------------------------------------------------------------
# Contract / wiring
# ---------------------------------------------------------------------------


def test_disrupt_is_exported_and_declares_its_ui_contracts():
    assert "Disrupt" in moves.__all__
    assert moves.Disrupt.display_name
    # Routed by CATEGORY_GROUPS' Offensive button; animation exists frontend-side.
    # (The exhaustive checks live in the two contract test modules.)
    assert moves.Disrupt.web_animation == "quick_attack"


def test_disrupt_is_a_cheap_basic_skill():
    """Basic-tree placement and price, relative to its neighbours."""
    from src.skilltree import Skilltree

    player = FakePlayer()
    basic = Skilltree(player).subtypes["Basic"]
    costs = {type(m).__name__: cost for m, cost in basic.items()}
    assert "Disrupt" in costs
    assert costs["Disrupt"] <= costs["StrategicInsight"]
    assert costs["Disrupt"] < min(
        costs["TacticalPositioning"], costs["MasterTactician"]
    )


def test_short_prep_and_long_cooldown():
    """The two levers the design depends on: it arrives fast and it is rationed."""
    player = FakePlayer()
    move = moves.Disrupt(player)
    prep, _execute, _recoil, cooldown = move.stage_beat
    assert prep <= 1, "a reaction verb has to arrive inside the wind-up window"
    assert cooldown >= 10, "the cooldown is what rations it"
    # Cheap: well under a basic Attack's fatigue with the same loadout.
    assert move.fatigue_cost < moves.Attack(player).fatigue_cost


def test_damage_is_much_lower_than_a_basic_attack():
    player = FakePlayer()
    assert moves.Disrupt(player).power < moves.Attack(player).power / 2


def test_preview_hit_chance_matches_what_execute_rolls(monkeypatch):
    """The preview must report the number execute() actually compares against.

    Enforced structurally: execute() calls preview_hit_chance for its own
    threshold, so this test pins that wiring rather than a percentage.
    """
    player, enemy, move = _engaged()
    seen = {}

    real_preview = move.preview_hit_chance

    def spy(target=None):
        value = real_preview(target)
        seen["chance"] = value
        return value

    move.preview_hit_chance = spy
    rolls = []
    monkeypatch.setattr(random, "randint", lambda a, b: rolls.append((a, b)) or a)
    with capture_narration():
        move.execute(player)

    assert seen["chance"] is not None
    assert seen["chance"] == move.preview_hit_chance(enemy)
    assert rolls == [(0, 100)]


def test_preview_hit_chance_is_none_when_out_of_reach():
    player, enemy, move = _engaged(distance=999)
    assert move.viable() is False
    assert move.preview_hit_chance(enemy) is None


def test_viability_ignores_allies_and_respects_reach():
    player, enemy, move = _engaged(distance=2)
    assert move.viable() is True

    # An ally standing next to Jean is not a reason the move is viable.
    ally = FakeEnemy(name="Gorran")
    player.combat_proximity = {enemy: 999, ally: 1}
    assert move.viable() is False


# ---------------------------------------------------------------------------
# The window: interrupts a move in PREP
# ---------------------------------------------------------------------------


def test_interrupts_a_target_that_is_still_winding_up(always_hits):
    player, enemy, move = _engaged()
    winding = _winding(enemy, stage=MOVE_STAGE_PREP, beats_left=4)

    with capture_narration():
        move.execute(player)

    assert winding.interrupted is True
    assert enemy.hp < enemy.maxhp, "it should still do its small damage"


def test_the_interrupted_move_actually_aborts_and_never_lands(always_hits):
    """End to end through the engine's own stage machine, not just the flag."""
    player, enemy, move = _engaged()
    winding = _winding(
        enemy, stage=MOVE_STAGE_PREP, beats_left=4, stage_beat=(6, 1, 2, 4)
    )

    with capture_narration():
        move.execute(player)

    winding.advance(enemy)  # the target's very next beat

    assert winding.interrupted is False, "flag consumed by advance()"
    assert winding.current_stage == MOVE_STAGE_COOLDOWN
    assert winding.beats_left == 4, "the target still pays the move's cooldown"
    assert enemy.current_move is None

    # Run the fight forward: the cancelled move must never execute.
    for _ in range(30):
        winding.advance(enemy)
    assert winding.executions == 0


def test_interrupt_awards_the_read(always_hits):
    player, enemy, move = _engaged()
    _winding(enemy, stage=MOVE_STAGE_PREP)
    before = player.combat_exp["Basic"]

    with capture_narration():
        move.execute(player)

    missed_player, missed_enemy, missed_move = _engaged()
    missed_move.target = missed_enemy
    missed_enemy.current_move = None
    with capture_narration():
        missed_move.execute(missed_player)

    assert player.combat_exp["Basic"] - before > (
        missed_player.combat_exp["Basic"] - 0
    ), "landing the read must pay better than swinging at nothing"


def test_a_cancel_does_not_also_stagger(always_hits):
    """Cancel *or* stagger, never both — stacking them compounds into a lock."""
    player, enemy, move = _engaged()
    _winding(enemy, stage=MOVE_STAGE_PREP)

    with capture_narration():
        move.execute(player)

    assert not any(getattr(s, "name", "") == "Staggered" for s in enemy.states)


# ---------------------------------------------------------------------------
# The brace: a cancelled target can't be cancelled twice running
# ---------------------------------------------------------------------------


def _land_in_window(player, enemy, move):
    """Land one Disrupt on a freshly winding target; return that wind-up."""
    winding = _winding(enemy, stage=MOVE_STAGE_PREP, beats_left=5)
    with capture_narration():
        move.execute(player)
    return winding


def test_a_cancel_leaves_the_target_braced(always_hits):
    player, enemy, move = _engaged()
    first = _land_in_window(player, enemy, move)

    assert first.interrupted is True
    assert getattr(enemy, moves.Disrupt.BRACE_ATTR) is True


def test_the_second_read_staggers_instead_of_cancelling(always_hits):
    player, enemy, move = _engaged()
    _land_in_window(player, enemy, move)
    second = _land_in_window(player, enemy, move)

    assert second.interrupted is False, "a braced target must not be cancelled"
    assert any(getattr(s, "name", "") == "Staggered" for s in enemy.states)
    assert getattr(enemy, moves.Disrupt.BRACE_ATTR) is False


def test_the_stagger_is_strictly_weaker_than_the_cancel(always_hits):
    """The braced wind-up still resolves; only the target's next move slows."""
    player, enemy, move = _engaged()
    _land_in_window(player, enemy, move)

    braced = _winding(
        enemy, stage=MOVE_STAGE_PREP, beats_left=2, stage_beat=(6, 1, 2, 4)
    )
    with capture_narration():
        move.execute(player)

    for _ in range(6):
        with capture_narration():
            braced.advance(enemy)
    assert braced.executions == 1, "the staggered wind-up must still land"

    # ...but the target's *next* cast pays the Staggered prep penalty.
    follow_up = CountingMove(enemy, stage_beat=(6, 1, 2, 4))
    follow_up.cast()
    assert follow_up.beats_left > follow_up.stage_beat[0]


def test_the_brace_alternates_so_cancels_resume(always_hits):
    player, enemy, move = _engaged()
    outcomes = []
    for _ in range(4):
        enemy.states = []
        outcomes.append(_land_in_window(player, enemy, move).interrupted)
    assert outcomes == [True, False, True, False]


def test_a_read_that_lands_outside_the_window_does_not_spend_the_brace(always_hits):
    player, enemy, move = _engaged()
    _land_in_window(player, enemy, move)  # target now braced

    # A poke that connects while the target is mid-execute buys nothing at all,
    # and must not be usable to burn the brace off for free.
    _winding(enemy, stage=MOVE_STAGE_EXECUTE, beats_left=1)
    with capture_narration():
        move.execute(player)
    assert getattr(enemy, moves.Disrupt.BRACE_ATTR) is True


# ---------------------------------------------------------------------------
# Outside the window: no interrupt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stage", [MOVE_STAGE_EXECUTE, MOVE_STAGE_RECOIL, MOVE_STAGE_COOLDOWN]
)
def test_does_not_interrupt_outside_the_prep_stage(always_hits, stage):
    player, enemy, move = _engaged()
    other = _winding(enemy, stage=stage, beats_left=2)
    enemy.known_moves = [other]

    with capture_narration():
        move.execute(player)

    assert other.interrupted is False
    assert enemy.hp < enemy.maxhp, "it still connects — it just buys nothing"


def test_does_not_interrupt_a_target_with_no_move_at_all(always_hits):
    player, enemy, move = _engaged()
    enemy.current_move = None
    enemy.known_moves = []

    with capture_narration():
        move.execute(player)

    assert enemy.hp < enemy.maxhp


def test_idle_move_sitting_at_stage_zero_is_not_a_windup(always_hits):
    """A move reset to stage 0 but never selected is not a wind-up.

    ``current_move`` is the discriminator: an unselected move parked at its
    reset stage must not read as an opening.
    """
    player, enemy, move = _engaged()
    idle = CountingMove(enemy)
    idle.current_stage = MOVE_STAGE_PREP
    enemy.current_move = None
    enemy.known_moves = [idle]

    with capture_narration():
        move.execute(player)

    assert idle.interrupted is False


# ---------------------------------------------------------------------------
# The roll gates the interrupt
# ---------------------------------------------------------------------------


def test_a_miss_interrupts_nothing(always_misses):
    player, enemy, move = _engaged()
    enemy.finesse = 500  # evasion past the to-hit floor: this cannot land
    winding = _winding(enemy, stage=MOVE_STAGE_PREP)
    hp_before = enemy.hp

    with capture_narration():
        move.execute(player)

    assert winding.interrupted is False
    assert enemy.hp == hp_before


def test_an_out_of_range_disrupt_auto_misses_and_interrupts_nothing(always_hits):
    player, enemy, move = _engaged(distance=999)
    winding = _winding(enemy, stage=MOVE_STAGE_PREP)
    hp_before = enemy.hp

    with capture_narration():
        move.execute(player)

    assert winding.interrupted is False
    assert enemy.hp == hp_before


def test_a_parried_disrupt_interrupts_nothing(always_hits):
    player, enemy, move = _engaged()
    winding = _winding(enemy, stage=MOVE_STAGE_PREP)

    class Parrying:
        name = "Parrying"

    enemy.states = [Parrying()]
    hp_before = enemy.hp

    with capture_narration():
        move.execute(player)

    assert winding.interrupted is False
    assert enemy.hp == hp_before


def test_a_dead_target_is_not_interrupted(always_hits):
    player, enemy, move = _engaged()
    winding = _winding(enemy, stage=MOVE_STAGE_PREP)
    enemy.hp = 0

    with capture_narration():
        move.execute(player)

    assert winding.interrupted is False


# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------


def test_disrupt_is_unavailable_until_its_cooldown_drains(always_hits):
    """Walk the real stage machine: it must not be re-castable mid-cycle.

    Availability in the API layer is gated on ``current_stage == 0``, so that
    is what this asserts, beat by beat, through ``Move.advance``.
    """
    player, enemy, move = _engaged()
    _cast(move, player)

    stages_seen = []
    landed_on_beat = None
    ready_again_on_beat = None
    for beat in range(1, 60):
        with capture_narration():
            move.advance(player)
        stages_seen.append(move.current_stage)
        if landed_on_beat is None and move.current_stage >= MOVE_STAGE_RECOIL:
            landed_on_beat = beat
        if landed_on_beat is not None and move.current_stage == MOVE_STAGE_PREP:
            ready_again_on_beat = beat
            break

    assert landed_on_beat is not None, "the move never resolved"
    assert ready_again_on_beat is not None, "the move never came off cooldown"
    # It spends the whole cooldown at a non-zero stage, i.e. unavailable.
    assert MOVE_STAGE_COOLDOWN in stages_seen
    assert ready_again_on_beat - landed_on_beat >= move.stage_beat[3]


# ---------------------------------------------------------------------------
# Balance: spamming it is neither a lock nor a win
# ---------------------------------------------------------------------------


def _simulate(beats, player, disrupt, enemy, enemy_stage_beat):
    """Beat-accurate fight loop: Jean casts Disrupt the instant it is ready,
    the enemy re-casts its move the instant it is free. Returns the enemy's
    landed-move count.
    """
    landed = 0
    enemy_move = CountingMove(enemy, stage_beat=enemy_stage_beat)
    with capture_narration():
        enemy_move.cast()
    enemy.current_move = enemy_move

    for _ in range(beats):
        if player.current_move is None and disrupt.current_stage == MOVE_STAGE_PREP:
            with capture_narration():
                _cast(disrupt, player)
            disrupt.target = enemy
        with capture_narration():
            disrupt.advance(player)
            enemy_move.advance(enemy)
        if enemy_move.executions > landed:
            landed = enemy_move.executions
        if enemy.current_move is None and enemy_move.current_stage == MOVE_STAGE_PREP:
            with capture_narration():
                enemy_move.cast()
            enemy.current_move = enemy_move
    return landed


def test_spamming_disrupt_on_cooldown_does_not_lock_the_target(always_hits):
    """Jean mashes the button: cast the instant it is ready, always hitting.

    Against an enemy whose only move is a heavily telegraphed wind-up — the
    most lockable case there is — the enemy must still land moves.
    """
    player, enemy, move = _engaged()
    landed = _simulate(300, player, move, enemy, enemy_stage_beat=(8, 1, 2, 4))
    assert landed >= 5, (
        "Disrupt spam locked the target out of the fight — raise its cooldown"
    )


def _simulate_perfect_reads(beats, player, disrupt, enemy, enemy_stage_beat):
    """The adversarial case: Jean never wastes a Disrupt.

    He commits only when the target is winding up *and* the strike is certain
    to arrive before that wind-up resolves, so every single cast is a correct
    read. Returns ``(landed, reads)``.
    """
    # Time from cast to impact, walked off the move's own stage machine rather
    # than hardcoded, so a retune of STAGE_BEATS keeps this honest.
    with capture_narration():
        disrupt.cast()
    time_to_impact = disrupt.beats_until_resolve()

    landed = 0
    reads = 0
    enemy_move = CountingMove(enemy, stage_beat=enemy_stage_beat)
    with capture_narration():
        enemy_move.cast()
    enemy.current_move = enemy_move

    for _ in range(beats):
        window_open = (
            enemy.current_move is enemy_move
            and enemy_move.current_stage == MOVE_STAGE_PREP
            and enemy_move.beats_left >= time_to_impact
        )
        if (
            player.current_move is None
            and disrupt.current_stage == MOVE_STAGE_PREP
            and window_open
        ):
            with capture_narration():
                _cast(disrupt, player)
            disrupt.target = enemy
            reads += 1
        with capture_narration():
            disrupt.advance(player)
            enemy_move.advance(enemy)
        landed = enemy_move.executions
        if enemy.current_move is None and enemy_move.current_stage == MOVE_STAGE_PREP:
            with capture_narration():
                enemy_move.cast()
            enemy.current_move = enemy_move
    return landed, reads


def test_perfect_play_cannot_lock_even_a_very_slow_enemy(always_hits):
    """The anti-perma-lock guarantee, against the worst case for it.

    A 25-beat wind-up (the debug dummy's; the slowest real hostile move, King
    Slime's Tidal Surge, preps for 13) sits inside Disrupt's window for most of
    Jean's cycle, so cooldown alone would not save it — without the brace rule
    this scenario lands **zero** enemy moves. With it, every other correct read
    only staggers, so the enemy keeps resolving moves no matter how perfectly
    Jean plays.
    """
    player, enemy, move = _engaged()
    enemy.hp = enemy.maxhp = 10 ** 6  # a balance test, not a damage race
    landed, reads = _simulate_perfect_reads(
        400, player, move, enemy, enemy_stage_beat=(25, 1, 4, 10)
    )
    assert reads >= 4, "the scenario has to actually exercise the interrupt"
    assert landed >= max(3, reads // 3), (
        "perfect reads locked the target out of the fight: "
        f"{reads} interrupts, only {landed} enemy moves resolved"
    )


def test_spamming_disrupt_is_worse_damage_than_just_attacking(always_hits):
    """It is a tempo tool, not a damage tool: mashing it must lose a DPS race."""
    player_a, enemy_a, disrupt = _engaged()
    player_b, enemy_b, _ = _engaged()
    attack = moves.Attack(player_b)
    attack.target = enemy_b

    for cycle in (disrupt, attack):
        owner = player_a if cycle is disrupt else player_b
        with capture_narration():
            cycle.cast()
        owner.current_move = cycle
        for _ in range(200):
            if owner.current_move is None and cycle.current_stage == MOVE_STAGE_PREP:
                with capture_narration():
                    cycle.cast()
                owner.current_move = cycle
            with capture_narration():
                cycle.advance(owner)

    assert (enemy_a.maxhp - enemy_a.hp) < (enemy_b.maxhp - enemy_b.hp)


# ---------------------------------------------------------------------------
# The braced read must actually reach the target's next cast.
#
# These exist because a code scrub found the original braced branch was a
# SILENT NO-OP and the suite could not see it. Staggered's penalty is consumed
# only at Move.cast(), but the braced branch deliberately lets the current
# wind-up resolve -- execute, recoil and cooldown all come first -- and the
# state's default lifetime of three beats expired long before then. Nothing
# here ticked cycle_states, so the state never had a chance to expire in a
# test, and FakeEnemy's stun resistance of 0.0 meant inflict() never failed
# either. Both blind spots are closed below.
# ---------------------------------------------------------------------------


def _tick_states(entity, beats):
    """Advance `entity`'s states by `beats` through the ENGINE's own pump.

    Calls `Combatant.cycle_states` rather than re-implementing its loop, so a
    change to how states are cycled is felt here instead of being masked by a
    private copy — the file's stated preference elsewhere ("end to end through
    the engine's own stage machine, not just the flag").
    """
    for _ in range(beats):
        Combatant.cycle_states(entity)


def test_braced_stagger_outlives_the_windup_it_let_through(always_hits):
    """The braced read is strictly weaker than a cancel -- not worthless."""
    player, enemy, move = _engaged()
    setattr(enemy, moves.Disrupt.BRACE_ATTR, True)  # braced -> stagger branch

    winding = _winding(enemy, beats_left=4, stage_beat=(6, 1, 2, 4))
    _cast(move, player)
    move.execute(player)

    staggered = [s for s in enemy.states if s.name == "Staggered"]
    assert staggered, "the braced read applied no state at all"

    # Beats the target must still burn before its next cast(): the rest of
    # prep, then execute + recoil + cooldown.
    remaining = winding.beats_left + sum(winding.stage_beat[1:])
    _tick_states(enemy, remaining)

    assert [s for s in enemy.states if s.name == "Staggered"], (
        "Staggered expired before the target could reach its next cast, so the "
        "braced read did nothing — the exact silent no-op this guards"
    )

    # Existing-but-expired is only a proxy. The behaviour that matters is that
    # the penalty is COLLECTED: Move.cast() reads Staggered and adds
    # prep_penalty beats. Prove it lands on the target's next move.
    follow_up = CountingMove(enemy, stage_beat=(6, 1, 2, 4))
    with capture_narration():
        follow_up.cast()
    assert follow_up.beats_left > follow_up.stage_beat[0], (
        f"the follow-up move cast at {follow_up.beats_left} prep beats against a "
        f"base of {follow_up.stage_beat[0]} — the stagger was never collected"
    )


def test_braced_stagger_is_not_narrated_when_resistance_blocks_it(always_hits):
    """A stun-immune target must not be told it was knocked off balance."""
    player, enemy, move = _engaged()
    enemy.status_resistance["stun"] = 1.0  # fully immune
    setattr(enemy, moves.Disrupt.BRACE_ATTR, True)

    _winding(enemy, stage=MOVE_STAGE_PREP, beats_left=4)
    _cast(move, player)
    with capture_narration() as narration:
        move.execute(player)

    spoken = " ".join(entry.get("text", "") for entry in narration)
    assert "knocked off balance" not in spoken, (
        f"narrated a stagger that resistance blocked: {spoken!r}"
    )
    assert "unshaken" in spoken, (
        f"expected the resisted-stagger line; got {spoken!r}"
    )
    assert not [s for s in enemy.states if s.name == "Staggered"]
    # The brace is still spent -- the anti-lock alternation must not depend on
    # whether the stagger happened to land.
    assert getattr(enemy, moves.Disrupt.BRACE_ATTR) is False
