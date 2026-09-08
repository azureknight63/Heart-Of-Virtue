"""Integration tests for the config chain: INI file -> SessionManager -> Player.

Scope note: the exhaustive field-by-field parsing proof lives in
``tests/test_config_manager_basic.py::test_every_field_round_trips_from_ini``,
which writes a non-default value for *every* ``GameConfig`` field and asserts
each one comes back. Nine per-section "are these settings accessible?" tests
that used to live here were strictly weaker copies of that and were removed.
What remains here is the part that file cannot cover: how ``CONFIG_FILE``
selects a config, how the path is resolved, and which of the loaded values
actually reach the SessionManager / Player.
"""

import configparser
import functools
import inspect
from pathlib import Path

import pytest

import src.items as items_module
from src.api.services import session_manager as session_manager_module
from src.api.services.session_manager import SessionManager
from src.config_manager import ConfigManager, GameConfig
from src.player import Player
from src.universe import Universe

ROOT = Path(__file__).resolve().parent.parent

# A real repo-root config, used to prove relative-path resolution. Its values
# are read from the file rather than hardcoded, so editing the config can't
# make this test lie.
_ROOT_CONFIG_NAME = "config_combat_testing.ini"


@pytest.fixture
def config_env(monkeypatch, tmp_path):
    """Write an INI file and point CONFIG_FILE at it."""

    def _write(text, name="probe.ini"):
        path = tmp_path / name
        path.write_text(text)
        monkeypatch.setenv("CONFIG_FILE", str(path))
        return path

    return _write


def test_session_manager_applies_every_config_field_it_reads(config_env):
    """CONFIG_FILE -> SessionManager: map, position, gold, items, equipment."""
    config_env(
        "[game]\n"
        "startmap = combat-testing-arena\n"
        "startposition = (3, 4)\n"
        "testmode = true\n"
        "starting_gold = 777\n"
        "starting_items = Restorative, Bitterroot\n"
        "starting_equipment = Longsword\n"
    )

    manager = SessionManager()

    assert manager.starting_map_name == "combat-testing-arena"
    assert (manager.start_x, manager.start_y) == (3, 4)
    assert manager.starting_gold == 777
    assert manager.starting_item_types == ["Restorative", "Bitterroot"]
    assert manager.starting_equipment == ["Longsword"]
    # The full GameConfig is loaded alongside the hand-parsed fields.
    assert manager.game_config.testmode is True
    assert manager.game_config.startmap == "combat-testing-arena"
    assert manager.game_config.startposition == (3, 4)


def test_session_manager_falls_back_to_defaults_without_config_file(monkeypatch):
    """No CONFIG_FILE: the documented defaults, and no GameConfig at all."""
    monkeypatch.delenv("CONFIG_FILE", raising=False)

    manager = SessionManager()

    assert manager.starting_map_name == "dark-grotto"
    assert (manager.start_x, manager.start_y) == (1, 1)
    assert manager.starting_gold == 0
    assert manager.starting_item_types == []
    assert manager.starting_equipment == []


def test_session_manager_ignores_a_config_file_that_does_not_exist(monkeypatch):
    """A stale CONFIG_FILE path degrades to defaults instead of crashing."""
    monkeypatch.setenv("CONFIG_FILE", "no_such_config_anywhere.ini")

    manager = SessionManager()

    assert manager.starting_map_name == "dark-grotto"
    assert (manager.start_x, manager.start_y) == (1, 1)
    assert manager.game_config is None


# ---------------------------------------------------------------------------
# Issue #562/#551: the beta loadout must include a blunt weapon.
#
# The Grondia beta route's first three enemy types (RockRumbler,
# CorruptedStoneCreature, KingSlime) all resist slashing and are *vulnerable*
# to crushing, and the canonical damage line in src/moves/_base.py subtracts
# protection AFTER the resistance multiplier — so halved slashing minus a high
# protection floors at zero. A slashing-only loadout leaves Jean literally
# unable to damage a Rock Rumbler (0 per hit) and doing 2-3 to a Stone
# Creature, which stalls the Mineral Pools tiles the beta exists to test.
#
# This pins the config, not the engine. Both sides are derived: the loadout is
# read the way the app reads it (CONFIG_FILE -> SessionManager) and "is a
# Bludgeon" comes from src/items.py rather than a hardcoded class name, so
# retiring RustedIronMace in favour of another blunt weapon keeps this green
# while dropping blunt entirely does not.
# ---------------------------------------------------------------------------

_BETA_CONFIG_NAME = "config_grondia_beta.ini"


@functools.lru_cache(maxsize=1)
def _weapon_subtypes():
    """Return ``{class_name: subtype}`` for every weapon class in src.items.

    Constructed rather than read off the source: ``subtype`` is passed up to
    ``Weapon.__init__`` as a kwarg, so there is nothing to grep for reliably.
    Deliberately **not** wrapped in try/except — all 20 weapon classes take
    only optional kwargs today, and a future one that needs a required
    argument should fail here with a traceback naming it, rather than be
    silently dropped and reported downstream as "the config has no blunt
    weapon". Cached because three tests below want the same map.
    """
    subtypes = {}
    for name, cls in inspect.getmembers(items_module, inspect.isclass):
        if not issubclass(cls, items_module.Weapon) or cls is items_module.Weapon:
            continue
        subtypes[name] = cls().subtype
    return subtypes


def test_the_bludgeon_population_is_derivable():
    """Positive control — the derived sets must be non-empty, or every
    assertion below passes vacuously.

    Floors, not pins: src/items.py currently yields 20 weapon classes, of
    which 4 are Bludgeon. The thresholds sit well below both so retiring an
    individual weapon does not trip them, while the derivation collapsing to
    nothing does.
    """
    subtypes = _weapon_subtypes()
    bludgeons = {n for n, s in subtypes.items() if s == "Bludgeon"}

    assert len(subtypes) >= 15, f"only {len(subtypes)} weapon classes found"
    assert bludgeons, "src/items.py defines no Bludgeon weapon at all"
    # And Bludgeon must still be the subtype that maps to crushing — the whole
    # point of the loadout fix is the damage type, not the label.
    crushing = items_module.item_types["weapons"]["base_damage_types"]["crushing"]
    assert "Bludgeon" in crushing


def test_beta_starting_loadout_includes_a_blunt_weapon(monkeypatch):
    """The committed beta config must arm Jean with a crushing weapon."""
    monkeypatch.setenv("CONFIG_FILE", _BETA_CONFIG_NAME)

    manager = SessionManager()

    assert manager.starting_equipment, (
        f"{_BETA_CONFIG_NAME} parsed to an empty starting_equipment"
    )

    subtypes = _weapon_subtypes()
    # `Item[:enchantment]` — the class name is everything before the colon.
    specs = [spec.split(":", 1)[0].strip() for spec in manager.starting_equipment]
    blunt = [name for name in specs if subtypes.get(name) == "Bludgeon"]

    assert blunt, (
        f"{_BETA_CONFIG_NAME} starting_equipment is {specs}, which contains no "
        "Bludgeon-subtype weapon. The route's first three enemy types resist "
        "slashing to (near) zero damage — see issue #562/#551. Every spec must "
        "also name a real src.items class; a typo silently no-ops."
    )

    # Every spec must actually resolve, or the loadout lies about itself.
    unknown = [name for name in specs if not hasattr(items_module, name)]
    assert unknown == [], f"src.items defines no {unknown}"


def test_beta_loadout_leaves_jean_holding_the_blunt_weapon(monkeypatch):
    """The *last* weapon listed wins the slot, so ordering is load-bearing.

    `SessionManager._apply_starting_equipment` unequips any already-equipped
    item of the same maintype before equipping the next, and sets
    `player.eq_weapon` to whichever weapon it processes last. A future edit
    that appended a sword after the mace would leave a green
    "includes a blunt weapon" assertion above and Jean still holding slashing.
    """
    monkeypatch.setenv("CONFIG_FILE", _BETA_CONFIG_NAME)

    manager = SessionManager()

    subtypes = _weapon_subtypes()
    specs = [spec.split(":", 1)[0].strip() for spec in manager.starting_equipment]
    weapons = [name for name in specs if name in subtypes]

    assert weapons, f"{_BETA_CONFIG_NAME} starting_equipment arms Jean with nothing"
    assert subtypes[weapons[-1]] == "Bludgeon", (
        f"the last weapon in {_BETA_CONFIG_NAME}'s starting_equipment is "
        f"{weapons[-1]} ({subtypes[weapons[-1]]}), so that is what Jean has "
        "drawn. List the blunt weapon last."
    )


def test_session_manager_resolves_a_relative_config_path_against_project_root(
    monkeypatch, tmp_path
):
    """`CONFIG_FILE=config_x.ini` must resolve from the repo root, not cwd."""
    monkeypatch.setenv("CONFIG_FILE", _ROOT_CONFIG_NAME)
    monkeypatch.chdir(tmp_path)  # a cwd where the file definitely is not

    parser = configparser.ConfigParser()
    parser.read(ROOT / _ROOT_CONFIG_NAME)
    expected_map = parser.get("game", "startmap")
    expected_pos = tuple(
        int(part) for part in parser.get("game", "startposition").split(",")
    )

    manager = SessionManager()

    assert manager.starting_map_name == expected_map
    assert (manager.start_x, manager.start_y) == expected_pos


@pytest.mark.parametrize("quote", ["'", '"'])
def test_session_manager_strips_dotenv_quotes_from_config_file(
    monkeypatch, tmp_path, quote
):
    """`.env` files often quote the value; the quotes are not part of the path."""
    path = tmp_path / "quoted.ini"
    path.write_text("[game]\nstartmap = quoted-map\nstartposition = 8, 9\n")
    monkeypatch.setenv("CONFIG_FILE", f"{quote}{path}{quote}")

    manager = SessionManager()

    assert manager.starting_map_name == "quoted-map"
    assert (manager.start_x, manager.start_y) == (8, 9)


def test_game_config_defaults_to_config_dev_ini(monkeypatch):
    """With CONFIG_FILE unset, _load_game_config still looks for config_dev.ini.

    Documented in CLAUDE.md ("Omit CONFIG_FILE to fall back to CONFIG_FILE from
    .env, or config_dev.ini"). config_dev.ini is not checked in, so the lookup
    is observed by forcing the existence check to succeed and recording which
    path ConfigManager is handed.
    """
    monkeypatch.delenv("CONFIG_FILE", raising=False)
    seen = []

    class _RecordingConfigManager:
        def __init__(self, path):
            seen.append(path)

        def load(self):
            return GameConfig(startmap="from-config-dev")

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(
        session_manager_module, "ConfigManager", _RecordingConfigManager
    )

    manager = SessionManager()

    assert seen == [str(ROOT / "config_dev.ini")]
    assert manager.game_config.startmap == "from-config-dev"


def test_malformed_startposition_in_config_does_not_break_session_manager(
    config_env,
):
    """A broken coordinate degrades to the default spawn rather than crashing.

    KNOWN DEFECT (src/api/services/session_manager.py:262-350): the int() parse
    of `startposition` and the read of `startmap` share one try/except, so an
    unparseable coordinate aborts the method before `startmap` is read — the
    game silently boots on the *default map*, not just the default tile. The
    assertion below pins today's behaviour; flip it to "ok-map" if that read
    order is ever fixed. GameConfig itself parses both fields independently
    and is unaffected, which is why manager.game_config still sees the map.
    """
    config_env("[game]\nstartmap = ok-map\nstartposition = not, coords\n")

    manager = SessionManager()

    assert manager.starting_map_name == "dark-grotto"          # startmap lost
    assert (manager.start_x, manager.start_y) == (1, 1)
    assert manager.game_config.startmap == "ok-map"            # but not by ConfigManager


def test_player_config_attribute_defaults():
    """Config-derived Player attributes start neutral until a config is applied."""
    player = Player()

    assert player.testing_mode is False
    assert player.use_colour is True
    assert player.enable_animations is True
    assert player.animation_speed == 1.0
    assert player.game_config is None


def test_universe_config_attribute_defaults():
    """Universe does not inherit config from its player implicitly."""
    universe = Universe(Player())

    assert universe.testing_mode is False
    assert universe.game_config is None


def test_loaded_config_drives_player_display_settings(tmp_path):
    """The INI values a caller copies onto the Player survive the round trip."""
    path = tmp_path / "display.ini"
    path.write_text(
        "[game]\n"
        "testmode = true\n"
        "use_colour = false\n"
        "enable_animations = false\n"
        "animation_speed = 0.5\n"
    )
    config = ConfigManager(str(path)).load()

    player = Player()
    player.testing_mode = config.testmode
    player.use_colour = config.use_colour
    player.enable_animations = config.enable_animations
    player.animation_speed = config.animation_speed
    player.game_config = config

    assert (player.testing_mode, player.use_colour) == (True, False)
    assert player.enable_animations is False
    assert player.animation_speed == 0.5
    # The whole config rides along, so downstream code can read rarer fields.
    assert player.game_config.startposition == (0, 0)
