"""``src/env_bootstrap.py`` — the ``.env`` load both process entry points share.

Why this file exists
--------------------
Nothing tested this at all. ``grep -rln "run_api" tests/`` found one
import-sync test and nothing else, so the ``.env`` resolution that decides
whether the API boots with the project's settings or with none of them was
entirely unguarded — in the module that exists *because* the two entry points'
hand-rolled copies had already diverged (S14: ``tools/run_api.py`` grew an
explicit-path reload while ``wsgi.py``, the gunicorn entry point, kept the bare
``load_dotenv()`` whose failure mode the reload exists to fix).

Two properties are load-bearing and both fail silently when broken:

1. The path is resolved from ``__file__``, not from the working directory. A
   bare ``load_dotenv()`` calls ``find_dotenv()``, which walks up from
   ``os.getcwd()``; a process started from anywhere but the project root then
   loads nothing, with no error and no log line, and boots with default
   settings that look deliberate.
2. ``override=False``. An explicitly-set process variable is the set the
   operator set on purpose, so the file fills gaps and never wins — that is
   what makes ``MYNX_LLM_ENABLED=0 python tools/run_api.py`` mean what it says
   even when ``.env`` says ``1``.

Every test here drives ``load_dotenv`` through a stub, so no real ``.env`` is
read and no credential from the developer's machine reaches the assertions.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from src import env_bootstrap
from tests.llm_doubles import child_env


REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestPathResolution:
    def test_project_root_is_derived_from_this_module_not_the_cwd(self):
        # src/env_bootstrap.py -> src -> <repo>
        assert env_bootstrap.PROJECT_ROOT == REPO_ROOT
        assert env_bootstrap.ENV_PATH == REPO_ROOT / ".env"

    def test_the_env_file_is_loaded_by_absolute_path(self, monkeypatch, tmp_path):
        """The whole point: an absolute path cannot be missed by a process
        started from another directory."""
        seen = {}

        def fake_load_dotenv(path=None, override=False):
            seen["path"] = path
            seen["override"] = override
            return True

        env_file = tmp_path / ".env"
        env_file.write_text("SOME_KEY=value\n", encoding="utf-8")
        monkeypatch.setattr(env_bootstrap, "ENV_PATH", env_file)
        monkeypatch.setattr(env_bootstrap, "load_dotenv", fake_load_dotenv)
        monkeypatch.chdir(tmp_path.parent)

        assert env_bootstrap.load_project_env() is True
        assert seen["path"] == env_file
        assert Path(seen["path"]).is_absolute()

    def test_a_missing_env_file_is_reported_rather_than_guessed_at(
        self, monkeypatch, tmp_path
    ):
        called = []
        monkeypatch.setattr(env_bootstrap, "ENV_PATH", tmp_path / "nope.env")
        monkeypatch.setattr(
            env_bootstrap, "load_dotenv", lambda *a, **k: called.append(1)
        )
        assert env_bootstrap.load_project_env() is False
        # No bare fall-through to find_dotenv(): a missing file is a False
        # return, not a silent cwd-relative search.
        assert called == []

    def test_resolution_does_not_change_with_the_working_directory(
        self, monkeypatch, tmp_path
    ):
        first = env_bootstrap.ENV_PATH
        monkeypatch.chdir(tmp_path)
        assert env_bootstrap.ENV_PATH == first

    @pytest.mark.parametrize("override", [False, True])
    def test_override_is_passed_through_verbatim(self, monkeypatch, tmp_path, override):
        seen = {}
        env_file = tmp_path / ".env"
        env_file.write_text("K=v\n", encoding="utf-8")
        monkeypatch.setattr(env_bootstrap, "ENV_PATH", env_file)
        monkeypatch.setattr(
            env_bootstrap,
            "load_dotenv",
            lambda path=None, override=False: seen.update(override=override),
        )
        env_bootstrap.load_project_env(override=override)
        assert seen["override"] is override

    def test_the_default_is_not_to_override(self):
        import inspect

        sig = inspect.signature(env_bootstrap.load_project_env)
        assert sig.parameters["override"].default is False


# ---------------------------------------------------------------------------
# End to end, in a child process
# ---------------------------------------------------------------------------


def _run_child(code, cwd, **env_overrides):
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(cwd),
        env=child_env(**env_overrides),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


class TestFromAnotherWorkingDirectory:
    """The failure S14 describes, reproduced and then guarded.

    Run from a directory that is not the project root, a bare
    ``load_dotenv()`` finds nothing. These drive the real function in a child
    process so the ``sys.path``/``cwd`` interaction is genuine rather than
    monkeypatched away.
    """

    _PROBE = (
        "import sys; sys.path.insert(0, %r)\n"
        "from src.env_bootstrap import ENV_PATH, load_project_env\n"
        "print('ENV_PATH=' + str(ENV_PATH))\n"
        "print('LOADED=' + str(load_project_env()))\n"
    )

    def test_env_path_is_the_repo_env_even_from_a_foreign_cwd(self, tmp_path):
        out = _run_child(self._PROBE % str(REPO_ROOT), cwd=tmp_path)
        assert "ENV_PATH=" + str(REPO_ROOT / ".env") in out

    def test_an_explicitly_set_variable_is_not_overridden_by_the_file(self, tmp_path):
        """``override=False`` is what makes ``VAR=x python tools/run_api.py``
        mean what it says.

        Uses a tmp ``.env`` that genuinely disagrees with the environment, the
        same technique as its sibling below. The previous version asserted that
        ``NPC_CHAT_LLM_ENABLED=0`` and ``LOG_LEVEL=WARNING`` survived the load
        -- but ``child_env`` is what set both, and unless the developer's
        ``.env`` happened to name them with a *different* value the assertion
        held identically under ``override=True``. It proved nothing.
        """
        env_file = tmp_path / ".env"
        env_file.write_text("HOV_BOOTSTRAP_PROBE=from-file\n", encoding="utf-8")
        code = (
            "import os, sys; sys.path.insert(0, %r)\n"
            "from src import env_bootstrap\n"
            "env_bootstrap.ENV_PATH = __import__('pathlib').Path(%r)\n"
            "env_bootstrap.load_project_env()\n"
            "print('VALUE=' + os.environ.get('HOV_BOOTSTRAP_PROBE', '<unset>'))\n"
        ) % (str(REPO_ROOT), str(env_file))
        out = _run_child(code, cwd=tmp_path, HOV_BOOTSTRAP_PROBE="from-process")
        assert "VALUE=from-process" in out

    def test_override_true_does_let_the_file_win(self, tmp_path):
        """The escape hatch exists and works; nothing in the entry points uses
        it, which is why the default is the one that matters."""
        env_file = tmp_path / ".env"
        env_file.write_text("HOV_BOOTSTRAP_PROBE=from-file\n", encoding="utf-8")
        code = (
            "import os, sys; sys.path.insert(0, %r)\n"
            "from src import env_bootstrap\n"
            "env_bootstrap.ENV_PATH = __import__('pathlib').Path(%r)\n"
            "env_bootstrap.load_project_env(override=True)\n"
            "print('VALUE=' + os.environ.get('HOV_BOOTSTRAP_PROBE', '<unset>'))\n"
        ) % (str(REPO_ROOT), str(env_file))
        out = _run_child(code, cwd=tmp_path, HOV_BOOTSTRAP_PROBE="from-process")
        assert "VALUE=from-file" in out


# ---------------------------------------------------------------------------
# Both entry points actually use it
# ---------------------------------------------------------------------------


class TestEntryPointsShareTheBootstrap:
    """S14: the fix landed in ``run_api.py`` and not in ``wsgi.py`` — the
    gunicorn entry point named in run_api.py's own docstring — so the
    documented failure mode stayed live in production while dev was patched.
    """

    @pytest.mark.parametrize("entry", ["tools/run_api.py", "wsgi.py"])
    def test_the_entry_point_calls_load_project_env(self, entry):
        source = (REPO_ROOT / entry).read_text(encoding="utf-8")
        assert "from src.env_bootstrap import load_project_env" in source
        assert "load_project_env()" in source

    @pytest.mark.parametrize("entry", ["tools/run_api.py", "wsgi.py"])
    def test_no_entry_point_still_calls_bare_load_dotenv(self, entry):
        source = (REPO_ROOT / entry).read_text(encoding="utf-8")
        assert "load_dotenv()" not in source

    @pytest.mark.parametrize("entry", ["tools/run_api.py", "wsgi.py"])
    def test_the_env_load_precedes_the_config_import(self, entry):
        """The ordering still matters, but no longer for the reason it was
        written for: ``src/api/config.py`` used to read SECRET_KEY/FLASK_ENV in
        its CLASS BODY at import time (S15), and those reads have since moved
        into ``runtime_config()``, which runs at ``create_app()`` time.

        What still reads the environment during import is everything the
        ``src.api`` import pulls in behind it — ``src/api/db.py`` (Turso URL and
        auth token), the rate-limiter thresholds, and the LLM modules. Anything
        not in ``os.environ`` by this line is invisible to them.
        """
        source = (REPO_ROOT / entry).read_text(encoding="utf-8")
        assert source.index("load_project_env()") < source.index(
            "from src.api.config import"
        )
