import sys
import os
import pickle

sys.path.append(os.path.abspath('src'))

with open("autosave1.sav", "rb") as f:
    try:
        raw = f.read()
    except Exception as e:
        print(f"Error reading: {e}")
        sys.exit(1)

# Print the first 200 chars of raw for debugging
print("File size:", len(raw), "bytes")
print("First 200 bytes (repr):", repr(raw[:200]))
