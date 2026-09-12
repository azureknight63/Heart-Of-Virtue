"""``story_gates``, ``set_story_gate``, ``gate_is_set`` and the ``Event``
helpers built on them.

Story events read the gates on nearly every ``check_conditions`` call and
had each grown their own ``getattr(getattr(self.player, "universe", None),
"story", {})`` chain; ``Passageway.end_demo`` had the same chain against a
bare ``player``. This pins one contract for reading, writing and retiring on
a gate, so every site that adopts the helpers can rely on one behaviour.
"""

from types import SimpleNamespace

import pytest

from src.events import GATE_SET, Event, gate_is_set, set_story_gate, story_gates

_GATE = "beat_done"


def _event(player, tile=None):
    return Event(name="probe", player=player, tile=tile)


def _player_with(story):
    return SimpleNamespace(universe=SimpleNamespace(story=story))


def _event_on_tile(story):
    """An event standing on a tile that lists it -- the shape retiring acts
    on; returns ``(event, tile)``."""
    tile = SimpleNamespace(events_here=[])
    event = _event(_player_with(story), tile)
    tile.events_here.append(event)
    return event, tile


#: Players with no story dict to read or write into: no universe, no story
#: yet, no player at all -- and a story that is not a dict, which a legacy or
#: tampered save can carry. The list story holds the gate's own key, so a
#: naive ``key in story`` check would read the gate as set there.
_NOWHERE_PLAYERS = pytest.mark.parametrize(
    "player",
    [
        SimpleNamespace(),
        _player_with(None),
        None,
        _player_with([_GATE]),
        _player_with("not a dict"),
    ],
    ids=["no universe", "no story", "no player", "a list story", "a string story"],
)

#: Stories in which the gate is not set: absent, or holding something other
#: than ``GATE_SET`` -- including the truthy int and bool a truthiness check
#: would read as set.
_UNSET_STORIES = pytest.mark.parametrize(
    "story",
    [{}, {_GATE: "0"}, {_GATE: 1}, {_GATE: True}],
    ids=["unset", "zero", "int", "bool"],
)


class TestStoryGates:
    @pytest.mark.parametrize(
        "story", [{}, {"gorran_first": GATE_SET}], ids=["empty", "populated"]
    )
    def test_returns_the_universe_story_dict_itself(self, story):
        # Identity, not equality -- and on an EMPTY dict too, where a
        # truthiness fallback (`or {}`) would hand back a throwaway, and a
        # caller holding it would never see the gate written a moment later.
        player = _player_with(story)

        assert story_gates(player) is story
        assert _event(player).story_gates() is story

    @_NOWHERE_PLAYERS
    def test_reads_an_empty_dict_when_there_is_no_story_dict(self, player):
        assert story_gates(player) == {}
        assert _event(player).story_gates() == {}


class TestSetStoryGate:
    def test_writes_the_gate_into_the_real_story_dict(self):
        story = {}

        assert set_story_gate(_player_with(story), _GATE) is True
        assert story == {_GATE: GATE_SET}

    def test_writes_the_value_it_is_given(self):
        story = {}

        set_story_gate(_player_with(story), "chain", "0")

        assert story == {"chain": "0"}

    def test_the_event_method_writes_for_its_own_player(self):
        story = {}

        assert _event(_player_with(story)).set_story_gate(_GATE) is True
        assert story == {_GATE: GATE_SET}

    @_NOWHERE_PLAYERS
    def test_skips_the_write_when_there_is_nowhere_to_record_it(self, player):
        assert set_story_gate(player, _GATE) is False
        assert _event(player).set_story_gate(_GATE) is False


class TestGateIsSet:
    def test_a_set_gate_reads_as_set(self):
        player = _player_with({_GATE: GATE_SET})

        assert gate_is_set(player, _GATE) is True
        assert _event(player).gate_is_set(_GATE) is True

    @_UNSET_STORIES
    def test_only_the_set_value_counts(self, story):
        player = _player_with(story)

        assert gate_is_set(player, _GATE) is False
        assert _event(player).gate_is_set(_GATE) is False

    @_NOWHERE_PLAYERS
    def test_no_gate_is_set_without_a_story_dict(self, player):
        assert gate_is_set(player, _GATE) is False
        assert _event(player).gate_is_set(_GATE) is False


class TestRetireIfGateSet:
    def test_retires_the_event_once_the_gate_is_set(self):
        event, tile = _event_on_tile({_GATE: GATE_SET})

        assert event.retire_if_gate_set(_GATE) is True
        assert tile.events_here == []

    @_UNSET_STORIES
    def test_leaves_the_event_alone_until_the_gate_is_set(self, story):
        event, tile = _event_on_tile(story)

        assert event.retire_if_gate_set(_GATE) is False
        assert tile.events_here == [event]

    def test_answers_true_for_an_event_already_off_its_tile(self):
        event, tile = _event_on_tile({_GATE: GATE_SET})
        tile.events_here.clear()

        assert event.retire_if_gate_set(_GATE) is True

    def test_tolerates_an_event_with_no_tile(self):
        event = _event(_player_with({_GATE: GATE_SET}))

        assert event.retire_if_gate_set(_GATE) is True


class _Beat(Event):
    """A one-shot story beat that relies on ``Event``'s default check."""

    GATE_KEY = _GATE

    def __init__(self, story):
        super().__init__(name="beat", player=_player_with(story), tile=SimpleNamespace(events_here=[]))
        self.tile.events_here.append(self)
        self.ran = False

    def process(self):
        self.ran = True


class TestAOneShotBeat:
    def test_runs_while_its_gate_is_unset(self):
        beat = _Beat({})

        beat.check_conditions()

        assert beat.ran is True

    def test_retires_instead_of_running_once_its_gate_is_set(self):
        beat = _Beat({_GATE: GATE_SET})

        beat.check_conditions()

        assert beat.ran is False
        assert beat.tile.events_here == []

    def test_retire_if_gate_set_reads_its_own_gate_by_default(self):
        assert _Beat({_GATE: GATE_SET}).retire_if_gate_set() is True
        assert _Beat({}).retire_if_gate_set() is False

    def test_an_event_that_is_not_a_beat_runs_whatever_the_story_holds(self):
        event, _tile = _event_on_tile({_GATE: GATE_SET})
        ran = []
        event.process = lambda: ran.append(True)

        event.check_conditions()

        assert ran == [True]
