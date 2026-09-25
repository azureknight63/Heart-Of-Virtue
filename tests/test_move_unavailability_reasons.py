"""Why a move is locked, as a closed vocabulary of reason codes (#627).

``viable()`` returns a bare bool, so for roughly two dozen untargeted moves the
only sentence the move card could ever show was the adapter's catch-all
"Cannot use this move" -- a whole column of locked cards saying the same
nothing for unrelated reasons.

``Move.unavailability_reason()`` is the engine answering *why*: ``None`` when
the move is viable, otherwise one code from ``UnavailableReason``. ``viable()``
stays the rule; these tests hold the reason to it from both directions:

* over a seeded spread of real engine states, ``viable()`` is False exactly
  when ``unavailability_reason()`` is not None, for every castable move; and
* a move's own diagnosis (``_unavailability_code``) never names a blocker
  while ``viable()`` says yes -- a false accusation is worse than the shrug.

Then each move the issue lists is driven into each of its real failing
conditions and must name that condition, not the generic code.
"""

import inspect
import random

import pytest

import src.items as items
import src.moves as moves
import src.states as states
from _combat_fixtures import (
    WEAPON_BY_SUBTYPE,
    engage,
    make_adapter,
    make_npc,
    make_player,
    make_weapon,
    place,
    seeded,
)
from src.moves._base import (
    UNAVAILABILITY_TEXT,
    Move,
    PassiveMove,
    UnavailableReason as R,
)
from src.npc import Slime


# ── the vocabulary itself ───────────────────────────────────────────────────

def test_every_code_has_exactly_one_sentence():
    assert set(UNAVAILABILITY_TEXT) == set(R)
    for code, text in UNAVAILABILITY_TEXT.items():
        assert isinstance(text, str) and text.strip() == text and text, code
        # Terse card copy: one short clause, no trailing full stop.
        assert len(text) <= 48, (code, text)
        assert not text.endswith("."), (code, text)


def test_codes_are_plain_wire_strings():
    for code in R:
        assert isinstance(code, str)
        assert code.value == code.value.lower()


def test_the_base_move_is_never_unavailable():
    move = moves.Wait(make_player())
    assert move.viable()
    assert move.unavailability_reason() is None


def test_a_passive_is_unavailable_but_says_nothing_specific():
    move = moves.StrategicInsight(make_player())
    assert move.unavailability_reason() is R.UNAVAILABLE


# ── agreement with viable() across a spread of real states ──────────────────

def _player_castable_classes():
    """Every concrete Move a Player can instantiate, passives excluded.

    NPC-only moves that cannot be built around a Player (they read
    ``user.target`` at construction) are skipped: they never reach a move
    card, and their viability belongs to the AI, not the player.
    """
    found = []
    for name, cls in sorted(vars(moves).items()):
        if not (inspect.isclass(cls) and issubclass(cls, Move)):
            continue
        if cls in (Move, PassiveMove) or issubclass(cls, PassiveMove):
            continue
        try:
            cls(make_player())
        except AttributeError:
            continue
        found.append(cls)
    return found


CASTABLE = _player_castable_classes()

_STATE_FACTORIES = (
    states.Parrying,
    states.Fervent,
    states.Hollowed,
    states.BloodOfMartyrsState,
)


def _random_state(rng):
    """A real Player in a real fight, with its situation drawn from ``rng``."""
    # Never an empty hand: a Player always falls back to Fists ("Unarmed"),
    # and Attack's evaluate() assumes as much.
    player = make_player(weapon=rng.choice(sorted(WEAPON_BY_SUBTYPE)))
    for stat in ("strength", "finesse", "speed", "endurance",
                 "charisma", "intelligence", "faith"):
        setattr(player, stat, rng.randint(5, 14))
    enemy = make_npc(Slime)
    allies = [make_npc(Slime)] if rng.random() < 0.4 else []
    engage(player, [enemy], allies, with_positions=False)
    player.in_combat = rng.random() < 0.8
    if rng.random() < 0.25:
        enemy.hp = 0
    distance = rng.choice([1, 2, 3, 5, 8, 12, 25, 60, 150])
    if rng.random() < 0.15:
        player.combat_proximity = {}
    else:
        player.combat_proximity = {enemy: distance}
        for ally in allies:
            player.combat_proximity[ally] = rng.choice([1, 3, 30])
    if rng.random() < 0.8:
        place(player, 10, 10)
        place(enemy, 10 + distance // 5, 10)
        for i, ally in enumerate(allies):
            place(ally, 9, 10 + i)
    else:
        player.combat_position = None
    player.states = [
        factory(player) for factory in _STATE_FACTORIES if rng.random() < 0.2
    ]
    player.fatigue = rng.choice([0, player.maxfatigue // 2, player.maxfatigue])
    player.inventory = rng.choice([
        [],
        [items.Restorative()],
        [items.WoodenArrow()],
        [items.Gold()],
        # A spare weapon (Jean holds Fists): the only way SwapWeapon is ever
        # viable, so without it that move's no-false-accusation check below
        # never ran.
        [items.Dagger()],
    ])
    return player


_SPREAD_CACHE = {}


def _spread(count=60, seed=627):
    """The seeded states, built once per module: a real Player is not free,
    and ``viable()`` only reads them. Each test builds its own move per state.
    """
    key = (count, seed)
    if key not in _SPREAD_CACHE:
        rng = random.Random(seed)
        with seeded(seed):
            _SPREAD_CACHE[key] = [_random_state(rng) for _ in range(count)]
    return _SPREAD_CACHE[key]


@pytest.mark.parametrize("cls", CASTABLE, ids=lambda c: c.__name__)
def test_reason_is_none_exactly_when_viable(cls):
    exercised = {True: 0, False: 0}
    for player in _spread():
        move = cls(player)
        viable = bool(move.viable())
        reason = move.unavailability_reason()
        exercised[viable] += 1
        assert (reason is None) == viable, (cls.__name__, viable, reason)
        if reason is not None:
            assert reason in set(R), reason
    # The spread must actually reach a listed move's refusal, or the parity
    # above checked nothing for it.
    # Parry is exempt: it refuses only an empty hand, which a Player never
    # has (Fists), so no real state reaches it -- its unit test below does.
    if cls.__name__ in _SPECIFIC - {"Parry"}:
        assert exercised[False], f"{cls.__name__}: spread never made it unviable"
    # And the other half: a move the spread never makes viable has had only
    # one side of the parity checked, and test_a_diagnosis_never_accuses_a_
    # viable_move checks nothing for it.
    if cls.__name__ in _BOTH_SIDES:
        assert exercised[True], f"{cls.__name__}: spread never made it viable"
        assert exercised[False], f"{cls.__name__}: spread never made it unviable"


@pytest.mark.parametrize("cls", CASTABLE, ids=lambda c: c.__name__)
def test_a_diagnosis_never_accuses_a_viable_move(cls):
    for player in _spread():
        move = cls(player)
        if move.viable():
            assert move._unavailability_code() is None, cls.__name__


#: The moves #627 names, each driven into each of its real failing conditions
#: below. The ungated ones (Dodge, Wait, Check) are pinned separately: they
#: have no viable() gate, so only a cooldown or fatigue can lock them, and the
#: adapter names those. StrategicInsight and MasterTactician are passives and
#: never reach a move card.
#: Moves the spread must reach on BOTH sides of viable(). SwapWeapon is here
#: because its only viable state (a spare weapon) had to be added to the spread.
_BOTH_SIDES = {"SwapWeapon"}

_SPECIFIC = {
    "Parry", "Withdraw", "TacticalRetreat", "Turn", "Rest", "CrusaderOath",
    "Ironhide", "WarCry", "SecretPlans", "BloodOfMartyrs", "Hawkeye",
    "BracePosition", "WhirlAttack", "Reap", "Sweep", "HalberdSpin",
    "UseItem", "Riposte", "ShootBow", "Pulverize", "KillingPrecision",
    "LightningAssault", "Advance", "QuickSwap",
}


@pytest.mark.parametrize(
    "cls", [c for c in CASTABLE if c.__name__ in _SPECIFIC],
    ids=lambda c: c.__name__,
)
def test_a_listed_move_never_falls_back_to_the_generic_code(cls):
    for player in _spread():
        move = cls(player)
        if not move.viable():
            if cls.__name__ == "Advance" and not player.combat_proximity:
                # #691: an empty/not-yet-built combat_proximity (the first
                # status poll right after a fight is joined) is genuinely
                # unmeasured, not a specific blocker -- the generic code is
                # the honest answer, not a gap in Advance's diagnosis.
                continue
            assert move.unavailability_reason() is not R.UNAVAILABLE, (
                f"{cls.__name__} refused in a state its diagnosis cannot name"
            )


def test_every_listed_move_is_in_the_castable_scan():
    assert _SPECIFIC <= {c.__name__ for c in CASTABLE}


@pytest.mark.parametrize("cls", [moves.Dodge, moves.Wait, moves.Check])
def test_the_ungated_moves_are_never_refused_by_the_engine(cls):
    for player in _spread(count=15):
        assert cls(player).unavailability_reason() is None


# ── each listed move, each real failing condition ───────────────────────────

def _jean(weapon="Sword", distance=5, **stats):
    """Jean in a real fight with one Slime ``distance`` ft away, positioned."""
    with seeded(627):
        player = make_player(weapon=weapon, **stats)
        enemy = make_npc(Slime)
        engage(player, [enemy], with_positions=False)
    player.combat_proximity = {enemy: distance}
    place(player, 10, 10)
    place(enemy, 10 + max(1, distance // 5), 10)
    player.fatigue = 0
    return player, enemy


def _make_highest(player, stat):
    for name in ("strength", "finesse", "speed", "endurance",
                 "charisma", "intelligence", "faith"):
        setattr(player, name, 8)
    setattr(player, stat, 12)


def _make_not_highest(player, stat):
    _make_highest(player, "strength" if stat != "strength" else "speed")


def _reason(cls, player):
    return cls(player).unavailability_reason()


def test_parry_bare_of_any_weapon():
    player, _ = _jean()
    player.eq_weapon = None
    assert _reason(moves.Parry, player) is R.NO_WEAPON


def test_withdraw_with_nothing_close():
    player, _ = _jean(distance=150)
    assert _reason(moves.Withdraw, player) is R.NO_ENEMY_NEAR


def test_tactical_retreat_with_nobody_on_the_field():
    player, _ = _jean()
    player.combat_proximity = {}
    assert _reason(moves.TacticalRetreat, player) is R.NO_OPPONENTS


def test_turn_off_the_grid():
    player, _ = _jean()
    player.combat_position = None
    assert _reason(moves.Turn, player) is R.NOT_POSITIONED


def test_rest_when_already_rested():
    player, _ = _jean()
    player.fatigue = player.maxfatigue
    assert _reason(moves.Rest, player) is R.FULLY_RESTED


def test_use_item_with_nothing_usable():
    player, _ = _jean()
    player.inventory = [items.Gold()]
    assert _reason(moves.UseItem, player) is R.NO_USABLE_ITEMS
    player.inventory = []
    assert _reason(moves.UseItem, player) is R.NO_USABLE_ITEMS


class TestCrusaderOath:
    def _ready(self):
        player, _ = _jean()
        _make_highest(player, "faith")
        return player

    def test_out_of_combat(self):
        player = self._ready()
        player.in_combat = False
        assert _reason(moves.CrusaderOath, player) is R.NOT_IN_COMBAT

    def test_apathy(self):
        player = self._ready()
        with seeded(1):
            player.states = [states.Hollowed(player)]
        assert _reason(moves.CrusaderOath, player) is R.APATHY

    def test_already_fervent(self):
        player = self._ready()
        player.states = [states.Fervent(player)]
        assert _reason(moves.CrusaderOath, player) is R.ALREADY_ACTIVE

    def test_faith_lowest(self):
        player = self._ready()
        _make_highest(player, "strength")
        player.faith = 3
        assert _reason(moves.CrusaderOath, player) is R.FAITH_TOO_LOW


_STAT_MASTERIES = [
    (moves.Ironhide, "endurance"),
    (moves.WarCry, "charisma"),
    (moves.SecretPlans, "intelligence"),
    (moves.BloodOfMartyrs, "faith"),
    (moves.Pulverize, "strength"),
    (moves.KillingPrecision, "finesse"),
    (moves.LightningAssault, "speed"),
]


@pytest.mark.parametrize("cls, stat", _STAT_MASTERIES, ids=lambda x: getattr(x, "__name__", x))
def test_a_mastery_out_of_combat(cls, stat):
    player, _ = _jean()
    _make_highest(player, stat)
    player.in_combat = False
    assert _reason(cls, player) is R.NOT_IN_COMBAT


@pytest.mark.parametrize("cls, stat", _STAT_MASTERIES, ids=lambda x: getattr(x, "__name__", x))
def test_a_mastery_whose_attribute_is_not_the_highest(cls, stat):
    player, _ = _jean()
    _make_not_highest(player, stat)
    assert _reason(cls, player) is R.ATTRIBUTE_NOT_HIGHEST


def test_a_mastery_tied_for_highest_is_not_the_highest():
    player, _ = _jean()
    _make_highest(player, "endurance")
    player.strength = player.endurance
    assert _reason(moves.Ironhide, player) is R.ATTRIBUTE_NOT_HIGHEST


@pytest.mark.parametrize(
    "cls, stat",
    [(moves.Pulverize, "strength"), (moves.KillingPrecision, "finesse"),
     (moves.LightningAssault, "speed")],
    ids=lambda x: getattr(x, "__name__", x),
)
def test_a_striking_mastery_out_of_reach(cls, stat):
    player, _ = _jean(distance=150)
    _make_highest(player, stat)
    assert _reason(cls, player) is R.NO_ENEMY_IN_REACH


def test_blood_of_martyrs_already_absorbing():
    player, _ = _jean()
    _make_highest(player, "faith")
    player.states = [states.BloodOfMartyrsState(player)]
    assert _reason(moves.BloodOfMartyrs, player) is R.ALREADY_ACTIVE


def test_hawkeye_out_of_combat_and_without_a_bow():
    player, _ = _jean(weapon="Bow")
    player.in_combat = False
    assert _reason(moves.Hawkeye, player) is R.NOT_IN_COMBAT
    player.in_combat = True
    player.eq_weapon = make_weapon("Sword")
    assert _reason(moves.Hawkeye, player) is R.WRONG_WEAPON
    player.eq_weapon = None
    assert _reason(moves.Hawkeye, player) is R.NO_WEAPON


def test_brace_position_without_a_polearm():
    player, _ = _jean(weapon="Sword")
    assert _reason(moves.BracePosition, player) is R.WRONG_WEAPON
    player.eq_weapon = None
    assert _reason(moves.BracePosition, player) is R.NO_WEAPON


@pytest.mark.parametrize("cls", [moves.Sweep, moves.HalberdSpin])
def test_a_polearm_arc_swing(cls):
    player, _ = _jean(weapon="Sword", distance=2)
    assert _reason(cls, player) is R.WRONG_WEAPON
    player, _ = _jean(weapon="Polearm", distance=60)
    assert _reason(cls, player) is R.NO_ENEMY_IN_REACH


def test_an_ally_beside_jean_does_not_make_an_arc_swing_reachable():
    player, enemy = _jean(weapon="Polearm", distance=60)
    ally = make_npc(Slime)
    player.combat_proximity[ally] = 1
    assert _reason(moves.Sweep, player) is R.NO_ENEMY_IN_REACH


def test_reap():
    player, enemy = _jean(weapon="Sword")
    assert _reason(moves.Reap, player) is R.WRONG_WEAPON
    player, enemy = _jean(weapon="Scythe")
    enemy.hp = 0
    assert _reason(moves.Reap, player) is R.NO_OPPONENTS


def test_whirl_attack():
    player, _ = _jean()
    player.combat_position = None
    assert _reason(moves.WhirlAttack, player) is R.NOT_POSITIONED
    player, enemy = _jean()
    place(enemy, 45, 45)
    assert _reason(moves.WhirlAttack, player) is R.NO_ENEMY_IN_REACH


def test_riposte_only_while_parrying():
    player, _ = _jean(weapon="Sword", distance=3)
    assert _reason(moves.Riposte, player) is R.REQUIRES_PARRY
    player.states = [states.Parrying(player)]
    assert _reason(moves.Riposte, player) is None


def test_shoot_bow_without_arrows():
    player, _ = _jean(weapon="Bow", distance=20)
    player.inventory = []
    assert _reason(moves.ShootBow, player) is R.NO_AMMUNITION
    player.inventory = [items.WoodenArrow()]
    assert _reason(moves.ShootBow, player) is None


def test_shoot_bow_is_simply_unviable_with_another_weapon_and_arrows():
    """Regression: with arrows in the pack and a non-bow in hand, viable()
    raised AttributeError (the arrow's range was folded against a weapon with
    no ``range_base``) instead of answering False -- and the adapter calls
    viable() unguarded for every known move on every combat poll."""
    player, _ = _jean(weapon="Axe", distance=20)
    player.inventory = [items.WoodenArrow()]
    move = moves.ShootBow(player)
    assert move.viable() is False
    assert move.unavailability_reason() is R.WRONG_WEAPON


def test_advance_with_everyone_adjacent():
    player, _ = _jean(distance=1)
    assert _reason(moves.Advance, player) is R.ALREADY_ADJACENT


def test_advance_stale_target_from_a_prior_fight_is_reset_on_new_combat():
    """#691: Advance.target is only reassigned once a cast completes
    (combat_adapter.py) and is never reset on its own, so a target chosen in
    a PRIOR fight (or a corpse from it) can still be sitting on the move when
    a brand new fight starts. If that stale reference happened to still be
    "adjacent" (distance <= 1) it would out-vote real, farther-away enemies
    via Advance's own target-specific branch -- ``ApiCombatAdapter`` fixes
    this at the source, by clearing a move's target when it names someone
    outside the new fight's roster, rather than in ``Advance`` itself
    (``test_advance_with_multiple_enemies_but_target_close`` below pins that
    a live, currently-selected, IN-FIGHT target that is already adjacent
    correctly keeps Advance unviable, even with another enemy far away --
    Advance walks toward ``self.target`` specifically, so "viable" would be
    a false promise there).
    """
    player = make_player(weapon="Sword")
    foreign_target = make_npc(Slime)  # from a fight that has already ended
    advance = next(m for m in player.known_moves if isinstance(m, moves.Advance))
    advance.target = foreign_target

    enemy1 = make_npc(Slime)
    enemy2 = make_npc(Slime)
    with seeded(627):
        adapter = make_adapter(player, enemies=[enemy1, enemy2])

    assert advance.target is not foreign_target
    assert advance.viable() is True
    assert adapter is not None  # keep the adapter alive for the assertion above


def test_advance_empty_proximity_is_not_already_adjacent():
    """#691 secondary: an empty/not-yet-built combat_proximity (as seen on
    the first /api/combat/status poll right after a fight is joined) is
    "not yet known", not "everyone is adjacent" -- it must not report
    ALREADY_ADJACENT."""
    player, _ = _jean()
    player.combat_proximity = {}
    move = moves.Advance(player)
    assert move.viable() is False
    assert move.unavailability_reason() is not R.ALREADY_ADJACENT


def test_quick_swap_with_no_ally():
    player, _ = _jean()
    assert _reason(moves.QuickSwap, player) is R.NO_ALLY_NEAR


def test_an_unknown_diagnosis_folds_to_the_generic_code():
    """A move author returning an out-of-vocabulary value must not reach the wire."""

    class Rogue(Move):
        display_name = "Rogue"

        def viable(self):
            return False

        def _unavailability_code(self):
            return "because I said so"

    player = make_player()
    move = Rogue(
        name="Rogue", description="", xp_gain=0, current_stage=0,
        stage_beat=[0, 0, 0, 0], targeted=False,
        stage_announce=["", "", "", ""], fatigue_cost=0, beats_left=0,
        target=player, user=player,
    )
    assert move.unavailability_reason() is R.UNAVAILABLE


# ── ShootBow checks its two blockers in one order (#674) ─────────────────────

def test_shoot_bow_with_no_arrows_and_nobody_in_range_blames_the_quiver():
    player, enemy = _jean(weapon="Bow", distance=20)
    player.combat_proximity[enemy] = 500
    player.inventory = []
    move = moves.ShootBow(player)
    assert move.viable() is False
    assert move.unavailability_reason() is R.NO_AMMUNITION


def test_shoot_bow_viable_and_its_diagnosis_check_arrows_first():
    """viable() and _unavailability_code must consult the same blocker first,
    or a refactor that stops short-circuiting one of them can name a blocker
    viable() never looked at. Both probes answer False, so each method stops
    at whichever it checks first."""
    player, _ = _jean(weapon="Bow", distance=20)
    move = moves.ShootBow(player)
    calls = []
    move._has_arrows = lambda: calls.append("arrows") or False
    move._enemy_in_range = lambda: calls.append("range") or False
    move.viable()
    viable_first = calls[0]
    calls.clear()
    move._unavailability_code()
    assert calls[0] == viable_first == "arrows"


# ── area/ranged reach ignores allies (#674) ──────────────────────────────────

def _jean_with_ally(weapon, enemy_distance, ally_distance):
    """Jean, one Slime ``enemy_distance`` ft off and one ally Slime
    ``ally_distance`` ft off -- the ally in combat_proximity exactly as
    positions.recalculate_proximity_dict puts it there."""
    with seeded(674):
        player = make_player(weapon=weapon)
        enemy = make_npc(Slime)
        ally = make_npc(Slime)
        engage(player, [enemy], allies=[ally], with_positions=False)
    player.combat_proximity = {enemy: enemy_distance, ally: ally_distance}
    place(player, 10, 10)
    place(enemy, min(50, 10 + max(1, enemy_distance // 5)), 10)
    place(ally, min(50, 10 + max(1, ally_distance // 5)), 10)
    player.fatigue = 0
    player.inventory = [items.WoodenArrow()]
    return player, enemy, ally


def test_whirl_attack_ignores_an_ally_in_reach():
    player, enemy, _ = _jean_with_ally("Sword", enemy_distance=200, ally_distance=1)
    move = moves.WhirlAttack(player)
    assert move.viable() is False
    assert move.unavailability_reason() is R.NO_ENEMY_IN_REACH
    place(enemy, 11, 10)
    assert move.viable() is True


def test_reap_ignores_a_living_ally():
    player, enemy, _ = _jean_with_ally("Scythe", enemy_distance=3, ally_distance=1)
    enemy.hp = 0
    move = moves.Reap(player)
    assert move.viable() is False
    assert move.unavailability_reason() is R.NO_OPPONENTS
    enemy.hp = 10
    assert move.viable() is True


def test_reapers_mark_ignores_a_living_ally():
    player, enemy, _ = _jean_with_ally("Scythe", enemy_distance=3, ally_distance=1)
    enemy.hp = 0
    move = moves.ReapersMark(player)
    assert move.viable() is False
    enemy.hp = 10
    assert move.viable() is True


def test_living_hostile_is_one_shared_move_helper():
    """Reap and Reaper's Mark ask the same question through one helper on
    ``Move``, beside ``_hostiles_in_proximity``, not a private copy each."""
    from src.moves._base import Move

    assert "_living_hostile" in Move.__dict__
    assert "_living_hostile" not in moves.Reap.__dict__
    assert "_living_hostile" not in moves.ReapersMark.__dict__


def test_shoot_bow_ignores_an_ally_in_range():
    player, enemy, ally = _jean_with_ally("Bow", enemy_distance=500, ally_distance=20)
    move = moves.ShootBow(player)
    assert move.viable() is False
    assert move.unavailability_reason() is R.NO_ENEMY_IN_REACH
    player.combat_proximity[enemy] = 20
    assert move.viable() is True
