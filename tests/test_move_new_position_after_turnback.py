"""``new_position`` disagrees with ``room`` when a tile-entry event moves the
player back (issue #689b).

``GameService.move_player`` builds ``new_position`` from the *requested* exit
tile before ``trigger_tile_events`` runs. ``EasternRoadTurnbackEvent``
(``src/story/ch03.py``) is exactly such an event: it fires on entry to the
eastern road and immediately teleports Jean back to the tile he came from. The
response's ``room`` (built from ``get_current_room`` after the event ran)
correctly reflects the turnback, but ``new_position`` still names the tile the
event un-did the arrival to -- a client trusting ``new_position`` would think
Jean is standing somewhere he was never left.
"""

from src.story.ch03 import EasternRoadTurnbackEvent
from tests._gs_fixtures import live_world


def test_new_position_matches_room_after_an_arrival_event_turns_the_player_back(
    game_service,
):
    player, game_map = live_world(coords=[(5, 4), (6, 4)], start=(5, 4))
    player.skip_dialog = True  # skip the narration/conversation branch

    destination = game_map[(6, 4)]
    destination.events_here = [
        EasternRoadTurnbackEvent(player, destination, repeat=True)
    ]

    result = game_service.move_player(player, "east")

    assert result["success"] is True
    assert (player.location_x, player.location_y) == (5, 4)
    assert result["room"]["description"] == game_map[(5, 4)].description
    assert result["new_position"] == {"x": 5, "y": 4}
