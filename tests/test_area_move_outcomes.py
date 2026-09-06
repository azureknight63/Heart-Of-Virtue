"""Area moves must report one combat outcome PER TARGET, not one per swing.

A sweep that catches four enemies — one parried, one missed, two struck — is
four separate resolutions. Reporting a single outcome for the whole animation
picks whichever enemy happened to narrate first and applies its result to
everyone, which is precisely the class of lie the engine-asserted outcome
channel (``src/moves/_base.publish_outcome``) exists to remove.

Sweep, Halberd Spin, Reap and Chip Away narrate their own per-enemy lines and
never route through ``Move.hit()/miss()/parry()``, so before this they published
no outcome at all: the animation fell through to the adapter's end-of-move
fallback, no target ever flashed, and ``impactSfxFor(undefined)`` played the
full-damage flesh-impact cue for every swing including a whiff.
"""

import pathlib
import sys
from unittest.mock import MagicMock

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.states as states
from src.api.combat_adapter import CombatOutputCapture
from src.api.schemas.combat_beat import OUTCOMES
from src.moves._pick import ChipAway
from src.moves._polearm import HalberdSpin, Sweep
from src.moves._scythe import Reap
from src.narration import capture_narration


RESISTANCE = {
    "piercing": 1.0,
    "slashing": 1.0,
    "crushing": 1.0,
    "fire": 1.0,
    "ice": 1.0,
    "shock": 1.0,
    "earth": 1.0,
    "light": 1.0,
    "dark": 1.0,
    "spiritual": 1.0,
    "pure": 1.0,
}


def _make_weapon(subtype, damage=40, wpnrange=(0, 6)):
    wpn = MagicMock()
    wpn.subtype = subtype
    wpn.damage = damage
    wpn.name = f"Test {subtype}"
    wpn.wpnrange = wpnrange
    wpn.str_mod = 0.5
    wpn.fin_mod = 0.3
    wpn.weight = 4
    wpn.isequipped = True
    return wpn


def _make_user(subtype):
    user = MagicMock()
    user.name = "Swinger"          # never "Jean" — skips player-only bookkeeping
    user.strength = 15
    user.finesse = 10
    user.intelligence = 10
    user.endurance = 10
    user.speed = 10
    user.hp = 100
    user.maxhp = 100
    user.fatigue = 500
    user.maxfatigue = 500
    user.heat = 1.0
    user.protection = 5
    user.states = []
    user.known_moves = []
    user.combat_exp = {"Basic": 0, subtype: 0}
    user.combat_proximity = {}
    user.combat_list = []
    user.combat_list_allies = []
    user.combat_position = None
    user.friend = True
    user.is_alive = lambda: True
    user.resistance = dict(RESISTANCE)
    user.eq_weapon = _make_weapon(subtype)
    return user


def _make_enemy(name, protection=0, finesse=5):
    tgt = MagicMock()
    tgt.name = name
    tgt.hp = 500
    tgt.maxhp = 500
    tgt.finesse = finesse
    tgt.intelligence = 5
    tgt.protection = protection
    tgt.protection_base = protection
    tgt.states = []
    tgt.known_moves = []
    tgt.is_alive = lambda: True
    tgt.combat_position = None
    tgt.combat_proximity = {}
    tgt.resistance = dict(RESISTANCE)
    tgt.friend = False
    tgt._reapers_mark = False
    return tgt


def _arm(user, move):
    """Give ``user`` the pending animation the adapter stamps before a move."""
    user._pending_animation = {
        "type": getattr(move, "web_animation", "attack"),
        "source_id": "player",
        "target_id": None,
        "move_name": move.name,
        "move_display_name": move.name,
        "outcome": None,
    }
    return user._pending_animation


def _run(capture, fn):
    with capture_narration(listener=lambda e: capture.write(e.get("text", ""))):
        fn()
    return capture.get_log()


def _impacts(entries):
    return [e["animation_data"] for e in entries if e.get("trigger_animation")]


def _outcomes(entries):
    return [a.get("outcome") for a in _impacts(entries)]


def _fixed_rolls(monkeypatch, module, rolls):
    """Feed the to-hit dice a fixed sequence of rolls.

    ``module.random`` *is* the stdlib ``random`` module, so this patch is
    process-wide for the test's duration (monkeypatch undoes it). The
    ``module`` argument is therefore cosmetic -- every import site sees the
    same patched module -- and is kept only so each call site names the
    module under test; it scopes nothing.

    Rolls are consumed in ``combat_proximity`` insertion order -- reordering the
    enemies re-maps which one gets which roll.

    Running past the end of the sequence raises rather than returning a default.
    An exhausted sequence used to yield ``0``, an automatic hit, so a move that
    grew a fourth resolution kept passing on an invented roll -- the fixture
    would have silently stopped testing what it names.
    """
    seq = list(rolls)
    total = len(seq)

    def _randint(a, b):
        if not seq:
            raise AssertionError(
                f"the move rolled more than the {total} to-hit rolls this "
                "fixture supplies -- it resolves against more targets than "
                "the test accounts for"
            )
        return seq.pop(0)

    monkeypatch.setattr(module.random, "randint", _randint)


def _capture_for(user):
    capture = CombatOutputCapture()
    capture.active_entity = user
    return capture


# ── Sweep (polearm, frontal cone) ───────────────────────────────────────────


def test_sweep_publishes_one_outcome_per_enemy_in_the_arc(monkeypatch):
    """Three enemies, three distinct resolutions, three impacts."""
    import src.moves._polearm as polearm

    user = _make_user("Polearm")
    struck, parried, missed = (
        _make_enemy("Struck"),
        _make_enemy("Parried"),
        _make_enemy("Missed"),
    )
    parried.states = [states.Parrying(parried)]
    user.combat_proximity = {struck: 2, parried: 2, missed: 2}
    user.combat_list = [struck, parried, missed]

    move = Sweep(user)
    _arm(user, move)
    # hit / (roll lands, then parried) / whiff
    _fixed_rolls(monkeypatch, polearm, [0, 0, 100])

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert _outcomes(entries) == ["hit", "parry", "miss"], entries


def test_sweep_attributes_each_outcome_to_its_own_enemy(monkeypatch):
    """The whole point: an outcome names the enemy it happened to."""
    import src.moves._polearm as polearm
    from src.api.serializers.combat import CombatantSerializer

    user = _make_user("Polearm")
    struck, missed = _make_enemy("Struck"), _make_enemy("Missed")
    user.combat_proximity = {struck: 2, missed: 2}
    user.combat_list = [struck, missed]

    move = Sweep(user)
    _arm(user, move)
    _fixed_rolls(monkeypatch, polearm, [0, 100])

    entries = _run(_capture_for(user), lambda: move.execute(user))

    impacts = _impacts(entries)
    assert [i["target_id"] for i in impacts] == [
        CombatantSerializer.stream_id(struck),
        CombatantSerializer.stream_id(missed),
    ], impacts


def test_sweep_narrates_a_line_for_every_enemy_it_swings_at(monkeypatch):
    """A whiffed enemy used to produce no line at all — the swing simply went
    quiet, and the player had no way to tell a miss from an enemy standing
    outside the cone. Each published outcome needs its own line to ride on.
    """
    import src.moves._polearm as polearm

    user = _make_user("Polearm")
    missed = _make_enemy("Missed")
    user.combat_proximity = {missed: 2}
    user.combat_list = [missed]

    move = Sweep(user)
    _arm(user, move)
    _fixed_rolls(monkeypatch, polearm, [100])

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert any("Missed" in e["message"] for e in entries), entries


# ── Halberd Spin (polearm, full circle) ─────────────────────────────────────


def test_halberd_spin_publishes_one_outcome_per_enemy(monkeypatch):
    import src.moves._polearm as polearm

    user = _make_user("Polearm")
    struck, parried, missed = (
        _make_enemy("Struck"),
        _make_enemy("Parried"),
        _make_enemy("Missed"),
    )
    parried.states = [states.Parrying(parried)]
    user.combat_proximity = {struck: 2, parried: 2, missed: 2}
    user.combat_list = [struck, parried, missed]

    move = HalberdSpin(user)
    _arm(user, move)
    _fixed_rolls(monkeypatch, polearm, [0, 0, 100])

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert _outcomes(entries) == ["hit", "parry", "miss"], entries


# ── Reap (scythe, frontal cone) ─────────────────────────────────────────────


def test_reap_publishes_one_outcome_per_enemy(monkeypatch):
    import src.moves._scythe as scythe

    user = _make_user("Scythe")
    struck, parried, missed = (
        _make_enemy("Struck"),
        _make_enemy("Parried"),
        _make_enemy("Missed"),
    )
    parried.states = [states.Parrying(parried)]
    user.combat_proximity = {struck: 2, parried: 2, missed: 2}
    user.combat_list = [struck, parried, missed]

    move = Reap(user)
    _arm(user, move)
    _fixed_rolls(monkeypatch, scythe, [0, 0, 100])

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert _outcomes(entries) == ["hit", "parry", "miss"], entries


# ── Chip Away (pick, three strikes on ONE target) ───────────────────────────


def test_chip_away_publishes_one_outcome_per_strike(monkeypatch):
    """Chip Away's three strikes are three independent resolutions against the
    same target, so they are three impacts — not one summarising the flurry.
    """
    import src.moves._pick as pick

    user = _make_user("Pick")
    target = _make_enemy("Dummy")
    user.combat_proximity = {target: 2}
    user.combat_list = [target]

    move = ChipAway(user)
    move.target = target
    _arm(user, move)
    # strike 1 lands, strike 2 whiffs, strike 3 lands
    _fixed_rolls(monkeypatch, pick, [0, 100, 0])

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert _outcomes(entries) == ["hit", "miss", "hit"], entries


def test_chip_away_publishes_parry_for_a_parried_strike(monkeypatch):
    import src.moves._pick as pick

    user = _make_user("Pick")
    target = _make_enemy("Dummy")
    target.states = [states.Parrying(target)]
    user.combat_proximity = {target: 2}
    user.combat_list = [target]

    move = ChipAway(user)
    move.target = target
    _arm(user, move)
    _fixed_rolls(monkeypatch, pick, [0, 0, 0])

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert _outcomes(entries) == ["parry", "parry", "parry"], entries


def test_chip_away_publishes_absorb_when_armour_swallows_a_strike(monkeypatch):
    """A strike that lands under the target's protection deals 0 -- that is an
    ``absorb``, not a ``hit``, and must not play the flesh-impact cue. This is
    the publication rule ``resolve_strike_outcome`` applies itself
    (``OUTCOME_ABSORB if damage <= 0 else OUTCOME_HIT``, unconditionally);
    Chip Away is the caller whose damage line can actually produce the zero.
    """
    import src.moves._pick as pick

    user = _make_user("Pick")
    target = _make_enemy("Ironclad", protection=500)
    user.combat_proximity = {target: 2}
    user.combat_list = [target]

    move = ChipAway(user)
    move.target = target
    _arm(user, move)
    _fixed_rolls(monkeypatch, pick, [0, 0, 0])  # every strike lands

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert _outcomes(entries) == ["absorb", "absorb", "absorb"], entries
    assert target.hp == 500


def test_chip_away_seeded_sequence_pins_the_rng_draw_order(seeded):
    """Characterisation pin, no monkeypatched dice: for one fixed seed the
    flurry's exact outcome sequence and per-strike damage numbers are frozen.

    This is what protects ``resolve_strike_outcome``'s ``roll=`` contract:
    Chip Away draws its to-hit roll BEFORE its damage variance, per strike,
    so letting the resolver roll internally (or hoisting the variance) swaps
    the order the draws come off the shared RNG and every number below moves.
    """
    user = _make_user("Pick")
    target = _make_enemy("Dummy")
    user.combat_proximity = {target: 2}
    user.combat_list = [target]

    move = ChipAway(user)
    move.target = target
    _arm(user, move)

    with seeded(1234):
        entries = _run(_capture_for(user), lambda: move.execute(user))

    assert _outcomes(entries) == ["miss", "hit", "hit"], _outcomes(entries)
    struck = [e["message"] for e in entries if "Strike" in e.get("message", "")]
    assert struck == [
        "Strike 1 missed!",
        "Strike 2: 16 damage to Dummy!",
        "Strike 3: 16 damage to Dummy!",
    ], struck


# ── glance: which area moves can actually produce one ───────────────────────


@pytest.mark.parametrize(
    "move_cls, subtype",
    [
        (Sweep, "Polearm"),
        (HalberdSpin, "Polearm"),
        (Reap, "Scythe"),
        (ChipAway, "Pick"),
    ],
)
def test_area_moves_never_publish_a_glance(move_cls, subtype, seeded):
    """None of these four has a glancing-blow branch.

    Sweep/Halberd Spin/Reap deal flat ``max(1, power - protection)`` with no
    near-miss margin test at all, and Chip Away rolls variance but never
    inspects the hit margin — so ``glance`` is not in their vocabulary. This
    asserts the absence rather than inventing one for them: a glance is a
    deliberate ``Move.hit(damage, glance=True)`` decision, and adding it here
    would be a balance change dressed up as a feedback fix.
    """
    seen = set()
    # 60 seeds: enough that the hit/parry/miss branches all fire for every move
    # (the parrying third enemy and the protection ladder need a spread of
    # rolls), while the assertion is an absence, which sampling can only ever
    # support -- the docstring's argument from source is the real proof.
    # The ``seeded`` fixture restores the RNG state per iteration, and does so
    # even when an assertion mid-loop fails -- the bare getstate/setstate pair
    # this replaces leaked a pinned RNG into the next test on any failure.
    for seed in range(60):
        with seeded(seed):
            user = _make_user(subtype)
            enemies = [_make_enemy(f"E{i}", protection=i * 6) for i in range(3)]
            enemies[2].states = [states.Parrying(enemies[2])]
            user.combat_proximity = {e: 2 for e in enemies}
            user.combat_list = list(enemies)
            move = move_cls(user)
            move.target = enemies[0]
            _arm(user, move)
            entries = _run(_capture_for(user), lambda: move.execute(user))
            seen.update(o for o in _outcomes(entries) if o)

    assert seen, f"{move_cls.__name__} published no outcomes at all"
    assert "glance" not in seen, f"{move_cls.__name__} published a glance: {seen}"
    assert seen <= set(OUTCOMES), seen


def test_a_multi_enemy_sweep_animates_in_full_on_every_enemy_it_reaches(monkeypatch):
    """Every enemy an arc catches gets the arc, in full, against its own id.

    The adapter used to downgrade every resolution after the first to a short
    flash-only ``impact`` animation, because the client played a beat's
    animations strictly one at a time and four full sweeps read as four swings.
    The client now plays them concurrently and layers their SFX, so the
    downgrade only cost the later targets their animation.
    """
    import src.moves._polearm as polearm

    user = _make_user("Polearm")
    enemies = [_make_enemy(f"E{i}") for i in range(4)]
    user.combat_proximity = {e: 2 for e in enemies}
    user.combat_list = list(enemies)

    move = Sweep(user)
    _arm(user, move)
    _fixed_rolls(monkeypatch, polearm, [0, 0, 100, 0])

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert [i["type"] for i in _impacts(entries)] == ["sweep"] * 4, entries


def _adapter_for(user):
    """A bare adapter wired up with just what ``_capture_output`` touches."""
    from src.api.combat_adapter import ApiCombatAdapter, CombatOutputCapture

    adapter = ApiCombatAdapter.__new__(ApiCombatAdapter)
    adapter.player = user
    adapter.session_id = None
    adapter.current_beat_state_index = 0
    adapter.output_capture = CombatOutputCapture(player=user)
    adapter.output_capture.active_entity = user
    user.combat_log = []
    user.combat_beat = 1
    return adapter


def test_every_landing_survives_the_log_deduplicator(monkeypatch):
    """The impacts have to reach ``player.combat_log``, not just the capture.

    ``_add_log_entry`` drops an entry whose (message, round, acting entity) it
    has already seen — a guard against two same-named NPC moves colliding in one
    beat. Every follow-up impact of a swing shares all three with the first, so
    a carrier message of "<Move> animation" collapsed a four-enemy sweep back
    down to a single animation the moment it left the capture buffer. That is
    the failure mode this whole change exists to remove, one layer further down.
    """
    import src.moves._polearm as polearm

    user = _make_user("Polearm")
    enemies = [_make_enemy(f"E{i}") for i in range(4)]
    user.combat_proximity = {e: 2 for e in enemies}
    user.combat_list = list(enemies)

    move = Sweep(user)
    _arm(user, move)
    _fixed_rolls(monkeypatch, polearm, [0, 0, 100, 0])

    adapter = _adapter_for(user)
    with adapter._capture_output():
        move.execute(user)

    logged = [e["animation"] for e in user.combat_log if e.get("animation")]
    assert [a["outcome"] for a in logged] == ["hit", "hit", "miss", "hit"], logged
    assert len({a["target_id"] for a in logged}) == 4, logged


def test_whirl_attack_reports_a_whiffed_enemy_like_every_other_arc():
    """An arc move must account for every enemy it reaches, hit or miss.

    Sweep, Halberd Spin, Reap and Chip Away each narrate and publish for a
    target they whiffed. Whirl Attack's per-enemy branch had no ``else``: an
    enemy inside the spin that the roll missed produced no outcome and no log
    line at all, so the player saw the swing pass through an enemy in silence
    with no way to tell a miss from a target that was never in range.
    """
    import random as _rng
    from unittest.mock import patch

    import src.items as items
    import src.moves as moves
    import src.moves._base as move_base
    import src.npc as npc
    import src.positions as positions
    from src.narration import capture_narration
    from src.player import Player

    player = Player()
    weapon = items.Longsword()
    player.inventory.append(weapon)
    weapon.isequipped = True
    player.eq_weapon = weapon
    player.combat_exp.setdefault(weapon.subtype, 0)
    player.combat_position = positions.CombatPosition(10, 10, positions.Direction.N)

    enemies = []
    for i in range(3):
        enemy = npc.Slime()
        enemy.name = f"Slime{i + 1}"
        enemy.maxhp = enemy.hp = 500
        enemy.combat_position = positions.CombatPosition(
            10, 11 + i, positions.Direction.S
        )
        enemies.append(enemy)
    player.combat_list = list(enemies)
    player.combat_list_allies = [player]
    player.combat_proximity = {enemy: 1 for enemy in enemies}
    player.in_combat = True
    player.fatigue = player.maxfatigue

    published = []
    original = move_base.publish_outcome

    def record(entity, outcome, target=None):
        published.append((outcome, getattr(target, "name", None)))
        return original(entity, outcome, target)

    move = moves.WhirlAttack(player)
    move.evaluate()
    move.target = player
    # 100 is above every reachable hit chance, so every enemy is whiffed.
    with capture_narration(), patch.object(
        move_base, "publish_outcome", record
    ), patch.object(_rng, "randint", return_value=100), patch(
        "src.functions.check_parry", return_value=False
    ):
        move.execute(player)

    assert [outcome for outcome, _ in published] == ["miss", "miss", "miss"], (
        "Whirl Attack reached 3 enemies and reported "
        f"{len(published)} outcomes: {published}"
    )
    assert {name for _, name in published} == {"Slime1", "Slime2", "Slime3"}, published


# ── Blood of Martyrs (faith mastery, battlefield-wide detonation) ───────────


class _AbsorbState:
    """Stand-in for ``states.BloodOfMartyrsState`` — the only two attributes
    ``BloodOfMartyrs.execute`` reads off it."""

    def __init__(self, absorbed):
        self.name = "Blood of Martyrs"
        self._absorbing = True
        self.absorbed = absorbed


def _martyr_user(absorbed=50):
    user = _make_user("Sword")
    user.faith = 40
    user.strength = user.finesse = user.speed = 10
    user.endurance = user.charisma = user.intelligence = 10
    user.states = [_AbsorbState(absorbed)]
    return user


def test_blood_of_martyrs_publishes_one_outcome_per_enemy():
    """The detonation is one resolution per enemy, exactly like an arc swing.

    It damages every living enemy on the battlefield and narrates a line for
    each — but published nothing at all, so the whole map-wide blast fell
    through to the adapter's end-of-move fallback: one animation, no per-target
    impact, and no way for the client to flash the enemies that were actually
    hit.
    """
    from src.moves._mastery import BloodOfMartyrs

    user = _martyr_user()
    enemies = [_make_enemy(f"E{i}") for i in range(3)]
    user.combat_list = list(enemies)

    move = BloodOfMartyrs(user)
    _arm(user, move)

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert _outcomes(entries) == ["hit", "hit", "hit"], entries


def test_blood_of_martyrs_attributes_each_outcome_to_its_own_enemy():
    from src.api.serializers.combat import CombatantSerializer
    from src.moves._mastery import BloodOfMartyrs

    user = _martyr_user()
    enemies = [_make_enemy(f"E{i}") for i in range(3)]
    user.combat_list = list(enemies)

    move = BloodOfMartyrs(user)
    _arm(user, move)

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert [i["target_id"] for i in _impacts(entries)] == [
        CombatantSerializer.stream_id(enemy) for enemy in enemies
    ], entries


def test_blood_of_martyrs_publishes_absorb_when_the_blast_does_nothing():
    """A ``pure`` resistance of 0 collapses the blast to zero damage against
    that enemy. Zero damage is an ``absorb``, not a ``hit`` — publishing a hit
    would play the full flesh-impact cue for a blow the enemy shrugged off,
    the same distinction ``Move.hit()`` and Chip Away already draw.
    """
    from src.moves._mastery import BloodOfMartyrs

    user = _martyr_user()
    immune, struck = _make_enemy("Immune"), _make_enemy("Struck")
    immune.resistance = dict(RESISTANCE, pure=0.0)
    user.combat_list = [immune, struck]

    move = BloodOfMartyrs(user)
    _arm(user, move)

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert _outcomes(entries) == ["absorb", "hit"], entries


def test_blood_of_martyrs_skips_the_dead_without_publishing():
    """Only the living get a resolution — a corpse is not a target the client
    should flash."""
    from src.moves._mastery import BloodOfMartyrs

    user = _martyr_user()
    dead, alive = _make_enemy("Dead"), _make_enemy("Alive")
    dead.is_alive = lambda: False
    user.combat_list = [dead, alive]

    move = BloodOfMartyrs(user)
    _arm(user, move)

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert _outcomes(entries) == ["hit"], entries


def test_blood_of_martyrs_publishes_nothing_when_it_absorbed_nothing():
    """No absorbed damage means no detonation at all — and therefore no
    per-enemy resolutions to report."""
    from src.moves._mastery import BloodOfMartyrs

    user = _martyr_user(absorbed=0)
    user.combat_list = [_make_enemy("E0")]

    move = BloodOfMartyrs(user)
    _arm(user, move)

    entries = _run(_capture_for(user), lambda: move.execute(user))

    assert _outcomes(entries) == [], entries
