"""Additional coverage for src/npc_ai_config.py — closes gaps left by
tests/test_npc_ai_config.py: the distance-range parse-exception fallback,
should_attempt_flank's early-return guards, should_attempt_retreat's missing
health-attribute guard, get_flank_position_angle, calculate_retreat_priority's
missing health-attribute guard, and get_weighted_move_bonus's flank-range
inner branch.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.npc_ai_config import NPCAIConfig  # type: ignore
from src.config_manager import GameConfig  # type: ignore
from src.player import Player  # type: ignore
from src.npc import NPC  # type: ignore


def _npc():
    return NPC(
        name="TestFoe", description="d", damage=5, aggro=True, exp_award=1, maxhp=40
    )


def test_get_flanking_distance_range_malformed_string_falls_back_to_default():
    player = Player()
    config = GameConfig()
    config.npc_flanking_distance_range = "not-a-valid-range"
    player.game_config = config
    ai_config = NPCAIConfig(player)

    assert ai_config.get_flanking_distance_range() == (20.0, 40.0)


def test_get_flanking_distance_range_non_numeric_parts_falls_back_to_default():
    """Two "to"-separated parts that aren't valid floats raise ValueError
    inside the try block, exercising the except-and-fall-through path
    (as opposed to the single-part case above, which never enters the
    try's float() calls at all)."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_distance_range = "abc to xyz"
    player.game_config = config
    ai_config = NPCAIConfig(player)

    assert ai_config.get_flanking_distance_range() == (20.0, 40.0)


def test_should_attempt_flank_false_without_npc():
    player = Player()
    ai_config = NPCAIConfig(player)
    assert ai_config.should_attempt_flank(None, [1, 2], ["enemy"]) is False


def test_should_attempt_flank_false_without_enemies():
    player = Player()
    ai_config = NPCAIConfig(player)
    npc = _npc()
    assert ai_config.should_attempt_flank(npc, [1, 2], []) is False


def test_should_attempt_flank_false_without_target():
    player = Player()
    ai_config = NPCAIConfig(player)
    npc = _npc()
    npc.target = None
    assert ai_config.should_attempt_flank(npc, [1, 2], ["enemy"]) is False


def test_should_attempt_flank_false_without_combat_proximity():
    player = Player()
    ai_config = NPCAIConfig(player)
    npc = _npc()
    npc.target = "enemy"
    if hasattr(npc, "combat_proximity"):
        del npc.combat_proximity
    assert ai_config.should_attempt_flank(npc, [1, 2], ["enemy"]) is False


def test_should_attempt_flank_false_when_distance_out_of_range():
    player = Player()
    config = GameConfig()
    config.npc_flanking_distance_range = "20 to 40"
    player.game_config = config
    ai_config = NPCAIConfig(player)
    npc = _npc()
    target = _npc()
    npc.target = target
    npc.combat_proximity = {target: 9999}
    assert ai_config.should_attempt_flank(npc, [1, 2], [target]) is False


def test_should_attempt_retreat_false_without_health_attrs():
    player = Player()
    ai_config = NPCAIConfig(player)

    class NoHealth:
        pass

    assert ai_config.should_attempt_retreat(NoHealth()) is False


def test_get_flank_position_angle_disabled_returns_none():
    player = Player()
    config = GameConfig()
    config.npc_flanking_enabled = False
    player.game_config = config
    ai_config = NPCAIConfig(player)
    npc = _npc()
    target = _npc()

    assert ai_config.get_flank_position_angle(npc, target) is None


def test_get_flank_position_angle_missing_attacker_or_target_returns_none():
    player = Player()
    ai_config = NPCAIConfig(player)
    npc = _npc()

    assert ai_config.get_flank_position_angle(None, npc) is None
    assert ai_config.get_flank_position_angle(npc, None) is None


def test_get_flank_position_angle_returns_ideal_angle():
    player = Player()
    ai_config = NPCAIConfig(player)
    npc = _npc()
    target = _npc()

    assert ai_config.get_flank_position_angle(npc, target, ignore_unit=None) == 90.0


def test_calculate_retreat_priority_false_without_health_attrs():
    player = Player()
    ai_config = NPCAIConfig(player)

    class NoHealth:
        pass

    assert ai_config.calculate_retreat_priority(NoHealth(), []) == 0.0


def test_get_weighted_move_bonus_flank_bonus_when_in_range():
    player = Player()
    config = GameConfig()
    config.npc_flanking_distance_range = "20 to 40"
    player.game_config = config
    ai_config = NPCAIConfig(player)

    npc = _npc()
    target = _npc()
    npc.target = target
    npc.combat_proximity = {target: 30}

    bonus = ai_config.get_weighted_move_bonus(npc, "advance")
    assert bonus == 2


def test_get_weighted_move_bonus_no_flank_bonus_when_out_of_range():
    player = Player()
    config = GameConfig()
    config.npc_flanking_distance_range = "20 to 40"
    player.game_config = config
    ai_config = NPCAIConfig(player)

    npc = _npc()
    target = _npc()
    npc.target = target
    npc.combat_proximity = {target: 999}

    bonus = ai_config.get_weighted_move_bonus(npc, "advance")
    assert bonus == 0
