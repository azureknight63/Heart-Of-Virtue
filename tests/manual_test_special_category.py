"""
Manual test to demonstrate the Special category showing Books and Crystals.
This script creates a player with various items including Books and Crystals
and opens the inventory to show they all appear in the Special category.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from player import Player
import items
from interface import InventoryInterface

def main():
    print("=" * 60)
    print("Testing Special Category with Books and Crystals")
    print("=" * 60)
    
    # Create a player
    player = Player()
    player.name = "Jean"
    
    # Clear default inventory
    player.inventory = []
    
    # Add various items including Books and Crystals
    print("\nAdding items to inventory:")
    
    # Add a book
    book = items.Book(name="Ancient Manuscript", description="A dusty old tome.", value=50, weight=2.0)
    player.inventory.append(book)
    print("  - Book: Ancient Manuscript")
    
    # Add unique crystal items (Relics)
    dragon_gem = items.DragonHeartGem()
    player.inventory.append(dragon_gem)
    print("  - Relic: Dragon Heart Gem")
    
    crystal_tear = items.CrystalTear()
    player.inventory.append(crystal_tear)
    print("  - Relic: Crystal Tear")
    
    # Add commodity crystals (Special type)
    crystals = items.Crystals(count=5)
    player.inventory.append(crystals)
    print("  - Special: Crystals (commodity)")
    
    # Add a key for comparison (also Special type)
    key = items.Key()
    player.inventory.append(key)
    print("  - Special: Key")
    
    # Add some regular items for context
    weapon = items.Shortsword()
    player.inventory.append(weapon)
    print("  - Weapon: Shortsword")
    
    armor = items.LeatherArmor()
    player.inventory.append(armor)
    print("  - Armor: Leather Armor")
    
    gold = items.Gold(100)
    player.inventory.append(gold)
    print("  - Gold: 100")
    
    print("\n" + "=" * 60)
    print("Opening inventory... Select 's' to view Special items.")
    print("You should see: Books, Relics (Crystals), and other Special items.")
    print("=" * 60 + "\n")
    
    # Open the inventory interface
    iface = InventoryInterface(player)
    iface.run()
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
