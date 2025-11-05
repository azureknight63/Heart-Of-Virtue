"""Tests for NPC AI configuration (Phase 2.4)."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.npc_ai_config import NPCAIConfig, AIDecisionValidator  # type: ignore
from src.config_manager import GameConfig  # type: ignore
from src.player import Player  # type: ignore
from src.npc import NPC  # type: ignore


def test_npc_ai_config_flanking_enabled_default():
    """Test default flanking enabled state."""
    player = Player()
    ai_config = NPCAIConfig(player)
    
    assert ai_config.is_flanking_enabled() is True


def test_npc_ai_config_flanking_enabled_from_config():
    """Test flanking enabled state from GameConfig."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_enabled = False
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    
    assert ai_config.is_flanking_enabled() is False


def test_npc_ai_config_tactical_retreat_enabled_default():
    """Test default tactical retreat enabled state."""
    player = Player()
    ai_config = NPCAIConfig(player)
    
    assert ai_config.is_tactical_retreat_enabled() is True


def test_npc_ai_config_tactical_retreat_enabled_from_config():
    """Test tactical retreat enabled state from GameConfig."""
    player = Player()
    config = GameConfig()
    config.npc_tactical_retreat = False
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    
    assert ai_config.is_tactical_retreat_enabled() is False


def test_npc_ai_config_flanking_threshold_default():
    """Test default flanking threshold."""
    player = Player()
    ai_config = NPCAIConfig(player)
    
    assert ai_config.get_flanking_threshold() == 45.0


def test_npc_ai_config_flanking_threshold_from_config():
    """Test flanking threshold from GameConfig."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_threshold = 60.0
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    
    assert ai_config.get_flanking_threshold() == 60.0


def test_npc_ai_config_retreat_health_threshold_default():
    """Test default retreat health threshold."""
    player = Player()
    ai_config = NPCAIConfig(player)
    
    assert ai_config.get_retreat_health_threshold() == 0.3


def test_npc_ai_config_retreat_health_threshold_from_config():
    """Test retreat health threshold from GameConfig."""
    player = Player()
    config = GameConfig()
    config.npc_retreat_health_threshold = 0.25
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    
    assert ai_config.get_retreat_health_threshold() == 0.25


def test_npc_ai_config_flanking_distance_range_default():
    """Test default flanking distance range."""
    player = Player()
    ai_config = NPCAIConfig(player)
    
    min_dist, max_dist = ai_config.get_flanking_distance_range()
    assert min_dist == 20.0
    assert max_dist == 40.0


def test_npc_ai_config_flanking_distance_range_from_config():
    """Test flanking distance range from GameConfig."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_distance_range = "15.0 to 50.0"
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    
    min_dist, max_dist = ai_config.get_flanking_distance_range()
    assert min_dist == 15.0
    assert max_dist == 50.0


def test_npc_ai_config_flanking_distance_range_parsing_variations():
    """Test parsing of various flanking distance range formats."""
    player = Player()
    config = GameConfig()
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    
    # Test with spaces
    config.npc_flanking_distance_range = "10.0  to  35.0"
    min_dist, max_dist = ai_config.get_flanking_distance_range()
    assert min_dist == 10.0
    assert max_dist == 35.0


def test_npc_ai_config_should_attempt_flank_disabled():
    """Test that flank attempt returns False when disabled."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_enabled = False
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0)
    
    should_flank = ai_config.should_attempt_flank(npc, [], [])
    assert should_flank is False


def test_npc_ai_config_should_attempt_flank_insufficient_allies():
    """Test that flank attempt requires sufficient allies."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_enabled = True
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0)
    enemy = NPC("Enemy", "Test", damage=10, aggro=True, exp_award=0)
    
    # Only 1 ally (npc itself doesn't count)
    should_flank = ai_config.should_attempt_flank(npc, [npc], [enemy])
    assert should_flank is False


def test_npc_ai_config_should_attempt_flank_valid():
    """Test valid flank attempt scenario."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_enabled = True
    config.npc_flanking_distance_range = "20.0 to 40.0"
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0)
    ally = NPC("Ally", "Test", damage=10, aggro=True, exp_award=0)
    enemy = NPC("Enemy", "Test", damage=10, aggro=True, exp_award=0)
    
    npc.target = enemy
    npc.combat_proximity = {enemy: 30.0}  # In flank range
    
    should_flank = ai_config.should_attempt_flank(npc, [npc, ally], [enemy])
    assert should_flank is True


def test_npc_ai_config_should_attempt_retreat_disabled():
    """Test that retreat attempt returns False when disabled."""
    player = Player()
    config = GameConfig()
    config.npc_tactical_retreat = False
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0, maxhp=100)
    npc.hp = 20  # 20% health
    
    should_retreat = ai_config.should_attempt_retreat(npc)
    assert should_retreat is False


def test_npc_ai_config_should_attempt_retreat_below_threshold():
    """Test retreat attempt when health is below threshold."""
    player = Player()
    config = GameConfig()
    config.npc_tactical_retreat = True
    config.npc_retreat_health_threshold = 0.3
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0, maxhp=100)
    npc.hp = 20  # 20% health (below 30% threshold)
    
    should_retreat = ai_config.should_attempt_retreat(npc)
    assert should_retreat is True


def test_npc_ai_config_should_attempt_retreat_above_threshold():
    """Test retreat attempt when health is above threshold."""
    player = Player()
    config = GameConfig()
    config.npc_tactical_retreat = True
    config.npc_retreat_health_threshold = 0.3
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0, maxhp=100)
    npc.hp = 50  # 50% health (above 30% threshold)
    
    should_retreat = ai_config.should_attempt_retreat(npc)
    assert should_retreat is False


def test_npc_ai_config_calculate_retreat_priority_disabled():
    """Test retreat priority returns 0 when disabled."""
    player = Player()
    config = GameConfig()
    config.npc_tactical_retreat = False
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0, maxhp=100)
    npc.hp = 20
    
    priority = ai_config.calculate_retreat_priority(npc, [])
    assert priority == 0.0


def test_npc_ai_config_calculate_retreat_priority_above_threshold():
    """Test retreat priority is 0 when above threshold."""
    player = Player()
    config = GameConfig()
    config.npc_tactical_retreat = True
    config.npc_retreat_health_threshold = 0.3
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0, maxhp=100)
    npc.hp = 50
    
    priority = ai_config.calculate_retreat_priority(npc, [])
    assert priority == 0.0


def test_npc_ai_config_calculate_retreat_priority_at_threshold():
    """Test retreat priority scales from threshold to critical."""
    player = Player()
    config = GameConfig()
    config.npc_tactical_retreat = True
    config.npc_retreat_health_threshold = 0.3
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0, maxhp=100)
    
    # At threshold (30%)
    npc.hp = 30
    priority = ai_config.calculate_retreat_priority(npc, [])
    assert 0.0 <= priority <= 1.0  # Should be reasonable
    
    # Critical (5%)
    npc.hp = 5
    priority = ai_config.calculate_retreat_priority(npc, [])
    assert priority > 0.8  # Should be very high priority


def test_npc_ai_config_get_weighted_move_bonus_retreat():
    """Test weighted move bonus for retreat moves when low health."""
    player = Player()
    config = GameConfig()
    config.npc_tactical_retreat = True
    config.npc_retreat_health_threshold = 0.3
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0, maxhp=100)
    npc.hp = 20  # Below threshold
    
    # Retreat moves should get bonus
    withdraw_bonus = ai_config.get_weighted_move_bonus(npc, "Withdraw")
    assert withdraw_bonus > 0
    
    # Attack moves should not
    attack_bonus = ai_config.get_weighted_move_bonus(npc, "NPC_Attack")
    assert attack_bonus >= 0


def test_npc_ai_config_get_ai_config_summary():
    """Test AI configuration summary generation."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_enabled = True
    config.npc_tactical_retreat = True
    config.npc_flanking_threshold = 45.0
    config.npc_retreat_health_threshold = 0.3
    config.npc_flanking_distance_range = "20.0 to 40.0"
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    
    summary = ai_config.get_ai_config_summary()
    assert "NPC AI Configuration" in summary
    assert "Flanking Enabled: True" in summary
    assert "Tactical Retreat Enabled: True" in summary
    assert "45.0°" in summary
    assert "20.0-40.0" in summary


def test_ai_decision_validator_initialization():
    """Test AIDecisionValidator initialization."""
    player = Player()
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    assert validator.ai_config is ai_config


def test_ai_decision_validator_is_valid_flank_decision_disabled():
    """Test flank decision validation when flanking is disabled."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_enabled = False
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0)
    enemy = NPC("Enemy", "Test", damage=10, aggro=True, exp_award=0)
    
    is_valid, reason = validator.is_valid_flank_decision(npc, enemy, [])
    assert is_valid is False
    assert "disabled" in reason.lower()


def test_ai_decision_validator_is_valid_flank_decision_no_allies():
    """Test flank decision validation fails with insufficient allies."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_enabled = True
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0)
    enemy = NPC("Enemy", "Test", damage=10, aggro=True, exp_award=0)
    
    is_valid, reason = validator.is_valid_flank_decision(npc, enemy, [npc])
    assert is_valid is False
    assert "allies" in reason.lower()


def test_ai_decision_validator_is_valid_flank_decision_valid():
    """Test flank decision validation succeeds with valid conditions."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_enabled = True
    config.npc_flanking_distance_range = "20.0 to 40.0"
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0)
    ally = NPC("Ally", "Test", damage=10, aggro=True, exp_award=0)
    enemy = NPC("Enemy", "Test", damage=10, aggro=True, exp_award=0)
    
    npc.combat_proximity = {enemy: 30.0}
    
    is_valid, reason = validator.is_valid_flank_decision(npc, enemy, [npc, ally])
    assert is_valid is True
    assert "conditions met" in reason.lower()


def test_ai_decision_validator_is_valid_retreat_decision_disabled():
    """Test retreat decision validation when retreat is disabled."""
    player = Player()
    config = GameConfig()
    config.npc_tactical_retreat = False
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0, maxhp=100)
    npc.hp = 20
    
    is_valid, reason = validator.is_valid_retreat_decision(npc)
    assert is_valid is False
    assert "disabled" in reason.lower()


def test_ai_decision_validator_is_valid_retreat_decision_health_critical():
    """Test retreat decision validation when health is critical."""
    player = Player()
    config = GameConfig()
    config.npc_tactical_retreat = True
    config.npc_retreat_health_threshold = 0.3
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    npc = NPC("TestNPC", "Test", damage=10, aggro=True, exp_award=0, maxhp=100)
    npc.hp = 20
    
    is_valid, reason = validator.is_valid_retreat_decision(npc)
    assert is_valid is True
    assert "critical" in reason.lower()


def test_ai_decision_validator_is_valid_flank_distance_in_range():
    """Test flank distance validation in range."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_distance_range = "20.0 to 40.0"
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    is_valid, reason = validator.is_valid_flank_distance(30.0)
    assert is_valid is True


def test_ai_decision_validator_is_valid_flank_distance_too_close():
    """Test flank distance validation too close."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_distance_range = "20.0 to 40.0"
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    is_valid, reason = validator.is_valid_flank_distance(10.0)
    assert is_valid is False
    assert "too close" in reason.lower()


def test_ai_decision_validator_is_valid_flank_distance_too_far():
    """Test flank distance validation too far."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_distance_range = "20.0 to 40.0"
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    is_valid, reason = validator.is_valid_flank_distance(50.0)
    assert is_valid is False
    assert "too far" in reason.lower()


def test_ai_decision_validator_is_valid_retreat_priority_in_range():
    """Test retreat priority validation in range."""
    player = Player()
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    is_valid, reason = validator.is_valid_retreat_priority(0.5)
    assert is_valid is True


def test_ai_decision_validator_is_valid_retreat_priority_out_of_range():
    """Test retreat priority validation out of range."""
    player = Player()
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    is_valid, reason = validator.is_valid_retreat_priority(1.5)
    assert is_valid is False
    assert "out of range" in reason.lower()


def test_ai_decision_validator_validate_all_settings_valid():
    """Test all settings validation with valid config."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_threshold = 45.0
    config.npc_retreat_health_threshold = 0.3
    config.npc_flanking_distance_range = "20.0 to 40.0"
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    all_valid, issues = validator.validate_all_settings()
    assert all_valid is True
    assert len(issues) == 0


def test_ai_decision_validator_validate_all_settings_invalid_flank_threshold():
    """Test all settings validation with invalid flanking threshold."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_threshold = 200.0  # Out of range
    config.npc_retreat_health_threshold = 0.3
    config.npc_flanking_distance_range = "20.0 to 40.0"
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    all_valid, issues = validator.validate_all_settings()
    assert all_valid is False
    assert any("flank" in issue.lower() and "threshold" in issue.lower() for issue in issues)


def test_ai_decision_validator_validate_all_settings_invalid_distance_range():
    """Test all settings validation with invalid distance range."""
    player = Player()
    config = GameConfig()
    config.npc_flanking_threshold = 45.0
    config.npc_retreat_health_threshold = 0.3
    config.npc_flanking_distance_range = "40.0 to 20.0"  # Min > max
    player.game_config = config
    
    ai_config = NPCAIConfig(player)
    validator = AIDecisionValidator(ai_config)
    
    all_valid, issues = validator.validate_all_settings()
    assert all_valid is False
    assert any("min" in issue.lower() and "max" in issue.lower() for issue in issues)
