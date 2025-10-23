"""
Unit tests for tiles module
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.tiles import MapTile


@pytest.fixture
def mock_universe():
    """Create a mock universe"""
    universe = Mock()
    return universe


@pytest.fixture
def mock_map():
    """Create a mock map"""
    return Mock()


@pytest.fixture
def basic_tile(mock_universe, mock_map):
    """Create a basic MapTile for testing"""
    return MapTile(mock_universe, mock_map, 5, 10, "A test room")


def test_tile_initialization(basic_tile):
    """Test that a tile initializes with correct properties"""
    assert basic_tile.x == 5
    assert basic_tile.y == 10
    assert basic_tile.description == "A test room"
    assert basic_tile.npcs_here == []
    assert basic_tile.items_here == []
    assert basic_tile.events_here == []
    assert basic_tile.objects_here == []
    assert basic_tile.last_entered == 0
    assert basic_tile.discovered is False
    assert basic_tile.respawn_rate == 9999
    assert basic_tile.block_exit == []
    assert basic_tile.symbol == '='


def test_tile_universe_reference(basic_tile, mock_universe):
    """Test that tile maintains reference to universe"""
    assert basic_tile.universe == mock_universe


def test_tile_map_reference(basic_tile, mock_map):
    """Test that tile maintains reference to map"""
    assert basic_tile.map == mock_map


def test_intro_text(basic_tile):
    """Test intro_text returns colored description"""
    result = basic_tile.intro_text()
    # Result should contain the description text
    assert "test room" in result.lower()


def test_intro_text_empty_description(mock_universe, mock_map):
    """Test intro_text with empty description"""
    tile = MapTile(mock_universe, mock_map, 0, 0, "")
    result = tile.intro_text()
    assert result is not None


def test_modify_player(basic_tile):
    """Test modify_player does nothing by default"""
    mock_player = Mock()
    result = basic_tile.modify_player(mock_player)
    assert result is None


def test_block_exit_initialization(basic_tile):
    """Test that block_exit starts empty"""
    assert basic_tile.block_exit == []


def test_block_exit_can_be_set(basic_tile):
    """Test that block_exit can be modified"""
    basic_tile.block_exit.append("north")
    assert "north" in basic_tile.block_exit


@patch('src.tiles.tile_exists')
def test_adjacent_moves_all_directions(mock_tile_exists, basic_tile):
    """Test adjacent_moves returns all valid directions"""
    # Mock all adjacent tiles exist
    mock_adjacent_tile = Mock()
    mock_adjacent_tile.discovered = False
    mock_tile_exists.return_value = mock_adjacent_tile
    
    moves = basic_tile.adjacent_moves()
    
    # Should have 8 directional moves
    assert len(moves) == 8


@patch('src.tiles.tile_exists')
def test_adjacent_moves_blocked_direction(mock_tile_exists, basic_tile):
    """Test adjacent_moves respects blocked exits"""
    mock_adjacent_tile = Mock()
    mock_adjacent_tile.discovered = False
    mock_tile_exists.return_value = mock_adjacent_tile
    
    # Block north exit
    basic_tile.block_exit.append("north")
    
    moves = basic_tile.adjacent_moves()
    
    # Should have 7 moves (8 - 1 blocked)
    assert len(moves) == 7


@patch('src.tiles.tile_exists')
def test_adjacent_moves_no_tiles(mock_tile_exists, basic_tile):
    """Test adjacent_moves when no adjacent tiles exist"""
    mock_tile_exists.return_value = None
    
    moves = basic_tile.adjacent_moves()
    
    # Should have no moves
    assert len(moves) == 0


@patch('src.tiles.tile_exists')
def test_adjacent_moves_marks_discovered(mock_tile_exists, basic_tile):
    """Test adjacent_moves marks adjacent tiles as discovered"""
    mock_adjacent_tile = Mock()
    mock_adjacent_tile.discovered = False
    mock_tile_exists.return_value = mock_adjacent_tile
    
    basic_tile.adjacent_moves()
    
    # Adjacent tile should be marked as discovered
    assert mock_adjacent_tile.discovered is True


def test_available_actions_includes_moves(basic_tile):
    """Test available_actions includes movement options"""
    with patch.object(basic_tile, 'adjacent_moves', return_value=[]):
        actions = basic_tile.available_actions()
        
        # Should have default actions
        assert len(actions) > 0


def test_evaluate_events_empty(basic_tile):
    """Test evaluate_events with no events"""
    basic_tile.evaluate_events()
    # Should complete without error


def test_evaluate_events_with_events(basic_tile):
    """Test evaluate_events calls check_conditions on all events"""
    mock_event1 = Mock()
    mock_event2 = Mock()
    basic_tile.events_here = [mock_event1, mock_event2]
    
    basic_tile.evaluate_events()
    
    mock_event1.check_conditions.assert_called_once()
    mock_event2.check_conditions.assert_called_once()


def test_spawn_npc_basic(basic_tile):
    """Test spawning an NPC"""
    npc = basic_tile.spawn_npc("TestNPC")
    
    assert npc is not None
    assert npc in basic_tile.npcs_here
    assert len(basic_tile.npcs_here) == 1


def test_spawn_npc_hidden(basic_tile):
    """Test spawning a hidden NPC"""
    npc = basic_tile.spawn_npc("TestNPC", hidden=True, hfactor=5)
    
    assert npc.hidden is True
    assert npc.hide_factor == 5


def test_spawn_npc_with_delay(basic_tile):
    """Test spawning an NPC with specific combat delay"""
    npc = basic_tile.spawn_npc("TestNPC", delay=3)
    
    assert npc.combat_delay == 3


def test_spawn_npc_random_delay(basic_tile):
    """Test spawning an NPC with random delay"""
    npc = basic_tile.spawn_npc("TestNPC", delay=-1)
    
    # Combat delay should be between 0 and 7
    assert 0 <= npc.combat_delay <= 7


def test_spawn_npc_sets_current_room(basic_tile):
    """Test that spawned NPC has current_room set"""
    npc = basic_tile.spawn_npc("TestNPC")
    
    assert hasattr(npc, 'current_room')


def test_spawn_multiple_npcs(basic_tile):
    """Test spawning multiple NPCs"""
    npc1 = basic_tile.spawn_npc("NPC1")
    npc2 = basic_tile.spawn_npc("NPC2")
    
    assert len(basic_tile.npcs_here) == 2
    assert npc1 in basic_tile.npcs_here
    assert npc2 in basic_tile.npcs_here


@patch('src.tiles.importlib.import_module')
def test_spawn_item_gold(mock_import, basic_tile):
    """Test spawning gold"""
    mock_items = Mock()
    mock_gold_cls = Mock(return_value=Mock())
    mock_items.Gold = mock_gold_cls
    mock_import.return_value = mock_items
    
    item = basic_tile.spawn_item("Gold", amt=50)
    
    assert item is not None
    assert len(basic_tile.items_here) == 1


@patch('src.tiles.importlib.import_module')
def test_spawn_item_stackable(mock_import, basic_tile):
    """Test spawning stackable items"""
    mock_items = Mock()
    mock_item_instance = Mock()
    mock_item_instance.count = 1
    mock_item_instance.merchandise = False
    mock_item_cls = Mock(return_value=mock_item_instance)
    mock_items.Potion = mock_item_cls
    mock_import.return_value = mock_items
    
    item = basic_tile.spawn_item("Potion", amt=5)
    
    assert mock_item_instance.count == 5
    assert len(basic_tile.items_here) == 1


@patch('src.tiles.importlib.import_module')
def test_spawn_item_non_stackable(mock_import, basic_tile):
    """Test spawning non-stackable items"""
    mock_items = Mock()
    mock_item_instance = Mock(spec=[])  # No 'count' attribute
    mock_item_cls = Mock(return_value=mock_item_instance)
    mock_items.Sword = mock_item_cls
    mock_import.return_value = mock_items
    
    item = basic_tile.spawn_item("Sword", amt=3)
    
    # Should create 3 separate instances
    assert len(basic_tile.items_here) == 3


@patch('src.tiles.importlib.import_module')
def test_spawn_item_hidden(mock_import, basic_tile):
    """Test spawning hidden items"""
    mock_items = Mock()
    mock_item = Mock()
    mock_item.count = 1
    mock_items.Item = Mock(return_value=mock_item)
    mock_import.return_value = mock_items
    
    item = basic_tile.spawn_item("Item", hidden=True, hfactor=10)
    
    assert item.hidden is True
    assert item.hide_factor == 10


@patch('src.tiles.importlib.import_module')
def test_spawn_item_merchandise(mock_import, basic_tile):
    """Test spawning merchandise items"""
    mock_items = Mock()
    mock_item = Mock()
    mock_item.count = 1
    mock_item.merchandise = False
    mock_items.Item = Mock(return_value=mock_item)
    mock_import.return_value = mock_items
    
    item = basic_tile.spawn_item("Item", merchandise=True)
    
    assert item.merchandise is True


@patch('src.tiles.functions.seek_class')
@patch('src.tiles.functions.instantiate_event')
def test_spawn_event(mock_instantiate, mock_seek, basic_tile):
    """Test spawning an event"""
    mock_event = Mock()
    mock_event_cls = Mock()
    mock_seek.return_value = mock_event_cls
    mock_instantiate.return_value = mock_event
    
    mock_player = Mock()
    event = basic_tile.spawn_event("TestEvent", mock_player, basic_tile)
    
    assert event is not None
    assert event in basic_tile.events_here


@patch('src.tiles.functions.seek_class')
@patch('src.tiles.functions.instantiate_event')
def test_spawn_event_with_repeat(mock_instantiate, mock_seek, basic_tile):
    """Test spawning a repeatable event"""
    mock_event = Mock()
    mock_seek.return_value = Mock()
    mock_instantiate.return_value = mock_event
    
    mock_player = Mock()
    event = basic_tile.spawn_event("TestEvent", mock_player, basic_tile, repeat=True)
    
    assert event in basic_tile.events_here
    # Verify instantiate_event called with repeat=True
    call_kwargs = mock_instantiate.call_args[1]
    assert call_kwargs['repeat'] is True


@patch('src.tiles.functions.seek_class')
@patch('src.tiles.functions.instantiate_event')
def test_spawn_event_returns_none_on_failure(mock_instantiate, mock_seek, basic_tile):
    """Test spawn_event returns None when instantiation fails"""
    mock_seek.return_value = Mock()
    mock_instantiate.return_value = None
    
    mock_player = Mock()
    event = basic_tile.spawn_event("TestEvent", mock_player, basic_tile)
    
    assert event is None
    assert len(basic_tile.events_here) == 0


def test_spawn_object(basic_tile):
    """Test spawning an object"""
    mock_player = Mock()
    
    with patch('builtins.__import__') as mock_import:
        mock_objects_module = Mock()
        mock_obj = Mock()
        mock_obj.hidden = False
        mock_obj.hide_factor = 0
        mock_obj_cls = Mock(return_value=mock_obj)
        mock_objects_module.Chest = mock_obj_cls
        mock_import.return_value = mock_objects_module
        
        obj = basic_tile.spawn_object("Chest", mock_player, basic_tile, {})
        
        assert obj is not None
        assert obj in basic_tile.objects_here


def test_spawn_object_hidden(basic_tile):
    """Test spawning a hidden object"""
    mock_player = Mock()
    
    with patch('builtins.__import__') as mock_import:
        mock_objects_module = Mock()
        mock_obj = Mock()
        mock_obj.hidden = False
        mock_obj.hide_factor = 0
        mock_obj_cls = Mock(return_value=mock_obj)
        mock_objects_module.Chest = mock_obj_cls
        mock_import.return_value = mock_objects_module
        
        obj = basic_tile.spawn_object("Chest", mock_player, basic_tile, {}, 
                                      hidden=True, hfactor=8)
        
        assert obj.hidden is True
        assert obj.hide_factor == 8


@patch('src.tiles.importlib.import_module')
def test_stack_duplicate_items(mock_import, basic_tile):
    """Test stacking duplicate items"""
    mock_items = Mock()
    
    # Create mock stackable items
    item1 = Mock()
    item1.count = 3
    item1.__class__ = Mock
    item1.stack_grammar = Mock()
    
    item2 = Mock()
    item2.count = 2
    item2.__class__ = item1.__class__  # Same class
    item2.stack_grammar = Mock()
    
    basic_tile.items_here = [item1, item2]
    
    basic_tile.stack_duplicate_items()
    
    # item1 should have combined count
    assert item1.count == 5
    # item2 should be removed
    assert item2 not in basic_tile.items_here
    assert len(basic_tile.items_here) == 1


@patch('src.tiles.importlib.import_module')
def test_stack_duplicate_items_calls_stack_grammar(mock_import, basic_tile):
    """Test that stack_grammar is called when count > 1"""
    item1 = Mock()
    item1.count = 2
    item1.__class__ = Mock
    item1.stack_grammar = Mock()
    
    item2 = Mock()
    item2.count = 3
    item2.__class__ = item1.__class__
    item2.stack_grammar = Mock()
    
    basic_tile.items_here = [item1, item2]
    
    basic_tile.stack_duplicate_items()
    
    # stack_grammar should be called
    assert item1.stack_grammar.called


def test_stack_duplicate_items_no_stackable(basic_tile):
    """Test stacking with non-stackable items"""
    item1 = Mock(spec=[])  # No count attribute
    item2 = Mock(spec=[])
    
    basic_tile.items_here = [item1, item2]
    
    # Should not raise error
    basic_tile.stack_duplicate_items()
    
    # Both items should remain
    assert len(basic_tile.items_here) == 2


def test_remove_event_by_name(basic_tile):
    """Test removing an event by name"""
    mock_event1 = Mock()
    mock_event1.name = "Event1"
    mock_event2 = Mock()
    mock_event2.name = "Event2"
    
    basic_tile.events_here = [mock_event1, mock_event2]
    
    basic_tile.remove_event("Event1")
    
    assert mock_event1 not in basic_tile.events_here
    assert mock_event2 in basic_tile.events_here


def test_remove_event_not_found(basic_tile):
    """Test removing an event that doesn't exist"""
    mock_event = Mock()
    mock_event.name = "Event1"
    
    basic_tile.events_here = [mock_event]
    
    # Should not raise error
    basic_tile.remove_event("NonExistent")
    
    assert mock_event in basic_tile.events_here


def test_remove_event_no_name_attribute(basic_tile):
    """Test removing event when event has no name attribute"""
    mock_event = Mock(spec=[])  # No name attribute
    basic_tile.events_here = [mock_event]
    
    # Should not raise error
    basic_tile.remove_event("SomeName")
    
    assert mock_event in basic_tile.events_here


def test_tile_coordinates_are_integers(basic_tile):
    """Test that tile coordinates are stored as provided"""
    assert isinstance(basic_tile.x, int)
    assert isinstance(basic_tile.y, int)


def test_tile_respawn_rate_default(basic_tile):
    """Test default respawn rate is very high"""
    assert basic_tile.respawn_rate == 9999


def test_tile_symbol_default(basic_tile):
    """Test default symbol"""
    assert basic_tile.symbol == '='
