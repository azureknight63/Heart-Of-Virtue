"""config_prod.ini: beta 2, as production serves it.

The server selects this file with ``CONFIG_FILE=config_prod.ini`` in its
``.env`` (docs/development/deployment.md). Beta 2 runs from the Grondia
entrance, where ``BetaTesterBriefing`` sits, to the nomad camp's Ferry Landing,
where the demo ends. Jean arrives at level 4 with the points unspent, so the
LEVEL UP dialog follows the briefing.

The file is read through both loaders the server uses -- ``ConfigManager`` and
``SessionManager``'s own configparser, which reads the start position, items
and gold and does not accept inline comments -- and checked against the maps
rather than restating their coordinates.
"""

import json
import pathlib

import pytest

from src.config_manager import ConfigManager

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROD_CONFIG = REPO_ROOT / "config_prod.ini"
MAPS_DIR = REPO_ROOT / "src" / "resources" / "maps"


@pytest.fixture(scope="module")
def config():
    assert PROD_CONFIG.is_file(), f"{PROD_CONFIG.name} is missing"
    return ConfigManager(str(PROD_CONFIG)).load()


def _map_tiles(path):
    return {key: tile for key, tile in json.loads(path.read_text(encoding="utf-8")).items() if isinstance(tile, dict)}


def test_it_starts_on_the_beta_briefing_tile(config):
    tiles = _map_tiles(MAPS_DIR / f"{config.startmap}.json")
    x, y = config.startposition
    events = {event.get("__class__") for event in tiles[f"({x}, {y})"].get("events", [])}
    assert "BetaTesterBriefing" in events


def test_the_route_ends_at_the_nomad_camp_ferry():
    """Exactly one demo edge, gated on the key Mara's conversation sets."""
    from src.objects import Passageway

    edges = [
        (path.stem, obj["props"].get("demo_end_ready_flag"))
        for path in sorted(MAPS_DIR.glob("*.json"))
        for tile in _map_tiles(path).values()
        for obj in tile.get("objects", [])
        if obj.get("props", {}).get("demo_end")
    ]
    assert edges == [("eastern-descent-nomad-camp", Passageway.DEMO_END_READY_FLAG)]


def test_jean_arrives_at_level_4_with_the_points_to_spend(config):
    assert config.starting_level == 4
    assert config.starting_level_allocation == "player"
    # Exp crossing a level boundary would add points the climb did not award.
    assert config.starting_exp == 0


def test_it_carries_the_chapter_1_state_beta_2_assumes(config):
    assert "lurker_defeated" in config.starting_story_flags
    assert config.starting_party_members == ["Gorran"]


def test_it_plays_the_story_and_keeps_saves(config):
    assert config.skipdialog is False
    assert config.autosave_enabled is True
    assert not any((
        config.learn_all_skills, config.god_mode, config.skip_combat,
        config.debug_mode, config.show_all_items,
    ))


def test_the_session_manager_reads_the_same_start(config, monkeypatch):
    import src.items as items
    from src.api.services.session_manager import SessionManager

    monkeypatch.setenv("CONFIG_FILE", PROD_CONFIG.name)
    manager = SessionManager()

    assert manager.starting_map_name == config.startmap
    assert (manager.start_x, manager.start_y) == config.startposition
    assert manager.game_config == config
    specs = manager.starting_equipment + manager.starting_item_types
    assert specs, "no starting equipment or items were read"
    unknown = [spec for spec in specs if not hasattr(items, spec.split(":")[0].strip())]
    assert unknown == []
    assert manager.starting_gold > 0
