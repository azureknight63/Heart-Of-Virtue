"""Tests for Move.preview_hit_chance (src/moves/_base.py) and its wiring into
combat_adapter._get_available_targets.

=== What this guards ===

Before this feature, exactly one targeted move (ShootBow) exposed a per-target
hit chance to the player, via a bespoke `calculate_hit_chance` method gated on
`verbose_targeting` in combat_adapter.py. The other 33 targeted moves computed
their own hit_chance inline in execute() but never surfaced it. `preview_hit_chance`
is the single new estimate every targeted move now exposes; combat_adapter wires
it into every target card unconditionally (see `_get_available_targets`).

Per CLAUDE.md's "To-hit arithmetic" note, the `to_hit_chance` call sites are
NOT uniform (bases of 85/90/95/98/105, floors of 1/5/none, several situational
modifiers), so the base class default cannot be trusted for every move --
each override has to be checked against what that move's own execute() path
actually computes. This file does that with real engine objects (Player, NPC,
real Move subclasses, real weapons) rather than mocks: a mock that encodes the
same base/floor as the implementation cannot catch a drift between them, which
is exactly the failure mode CLAUDE.md documents for this arithmetic.

=== How the equality checks work ===

`_capture_real_hit_chance` runs `move.execute(user)` once and spies on the
shared `_apply_to_hit_modifiers` function -- every to-hit path in src/moves
(both the base class default and every per-move override) feeds its raw
hit_chance through that single call and uses the return value, unmodified,
against the roll. Spying on it (rather than reimplementing the formula in the
test) captures the literal number execute() used, so comparing it to
`preview_hit_chance()`'s return is a real equality check between the preview
and the real roll, not two independent computations that happen to agree.

Because `_apply_to_hit_modifiers` is imported separately into every moves
submodule (`from ._base import ... _apply_to_hit_modifiers`) and into `_base`
itself, the spy patches both the owning module's copy (for moves whose
override calls it directly) and `src.moves._base`'s copy (for moves that go
through `Move._standard_preview_hit_chance`, defined in `_base.py`), so
either code path is caught by the same recorder.
"""

import contextlib
from unittest.mock import patch

import pytest

from src.api.combat_adapter import ApiCombatAdapter
import src.moves._base as moves_base
import src.moves._dagger as moves_dagger
import src.moves._mastery as moves_mastery
import src.moves._movement as moves_movement
import src.moves._pick as moves_pick
import src.moves._polearm as moves_polearm
import src.moves._ranged as moves_ranged
import src.moves._scythe as moves_scythe
import src.moves._spear as moves_spear
import src.moves._sword as moves_sword
import src.moves._unarmed as moves_unarmed
import src.moves._utility as moves_utility
import src.states as states
from src.items import (
    Crossbow,
    Dagger,
    Fists,
    Longbow,
    Mace,
    Pickaxe,
    Pole,
    Scythe,
    Shortsword,
    Spear,
    WoodenArrow,
)
from src.moves import (
    AimedShot,
    ArmorPierce,
    Attack,
    Advance,
    Backstab,
    BroadheadBolt,
    BullCharge,
    ChipAway,
    DeathsHarvest,
    DisarmingSlash,
    ExploitWeakness,
    FeintAndPivot,
    FlankingManeuver,
    Impale,
    Jab,
    KeepAway,
    KillingPrecision,
    LightningAssault,
    Lunge,
    OverheadSmash,
    PinningBolt,
    PommelStrike,
    PowerStrike,
    Pulverize,
    QuickSwap,
    ReapersMark,
    Riposte,
    ShootBow,
    ShootCrossbow,
    Slash,
    Stupefy,
    TacticalPositioning,
    Thrust,
    VertigoSpin,
)
from src.npc import NPC
from src.player import Player
from src.positions import CombatPosition, Direction, turn_toward


def _make_player(weapon=None, **stat_overrides):
    player = Player()
    player.name = "Jean"
    player.in_combat = True
    player.known_moves = []
    player.combat_log = []
    player.last_move_summary = ""
    player.combat_beat = 1
    if weapon is not None:
        player.eq_weapon = weapon
    for stat, value in stat_overrides.items():
        setattr(player, stat, value)
    return player


def _make_enemy(**kwargs):
    defaults = dict(
        name="Target Dummy",
        description="A stationary training dummy.",
        damage=5,
        aggro=True,
        exp_award=1,
        maxhp=500,
    )
    defaults.update(kwargs)
    return NPC(**defaults)


def _link(player, enemy, distance):
    player.combat_list = [enemy]
    player.combat_list_allies = [player]
    player.combat_proximity = {enemy: distance}
    enemy.combat_proximity = {player: distance}


def _face_each_other(player, enemy, distance=5):
    """Give both combatants coordinate positions with the player already
    turned to face the enemy, so execute()'s own turn_toward() call (which
    runs before it computes hit_chance) is a no-op -- keeping the facing
    state identical between the preview call and the real execute() call
    for moves whose viable()/accuracy depends on combat_position.
    """
    player.combat_position = CombatPosition(x=0, y=0, facing=Direction.E)
    enemy.combat_position = CombatPosition(x=distance, y=0, facing=Direction.W)
    player.combat_position.facing = turn_toward(player.combat_position, enemy.combat_position)


def _capture_real_hit_chance(file_module, move, user):
    """Run move.execute(user) once, capturing the hit_chance value it
    actually used for its to-hit roll (see module docstring). Returns None
    if `_apply_to_hit_modifiers` was never called -- i.e. execute() took a
    no-roll or structurally-always-hits path.
    """
    real_fn = moves_base._apply_to_hit_modifiers
    captured = []

    def spy(*args, **kwargs):
        result = real_fn(*args, **kwargs)
        captured.append(result)
        return result

    patches = [patch.object(moves_base, "_apply_to_hit_modifiers", side_effect=spy)]
    if file_module is not moves_base and hasattr(file_module, "_apply_to_hit_modifiers"):
        patches.append(patch.object(file_module, "_apply_to_hit_modifiers", side_effect=spy))

    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        move.execute(user)

    return captured[-1] if captured else None


# ============================================================================
# Default-bucket moves (to_hit_chance(..., floor=5), no situational modifiers)
# One per weapon class, plus the hand-rolled Attack/PommelStrike/OverheadSmash
# paths that use standard_execute_attack, and the Mastery/Riposte call sites
# CLAUDE.md specifically flags as easy to get wrong.
# ============================================================================

class TestDefaultBucketMovesMatchExecute:
    @staticmethod
    def _run(file_module, move_cls, weapon, distance, **player_stats):
        player = _make_player(weapon=weapon, **player_stats)
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, distance)
        move = move_cls(player)
        move.target = enemy
        preview = move.preview_hit_chance(enemy)
        real = _capture_real_hit_chance(file_module, move, player)
        # Guard against a vacuous pass: if `distance` accidentally sat outside
        # the move's viable range, both preview and real collapse to None and
        # `preview == real` would pass without exercising any arithmetic at
        # all. Fail loudly instead so a bad fixture distance is obvious.
        assert preview is not None, (
            f"{move_cls.__name__}: preview_hit_chance returned None at "
            f"distance={distance} -- move likely not viable at this distance"
        )
        assert real is not None, (
            f"{move_cls.__name__}: execute() never called "
            f"_apply_to_hit_modifiers at distance={distance} -- move likely "
            f"not viable at this distance"
        )
        return preview, real

    def test_attack_matches(self):
        preview, real = self._run(moves_utility, Attack, Shortsword(), 3)
        assert preview == real

    def test_pommel_strike_matches(self):
        preview, real = self._run(moves_sword, PommelStrike, Shortsword(), 3)
        assert preview == real

    def test_backstab_matches_dagger(self):
        preview, real = self._run(moves_dagger, Backstab, Dagger(), 2)
        assert preview == real

    def test_slash_matches_dagger(self):
        preview, real = self._run(moves_dagger, Slash, Dagger(), 2)
        assert preview == real

    def test_lunge_matches_spear(self):
        # Distance 10, not 5: Lunge's execute() steps the user 3 ft toward the
        # target *before* it re-derives hit_chance, and viable() is re-checked
        # against that post-step distance. A starting distance near the low
        # end of Lunge's [3, 15] range (e.g. 5) can step itself out of range
        # and auto-miss regardless of what the pre-step preview showed -- a
        # real, pre-existing quirk (see this file's module docstring / the
        # task report), not something this test is meant to exercise. 10
        # steps down to 7, safely inside range both before and after.
        preview, real = self._run(moves_spear, Lunge, Spear(), 10)
        assert preview == real

    def test_keep_away_matches_spear(self):
        preview, real = self._run(moves_spear, KeepAway, Spear(), 5)
        assert preview == real

    def test_impale_matches_spear(self):
        preview, real = self._run(moves_spear, Impale, Spear(), 5)
        assert preview == real

    def test_armor_pierce_matches_pick(self):
        # ArmorPierce is defined in _spear.py (see CLAUDE.md's project
        # structure table) despite requiring a Pick weapon -- the spy must
        # target the module the move's execute() actually lives in.
        preview, real = self._run(moves_spear, ArmorPierce, Pickaxe(), 3)
        assert preview == real

    def test_chip_away_matches_pick(self):
        preview, real = self._run(moves_pick, ChipAway, Pickaxe(), 3)
        assert preview == real

    def test_exploit_weakness_matches_pick(self):
        preview, real = self._run(moves_pick, ExploitWeakness, Pickaxe(), 3)
        assert preview == real

    def test_stupefy_matches_pick(self):
        preview, real = self._run(moves_pick, Stupefy, Pickaxe(), 3)
        assert preview == real

    def test_deaths_harvest_matches_scythe(self):
        preview, real = self._run(moves_scythe, DeathsHarvest, Scythe(), 3)
        assert preview == real

    def test_overhead_smash_matches_polearm(self):
        preview, real = self._run(moves_polearm, OverheadSmash, Pole(), 4)
        assert preview == real

    def test_disarming_slash_matches_sword(self):
        preview, real = self._run(moves_sword, DisarmingSlash, Shortsword(), 3)
        assert preview == real

    def test_thrust_matches_sword(self):
        preview, real = self._run(moves_sword, Thrust, Shortsword(), 3)
        assert preview == real

    def test_riposte_matches_default_98_not_85(self):
        """CLAUDE.md specifically flags Riposte as a site that was once
        wrongly documented as base=85 -- pin it at the real default (98)."""
        player = _make_player(weapon=Shortsword())
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, 3)
        player.states = [states.Parrying(player)]
        move = Riposte(player)
        move.target = enemy
        preview = move.preview_hit_chance(enemy)
        real = _capture_real_hit_chance(moves_sword, move, player)
        assert preview is not None and real is not None
        assert preview == real
        # Cross-check against the literal default (base=98, floor=5) so a
        # regression to some other base doesn't silently pass via `real`
        # having drifted the same way `preview` did.
        expected = moves_base._apply_to_hit_modifiers(
            player, enemy, moves_base.to_hit_chance(player, enemy, floor=5)
        )
        assert preview == expected

    def test_pulverize_matches_mastery(self):
        preview, real = self._run(
            moves_mastery, Pulverize, Shortsword(), 3, strength=50, finesse=10,
            speed=10, endurance=10, charisma=10, intelligence=10, faith=10,
        )
        assert preview == real

    def test_lightning_assault_matches_mastery(self):
        preview, real = self._run(
            moves_mastery, LightningAssault, Shortsword(), 3, speed=50,
            strength=10, finesse=10, endurance=10, charisma=10, intelligence=10, faith=10,
        )
        assert preview == real


# ============================================================================
# Simple-base/floor overrides
# ============================================================================

class TestSimpleOverrideMoves:
    def test_power_strike_base85_floor1(self):
        player = _make_player(weapon=Mace())
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, 3)
        move = PowerStrike(player)
        move.target = enemy
        preview = move.preview_hit_chance(enemy)
        real = _capture_real_hit_chance(moves_unarmed, move, player)
        assert preview == real
        expected = moves_base._apply_to_hit_modifiers(
            player, enemy, moves_base.to_hit_chance(player, enemy, base=85, floor=1)
        )
        assert preview == expected

    def test_jab_floor1_default_base(self):
        player = _make_player(weapon=Fists())
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, 3)
        move = Jab(player)
        move.target = enemy
        preview = move.preview_hit_chance(enemy)
        real = _capture_real_hit_chance(moves_unarmed, move, player)
        assert preview == real
        expected = moves_base._apply_to_hit_modifiers(
            player, enemy, moves_base.to_hit_chance(player, enemy, floor=1)
        )
        assert preview == expected

    def test_vertigo_spin_base85_no_floor(self):
        player = _make_player(weapon=Shortsword())
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, 5)
        _face_each_other(player, enemy, distance=5)
        move = VertigoSpin(player)
        move.target = enemy
        preview = move.preview_hit_chance(enemy)
        real = _capture_real_hit_chance(moves_sword, move, player)
        assert preview is not None and real is not None
        assert preview == real

    def test_feint_and_pivot_base90_no_floor(self):
        player = _make_player(weapon=Dagger())
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, 5)
        _face_each_other(player, enemy, distance=5)
        move = FeintAndPivot(player)
        move.target = enemy
        preview = move.preview_hit_chance(enemy)
        real = _capture_real_hit_chance(moves_dagger, move, player)
        assert preview is not None and real is not None
        assert preview == real


# ============================================================================
# Always-hits move: no roll exists in execute() to capture, so this is
# verified structurally (never a miss branch) instead of numerically.
# ============================================================================

class TestKillingPrecisionAlwaysHits:
    def test_preview_is_100_when_viable(self):
        player = _make_player(weapon=Shortsword(), finesse=50, strength=10,
                               speed=10, endurance=10, charisma=10, intelligence=10, faith=10)
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, 3)
        move = KillingPrecision(player)
        move.target = enemy
        assert move.preview_hit_chance(enemy) == 100

    def test_preview_is_none_when_not_viable(self):
        player = _make_player(weapon=Shortsword())  # finesse not dominant
        player.in_combat = True
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, 3)
        move = KillingPrecision(player)
        move.target = enemy
        assert move.preview_hit_chance(enemy) is None

    def test_execute_never_misses(self):
        """execute() has no roll at all (see src/moves/_mastery.py) -- confirm
        the "always hits" semantics behind preview's 100 by running it many
        times and asserting the target is never left unscathed by a miss."""
        for _ in range(25):
            player = _make_player(
                weapon=Shortsword(), finesse=50, strength=10, speed=10,
                endurance=10, charisma=10, intelligence=10, faith=10,
            )
            enemy = _make_enemy(finesse=99, maxhp=100000)  # absurd evasion stat
            enemy.hp = enemy.maxhp
            _link(player, enemy, 3)
            move = KillingPrecision(player)
            move.target = enemy
            move.execute(player)
            assert enemy.hp < enemy.maxhp, "Killing Precision should never miss"


# ============================================================================
# Crossbow-family moves: floor/base plus close-range halving and/or distance
# accuracy decay, factored through _apply_crossbow_range_decay.
# ============================================================================

class TestCrossbowFamilyMoves:
    @staticmethod
    def _run(move_cls, distance=20):
        player = _make_player(weapon=Crossbow())
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, distance)
        move = move_cls(player)
        move.target = enemy
        preview = move.preview_hit_chance(enemy)
        real = _capture_real_hit_chance(moves_ranged, move, player)
        return preview, real

    def test_shoot_crossbow_matches_with_decay(self):
        preview, real = self._run(ShootCrossbow, distance=25)  # > range_base=15
        assert preview is not None and real is not None
        assert preview == real

    def test_broadhead_bolt_matches_no_close_range_penalty(self):
        """BroadheadBolt's execute() -- unlike ShootCrossbow/PinningBolt --
        never calls _crossbow_close_range_penalty. Put a second hostile
        inside the crossbow's minimum range (6 ft) and confirm the preview
        does NOT get halved, matching that asymmetry in execute()."""
        player = _make_player(weapon=Crossbow())
        far_enemy = _make_enemy(name="Far Target", finesse=8)
        near_enemy = _make_enemy(name="Close Target", finesse=8)
        player.combat_list = [far_enemy, near_enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {far_enemy: 20, near_enemy: 2}
        far_enemy.combat_proximity = {player: 20}
        near_enemy.combat_proximity = {player: 2}

        move = BroadheadBolt(player)
        move.target = far_enemy
        preview = move.preview_hit_chance(far_enemy)
        real = _capture_real_hit_chance(moves_ranged, move, player)
        assert preview is not None and real is not None
        assert preview == real

        # Sanity: an otherwise-identical ShootCrossbow WOULD be halved here.
        move2 = ShootCrossbow(player)
        move2.target = far_enemy
        halved_preview = move2.preview_hit_chance(far_enemy)
        assert halved_preview is not None
        assert halved_preview < preview, (
            "expected the close-range penalty to make ShootCrossbow's preview "
            "lower than BroadheadBolt's under the same near-enemy setup"
        )

    def test_aimed_shot_matches_with_flat_bonus_and_clamp(self):
        preview, real = self._run(AimedShot, distance=25)
        assert preview is not None and real is not None
        assert preview == real

    def test_pinning_bolt_matches_with_decay(self):
        preview, real = self._run(PinningBolt, distance=25)
        assert preview is not None and real is not None
        assert preview == real


# ============================================================================
# ShootBow: the pre-existing reference implementation. preview_hit_chance
# must delegate to calculate_hit_chance exactly, never recompute it.
# ============================================================================

class TestShootBowDelegatesToCalculateHitChance:
    def test_preview_equals_calculate_hit_chance(self):
        player = _make_player(weapon=Longbow())
        player.inventory = [WoodenArrow()]
        player.inventory[0].count = 5
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, 15)
        move = ShootBow(player)
        move.target = enemy
        assert move.preview_hit_chance(enemy) == move.calculate_hit_chance(enemy)


# ============================================================================
# No-roll moves: pure positioning/status, no damage or to-hit roll at all.
# ============================================================================

class TestNoRollMovesReturnNone:
    @pytest.mark.parametrize(
        "file_module,move_cls,weapon",
        [
            (moves_movement, Advance, Shortsword()),
            (moves_movement, BullCharge, Shortsword()),
            (moves_movement, FlankingManeuver, Shortsword()),
            (moves_movement, TacticalPositioning, Shortsword()),
            (moves_scythe, ReapersMark, Scythe()),
        ],
    )
    def test_preview_is_none_and_no_modifier_call(self, file_module, move_cls, weapon):
        player = _make_player(weapon=weapon)
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, 5)
        _face_each_other(player, enemy, distance=5)
        move = move_cls(player)
        move.target = enemy
        assert move.preview_hit_chance(enemy) is None
        # Confirm the "no roll" story: the shared to-hit modifier function is
        # never invoked by execute() for these moves.
        real = _capture_real_hit_chance(file_module, move, player)
        assert real is None

    def test_quick_swap_returns_none(self):
        player = _make_player(weapon=Shortsword())
        ally = _make_enemy(name="Ally", finesse=8, friend=True)
        player.combat_list = []
        player.combat_list_allies = [player, ally]
        player.combat_proximity = {ally: 2}
        ally.combat_proximity = {player: 2}
        move = QuickSwap(player)
        move.target = ally
        assert move.preview_hit_chance(ally) is None


# ============================================================================
# combat_adapter wiring: verify _get_available_targets now populates
# hit_chance for a formerly-uncovered move (not just ShootBow).
# ============================================================================

class TestAdapterWiresHitChanceForNonShootBowMoves:
    def test_power_strike_target_card_has_hit_chance(self):
        player = _make_player(weapon=Mace())
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, 3)

        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player)
            move = PowerStrike(player)
            targets = adapter._get_available_targets(move)

        assert targets, "expected the in-range dummy to produce a target entry"
        assert "hit_chance" in targets[0], (
            "PowerStrike is one of the 33 moves that had no per-target hit "
            "chance before this change -- the adapter must now populate it "
            "via Move.preview_hit_chance, not just verbose_targeting moves"
        )
        assert targets[0]["hit_chance"] == move.preview_hit_chance(enemy)

    def test_no_roll_move_target_card_omits_hit_chance(self):
        player = _make_player(weapon=Shortsword())
        enemy = _make_enemy(finesse=8)
        _link(player, enemy, 5)

        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player)
            move = Advance(player)
            targets = adapter._get_available_targets(move)

        assert targets
        assert "hit_chance" not in targets[0], (
            "Advance deals no damage and rolls no to-hit -- the adapter must "
            "not fabricate a number for it"
        )
