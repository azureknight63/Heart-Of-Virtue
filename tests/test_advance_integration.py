"""Integration test: an NPC closes with Advance and stops at striking distance.

What changed and why
--------------------
This file used to *simulate* the advance by hand -- it decremented
``combat_proximity`` itself (``npc.combat_proximity[player] -= 8``) between
``viable()`` checks and never called the move at all. So the only thing under
test was ``Advance.viable()`` at four distances, which
``tests/test_advance_viable.py`` already covers exhaustively; the "integration"
in the name was the test doing the engine's job for it. It also ``print``ed its
progress, which pytest swallows.

It now drives the real ``Advance.beat_update`` loop, so the distances asserted
below are the ones the engine actually produces.
"""

from unittest.mock import patch

from src.moves import Advance
from src.npc import NPC


def test_advance_move_integration():
    npc = NPC(name="Enemy", description="Test Enemy", damage=20, aggro=80, exp_award=50)
    player = NPC(
        name="Player",
        description="Test Player",
        damage=15,
        aggro=50,
        exp_award=0,
        friend=True,
    )
    assert npc.speed == 10 and player.speed == 10

    advance = Advance(npc)
    advance.target = player
    advance.current_stage = 1  # execute stage: beat_update actually moves

    # No coordinates -> the legacy proximity path.
    npc.combat_position = None
    player.combat_position = None
    npc.combat_proximity[player] = 15
    player.combat_proximity[npc] = 15
    assert advance.can_use_coordinates(npc) is False
    assert advance.viable() is True

    fatigue_before = npc.fatigue

    # randint(0, 30) pinned to 30, so each beat closes
    # min(3, max(1, (30 + speed 10 - target speed 10) // 10)) = 3.
    with patch("src.moves._movement.random.randint", return_value=30):
        distances = []
        for _ in range(5):
            advance.beat_update(npc)
            distances.append(npc.combat_proximity[player])

    # 15 -> 12 -> 9 -> 6 -> 3, then the final step is clamped at 1 rather than
    # running the target down to 0.
    assert distances == [12, 9, 6, 3, 1]
    # The target's own view of the distance is kept in step.
    assert player.combat_proximity[npc] == 1
    # One fatigue point per beat spent advancing.
    assert npc.fatigue == fatigue_before - 5 * advance.fatigue_per_beat
    # At striking distance the move retires itself.
    assert advance.viable() is False


def test_advance_fires_sentinels_vigil_at_most_once_per_use():
    """The spear punish triggers on entering range, not on every beat inside it."""
    npc = NPC(name="Enemy", description="Test Enemy", damage=20, aggro=80, exp_award=50)
    player = NPC(
        name="Player",
        description="Test Player",
        damage=15,
        aggro=50,
        exp_award=0,
        friend=True,
    )

    advance = Advance(npc)
    advance.target = player
    advance.current_stage = 1
    npc.combat_position = None
    player.combat_position = None
    npc.combat_proximity[player] = 10
    player.combat_proximity[npc] = 10

    with patch("src.moves._movement._apply_sentinels_vigil") as mock_vigil, patch(
        "src.moves._movement.random.randint", return_value=30
    ):
        for _ in range(5):
            advance.beat_update(npc)

    assert npc.combat_proximity[player] == 1
    assert mock_vigil.call_count == 1
    assert mock_vigil.call_args[0] == (npc, player)

    # Re-prepping the move rearms the punish for the next use.
    advance.prep(npc)
    assert advance._sentinels_vigil_triggered is False
