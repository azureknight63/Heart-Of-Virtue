"""Guard: the production import path yields no bare<->src module duplication.

This must run in a SUBPROCESS. In-process, tests/conftest.py installs a
bare<->src aliasing hook, which would mask the very split this guards against.
The subprocess reproduces the real production entry sequence (project root on
sys.path, no sync hook — src/import_sync.py was retired once every local
import moved to the canonical `src.` path) and asserts the critical API/engine
boundary modules resolve to a single object.
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

# Reproduce the production entry point (wsgi.py / tools/run_api.py): project
# root only on sys.path, no import-sync hook.
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
# A bare copy existing at all (even without a src.* twin) means some code path
# still imports outside the canonical src.* namespace.
bare_loaded = [m for m in critical if m in sys.modules and f"src.{m}" not in sys.modules]
print("DUPLICATED:" + ",".join(bad))
print("BARE_ONLY:" + ",".join(bare_loaded))
sys.exit(1 if (bad or bare_loaded) else 0)
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
    bare_line = next((ln for ln in out.splitlines() if ln.startswith("BARE_ONLY:")), "")
    assert proc.returncode == 0, (
        "Critical API/engine modules are duplicated (bare vs src.) or loaded "
        f"bare in the production import path: {dup_line} {bare_line}\n"
        f"--- subprocess output ---\n{out}"
    )
