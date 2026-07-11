import sys
import os

# Add src to python path

try:
    print("Importing moves...")
    import src.moves as moves
    print("Successfully imported moves.")

    print("Importing api.serializers.combat...")
    import src.api.serializers.combat
    print("Successfully imported api.serializers.combat.")

except Exception as e:
    print(f"Error importing modules: {e}")
    import traceback
    traceback.print_exc()
