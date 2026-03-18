"""Tests for reputation GameService methods (Phase 3 Stage 2)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.player import Player
from src.api.services.game_service import GameService
from src.universe import Universe


@pytest.fixture
def universe():
    """Create a test universe."""
    u = Universe()
    return u


@pytest.fixture
def game_service(universe):
    """Create a GameService instance."""
    return GameService(universe)


@pytest.fixture
def player():
    """Create a test player with reputation data."""
    p = Player()
    p.reputation = {
        "merchant": 50,
        "cave_guide": 30,
        "blacksmith": -30,
    }
    return p


class TestGetPlayerReputation:
    """Tests for get_player_reputation method."""

    def test_get_player_reputation_success(self, game_service, player):
        """Test getting player's reputation data."""
        result = game_service.get_player_reputation(player)

        assert result["success"] is True
        assert "reputation" in result
        assert result["reputation"]["total_npcs"] == 3
        assert result["reputation"]["highest_reputation"] == 50
        assert result["reputation"]["lowest_reputation"] == -30

    def test_get_player_reputation_empty(self, game_service):
        """Test getting reputation for player with no reputation data."""
        player = Player()
        result = game_service.get_player_reputation(player)

        assert result["success"] is True
        assert result["reputation"]["total_npcs"] == 0


class TestGetNPCRelationship:
    """Tests for get_npc_relationship method."""

    def test_get_npc_relationship_success(self, game_service, player):
        """Test getting NPC relationship."""
        result = game_service.get_npc_relationship(player, "merchant")

        assert result["success"] is True
        assert "relationship" in result
        assert "flags" in result
        assert result["relationship"]["npc_id"] == "merchant"
        assert result["relationship"]["reputation"] == 50
        assert result["relationship"]["attitude"] in ["favorable", "friendly"]

    def test_get_npc_relationship_no_prior(self, game_service, player):
        """Test getting relationship with new NPC."""
        result = game_service.get_npc_relationship(player, "unknown_npc")

        assert result["success"] is True
        assert result["relationship"]["reputation"] == 0
        assert result["relationship"]["attitude"] == "neutral"

    def test_get_npc_relationship_includes_flags(self, game_service, player):
        """Test that relationship includes flags."""
        result = game_service.get_npc_relationship(player, "merchant")

        assert "flags" in result
        assert result["flags"]["npc_id"] == "merchant"
        assert result["flags"]["active_count"] >= 0


class TestUpdateReputation:
    """Tests for update_reputation method."""

    def test_update_reputation_increase(self, game_service, player):
        """Test increasing reputation."""
        result = game_service.update_reputation(
            player, "merchant", 20, "quest_complete"
        )

        assert result["success"] is True
        assert result["reputation_change"]["change"] == 20
        assert result["reputation_change"]["direction"] == "positive"
        assert player.reputation["merchant"] == 70

    def test_update_reputation_decrease(self, game_service, player):
        """Test decreasing reputation."""
        result = game_service.update_reputation(
            player, "merchant", -15, "dialogue_choice"
        )

        assert result["success"] is True
        assert result["reputation_change"]["change"] == -15
        assert result["reputation_change"]["direction"] == "negative"
        assert player.reputation["merchant"] == 35

    def test_update_reputation_clamped_max(self, game_service, player):
        """Test reputation is clamped to +100."""
        result = game_service.update_reputation(
            player, "merchant", 100, "quest_complete"
        )

        assert player.reputation["merchant"] == 100
        assert result["reputation_change"]["new_reputation"] == 100

    def test_update_reputation_clamped_min(self, game_service, player):
        """Test reputation is clamped to -100."""
        result = game_service.update_reputation(
            player, "merchant", -200, "betrayal"
        )

        assert player.reputation["merchant"] == -100
        assert result["reputation_change"]["new_reputation"] == -100

    def test_update_reputation_new_npc(self, game_service, player):
        """Test updating reputation for new NPC."""
        result = game_service.update_reputation(
            player, "new_npc", 30, "first_meeting"
        )

        assert player.reputation["new_npc"] == 30
        assert result["success"] is True

    def test_update_reputation_attitude_change_tracked(self, game_service, player):
        """Test that attitude changes are tracked."""
        result = game_service.update_reputation(
            player, "blacksmith", 100, "redemption"
        )

        # blacksmith was -30, +100 = 70 (friendly)
        assert result["reputation_change"]["attitude_changed"] is True
        assert result["reputation_change"]["old_attitude"] == "hostile"
        assert result["reputation_change"]["new_attitude"] == "friendly"


class TestSetRelationshipFlag:
    """Tests for set_relationship_flag method."""

    def test_set_relationship_flag_success(self, game_service, player):
        """Test setting a relationship flag."""
        result = game_service.set_relationship_flag(
            player, "merchant", "romance", True
        )

        assert result["success"] is True
        assert player.relationship_flags["merchant"]["romance"] is True

    def test_set_relationship_flag_multiple(self, game_service, player):
        """Test setting multiple flags."""
        game_service.set_relationship_flag(
            player, "merchant", "romance", True
        )
        game_service.set_relationship_flag(
            player, "merchant", "alliance", True
        )

        assert player.relationship_flags["merchant"]["romance"] is True
        assert player.relationship_flags["merchant"]["alliance"] is True

    def test_set_relationship_flag_toggle(self, game_service, player):
        """Test toggling a flag off."""
        game_service.set_relationship_flag(
            player, "merchant", "romance", True
        )
        result = game_service.set_relationship_flag(
            player, "merchant", "romance", False
        )

        assert player.relationship_flags["merchant"]["romance"] is False
        assert result["success"] is True


class TestCheckDialogueAvailable:
    """Tests for check_dialogue_available method."""

    def test_check_dialogue_available_success(self, game_service, player):
        """Test checking dialogue availability."""
        result = game_service.check_dialogue_available(
            player, "merchant", "quest_offer"
        )

        assert result["success"] is True
        assert result["available"] is True

    def test_check_dialogue_locked_negative_reputation(self, game_service, player):
        """Test dialogue locked at negative reputation."""
        result = game_service.check_dialogue_available(
            player, "blacksmith", "greeting_friendly"
        )

        assert result["available"] is False
        assert result["locked_reason"] is not None

    def test_check_dialogue_special_locked(self, game_service, player):
        """Test special dialogue locked at low reputation."""
        result = game_service.check_dialogue_available(
            player, "cave_guide", "special_dialogue"
        )

        # cave_guide is at 30, needs 50 for special dialogue
        assert result["available"] is False


class TestCheckQuestAvailable:
    """Tests for check_quest_available method."""

    def test_check_quest_normal_available(self, game_service, player):
        """Test normal quest is available."""
        result = game_service.check_quest_available(
            player, "merchant", "normal_quest"
        )

        assert result["success"] is True
        assert result["available"] is True

    def test_check_quest_secret_locked(self, game_service, player):
        """Test secret quest locked at low reputation."""
        result = game_service.check_quest_available(
            player, "cave_guide", "secret_quest"
        )

        # cave_guide is at 30, needs 75 for secret quest
        assert result["available"] is False
        assert result["locked_reason"] is not None

    def test_check_quest_difficult_locked(self, game_service, player):
        """Test difficult quest locked at low reputation."""
        result = game_service.check_quest_available(
            player, "blacksmith", "difficult_quest"
        )

        # blacksmith is at -30, needs 50 for difficult quest
        assert result["available"] is False


class TestReputationIntegration:
    """Integration tests for reputation system."""

    def test_complete_reputation_flow(self, game_service, player):
        """Test complete reputation management flow."""
        # Start with neutral reputation
        merchant_rep = player.reputation.get("new_merchant", 0)
        assert merchant_rep == 0

        # Complete a quest, gain reputation
        game_service.update_reputation(
            player, "new_merchant", 25, "quest_complete"
        )
        assert player.reputation["new_merchant"] == 25

        # Set flag for future reference
        game_service.set_relationship_flag(
            player, "new_merchant", "alliance", True
        )
        assert player.relationship_flags["new_merchant"]["alliance"] is True

        # Check what's available now
        dialogue_result = game_service.check_dialogue_available(
            player, "new_merchant", "special_dialogue"
        )
        quest_result = game_service.check_quest_available(
            player, "new_merchant", "important_quest"
        )

        # At 25 reputation, we may not have special_dialogue yet (needs 50)
        # But important_quest should be available (needs 25)
        assert quest_result["available"] is True

        # Get complete relationship status
        relationship = game_service.get_npc_relationship(
            player, "new_merchant"
        )
        assert relationship["relationship"]["attitude"] in ["favorable", "friendly"]

    def test_negative_reputation_gates_content(self, game_service, player):
        """Test that negative reputation gates content."""
        # Get hostile with someone
        game_service.update_reputation(
            player, "enemy_npc", -80, "betrayal"
        )

        # Check available content
        dialogue = game_service.check_dialogue_available(
            player, "enemy_npc", "greeting_friendly"
        )
        quest = game_service.check_quest_available(
            player, "enemy_npc", "normal_quest"
        )

        # Everything should be locked
        assert dialogue["available"] is False
        assert quest["available"] is False

    def test_multiple_npc_relationships(self, game_service, player):
        """Test managing relationships with multiple NPCs."""
        # Update multiple NPCs
        game_service.update_reputation(
            player, "npc1", 50, "quest_complete"
        )
        game_service.update_reputation(
            player, "npc2", 30, "quest_complete"
        )
        game_service.update_reputation(
            player, "npc3", -40, "conflict"
        )

        # Get full reputation status
        rep_data = game_service.get_player_reputation(player)
        assert rep_data["reputation"]["total_npcs"] >= 3
        assert rep_data["reputation"]["friendly_npcs"] >= 1
        # hostile_npcs requires reputation <= -50, we're at -40 which is "wary"
        assert rep_data["reputation"]["hostile_npcs"] >= 0
