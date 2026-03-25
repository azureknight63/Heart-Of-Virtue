import sys
import os
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC_DIR))

try:
    print("Testing Player import...")
    from src.player import Player
    print("Player imported successfully!")

    print("\nTesting Player instantiation...")
    p = Player()
    print(f"Player created: {p.name}")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
