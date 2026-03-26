"""
Structural tests for verdette-caverns.json.

Guards against regressions in the map's event placement:
- Tile (2,1) must NOT have an NPCSpawnerEvent (duplicate Gorran bug fix)
- Tile (4,3) must have Ch01GorranCautionJunction
- Tile (5,6) must have Ch01GorranMarkings
- Tile (7,6) must have Ch01GorranDarkChamber
"""

import json
import pytest
from pathlib import Path

MAP_PATH = Path(__file__).parent.parent / 'src' / 'resources' / 'maps' / 'verdette-caverns.json'


@pytest.fixture(scope='module')
def map_data():
    with open(MAP_PATH) as f:
        return json.load(f)


def get_event_classes(tile):
    return [ev.get('__class__') for ev in tile.get('events', [])]


class TestSpawnerRemoval:
    def test_tile_2_1_has_no_npc_spawner(self, map_data):
        """Regression guard: duplicate Gorran bug was caused by NPCSpawnerEvent at (2,1)."""
        tile = map_data.get('(2, 1)', {})
        classes = get_event_classes(tile)
        assert 'NPCSpawnerEvent' not in classes, (
            "Tile (2,1) must not have an NPCSpawnerEvent — "
            "recall_friends() already moves the ally Gorran there and "
            "a spawner would create a second non-ally Gorran."
        )


class TestGorranTraversalEvents:
    def test_tile_4_3_has_caution_junction(self, map_data):
        tile = map_data.get('(4, 3)', {})
        classes = get_event_classes(tile)
        assert 'Ch01GorranCautionJunction' in classes, (
            f"Tile (4,3) must have Ch01GorranCautionJunction. Found: {classes}"
        )

    def test_tile_5_6_has_markings(self, map_data):
        tile = map_data.get('(5, 6)', {})
        classes = get_event_classes(tile)
        assert 'Ch01GorranMarkings' in classes, (
            f"Tile (5,6) must have Ch01GorranMarkings. Found: {classes}"
        )

    def test_tile_7_6_has_dark_chamber(self, map_data):
        tile = map_data.get('(7, 6)', {})
        classes = get_event_classes(tile)
        assert 'Ch01GorranDarkChamber' in classes, (
            f"Tile (7,6) must have Ch01GorranDarkChamber. Found: {classes}"
        )

    def test_gorran_events_are_not_repeating(self, map_data):
        """All three traversal events should fire once only (repeat=False)."""
        event_tiles = {
            '(4, 3)': 'Ch01GorranCautionJunction',
            '(5, 6)': 'Ch01GorranMarkings',
            '(7, 6)': 'Ch01GorranDarkChamber',
        }
        for coord, cls_name in event_tiles.items():
            tile = map_data.get(coord, {})
            for ev in tile.get('events', []):
                if ev.get('__class__') == cls_name:
                    props = ev.get('props', {})
                    repeat = props.get('repeat', False)
                    assert repeat is False, (
                        f"{cls_name} at {coord} has repeat={repeat}; expected False."
                    )
