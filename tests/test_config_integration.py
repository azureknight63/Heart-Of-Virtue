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
from pathlib import Path

import pytest

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
