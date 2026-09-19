"""Guard: tools/run_api.py's LOG_JSONL_DIR default is production-safe.

Must run in a SUBPROCESS: run_api.py sets the env var and imports
src.api.config at module level, and each FLASK_ENV value needs a clean
process to observe the guard without cross-test env pollution.

The subprocess stubs ``src.api.app`` and ``src.api.config`` before exec'ing
run_api.py. That is safe, and it is what keeps these tests deterministic:
the LOG_JSONL_DIR guard runs *above* both of those imports in run_api.py, so
it is still exercised for real in a real clean process — only the Flask and
engine stack that the guard never touches is skipped. Importing that stack
cold costs ~60s on a loaded machine, which is how this file used to blow a
30s timeout and fail intermittently under ``-n auto`` while passing in
isolation. A non-deterministic baseline is worse than a slow one: CLAUDE.md
tells contributors that anything beyond the four known ``openai`` failures is
theirs, so a real regression in a parallel run was easy to wave through as
"probably the flaky log test".

Nothing here can fail *open* if the guard is later moved or deleted. The two
"defaults on" tests assert the variable is set, and the stubs do not set it —
so a guard that stops running, including one relocated into a stubbed module,
fails them.
"""

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

#: Generous because a Python interpreter spawn can still be slow under a
#: saturated ``-n auto`` run; the probe's own work is ~2s now that the engine
#: import is stubbed out. Anything approaching this really is a hang.
_PROBE_TIMEOUT_SECONDS = 120

_SCRIPT = """
import os, sys, types, importlib.util
root = sys.argv[1]
sys.path.insert(0, root)

# Stub the two modules run_api.py imports BELOW the LOG_JSONL_DIR guard. The
# guard is what this file tests and it has already run by the time these are
# reached, so stubbing them changes nothing about what is measured -- it only
# skips importing Flask, the engine and the LLM modules, which is the entire
# cost of this probe.
_app = types.ModuleType("src.api.app")
_app.create_app = lambda *a, **k: None
_cfg = types.ModuleType("src.api.config")
_cfg._env_flag = lambda *a, **k: False
_cfg.config_for_env = lambda *a, **k: None
_cfg.normalized_env = lambda *a, **k: "development"
sys.modules["src.api.app"] = _app
sys.modules["src.api.config"] = _cfg

spec = importlib.util.spec_from_file_location(
    "_run_api_probe", root + "/tools/run_api.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(os.environ.get("LOG_JSONL_DIR", "<unset>"))
"""


def _probe(flask_env):
    env = {"FLASK_ENV": flask_env} if flask_env else {}
    # src/api/config.py's SECRET_KEY and ENCRYPTION_KEY guards used to need
    # satisfying here for the production case. They no longer do: that module
    # is stubbed above, and the guard under test runs before it is imported.
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(_ROOT)],
        capture_output=True,
        text=True,
        cwd=str(_ROOT),
        env={**os.environ, **env},
        timeout=_PROBE_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


def test_log_jsonl_dir_defaults_on_in_development():
    assert _probe("development") != "<unset>"


def test_log_jsonl_dir_defaults_on_when_flask_env_unset():
    assert _probe(None) != "<unset>"


def test_log_jsonl_dir_stays_unset_in_production():
    # A copied/shared .env carrying FLASK_ENV=production must not silently
    # turn on per-request synchronous file writes + DEBUG-level capture —
    # the same failure shape as the project's documented GITHUB_TOKEN leak.
    assert _probe("production") == "<unset>"
