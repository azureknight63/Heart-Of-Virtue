"""
Unit tests for Chapter 1 Gorran traversal events in Verdette Caverns.

Verifies that each event class instantiates correctly, fires immediately on
tile entry (no guard conditions), and executes its process() without error.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Stub tkinter before any game engine imports — not available in headless CI.
if 'tkinter' not in sys.modules:
    sys.modules['tkinter'] = MagicMock()
    sys.modules['tkinter.ttk'] = MagicMock()
    sys.modules['tkinter.font'] = MagicMock()

src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from tiles import MapTile
from story.ch01 import (
    Ch01GorranCautionJunction,
    Ch01GorranMarkings,
    Ch01GorranDarkChamber,
)


def make_player_and_tile():
    player = Mock()
    player.combat_list = []
    player.combat_list_allies = [player]
    player.in_combat = False
    player.universe.story = {}
    tile = Mock(spec=MapTile)
    tile.events_here = []
    return player, tile


class TestCh01GorranCautionJunction:
    def test_instantiates(self):
        player, tile = make_player_and_tile()
        ev = Ch01GorranCautionJunction(player=player, tile=tile)
        assert ev is not None
        assert ev.name == 'Ch01_Gorran_Caution_Junction'
        assert ev.repeat is False

    def test_check_conditions_fires_immediately(self):
        """Event has no guard — fires unconditionally on tile entry."""
        player, tile = make_player_and_tile()
        ev = Ch01GorranCautionJunction(player=player, tile=tile)
        with patch.object(ev, 'pass_conditions_to_process') as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_process_executes_without_error(self):
        player, tile = make_player_and_tile()
        ev = Ch01GorranCautionJunction(player=player, tile=tile)
        with patch('story.ch01.cprint'), patch('story.ch01.time.sleep'):
            ev.process()  # should not raise

    def test_process_produces_output(self):
        """process() prints at least two lines of narrative."""
        player, tile = make_player_and_tile()
        ev = Ch01GorranCautionJunction(player=player, tile=tile)
        call_count = 0
        def count_print(*args, **kwargs):
            nonlocal call_count
            call_count += 1
        with patch('story.ch01.cprint', side_effect=count_print), \
             patch('story.ch01.time.sleep'):
            ev.process()
        assert call_count >= 2


class TestCh01GorranMarkings:
    def test_instantiates(self):
        player, tile = make_player_and_tile()
        ev = Ch01GorranMarkings(player=player, tile=tile)
        assert ev is not None
        assert ev.name == 'Ch01_Gorran_Markings'
        assert ev.repeat is False

    def test_check_conditions_fires_immediately(self):
        player, tile = make_player_and_tile()
        ev = Ch01GorranMarkings(player=player, tile=tile)
        with patch.object(ev, 'pass_conditions_to_process') as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_process_executes_without_error(self):
        player, tile = make_player_and_tile()
        ev = Ch01GorranMarkings(player=player, tile=tile)
        with patch('story.ch01.cprint'), patch('story.ch01.time.sleep'):
            ev.process()

    def test_process_produces_output(self):
        player, tile = make_player_and_tile()
        ev = Ch01GorranMarkings(player=player, tile=tile)
        call_count = 0
        def count_print(*args, **kwargs):
            nonlocal call_count
            call_count += 1
        with patch('story.ch01.cprint', side_effect=count_print), \
             patch('story.ch01.time.sleep'):
            ev.process()
        assert call_count >= 2


class TestCh01GorranDarkChamber:
    def test_instantiates(self):
        player, tile = make_player_and_tile()
        ev = Ch01GorranDarkChamber(player=player, tile=tile)
        assert ev is not None
        assert ev.name == 'Ch01_Gorran_Dark_Chamber'
        assert ev.repeat is False

    def test_check_conditions_fires_immediately(self):
        player, tile = make_player_and_tile()
        ev = Ch01GorranDarkChamber(player=player, tile=tile)
        with patch.object(ev, 'pass_conditions_to_process') as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_process_executes_without_error(self):
        player, tile = make_player_and_tile()
        ev = Ch01GorranDarkChamber(player=player, tile=tile)
        with patch('story.ch01.cprint'), patch('story.ch01.time.sleep'):
            ev.process()

    def test_process_produces_output(self):
        """Dark chamber is the most pronounced beat — expect at least 2 lines."""
        player, tile = make_player_and_tile()
        ev = Ch01GorranDarkChamber(player=player, tile=tile)
        call_count = 0
        def count_print(*args, **kwargs):
            nonlocal call_count
            call_count += 1
        with patch('story.ch01.cprint', side_effect=count_print), \
             patch('story.ch01.time.sleep'):
            ev.process()
        assert call_count >= 2

    def test_process_pauses_longest(self):
        """Dark chamber event should have the longest total sleep — it's the threat signal."""
        player, tile = make_player_and_tile()
        ev = Ch01GorranDarkChamber(player=player, tile=tile)
        total_sleep = 0
        def capture_sleep(t):
            nonlocal total_sleep
            total_sleep += t
        with patch('story.ch01.cprint'), patch('story.ch01.time.sleep', side_effect=capture_sleep):
            ev.process()
        assert total_sleep >= 3.0, f"Dark chamber should pause >= 3s total, got {total_sleep}"
