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

import json
import os
import subprocess
import sys
from pathlib import Path

import tools.bug_hunt as bug_hunt
from tools.harness.reporter import BugCategory, BugReport, BugSeverity

ROOT = Path(__file__).resolve().parent.parent


class TestHarnessConfigFileHelper:
    def test_the_shells_value_is_kept(self):
        assert bug_hunt._harness_config_file("config_combat_testing.ini") == (
            "config_combat_testing.ini"
        )

    def test_an_absent_value_becomes_empty_not_none(self):
        # "" rather than unset: session_manager defaults an *unset*
        # CONFIG_FILE to config_dev.ini, and load_dotenv(override=False)
        # refills a popped key -- an assigned "" survives both.
        assert bug_hunt._harness_config_file(None) == ""

    def test_an_empty_value_stays_empty(self):
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
    def test_headless_summary_names_the_config(self, capsys):
        bug_hunt._print_summary([_bug()], True, "config_combat_testing.ini")
        out = json.loads(capsys.readouterr().out)
        assert out["config_file"] == "config_combat_testing.ini"

    def test_each_output_bug_names_the_config(self):
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


def _run_probe(tmp_path, shell_value):
    dotenv = tmp_path / "probe.env"
    dotenv.write_text("CONFIG_FILE=config_from_dotenv.ini\n")
    env = dict(os.environ)
    env.pop("CONFIG_FILE", None)
    if shell_value is not None:
        env["CONFIG_FILE"] = shell_value
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
        dotenv = tmp_path / "probe.env"
        dotenv.write_text("CONFIG_FILE=config_from_dotenv.ini\n")
        env = dict(os.environ)
        env.pop("CONFIG_FILE", None)
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
