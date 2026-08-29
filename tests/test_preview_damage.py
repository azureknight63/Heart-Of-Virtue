"""Tests for the pre-commitment damage preview: ``damage_bounds``,
``Move.preview_damage`` and ``Move.preview_affected`` (src/moves/_base.py),
plus their wiring into the combat API payload.

=== What this guards ===

The player commits to a move with no idea what it will do. ``preview_damage``
is the number the client shows *before* the commit, so it is a second
statement of the engine's damage expression -- exactly the shape of thing this
codebase has repeatedly let drift (see CLAUDE.md's wire-field-drift note and
the to-hit arithmetic note). A preview that drifts from reality is worse than
no preview, because the player makes decisions on it.

``TestPreviewMatchesRealExecute`` below is the link between prediction and
reality. For a representative move from each structural shape in the moves
package it pins ``random.uniform`` to the two ends of the engine's +/-20%
damage band, runs the *real* ``execute()``, and asserts the HP actually
removed equals the ``min``/``max`` the preview advertised. Nothing in that
test reimplements the damage formula: it reads the preview and it reads the
target's HP, so the two cannot agree by both being wrong in the same way --
the failure mode CLAUDE.md documents for mock-on-mock fixtures.

The four shapes, and why each needs its own case:

* ``standard_execute_attack`` caller (PommelStrike) -- the shared pipeline in
  ``_base.py``.
* hand-rolled single-target ``execute()`` (Slash) -- copies the expression
  inline; the copy is what can drift.
* area move (Whirl Attack, Reap) -- no single ``self.target``; damage resolves
  against a set. Whirl Attack runs the canonical expression per enemy; Reap
  runs a *different*, flat one (no resistance, no heat, no variance), which is
  precisely why one area case is not enough.
* ranged (Shoot Crossbow) -- power arrives from the weapon/ammo rather than
  ``standard_evaluate_attack``.
"""

import ast
import contextlib
import copy
import importlib
import inspect
import pathlib
import textwrap
from unittest.mock import patch

import pytest

import src.moves as _moves_pkg
import src.moves._base as moves_base
from src.items import (
    Crossbow,
    Dagger,
    Longbow,
    Pole,
    Scythe,
    Shortsword,
    WoodenArrow,
)
from src.moves import (
    Backstab,
    HalberdSpin,
    PommelStrike,
    Reap,
    ShootBow,
    ShootCrossbow,
    Slash,
    Sweep,
    WhirlAttack,
)
from src.moves._base import damage_bounds
from src.npc import NPC
from src.player import Player
from src.positions import CombatPosition, Direction, turn_toward


# ---------------------------------------------------------------------------
# Fixtures (real engine objects only -- no mocks; see module docstring)
# ---------------------------------------------------------------------------


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
        maxhp=5000,
    )
    defaults.update(kwargs)
    enemy = NPC(**defaults)
    enemy.hp = enemy.maxhp
    return enemy


def _link(player, enemies, distance):
    if not isinstance(enemies, (list, tuple)):
        enemies = [enemies]
    player.combat_list = list(enemies)
    player.combat_list_allies = [player]
    player.combat_proximity = {e: distance for e in enemies}
    for e in enemies:
        e.combat_proximity = {player: distance}
        e.combat_list = [player]


def _place(player, enemy, distance=3):
    """Give both combatants coordinates, player already facing the enemy.

    ``execute()`` turns the attacker toward the target before scoring damage;
    pre-facing keeps the preview and the real run reading the same geometry.
    """
    player.combat_position = CombatPosition(x=0, y=0, facing=Direction.E)
    enemy.combat_position = CombatPosition(x=distance, y=0, facing=Direction.W)
    player.combat_position.facing = turn_toward(
        player.combat_position, enemy.combat_position
    )


@contextlib.contextmanager
def _pinned_rng(variance):
    """Force a landing, non-glancing hit with the damage roll pinned.

    ``random.randint`` -> 0 makes every ``roll`` a 0, so ``hit_chance >= roll``
    always holds; the fixtures below all produce a hit chance well above 10, so
    ``hit_chance - roll < 10`` (the glancing window) never fires. Parry is
    stubbed off because a parry short-circuits the damage entirely.
    """
    with patch("random.uniform", return_value=variance), patch(
        "random.randint", return_value=0
    ), patch("src.functions.check_parry", return_value=False), patch(
        "random.random", return_value=1.0
    ):
        yield


def _damage_dealt(move, player, enemy, variance):
    before = enemy.hp
    with _pinned_rng(variance):
        move.execute(player)
    return before - enemy.hp


# ---------------------------------------------------------------------------
# damage_bounds -- the one place the damage expression lives
# ---------------------------------------------------------------------------


class TestDamageBounds:
    def test_returns_the_variance_band_around_the_core_expression(self):
        player = _make_player(Shortsword(), heat=1.0)
        enemy = _make_enemy()
        enemy.protection = 10
        enemy.resistance["slashing"] = 1.0
        low, high = damage_bounds(player, enemy, 100, "slashing")
        # (100 * 1.0 - 10) * 1.0 -> 90; band is 72 .. 108
        assert (low, high) == (72, 108)

    def test_applies_resistance_protection_and_heat(self):
        player = _make_player(Shortsword(), heat=2.0)
        enemy = _make_enemy()
        enemy.protection = 5
        enemy.resistance["piercing"] = 0.5
        low, high = damage_bounds(player, enemy, 100, "piercing")
        # (100 * 0.5 - 5) * 2.0 -> 90
        assert (low, high) == (72, 108)

    def test_explicit_heat_overrides_the_attackers_heat(self):
        player = _make_player(Shortsword(), heat=1.0)
        enemy = _make_enemy()
        enemy.protection = 0
        enemy.resistance["slashing"] = 1.0
        assert damage_bounds(player, enemy, 100, "slashing", heat=2.0) == (160, 240)

    def test_fully_absorbed_damage_floors_at_zero_not_negative(self):
        player = _make_player(Shortsword(), heat=1.0)
        enemy = _make_enemy()
        enemy.protection = 500
        enemy.resistance["slashing"] = 1.0
        assert damage_bounds(player, enemy, 10, "slashing") == (0, 0)

    def test_facing_curve_is_included(self):
        """A rear attack must preview higher than a frontal one."""
        player = _make_player(Shortsword(), heat=1.0)
        enemy = _make_enemy()
        enemy.protection = 0
        enemy.resistance["slashing"] = 1.0
        player.combat_position = CombatPosition(x=0, y=0, facing=Direction.E)
        enemy.combat_position = CombatPosition(x=3, y=0, facing=Direction.E)  # back
        rear = damage_bounds(player, enemy, 100, "slashing")
        enemy.combat_position.facing = Direction.W  # head on
        front = damage_bounds(player, enemy, 100, "slashing")
        assert rear[0] > front[0] and rear[1] > front[1]


# ---------------------------------------------------------------------------
# Move.preview_damage -- shape, None cases, lethality
# ---------------------------------------------------------------------------


class TestPreviewDamageShape:
    def _armed(self, distance=3):
        player = _make_player(Shortsword())
        enemy = _make_enemy()
        _link(player, enemy, distance)
        _place(player, enemy, distance)
        move = PommelStrike(player)
        move.target = enemy
        return player, enemy, move

    def test_returns_min_max_lethal(self):
        _, enemy, move = self._armed()
        preview = move.preview_damage(enemy)
        assert set(preview) == {"min", "max", "lethal"}
        assert isinstance(preview["min"], int)
        assert isinstance(preview["max"], int)
        assert isinstance(preview["lethal"], bool)
        assert preview["min"] <= preview["max"]

    def test_lethal_true_when_max_exactly_equals_hp(self):
        _, enemy, move = self._armed()
        enemy.hp = move.preview_damage(enemy)["max"]
        assert move.preview_damage(enemy)["lethal"] is True

    def test_lethal_false_one_hp_above_max(self):
        _, enemy, move = self._armed()
        enemy.hp = move.preview_damage(enemy)["max"] + 1
        assert move.preview_damage(enemy)["lethal"] is False

    def test_out_of_range_target_previews_nothing(self):
        player, enemy, move = self._armed(distance=3)
        _link(player, enemy, 400)
        assert move.preview_damage(enemy) is None

    def test_out_of_reach_target_previews_nothing_while_another_is_in_reach(self):
        """``viable()`` for most attacks asks only whether *some* enemy is in
        range, so it stays True while a second enemy stands well outside the
        move's reach. Without a per-target reach check the preview happily
        prices a swing that could not possibly land."""
        player = _make_player(Shortsword())
        near = _make_enemy(name="Near")
        far = _make_enemy(name="Far")
        _link(player, [near, far], 3)
        player.combat_proximity[far] = 40
        _place(player, near, 3)
        far.combat_position = CombatPosition(x=40, y=0, facing=Direction.W)
        move = PommelStrike(player)
        move.target = near
        assert move.preview_damage(near) is not None
        assert move.preview_damage(far) is None

    def test_dead_target_previews_nothing(self):
        _, enemy, move = self._armed()
        enemy.hp = 0
        assert move.preview_damage(enemy) is None

    def test_no_resolvable_target_previews_nothing(self):
        _, _, move = self._armed()
        move.target = None
        assert move.preview_damage() is None

    def test_untargeted_non_damaging_move_previews_nothing(self):
        from src.moves import Rest

        player = _make_player(Shortsword())
        enemy = _make_enemy()
        _link(player, enemy, 3)
        assert Rest(player).preview_damage() is None

    def test_is_side_effect_free(self):
        """Calling the preview must not mutate the move or either combatant,
        and ``evaluate()`` must remain idempotent afterwards."""
        player, enemy, move = self._armed()
        move.evaluate()
        move_before = copy.deepcopy(
            {k: v for k, v in move.__dict__.items() if k not in ("user", "target")}
        )
        player_before = (player.hp, player.fatigue, player.heat, player.strength)
        enemy_before = (enemy.hp, enemy.protection, dict(enemy.resistance))

        move.preview_damage(enemy)

        after = {k: v for k, v in move.__dict__.items() if k not in ("user", "target")}
        assert after == move_before
        assert (player.hp, player.fatigue, player.heat, player.strength) == player_before
        assert (enemy.hp, enemy.protection, dict(enemy.resistance)) == enemy_before

        move.evaluate()
        again = {k: v for k, v in move.__dict__.items() if k not in ("user", "target")}
        assert again == move_before


# ---------------------------------------------------------------------------
# Move.preview_affected -- who the move resolves against
# ---------------------------------------------------------------------------


class TestPreviewAffected:
    def test_single_target_move_reports_its_target(self):
        player = _make_player(Shortsword())
        enemy = _make_enemy()
        _link(player, enemy, 3)
        _place(player, enemy, 3)
        move = PommelStrike(player)
        move.target = enemy
        assert move.preview_affected() == [enemy]

    def test_untargeted_non_area_move_reports_nobody(self):
        from src.moves import Rest

        player = _make_player(Shortsword())
        assert Rest(player).preview_affected() == []

    def test_whirl_attack_reports_every_hostile_in_the_circle(self):
        player = _make_player(Shortsword())
        near = _make_enemy(name="Near")
        far = _make_enemy(name="Far")
        _link(player, [near, far], 3)
        player.combat_proximity[far] = 40
        player.combat_position = CombatPosition(x=0, y=0, facing=Direction.E)
        near.combat_position = CombatPosition(x=3, y=0, facing=Direction.W)
        far.combat_position = CombatPosition(x=40, y=0, facing=Direction.W)
        move = WhirlAttack(player)
        assert move.preview_affected() == [near]

    def test_reap_excludes_enemies_outside_the_frontal_arc(self):
        player = _make_player(Scythe())
        ahead = _make_enemy(name="Ahead")
        behind = _make_enemy(name="Behind")
        _link(player, [ahead, behind], 3)
        player.combat_position = CombatPosition(x=10, y=0, facing=Direction.E)
        ahead.combat_position = CombatPosition(x=13, y=0, facing=Direction.W)
        behind.combat_position = CombatPosition(x=7, y=0, facing=Direction.E)
        move = Reap(player)
        assert move.preview_affected() == [ahead]

    def test_area_move_never_reports_an_ally(self):
        """``combat_list`` is the hostile side; an ally sitting in the arc must
        not appear (the friendly-fire bug the arc loops were fixed for)."""
        player = _make_player(Pole())
        enemy = _make_enemy(name="Enemy")
        ally = _make_enemy(name="Gorran")
        ally.friend = True
        _link(player, enemy, 3)
        player.combat_proximity[ally] = 3
        player.combat_list_allies = [player, ally]
        player.combat_position = CombatPosition(x=0, y=0, facing=Direction.E)
        enemy.combat_position = CombatPosition(x=3, y=0, facing=Direction.W)
        ally.combat_position = CombatPosition(x=2, y=0, facing=Direction.E)
        move = Sweep(player)
        assert move.preview_affected() == [enemy]

    def test_area_move_previews_damage_per_affected_combatant(self):
        player = _make_player(Pole())
        a = _make_enemy(name="A")
        b = _make_enemy(name="B")
        _link(player, [a, b], 3)
        player.combat_position = CombatPosition(x=0, y=0, facing=Direction.E)
        a.combat_position = CombatPosition(x=3, y=0, facing=Direction.W)
        b.combat_position = CombatPosition(x=4, y=1, facing=Direction.W)
        move = HalberdSpin(player)
        affected = move.preview_affected()
        assert set(affected) == {a, b}
        for enemy in affected:
            preview = move.preview_damage(enemy)
            assert preview is not None and preview["max"] > 0


# ---------------------------------------------------------------------------
# THE CONTRACT: preview vs. what execute() really does
# ---------------------------------------------------------------------------


class TestPreviewMatchesRealExecute:
    """Pin the RNG to both ends of the band, run the real ``execute()``, and
    assert the HP actually removed is exactly what the preview promised."""

    def _assert_bounds_hold(self, build, variance, key):
        player, enemy, move = build()
        preview = move.preview_damage(enemy)
        assert preview is not None, "preview_damage returned None for a live attack"
        dealt = _damage_dealt(move, player, enemy, variance)
        assert dealt == preview[key], (
            f"{type(move).__name__}: preview {key}={preview[key]} but execute() "
            f"dealt {dealt} at uniform={variance}"
        )
        assert preview["min"] <= dealt <= preview["max"]

    # -- shape 1: standard_execute_attack caller -----------------------------

    @staticmethod
    def _pommel_strike():
        player = _make_player(Shortsword())
        enemy = _make_enemy()
        _link(player, enemy, 3)
        _place(player, enemy, 3)
        move = PommelStrike(player)
        move.target = enemy
        return player, enemy, move

    @pytest.mark.parametrize("variance,key", [(0.8, "min"), (1.2, "max")])
    def test_standard_pipeline(self, variance, key):
        self._assert_bounds_hold(self._pommel_strike, variance, key)

    # -- shape 2: hand-rolled single-target execute --------------------------

    @staticmethod
    def _slash():
        player = _make_player(Dagger())
        enemy = _make_enemy()
        _link(player, enemy, 2)
        _place(player, enemy, 2)
        move = Slash(player)
        move.target = enemy
        return player, enemy, move

    @pytest.mark.parametrize("variance,key", [(0.8, "min"), (1.2, "max")])
    def test_hand_rolled_single_target(self, variance, key):
        self._assert_bounds_hold(self._slash, variance, key)

    # -- shape 3a: area move on the canonical expression ---------------------

    @staticmethod
    def _whirl():
        player = _make_player(Shortsword())
        enemy = _make_enemy()
        _link(player, enemy, 3)
        _place(player, enemy, 3)
        move = WhirlAttack(player)
        return player, enemy, move

    @pytest.mark.parametrize("variance,key", [(0.8, "min"), (1.2, "max")])
    def test_area_move_canonical(self, variance, key):
        self._assert_bounds_hold(self._whirl, variance, key)

    # -- shape 3b: area move on the flat arc expression ----------------------

    @staticmethod
    def _reap():
        player = _make_player(Scythe())
        enemy = _make_enemy()
        _link(player, enemy, 3)
        _place(player, enemy, 3)
        move = Reap(player)
        return player, enemy, move

    @pytest.mark.parametrize("variance,key", [(0.8, "min"), (1.2, "max")])
    def test_area_move_flat_arc(self, variance, key):
        """Reap's execute() has no variance roll at all: min and max must both
        equal the single damage it deals, or the preview is advertising a
        spread the engine cannot produce."""
        self._assert_bounds_hold(self._reap, variance, key)

    # -- shape 4: ranged -----------------------------------------------------

    @staticmethod
    def _crossbow():
        player = _make_player(Crossbow())
        enemy = _make_enemy()
        _link(player, enemy, 12)
        _place(player, enemy, 12)
        move = ShootCrossbow(player)
        move.target = enemy
        move.evaluate()
        return player, enemy, move

    @pytest.mark.parametrize("variance,key", [(0.8, "min"), (1.2, "max")])
    def test_ranged(self, variance, key):
        self._assert_bounds_hold(self._crossbow, variance, key)

    # -- shim: Backstab scores the facing curve at double steepness ----------

    @staticmethod
    def _backstab():
        player = _make_player(Dagger())
        enemy = _make_enemy()
        _link(player, enemy, 2)
        # Attack the enemy's back, where the steepened curve actually differs
        # from the baseline one; head-on the two shims are indistinguishable.
        player.combat_position = CombatPosition(x=0, y=0, facing=Direction.E)
        enemy.combat_position = CombatPosition(x=2, y=0, facing=Direction.E)
        move = Backstab(player)
        move.target = enemy
        return player, enemy, move

    @pytest.mark.parametrize("variance,key", [(0.8, "min"), (1.2, "max")])
    def test_steepened_facing_curve(self, variance, key):
        self._assert_bounds_hold(self._backstab, variance, key)

    # -- shim: Shoot Bow adds a finesse term inside execute() ----------------

    @staticmethod
    def _shoot_bow():
        player = _make_player(Longbow())
        arrow = WoodenArrow()
        arrow.count = 5
        player.inventory = [arrow]
        player.combat_exp.setdefault("Bow", 0)
        enemy = _make_enemy()
        _link(player, enemy, 15)
        _place(player, enemy, 15)
        move = ShootBow(player)
        move.target = enemy
        move.evaluate()
        return player, enemy, move

    @pytest.mark.parametrize("variance,key", [(0.8, "min"), (1.2, "max")])
    def test_ranged_with_in_execute_power_term(self, variance, key):
        self._assert_bounds_hold(self._shoot_bow, variance, key)


#: Every submodule of ``src.moves``, globbed rather than listed. Same rule as
#: ``tests/test_facing_damage_hand_rolled_attacks.py`` and for the same reason:
#: this guard replaces a hand-maintained table of the moves whose damage
#: diverges, so it must not itself become one. A new weapon module is covered
#: the day it lands, with nobody having to remember this file exists.
MOVE_MODULES = tuple(
    f"src.moves.{path.stem}"
    for path in sorted(pathlib.Path(_moves_pkg.__file__).parent.glob("*.py"))
    if path.stem != "__init__"
)

#: NPC moves are excluded, structurally rather than by name. The preview is
#: computed only for ``self.player.known_moves`` (see
#: ``ApiCombatAdapter._get_available_targets`` and ``_build_target_entry``);
#: nothing ever calls ``preview_damage`` on a move an NPC is running, so a
#: divergence there cannot mislead a player mid-commitment. If NPC intent ever
#: grows a damage preview, delete this line — that is the whole change.
NPC_MOVE_MODULE = "src.moves._npc"

#: How an ``execute()`` is recognised as reducing somebody's HP. Same spellings
#: as the facing-curve guard, and for the same reason: the package genuinely
#: uses several, and a signal list that is too narrow fails silently in the
#: safe-looking direction.
_DAMAGE_SIGNALS = ("self.hit(", "hp -=", "hp = max(", ".hp = max(")

#: Damage paths that diverge but are knowingly left on the default preview,
#: with the reason. Not a shim: nothing here changes what any move does. An
#: entry is a debt to be paid by *fixing the move*, and the test below fails if
#: one stops naming a real divergence.
_KNOWN_GAPS = {
    "Jab": (
        "Known mispricing, not a decision. Jab's execute() deals "
        "`power - protection` with no resistance, no heat scaling and no "
        "variance roll, so the default preview overstates it exactly as the "
        "shim table's absence always did. Left alone during the shim migration "
        "because correcting it moves numbers the player sees, which is a "
        "balance-visible change and not a refactor. Fix it with a "
        "preview_damage override on Jab and delete this entry."
    ),
}


def _defining_class(cls, method_name):
    """The class in ``cls``'s MRO that actually supplies ``method_name``."""
    for klass in cls.__mro__:
        if method_name in vars(klass):
            return klass
    return None


def _castable_move_classes():
    """Every castable ``Move`` subclass defined in a non-NPC `src.moves` module."""
    found = []
    for module_name in MOVE_MODULES:
        if module_name == NPC_MOVE_MODULE:
            continue
        module = importlib.import_module(module_name)
        for name, obj in vars(module).items():
            if not inspect.isclass(obj) or not issubclass(obj, moves_base.Move):
                continue
            if obj.__module__ != module_name:
                continue  # re-export, not a definition
            if issubclass(obj, moves_base.PassiveMove):
                continue  # never castable, never rolls damage
            found.append((module_name, name, obj))
    return found


def _divergences(source):
    """Why this ``execute()`` departs from the canonical damage path, if it does.

    The canonical path is the expression ``damage_bounds`` states: power scaled
    by the facing curve at steepness 1.0, times resistance, less protection,
    times heat, times ``random.uniform(0.8, 1.2)``, on ``self.power`` against
    ``self.target``. Each signal below is one way an ``execute()`` stops
    matching it -- and each is a way the preview silently mispriced a move
    before that move grew an override.
    """
    reasons = []
    if "_hostiles_in_proximity()" in source:
        reasons.append("damages a set of enemies rather than self.target")
    if "standard_execute_attack(" not in source and "random.uniform(" not in source:
        reasons.append("scores damage outside the canonical variance expression")
    for node in ast.walk(ast.parse(textwrap.dedent(source))):
        if isinstance(node, ast.Call):
            named = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if named == "apply_facing_damage" and (
                len(node.args) > 3
                or any(kw.arg == "steepness" for kw in node.keywords)
            ):
                reasons.append("scores the facing curve at a non-default steepness")
        targets = []
        if isinstance(node, ast.AugAssign):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = node.targets
        for target in targets:
            if isinstance(target, ast.Attribute) and target.attr == "power":
                reasons.append("rewrites self.power before scoring damage")
    return sorted(set(reasons))


def _divergent_damage_paths():
    """``(module, name, cls, reasons)`` for every castable move whose
    ``execute()`` deals damage by something other than the canonical line."""
    paths = []
    for module_name, name, cls in _castable_move_classes():
        defining = _defining_class(cls, "execute")
        if defining is None or defining is moves_base.Move:
            continue  # inert base execute -- narration only
        source = inspect.getsource(vars(defining)["execute"])
        if not any(signal in source for signal in _DAMAGE_SIGNALS):
            continue
        reasons = _divergences(source)
        if reasons:
            paths.append((module_name, name, cls, reasons))
    return paths


def _previewable(cls):
    """Can the preview ever produce a number for this move?

    Only if something resolves a target for it: it is targeted (the adapter
    prices each candidate the player could point it at), or it overrides
    ``preview_affected`` (an area swing, whose affected set the adapter prices
    one by one). An untargeted move that does neither resolves ``self.target``
    -- itself -- so the default returns ``None`` and there is no number to be
    wrong. Blood of Martyrs is the one such move today; the test below pins
    that premise so this is not a silent assumption.
    """
    init = _defining_class(cls, "__init__")
    if init is not None and "targeted=True" in inspect.getsource(vars(init)["__init__"]):
        return True
    return _defining_class(cls, "preview_affected") is not moves_base.Move


def _is_area_move(cls, reasons):
    """An area swing: it damages a set, so ``self.target`` (the user, for every
    one of them) cannot describe who it hits."""
    return any("set of enemies" in reason for reason in reasons)


class TestDivergentMovesOwnTheirPreview:
    """The shim table is gone; this is what replaces it.

    ``_PREVIEW_SHIMS`` was a second description of six moves' behaviour, kept
    in a file none of their owners had reason to open, keyed by class name. It
    is the structural pattern behind most of this codebase's recent bugs (see
    CLAUDE.md's wire-field-drift and to-hit notes), and the guard that used to
    sit here only checked that its keys named real classes -- which says
    nothing at all once the table is empty.

    So: assert the table is gone, and assert the property that made it
    unnecessary -- a move whose ``execute()`` diverges from the canonical
    damage line carries its own ``preview_damage``, beside the ``execute()``
    it mirrors. The next divergent move then gets an override rather than a
    new lookup table.
    """

    def test_the_shim_table_and_its_plumbing_are_gone(self):
        assert not getattr(moves_base, "_PREVIEW_SHIMS", None), (
            "_PREVIEW_SHIMS is back. A per-move divergence belongs on the move "
            "as a preview_damage/preview_affected override, not in a class-name "
            "lookup table in _base.py."
        )
        assert not hasattr(moves_base, "preview_shim")

    def test_the_enumeration_actually_finds_the_divergences(self):
        """A guard that silently matches nothing is worse than no guard.

        These are the six the shim table described plus the one gap it never
        covered; if the enumeration stops seeing them it has broken, not the
        package.
        """
        found = {name for _, name, _, _ in _divergent_damage_paths()}
        for expected in (
            "Backstab",
            "ShootBow",
            "WhirlAttack",
            "Reap",
            "Sweep",
            "HalberdSpin",
            "Jab",
        ):
            assert expected in found, f"{expected} vanished from the enumeration"

    def test_every_divergent_move_declares_its_own_preview_damage(self):
        missing = []
        for module_name, name, cls, reasons in _divergent_damage_paths():
            if name in _KNOWN_GAPS or not _previewable(cls):
                continue
            if _defining_class(cls, "preview_damage") is moves_base.Move:
                missing.append(f"{module_name}.{name}: {'; '.join(reasons)}")
        assert not missing, (
            "these moves' execute() diverges from the canonical damage line "
            "while their preview still reports it -- give each one a "
            "preview_damage override beside its execute():\n  "
            + "\n  ".join(missing)
        )

    def test_every_area_move_declares_its_own_preview_affected(self):
        """An area swing that does not override ``preview_affected`` previews
        *nobody*: it is untargeted with ``self.target`` set to the user, so the
        default reports an empty list and the client has nothing to draw."""
        missing = []
        for module_name, name, cls, reasons in _divergent_damage_paths():
            if not _is_area_move(cls, reasons):
                continue
            if _defining_class(cls, "preview_affected") is moves_base.Move:
                missing.append(f"{module_name}.{name}")
        assert not missing, (
            "these area moves damage a set of enemies but preview nobody:\n  "
            + "\n  ".join(missing)
        )

    def test_an_untargeted_move_with_no_affected_set_needs_no_override(self):
        """Why the guard above does not demand one from Blood of Martyrs.

        It is untargeted and overrides neither ``preview_affected`` nor
        ``preview_damage``, so the default resolves ``self.target`` -- the user
        -- and returns ``None``. There is no number to be wrong. This pins that
        premise rather than leaving it as a silent assumption.
        """
        from src.moves import BloodOfMartyrs

        player = _make_player(Shortsword())
        move = BloodOfMartyrs(player)
        assert move.preview_affected() == []
        assert move.preview_damage() is None

    @pytest.mark.parametrize("name", sorted(_KNOWN_GAPS))
    def test_each_known_gap_still_describes_a_real_divergence(self, name):
        """Gaps rot into lies. If the move stops diverging (or grows the
        override), the entry must go rather than sit there implying a debt that
        no longer exists."""
        paths = {n: cls for _, n, cls, _ in _divergent_damage_paths()}
        assert name in paths, f"_KNOWN_GAPS['{name}'] no longer diverges -- delete it"
        assert _defining_class(paths[name], "preview_damage") is moves_base.Move, (
            f"{name} now overrides preview_damage -- delete its _KNOWN_GAPS entry"
        )
        assert len(_KNOWN_GAPS[name]) > 40, "a gap needs a reason, not a label"


# ---------------------------------------------------------------------------
# Wire shape: the preview has to reach the client, inside battle_state
# ---------------------------------------------------------------------------


class TestCombatApiWiring:
    """CLAUDE.md: per-poll combat fields go INSIDE ``battle_state`` --
    ``transformCombatData`` whitelists top-level keys and silently drops the
    rest, which is how five wire fields have already gone missing."""

    @staticmethod
    def _adapter(player):
        from src.api.combat_adapter import ApiCombatAdapter

        with patch("src.api.combat_adapter.CombatStrategist"):
            return ApiCombatAdapter(player)

    def _melee_fight(self, distance=3):
        player = _make_player(Shortsword())
        enemy = _make_enemy(name="Slime")
        _link(player, enemy, distance)
        _place(player, enemy, distance)
        move = PommelStrike(player)
        move.target = enemy
        player.known_moves = [move]
        return player, enemy, move

    def test_viable_target_entry_carries_the_damage_preview(self):
        player, enemy, move = self._melee_fight()
        entry = self._adapter(player)._get_available_targets(move)[0]
        assert entry["damage_preview"] == move.preview_damage(enemy)
        assert entry["damage_preview"]["max"] > 0

    def test_viable_target_entry_reports_no_shortfall(self):
        player, _, move = self._melee_fight()
        entry = self._adapter(player)._get_available_targets(move)[0]
        assert entry["in_range"] is True
        assert entry["shortfall_ft"] is None

    def test_out_of_reach_enemy_reports_how_far_short_it_is(self):
        """The point of ``shortfall_ft``: the client renders '3 ft short'
        rather than just greying the move out with no explanation."""
        player, enemy, move = self._melee_fight(distance=3)
        _link(player, enemy, move.mvrange[1] + 3)
        entry = self._adapter(player)._get_available_moves()[0]
        preview = entry["target_previews"][0]
        assert preview["in_range"] is False
        assert preview["shortfall_ft"] == 3
        assert preview["damage_preview"] is None

    def test_out_of_reach_enemy_is_not_a_selectable_target(self):
        """``_get_available_targets`` is the adapter's allow-list for
        ``select_target``; the preview list must not widen it."""
        player, enemy, move = self._melee_fight(distance=3)
        _link(player, enemy, move.mvrange[1] + 3)
        assert self._adapter(player)._get_available_targets(move) == []

    def test_range_ring_only_for_reach_beyond_melee(self):
        player, enemy, move = self._melee_fight()
        melee_entry = self._adapter(player)._get_available_moves()[0]
        assert melee_entry["range_ring"] is None, (
            "a 5 ft ring is noise on every melee move; only reach past 6 ft "
            "earns a ring"
        )

        reach_player = _make_player(Pole())
        reach_enemy = _make_enemy(name="Slime")
        _link(reach_player, reach_enemy, 5)
        _place(reach_player, reach_enemy, 5)
        sweep = Sweep(reach_player)
        reach_player.known_moves = [sweep]
        reach_entry = self._adapter(reach_player)._get_available_moves()[0]
        assert reach_entry["range_ring"] == sweep.mvrange[1] > 6

    def test_area_move_publishes_a_preview_per_affected_enemy(self):
        player = _make_player(Pole())
        a = _make_enemy(name="A")
        b = _make_enemy(name="B")
        _link(player, [a, b], 3)
        player.combat_position = CombatPosition(x=0, y=0, facing=Direction.E)
        a.combat_position = CombatPosition(x=3, y=0, facing=Direction.W)
        b.combat_position = CombatPosition(x=4, y=1, facing=Direction.W)
        move = HalberdSpin(player)
        player.known_moves = [move]
        entry = self._adapter(player)._get_available_moves()[0]
        affected = entry["affected_preview"]
        assert {p["name"] for p in affected} == {"A", "B"}
        for p in affected:
            assert p["damage_preview"]["max"] > 0

    def test_single_target_move_publishes_an_empty_affected_set(self):
        player, _, _ = self._melee_fight()
        entry = self._adapter(player)._get_available_moves()[0]
        assert entry["affected_preview"] == []

    def test_previews_ride_inside_battle_state_not_the_top_level(self):
        player, _, _ = self._melee_fight()
        adapter = self._adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        adapter.available_options = adapter._get_available_moves()
        state = adapter.get_combat_state()
        assert "available_options" not in state
        assert "target_previews" not in state
        move_entry = state["battle_state"]["available_options"][0]
        assert "target_previews" in move_entry
        assert "range_ring" in move_entry

    def test_previews_are_recomputed_on_every_poll(self):
        """Fidelity is 'exact, recomputed each poll'. A preview frozen at move
        selection would still claim a non-lethal hit after the target had been
        chipped down to one HP."""
        player, enemy, _ = self._melee_fight()
        adapter = self._adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        adapter.available_options = adapter._get_available_moves()
        stale = adapter.available_options[0]["viable_targets"][0]
        assert stale["damage_preview"]["lethal"] is False

        enemy.hp = 1
        fresh = adapter.get_combat_state()["battle_state"]["available_options"][0]
        assert fresh["viable_targets"][0]["damage_preview"]["lethal"] is True


class TestOutOfReachTargetsArePricedHonestly:
    """A target the move cannot reach must carry no damage and no hit chance --
    only the shortfall that says how far short it is. Both numbers were
    previously computed for it, because most attacks' ``viable()`` only asks
    whether *some* enemy is in range."""

    def _fight(self):
        from src.api.combat_adapter import ApiCombatAdapter

        player = _make_player(Pole())
        near = _make_enemy(name="Slime")
        far = _make_enemy(name="Lurker")
        _link(player, [near, far], 3)
        player.combat_proximity[far] = 14
        player.combat_position = CombatPosition(x=0, y=0, facing=Direction.E)
        near.combat_position = CombatPosition(x=3, y=0, facing=Direction.W)
        far.combat_position = CombatPosition(x=14, y=0, facing=Direction.W)
        from src.moves import OverheadSmash

        move = OverheadSmash(player)
        move.target = near
        player.known_moves = [move]
        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player)
        return adapter, near, far

    def test_unreachable_entry_has_no_damage_or_hit_chance(self):
        adapter, _, _ = self._fight()
        previews = adapter._get_available_moves()[0]["target_previews"]
        unreachable = [p for p in previews if not p["in_range"]]
        assert unreachable, "expected the far enemy to be out of reach"
        for entry in unreachable:
            assert entry["damage_preview"] is None
            assert "hit_chance" not in entry
            assert entry["shortfall_ft"] == 7

    def test_reachable_entry_still_carries_both(self):
        adapter, _, _ = self._fight()
        previews = adapter._get_available_moves()[0]["target_previews"]
        reachable = [p for p in previews if p["in_range"]]
        assert reachable
        for entry in reachable:
            assert entry["damage_preview"]["max"] > 0
            assert entry["hit_chance"] is not None
