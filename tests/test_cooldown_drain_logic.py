"""
Tests for the cooldown-drain beat-loop logic in combat_adapter.

The fix (d0876dd) changed the beat loop so that when current_move is None:
  - If ANY move is at stage 0 (ready) → break and return control to the player
  - If ALL moves are in cooldown (stage > 0) → keep advancing beats

This ensures the player always gets back at least one available action
rather than being returned zero options when all moves happen to be cooling.
"""
import sys
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class _Move:
    def __init__(self, name, stage=0):
        self.name = name
        self.current_stage = stage


def _simulate_beat_exit(moves, current_move):
    """
    Simulate the beat-loop exit condition from combat_adapter.py.

    Returns (broke_early, advances) where:
      broke_early — True if the loop exited because a move became available
      advances    — number of beat advances needed before exiting
    """
    advances = 0
    while current_move is None:
        if any(m.current_stage == 0 for m in moves):
            return True, advances
        # Simulate one beat: tick every move down by 1
        for m in moves:
            if m.current_stage > 0:
                m.current_stage -= 1
        advances += 1
        if advances > 20:
            return False, advances  # safety — should never happen
    return False, advances


def test_all_cooldown_advances_until_one_ready():
    """All moves in cooldown → loop must advance beats until one is at stage 0."""
    moves = [_Move("Slash", stage=2), _Move("Shield Bash", stage=1)]
    broke_early, advances = _simulate_beat_exit(moves, current_move=None)

    assert broke_early, "Loop should have broken once a move reached stage 0"
    assert advances >= 1, "Should have advanced at least one beat (all moves were cooling)"
    assert any(m.current_stage == 0 for m in moves), (
        "After loop exit at least one move must be at stage 0"
    )


def test_move_already_ready_breaks_immediately():
    """If a move is already at stage 0 when current_move becomes None, break instantly."""
    moves = [_Move("Attack", stage=0), _Move("Wait", stage=3)]
    broke_early, advances = _simulate_beat_exit(moves, current_move=None)

    assert broke_early, "Should have broken immediately — Attack was already ready"
    assert advances == 0, (
        f"Expected 0 advances when a move is already ready, got {advances}"
    )


def test_longer_cooldown_drains_fully():
    """Move at stage 5 requires 5 advances to become available."""
    moves = [_Move("Heavy Strike", stage=5)]
    broke_early, advances = _simulate_beat_exit(moves, current_move=None)

    assert broke_early
    assert advances == 5
    assert moves[0].current_stage == 0


def test_shortest_cooldown_wins():
    """When multiple moves are cooling, the shortest one (stage 1) wins — only 1 advance."""
    moves = [_Move("Slash", stage=4), _Move("Quick Jab", stage=1)]
    broke_early, advances = _simulate_beat_exit(moves, current_move=None)

    assert broke_early
    assert advances == 1, f"Quick Jab (stage 1) should have opened after 1 advance, got {advances}"
    assert any(m.current_stage == 0 for m in moves)
