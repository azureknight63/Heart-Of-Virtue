"""Start one backend + one Vite dev server pair for live QA and keep them alive.

    python start_stack.py --tag full --api-port 5001 --vite-port 3001 --config config_qa_beta_full.ini

Run it in the background (Bash run_in_background). It prints a READY line once
both servers answer and the SPA bundle is warm; killing the process (or its API
child) tears both down. Logs land in <root>/logs/qa/<tag>/{api,vite}.log.

The Vite port must be one the backend accepts as a Socket.IO origin
(Config.CORS_ORIGINS in src/api/config.py — 3000 and 3001 today). Any other
port still serves the SPA and every REST call, but Chrome sends Origin on
same-origin POSTs, so engineio rejects every Socket.IO polling POST with 400
and combat streaming silently dies. Two testers and a reviewer burned their
budgets on that once; the guard below refuses unless --allow-any-port.

Env for Vite is passed through Python on purpose: Git Bash rewrites
VITE_API_URL=/games/HeartOfVirtue/api into a C:/Program Files/Git/... path.

Pass --no-llm for a scripted-only run: it forces all three LLM gates off in the
backend's environment so the run cannot spend provider tokens whatever `.env`
says (it ships two of them enabled). It is opt-in rather than the default so an
LLM-dialogue run needs no extra flag; qa_api.py's banner prints the resolved
values either way, so check there rather than trusting the command line.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4])
HERE = Path(__file__).resolve().parent


def venv_python() -> str:
    for cand in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if cand.exists():
            return str(cand)
    return sys.executable


def npm_cmd() -> str:
    return shutil.which("npm.cmd") or shutil.which("npm") or "npm"


def accepted_origins():
    sys.path.insert(0, str(ROOT))
    try:
        from src.api.config import Config
        return list(Config.CORS_ORIGINS)
    except Exception as exc:  # pragma: no cover - diagnostics only
        print(f"[stack] could not read CORS_ORIGINS: {exc}", flush=True)
        return []


def kill_tree(proc):
    if proc and proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def wait_for(url, name, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(url, timeout=3).status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1)
    print(f"[stack] {name} not ready after {timeout}s: {url}", flush=True)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="short name; logs go to logs/qa/<tag>/")
    ap.add_argument("--api-port", type=int, required=True)
    ap.add_argument("--vite-port", type=int, required=True)
    ap.add_argument("--config", required=True, help="game config .ini, relative to the repo root")
    ap.add_argument("--allow-any-port", action="store_true",
                    help="skip the accepted-origin guard (you will lose Socket.IO)")
    ap.add_argument("--no-llm", action="store_true",
                    help="force every LLM gate off so a scripted-only run cannot spend "
                         "provider tokens, whatever .env says")
    args = ap.parse_args()

    origins = accepted_origins()
    origin = f"http://localhost:{args.vite_port}"
    if origins and origin not in origins and not args.allow_any_port:
        raise SystemExit(
            f"[stack] {origin} is not in Config.CORS_ORIGINS {origins}; Socket.IO would 400 on "
            f"every polling POST and combat streaming would die. Pick an accepted port or pass "
            f"--allow-any-port if you really only need REST."
        )
    if not (ROOT / args.config).exists():
        raise SystemExit(f"[stack] config not found: {ROOT / args.config}")

    logdir = ROOT / "logs" / "qa" / args.tag
    logdir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update({
        "PORT": str(args.api_port),
        "CONFIG_FILE": args.config,
        "QA_TAG": args.tag,
        "FLASK_ENV": "testing",
        "GITHUB_TOKEN": "",
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "HOV_QA_ROOT": str(ROOT),
        "LOG_JSONL_DIR": str(logdir / "backend"),
        # Same-origin through the Vite proxy, exactly like production; process
        # env beats frontend/.env.development, which points absolutely at :5000.
        "HOV_API_PROXY_TARGET": f"http://localhost:{args.api_port}",
        "VITE_API_URL": "/games/HeartOfVirtue/api",
    })
    if args.no_llm:
        # Assignments, not pops: load_project_env uses override=False, so a
        # popped key gets refilled from .env (which ships NPC_CHAT_LLM_ENABLED=1
        # and MYNX_LLM_ENABLED=1) and the run would quietly bill OpenRouter.
        #
        # All three are needed because they gate three different consumers, not
        # because one falls through to another:
        #   NPC_CHAT_LLM_ENABLED -> NPC chat (src/api/serializers/npc_serializer.py)
        #   MYNX_LLM_ENABLED     -> the Mynx adapter (src/npc/_llm.py:161)
        #   COMBAT_LLM_ENABLED   -> the Tactical Advisor (ai/combat_strategist.py)
        # The advisor's gate is ("COMBAT_LLM_ENABLED", "MYNX_LLM_ENABLED") and
        # resolves to the first non-empty value, so COMBAT_LLM_ENABLED="0" alone
        # would silence the advisor -- but MYNX_LLM_ENABLED="0" is still required
        # to stop the Mynx adapter, which reads only its own variable. Do not
        # "simplify" this to one key.
        env.update({
            "NPC_CHAT_LLM_ENABLED": "0",
            "MYNX_LLM_ENABLED": "0",
            "COMBAT_LLM_ENABLED": "0",
        })

    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    api_log = open(logdir / "api.log", "ab")
    vite_log = open(logdir / "vite.log", "ab")
    api = subprocess.Popen([venv_python(), str(HERE / "qa_api.py")], cwd=str(ROOT), env=env,
                           stdout=api_log, stderr=subprocess.STDOUT, creationflags=flags)
    vite = subprocess.Popen([npm_cmd(), "run", "dev", "--", "--port", str(args.vite_port), "--strictPort"],
                            cwd=str(ROOT / "frontend"), env=env, stdout=vite_log,
                            stderr=subprocess.STDOUT, creationflags=flags)
    try:
        api_url = f"http://localhost:{args.api_port}"
        fe_url = f"http://localhost:{args.vite_port}/games/HeartOfVirtue/"
        if not (wait_for(f"{api_url}/health", "API") and wait_for(fe_url, "Vite")):
            raise SystemExit(1)
        for _ in range(20):  # pre-warm the bundle so the first navigation doesn't race the compile
            try:
                if ".js" in requests.get(fe_url, timeout=10).text:
                    break
            except Exception:
                pass
            time.sleep(2)
        print(f"READY tag={args.tag} api={api_url} frontend={fe_url} config={args.config} logs={logdir}",
              flush=True)
        while True:
            time.sleep(5)
            for name, p in (("api", api), ("vite", vite)):
                if p.poll() is not None:
                    print(f"[stack] {name} exited with {p.returncode}; shutting down", flush=True)
                    raise SystemExit(1)
    finally:
        kill_tree(vite)
        kill_tree(api)


if __name__ == "__main__":
    main()
