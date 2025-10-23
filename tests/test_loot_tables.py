"""
Unit tests for loot_tables module
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.loot_tables import Loot


@pytest.fixture
def loot_instance():
    """Create a Loot instance for testing"""
    return Loot()


def test_loot_initialization(loot_instance):
    """Test that Loot object initializes with correct loot tables"""
    assert loot_instance.lev0 is not None
    assert loot_instance.lev1 is not None


def test_lev0_structure(loot_instance):
    """Test that lev0 loot table has expected structure"""
    assert "Gold" in loot_instance.lev0
    assert "Restorative" in loot_instance.lev0
    assert "Draught" in loot_instance.lev0
    assert "Equipment_0_1" in loot_instance.lev0


def test_lev0_gold_properties(loot_instance):
    """Test lev0 gold drop properties"""
    gold = loot_instance.lev0["Gold"]
    assert "chance" in gold
    assert "qty" in gold
    assert gold["chance"] == 50
    assert gold["qty"] == "r25-50"


def test_lev0_restorative_properties(loot_instance):
    """Test lev0 restorative properties"""
    restorative = loot_instance.lev0["Restorative"]
    assert restorative["chance"] == 25
    assert restorative["qty"] == 1


def test_lev0_draught_properties(loot_instance):
    """Test lev0 draught properties"""
    draught = loot_instance.lev0["Draught"]
    assert draught["chance"] == 25
    assert draught["qty"] == 1


def test_lev0_equipment_properties(loot_instance):
    """Test lev0 equipment properties"""
    equipment = loot_instance.lev0["Equipment_0_1"]
    assert equipment["chance"] == 10
    assert equipment["qty"] == 1


def test_lev1_structure(loot_instance):
    """Test that lev1 loot table has expected structure"""
    assert "Gold" in loot_instance.lev1
    assert "Restorative" in loot_instance.lev1
    assert "Draught" in loot_instance.lev1
    assert "Equipment_0_0" in loot_instance.lev1
    assert "Equipment_1_0" in loot_instance.lev1


def test_lev1_gold_properties(loot_instance):
    """Test lev1 gold drop has higher value range than lev0"""
    gold = loot_instance.lev1["Gold"]
    assert gold["chance"] == 50
    assert gold["qty"] == "r50-100"


def test_lev1_restorative_range(loot_instance):
    """Test lev1 restorative can drop multiple items"""
    restorative = loot_instance.lev1["Restorative"]
    assert restorative["chance"] == 25
    assert restorative["qty"] == "r1-3"


def test_lev1_equipment_tiers(loot_instance):
    """Test lev1 has multiple equipment tiers"""
    eq0 = loot_instance.lev1["Equipment_0_0"]
    eq1 = loot_instance.lev1["Equipment_1_0"]
    
    assert eq0["chance"] == 40
    assert eq1["chance"] == 10
    assert eq0["qty"] == 1
    assert eq1["qty"] == 1


@patch('src.loot_tables.items', create=True)
@patch('src.loot_tables.functions.add_random_enchantments', create=True)
@patch('src.loot_tables.inspect.getmembers', create=True)
@patch('src.loot_tables.inspect.isclass', create=True, side_effect=lambda x: True)
def test_random_equipment_basic(mock_isclass, mock_getmembers, mock_enchant, mock_items):
    """Test random_equipment generates equipment"""
    # Mock a class with level attribute
    class MockEquipment:
        level = 1
    
    mock_getmembers.return_value = [("MockEquipment", MockEquipment)]
    
    mock_tile = Mock()
    mock_drop = Mock()
    mock_tile.spawn_item.return_value = mock_drop
    
    result = Loot.random_equipment(mock_tile, 1, 0)
    
    assert mock_tile.spawn_item.called
    assert result == mock_drop


@patch('src.loot_tables.items', create=True)
@patch('src.loot_tables.functions.add_random_enchantments', create=True)
@patch('src.loot_tables.inspect.getmembers', create=True)
@patch('src.loot_tables.inspect.isclass', create=True, side_effect=lambda x: True)
@patch('src.loot_tables.random.randint')
def test_random_equipment_with_enchantment(mock_randint, mock_isclass, mock_getmembers, 
                                           mock_enchant, mock_items):
    """Test random_equipment applies enchantments"""
    class MockEquipment:
        level = 2
    
    mock_getmembers.return_value = [("MockEquipment", MockEquipment)]
    mock_randint.return_value = 0
    
    mock_tile = Mock()
    mock_drop = Mock()
    mock_tile.spawn_item.return_value = mock_drop
    
    result = Loot.random_equipment(mock_tile, 2, 5)
    
    # Verify enchantments were added
    mock_enchant.assert_called_once_with(mock_drop, 5)


@patch('src.loot_tables.items', create=True)
@patch('src.loot_tables.functions.add_random_enchantments', create=True)
@patch('src.loot_tables.inspect.getmembers', create=True)
@patch('src.loot_tables.inspect.isclass', create=True, side_effect=lambda x: True)
@patch('builtins.print')
def test_random_equipment_invalid_enchantment(mock_print, mock_isclass, mock_getmembers,
                                               mock_enchant, mock_items):
    """Test random_equipment handles invalid enchantment values"""
    class MockEquipment:
        level = 1
    
    mock_getmembers.return_value = [("MockEquipment", MockEquipment)]
    
    mock_tile = Mock()
    mock_drop = Mock()
    mock_tile.spawn_item.return_value = mock_drop
    
    # Pass invalid enchantment value
    result = Loot.random_equipment(mock_tile, 1, "invalid")
    
    # Should print error and use 0 for enchantment
    assert mock_print.called
    mock_enchant.assert_called_once_with(mock_drop, 0)


@patch('src.loot_tables.items', create=True)
@patch('src.loot_tables.functions.add_random_enchantments', create=True)
@patch('src.loot_tables.inspect.getmembers', create=True)
@patch('src.loot_tables.inspect.isclass', create=True, side_effect=lambda x: True)
@patch('src.loot_tables.random.randint')
def test_random_equipment_multiple_candidates(mock_randint, mock_isclass, mock_getmembers,
                                              mock_enchant, mock_items):
    """Test random_equipment selects from multiple items of same level"""
    class MockEquipment1:
        level = 3
    
    class MockEquipment2:
        level = 3
    
    class MockEquipment3:
        level = 5  # Different level, should be filtered out
    
    mock_getmembers.return_value = [
        ("MockEquipment1", MockEquipment1),
        ("MockEquipment2", MockEquipment2),
        ("MockEquipment3", MockEquipment3)
    ]
    mock_randint.return_value = 1  # Select second item
    
    mock_tile = Mock()
    mock_drop = Mock()
    mock_tile.spawn_item.return_value = mock_drop
    
    result = Loot.random_equipment(mock_tile, 3, 0)
    
    # Should have spawned one of the level 3 items
    assert mock_tile.spawn_item.called
    call_args = mock_tile.spawn_item.call_args[0]
    # First argument should be one of the level 3 equipment names
    assert call_args[0] in ["MockEquipment1", "MockEquipment2"]


@patch('src.loot_tables.items', create=True)
@patch('src.loot_tables.functions.add_random_enchantments', create=True)
@patch('src.loot_tables.inspect.getmembers', create=True)
@patch('src.loot_tables.inspect.isclass', create=True, side_effect=lambda x: True)
def test_random_equipment_spawn_parameters(mock_isclass, mock_getmembers, mock_enchant, mock_items):
    """Test random_equipment uses correct spawn parameters"""
    class MockEquipment:
        level = 1
    
    mock_getmembers.return_value = [("MockEquipment", MockEquipment)]
    
    mock_tile = Mock()
    mock_drop = Mock()
    mock_tile.spawn_item.return_value = mock_drop
    
    Loot.random_equipment(mock_tile, 1, 0)
    
    # Verify spawn_item called with correct parameters
    mock_tile.spawn_item.assert_called_once()
    call_args, call_kwargs = mock_tile.spawn_item.call_args
    assert call_kwargs['amt'] == 1
    assert call_kwargs['hidden'] is False
    assert call_kwargs['hfactor'] == 0


def test_loot_table_all_items_have_chance(loot_instance):
    """Test that all items in loot tables have a chance value"""
    for item_name, item_data in loot_instance.lev0.items():
        assert "chance" in item_data, f"{item_name} missing chance"
        assert isinstance(item_data["chance"], int)
    
    for item_name, item_data in loot_instance.lev1.items():
        assert "chance" in item_data, f"{item_name} missing chance"
        assert isinstance(item_data["chance"], int)


def test_loot_table_all_items_have_qty(loot_instance):
    """Test that all items in loot tables have a qty value"""
    for item_name, item_data in loot_instance.lev0.items():
        assert "qty" in item_data, f"{item_name} missing qty"
    
    for item_name, item_data in loot_instance.lev1.items():
        assert "qty" in item_data, f"{item_name} missing qty"


def test_loot_table_chance_values_positive(loot_instance):
    """Test that all chance values are positive"""
    for item_data in loot_instance.lev0.values():
        assert item_data["chance"] > 0
    
    for item_data in loot_instance.lev1.values():
        assert item_data["chance"] > 0
