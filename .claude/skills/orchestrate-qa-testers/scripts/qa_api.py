"""Reloader-free API launcher for live-QA stacks (orchestrate-qa-testers).

Why not tools/run_api.py: it runs the Werkzeug reloader, and on this Windows
box the reloader child has come up on the wrong interpreter with FLASK_ENV
unset. One process, no reloader, explicit env — nothing to drop.

Environment (start_stack.py sets these): PORT, CONFIG_FILE, QA_TAG, and
optionally HOV_QA_ROOT to point at a different worktree than the one this
skill lives in. The script assigns (never pops) GITHUB_TOKEN="" so the
Feedback button cannot file a real issue, and FLASK_ENV=testing so
/api/test/session exists. dotenv's override=False refills popped keys, which
is why these are assignments.

The LLM gates (NPC_CHAT_LLM_ENABLED, MYNX_LLM_ENABLED, COMBAT_LLM_ENABLED) are
part of that inherited contract but are deliberately NOT forced here:
`start_stack.py --no-llm` puts them in this process's environment, and
override=False then keeps them. Running this script directly inherits whatever
`.env` says -- which ships NPC_CHAT_LLM_ENABLED=1 and MYNX_LLM_ENABLED=1, i.e.
billable. The banner below prints all three, so a run that expected them off
says so on its first line.
"""
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4])
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.env_bootstrap import load_project_env  # noqa: E402

load_project_env()  # override=False: values already in os.environ win

os.environ["GITHUB_TOKEN"] = ""
os.environ["FLASK_ENV"] = "testing"
tag = os.environ.get("QA_TAG", "default")
os.environ.setdefault("LOG_JSONL_DIR", str(ROOT / "logs" / "qa" / tag / "backend"))

from src.api.app import create_app  # noqa: E402
from src.api.config import config_for_env, normalized_env  # noqa: E402

env = normalized_env()
app, socketio = create_app(config_for_env(env))
port = int(os.environ["PORT"])
print(
    f"[qa_api] tag={tag} env={env} port={port} CONFIG_FILE={os.environ.get('CONFIG_FILE')} "
    f"NPC_CHAT_LLM_ENABLED={os.environ.get('NPC_CHAT_LLM_ENABLED')} "
    f"MYNX_LLM_ENABLED={os.environ.get('MYNX_LLM_ENABLED')} "
    f"COMBAT_LLM_ENABLED={os.environ.get('COMBAT_LLM_ENABLED')} "
    f"GITHUB_TOKEN={'blank' if not os.environ.get('GITHUB_TOKEN') else 'SET!'}",
    flush=True,
)
socketio.run(app, host="127.0.0.1", port=port, debug=False, use_reloader=False,
             allow_unsafe_werkzeug=True)
