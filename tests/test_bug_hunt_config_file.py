"""tools/bug_hunt.py runs with the shell's CONFIG_FILE, never .env's (#699).

bug_hunt.py loads ``.env`` as a side effect of importing ``tests.llm_doubles``
(-> ``ai.llm_client`` -> ``load_project_env()``). ``blank_outbound_env()``
leaves CONFIG_FILE alone because every conftest overrides it -- but bug_hunt is
not a conftest, so a developer's manual-QA ``CONFIG_FILE`` in ``.env`` silently
chose which game config every scenario ran against.

The shell's value still has to win: ``/combat-test`` and the acceptance
scaffolds run ``CONFIG_FILE=config_combat_testing.ini python tools/bug_hunt.py``
on purpose. So the harness snapshots CONFIG_FILE before ``.env`` loads and
assigns the snapshot (or ``""``) back afterwards.
"""

import contextlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.harness.reporter import BugCategory, BugReport, BugSeverity

ROOT = Path(__file__).resolve().parent.parent


@contextlib.contextmanager
def _imported_bug_hunt():
    """Yield tools.bug_hunt with os.environ exactly as it was on entry, after.

    Its module body blanks the outbound credentials and assigns CONFIG_FILE --
    right for the harness process, a leak into every later test file on this
    xdist worker when done at this module's collection. So the import is lazy
    and the whole environment is restored, not just the keys known today.
    """
    saved = dict(os.environ)
    try:
        yield importlib.import_module("tools.bug_hunt")
    finally:
        os.environ.clear()
        os.environ.update(saved)


@pytest.fixture
def bug_hunt():
    with _imported_bug_hunt() as module:
        yield module


class TestHarnessConfigFileHelper:
    def test_the_shells_value_is_kept(self, bug_hunt):
        assert bug_hunt._harness_config_file("config_combat_testing.ini") == (
            "config_combat_testing.ini"
        )

    def test_an_absent_value_becomes_empty_not_none(self, bug_hunt):
        # "" rather than unset: session_manager defaults an *unset*
        # CONFIG_FILE to config_dev.ini, and load_dotenv(override=False)
        # refills a popped key -- an assigned "" survives both.
        assert bug_hunt._harness_config_file(None) == ""

    def test_an_empty_value_stays_empty(self, bug_hunt):
        assert bug_hunt._harness_config_file("") == ""


def _bug():
    return BugReport(
        title="t",
        severity=BugSeverity.LOW,
        category=BugCategory.CRASH,
        scenario="combat",
        endpoint="/x",
        method="GET",
        expected="e",
        actual="a",
    )


class TestTheResolvedConfigIsRecorded:
    def test_headless_summary_names_the_config(self, bug_hunt, capsys):
        bug_hunt._print_summary([_bug()], True, "config_combat_testing.ini")
        out = json.loads(capsys.readouterr().out)
        assert out["config_file"] == "config_combat_testing.ini"

    def test_each_output_bug_names_the_config(self, bug_hunt):
        dicts = bug_hunt._bug_dicts([_bug()], "config_combat_testing.ini")
        assert dicts[0]["config_file"] == "config_combat_testing.ini"
        # Backward compatible: every field the fix-agent prompt reads survives.
        assert dicts[0]["severity"] == "low"
        assert dicts[0]["scenario"] == "combat"


# Runs bug_hunt.py's module body in a fresh interpreter with .env redirected at
# a temp file. ENV_PATH is read by load_project_env() at call time, so every
# real load site (ai.llm_client, src.api.db, rate_limiter) goes through the
# real python-dotenv against that file -- the .env case is the real path, not
# a stub of it.
_PROBE = """
import importlib.util, json, os, sys
sys.path.insert(0, sys.argv[1])
import src.env_bootstrap as eb
from pathlib import Path
eb.ENV_PATH = Path(sys.argv[2])

spec = importlib.util.spec_from_file_location("_probe_bug_hunt", sys.argv[1] + "/tools/bug_hunt.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["_probe_bug_hunt"] = mod
spec.loader.exec_module(mod)

# Any later load (db.py and friends at create_app time) must not refill it.
eb.load_project_env()
print("PROBE_RESULT " + json.dumps({"config_file": os.environ.get("CONFIG_FILE")}))
"""


def _probe_env(tmp_path, shell_value):
    """(child env, redirected .env path): .env sets CONFIG_FILE, and the
    shell sets it to ``shell_value`` -- or leaves it unset for None."""
    dotenv = tmp_path / "probe.env"
    dotenv.write_text("CONFIG_FILE=config_from_dotenv.ini\n")
    env = dict(os.environ)
    env.pop("CONFIG_FILE", None)
    if shell_value is not None:
        env["CONFIG_FILE"] = shell_value
    return env, dotenv


def _run_probe(tmp_path, shell_value):
    env, dotenv = _probe_env(tmp_path, shell_value)
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE, str(ROOT), str(dotenv)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
        timeout=300,
    )
    for line in completed.stdout.splitlines():
        if line.startswith("PROBE_RESULT "):
            return json.loads(line[len("PROBE_RESULT "):])["config_file"]
    raise AssertionError(
        "probe produced no result\nstdout:\n%s\nstderr:\n%s"
        % (completed.stdout[-4000:], completed.stderr[-4000:])
    )


class TestDotenvCannotChooseTheConfig:
    def test_the_probe_is_not_vacuous(self, tmp_path):
        """Without bug_hunt in the way, the redirected .env really does set
        CONFIG_FILE -- otherwise the next test would pass on a no-op."""
        env, dotenv = _probe_env(tmp_path, None)
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]);"
            "import os, src.env_bootstrap as eb; from pathlib import Path;"
            "eb.ENV_PATH = Path(sys.argv[2]); eb.load_project_env();"
            "print(os.environ.get('CONFIG_FILE'))"
        )
        out = subprocess.run(
            [sys.executable, "-c", code, str(ROOT), str(dotenv)],
            capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=60,
        ).stdout.strip()
        assert out == "config_from_dotenv.ini"

    def test_absent_in_the_shell_means_empty_even_when_dotenv_sets_it(self, tmp_path):
        assert _run_probe(tmp_path, None) == ""

    def test_the_shells_value_beats_dotenv(self, tmp_path):
        assert _run_probe(tmp_path, "config_combat_testing.ini") == (
            "config_combat_testing.ini"
        )


# Importing this test module must not touch os.environ: pytest imports it at
# collection, in an xdist worker every later file shares, so anything it sets
# leaks into them (an unset CONFIG_FILE assigned "" disables session_manager's
# config_dev.ini default). Fresh interpreter, because by the time any
# in-process test here could snapshot, collection has already leaked.
_ENV_PROBE = """
import importlib, json, os, sys
sys.path.insert(0, sys.argv[1])
before = dict(os.environ)
t = importlib.import_module("tests.test_bug_hunt_config_file")
after_import = dict(os.environ)
helper = getattr(t, "_imported_bug_hunt", None)
if helper is not None:
    with helper() as mod:
        assert mod.__name__ == "tools.bug_hunt"
after_helper = dict(os.environ)

def diff(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))

# Key names only -- never values, which can be .env secrets.
print("ENV_PROBE " + json.dumps({
    "import": diff(before, after_import),
    "helper": diff(before, after_helper),
    "has_helper": helper is not None,
}))
"""


class TestImportingThisModuleLeavesTheEnvironmentAlone:
    def test_collection_and_the_fixture_restore_os_environ(self):
        completed = subprocess.run(
            [sys.executable, "-c", _ENV_PROBE, str(ROOT)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=300,
        )
        lines = [
            ln for ln in completed.stdout.splitlines()
            if ln.startswith("ENV_PROBE ")
        ]
        assert lines, completed.stderr[-4000:]
        result = json.loads(lines[-1][len("ENV_PROBE "):])
        assert result["import"] == [], "collection changed: %s" % result["import"]
        assert result["has_helper"]
        assert result["helper"] == [], "fixture leaked: %s" % result["helper"]
