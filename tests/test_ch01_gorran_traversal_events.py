"""
Unit tests for the Chapter 1 Gorran traversal beats in Verdette Caverns.

These are three unguarded, one-shot tile-entry events whose entire job is to
characterise Gorran through escalating body language on the way to the Rumbler
fight: he slows at the junction, lingers at the markings, and stops dead in the
dark chamber. Only the last one leaves a mark on world state.

The tests assert the narration the sink actually receives, the story-flag
transition, and the one-shot retirement — counting print calls would pass just
as happily against three copies of the same paragraph.
"""

import sys
from unittest.mock import Mock, patch, MagicMock

import pytest

# Stub tkinter before any game engine imports — not available in headless CI.
if 'tkinter' not in sys.modules:
    sys.modules['tkinter'] = MagicMock()
    sys.modules['tkinter.ttk'] = MagicMock()
    sys.modules['tkinter.font'] = MagicMock()


from src.narration import capture_narration
from src.tiles import MapTile
from src.story.ch01 import (
    Ch01GorranCautionJunction,
    Ch01GorranMarkings,
    Ch01GorranDarkChamber,
)

# (event class, event name, opening phrase, closing phrase)
TRAVERSAL_EVENTS = [
    (
        Ch01GorranCautionJunction,
        "Ch01_Gorran_Caution_Junction",
        "Gorran slows as he enters the junction",
        "he lowers it and moves forward, unhurried",
    ),
    (
        Ch01GorranMarkings,
        "Ch01_Gorran_Markings",
        "Gorran pauses at the crystal",
        "his eyes stay ahead",
    ),
    (
        Ch01GorranDarkChamber,
        "Ch01_Gorran_Dark_Chamber",
        "Gorran stops entirely",
        "he heard it first",
    ),
]

_IDS = [cls.__name__ for cls, _n, _o, _c in TRAVERSAL_EVENTS]


def make_player_and_tile():
    player = Mock()
    player.combat_list = []
    player.combat_list_allies = [player]
    player.combat_events = []
    player.in_combat = False
    player.universe.story = {}
    tile = Mock(spec=MapTile)
    tile.events_here = []
    return player, tile


def _run(event):
    """Process the event with sleeps stubbed; return (messages, sleep_seconds)."""
    slept = []
    with capture_narration() as msgs:
        with patch('src.story.ch01.time.sleep', side_effect=slept.append):
            event.process()
    return msgs, slept


@pytest.mark.parametrize(
    "event_cls, event_name, opening, closing", TRAVERSAL_EVENTS, ids=_IDS
)
class TestGorranTraversalBeats:
    def test_is_a_one_shot_unguarded_tile_entry_event(
        self, event_cls, event_name, opening, closing
    ):
        """No guard condition, and it retires from the tile once it has run."""
        player, tile = make_player_and_tile()
        ev = event_cls(player=player, tile=tile)
        tile.events_here.append(ev)

        assert ev.name == event_name
        assert ev.repeat is False

        with patch('src.story.ch01.time.sleep'):
            ev.check_conditions()

        # check_conditions fires straight through to process(), and because the
        # event neither repeats nor needs input it removes itself afterwards —
        # re-firing Gorran's silent warning on every re-entry would flatten the
        # escalation these three beats exist to build.
        assert ev not in tile.events_here

    def test_narrates_its_beat_through_the_sink(
        self, event_cls, event_name, opening, closing
    ):
        player, tile = make_player_and_tile()
        ev = event_cls(player=player, tile=tile)

        msgs, _slept = _run(ev)

        assert len(msgs) == 2, "each beat is an action line followed by a resolution"
        assert opening in msgs[0]["text"]
        assert closing in msgs[1]["text"]
        # Gorran's wordless cues share the cyan "companion" colour.
        assert all(m["color"] == "cyan" for m in msgs)
        assert all(m["type"] == "narration" for m in msgs)
        # These beats are body language: Gorran never speaks here.
        assert not any("speaker" in m for m in msgs)


def test_only_the_dark_chamber_records_world_state():
    """The dark chamber is the one beat with a consequence beyond its prose."""
    flags = {}
    for event_cls, _name, _opening, _closing in TRAVERSAL_EVENTS:
        player, tile = make_player_and_tile()
        ev = event_cls(player=player, tile=tile)
        _run(ev)
        flags[event_cls.__name__] = dict(player.universe.story)

    assert flags["Ch01GorranCautionJunction"] == {}
    assert flags["Ch01GorranMarkings"] == {}
    assert flags["Ch01GorranDarkChamber"] == {"gorran_dark_chamber_seen": "1"}


def test_the_dark_chamber_holds_the_longest_silence():
    """Pacing is the beat's payload: the threat signal must land the slowest.

    Each event's pauses are asserted relative to the others rather than against
    a magic constant, so retuning the scene as a whole stays legal but flipping
    the escalation does not.
    """
    totals = {}
    for event_cls, _name, _opening, _closing in TRAVERSAL_EVENTS:
        player, tile = make_player_and_tile()
        _msgs, slept = _run(event_cls(player=player, tile=tile))
        totals[event_cls.__name__] = sum(slept)

    assert totals["Ch01GorranDarkChamber"] > totals["Ch01GorranMarkings"]
    assert totals["Ch01GorranMarkings"] > totals["Ch01GorranCautionJunction"]
