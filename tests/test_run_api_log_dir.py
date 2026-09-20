"""Guard: tools/run_api.py's LOG_JSONL_DIR default is production-safe.

Must run in a SUBPROCESS: run_api.py sets the env var and imports
src.api.config at module level, and each FLASK_ENV value needs a clean
process to observe the guard without cross-test env pollution.

The subprocess stubs ``src.api.app`` and ``src.api.config`` before exec'ing
run_api.py. That is safe, and it is what keeps these tests deterministic:
the LOG_JSONL_DIR guard runs *above* both of those imports in run_api.py, so
it is still exercised for real in a real clean process — only the Flask and
engine stack that the guard never touches is skipped. Importing that stack
cold was slow enough on a loaded machine to blow a 30s timeout, so this file
failed intermittently under ``-n auto`` while passing in isolation -- and a
non-deterministic baseline makes a real regression easy to wave through as
"probably the flaky log test".

Closing the fail-open paths is the other half. The child starts WITHOUT
``LOG_JSONL_DIR`` and ``FLASK_ENV`` from the parent's environment, and
``src.env_bootstrap`` is stubbed too: ``run_api.py`` calls
``load_project_env()`` before the guard, and ``load_dotenv(override=False)``
refills any absent key from a developer's ``.env``. Either way the variable
could arrive already set, and a deleted guard would then pass the "defaults
on" tests. Those tests also assert the exact default path, not merely "set".
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
# And the .env loader, which runs ABOVE the guard: a developer's .env would
# otherwise refill LOG_JSONL_DIR or FLASK_ENV that _probe deliberately removed.
_env = types.ModuleType("src.env_bootstrap")
_env.load_project_env = lambda *a, **k: False
sys.modules["src.env_bootstrap"] = _env

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


#: What the guard sets when it applies (run_api.py's own default).
_DEFAULT_DIR = _ROOT / "logs" / "backend"


def _probe(flask_env):
    env = {
        k: v for k, v in os.environ.items() if k not in ("LOG_JSONL_DIR", "FLASK_ENV")
    }
    if flask_env:
        env["FLASK_ENV"] = flask_env
    # src/api/config.py's SECRET_KEY and ENCRYPTION_KEY guards used to need
    # satisfying here for the production case. They no longer do: that module
    # is stubbed above, and the guard under test runs before it is imported.
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(_ROOT)],
        capture_output=True,
        text=True,
        cwd=str(_ROOT),
        env=env,
        timeout=_PROBE_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


def test_log_jsonl_dir_defaults_on_in_development():
    assert Path(_probe("development")) == _DEFAULT_DIR


def test_log_jsonl_dir_defaults_on_when_flask_env_unset():
    assert Path(_probe(None)) == _DEFAULT_DIR


def test_log_jsonl_dir_stays_unset_in_production():
    # A copied/shared .env carrying FLASK_ENV=production must not silently
    # turn on per-request synchronous file writes + DEBUG-level capture —
    # the same failure shape as the project's documented GITHUB_TOKEN leak.
    assert _probe("production") == "<unset>"
