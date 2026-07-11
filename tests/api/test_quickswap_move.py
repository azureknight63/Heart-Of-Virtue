"""
Integration tests for QuickSwap move functionality.

Tests verify that:
1. QuickSwap accepts ally targets (accepts_ally_target=True)
2. QuickSwap honors the selected target and swaps positions with it
3. QuickSwap fails gracefully if the selected ally moves out of range
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


import pytest


class TestQuickSwapMove:
    """Integration tests for QuickSwap move functionality."""

    def test_quickswap_has_accepts_ally_target_flag(self, app, authenticated_session):
        """
        Test that QuickSwap has accepts_ally_target=True set.

        This verifies that the move properly declares that it can target allies.
        """
        from src import moves

        session_id, player, session_manager = authenticated_session

        # Create QuickSwap move
        quickswap_move = moves.QuickSwap(player)

        # Verify targeted flag
        assert quickswap_move.targeted, "Quick Swap should be a targeted move"

        # Verify accepts_ally_target flag
        assert (
            quickswap_move.accepts_ally_target
        ), "Quick Swap should have accepts_ally_target=True"

    def test_quickswap_honors_selected_target(self, app, authenticated_session):
        """
        Test that QuickSwap uses self.target instead of hardcoding the first ally.

        This verifies that execute() honors the chosen target when swapping.
        """
        from src.npc import NPC
        from src import moves

        session_id, player, session_manager = authenticated_session
        game_service = app.game_service

        # Create two allied NPCs
        ally_1 = NPC("Ally One", "First ally", 30, False, 50)
        ally_1.friend = True
        ally_2 = NPC("Ally Two", "Second ally", 30, False, 50)
        ally_2.friend = True

        # Add QuickSwap to player's known moves
        quickswap_move = moves.QuickSwap(player)
        player.known_moves.append(quickswap_move)

        # Use distance-based system (no coordinates)
        player.combat_proximity = {ally_1: 2, ally_2: 2}
        player.combat_list_allies = [player, ally_1, ally_2]

        # Make allies alive and able to find each other
        ally_1.combat_proximity = {player: 2, ally_2: 1}
        ally_2.combat_proximity = {player: 2, ally_1: 1}
        ally_1.combat_list_allies = [player, ally_1, ally_2]
        ally_2.combat_list_allies = [player, ally_1, ally_2]

        # Select ally_2 as the target (not the first one)
        quickswap_move.target = ally_2
        quickswap_move.user = player

        # Verify that this is the selected target, not ally_1
        assert quickswap_move.target is ally_2, "Target should be ally_2"

        # Execute - should use ally_2, not ally_1
        quickswap_move.execute(player)

        # Verify swap happened: player and ally_2 exchanged proximity dictionaries
        # After swap, player has ally_2's old proximity (which has player: 2, ally_1: 1)
        # and ally_2 has player's old proximity (which has ally_1: 2, ally_2: 2)
        assert player.combat_proximity[ally_1] == 1, "Player should have ally_2's old proximity"
        assert ally_2.combat_proximity[ally_2] == 2, "Ally_2 should have player's old proximity"

    def test_quickswap_fails_if_target_out_of_range(self, app, authenticated_session):
        """
        Test that QuickSwap fails if the selected ally is out of range.

        This verifies that execute() validates the target is still nearby.
        """
        from src.npc import NPC
        from src import moves

        session_id, player, session_manager = authenticated_session

        # Create an allied NPC that will be out of range
        ally = NPC("Distant Ally", "Far away", 30, False, 50)
        ally.friend = True

        # Add QuickSwap to player's known moves
        quickswap_move = moves.QuickSwap(player)
        player.known_moves.append(quickswap_move)

        # Set up allies list but ally is out of range (distance 10, beyond max 4)
        player.combat_proximity = {ally: 10}
        player.combat_list_allies = [player, ally]
        ally.combat_proximity = {player: 10}
        ally.combat_list_allies = [player, ally]

        # Select the distant ally as target
        quickswap_move.target = ally
        quickswap_move.user = player

        # Attempt to execute - should raise an error
        with pytest.raises(ValueError, match="no longer within swapping range"):
            quickswap_move.execute(player)

    def test_quickswap_viable_requires_nearby_allies(self, app, authenticated_session):
        """
        Test that QuickSwap.viable() returns False when no nearby allies exist.
        """
        from src.npc import NPC
        from src import moves

        session_id, player, session_manager = authenticated_session

        # Create an NPC that's too far away
        distant_npc = NPC("Distant", "Far away", 30, False, 50)
        distant_npc.friend = False  # Not an ally

        # Add QuickSwap
        quickswap_move = moves.QuickSwap(player)
        player.combat_list_allies = [player]
        player.combat_proximity = {distant_npc: 10}

        # Should not be viable with no nearby allies
        assert not quickswap_move.viable(), "QuickSwap should not be viable without nearby allies"

        # Add a nearby ally
        nearby_ally = NPC("Close", "Right here", 30, False, 50)
        nearby_ally.friend = True
        player.combat_list_allies = [player, nearby_ally]
        player.combat_proximity = {nearby_ally: 2}
        nearby_ally.combat_proximity = {player: 2}
        nearby_ally.combat_list_allies = [player, nearby_ally]

        # Now should be viable
        assert quickswap_move.viable(), "QuickSwap should be viable with nearby allies"
