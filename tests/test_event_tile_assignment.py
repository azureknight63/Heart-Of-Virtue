import pytest

from src.universe import Universe
from src.player import Player


def test_all_events_have_tile_reference():
    player = Player()
    univ = Universe()
    univ.build(player)
    # Basic sanity: at least one map loaded
    assert len(univ.maps) > 0, "No maps loaded; test precondition failed."
    problems = []
    for game_map in univ.maps:
        for coord, tile in game_map.items():
            if not isinstance(coord, tuple):
                continue
            if tile is None:
                continue
            for ev in getattr(tile, 'events_here', []):
                if not hasattr(ev, 'tile') or ev.tile is not tile:
                    problems.append((game_map.get('name'), coord, ev.__class__.__name__, getattr(ev, 'tile', None)))
    assert not problems, f"Events missing/incorrect tile reference: {problems}"

