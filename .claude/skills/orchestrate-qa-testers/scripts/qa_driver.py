"""qa_driver.py — one persistent Playwright browser, controlled over a local HTTP port.

    python qa_driver.py --name T1 --frontend http://localhost:3001 --api http://localhost:5001 --ctrl 7001 [--headed] [--mobile]

Why this exists: a tester agent only has one-shot Bash, so a Playwright session
cannot live across its tool calls. This process owns the browser and executes
snippets the agent posts to 127.0.0.1:<ctrl>/exec; qa.py is the CLI. It logs in
through the testing-mode session bypass (cookie + localStorage marker, the same
thing tools/inquisitor/browser_layer.py does), lands on the game page, and
records every console error/warning, page error, failed request and 4xx/5xx
response to <outdir>/<name>_events.jsonl — surfaced on the next control call.

Playwright's sync API is single-threaded, so the HTTP handler enqueues and the
main thread executes. Screenshots go to <outdir>/shots/.
"""
import argparse
import contextlib
import io
import json
import os
import queue
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

ROOT = Path(os.environ.get("HOV_QA_ROOT") or Path(__file__).resolve().parents[4])
COOKIE = "hov_session"  # src/api/session_cookie.DEFAULT_COOKIE_NAME
SPA_PATH = "/games/HeartOfVirtue/"
NOISE = (
    "fonts.googleapis.com", "fonts.gstatic.com", "favicon.ico",
    "React Router Future Flag Warning", "React.startTransition",
    "Relative route resolution within Splat routes", "Download the React DevTools",
    "[Report Only]",  # CSP report-only violations: known, tracked in docs/development/csp-rollout.md
    # Headless Chromium has no user gesture, so background music can't autoplay and
    # the bgm fetch is aborted — every session, every tester. Not a game bug.
    "NotAllowedError: play() failed", "/assets/sounds/",
)
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
INNER_TEXT_JS = '() => document.body ? document.body.innerText : ""'


class Driver:
    def __init__(self, a):
        self.a = a
        self.outdir = Path(a.outdir)
        (self.outdir / "shots").mkdir(parents=True, exist_ok=True)
        self.events_path = self.outdir / f"{a.name}_events.jsonl"
        self.events = []
        self.seq = 0
        self.cursor = 0
        self.shot_n = 0
        self.frontend = a.frontend.rstrip("/")
        self.api_base = a.api.rstrip("/")
        self.q = queue.Queue()

    # ---- browser -----------------------------------------------------
    def start(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=not self.a.headed,
                                               args=["--no-sandbox", "--disable-dev-shm-usage"])
        if self.a.mobile:
            ctx = dict(viewport={"width": 375, "height": 812}, device_scale_factor=2,
                       is_mobile=True, has_touch=True, user_agent=MOBILE_UA)
        else:
            ctx = dict(viewport={"width": 1280, "height": 900})
        self.context = self.browser.new_context(**ctx)
        self.page = self.context.new_page()
        self.page.set_default_timeout(10000)
        self.page.on("console", self._on_console)
        self.page.on("pageerror", lambda e: self._rec("pageerror", text=str(e)))
        self.page.on("requestfailed", lambda r: self._rec("requestfailed", url=r.url, method=r.method,
                                                            text=str(r.failure)))
        self.page.on("response", self._on_response)
        self.login()

    def _rec(self, kind, **kw):
        self.seq += 1
        ev = {"seq": self.seq, "ts": time.strftime("%H:%M:%S"), "kind": kind, **kw}
        ev["noise"] = any(n in (ev.get("text", "") + ev.get("url", "")) for n in NOISE)
        self.events.append(ev)
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")

    def _on_console(self, msg):
        if msg.type in ("error", "warning"):
            loc = msg.location or {}
            self._rec("console." + msg.type, text=msg.text,
                      url=loc.get("url", "") if isinstance(loc, dict) else "")

    def _on_response(self, resp):
        if resp.status >= 400:
            body = ""
            try:
                body = resp.text()[:1500]
            except Exception:
                pass
            self._rec("http", url=resp.url, method=resp.request.method, status=resp.status, text=body)

    def login(self):
        username = f"qa_{self.a.name}_{uuid.uuid4().hex[:5]}"
        r = requests.post(f"{self.api_base}/api/test/session", json={"username": username}, timeout=10)
        r.raise_for_status()
        self.token = r.json()["session_id"]
        self.username = username
        self.api = requests.Session()
        self.api.headers["Authorization"] = f"Bearer {self.token}"
        self.context.add_cookies([{"name": COOKIE, "value": self.token, "domain": "localhost",
                                   "path": "/", "httpOnly": True, "sameSite": "Lax"}])
        self.page.goto(self.frontend + SPA_PATH, wait_until="domcontentloaded", timeout=60000)
        # The SPA renders as signed-in from this marker (AuthContext.checkAuth); the
        # cookie is what actually authorises its requests.
        self.page.evaluate(f'localStorage.setItem("username", {json.dumps(username)})')
        self.page.goto(self.frontend + SPA_PATH, wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_timeout(1500)

    # ---- helpers exposed to exec ---------------------------------------
    def text(self):
        return self.page.evaluate(INNER_TEXT_JS)

    def aria(self):
        return self.page.locator("body").aria_snapshot()

    def shot(self, label="shot"):
        self.shot_n += 1
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:60]
        p = self.outdir / "shots" / f"{self.a.name}_{self.shot_n:03d}_{safe}.png"
        self.page.screenshot(path=str(p))
        return str(p)

    def wait(self, ms=500):
        self.page.wait_for_timeout(ms)

    def get(self, path):
        r = self.api.get(self.api_base + path, timeout=30)
        try:
            return r.json()
        except Exception:
            return {"_status": r.status_code, "_text": r.text[:1000]}

    def post(self, path, payload=None):
        r = self.api.post(self.api_base + path, json=payload or {}, timeout=60)
        try:
            return r.json()
        except Exception:
            return {"_status": r.status_code, "_text": r.text[:1000]}

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
            "url": self.page.url,
        }

    def hit_test(self, locator):
        """Raw DOM hit-test for a locator: is the element what a pointer would reach?

        Playwright's actionability check refuses clicks on elements another node
        covers, and an agent will call that "unclickable". Real pointers can still
        reach through (a row container may own the click), so this reports the
        stack at the element's centre so the agent can judge before filing.
        """
        box = locator.first.bounding_box()
        if not box:
            return {"box": None}
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        return locator.first.evaluate(
            """(el, [x, y]) => {
                 const stack = document.elementsFromPoint(x, y);
                 return {top_is_element: document.elementFromPoint(x, y) === el,
                         stack_has_element: stack.includes(el),
                         stack: stack.slice(0, 6).map(e => e.tagName + (e.className ? '.' + String(e.className).slice(0, 30) : '')
                                                          + '|z=' + getComputedStyle(e).zIndex + '|pe=' + getComputedStyle(e).pointerEvents)};
               }""", [cx, cy]) | {"box": {k: round(v) for k, v in box.items()}, "center": (cx, cy)}

    def raw_click(self, locator):
        """Click at the element's centre with a real pointer event (bypasses actionability)."""
        box = locator.first.bounding_box()
        self.page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        return True

    def new_events(self):
        evs = [e for e in self.events[self.cursor:] if not e["noise"]]
        self.cursor = len(self.events)
        return evs

    def all_errors(self):
        return [e for e in self.events if not e["noise"]]

    # ---- exec ----------------------------------------------------------
    def namespace(self):
        return {
            "page": self.page, "context": self.context, "browser": self.browser,
            "api": self.api, "API": self.api_base, "get": self.get, "post": self.post,
            "text": self.text, "aria": self.aria, "shot": self.shot, "wait": self.wait,
            "state": self.state, "where": self.where, "pending": self.pending,
            "hit_test": self.hit_test, "raw_click": self.raw_click,
            "all_errors": self.all_errors, "json": json, "time": time, "re": __import__("re"),
        }

    def run(self, code):
        buf = io.StringIO()
        ns = self.ns
        result, err = None, None
        with contextlib.redirect_stdout(buf):
            try:
                try:
                    compiled = compile(code, "<qa>", "eval")
                except SyntaxError:
                    exec(compile(code, "<qa>", "exec"), ns)
                    result = ns.pop("result", None)
                else:
                    result = eval(compiled, ns)
            except Exception:
                err = traceback.format_exc()[-4000:]
        try:
            json.dumps(result)
        except Exception:
            result = repr(result)
        if isinstance(result, str) and len(result) > 40000:
            result = result[:40000] + "\n...[truncated]"
        return {"ok": err is None, "result": result, "stdout": buf.getvalue()[-30000:],
                "error": err, "url": self.page.url, "new_events": self.new_events()}

    # ---- control loop --------------------------------------------------
    def serve(self):
        driver = self
        driver.ns = driver.namespace()

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def _send(self, obj, status=200):
                data = json.dumps(obj).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path == "/ping":
                    return self._send({"ok": True, "name": driver.a.name, "user": driver.username,
                                       "url": driver.page.url, "frontend": driver.frontend,
                                       "api": driver.api_base})
                self._send({"ok": False, "error": "unknown"}, 404)

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
                if self.path == "/quit":
                    driver.q.put(("quit", None, None))
                    return self._send({"ok": True})
                if self.path != "/exec":
                    return self._send({"ok": False, "error": "unknown"}, 404)
                done = threading.Event()
                box = {}
                driver.q.put((body.get("code", ""), done, box))
                if not done.wait(timeout=float(body.get("timeout", 240))):
                    return self._send({"ok": False, "error": "timeout waiting for browser thread"}, 504)
                self._send(box["r"])

        srv = ThreadingHTTPServer(("127.0.0.1", self.a.ctrl), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"DRIVER READY name={self.a.name} ctrl={self.a.ctrl} user={self.username} "
              f"url={self.page.url} events={self.events_path}", flush=True)
        while True:
            code, done, box = self.q.get()
            if code == "quit":
                break
            try:
                box["r"] = self.run(code)
            except Exception:
                box["r"] = {"ok": False, "error": traceback.format_exc()[-4000:]}
            done.set()
        srv.shutdown()
        with contextlib.suppress(Exception):
            self.browser.close()
            self.pw.stop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--frontend", required=True)
    ap.add_argument("--api", required=True)
    ap.add_argument("--ctrl", type=int, required=True)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--mobile", action="store_true")
    ap.add_argument("--outdir", default=str(ROOT / "logs" / "qa" / "runs"))
    a = ap.parse_args()
    d = Driver(a)
    d.start()
    d.serve()


if __name__ == "__main__":
    main()
