"""Regression tests for Move.advance() stage condition fix.

Root cause (fixed): advance() used `self.current_stage == 3` to check whether an
in-flight move should keep ticking.  This meant moves in stage 1 (execution) or
stage 2 (recovery) would silently stall if another move replaced them as
user.current_move before they finished.

Fix (moves.py, line ~119): changed `self.current_stage == 3` → `self.current_stage > 0`
so any move that has been cast (stage > 0) continues advancing until cooldown ends.

These tests verify the invariant in isolation — no Player/NPC required.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from moves import Move


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_move(stage, beats):
    """Construct a minimal base Move at the given stage with beats_left beats."""
    return Move(
        name="TestMove",
        description="A test move",
        xp_gain=0,
        current_stage=stage,
        beats_left=beats,
        stage_announce=["", "", "", ""],
        target=None,
        user=None,
        stage_beat=[0, 2, 1, 1],   # prep=instant, execution=2 beats, recovery=1, cooldown=1
        targeted=False,
    )


class _User:
    """Minimal user stub — only needs current_move."""
    def __init__(self, current_move=None):
        self.current_move = current_move


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMoveAdvanceStageCondition:
    """Regression suite: move.advance() must tick moves in stage 1/2 even when
    user.current_move has moved on to a different ability."""

    def test_stage1_advances_when_not_current_move(self):
        """A move in execution (stage 1) with beats remaining must tick down
        even when it is no longer the user's current_move."""
        move = _make_move(stage=1, beats=3)
        user = _User(current_move=None)   # move was replaced mid-execution

        move.advance(user)

        assert move.beats_left == 2, (
            "beats_left should have decreased from 3 to 2; "
            "old code with `== 3` would have left it at 3."
        )

    def test_stage2_advances_when_not_current_move(self):
        """A move in recovery (stage 2) with beats remaining must tick down
        even when it is no longer the user's current_move."""
        move = _make_move(stage=2, beats=1)
        user = _User(current_move=None)

        move.advance(user)

        assert move.beats_left == 0, (
            "beats_left should have decreased from 1 to 0; "
            "old code with `== 3` would have left it at 1."
        )

    def test_stage3_advances_when_not_current_move(self):
        """A move in cooldown (stage 3) must still tick down — this was
        already true under the old condition and must continue to work."""
        move = _make_move(stage=3, beats=1)
        user = _User(current_move=None)

        move.advance(user)

        assert move.beats_left == 0, (
            "Cooldown stage should advance regardless of current_move."
        )

    def test_stage0_does_not_advance_when_not_current_move(self):
        """A move that hasn't been cast yet (stage 0) must NOT advance
        if user.current_move points to something else.
        stage 0 is the idle/prep state before cast() is called."""
        move = _make_move(stage=0, beats=2)
        user = _User(current_move=None)   # this move was never cast

        move.advance(user)

        assert move.beats_left == 2, (
            "An uncast move (stage 0) should not advance when it is "
            "not user.current_move — no regression here."
        )

    def test_stage0_advances_when_is_current_move(self):
        """Stage 0 does advance when the move IS user.current_move
        (normal prep-stage tick)."""
        move = _make_move(stage=0, beats=2)
        user = _User(current_move=move)

        move.advance(user)

        assert move.beats_left == 1
