"""Coverage-focused unit tests for src/api/services/session_manager.py.

Covers: config-loading branches (position/items/equipment/gold/game-config/
player-stats — success, missing-file, missing-option, and exception paths),
item/equipment/party-member application helpers, player creation success and
fallback paths, and the full Session/SessionManager session-lifecycle API
(create/get/set/save/expire/cleanup/count/list).

Uses the normal package import path (`from src.api.services.session_manager
import ...`) rather than the spec_from_file_location trick used in
tests/test_session_manager_map_fallback.py — under pytest, tests/conftest.py
pre-wires the src.* <-> bare-name import shims before this module's own lazy
imports (Player/Universe/items/functions) ever run, so the normal import
works fine and keeps coverage attribution simple.
"""

import sys
import types
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.api.services.session_manager import MinimalPlayer, Session, SessionManager

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ini(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


def _bare_manager(monkeypatch) -> SessionManager:
    """A SessionManager built with CONFIG_FILE unset (no config side effects)."""
    monkeypatch.delenv("CONFIG_FILE", raising=False)
    return SessionManager()


@pytest.fixture
def repo_root_ini(monkeypatch):
    """Write a transient config file at the *real* repo root and point
    CONFIG_FILE at it via a relative filename.

    session_manager.py resolves relative CONFIG_FILE paths against a
    hardcoded project-root computation (Path(__file__)...parent x4), so the
    only way to exercise that "relative path" branch is with a file that
    genuinely exists at the repo root — tmp_path won't do. Rather than
    piggyback on a real project config (e.g. config_combat_testing.ini,
    which CLAUDE.md documents as a mutable surface other agents/skills
    actively edit for combat testing — asserting on its exact values would
    make this test break for reasons unrelated to session_manager), this
    fixture creates and tears down its own scratch file.
    """
    path = ROOT / "_pytest_session_manager_scratch.ini"

    def _write(content: str) -> Path:
        path.write_text(content)
        monkeypatch.setenv("CONFIG_FILE", path.name)
        return path

    try:
        yield _write
    finally:
        if path.exists():
            path.unlink()


def _make_universe(maps=None, default=None, story=None):
    u = MagicMock()
    u.maps = maps if maps is not None else ([default] if default else [])
    u.starting_map_default = default
    u.story = story if story is not None else {}
    u.game_tick = 0
    return u


def _make_player():
    p = MagicMock()
    p.username = "testuser"
    p.inventory = []
    p.game_config = None
    return p


def _fake_modules(mock_player, mock_universe):
    """Inject lightweight fake src.player / src.universe into sys.modules."""
    player_mod = types.ModuleType("src.player")
    player_mod.Player = MagicMock(return_value=mock_player)

    universe_mod = types.ModuleType("src.universe")
    universe_mod.Universe = MagicMock(return_value=mock_universe)

    return patch.dict(
        sys.modules,
        {"src.player": player_mod, "src.universe": universe_mod},
    )


def _make_game_config(**overrides):
    defaults = dict(
        skipdialog=False,
        starting_exp=0,
        learn_all_skills=False,
        god_mode=False,
        starting_party_members=[],
    )
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


class _FakeGold:
    def __init__(self, amount=1):
        self.amount = amount
        self.name = "Gold"


class _FakeWeapon:
    maintype = "Weapon"

    def __init__(self, enchantment_level=0):
        self.enchantment_level = enchantment_level
        self.isequipped = False
        self.interactions = ["equip"]
        self.on_equip_called_with = None

    def on_equip(self, player):
        self.on_equip_called_with = player


class _FakeArmor:
    maintype = "Armor"

    def __init__(self, enchantment_level=0):
        self.enchantment_level = enchantment_level
        self.isequipped = False
        self.interactions = ["equip"]

    def on_equip(self, player):
        pass


class _FakeAccessory:
    maintype = "Accessory"

    def __init__(self, enchantment_level=0):
        self.enchantment_level = enchantment_level
        self.isequipped = False
        self.interactions = ["equip"]

    def on_equip(self, player):
        pass


class _FakeNoIsEquipped:
    """Item lacking `isequipped` — exercises the hasattr(item, "isequipped") False branch."""

    maintype = "Trinket"

    def __init__(self, enchantment_level=0):
        self.enchantment_level = enchantment_level

    def on_equip(self, player):
        pass


class _FakeBrokenOnEquip:
    maintype = "Weapon"

    def __init__(self, enchantment_level=0):
        self.enchantment_level = enchantment_level
        self.isequipped = False
        self.interactions = ["equip"]

    def on_equip(self, player):
        raise RuntimeError("on_equip exploded")


class _FakeBrokenInit:
    def __init__(self, enchantment_level=0):
        raise RuntimeError("cannot construct")


def _fake_items_module(**classes):
    mod = types.ModuleType("items")
    for name, cls in classes.items():
        setattr(mod, name, cls)
    return mod


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


def test_session_init_sets_fields_and_expiry():
    created = datetime(2026, 1, 1, 12, 0, 0)
    s = Session("sid", "pid", "alice", created)
    assert s.session_id == "sid"
    assert s.player_id == "pid"
    assert s.username == "alice"
    assert s.created_at == created
    assert s.last_accessed == created
    assert s.expires_at == created + timedelta(hours=24)
    assert s.data == {}


def test_session_is_expired_false_when_fresh():
    s = Session("sid", "pid", "alice", datetime.now())
    assert s.is_expired() is False


def test_session_is_expired_true_when_old():
    old = datetime.now() - timedelta(hours=48)
    s = Session("sid", "pid", "alice", old)
    assert s.is_expired() is True


def test_session_update_access_time_extends_when_active():
    s = Session("sid", "pid", "alice", datetime.now())
    old_expiry = s.expires_at
    s.update_access_time()
    assert s.expires_at >= old_expiry


def test_session_update_access_time_does_not_extend_when_expired():
    old = datetime.now() - timedelta(hours=48)
    s = Session("sid", "pid", "alice", old)
    original_expiry = s.expires_at
    s.update_access_time()
    # last_accessed always updates...
    assert s.last_accessed != old
    # ...but expires_at is untouched because the session is already expired.
    assert s.expires_at == original_expiry


def test_session_to_dict():
    created = datetime(2026, 1, 1, 12, 0, 0)
    s = Session("sid", "pid", "alice", created)
    s.data = {"foo": "bar"}
    d = s.to_dict()
    assert d == {
        "session_id": "sid",
        "player_id": "pid",
        "username": "alice",
        "created_at": created.isoformat(),
        "last_accessed": created.isoformat(),
        "expires_at": s.expires_at.isoformat(),
        "data": {"foo": "bar"},
    }


# ---------------------------------------------------------------------------
# MinimalPlayer
# ---------------------------------------------------------------------------


def test_minimal_player_defaults():
    p = MinimalPlayer("bob")
    assert p.username == "bob"
    assert p.name == "Jean"
    assert p.location_x == 0 and p.location_y == 0
    assert p.universe is None
    assert p.hp == 100 and p.maxhp == 100
    assert p.level == 1
    assert p.story == {}
    assert p.reputation == {}
    assert len(p.inventory) == 4
    names = {item["name"] for item in p.inventory}
    assert names == {"Wooden Sword", "Leather Armor", "Health Potion", "Gold Coins"}
    assert p.resistance["fire"] == 1.0
    assert p.status_resistance["poison"] == 1.0
    assert isinstance(p.prayer_msg, list) and len(p.prayer_msg) == 6


# ---------------------------------------------------------------------------
# _load_starting_position_from_config
# ---------------------------------------------------------------------------


def test_load_starting_position_no_config_file_env(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    assert (mgr.start_x, mgr.start_y) == (1, 1)
    assert mgr.starting_map_name == "dark-grotto"


def test_load_starting_position_absolute_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "does-not-exist.ini"))
    mgr = SessionManager()
    assert (mgr.start_x, mgr.start_y) == (1, 1)
    assert mgr.starting_map_name == "dark-grotto"


def test_load_starting_position_absolute_with_options(monkeypatch, tmp_path):
    ini = _write_ini(
        tmp_path / "cfg.ini",
        "[game]\nstartposition = (3, 4)\nstartmap = my-map\n",
    )
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    assert (mgr.start_x, mgr.start_y) == (3, 4)
    assert mgr.starting_map_name == "my-map"


def test_load_starting_position_no_options_in_game_section(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\nother_key = 1\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    assert (mgr.start_x, mgr.start_y) == (1, 1)
    assert mgr.starting_map_name == "dark-grotto"


def test_load_starting_position_malformed_value_is_caught(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\nstartposition = abc, def\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    # Should not raise, exception is caught and defaults are preserved.
    mgr = SessionManager()
    assert (mgr.start_x, mgr.start_y) == (1, 1)


def test_load_starting_position_relative_path(repo_root_ini):
    # A scratch file at the real repo root, referenced by relative filename —
    # exercises the relative-path branch (project_root computation) as well
    # as the "option present" branches.
    repo_root_ini("[game]\nstartposition = 2, 5\nstartmap = some-map\n")
    mgr = SessionManager()
    assert (mgr.start_x, mgr.start_y) == (2, 5)
    assert mgr.starting_map_name == "some-map"


def test_load_starting_position_quoted_path(monkeypatch, tmp_path):
    ini = _write_ini(
        tmp_path / "cfg.ini", "[game]\nstartposition = 7, 8\nstartmap = quoted\n"
    )
    monkeypatch.setenv("CONFIG_FILE", f"'{ini}'")
    mgr = SessionManager()
    assert (mgr.start_x, mgr.start_y) == (7, 8)
    assert mgr.starting_map_name == "quoted"


# ---------------------------------------------------------------------------
# _load_starting_items_from_config
# ---------------------------------------------------------------------------


def test_load_starting_items_no_config_file(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    assert mgr.starting_item_types == []


def test_load_starting_items_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "nope.ini"))
    mgr = SessionManager()
    assert mgr.starting_item_types == []


def test_load_starting_items_no_option(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\nfoo = 1\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    assert mgr.starting_item_types == []


def test_load_starting_items_with_option(monkeypatch, tmp_path):
    ini = _write_ini(
        tmp_path / "cfg.ini", "[game]\nstarting_items = Shortsword, IronCuirass ,  \n"
    )
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    assert mgr.starting_item_types == ["Shortsword", "IronCuirass"]


def test_load_starting_items_exception_is_caught(monkeypatch, tmp_path):
    # Bare '%' triggers configparser.InterpolationSyntaxError inside .get().
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\nstarting_items = 50%% off\n")
    ini.write_text("[game]\nstarting_items = 50% off\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    assert mgr.starting_item_types == []


# ---------------------------------------------------------------------------
# _load_starting_equipment_from_config
# ---------------------------------------------------------------------------


def test_load_starting_equipment_no_config_file(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    assert mgr.starting_equipment == []


def test_load_starting_equipment_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "nope.ini"))
    mgr = SessionManager()
    assert mgr.starting_equipment == []


def test_load_starting_equipment_no_option(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\nfoo = 1\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    assert mgr.starting_equipment == []


def test_load_starting_equipment_with_option(monkeypatch, tmp_path):
    ini = _write_ini(
        tmp_path / "cfg.ini", "[game]\nstarting_equipment = Shortsword:2, Buckler\n"
    )
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    assert mgr.starting_equipment == ["Shortsword:2", "Buckler"]


def test_load_starting_equipment_exception_is_caught(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\nstarting_equipment = 50% off\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    assert mgr.starting_equipment == []


# ---------------------------------------------------------------------------
# _load_starting_gold_from_config
# ---------------------------------------------------------------------------


def test_load_starting_gold_no_config_file(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    assert mgr.starting_gold == 0


def test_load_starting_gold_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "nope.ini"))
    mgr = SessionManager()
    assert mgr.starting_gold == 0


def test_load_starting_gold_no_option(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\nfoo = 1\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    assert mgr.starting_gold == 0


def test_load_starting_gold_with_option(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\nstarting_gold = 250\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    assert mgr.starting_gold == 250


def test_load_starting_gold_exception_is_caught(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\nstarting_gold = notanumber\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    assert mgr.starting_gold == 0


# ---------------------------------------------------------------------------
# _load_game_config
# ---------------------------------------------------------------------------


def test_load_game_config_default_missing_file(monkeypatch):
    # No CONFIG_FILE -> defaults to "config_dev.ini" (relative), which does
    # not exist at the repo root, so game_config stays None.
    mgr = _bare_manager(monkeypatch)
    assert mgr.game_config is None


def test_load_game_config_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "nope.ini"))
    mgr = SessionManager()
    assert mgr.game_config is None


def test_load_game_config_success(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\ntestmode = True\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    sentinel = object()
    fake_cm_instance = MagicMock()
    fake_cm_instance.load.return_value = sentinel
    with patch(
        "src.api.services.session_manager.ConfigManager",
        return_value=fake_cm_instance,
    ):
        mgr = SessionManager()
    assert mgr.game_config is sentinel


def test_load_game_config_exception_is_caught(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\ntestmode = True\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    with patch(
        "src.api.services.session_manager.ConfigManager",
        side_effect=RuntimeError("boom"),
    ):
        mgr = SessionManager()
    assert mgr.game_config is None


# ---------------------------------------------------------------------------
# _create_items_from_config
# ---------------------------------------------------------------------------


def test_create_items_from_config_empty_types(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_item_types = []
    assert mgr._create_items_from_config() == []


def test_create_items_from_config_found_and_not_found(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_item_types = ["Gold", "NoSuchItem"]
    fake_mod = _fake_items_module(Gold=_FakeGold)
    with patch.dict(sys.modules, {"items": fake_mod}):
        items = mgr._create_items_from_config()
    assert len(items) == 1
    assert isinstance(items[0], _FakeGold)


def test_create_items_from_config_construction_error_is_caught(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_item_types = ["Broken"]
    fake_mod = _fake_items_module(Broken=_FakeBrokenInit)
    with patch.dict(sys.modules, {"items": fake_mod}):
        items = mgr._create_items_from_config()
    assert items == []


def test_create_items_from_config_import_fallback_to_src(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_item_types = ["Gold"]
    fake_mod = _fake_items_module(Gold=_FakeGold)
    # `from src import items` resolves via getattr(sys.modules["src"], "items")
    # first (falling back to sys.modules["src.items"] only on AttributeError) —
    # patch both so the fallback path deterministically picks up the fake.
    src_pkg = sys.modules["src"]
    monkeypatch.setattr(src_pkg, "items", fake_mod, raising=False)
    # Force `import items` to fail (ImportError) so the `from src import items`
    # fallback path executes and succeeds.
    with patch.dict(sys.modules, {"items": None, "src.items": fake_mod}):
        items = mgr._create_items_from_config()
    assert len(items) == 1
    assert isinstance(items[0], _FakeGold)


def test_create_items_from_config_both_imports_fail(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_item_types = ["Gold"]
    src_pkg = sys.modules["src"]
    # Remove any cached "items" attribute so the fallback import is forced to
    # actually consult sys.modules["src.items"] (which we set to None below).
    monkeypatch.delattr(src_pkg, "items", raising=False)
    with patch.dict(sys.modules, {"items": None, "src.items": None}):
        items = mgr._create_items_from_config()
    assert items == []


# ---------------------------------------------------------------------------
# _apply_player_stats_from_config
# ---------------------------------------------------------------------------


def test_apply_player_stats_no_config_file(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    player = MagicMock()
    mgr._apply_player_stats_from_config(player)  # early return, should not raise


def test_apply_player_stats_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "nope.ini"))
    mgr = SessionManager()
    player = MagicMock()
    mgr._apply_player_stats_from_config(player)  # should not raise


def test_apply_player_stats_no_player_section(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[game]\nfoo = 1\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    player = MagicMock()
    mgr._apply_player_stats_from_config(player)  # should not raise


def test_apply_player_stats_applies_valid_values_and_skips_invalid(
    monkeypatch, tmp_path
):
    ini = _write_ini(
        tmp_path / "cfg.ini",
        "[player]\nhp = 80\nmaxhp = 120\nheat = 1.5\nfinesse = notanumber\n",
    )
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    player = MagicMock()
    mgr._apply_player_stats_from_config(player)
    assert player.hp == 80
    assert player.maxhp == 120
    assert player.maxhp_base == 120
    assert player.heat == 1.5
    # finesse could not be parsed as int -> left untouched (still a MagicMock attr,
    # not the string "notanumber")
    assert player.finesse != "notanumber"


def test_apply_player_stats_exception_is_caught(monkeypatch, tmp_path):
    ini = _write_ini(tmp_path / "cfg.ini", "[player]\nhp = 50% off\n")
    monkeypatch.setenv("CONFIG_FILE", str(ini))
    mgr = SessionManager()
    player = MagicMock()
    mgr._apply_player_stats_from_config(player)  # should not raise


def test_apply_player_stats_relative_path(repo_root_ini):
    # A scratch file at the real repo root, referenced by relative filename —
    # exercises the relative-path branch (project_root computation).
    repo_root_ini("[player]\nhp = 350\nlevel = 5\n")
    mgr = SessionManager()
    player = MagicMock()
    mgr._apply_player_stats_from_config(player)
    assert player.hp == 350
    assert player.level == 5


# ---------------------------------------------------------------------------
# _apply_starting_equipment
# ---------------------------------------------------------------------------


def test_apply_starting_equipment_empty(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_equipment = []
    player = MagicMock()
    mgr._apply_starting_equipment(player)  # no-op, returns immediately


def test_apply_starting_equipment_class_not_found(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_equipment = ["NoSuchThing"]
    player = MagicMock()
    player.inventory = []
    fake_mod = _fake_items_module()
    fake_functions = types.ModuleType("functions")
    fake_functions.refresh_stat_bonuses = MagicMock()
    with patch.dict(sys.modules, {"items": fake_mod, "functions": fake_functions}):
        mgr._apply_starting_equipment(player)
    assert player.inventory == []


def test_apply_starting_equipment_equips_weapon_and_unequips_conflict(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_equipment = ["Sword:3"]
    player = MagicMock()
    existing = _FakeWeapon()
    existing.isequipped = True
    existing.interactions = ["unequip"]
    player.inventory = [existing]
    player.eq_weapon = None

    fake_mod = _fake_items_module(Sword=_FakeWeapon)
    fake_functions = types.ModuleType("functions")
    fake_functions.refresh_stat_bonuses = MagicMock()
    with patch.dict(sys.modules, {"items": fake_mod, "functions": fake_functions}):
        mgr._apply_starting_equipment(player)

    # Existing weapon of the same maintype is unequipped.
    assert existing.isequipped is False
    assert "equip" in existing.interactions
    assert "unequip" not in existing.interactions
    # New weapon appended, equipped, and set as eq_weapon.
    assert len(player.inventory) == 2
    new_item = player.inventory[1]
    assert isinstance(new_item, _FakeWeapon)
    assert new_item.enchantment_level == 3
    assert new_item.isequipped is True
    assert "unequip" in new_item.interactions
    assert player.eq_weapon is new_item
    assert new_item.on_equip_called_with is player
    fake_functions.refresh_stat_bonuses.assert_called_once_with(player)


def test_apply_starting_equipment_accessory_skips_conflict_check(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_equipment = ["Ring"]
    player = MagicMock()
    player.inventory = []
    fake_mod = _fake_items_module(Ring=_FakeAccessory)
    fake_functions = types.ModuleType("functions")
    fake_functions.refresh_stat_bonuses = MagicMock()
    with patch.dict(sys.modules, {"items": fake_mod, "functions": fake_functions}):
        mgr._apply_starting_equipment(player)
    assert len(player.inventory) == 1
    assert player.inventory[0].isequipped is True


def test_apply_starting_equipment_item_without_isequipped(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_equipment = ["Trinket"]
    player = MagicMock()
    player.inventory = []
    fake_mod = _fake_items_module(Trinket=_FakeNoIsEquipped)
    fake_functions = types.ModuleType("functions")
    fake_functions.refresh_stat_bonuses = MagicMock()
    with patch.dict(sys.modules, {"items": fake_mod, "functions": fake_functions}):
        mgr._apply_starting_equipment(player)
    assert len(player.inventory) == 1
    assert not hasattr(player.inventory[0], "isequipped")


def test_apply_starting_equipment_invalid_enchantment_level_defaults_to_zero(
    monkeypatch,
):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_equipment = ["Sword:notanumber"]
    player = MagicMock()
    player.inventory = []
    fake_mod = _fake_items_module(Sword=_FakeWeapon)
    fake_functions = types.ModuleType("functions")
    fake_functions.refresh_stat_bonuses = MagicMock()
    with patch.dict(sys.modules, {"items": fake_mod, "functions": fake_functions}):
        mgr._apply_starting_equipment(player)
    assert len(player.inventory) == 1
    assert player.inventory[0].enchantment_level == 0


def test_apply_starting_equipment_construction_error_continues(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_equipment = ["Broken", "Sword"]
    player = MagicMock()
    player.inventory = []
    fake_mod = _fake_items_module(Broken=_FakeBrokenInit, Sword=_FakeWeapon)
    fake_functions = types.ModuleType("functions")
    fake_functions.refresh_stat_bonuses = MagicMock()
    with patch.dict(sys.modules, {"items": fake_mod, "functions": fake_functions}):
        mgr._apply_starting_equipment(player)
    # Broken item skipped, Sword still applied.
    assert len(player.inventory) == 1
    assert isinstance(player.inventory[0], _FakeWeapon)


def test_apply_starting_equipment_on_equip_error_is_caught(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_equipment = ["Sword"]
    player = MagicMock()
    player.inventory = []
    fake_mod = _fake_items_module(Sword=_FakeBrokenOnEquip)
    fake_functions = types.ModuleType("functions")
    fake_functions.refresh_stat_bonuses = MagicMock()
    with patch.dict(sys.modules, {"items": fake_mod, "functions": fake_functions}):
        mgr._apply_starting_equipment(player)  # should not raise
    assert len(player.inventory) == 1


def test_apply_starting_equipment_refresh_stat_bonuses_error_is_caught(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_equipment = ["Sword"]
    player = MagicMock()
    player.inventory = []
    fake_mod = _fake_items_module(Sword=_FakeWeapon)
    fake_functions = types.ModuleType("functions")
    fake_functions.refresh_stat_bonuses = MagicMock(side_effect=RuntimeError("boom"))
    with patch.dict(sys.modules, {"items": fake_mod, "functions": fake_functions}):
        mgr._apply_starting_equipment(player)  # should not raise


def test_apply_starting_equipment_functions_import_fallback(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_equipment = ["Sword"]
    player = MagicMock()
    player.inventory = []
    fake_mod = _fake_items_module(Sword=_FakeWeapon)
    fake_functions = types.ModuleType("functions")
    fake_functions.refresh_stat_bonuses = MagicMock()
    src_pkg = sys.modules["src"]
    monkeypatch.setattr(src_pkg, "functions", fake_functions, raising=False)
    with patch.dict(
        sys.modules,
        {"items": fake_mod, "functions": None, "src.functions": fake_functions},
    ):
        mgr._apply_starting_equipment(player)
    fake_functions.refresh_stat_bonuses.assert_called_once_with(player)


def test_apply_starting_equipment_outer_exception_is_caught(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_equipment = ["Sword"]
    player = MagicMock()
    player.inventory = []
    src_pkg = sys.modules["src"]
    # Remove any cached "items" attribute so the fallback import actually
    # consults sys.modules["src.items"] (set to None below) instead of
    # short-circuiting via getattr(src_pkg, "items").
    monkeypatch.delattr(src_pkg, "items", raising=False)
    with patch.dict(sys.modules, {"items": None, "src.items": None}):
        mgr._apply_starting_equipment(player)  # should not raise
    assert player.inventory == []


# ---------------------------------------------------------------------------
# _apply_starting_party_members
# ---------------------------------------------------------------------------


def test_apply_starting_party_members_no_game_config(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = None
    player = MagicMock()
    mgr._apply_starting_party_members(player)  # returns immediately


def test_apply_starting_party_members_no_members(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(starting_party_members=[])
    player = MagicMock()
    mgr._apply_starting_party_members(player)


def test_apply_starting_party_members_player_lacks_combat_list(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(starting_party_members=["Gorran"])

    class _NoAllies:
        pass

    player = _NoAllies()
    mgr._apply_starting_party_members(player)  # hasattr check fails -> return


def test_apply_starting_party_members_no_tile(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(starting_party_members=["Gorran"])
    player = MagicMock()
    player.combat_list_allies = []
    player.map = None
    player.location_x = 0
    player.location_y = 0
    mgr._apply_starting_party_members(player)
    assert player.combat_list_allies == []


def test_apply_starting_party_members_spawns_and_flags_gorran(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(starting_party_members=["Gorran"])
    player = MagicMock()
    player.combat_list_allies = []
    player.location_x = 0
    player.location_y = 0
    ally = MagicMock()
    tile = MagicMock()
    tile.spawn_npc.return_value = ally
    player.map = {(0, 0): tile}
    story = {}
    player.universe.story = story

    mgr._apply_starting_party_members(player)

    tile.spawn_npc.assert_called_once_with("Gorran", delay=0)
    assert ally.friend is True
    assert ally in player.combat_list_allies
    assert story["gorran_first"] == "1"


def test_apply_starting_party_members_skips_duplicate_ally(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(starting_party_members=["Gorran"])
    player = MagicMock()
    ally = MagicMock()
    player.combat_list_allies = [ally]
    player.location_x = 0
    player.location_y = 0
    tile = MagicMock()
    tile.spawn_npc.return_value = ally
    player.map = {(0, 0): tile}
    player.universe.story = {}

    mgr._apply_starting_party_members(player)

    assert player.combat_list_allies.count(ally) == 1


def test_apply_starting_party_members_spawn_error_continues(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(starting_party_members=["Gorran", "Slime"])
    player = MagicMock()
    player.combat_list_allies = []
    player.location_x = 0
    player.location_y = 0
    tile = MagicMock()
    tile.spawn_npc.side_effect = [RuntimeError("boom"), MagicMock()]
    player.map = {(0, 0): tile}
    player.universe.story = {}

    mgr._apply_starting_party_members(player)

    # First (Gorran) failed, second (Slime) succeeded and was appended.
    assert len(player.combat_list_allies) == 1


def test_apply_starting_party_members_non_dict_story_is_skipped(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(starting_party_members=["Gorran"])
    player = MagicMock()
    player.combat_list_allies = []
    player.location_x = 0
    player.location_y = 0
    ally = MagicMock()
    tile = MagicMock()
    tile.spawn_npc.return_value = ally
    player.map = {(0, 0): tile}
    player.universe = None  # getattr(player, "universe", None) -> None -> not a dict

    mgr._apply_starting_party_members(player)  # should not raise
    assert ally in player.combat_list_allies


# ---------------------------------------------------------------------------
# _create_player_for_session
# ---------------------------------------------------------------------------


def test_create_player_import_error_falls_back_to_minimal_player(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    with patch.dict(sys.modules, {"src.player": None}):
        player = mgr._create_player_for_session("bob")
    assert isinstance(player, MinimalPlayer)
    assert player.username == "bob"


def test_create_player_full_success_applies_game_config(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(
        skipdialog=True,
        starting_exp=5,
        learn_all_skills=True,
        god_mode=True,
        starting_party_members=[],
    )
    game_map = {(1, 1): {}, "name": "test-map"}
    mgr.starting_map_name = "test-map"
    mgr.start_x, mgr.start_y = 1, 1

    universe = _make_universe([game_map], default=game_map)
    player = _make_player()
    player.combat_list_allies = []

    fake_learn = MagicMock()
    fake_functions_mod = types.ModuleType("src.functions")
    fake_functions_mod.learn_all_skills_from_skilltree = fake_learn

    with _fake_modules(player, universe), patch.dict(
        sys.modules, {"src.functions": fake_functions_mod}
    ):
        result = mgr._create_player_for_session("carol")

    assert result is player
    assert player.skip_dialog is True
    player.apply_starting_experience.assert_called_once_with(5)
    fake_learn.assert_called_once_with(player)
    player.supersaiyan.assert_called_once()


def test_create_player_learn_all_skills_error_is_caught(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(learn_all_skills=True)
    game_map = {(1, 1): {}, "name": "test-map"}
    mgr.starting_map_name = "test-map"
    mgr.start_x, mgr.start_y = 1, 1

    universe = _make_universe([game_map], default=game_map)
    player = _make_player()
    player.combat_list_allies = []

    fake_functions_mod = types.ModuleType("src.functions")
    fake_functions_mod.learn_all_skills_from_skilltree = MagicMock(
        side_effect=RuntimeError("boom")
    )

    with _fake_modules(player, universe), patch.dict(
        sys.modules, {"src.functions": fake_functions_mod}
    ):
        result = mgr._create_player_for_session("dave")

    # Error was caught internally; player creation still succeeded (not a fallback).
    assert result is player


def test_create_player_outer_exception_triggers_full_fallback(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(starting_exp=5)
    mgr.starting_item_types = ["Gold"]
    mgr.starting_gold = 25
    game_map = {(1, 1): {}, "name": "test-map"}
    mgr.starting_map_name = "test-map"
    mgr.start_x, mgr.start_y = 1, 1

    universe = _make_universe([game_map], default=game_map)
    player = _make_player()
    # Unguarded call in the outer try -> propagates to the outer except,
    # which rebuilds a brand new MinimalPlayer from scratch (re-running the
    # config-items / starting-gold / equipment / party / stats application
    # against the fresh MinimalPlayer).
    player.apply_starting_experience.side_effect = RuntimeError("boom")

    fake_mod = _fake_items_module(Gold=_FakeGold)
    with _fake_modules(player, universe), patch.dict(sys.modules, {"items": fake_mod}):
        result = mgr._create_player_for_session("erin")

    assert isinstance(result, MinimalPlayer)
    assert result.username == "erin"
    # One Gold from starting_item_types + one Gold from starting_gold.
    assert len(result.inventory) == 4 + 2  # 4 default MinimalPlayer items + 2 Gold
    assert sum(isinstance(i, _FakeGold) for i in result.inventory) == 2


def test_create_player_applies_starting_gold_and_config_items(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_gold = 100
    mgr.starting_item_types = ["Gold"]
    game_map = {(1, 1): {}, "name": "test-map"}
    mgr.starting_map_name = "test-map"
    mgr.start_x, mgr.start_y = 1, 1

    universe = _make_universe([game_map], default=game_map)
    player = _make_player()
    player.combat_list_allies = []

    fake_mod = _fake_items_module(Gold=_FakeGold)
    with _fake_modules(player, universe), patch.dict(sys.modules, {"items": fake_mod}):
        result = mgr._create_player_for_session("frank")

    assert result is player
    # One Gold from starting_gold + one Gold from starting_item_types.
    assert len(player.inventory) == 2
    assert all(isinstance(i, _FakeGold) for i in player.inventory)


def test_create_player_starting_gold_import_fallback_to_src(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_gold = 50
    game_map = {(1, 1): {}, "name": "test-map"}
    mgr.starting_map_name = "test-map"
    mgr.start_x, mgr.start_y = 1, 1

    universe = _make_universe([game_map], default=game_map)
    player = _make_player()
    player.combat_list_allies = []

    fake_mod = _fake_items_module(Gold=_FakeGold)
    src_pkg = sys.modules["src"]
    monkeypatch.setattr(src_pkg, "items", fake_mod, raising=False)
    with _fake_modules(player, universe), patch.dict(
        sys.modules, {"items": None, "src.items": fake_mod}
    ):
        result = mgr._create_player_for_session("holly")

    assert result is player
    assert len(player.inventory) == 1
    assert isinstance(player.inventory[0], _FakeGold)


def test_create_player_starting_gold_error_is_caught(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    mgr.starting_gold = 100
    game_map = {(1, 1): {}, "name": "test-map"}
    mgr.starting_map_name = "test-map"
    mgr.start_x, mgr.start_y = 1, 1

    universe = _make_universe([game_map], default=game_map)
    player = _make_player()
    player.combat_list_allies = []

    class _BrokenGold:
        def __init__(self, amount):
            raise RuntimeError("boom")

    fake_mod = _fake_items_module(Gold=_BrokenGold)
    with _fake_modules(player, universe), patch.dict(sys.modules, {"items": fake_mod}):
        result = mgr._create_player_for_session("grace")

    # Error is caught internally; player creation still succeeds.
    assert result is player
    assert player.inventory == []


def test_create_player_full_fallback_gold_import_fallback_to_src(monkeypatch):
    """Outer-fallback path's own gold block: bare `import items` fails, so it
    falls back to `from src import items` (lines 944-945 in the fallback
    branch, distinct from the main-path gold block covered elsewhere)."""
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(starting_exp=5)
    mgr.starting_gold = 10
    game_map = {(1, 1): {}, "name": "test-map"}
    mgr.starting_map_name = "test-map"
    mgr.start_x, mgr.start_y = 1, 1

    universe = _make_universe([game_map], default=game_map)
    player = _make_player()
    player.apply_starting_experience.side_effect = RuntimeError("boom")

    fake_mod = _fake_items_module(Gold=_FakeGold)
    src_pkg = sys.modules["src"]
    monkeypatch.setattr(src_pkg, "items", fake_mod, raising=False)
    with _fake_modules(player, universe), patch.dict(
        sys.modules, {"items": None, "src.items": fake_mod}
    ):
        result = mgr._create_player_for_session("iris")

    assert isinstance(result, MinimalPlayer)
    assert any(isinstance(i, _FakeGold) for i in result.inventory)


def test_create_player_full_fallback_gold_error_is_swallowed(monkeypatch):
    """Outer-fallback path's gold block swallows any exception silently
    (bare `except Exception: pass` at the end of the fallback gold block)."""
    mgr = _bare_manager(monkeypatch)
    mgr.game_config = _make_game_config(starting_exp=5)
    mgr.starting_gold = 10
    game_map = {(1, 1): {}, "name": "test-map"}
    mgr.starting_map_name = "test-map"
    mgr.start_x, mgr.start_y = 1, 1

    universe = _make_universe([game_map], default=game_map)
    player = _make_player()
    player.apply_starting_experience.side_effect = RuntimeError("boom")

    class _BrokenGold:
        def __init__(self, amount):
            raise RuntimeError("gold boom")

    fake_mod = _fake_items_module(Gold=_BrokenGold)
    with _fake_modules(player, universe), patch.dict(sys.modules, {"items": fake_mod}):
        result = mgr._create_player_for_session("jack")  # should not raise

    assert isinstance(result, MinimalPlayer)
    assert not any(isinstance(i, _BrokenGold) for i in result.inventory)


# ---------------------------------------------------------------------------
# create_session / start_new_game
# ---------------------------------------------------------------------------


def test_create_session_returns_ids_and_stores_state(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    sentinel_player = object()
    with patch.object(
        mgr, "_create_player_for_session", return_value=sentinel_player
    ) as mock_create:
        session_id, player_id = mgr.create_session("hank")

    mock_create.assert_called_once_with("hank")
    assert session_id in mgr.sessions
    assert mgr.session_to_player[session_id] == player_id
    assert mgr.players[player_id] is sentinel_player
    assert mgr.sessions[session_id].username == "hank"


def test_start_new_game_session_not_found(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    assert mgr.start_new_game("nonexistent") is False


def test_start_new_game_resets_player_and_clears_data(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    with patch.object(mgr, "_create_player_for_session", return_value="player-v1"):
        session_id, player_id = mgr.create_session("ivan")

    mgr.sessions[session_id].data["some_flag"] = True

    with patch.object(mgr, "_create_player_for_session", return_value="player-v2"):
        result = mgr.start_new_game(session_id)

    assert result is True
    assert mgr.players[player_id] == "player-v2"
    assert mgr.sessions[session_id].data == {}


# ---------------------------------------------------------------------------
# get_session / get_player / set_player / save_session / expire_session
# ---------------------------------------------------------------------------


def test_get_session_not_found(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    assert mgr.get_session("nope") is None


def test_get_session_expired_is_removed(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    old = datetime.now() - timedelta(hours=48)
    session = Session("sid", "pid", "kate", old)
    mgr.sessions["sid"] = session
    mgr.session_to_player["sid"] = "pid"
    mgr.players["pid"] = "player-obj"

    result = mgr.get_session("sid")

    assert result is None
    assert "sid" not in mgr.sessions
    assert "sid" not in mgr.session_to_player
    assert "pid" not in mgr.players


def test_get_session_valid_updates_access_time(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    with patch.object(mgr, "_create_player_for_session", return_value="p"):
        session_id, _ = mgr.create_session("liam")

    session = mgr.get_session(session_id)
    assert session is not None
    assert session.session_id == session_id


def test_get_player_no_session(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    assert mgr.get_player("nope") is None


def test_get_player_returns_player(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    sentinel_player = object()
    with patch.object(
        mgr, "_create_player_for_session", return_value=sentinel_player
    ):
        session_id, _ = mgr.create_session("mona")

    assert mgr.get_player(session_id) is sentinel_player


def test_set_player_no_session(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    assert mgr.set_player("nope", object()) is False


def test_set_player_success(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    with patch.object(mgr, "_create_player_for_session", return_value="old"):
        session_id, player_id = mgr.create_session("nate")

    new_player = object()
    assert mgr.set_player(session_id, new_player) is True
    assert mgr.players[player_id] is new_player


def test_save_session_no_session(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    assert mgr.save_session("nope") is False


def test_save_session_success(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    with patch.object(mgr, "_create_player_for_session", return_value="p"):
        session_id, _ = mgr.create_session("olga")
    assert mgr.save_session(session_id) is True


def test_expire_session_not_found(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    assert mgr.expire_session("nope") is False


def test_expire_session_removes_all_state(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    with patch.object(mgr, "_create_player_for_session", return_value="p"):
        session_id, player_id = mgr.create_session("pete")

    assert mgr.expire_session(session_id) is True
    assert session_id not in mgr.sessions
    assert session_id not in mgr.session_to_player
    assert player_id not in mgr.players


def test_expire_session_player_id_missing_from_players(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    session = Session("sid", "pid-missing", "quinn", datetime.now())
    mgr.sessions["sid"] = session
    mgr.session_to_player["sid"] = "pid-missing"
    # Note: no entry added to mgr.players for "pid-missing".

    assert mgr.expire_session("sid") is True
    assert "sid" not in mgr.sessions


# ---------------------------------------------------------------------------
# cleanup_expired / get_active_session_count / get_all_sessions
# ---------------------------------------------------------------------------


def test_cleanup_expired_removes_only_expired(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    active = Session("active", "p1", "rose", datetime.now())
    expired = Session("expired", "p2", "sam", datetime.now() - timedelta(hours=48))
    mgr.sessions = {"active": active, "expired": expired}
    mgr.session_to_player = {"active": "p1", "expired": "p2"}
    mgr.players = {"p1": "player1", "p2": "player2"}

    count = mgr.cleanup_expired()

    assert count == 1
    assert "active" in mgr.sessions
    assert "expired" not in mgr.sessions


def test_get_active_session_count(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    active = Session("active", "p1", "tina", datetime.now())
    expired = Session("expired", "p2", "uma", datetime.now() - timedelta(hours=48))
    mgr.sessions = {"active": active, "expired": expired}

    assert mgr.get_active_session_count() == 1


def test_get_all_sessions_returns_dicts_and_cleans_expired(monkeypatch):
    mgr = _bare_manager(monkeypatch)
    active = Session("active", "p1", "vera", datetime.now())
    expired = Session("expired", "p2", "walt", datetime.now() - timedelta(hours=48))
    mgr.sessions = {"active": active, "expired": expired}
    mgr.session_to_player = {"active": "p1", "expired": "p2"}
    mgr.players = {"p1": "player1", "p2": "player2"}

    result = mgr.get_all_sessions()

    assert len(result) == 1
    assert result[0]["username"] == "vera"
    assert "expired" not in mgr.sessions
