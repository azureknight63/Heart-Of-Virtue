import pytest
import sys
import os

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


def test_multiple_spawners_execute_simultaneously():
    """
    Test that multiple NPCSpawnerEvents on the same tile all execute in the same tick
    before combat evaluation. This ensures friendly and adversarial NPCs spawn together.
    """
    player = Player()
    universe = Universe(player)
    player.universe = universe
    test_map, tile_a, _ = build_basic_map(universe)
    player.map = test_map

    # Create two spawner events on the same tile
    ev1 = NPCSpawnerEvent(player=player, tile=tile_a, npc_cls='Slime', count=2)
    ev2 = NPCSpawnerEvent(player=player, tile=tile_a, npc_cls='CaveBat', count=1)
    tile_a.events_here.append(ev1)
    tile_a.events_here.append(ev2)

    # Pre-condition: no NPCs
    assert len(tile_a.npcs_here) == 0

    # Single tick evaluation should trigger both spawners
    tile_a.evaluate_events()

    # BOTH spawners should have fired in the same tick
    assert len(tile_a.npcs_here) == 3  # 2 Slimes + 1 CaveBat
    # Both events should be removed (one-shot by default)
    assert ev1 not in tile_a.events_here
    assert ev2 not in tile_a.events_here

    # Verify NPC types
    slime_count = sum(1 for npc in tile_a.npcs_here if npc.__class__.__name__ == 'Slime')
    bat_count = sum(1 for npc in tile_a.npcs_here if npc.__class__.__name__ == 'CaveBat')
    assert slime_count == 2
    assert bat_count == 1


def test_multiple_spawners_with_other_events():
    """
    Test that NPCSpawnerEvents are processed first, before other event types.
    This ensures all spawners complete before any other events are processed.
    """
    from src.events import Event

    player = Player()
    universe = Universe(player)
    player.universe = universe
    test_map, tile_a, _ = build_basic_map(universe)
    player.map = test_map

    # Create spawner events and a non-spawner event
    ev_spawn1 = NPCSpawnerEvent(player=player, tile=tile_a, npc_cls='Slime', count=1)
    ev_spawn2 = NPCSpawnerEvent(player=player, tile=tile_a, npc_cls='CaveBat', count=1)

    # Create a simple mock event (not a spawner)
    class DummyEvent(Event):
        def __init__(self, player, tile):
            super().__init__(name="DummyEvent", player=player, tile=tile, repeat=False, params=None)
            self.was_processed = False
        
        def check_conditions(self):
            self.was_processed = True
            self.pass_conditions_to_process()

    ev_dummy = DummyEvent(player=player, tile=tile_a)

    tile_a.events_here.append(ev_spawn1)
    tile_a.events_here.append(ev_dummy)
    tile_a.events_here.append(ev_spawn2)

    # Evaluate events
    tile_a.evaluate_events()

    # Spawners should have fired and been removed
    assert len(tile_a.npcs_here) == 2, f"Expected 2 NPCs, got {len(tile_a.npcs_here)}"
    assert ev_spawn1 not in tile_a.events_here, "First spawner should be removed"
    assert ev_spawn2 not in tile_a.events_here, "Second spawner should be removed"
    # Dummy event should also be removed (one-shot by default)
    assert ev_dummy not in tile_a.events_here, "Dummy event should be removed"
    assert ev_dummy.was_processed, "Dummy event should have been processed"


if __name__ == '__main__':
    pytest.main([__file__])

