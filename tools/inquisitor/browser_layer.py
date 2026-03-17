"""Browser layer: Playwright driving the real React + Flask stack.

Auto-starts both servers, runs the full login flow via the browser, then
executes game tool calls through the real API (using the session token
extracted from localStorage) while using Playwright for UI-specific probes
(screenshots, page errors, element clicks, visible text).

Required: pip install playwright && playwright install chromium
"""

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests as http_requests

from tools.inquisitor.game_tools import ToolResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = ROOT / "frontend"
API_URL = "http://localhost:5000"
FRONTEND_URL = "http://localhost:3000"
SERVER_STARTUP_TIMEOUT = 120  # seconds — Vite cold-starts slowly on first run
SCREENSHOT_DIR = ROOT / "tools" / "inquisitor_screenshots"


class BrowserLayer:
    """Executes game tool calls via Playwright + real HTTP requests."""

    def __init__(self, headless: bool = False):
        self._headless = headless
        self._api_process: Optional[subprocess.Popen] = None
        self._vite_process: Optional[subprocess.Popen] = None
        self._pw = None          # playwright instance
        self._browser = None
        self._page = None
        self._token: Optional[str] = None
        self._console_errors: list = []
        self._network_failures: list = []
        self._screenshot_count = 0

        self._session_dir = SCREENSHOT_DIR / datetime.now(timezone.utc).strftime(
            "%Y%m%d_%H%M%S"
        )

        self._start_servers()
        self._start_browser()
        self._login()

    # ------------------------------------------------------------------
    # Layer contract
    # ------------------------------------------------------------------

    def get_initial_state(self) -> str:
        result = self._call_get_game_state()
        return json.dumps(result.data, indent=2)

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> ToolResult:
        handler = getattr(self, f"_call_{tool_name}", None)
        if handler is None:
            return ToolResult.err(f"Unknown tool: {tool_name}")

        try:
            return handler(**inputs)
        except Exception as exc:
            return ToolResult.server_error(str(exc), f"Unhandled exception in {tool_name}")

    def teardown(self):
        """Clean up browser and servers."""
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

        for proc in (self._vite_process, self._api_process):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def _free_port(port: int):
        """Kill any process listening on *port* so we start with a clean slate.

        Uses ``fuser`` (Linux) and falls back to ``lsof`` (macOS/BSD).  Errors
        are silently ignored — if neither tool is available the server will
        simply fail to bind and raise a clear error at startup.
        """
        for cmd in (
            ["fuser", "-k", f"{port}/tcp"],
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
        ):
            try:
                result = subprocess.run(
                    cmd, capture_output=True, timeout=5
                )
                if result.returncode == 0 and cmd[0] == "lsof":
                    # lsof just prints PIDs; kill them
                    for pid in result.stdout.decode().split():
                        subprocess.run(
                            ["kill", "-9", pid.strip()],
                            capture_output=True,
                        )
                break  # stop after first tool that exists on this OS
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        time.sleep(0.5)  # give the OS a moment to reclaim the port

    def _start_servers(self):
        """Start Flask API and Vite dev server as subprocesses.

        Clears ports 5000 and 3000 first so a crashed previous run never
        blocks this one.
        """
        self._free_port(5000)
        self._free_port(3000)

        env = os.environ.copy()
        # Use testing config so the /api/test/session bypass endpoint is active
        # and no database credentials are required for auth.
        env["FLASK_ENV"] = "testing"
        env["MYNX_LLM_ENABLED"] = "0"

        self._api_process = subprocess.Popen(
            [sys.executable, str(ROOT / "tools" / "run_api.py")],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        npm_bin = "npm"
        self._vite_process = subprocess.Popen(
            [npm_bin, "run", "dev"],
            cwd=str(FRONTEND_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self._wait_for_server(f"{API_URL}/health", "Flask API")
        self._wait_for_server(FRONTEND_URL, "Vite frontend")

        # Pre-warm Vite: trigger the JS bundle compile with a plain HTTP
        # request before opening the browser.  Without this, the first
        # browser navigation races against the compile and can time out.
        self._prewarm_vite()

    def _prewarm_vite(self):
        """Fetch the Vite root URL repeatedly until the JS bundle is compiled.

        Vite responds to HTTP requests as soon as it binds the port, but the
        first browser navigation can stall for 15–30 s while it compiles the
        bundle.  Hitting the URL from Python forces the compile to happen *before*
        the browser opens, so navigation is fast and reliable.
        """
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                resp = http_requests.get(FRONTEND_URL, timeout=10)
                # Vite serves HTML immediately; the bundle is done when the
                # response contains a script tag pointing to a compiled asset.
                if "src/main" in resp.text or ".js" in resp.text:
                    return
            except Exception:
                pass
            time.sleep(2)
        # Not fatal — the browser will still try; it just might be slower.

    def _wait_for_server(self, url: str, name: str):
        """Poll a URL until it responds or the timeout is exceeded."""
        deadline = time.time() + SERVER_STARTUP_TIMEOUT
        while time.time() < deadline:
            try:
                resp = http_requests.get(url, timeout=2)
                if resp.status_code < 500:
                    return
            except Exception:
                pass
            time.sleep(1)
        raise RuntimeError(
            f"[inquisitor/browser] {name} did not become ready within "
            f"{SERVER_STARTUP_TIMEOUT}s (url={url})"
        )

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def _start_browser(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                "playwright is required for browser mode. "
                "Install with: pip install playwright && playwright install chromium"
            )

        self._pw = sync_playwright().start()

        # Try the default browser path first; fall back to any cached Chromium
        # build if the expected version isn't installed (e.g. CDN is blocked).
        launch_kwargs: dict = {
            "headless": self._headless,
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
        }
        try:
            self._browser = self._pw.chromium.launch(**launch_kwargs)
        except Exception:
            import glob as _glob
            candidates = sorted(
                _glob.glob(
                    os.path.expanduser(
                        "~/.cache/ms-playwright/chromium-*/chrome-linux/chrome"
                    )
                ),
                reverse=True,  # prefer highest build number
            )
            if not candidates:
                raise
            launch_kwargs["executable_path"] = candidates[0]
            self._browser = self._pw.chromium.launch(**launch_kwargs)

        context = self._browser.new_context()
        self._page = context.new_page()

        # Collect JS errors
        self._page.on("console", self._on_console)
        self._page.on("pageerror", self._on_page_error)
        self._page.on("requestfailed", self._on_request_failed)

    def _login(self):
        """Register a fresh test account and extract the auth token."""
        username = f"inquisitor_{uuid.uuid4().hex[:6]}"
        password = "Inquisitor1234!X"  # 16 chars — meets minimum length requirement

        self._page.goto(f"{FRONTEND_URL}/login", wait_until="domcontentloaded", timeout=60000)

        # Wait for React to hydrate — the form elements won't exist until the
        # JS bundle has run and the component has mounted.
        try:
            self._page.wait_for_selector("form", timeout=15000)
        except Exception:
            pass  # continue anyway; fallback will handle it

        # Switch to register mode if needed (look for a "Register" toggle)
        try:
            self._page.get_by_text("Register", exact=False).first.click(timeout=3000)
        except Exception:
            pass  # might already be on register form

        # Fill in the form — target the register form explicitly since both
        # the login and register forms are rendered simultaneously in the DOM.
        email = f"{username}@inquisitor.test"
        try:
            reg_form = self._page.locator("#register-form")
            reg_form.locator("input[type='text'], input[name='username']").first.fill(username)
            reg_form.locator("input[type='password']").first.fill(password)
            email_input = reg_form.locator("input[type='email']")
            if email_input.count():
                email_input.first.fill(email)
            reg_form.locator("button[type='submit']").click()
            self._page.wait_for_url("**/menu**", timeout=30000)
        except Exception as exc:
            # Fallback: create a session directly via the test-only bypass endpoint
            # (available when FLASK_ENV=testing).  This avoids any database
            # dependency and is safe because the endpoint is not registered in
            # production (TESTING=False).
            resp = http_requests.post(
                f"{API_URL}/api/test/session",
                json={"username": username},
                timeout=5,
            )
            if resp.status_code in (200, 201):
                token = resp.json().get("session_id", "")
                self._token = token
                self._page.goto(FRONTEND_URL, wait_until="domcontentloaded", timeout=60000)
                self._page.evaluate(
                    f'localStorage.setItem("authToken", {json.dumps(token)})'
                )
                return
            raise RuntimeError(
                f"Login failed (UI: {exc!s}; test-session fallback: "
                f"HTTP {resp.status_code} {resp.text[:200]})"
            ) from exc

        # Extract token from localStorage
        self._token = self._page.evaluate('localStorage.getItem("authToken")')
        if not self._token:
            raise RuntimeError("Auth token not found in localStorage after login")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_console(self, msg):
        if msg.type in ("error", "warning"):
            self._console_errors.append({
                "type": msg.type,
                "text": msg.text,
                "location": str(msg.location),
            })

    def _on_page_error(self, exc):
        self._console_errors.append({"type": "pageerror", "text": str(exc)})

    def _on_request_failed(self, request):
        self._network_failures.append({
            "url": request.url,
            "failure": request.failure,
            "method": request.method,
        })

    # ------------------------------------------------------------------
    # HTTP helpers (uses real server + auth token)
    # ------------------------------------------------------------------

    def _get(self, path: str) -> http_requests.Response:
        return http_requests.get(
            f"{API_URL}{path}",
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=10,
        )

    def _post(self, path: str, payload: dict = None) -> http_requests.Response:
        return http_requests.post(
            f"{API_URL}{path}",
            json=payload or {},
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=10,
        )

    def _wrap_resp(self, resp: http_requests.Response, endpoint: str) -> ToolResult:
        status = resp.status_code
        try:
            data = resp.json()
        except Exception:
            data = {"_raw": resp.text[:500]}

        if status >= 500:
            return ToolResult.server_error(
                data.get("error", f"HTTP {status}"),
                f"{endpoint} returned {status}",
            )
        if status >= 400:
            return ToolResult(success=False, data=data,
                              error=data.get("error", f"HTTP {status}"),
                              http_status=status)
        return ToolResult(success=True, data=data, http_status=status)

    # ------------------------------------------------------------------
    # Game tool implementations (API calls against real server)
    # ------------------------------------------------------------------

    def _call_get_game_state(self) -> ToolResult:
        full = self._get("/api/full-state")
        events = self._get("/api/world/events/pending")
        if full.status_code >= 500:
            return ToolResult.server_error(
                full.json().get("error", "server error"),
                "GET /api/full-state returned 5xx",
            )
        data = full.json()
        data["pending_events"] = events.json().get("events", []) if events.ok else []
        return ToolResult.ok(data)

    def _call_move_player(self, direction: str) -> ToolResult:
        return self._wrap_resp(
            self._post("/api/world/move", {"direction": direction}),
            f"POST /api/world/move direction={direction!r}",
        )

    def _call_start_combat(self, enemy_id: str) -> ToolResult:
        return self._wrap_resp(
            self._post("/api/combat/start", {"enemy_id": enemy_id}),
            f"POST /api/combat/start enemy_id={enemy_id!r}",
        )

    def _call_get_combat_status(self) -> ToolResult:
        return self._wrap_resp(self._get("/api/combat/status"), "GET /api/combat/status")

    def _call_execute_combat_move(self, move_id: str, target_id: str) -> ToolResult:
        return self._wrap_resp(
            self._post("/api/combat/move", {"move_id": move_id, "target_id": target_id}),
            "POST /api/combat/move",
        )

    def _call_use_item(self, item_id: str) -> ToolResult:
        return self._wrap_resp(
            self._post("/api/inventory/use", {"item_id": item_id}),
            f"POST /api/inventory/use item_id={item_id!r}",
        )

    def _call_equip_item(self, item_id: str) -> ToolResult:
        return self._wrap_resp(
            self._post("/api/inventory/equip", {"item_id": item_id}),
            f"POST /api/inventory/equip item_id={item_id!r}",
        )

    def _call_interact(self, target_id: str) -> ToolResult:
        return self._wrap_resp(
            self._post("/api/world/interact", {"target_id": target_id}),
            f"POST /api/world/interact target_id={target_id!r}",
        )

    def _call_trigger_room_events(self) -> ToolResult:
        return self._wrap_resp(self._post("/api/world/events"), "POST /api/world/events")

    def _call_submit_event_input(self, event_id: str, user_input: str) -> ToolResult:
        return self._wrap_resp(
            self._post(
                "/api/world/events/input",
                {"event_id": event_id, "user_input": user_input},
            ),
            "POST /api/world/events/input",
        )

    def _call_get_pending_events(self) -> ToolResult:
        return self._wrap_resp(
            self._get("/api/world/events/pending"), "GET /api/world/events/pending"
        )

    def _call_save_game(self) -> ToolResult:
        name = f"inquisitor_{int(time.time())}"
        return self._wrap_resp(
            self._post("/api/saves", {"name": name}), "POST /api/saves"
        )

    # ------------------------------------------------------------------
    # Browser-specific tool implementations
    # ------------------------------------------------------------------

    def _call_take_screenshot(self, label: str) -> ToolResult:
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._screenshot_count += 1
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
        path = self._session_dir / f"{self._screenshot_count:03d}_{safe_label}.png"
        self._page.screenshot(path=str(path))
        return ToolResult.ok({"screenshot_saved": str(path)})

    # Patterns that produce console noise in every run but are not code bugs.
    # Confidence is intentionally high — only add a pattern here if you're
    # certain it can never indicate a real regression in this codebase.
    _NOISE_PATTERNS = (
        # External font CDNs are unreachable in offline / sandboxed CI.
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        # React Router v6 → v7 migration warnings — known, tracked upstream.
        "React Router Future Flag Warning",
        "React.startTransition",
        "Relative route resolution within Splat routes",
    )

    def _is_noise(self, entry: dict) -> bool:
        text = entry.get("text", "") + entry.get("url", "")
        return any(pat in text for pat in self._NOISE_PATTERNS)

    def _call_get_page_errors(self) -> ToolResult:
        """Return browser errors split into *significant* and *known_noise*.

        Significant errors are real JS exceptions or network failures that
        indicate a bug in this codebase.  Known noise is filtered out so the
        LLM agent doesn't waste turns investigating environment artefacts
        (blocked CDNs, expected deprecation warnings, etc.).
        """
        recent_console = self._console_errors[-50:]
        recent_net = self._network_failures[-20:]

        significant_console = [e for e in recent_console if not self._is_noise(e)]
        noise_console = [e for e in recent_console if self._is_noise(e)]
        significant_net = [f for f in recent_net if not self._is_noise(f)]
        noise_net = [f for f in recent_net if self._is_noise(f)]

        return ToolResult.ok({
            # Primary view — what the agent should act on
            "console_errors": significant_console,
            "network_failures": significant_net,
            "total_console_errors": len(significant_console),
            "total_network_failures": len(significant_net),
            # Secondary view — visible but clearly labelled as non-actionable
            "known_noise": {
                "console": noise_console,
                "network": noise_net,
            },
        })

    def _call_click_element(self, selector: str) -> ToolResult:
        try:
            self._page.locator(selector).first.click(timeout=5000)
            return ToolResult.ok({"clicked": selector})
        except Exception as exc:
            return ToolResult.err(f"Could not click {selector!r}: {exc}")

    def _call_get_visible_text(self) -> ToolResult:
        text = self._page.evaluate(
            "() => document.body ? document.body.innerText : ''"
        )
        return ToolResult.ok({"text": text[:8000]})  # cap to avoid token explosion
