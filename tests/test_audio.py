import sys
import traceback

try:
    exec(open('tools/generate_audio.py').read())
except Exception as e:
    print("FULL ERROR:")
    traceback.print_exc()
    sys.exit(1)
