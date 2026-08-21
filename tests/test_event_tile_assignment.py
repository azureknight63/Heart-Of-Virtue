import pytest

from src.universe import Universe
from src.player import Player


def test_all_events_have_tile_reference():
    """Every event deserialized from a map JSON must point back at its own tile.

    Events reach for ``self.tile`` to spawn NPCs, unblock exits and remove
    themselves. A wrong (or missing) back-reference means the effect lands on
    the wrong room — or crashes with AttributeError on None.
    """
    player = Player()
    univ = Universe()
    univ.build(player)
    # Basic sanity: at least one map loaded
    assert len(univ.maps) > 0, "No maps loaded; test precondition failed."
    problems = []
    checked = 0
    for game_map in univ.maps:
        for coord, tile in game_map.items():
            if not isinstance(coord, tuple):
                continue
            if tile is None:
                continue
            for ev in getattr(tile, 'events_here', []):
                checked += 1
                if not hasattr(ev, 'tile') or ev.tile is not tile:
                    problems.append((game_map.get('name'), coord, ev.__class__.__name__, getattr(ev, 'tile', None)))
    assert not problems, f"Events missing/incorrect tile reference: {problems}"
    # Guard against the check passing vacuously: a build that loaded no events
    # at all (or stopped attaching them to tiles) would otherwise look clean.
    assert checked > 0, "No tile events found across any map — nothing was checked."
