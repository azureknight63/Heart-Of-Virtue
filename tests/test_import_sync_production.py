"""Guard: production module-sync collapses bare<->src duplication.

This must run in a SUBPROCESS. In-process, tests/conftest.py installs its own
bare<->src aliasing hook, which would mask the very split this guards against.
The subprocess reproduces the real production entry sequence (root + src/ on
sys.path, `src.import_sync.install()` before the app loads) and asserts the
critical API/engine boundary modules resolve to a single object.
"""

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# Modules whose classes/state cross the API<->engine boundary. If any of these
# exist as two distinct objects (bare `x` vs `src.x`), isinstance checks and
# module-level registries silently desync in production.
_CRITICAL = [
    "narration",
    "items",
    "objects",
    "events",
    "npc",
    "player",
    "tiles",
    "universe",
    "functions",
    "animations",
    "story",
    "story.effects",
    "inventory_utils",
]

_SCRIPT = """
import sys, pathlib
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))

# Reproduce the production entry point: install the sync BEFORE the app loads.
from src.import_sync import install
install()

# Load the app + exercise a new game so the full engine import graph is pulled
# in (items, objects, npc, player, story, tiles, ...).
from src.api.app import create_app  # noqa: F401
from src.api.services.session_manager import SessionManager
sm = SessionManager()
sid, pid = sm.create_session("guard")
sm.start_new_game(sid)

critical = %r
bad = [
    m for m in critical
    if m in sys.modules
    and f"src.{m}" in sys.modules
    and sys.modules[m] is not sys.modules[f"src.{m}"]
]
print("DUPLICATED:" + ",".join(bad))
sys.exit(1 if bad else 0)
""" % _CRITICAL


def test_critical_modules_not_duplicated_in_production():
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(_ROOT)],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    out = proc.stdout + proc.stderr
    dup_line = next((ln for ln in out.splitlines() if ln.startswith("DUPLICATED:")), "")
    assert proc.returncode == 0, (
        "Critical API/engine modules are duplicated (bare vs src.) in the "
        f"production import path: {dup_line}\n--- subprocess output ---\n{out}"
    )
