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

import ast
import json
import pathlib
import subprocess

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
    assert config.starting_party_members == ["Gorran"]


def _tracked_flag_configs():
    """Every tracked .ini that sets starting_story_flags, parsed by the engine.

    Tracked only: untracked QA configs in a developer's worktree are theirs.
    """
    listed = subprocess.run(
        ["git", "ls-files", "--", "*.ini"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    return {
        name: ConfigManager(str(REPO_ROOT / name)).load()
        for name in listed
        if "starting_story_flags" in (REPO_ROOT / name).read_text(encoding="utf-8")
    }


def _seeded_flag_keys(game_config):
    """Flag keys, with SessionManager._apply_starting_story_flags' token rules."""
    keys = (token.partition("=")[0].strip() for token in game_config.starting_story_flags)
    return {key for key in keys if key}


def _json_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _json_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _json_strings(value)


def _src_string_literals():
    """Every whole string literal in src/ Python and in the map JSON.

    Exact matches only: a flag named in a comment, or inside a docstring's
    prose, is not a reader of it.
    """
    found = set()
    for path in (REPO_ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found.update(
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
    for path in MAPS_DIR.glob("*.json"):
        found.update(_json_strings(json.loads(path.read_text(encoding="utf-8"))))
    return found


def test_every_flag_a_tracked_config_seeds_is_read_by_the_engine():
    """Issue #709: a seeded flag nothing reads is a claim about game state no
    code honours. ``lurker_defeated`` sat in config_prod.ini, asserted here,
    while nothing in src/ ever read or set it."""
    from src.story.ch02 import AfterDefeatingKingSlime, AfterKingSlimeReturn

    literals = _src_string_literals()
    # The scanner must find readers it is known to have; an empty scan would
    # pass every config vacuously.
    assert {AfterDefeatingKingSlime.GATE_KEY, AfterKingSlimeReturn.GATE_KEY} <= literals

    configs = _tracked_flag_configs()
    assert configs, "no tracked config seeds starting_story_flags; the guard is vacuous"
    unread = {
        name: sorted(_seeded_flag_keys(cfg) - literals)
        for name, cfg in configs.items()
        if _seeded_flag_keys(cfg) - literals
    }
    assert unread == {}


def test_the_starting_story_flags_land_on_a_real_session(monkeypatch):
    """Issue #687: config.starting_story_flags was parsed but never applied.

    Prove a tracked config's flags actually reach the player's story dict, not
    just that the parser produced them. config_prod.ini seeds none since #709,
    so this runs on the tracked config that seeds the most.
    """
    from src.api.services.session_manager import SessionManager
    from src.events import GATE_SET, story_gates

    configs = _tracked_flag_configs()
    name = max(configs, key=lambda n: len(_seeded_flag_keys(configs[n])))
    seeded = _seeded_flag_keys(configs[name])
    assert seeded, "no tracked config seeds a flag to check"

    monkeypatch.setenv("CONFIG_FILE", name)
    manager = SessionManager()

    session_id, _player_id = manager.create_session("config-flag-check")
    player = manager.get_player(session_id)

    gates = story_gates(player)
    assert {key: gates.get(key) for key in seeded} == {key: GATE_SET for key in seeded}


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
