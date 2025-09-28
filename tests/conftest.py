# Ensure src.functions is imported under its canonical package path so coverage hooks it.
import sys
import src.functions as _functions  # noqa: F401
# Alias plain module name used elsewhere to canonical module for consistent coverage
sys.modules.setdefault('functions', _functions)
