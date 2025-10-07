import pytest

from src.player import Player
from src.universe import Universe
from src.tiles import MapTile
from src.story.effects import NPCSpawnerEvent


def build_basic_map(universe: Universe):
    test_map = {'name': 'npc_spawner_test'}
    tile_a = MapTile(universe, test_map, 0, 0, description='A')
    tile_b = MapTile(universe, test_map, 1, 0, description='B')
    test_map[(0, 0)] = tile_a
    test_map[(1, 0)] = tile_b
    return test_map, tile_a, tile_b


def test_spawner_basic_spawn():
    player = Player()
    universe = Universe(player)
    player.universe = universe
    test_map, tile_a, _ = build_basic_map(universe)
    player.map = test_map

    # Create event: spawn 2 Slimes on tile_a
    ev = NPCSpawnerEvent(player=player, tile=tile_a, npc_cls='Slime', count=2)
    tile_a.events_here.append(ev)

    # Pre-condition
    assert len(tile_a.npcs_here) == 0

    # Trigger evaluation (tick 0 path)
    universe.game_tick_events()

    # Should have spawned
    assert len(tile_a.npcs_here) == 2
    # Event should have removed itself (one-shot)
    assert ev not in tile_a.events_here
    # Event should not respawn on subsequent ticks
    universe.game_tick += 1
    universe.game_tick_events()
    assert len(tile_a.npcs_here) == 2  # unchanged


def test_spawner_params_coordinate_override():
    player = Player()
    universe = Universe(player)
    player.universe = universe
    test_map, tile_a, tile_b = build_basic_map(universe)
    player.map = test_map

    # Params variant: ["Slime", 1, (1,0)] should spawn on tile_b
    ev = NPCSpawnerEvent(player=player, tile=tile_a, params=['Slime', 1, (1, 0)])
    tile_a.events_here.append(ev)

    universe.game_tick_events()  # tick 0 path

    assert len(tile_a.npcs_here) == 0
    assert len(tile_b.npcs_here) == 1
    assert ev not in tile_a.events_here


def test_spawner_repeat_mode():
    player = Player()
    universe = Universe(player)
    player.universe = universe
    test_map, tile_a, _ = build_basic_map(universe)
    player.map = test_map

    ev = NPCSpawnerEvent(player=player, tile=tile_a, npc_cls='Slime', count=1, repeat=True)
    tile_a.events_here.append(ev)

    # First trigger
    universe.game_tick_events()
    assert len(tile_a.npcs_here) == 1
    assert ev in tile_a.events_here  # repeat should keep it

    # Simulate later tick
    universe.game_tick += 1
    universe.game_tick_events()
    # Another spawn expected
    assert len(tile_a.npcs_here) == 2
    assert ev in tile_a.events_here


if __name__ == '__main__':
    pytest.main([__file__])

