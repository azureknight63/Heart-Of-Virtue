
import sys
import os

# Add project root and src to path
root_path = os.path.abspath(".")
sys.path.append(root_path)
sys.path.append(os.path.join(root_path, "src"))

# Mock flask
from unittest.mock import MagicMock
sys.modules['flask'] = MagicMock()
sys.modules['flask_cors'] = MagicMock()
sys.modules['flask_socketio'] = MagicMock()

try:
    from src.npc import NPC
    import src.moves as moves

    print("=" * 60)
    print("Testing Move.advance() user update fix")
    print("=" * 60)

    # Create an NPC
    enemy = NPC("TestSlime", "A test slime", 10, True, 10, speed=10)

    # Create a move with a BAD user (string)
    print("\n1. Creating NpcAttack with valid NPC user...")
    test_move = moves.NpcAttack(enemy)
    print(f"   Initial user type: {type(test_move.user)}")
    print(f"   Initial user value: {test_move.user}")

    # Corrupt the user to a string (simulating the bug)
    print("\n2. Corrupting user to a string...")
    test_move.user = "CORRUPTED_STRING"
    print(f"   Corrupted user type: {type(test_move.user)}")
    print(f"   Corrupted user value: {test_move.user}")

    # Call advance() which should fix it
    print("\n3. Calling move.advance(enemy)...")
    test_move.advance(enemy)
    print(f"   After advance() user type: {type(test_move.user)}")
    print(f"   After advance() user value: {test_move.user}")

    # Verify the fix
    print("\n4. Verification:")
    if isinstance(test_move.user, str):
        print("   [FAIL] user is still a string!")
    else:
        print("   [SUCCESS] user was fixed to an NPC object!")
        if hasattr(test_move.user, 'name'):
            print(f"   [OK] User has name attribute: {test_move.user.name}")
        if hasattr(test_move.user, 'damage'):
            print(f"   [OK] User has damage attribute: {test_move.user.damage}")

    print("\n" + "=" * 60)

except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
