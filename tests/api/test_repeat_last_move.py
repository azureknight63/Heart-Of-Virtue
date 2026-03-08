"""
Integration tests for the "DO IT AGAIN" (repeat_last) move functionality.

Tests the flow where a player uses a targeted move (e.g., Attack), then uses
the "DO IT AGAIN" button to repeat that same move on the same target.
"""

import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest


class TestRepeatLastMove:
    """Integration tests for repeat_last (DO IT AGAIN) functionality."""

    def test_repeat_last_move_after_targeting(self, app, authenticated_session):
        """
        Test that "DO IT AGAIN" handles repeat_last correctly by looking up the saved move.

        The fix validates that repeat_last is recognized and converted to the actual move name,
        rather than returning "Move 'repeat_last' not found".
        """
        from src.npc import NPC

        session_id, player, session_manager = authenticated_session
        game_service = app.game_service

        # Create an enemy and initialize combat properly
        enemy = NPC("Test Enemy", "A test minion", 10, True, 50)
        game_service._initialize_combat(player, [enemy], session_id=session_id)

        # Get the enemy ID for targeting
        enemy_id = f"enemy_{id(enemy)}"

        # Simulate that a previous Attack move was executed and recorded
        player.last_move_name = "Attack"
        player.last_move_target_id = enemy_id

        # Verify last_move_name and last_move_target_id are set
        assert hasattr(player, "last_move_name"), "Player should have last_move_name attribute"
        assert hasattr(player, "last_move_target_id"), "Player should have last_move_target_id attribute"
        assert player.last_move_name == "Attack", f"Expected last_move_name='Attack', got '{player.last_move_name}'"
        assert player.last_move_target_id == enemy_id, f"Expected target_id='{enemy_id}', got '{player.last_move_target_id}'"

        # Now execute repeat_last move - this is the main test of the fix
        repeat_result = game_service.execute_move(
            player,
            "select_move_and_target",
            "repeat_last",
            session_id=session_id,
            session_data={}
        )

        # The fix should successfully look up the move name and attempt to execute it
        # The error should be about the move's viability, NOT "repeat_last not found"
        # (which would indicate the fix didn't work)
        if "error" in repeat_result:
            # Verify the error is NOT about repeat_last being an invalid move
            assert "repeat_last" not in repeat_result["error"].lower(), \
                f"repeat_last was not recognized: {repeat_result}"
        else:
            # If no error, execution was successful
            assert repeat_result.get("success") or "battle_state" in repeat_result

    def test_repeat_last_no_previous_move(self, app, authenticated_session):
        """Test that repeat_last fails gracefully when no previous move exists."""
        from src.npc import NPC

        session_id, player, session_manager = authenticated_session
        game_service = app.game_service

        # Initialize combat without executing any moves
        enemy = NPC("Test Enemy", "A test minion", 10, True, 50)
        game_service._initialize_combat(player, [enemy], session_id=session_id)

        # Try to use repeat_last without executing any move first
        repeat_result = game_service.execute_move(
            player,
            "select_move_and_target",
            "repeat_last",
            session_id=session_id,
            session_data={}
        )

        # Should return an error
        assert "error" in repeat_result
        assert "no previous move" in repeat_result["error"].lower()

    def test_repeat_last_target_defeated(self, app, authenticated_session):
        """Test that repeat_last fails gracefully when the target is no longer alive."""
        from src.npc import NPC

        session_id, player, session_manager = authenticated_session
        game_service = app.game_service

        # Initialize combat
        enemy = NPC("Test Enemy", "A test minion", 10, True, 50)
        game_service._initialize_combat(player, [enemy], session_id=session_id)

        enemy_id = f"enemy_{id(enemy)}"

        # Manually set last_move tracking (simulating that a previous move was executed)
        player.last_move_name = "Attack"
        player.last_move_target_id = enemy_id

        # Manually defeat the enemy by setting HP to 0
        enemy.hp = 0

        # Try to use repeat_last on a defeated enemy
        repeat_result = game_service.execute_move(
            player,
            "select_move_and_target",
            "repeat_last",
            session_id=session_id,
            session_data={}
        )

        # Should return an error about no valid target
        assert "error" in repeat_result
        assert "target" in repeat_result["error"].lower() and "no longer available" in repeat_result["error"].lower()

