# Ensure src.functions is imported under its canonical package path so coverage hooks it.
import sys, os, pathlib
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import src.functions as _functions  # noqa: F401
# Alias plain module name used elsewhere to canonical module for consistent coverage
sys.modules.setdefault('functions', _functions)
