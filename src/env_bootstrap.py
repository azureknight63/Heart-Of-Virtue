"""Project-root-relative bootstrap shared by everything that needs ``.env``.

Four modules call :func:`load_project_env`, and a fifth reads
:data:`PROJECT_ROOT`:

* ``tools/run_api.py`` (dev entry point) and ``wsgi.py`` (gunicorn entry
  point) — before importing anything under ``src.``.
* ``src/api/db.py`` and ``ai/llm_client.py`` — at their own import time,
  because they read their settings during import and are reachable from
  processes (pytest, the bug-hunt harness) that never run an entry point.
* ``src/api/app.py`` imports ``PROJECT_ROOT`` rather than recomputing it.

The entry points used to carry their own copy of the load, and the copies had
already diverged: run_api.py grew an explicit-path ``.env`` reload while
wsgi.py — the gunicorn entry point run_api.py's own docstring points at —
kept the bare ``load_dotenv()`` whose failure mode the reload exists to fix.

**Constraint for anyone editing this file: it must import nothing from
``src.`` or ``ai.``.** ``ai/llm_client.py`` imports it, and ``src.api``
imports it, so any local dependency added here becomes an import cycle for one
of them. ``pathlib`` + ``python-dotenv`` is the whole budget. (That rule used
to be documented only in ``ai/llm_client.py``, i.e. in a caller rather than in
the module a contributor would actually be editing when they broke it.
``src/text_safety.py`` follows the same precedent for the same reason.)

Note on ``sys.path``: only the project root goes on it. ``src/`` is
deliberately *not* added — every local import uses the canonical ``src.``
path, and keeping bare names unimportable makes any regression fail loudly
instead of silently duplicating module state (issue #380).
"""

from pathlib import Path

from dotenv import load_dotenv

# src/env_bootstrap.py -> src -> <repo>
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def load_project_env(override=False):
    """Load ``<repo>/.env`` by explicit path. Returns True if the file existed.

    A bare ``load_dotenv()`` resolves ``find_dotenv()`` from the **working
    directory**, so a process started from anywhere but the project root
    silently loads nothing at all and boots with none of the project's
    settings — no error, no log line. Resolving from ``__file__`` cannot miss.

    ``override=False`` is the default on purpose: "already in the
    environment" is exactly the set the operator set deliberately, so the file
    fills gaps and never wins. That is what makes
    ``MYNX_LLM_ENABLED=0 python tools/run_api.py`` mean what it says even when
    ``.env`` says 1.
    """
    if not ENV_PATH.exists():
        return False
    load_dotenv(ENV_PATH, override=override)
    return True
