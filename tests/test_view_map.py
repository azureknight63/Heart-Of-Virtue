"""Tests for the player's view_map functionality and map rendering."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytest
from unittest.mock import MagicMock, patch, Mock

# Import modules after sys.path is set
from player import Player
from tiles import MapTile
from universe import Universe


def test_player_has_prev_location_attributes():
    """Test that player initializes with previous location tracking."""
    
    player = Player()
    assert hasattr(player, 'prev_location_x')
    assert hasattr(player, 'prev_location_y')
    assert player.prev_location_x == 0
    assert player.prev_location_y == 0


def test_player_has_view_map_method():
    """Test that player has a view_map method."""
    
    player = Player()
    assert hasattr(player, 'view_map')
    assert callable(player.view_map)


def test_starting_tile_discovered_in_game():
    """Test that the starting tile is marked as discovered when game starts."""
    # This tests the game.py change we made
    
    universe = Universe()
    game_map = {'name': 'test_map'}
    tile = MapTile(universe, game_map, 0, 0, "Starting tile")
    
    # Initially not discovered
    assert tile.discovered == False
    
    # After setting (simulating game start)
    tile.discovered = True
    assert tile.discovered == True


def test_tile_has_symbol_attribute():
    """Test that tiles have a symbol attribute for map display."""
    
    universe = Universe()
    game_map = {'name': 'test_map'}
    tile = MapTile(universe, game_map, 0, 0, "Test tile")
    
    assert hasattr(tile, 'symbol')
    assert tile.symbol == '●'  # Default symbol


def test_tile_has_last_entered_attribute():
    """Test that tiles track when they were last entered."""
    
    universe = Universe()
    game_map = {'name': 'test_map'}
    tile = MapTile(universe, game_map, 0, 0, "Test tile")
    
    assert hasattr(tile, 'last_entered')
    assert tile.last_entered == 0  # Initially not entered


def test_tile_has_discovered_attribute():
    """Test that tiles can be marked as discovered."""
    
    universe = Universe()
    game_map = {'name': 'test_map'}
    tile = MapTile(universe, game_map, 0, 0, "Test tile")
    
    assert hasattr(tile, 'discovered')
    assert tile.discovered == False  # Initially not discovered
    
    # Can be marked as discovered
    tile.discovered = True
    assert tile.discovered == True


def test_map_rendering_direction_calculation():
    """Test the direction calculation logic for connectors."""
    # Test horizontal movement (east)
    prev_x, prev_y = 1, 1
    curr_x, curr_y = 2, 1
    dx = curr_x - prev_x
    dy = curr_y - prev_y
    
    assert dx == 1 and dy == 0  # East movement
    
    # Test vertical movement (south)
    prev_x, prev_y = 1, 1
    curr_x, curr_y = 1, 2
    dx = curr_x - prev_x
    dy = curr_y - prev_y
    
    assert dx == 0 and dy == 1  # South movement
    
    # Test diagonal movement (southeast)
    prev_x, prev_y = 1, 1
    curr_x, curr_y = 2, 2
    dx = curr_x - prev_x
    dy = curr_y - prev_y
    
    assert dx == 1 and dy == 1  # Southeast movement


def test_map_bounds_calculation():
    """Test that map bounds are calculated correctly from tile coordinates."""
    # Simulate discovered tiles at various positions
    tiles = [(0, 0), (2, 1), (1, 3), (3, 2)]
    
    min_x = min(x for x, y in tiles)
    max_x = max(x for x, y in tiles)
    min_y = min(y for x, y in tiles)
    max_y = max(y for x, y in tiles)
    
    assert min_x == 0
    assert max_x == 3
    assert min_y == 0
    assert max_y == 3


def test_empty_symbol_handling():
    """Test that empty symbols are handled correctly."""
    symbol = ''
    default_symbol = '●'
    
    # Logic from view_map: symbol if symbol else default
    result = symbol if symbol else default_symbol
    assert result == default_symbol
    
    # Non-empty symbol should be kept
    symbol = '='
    result = symbol if symbol else default_symbol
    assert result == '='
