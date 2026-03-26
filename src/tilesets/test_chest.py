import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so imports resolve like other tests
file_path = Path(__file__).resolve()
if "src" in str(file_path):
    ROOT = file_path.parents[2]  # For files in src/, go up to root
else:
    ROOT = file_path.parents[1]  # For files in tests/, go up to root
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.tiles import MapTile  # noqa: E402


class ChestRoom(MapTile):
    def __init__(self, universe, current_map, x, y, description: str = None):
        super().__init__(
            universe,
            current_map,
            x,
            y,
            description="""
        A test room with a wooden chest. This is for testing the chest rumbler battle narrative.
        """,
        )
        self.symbol = "#"

    def modify_player(self, the_player):
        # Room has no action on player
        pass
