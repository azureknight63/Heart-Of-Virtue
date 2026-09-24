"""qa_api_client.py -- REST client for API tester agents (orchestrate-qa-testers).

API testers play over HTTP with no browser, so they need no Vite port and any
number can share one backend. Introduced for the 2026-09-24 run.

A tester's session outlives each one-shot Bash call: `login` stores the
session token in <RUNS>/<NAME>.session.json and every later call reuses it.
Every request/response is appended to <RUNS>/<NAME>_api.jsonl as evidence.

    python qa_api_client.py NAME login PORT          # fresh test session on http://localhost:PORT
    python qa_api_client.py NAME where               # map, x, y, title, exits, npcs, objects, items, hp, pending
    python qa_api_client.py NAME get /api/world
    python qa_api_client.py NAME post /api/world/move '{"direction": "south"}'
    python qa_api_client.py NAME exec <<'PY'         # multi-line Python with get/post/where/pending/state/log
    r = post("/api/world/move", {"direction": "south"})
    print(r["_status"], r.get("message"))
    PY

Responses are printed as JSON with an extra "_status" (HTTP status). Long
bodies are truncated in the printout (not in the log) unless --full is given.
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests

# Session files and request logs. Default: <repo>/logs/qa/api-runs (logs/ is gitignored);
# HOV_QA_RUNS overrides, e.g. a per-run scratch directory.
ROOT = Path(os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4])
RUNS = Path(os.environ.get("HOV_QA_RUNS") or ROOT / "logs" / "qa" / "api-runs")
RUNS.mkdir(parents=True, exist_ok=True)
PRINT_LIMIT = 6000


def _sess_file(name):
    return RUNS / f"{name}.session.json"


class Client:
    def __init__(self, name):
        self.name = name
        f = _sess_file(name)
        if not f.exists():
            sys.exit(f"no session for {name}: run `login PORT` first")
        d = json.loads(f.read_text())
        self.base = f"http://localhost:{d['port']}"
        self.token = d["token"]
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {self.token}"
        self.log = RUNS / f"{name}_api.jsonl"

    def _rec(self, method, path, payload, status, body):
        with self.log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.strftime("%H:%M:%S"), "m": method, "path": path,
                                 "req": payload, "status": status, "body": body},
                                ensure_ascii=False) + "\n")

    def _call(self, method, path, payload=None):
        # Git Bash's MSYS path conversion turns "/api/x" into
        # "C:/Program Files/Git/api/x" before Python sees it; undo that, and
        # accept "api/x" without the leading slash too.
        if ":/" in path and "/api/" in path:
            path = path[path.index("/api/"):]
        if not path.startswith("/"):
            path = "/" + path
        try:
            if method == "GET":
                r = self.s.get(self.base + path, timeout=60)
            else:
                r = self.s.post(self.base + path, json=payload or {}, timeout=120)
        except requests.RequestException as e:
            self._rec(method, path, payload, None, str(e))
            return {"_status": None, "_error": str(e)}
        try:
            body = r.json()
        except ValueError:
            body = {"_text": r.text[:3000]}
        if not isinstance(body, dict):
            body = {"_body": body}
        self._rec(method, path, payload, r.status_code, body)
        body["_status"] = r.status_code
        return body

    def get(self, path):
        return self._call("GET", path)

    def post(self, path, payload=None):
        return self._call("POST", path, payload)

    def state(self):
        return self.get("/api/full-state")

    def pending(self):
        return self.get("/api/world/events/pending")

    def where(self):
        room = self.get("/api/world").get("room", {}) or {}
        st = (self.state() or {}).get("status", {}) or {}

        def names(seq):
            return [x.get("name") if isinstance(x, dict) else str(x) for x in (seq or [])]
        return {
            "map": room.get("map") or room.get("map_name") or room.get("area"),
            "x": room.get("x"), "y": room.get("y"),
            "title": room.get("title") or room.get("name"),
            "exits": room.get("exits"),
            "npcs": names(room.get("npcs")), "objects": names(room.get("objects")),
            "items": names(room.get("items")),
            "hp": st.get("hp"), "maxhp": st.get("maxhp") or st.get("max_hp"),
            "pending_events": len((self.pending() or {}).get("events", []) or []),
        }


def _show(obj, full):
    s = obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False)
    if not full and len(s) > PRINT_LIMIT:
        s = s[:PRINT_LIMIT] + f"\n... [truncated {len(s) - PRINT_LIMIT} chars; use --full or exec]"
    print(s)


def main():
    argv = [a for a in sys.argv[1:] if a != "--full"]
    full = "--full" in sys.argv
    if len(argv) < 2:
        print(__doc__)
        sys.exit(2)
    name, cmd = argv[0], argv[1]
    if cmd == "login":
        port = int(argv[2])
        username = f"qa_{name}_{uuid.uuid4().hex[:5]}"
        r = requests.post(f"http://localhost:{port}/api/test/session",
                          json={"username": username}, timeout=30)
        r.raise_for_status()
        token = r.json()["session_id"]
        _sess_file(name).write_text(json.dumps({"port": port, "token": token, "username": username}))
        print(f"logged in as {username} on :{port}")
        c = Client(name)
        _show(c.where(), full)
        return
    c = Client(name)
    if cmd == "where":
        _show(c.where(), full)
    elif cmd == "get":
        _show(c.get(argv[2]), full)
    elif cmd == "post":
        payload = json.loads(argv[3]) if len(argv) > 3 else {}
        _show(c.post(argv[2], payload), full)
    elif cmd == "exec":
        code = sys.stdin.read()
        env = {"get": c.get, "post": c.post, "where": c.where, "state": c.state,
               "pending": c.pending, "json": json, "time": time, "re": __import__("re"),
               "show": lambda o: _show(o, full), "client": c}
        exec(compile(code, "<exec>", "exec"), env)
        if "result" in env:
            _show(env["result"], full)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
