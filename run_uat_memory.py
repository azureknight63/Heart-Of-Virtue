"""
UAT Script: Memory Flash System
Quick test to experience the memory flash without playing through the game.
"""

def run_uat():
    import sys
    sys.path.insert(0, 'src')
    
    print("\n" + "="*79)
    print("UAT: Memory Flash System".center(79))
    print("="*79 + "\n")
    
    print("This will demonstrate the memory flash sequence that triggers after")
    print("Jean defeats his first Rock Rumbler.\n")
    
    input("Press Enter to begin...")
    print("\n")
    
    # Simulate the combat victory moment
    from neotermcolor import cprint
    import time
    
    cprint("Jean lowers his mace, breathing heavily. The creature has dissolved", "cyan")
    cprint("into shimmering fragments that slowly fade into nothingness.", "cyan")
    time.sleep(2)
    
    # Trigger the memory flash
    from src.story.ch01 import Ch01_Memory_Emily
    from src.player import Player
    from src.universe import Universe
    from src.tiles import MapTile
    
    # Create minimal test objects
    test_universe = Universe()
    test_player = Player()
    test_player.universe = test_universe
    
    # Create a simple test tile
    test_map = {}
    test_tile = MapTile(test_universe, test_map, 0, 0, "Test chamber")
    test_player.tile = test_tile
    
    # Create and trigger the memory
    memory = Ch01_Memory_Emily(player=test_player, tile=test_tile)
    memory.process()
    
    # Simulate return to gameplay
    print()
    cprint("The ground quivers slightly as more rock creatures appear.", "white")
    print()
    
    print("\n" + "="*79)
    print("UAT Complete".center(79))
    print("="*79 + "\n")
    
    print("Please provide feedback:")
    print("1. Did the animation play correctly?")
    print("2. Was the memory text readable and emotionally engaging?")
    print("3. Did the pacing feel appropriate?")
    print("4. Any suggested changes?")
    print()

if __name__ == "__main__":
    try:
        run_uat()
    except KeyboardInterrupt:
        print("\n\nUAT interrupted by user.")
    except Exception as e:
        print(f"\n\nError during UAT: {e}")
        import traceback
        traceback.print_exc()
