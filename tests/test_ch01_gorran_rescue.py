"""
Test for Chapter 1 Gorran rescue event - battlefield map position updates.

This test verifies that when Gorran rescues Jean and new enemies are spawned,
the battlefield map properly updates with accurate enemy positions.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from unittest.mock import Mock, patch
from player import Player
from tiles import MapTile
from story.ch01 import Ch01PostRumbler3


def test_gorran_rescue_updates_battlefield_positions():
    """Test that Gorran rescue event properly updates battlefield positions."""
    # Create mock player
    player = Mock(spec=Player)
    player.combat_list = []
    player.combat_list_allies = [player]
    player.in_combat = True
    player.current_room = Mock(spec=MapTile)
    
    # Create mock tile
    tile = Mock(spec=MapTile)
    
    # Mock spawn_npc to return mock NPCs
    mock_gorran = Mock()
    mock_gorran.name = "Gorran"
    mock_gorran.in_combat = False
    
    mock_rumblers = []
    for i in range(5):
        rumbler = Mock()
        rumbler.name = f"RockRumbler{i}"
        rumbler.in_combat = False
        mock_rumblers.append(rumbler)
    
    spawn_calls = [mock_gorran] + mock_rumblers
    tile.spawn_npc = Mock(side_effect=spawn_calls)
    tile.events_here = []
    
    # Create the event
    event = Ch01PostRumbler3(player=player, tile=tile)
    
    # Mock the cprint and time.sleep to avoid delays
    with patch('story.ch01.cprint'), \
         patch('story.ch01.time.sleep'), \
         patch('functions.add_enemies_to_combat') as mock_add_enemies:
        
        # Simulate user choosing option 'a' (help Gorran)
        event.process(user_input='a')
        
        # Verify Gorran was added to allies
        assert mock_gorran in player.combat_list_allies
        assert mock_gorran.in_combat == True
        
        # Verify add_enemies_to_combat was called with the new enemies
        mock_add_enemies.assert_called_once()
        call_args = mock_add_enemies.call_args
        assert call_args[0][0] == player  # First arg is player
        assert len(call_args[0][1]) == 5  # Second arg is list of 5 enemies
        
        # Verify all rumblers are in the list passed to add_enemies_to_combat
        enemies_added = call_args[0][1]
        for rumbler in mock_rumblers:
            assert rumbler in enemies_added


def test_gorran_rescue_sets_combat_lists():
    """Test that Gorran's combat lists are properly configured."""
    # Create mock player
    player = Mock(spec=Player)
    player.combat_list = []
    player.combat_list_allies = [player]
    player.in_combat = True
    player.current_room = Mock(spec=MapTile)
    
    # Create mock tile
    tile = Mock(spec=MapTile)
    
    # Mock spawn_npc to return mock NPCs
    mock_gorran = Mock()
    mock_gorran.name = "Gorran"
    mock_gorran.in_combat = False
    
    mock_rumblers = [Mock() for _ in range(5)]
    
    spawn_calls = [mock_gorran] + mock_rumblers
    tile.spawn_npc = Mock(side_effect=spawn_calls)
    tile.events_here = []
    
    # Create the event
    event = Ch01PostRumbler3(player=player, tile=tile)
    
    # Mock the cprint and time.sleep to avoid delays
    with patch('story.ch01.cprint'), \
         patch('story.ch01.time.sleep'), \
         patch('functions.add_enemies_to_combat'):
        
        # Simulate user choosing option 'a' (help Gorran)
        event.process(user_input='a')
        
        # Verify Gorran's combat lists are set correctly
        assert mock_gorran.combat_list == player.combat_list  # Gorran targets enemies
        assert mock_gorran.combat_list_allies == player.combat_list_allies  # Gorran is allied with player


def test_gorran_rescue_coward_choice():
    """Test that choosing to flee doesn't add Gorran or call add_enemies_to_combat."""
    # Create mock player
    player = Mock(spec=Player)
    player.combat_list = []
    player.combat_list_allies = [player]
    player.hp = 100
    
    # Create mock tile
    tile = Mock(spec=MapTile)
    tile.spawn_npc = Mock()
    
    # Create the event
    event = Ch01PostRumbler3(player=player, tile=tile)
    
    # Mock the cprint and time.sleep to avoid delays
    with patch('story.ch01.cprint'), \
         patch('story.ch01.time.sleep'), \
         patch('story.ch01.random.randint', return_value=50), \
         patch('functions.add_enemies_to_combat') as mock_add_enemies:
        
        # Simulate user choosing option 'b' (flee)
        event.process(user_input='b')
        
        # Verify add_enemies_to_combat was NOT called
        mock_add_enemies.assert_not_called()
        
        # Verify player took damage (hp set to 0 in the bad ending)
        assert player.hp == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
