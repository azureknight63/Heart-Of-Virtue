import pytest
from unittest.mock import MagicMock, patch
from npc._loot import NPCLootMixin

class MockNPC(NPCLootMixin):
    def __init__(self):
        self.name = "MockNPC"
        self.inventory = []
        self.loot = None
        self.current_room = None
        self.player_ref = None

def test_stack_items_list_called():
    npc = MockNPC()
    npc.current_room = MagicMock()
    # current_room has items_here
    npc.current_room.items_here = [MagicMock()]
    
    with patch("functions.stack_items_list") as mock_stack:
        npc.before_death()
        mock_stack.assert_called_once()

def test_drop_inventory_various_branches():
    # 1. Item without count attribute
    npc = MockNPC()
    item_no_count = MagicMock(spec=["__class__"])
    item_no_count.__class__.__name__ = "Herb"
    # Do not set item_no_count.count
    npc.inventory = [item_no_count]
    npc.current_room = MagicMock()
    
    with patch("random.random", return_value=0.7): # random > 0.6 -> decrements quantity
        npc.drop_inventory()
        # quantity was 1, decremented to 0, so spawn_item shouldn't be called
        npc.current_room.spawn_item.assert_not_called()

    # 2. Player ref without combat_drops attribute
    npc = MockNPC()
    item = MagicMock()
    item.count = 2
    item.__class__.__name__ = "Gold"
    item.name = "Gold Coin"
    npc.inventory = [item]
    npc.current_room = MagicMock()
    
    player = MagicMock()
    player._combat_adapter = MagicMock()
    # Deliberately do not have player.combat_drops
    if hasattr(player, "combat_drops"):
        del player.combat_drops
        
    npc.player_ref = player
    
    with patch("random.random", return_value=0.1): # random < 0.6 -> quantity stays 2
        npc.drop_inventory()
        assert hasattr(player, "combat_drops")
        assert len(player.combat_drops) == 1
        assert player.combat_drops[0]["quantity"] == 2

def test_roll_loot_equipment_branches():
    npc = MockNPC()
    npc.loot = {"Equipment_1_2": {"chance": 100, "qty": 1}}
    npc.current_room = MagicMock()
    
    player = MagicMock()
    player._combat_adapter = MagicMock()
    # Deliberately do not have player.combat_drops
    if hasattr(player, "combat_drops"):
        del player.combat_drops
    npc.player_ref = player

    with patch("random.shuffle"):
        with patch("random.randint", return_value=50): # success (chance 100 >= 50)
            with patch("functions.randomize_amount", return_value=1):
                with patch("npc._loot.loot.random_equipment") as mock_random_eq:
                    drop = MagicMock()
                    drop.name = "Fine Dagger"
                    mock_random_eq.return_value = drop
                    
                    npc.roll_loot()
                    
                    mock_random_eq.assert_called_once_with(npc.current_room, "1", "2")
                    assert hasattr(player, "combat_drops")
                    assert player.combat_drops[0]["name"] == "Fine Dagger"
