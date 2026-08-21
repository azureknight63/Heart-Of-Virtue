"""Regression tests for trigger_tile_events chained-event processing.

Some events queue a follow-up event onto tile.events_here as a side effect of
their own check_conditions()/process() (e.g. ch02's AfterDefeatingKingSlime
queuing Ch02KingSlimeMemoryFlash once the King Slime is dead). Before the fix,
trigger_tile_events took a plain `for event in list(tile.events_here)`
snapshot before iterating, so a follow-up event appended mid-pass was invisible
to that same call. Combined with GameService.get_combat_status's one-shot
`_post_combat_tile_events_fired` guard (which only calls trigger_tile_events
once per combat), the follow-up event was stranded in tile.events_here
indefinitely — reproducing the real bug report: after defeating King Slime,
the mineral fragment appeared in inventory with no finger-cutting memory-flash
scene and no clear indication of what to do next.

trigger_tile_events now processes newly queued events within the same pass
(a fixed-point loop keyed by object identity), so the chained event fires
immediately instead of waiting for a later, possibly-never-happening tile
visit. These tests exercise the general mechanism with lightweight fake
events rather than the full ch02 narrative (which needs a much heavier
player/universe/map fixture) — see tests/test_ch02_memory_flash_guards.py and
tests/test_ch02_after_king_slime_return_coverage.py for ch02-specific
coverage of Ch02KingSlimeMemoryFlash itself.
"""

import pytest
from unittest.mock import MagicMock



@pytest.fixture
def player():
    p = MagicMock()
    p.in_combat = False
    return p


class _FollowUpEvent:
    """Mirrors Ch02KingSlimeMemoryFlash: a plain follow-up event that a prior
    event queues onto tile.events_here as a side effect of its own
    check_conditions()."""

    def __init__(self, name="FollowUpEvent"):
        self.name = name
        self.needs_input = False
        self.completed = False
        self.player = None
        self.tile = None
        self.fired = False

    def check_conditions(self):
        self.fired = True


class _ChainingEvent:
    """Mirrors AfterDefeatingKingSlime: appends a follow-up event to
    tile.events_here as a side effect of check_conditions(), then removes
    itself (as AfterDefeatingKingSlime does via tile.remove_event)."""

    def __init__(self, tile, follow_up, name="ChainingEvent"):
        self.name = name
        self.needs_input = False
        self.completed = False
        self.player = None
        self.tile = tile
        self.fired = False
        self._follow_up = follow_up

    def check_conditions(self):
        self.fired = True
        self.tile.events_here.append(self._follow_up)
        self.tile.events_here.remove(self)


def test_event_queued_mid_pass_fires_in_same_call(game_service, player):
    """A follow-up event appended during another event's check_conditions()
    must be processed within the same trigger_tile_events() call."""
    tile = MagicMock()
    follow_up = _FollowUpEvent("Ch02KingSlimeMemoryFlash")
    chaining_event = _ChainingEvent(tile, follow_up, name="AfterDefeatingKingSlime")
    tile.events_here = [chaining_event]

    game_service.trigger_tile_events(player, tile)

    assert chaining_event.fired
    assert follow_up.fired, (
        "follow-up event queued mid-pass was not processed in the same call "
        "— this is the King Slime memory-flash orphaning bug"
    )


def test_event_queued_mid_pass_is_not_processed_twice(game_service, player):
    """The newly queued event fires exactly once per call, even though it's
    discovered via a re-scan of tile.events_here after each processed event."""
    tile = MagicMock()
    follow_up = _FollowUpEvent()
    call_count = {"n": 0}
    original_check = follow_up.check_conditions

    def counting_check():
        call_count["n"] += 1
        original_check()

    follow_up.check_conditions = counting_check
    chaining_event = _ChainingEvent(tile, follow_up)
    tile.events_here = [chaining_event]

    game_service.trigger_tile_events(player, tile)

    assert call_count["n"] == 1


def test_chain_of_three_events_all_fire_in_one_pass(game_service, player):
    """A -> queues B -> queues C: all three must fire in a single call."""
    tile = MagicMock()

    event_c = _FollowUpEvent("C")

    class _BQueuesC(_FollowUpEvent):
        def check_conditions(self):
            super().check_conditions()
            tile.events_here.append(event_c)

    event_b = _BQueuesC("B")
    chaining_event = _ChainingEvent(tile, event_b, name="A")
    tile.events_here = [chaining_event]

    game_service.trigger_tile_events(player, tile)

    assert chaining_event.fired
    assert event_b.fired
    assert event_c.fired


def test_unrelated_events_in_original_snapshot_still_all_fire(game_service, player):
    """The fixed-point loop must not skip or reorder events that were already
    present in the original snapshot alongside a chaining event."""
    tile = MagicMock()
    follow_up = _FollowUpEvent()
    chaining_event = _ChainingEvent(tile, follow_up)
    sibling = _FollowUpEvent("Sibling")
    tile.events_here = [chaining_event, sibling]

    game_service.trigger_tile_events(player, tile)

    assert chaining_event.fired
    assert sibling.fired
    assert follow_up.fired


def test_runaway_generative_chain_is_capped(game_service, player):
    """A misbehaving event that keeps generating fresh instances of itself
    (rather than firing once and removing itself, as a correctly-guarded
    event does) must not hang trigger_tile_events forever."""
    tile = MagicMock()
    tile.events_here = []
    spawn_count = {"n": 0}

    class _GenerativeEvent:
        """Deliberately buggy: every check_conditions() queues ANOTHER new
        instance, simulating a missing needs_input/story-flag guard."""

        def __init__(self):
            self.name = "GenerativeEvent"
            self.needs_input = False
            self.completed = False
            self.player = None
            self.tile = tile

        def check_conditions(self):
            spawn_count["n"] += 1
            tile.events_here.append(_GenerativeEvent())

    tile.events_here.append(_GenerativeEvent())

    result = game_service.trigger_tile_events(player, tile)

    assert isinstance(result, list)
    # Bounded well below "ran forever" — the cap is max(50, initial_len * 10);
    # initial_len is 1 here, so the floor of 50 applies.
    assert spawn_count["n"] <= 50
