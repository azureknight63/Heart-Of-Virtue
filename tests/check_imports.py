import sys
import os

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    print("Importing moves...")
    import moves
    print("Successfully imported moves.")

    print("Importing api.serializers.combat...")
    import api.serializers.combat
    print("Successfully imported api.serializers.combat.")

except Exception as e:
    print(f"Error importing modules: {e}")
    import traceback
    traceback.print_exc()
