"""Guard: tools/run_api.py's LOG_JSONL_DIR default is production-safe.

Must run in a SUBPROCESS: run_api.py sets the env var and imports
src.api.config at module level, and each FLASK_ENV value needs a clean
process to observe the guard without cross-test env pollution.
"""

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

_SCRIPT = """
import os, sys, importlib.util
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "_run_api_probe", sys.argv[1] + "/tools/run_api.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(os.environ.get("LOG_JSONL_DIR", "<unset>"))
"""


def _probe(flask_env):
    env = {"FLASK_ENV": flask_env} if flask_env else {}
    if flask_env == "production":
        # src/api/config.py fails closed without this in production; not
        # what this test is about, just satisfying that unrelated guard.
        env["SECRET_KEY"] = "test-secret-not-real"
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(_ROOT)],
        capture_output=True,
        text=True,
        cwd=str(_ROOT),
        env={**os.environ, **env},
        timeout=30,
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
