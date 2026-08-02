"""Thin compatibility shim.

The map editor's implementation was split out of this file into the
utils/mapgen/ package (see utils/mapgen/__init__.py for the module
breakdown and rationale). This file exists only so that:

  - `python utils/map_generator.py` (the documented entry point in
    .github/copilot-instructions.md and the map-design skill) keeps working
    unchanged, and
  - `import utils.map_generator` / `importlib.import_module("utils.map_generator")`
    (used throughout tests/test_map_generator_*.py and
    tests/test_map_placeholders.py) keeps resolving every name it used to,
    unchanged.

Do not add new code here -- it belongs in utils/mapgen/.
"""
import os
import sys

# When this file is run directly (`python utils/map_generator.py`), Python
# puts this script's own directory (utils/) at the front of sys.path, NOT
# the project root -- so `from utils.mapgen import *` below would fail to
# resolve `utils` as a package (there is no utils/utils/) unless the
# project root is added first. utils.mapgen.constants does this same
# bootstrap for every other import path (`import utils.map_generator`,
# pytest, etc.), but this file can't rely on that yet -- it's the reason
# `import utils.mapgen` is reachable at all in the direct-script case.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from utils.mapgen import *  # noqa: F401,F403

# Do NOT remove this section; needed for testing the MapEditor directly
if __name__ == "__main__":
    root = tk.Tk()
    app = MapEditor(root)
    root.mainloop()
