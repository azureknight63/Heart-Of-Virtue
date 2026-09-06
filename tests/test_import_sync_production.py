"""Guard: the production import path yields no bare<->src module duplication.

This must run in a SUBPROCESS so it exercises the real production entry
sequence rather than pytest's. (An earlier revision of this docstring said
tests/conftest.py installs a bare<->src aliasing hook that the subprocess
escapes; it does not, and has not since every local import moved to the
canonical `src.` path -- conftest.py:1-3 says so explicitly.)
The subprocess reproduces that entry sequence (project root on
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
# Anti-vacuity: if booting the app didn't actually pull these modules in, the
# duplication check above proves nothing. Report what was really loaded so the
# parent test can insist the import graph was exercised.
not_loaded = [m for m in critical if f"src.{m}" not in sys.modules]
player = sm.get_player(sid)
# Live-object provenance: real engine instances the API hands out must come
# from the canonical src.* modules, not bare twins.
print("DUPLICATED:" + ",".join(bad))
print("BARE_ONLY:" + ",".join(bare_loaded))
print("NOT_LOADED:" + ",".join(not_loaded))
print("LIVE_MODULES:" + ",".join(sorted({
    type(player).__module__,
    type(player.universe).__module__,
    type(player.inventory[0]).__module__,
})))
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

    def _field(prefix):
        line = next((ln for ln in out.splitlines() if ln.startswith(prefix)), None)
        assert line is not None, (
            f"subprocess never reported {prefix} — it died before finishing "
            f"(returncode {proc.returncode}).\n--- subprocess output ---\n{out}"
        )
        return line[len(prefix):]

    dup = _field("DUPLICATED:")
    bare = _field("BARE_ONLY:")
    not_loaded = _field("NOT_LOADED:")
    live_modules = _field("LIVE_MODULES:").split(",")

    # The guard is only meaningful if booting the app really imported the whole
    # engine graph; an empty graph would make the duplication check vacuous.
    assert not_loaded == "", (
        "Booting the production entry point did not import these critical "
        f"modules, so the duplication check is vacuous: {not_loaded}"
    )
    # ...and the live objects the API hands out must carry canonical classes.
    assert live_modules == ["src.items", "src.player", "src.universe"], (
        f"live engine objects resolved from non-canonical modules: {live_modules}"
    )

    assert proc.returncode == 0, (
        "Critical API/engine modules are duplicated (bare vs src.) or loaded "
        f"bare in the production import path: DUPLICATED:{dup} BARE_ONLY:{bare}\n"
        f"--- subprocess output ---\n{out}"
    )
