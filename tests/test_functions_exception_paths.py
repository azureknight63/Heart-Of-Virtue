"""Coverage for exception/edge-case branches in src/functions.py not exercised
by the existing suite.

Targets (line numbers as of this writing):
    119        check_for_combat: finesse low/high swap
    192-193    add_enemies_to_combat: player_ref assignment exception
    220        add_enemies_to_combat: pincer scenario
    249-250    add_enemies_to_combat: _combat_adapter reinit exception
    340-341    refresh_stat_bonuses: resistance merge exception
    349-350    refresh_stat_bonuses: status_resistance merge exception
    372        refresh_stat_bonuses: negative primary stat clamp
    380-381    refresh_stat_bonuses: maxhp bump exception
    387-388    refresh_stat_bonuses: maxfatigue bump exception
    416-417    refresh_stat_bonuses: Jean refresh_weight() exception
    428        refresh_stat_bonuses: Jean overweight maxfatigue floor at 0
    439-440    refresh_stat_bonuses: refresh_protection_rating exception
    448-449    refresh_stat_bonuses: add_protection sum exception
    535-537    reset_stats: setattr exception (primary stat)
    564-565    reset_stats: weight_tolerance setattr exception
    576-577    reset_stats: protection setattr exception
    624        SafeUnpickler.find_class: successful module rewrite
    679-680    _patch_player_integrity: `from player import Player` failure
    697-698    _patch_player_integrity: `import items` failure
    700        _patch_player_integrity: eq_weapon fallback to fists
    807-818    autosave: rotation load/save exception handling
    871-872    seek_class: add_modules_for exception
    889-890    seek_class: module import failure during class search
    949-951    inflict: on_application TypeError fallback (replace branch)
    958-959    inflict: on_application TypeError fallback (append branch)
    1017-1019  add_random_enchantments: candidate instantiation exception
    1035-1036  add_random_enchantments: ench.modify() exception
    1040-1044  add_random_enchantments: equip_states assignment failure
    1047-1052  add_random_enchantments: += failure -> extend fallback -> failure
    1188       stack_items_list: dup is master (same instance twice)
    1192-1194  stack_items_list: count += exception
    1201-1202  stack_items_list: stack_grammar() exception

Deliberately NOT covered (documented, not a bug):
    398-399  refresh_stat_bonuses faith-scaling except: unreachable without a
             contrived non-dict status_resistance that would also break the
             surrounding reset_stats()/resistance-merge logic it shares.
    627-628  SafeUnpickler rewrite predicate/rewrite except: the predicate/
             rewrite lambdas (str.startswith / string concat) cannot raise for
             any string `module` argument, and `module` is guaranteed to be a
             string by this point (super().find_class() already validated it,
             else it would have raised TypeError before reaching this code,
             which is a *different*, uncaught, exception type). Effectively
             dead defensive code under the current MODULE_REWRITES contents.
"""

import io
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import src.functions as functions

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"


# ---------------------------------------------------------------------------
# check_for_combat -- finesse low/high swap (line 119)
# ---------------------------------------------------------------------------


def test_check_for_combat_finesse_negative_triggers_swap():
    player = types.SimpleNamespace(
        finesse=-10,
        known_moves=[],
        current_room=types.SimpleNamespace(
            npcs_here=[types.SimpleNamespace(friend=True)]
        ),
    )
    # Should not raise, and friend NPC is skipped -> empty result
    result = functions.check_for_combat(player)
    assert result == []


# ---------------------------------------------------------------------------
# add_enemies_to_combat -- player_ref exception / pincer / adapter reinit
# ---------------------------------------------------------------------------


class _SlottedEnemy:
    __slots__ = ("in_combat", "combat_proximity", "combat_list", "combat_list_allies", "known_moves")

    def __init__(self):
        self.in_combat = False
        self.combat_proximity = {}
        self.combat_list = []
        self.combat_list_allies = []
        self.known_moves = []


class TestAddEnemiesToCombatExceptionPaths:
    def _player_in_combat(self):
        from src.player import Player

        p = Player()
        p.combat_list = []
        p.combat_list_allies = [p]
        p.combat_proximity = {}
        return p

    def test_player_ref_assignment_exception_is_swallowed(self):
        """Lines 192-193: enemy.player_ref = player raising is caught."""
        p = self._player_in_combat()
        enemy = _SlottedEnemy()
        # Should not raise even though `enemy.player_ref = player` fails
        # (no such slot exists on _SlottedEnemy).
        functions.add_enemies_to_combat(p, [enemy])
        assert enemy in p.combat_list
        assert enemy.in_combat is True

    def test_pincer_scenario_selected(self):
        """Line 220: pincer scenario chosen when allies outnumbered by enemies."""
        p = self._player_in_combat()
        existing_enemy = MagicMock()
        existing_enemy.in_combat = True
        existing_enemy.combat_proximity = {}
        p.combat_list.append(existing_enemy)

        new_enemy = MagicMock()
        new_enemy.in_combat = False
        new_enemy.combat_proximity = {}

        functions.add_enemies_to_combat(p, [new_enemy])
        # 2 enemies, 1 ally -> pincer branch executed (no assertion on scenario_type
        # itself since it's a local var, but this exercises the line without error)
        assert new_enemy in p.combat_list

    def test_combat_adapter_reinit_exception_is_swallowed(self):
        """Lines 249-250: _combat_adapter.initialize_combat raising is caught."""
        p = self._player_in_combat()
        p._combat_adapter = MagicMock()
        p._combat_adapter.initialize_combat.side_effect = RuntimeError("boom")
        enemy = MagicMock()
        enemy.in_combat = False
        enemy.combat_proximity = {}
        # Should not raise
        functions.add_enemies_to_combat(p, [enemy])
        assert enemy in p.combat_list


# ---------------------------------------------------------------------------
# refresh_stat_bonuses / reset_stats -- exception branches
# ---------------------------------------------------------------------------


def _rsb_target(**overrides):
    ns = types.SimpleNamespace(
        strength_base=10,
        finesse_base=10,
        speed_base=10,
        endurance_base=10,
        charisma_base=10,
        intelligence_base=10,
        faith_base=10,
        maxhp_base=100,
        maxfatigue_base=50,
        resistance_base={"fire": 1.0},
        status_resistance_base={"generic": 0.0},
        resistance={},
        status_resistance={},
        inventory=[],
        states=[],
        name="Dummy",
    )
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


class _StateWith:
    """Minimal bonus-carrying state; only sets the attrs passed in."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestRefreshStatBonusesExceptionPaths:
    def test_resistance_merge_exception_is_swallowed(self):
        """Lines 340-341: non-numeric resistance bonus value skipped."""
        target = _rsb_target()
        target.states.append(_StateWith(add_resistance={"fire": "not-a-number"}))
        functions.refresh_stat_bonuses(target)
        # Merge failed silently; base value preserved
        assert target.resistance["fire"] == 1.0

    def test_status_resistance_merge_exception_is_swallowed(self):
        """Lines 349-350: non-numeric status_resistance bonus value skipped."""
        target = _rsb_target()
        target.states.append(
            _StateWith(add_status_resistance={"generic": "not-a-number"})
        )
        functions.refresh_stat_bonuses(target)
        assert target.status_resistance["generic"] == 0.0

    def test_negative_primary_stat_clamped_to_zero(self):
        """Line 372: a stacked debuff driving a stat negative is clamped to 0."""
        target = _rsb_target()
        target.states.append(_StateWith(add_str=-9999))
        functions.refresh_stat_bonuses(target)
        assert target.strength == 0

    def test_maxhp_bump_exception_is_swallowed(self):
        """Lines 380-381: non-numeric maxhp prevents the strength-derived bump."""
        target = _rsb_target(maxhp_base="not-a-number")
        # Should not raise despite maxhp being non-numeric
        functions.refresh_stat_bonuses(target)
        assert target.maxhp == "not-a-number"

    def test_maxfatigue_bump_exception_is_swallowed(self):
        """Lines 387-388: non-numeric maxfatigue prevents the endurance-derived bump."""
        target = _rsb_target(maxfatigue_base="not-a-number")
        # No 'fatigue' attribute -> final rounding block is skipped, so the
        # corrupted maxfatigue value is never touched again.
        functions.refresh_stat_bonuses(target)
        assert target.maxfatigue == "not-a-number"

    def test_refresh_protection_rating_exception_is_swallowed(self):
        """Lines 439-440: refresh_protection_rating() raising is caught."""
        target = _rsb_target()
        target.refresh_protection_rating = MagicMock(side_effect=RuntimeError("no"))
        functions.refresh_stat_bonuses(target)
        target.refresh_protection_rating.assert_called_once()

    def test_add_protection_sum_exception_is_swallowed(self):
        """Lines 448-449: incompatible protection type skips the add_protection sum."""
        target = _rsb_target(protection="not-a-number")
        target.states.append(_StateWith(add_protection=5))
        functions.refresh_stat_bonuses(target)
        # Unaffected since the += raised and was swallowed
        assert target.protection == "not-a-number"

    def test_jean_refresh_weight_exception_is_swallowed(self):
        """Lines 416-417: Jean's refresh_weight() raising is caught."""
        target = _rsb_target(name="Jean")
        target.refresh_weight = MagicMock(side_effect=RuntimeError("no"))
        functions.refresh_stat_bonuses(target)
        target.refresh_weight.assert_called_once()

    def test_jean_overweight_maxfatigue_floored_at_zero(self):
        """Line 428: extreme overweight drives maxfatigue negative -> floored at 0."""
        target = _rsb_target(
            name="Jean", weight_tolerance=5, weight_current=1000
        )
        functions.refresh_stat_bonuses(target)
        assert target.maxfatigue == 0


class TestResetStatsExceptionPaths:
    def test_setattr_exception_on_primary_stat_is_swallowed(self):
        """Lines 535-537: read-only `strength` property can't be set."""

        class T:
            def __init__(self):
                self.strength_base = 5

            @property
            def strength(self):
                return 0

        t = T()
        functions.reset_stats(t)  # must not raise
        assert t.strength == 0

    def test_setattr_exception_on_weight_tolerance_is_swallowed(self):
        """Lines 564-565: read-only `weight_tolerance` property can't be set."""

        class T:
            def __init__(self):
                self.weight_tolerance_base = 10

            @property
            def weight_tolerance(self):
                return 99

        t = T()
        functions.reset_stats(t)
        assert t.weight_tolerance == 99

    def test_setattr_exception_on_protection_is_swallowed(self):
        """Lines 576-577: read-only `protection` property can't be set."""

        class T:
            def __init__(self):
                self.protection_base = 10

            @property
            def protection(self):
                return 42

        t = T()
        functions.reset_stats(t)
        assert t.protection == 42


# ---------------------------------------------------------------------------
# SafeUnpickler -- successful module rewrite (line 624)
# ---------------------------------------------------------------------------


def test_safe_unpickler_rewrite_success(tmp_path, monkeypatch):
    import pickle

    mod_name = "story.temp_rewrite_mod_xyz"
    story_pkg = types.ModuleType("story")
    story_pkg.__path__ = []
    monkeypatch.setitem(sys.modules, "story", story_pkg)
    ghost_mod = types.ModuleType(mod_name)
    exec(
        "class RewriteClass:\n    def __init__(self):\n        self.v = 7\n",
        ghost_mod.__dict__,
    )
    monkeypatch.setitem(sys.modules, mod_name, ghost_mod)
    obj = ghost_mod.RewriteClass()
    pfile = tmp_path / "rewrite.sav"
    with open(pfile, "wb") as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

    # Remove the bare 'story.*' entries so normal unpickling fails, forcing the
    # module-rewrite path; register the rewritten 'src.story.*' name exposing
    # the same class so the rewrite succeeds.
    monkeypatch.delitem(sys.modules, mod_name, raising=False)
    monkeypatch.delitem(sys.modules, "story", raising=False)
    rewritten_name = "src." + mod_name
    monkeypatch.setitem(sys.modules, rewritten_name, ghost_mod)

    loaded = functions.load(str(pfile))
    assert loaded.__class__.__name__ == "RewriteClass"
    assert loaded.v == 7


# ---------------------------------------------------------------------------
# _patch_player_integrity -- import failures
# ---------------------------------------------------------------------------


def test_patch_player_integrity_player_import_failure_returns_obj(monkeypatch):
    """Lines 679-680: `from player import Player` failing returns obj unchanged."""
    monkeypatch.setitem(sys.modules, "player", None)
    sentinel = object()
    result = functions._patch_player_integrity(sentinel)
    assert result is sentinel


class _FlakyOnceDescriptor:
    """Data descriptor whose first __set__ raises; subsequent sets succeed.

    Used to exercise the fallback retry at functions.py lines 687-690: the
    first setattr in the try block fails, and the fallback `if factory in
    (list, dict): setattr(...)` retry must succeed.
    """

    def __init__(self):
        self._calls = 0

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get("_flaky_stored")

    def __set__(self, obj, value):
        self._calls += 1
        if self._calls == 1:
            raise RuntimeError("boom-once")
        obj.__dict__["_flaky_stored"] = value


def test_patch_player_integrity_fallback_setattr_retry_succeeds(monkeypatch):
    """Lines 687-690: first setattr raises, fallback retry (factory is list)
    succeeds on the second attempt."""
    from src.player import Player

    player = Player()
    monkeypatch.setattr(Player, "combat_log", _FlakyOnceDescriptor(), raising=False)

    result = functions._patch_player_integrity(player)
    assert result is player
    assert player.combat_log == []


def test_patch_player_integrity_items_import_failure_and_eq_weapon_fallback(monkeypatch):
    """`import src.items` failing leaves fists unset; eq_weapon falls back to
    (still-falsy) fists."""
    from src.player import Player

    player = Player()
    player.fists = None
    player.eq_weapon = None
    monkeypatch.setitem(sys.modules, "src.items", None)

    result = functions._patch_player_integrity(player)
    assert result is player
    assert player.fists is None
    assert player.eq_weapon is None


# ---------------------------------------------------------------------------
# autosave -- rotation exception handling
# ---------------------------------------------------------------------------


class _AutosavePlayer:
    """Minimal picklable stand-in for a saved player."""

    def __init__(self, marker="p"):
        self.marker = marker


def _autosave_dir():
    return Path(functions.__file__).resolve().parent


def _cleanup_autosaves():
    for i in range(1, 6):
        p = _autosave_dir() / f"autosave{i}.sav"
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


class TestAutosaveRotationExceptionPaths:
    """`save`/`load` operate on cwd-relative paths while `saves_list()` always
    scans the src/ directory (`os.path.dirname(__file__)`); chdir into src/ so
    both mechanisms agree on where files live, matching how these functions
    are actually invoked together in practice."""

    def setup_method(self):
        _cleanup_autosaves()

    def teardown_method(self):
        _cleanup_autosaves()

    def test_rotation_normal_path(self, monkeypatch):
        """Lines 806-808, 811-813: normal rotation when autosave1 is loadable."""
        monkeypatch.chdir(_autosave_dir())
        functions.save(_AutosavePlayer("first"), "autosave1")
        functions.autosave(_AutosavePlayer("new"))
        assert (_autosave_dir() / "autosave2.sav").exists()
        assert (_autosave_dir() / "autosave1.sav").exists()

    def test_rotation_skips_corrupt_autosave(self, monkeypatch):
        """Lines 809-810: load() raising on a corrupt autosave is skipped."""
        monkeypatch.chdir(_autosave_dir())
        corrupt_path = _autosave_dir() / "autosave1.sav"
        with open(corrupt_path, "wb") as f:
            f.write(b"not a pickle at all")
        # Must not raise
        functions.autosave(_AutosavePlayer("new"))
        assert (_autosave_dir() / "autosave1.sav").exists()

    def test_rotation_skips_save_failure(self, monkeypatch):
        """Lines 814-815: save() raising during rotation is skipped."""
        monkeypatch.chdir(_autosave_dir())
        functions.save(_AutosavePlayer("first"), "autosave1")
        orig_save = functions.save

        def flaky_save(obj, filename):
            if "autosave2" in str(filename):
                raise RuntimeError("disk full")
            return orig_save(obj, filename)

        monkeypatch.setattr(functions, "save", flaky_save)
        functions.autosave(_AutosavePlayer("new"))
        assert (_autosave_dir() / "autosave1.sav").exists()

    def test_rotation_outer_exception_is_swallowed(self, monkeypatch):
        """Lines 816-818: saves_list() raising is caught; final save still happens."""
        monkeypatch.chdir(_autosave_dir())
        monkeypatch.setattr(
            functions, "saves_list", MagicMock(side_effect=RuntimeError("fs error"))
        )
        functions.autosave(_AutosavePlayer("new"))
        assert (_autosave_dir() / "autosave1.sav").exists()


# ---------------------------------------------------------------------------
# seek_class -- exception branches
# ---------------------------------------------------------------------------


def test_seek_class_add_modules_for_exception_is_swallowed(monkeypatch):
    """Lines 871-872: a failing __import__/import_module for one package is
    caught, and the search continues (ultimately raising ValueError since the
    bogus classname doesn't exist anywhere)."""
    orig_import_module = functions.importlib.import_module

    def fake_import_module(name, *a, **k):
        if name == "tilesets":
            raise ImportError("boom")
        return orig_import_module(name, *a, **k)

    monkeypatch.setattr(functions.importlib, "import_module", fake_import_module)
    with pytest.raises(ValueError):
        functions.seek_class(
            "DefinitelyNotARealClassXYZ123", package="tilesets", allow_other_modules=False
        )


def test_seek_class_module_import_failure_continues(monkeypatch):
    """Lines 889-890: a discovered submodule failing to import is skipped."""

    class _FakeModInfo:
        def __init__(self, name):
            self.name = name

    def fake_walk_packages(path, prefix=""):
        yield _FakeModInfo(prefix + "definitely_not_a_real_submodule_xyz")

    monkeypatch.setattr(functions.pkgutil, "walk_packages", fake_walk_packages)
    with pytest.raises(ValueError):
        functions.seek_class(
            "AlsoNotARealClassXYZ", package="tilesets", allow_other_modules=False
        )


# ---------------------------------------------------------------------------
# inflict -- on_application TypeError fallback
# ---------------------------------------------------------------------------


class _NoArgOnApplication:
    statustype = "generic"
    compounding = False

    def __init__(self):
        self.called_bare = False

    def on_application(self):
        self.called_bare = True


def test_inflict_replace_in_place_on_application_typeerror_fallback():
    """Lines 949-951: replace-in-place branch retries on_application() bare."""
    tgt = MagicMock()
    tgt.status_resistance = {"generic": 0.0}
    existing = _NoArgOnApplication()
    tgt.states = [existing]
    new_state = _NoArgOnApplication()
    result = functions.inflict(new_state, tgt, chance=1.0, force=True)
    assert result is new_state
    assert new_state.called_bare is True
    assert existing not in tgt.states


def test_inflict_append_new_on_application_typeerror_fallback():
    """Lines 958-959: append branch retries on_application() bare."""
    tgt = MagicMock()
    tgt.status_resistance = {"generic": 0.0}
    tgt.states = []
    state = _NoArgOnApplication()
    result = functions.inflict(state, tgt, chance=1.0, force=True)
    assert result is state
    assert state.called_bare is True


# ---------------------------------------------------------------------------
# add_random_enchantments -- exception branches via a fake enchant_tables module
# ---------------------------------------------------------------------------


class _BadInitEnch:
    tier = 1

    def __init__(self, item):
        raise RuntimeError("cannot init")


class _GoodEnch:
    tier = 1
    rarity = 0

    def __init__(self, item):
        self.item = item
        self.requirements = None
        self.equip_states = ["state_marker"]
        self.modify_called = False

    def modify(self):
        self.modify_called = True


class _ModifyRaisesEnch:
    tier = 1
    rarity = 0

    def __init__(self, item):
        self.item = item
        self.requirements = None
        self.equip_states = None

    def modify(self):
        raise RuntimeError("modify failed")


def _install_fake_enchant_tables(monkeypatch, **classes):
    mod = types.ModuleType("enchant_tables")
    for name, cls in classes.items():
        setattr(mod, name, cls)
    monkeypatch.setitem(sys.modules, "enchant_tables", mod)
    # Force a single deterministic roll: group 0 (prefix), rarity always passes.
    import random

    monkeypatch.setattr(random, "randrange", lambda n: 0)
    monkeypatch.setattr(random, "randint", lambda a, b: b)


class _NoEquipStatesItem:
    __slots__ = ("name", "_enchantment_count")

    def __init__(self):
        self.name = "Item"


def test_add_random_enchantments_skips_failing_candidate(monkeypatch):
    """Lines 1017-1019: a candidate that raises on instantiation is skipped,
    while a working candidate in the same tier is still picked."""
    _install_fake_enchant_tables(monkeypatch, BadInit=_BadInitEnch, GoodEnch=_GoodEnch)
    item = types.SimpleNamespace(name="Item", equip_states=[])
    functions.add_random_enchantments(item, 1)
    assert item._enchantment_count == 1


def test_add_random_enchantments_modify_exception_is_swallowed(monkeypatch):
    """Lines 1035-1036: ench.modify() raising is caught."""
    _install_fake_enchant_tables(monkeypatch, Bad=_ModifyRaisesEnch)
    item = types.SimpleNamespace(name="Item", equip_states=[])
    # Should not raise
    functions.add_random_enchantments(item, 1)


def test_add_random_enchantments_equip_states_assignment_failure(monkeypatch):
    """Lines 1040-1044: item without a settable equip_states attribute is
    skipped gracefully (no crash)."""
    _install_fake_enchant_tables(monkeypatch, Good=_GoodEnch)
    item = _NoEquipStatesItem()
    # Should not raise even though `item.equip_states = []` is impossible.
    functions.add_random_enchantments(item, 1)
    assert not hasattr(item, "equip_states")


def test_add_random_enchantments_equip_states_iadd_and_extend_both_fail(monkeypatch):
    """Lines 1047-1052: `+=` failing falls back to `.extend()`, which also
    fails and is swallowed."""
    _install_fake_enchant_tables(monkeypatch, Good=_GoodEnch)
    item = types.SimpleNamespace(name="Item", equip_states=5)  # int: no += list, no extend
    # Should not raise
    functions.add_random_enchantments(item, 1)
    assert item.equip_states == 5


# ---------------------------------------------------------------------------
# stack_items_list -- edge branches
# ---------------------------------------------------------------------------


def test_stack_items_list_dup_is_master_is_skipped():
    """Line 1188: the same instance appearing twice hits `dup is master: continue`."""

    class Item:
        def __init__(self):
            self.name = "Same"
            self.description = "Same"
            self.count = 3

    same = Item()
    lst = [same, same]
    functions.stack_items_list(lst)
    # `dup is master` -> continue: the duplicate is never marked for removal
    # nor merged, so both positional references to the same object remain.
    assert lst == [same, same]
    assert same.count == 3  # unchanged; no self-merge happened


def test_stack_items_list_count_addition_exception_is_swallowed():
    """Lines 1192-1194: master.count += dup.count raising is caught."""

    class Item:
        def __init__(self, name, count):
            self.name = name
            self.description = name
            self.count = count

    master = Item("Rock", None)  # None + int raises TypeError
    dup = Item("Rock", 5)
    lst = [master, dup]
    functions.stack_items_list(lst)
    # Exception swallowed; master.count remains None but dup still removed logic
    # only removes on success, so dup should remain in the list since merge failed.
    assert master.count is None


def test_stack_items_list_stack_grammar_exception_is_swallowed():
    """Lines 1201-1202: stack_grammar() raising is caught."""

    class Item:
        def __init__(self, name, count):
            self.name = name
            self.description = name
            self.count = count

        def stack_grammar(self):
            raise RuntimeError("grammar boom")

    a = Item("Rock", 1)
    b = Item("Rock", 2)
    lst = [a, b]
    # Should not raise
    functions.stack_items_list(lst)
    assert lst[0].count == 3

