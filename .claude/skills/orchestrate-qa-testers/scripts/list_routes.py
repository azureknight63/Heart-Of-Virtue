"""Print the API's real route table, for pasting into a tester primer.

The 2026-09-24 primer named /api/combat/end and /api/combat/pray (neither
exists; Pray is a move) and a tester filed the 404s. List the routes instead
of writing endpoints from memory:

    cd <worktree root>/.claude/skills/orchestrate-qa-testers/scripts
    PYTHONIOENCODING=utf-8 python list_routes.py /api/combat

(`python` here is the repo venv's interpreter.) Only the routes go to stdout;
create_app's start-up chatter is sent to stderr.
"""

import contextlib

import os
import sys
from pathlib import Path

ROOT = Path(
    os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4]
)
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
# Assign, never pop: load_dotenv(override=False) refills popped keys.
os.environ["GITHUB_TOKEN"] = ""
os.environ["FLASK_ENV"] = "testing"

import logging  # noqa: E402

logging.disable(logging.CRITICAL)

from src.api.app import create_app  # noqa: E402


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else "/api"
    # Git Bash rewrites "/api/x" to "C:/Program Files/Git/api/x"; undo it.
    if ":/" in prefix and "/api" in prefix:
        prefix = prefix[prefix.index("/api"):]
    with contextlib.redirect_stdout(sys.stderr):
        app = create_app()
    app = app[0] if isinstance(app, tuple) else app
    rows = sorted(
        (rule.rule, ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"})))
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith(prefix)
    )
    for path, methods in rows:
        print(f"{methods:<12} {path}")
    print(f"# {len(rows)} routes under {prefix}", file=sys.stderr)


if __name__ == "__main__":
    main()
