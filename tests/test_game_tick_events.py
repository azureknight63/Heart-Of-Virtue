import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
# Also add project root so imports like 'src.moves' succeed when modules import 'src.*'
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from universe import Universe


class DummyPlayer:
    def __init__(self):
        self.refresh_called = 0

    def refresh_merchants(self):
        self.refresh_called += 1


def test_game_tick_events_noop_on_zero():
    u = Universe()
    player = DummyPlayer()
    u.player = player
    u.game_tick = 0

    u.game_tick_events()

    assert player.refresh_called == 0


def test_game_tick_events_noop_on_non_multiple_of_1000():
    u = Universe()
    player = DummyPlayer()
    u.player = player
    u.game_tick = 999

    u.game_tick_events()

    assert player.refresh_called == 0


@pytest.mark.parametrize("tick", [1000, 2000, 3000])
def test_game_tick_events_refresh_on_multiples_of_1000(tick):
    u = Universe()
    player = DummyPlayer()
    u.player = player
    u.game_tick = tick

    u.game_tick_events()

    assert player.refresh_called == 1
