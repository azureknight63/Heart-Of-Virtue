"""Regression coverage for location-specific background music wiring."""

from pathlib import Path

import pytest

from src.api.services.game_service import GameService
from src.player import Player
from src.universe import Universe


_ROOT = Path(__file__).resolve().parents[1]
_MAPS = _ROOT / "src" / "resources" / "maps"


@pytest.mark.parametrize(
    "map_filename, coordinate, expected_track",
    [
        ("eastern-descent-jambos-tent.json", (2, 2), "jambos_tent"),
        ("grondia-jambos_shop.json", (2, 2), "jambos_tent"),
        ("eastern-descent-nomad-camp.json", (4, 3), "iron_and_oath"),
    ],
)
def test_real_location_map_resolves_its_bgm(map_filename, coordinate, expected_track):
    """The shipped location maps select the track intended for their shops."""
    player = Player()
    universe = Universe(player=player)
    universe._load_single_json_map(player, _MAPS / map_filename)
    game_map = universe.maps[-1]
    player.universe = universe
    player.map = game_map

    tile = game_map[coordinate]
    player.location_x, player.location_y = coordinate
    player.current_room = tile

    assert GameService().get_current_room(player)["bgm"] == expected_track
