"""
Verification tests for CombatEvent loading out of the shipped map JSON.

These pin the deserialization contract for scripted combat: a `CombatEvent`
entry in a map file must come back as a real `CombatEvent` carrying a real
`CombatEventConfig`, with its enemy roster intact. A map that silently loads
its events as inert dicts still "loads fine" — the fight just never happens.

The universe is built once for the whole module (it is expensive and mutates
module-level item/NPC registries); every test here is read-only.
"""

import pytest

from src.combat_event_config import CombatEventConfig
from src.events import CombatEvent
from src.player import Player
from src.universe import Universe


@pytest.fixture(scope="module")
def built_universe():
    player = Player()
    universe = Universe(player)
    if hasattr(player, "attach_universe"):
        player.attach_universe(universe)
    else:
        player.universe = universe
    universe.build(player)
    return player, universe


@pytest.fixture(scope="module")
def testing_map(built_universe):
    _player, universe = built_universe
    for game_map in universe.maps:
        if game_map.get("name") == "testing-map":
            return game_map
    pytest.fail("Could not find 'testing-map' among the loaded maps")


class TestUniverseBuild:
    def test_build_attaches_the_universe_to_the_player(self, built_universe):
        player, universe = built_universe
        assert player.universe is universe

    def test_build_loads_every_shipped_map_exactly_once(self, built_universe):
        """Every map JSON on disk must load, and none twice.

        A duplicate here means two live copies of the same tiles, so an event
        cleared on one is still armed on the other.
        """
        _player, universe = built_universe
        names = [m.get("name") for m in universe.maps]
        assert None not in names
        assert len(names) == len(set(names))
        # Named anchors from three different chapters — a partial load that
        # dropped later maps would still satisfy a bare "len(maps) > 0".
        assert {"testing-map", "verdette-caverns", "grondia"} <= set(names)


class TestCombatEventLoading:
    def test_rock_rumbler_ambush_deserializes_into_a_live_combat_event(
        self, testing_map
    ):
        tile = testing_map.get((2, 3))
        assert tile is not None, "Could not find tile (2, 3) in testing-map"

        combat_events = [
            ev for ev in tile.events_here if isinstance(ev, CombatEvent)
        ]
        assert len(combat_events) == 1, (
            "testing-map (2,3) must carry exactly one scripted CombatEvent; "
            f"found {[type(e).__name__ for e in tile.events_here]}"
        )

        event = combat_events[0]
        assert event.name == "Rock Rumbler Ambush"
        config = event.config
        assert isinstance(config, CombatEventConfig)
        # The roster survives the JSON round-trip as [class_name, count] pairs.
        assert [list(pair) for pair in config.enemy_list] == [["RockRumbler", 2]]
        assert config.scenario_type == "standard"
        assert "Rock Rumblers block your path" in config.narrative_text
        # The event advertises itself as awaiting the client's combat_start.
        assert event.needs_input is True
        assert [o["value"] for o in event.input_options] == ["combat_start"]

    def test_every_tile_exposes_a_list_of_events(self, testing_map):
        """events_here must be a real list on every tile, not None or a dict."""
        checked = 0
        for coord, tile in testing_map.items():
            if not isinstance(coord, tuple) or tile is None:
                continue
            assert isinstance(tile.events_here, list), coord
            checked += 1
        assert checked > 0, "testing-map contained no tiles"


class TestCombatEventConfigDefaults:
    def test_defaults_are_inert(self):
        """A bare config must not conjure enemies, allies, or a grid override."""
        config = CombatEventConfig()
        assert config.enemy_list == []
        assert config.ally_list == []
        assert config.grid_size_override is None
        assert config.scenario_type == "standard"
        assert config.narrative_text == ""
        assert config.on_victory_text == ""
