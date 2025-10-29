"""tests/test_memory_flash.py

Converts the manual script into a pytest-style test. The original file was a
script (and contained markdown-style backticks), which prevented pytest from
discovering any tests. This test simply constructs minimal objects and runs
the memory event, asserting it completes and emits expected output.
"""
import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so imports resolve like other tests
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.story.ch01 import Ch01_Memory_Amelia
from src.player import Player
from src.universe import Universe
from src.tiles import MapTile


def test_memory_flash_runs_and_prints(capsys):
    """Construct a minimal universe/player/tile and run the memory event.

    The test asserts the script prints the start/finish lines (legacy script
    output) and that calling process() does not raise.
    """
    """tests/test_memory_flash.py

    Simple pytest wrapper for the memory flash event. Replaces the original
    script-style file so pytest can discover and run it.
    """
    import sys
    from pathlib import Path

    # Ensure the project's src directory is on sys.path so imports resolve like other tests
    ROOT = Path(__file__).resolve().parent.parent
    SRC_DIR = ROOT / "src"
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    from src.story.ch01 import Ch01_Memory_Amelia
    from src.player import Player
    from src.universe import Universe
    from src.tiles import MapTile


    def test_memory_flash_runs_and_prints(capsys):
        """Construct a minimal universe/player/tile and run the memory event.

        The test asserts the script prints the start/finish lines (legacy script
        output) and that calling process() does not raise.
        """
        test_universe = Universe()
        test_player = Player()
        test_player.universe = test_universe

        test_map = {}
        test_tile = MapTile(test_universe, test_map, 0, 0, "Test chamber")
        test_player.tile = test_tile

        print("Testing memory flash system...\n")
        memory = Ch01_Memory_Amelia(player=test_player, tile=test_tile)
        # Should not raise
        memory.process()

        print("\n✓ Memory flash test completed!")

        captured = capsys.readouterr()
        assert "Testing memory flash system" in captured.out
        assert "Memory flash test completed" in captured.out
print("\n✓ Memory flash test completed!")
