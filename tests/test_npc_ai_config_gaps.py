"""Additional coverage for src/npc_ai_config.py — closes gaps left by
tests/test_npc_ai_config.py: the distance-range parse-exception fallback,
should_attempt_flank's early-return guards, should_attempt_retreat's missing
health-attribute guard, get_flank_position_angle, calculate_retreat_priority's
missing health-attribute guard, get_weighted_move_bonus's flank-range inner
branch, and AIDecisionValidator's None/missing-attribute guards plus the
moderate/high retreat-priority and out-of-range-distance validation messages.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.npc_ai_config import NPCAIConfig, AIDecisionValidator  # type: ignore
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


# ---------------------------------------------------------------------------
# AIDecisionValidator gaps
# ---------------------------------------------------------------------------


def test_is_valid_flank_decision_false_without_npc():
    ai_config = NPCAIConfig(Player())
    validator = AIDecisionValidator(ai_config)
    valid, reason = validator.is_valid_flank_decision(None, "target", [1, 2])
    assert valid is False
    assert "NPC is None" in reason


def test_is_valid_flank_decision_false_without_target():
    ai_config = NPCAIConfig(Player())
    validator = AIDecisionValidator(ai_config)
    npc = _npc()
    valid, reason = validator.is_valid_flank_decision(npc, None, [1, 2])
    assert valid is False
    assert "No target available" in reason


def test_is_valid_flank_decision_false_without_proximity_entry():
    ai_config = NPCAIConfig(Player())
    validator = AIDecisionValidator(ai_config)
    npc = _npc()
    npc.combat_proximity = {}
    valid, reason = validator.is_valid_flank_decision(npc, "target", [1, 2])
    assert valid is False
    assert "not in proximity range" in reason


def test_is_valid_flank_decision_false_when_distance_out_of_range():
    ai_config = NPCAIConfig(Player())
    validator = AIDecisionValidator(ai_config)
    npc = _npc()
    npc.combat_proximity = {"target": 9999}
    valid, reason = validator.is_valid_flank_decision(npc, "target", [1, 2])
    assert valid is False
    assert "outside flank range" in reason


def test_is_valid_retreat_decision_false_without_npc():
    ai_config = NPCAIConfig(Player())
    validator = AIDecisionValidator(ai_config)
    valid, reason = validator.is_valid_retreat_decision(None)
    assert valid is False
    assert "NPC is None" in reason


def test_is_valid_retreat_decision_false_without_health_attrs():
    ai_config = NPCAIConfig(Player())
    validator = AIDecisionValidator(ai_config)

    class NoHealth:
        pass

    valid, reason = validator.is_valid_retreat_decision(NoHealth())
    assert valid is False
    assert "missing health attributes" in reason


def test_is_valid_retreat_decision_false_when_health_above_threshold():
    ai_config = NPCAIConfig(Player())
    validator = AIDecisionValidator(ai_config)
    npc = _npc()
    npc.hp = npc.maxhp  # full health, well above the 0.3 default threshold

    valid, reason = validator.is_valid_retreat_decision(npc)
    assert valid is False
    assert "above threshold" in reason


def test_is_valid_retreat_priority_low_moderate_and_high_messages():
    ai_config = NPCAIConfig(Player())
    validator = AIDecisionValidator(ai_config)

    valid, reason = validator.is_valid_retreat_priority(0.1)
    assert valid is True
    assert "Low retreat priority" in reason

    valid, reason = validator.is_valid_retreat_priority(0.5)
    assert valid is True
    assert "Moderate retreat priority" in reason

    valid, reason = validator.is_valid_retreat_priority(0.9)
    assert valid is True
    assert "High retreat priority" in reason


def test_validate_all_settings_flags_retreat_threshold_out_of_range():
    player = Player()
    config = GameConfig()
    config.npc_retreat_health_threshold = 5.0  # invalid, > 1.0
    player.game_config = config
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)

    valid, issues = validator.validate_all_settings()
    assert valid is False
    assert any("Retreat threshold out of range" in i for i in issues)


def test_validate_all_settings_flags_negative_distance_range():
    player = Player()
    config = GameConfig()
    config.npc_flanking_distance_range = "-10 to -5"
    player.game_config = config
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)

    valid, issues = validator.validate_all_settings()
    assert valid is False
    assert any("negative value" in i for i in issues)
