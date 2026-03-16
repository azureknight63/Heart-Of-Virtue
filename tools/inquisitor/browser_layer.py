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

from tools.inquisitor.game_tools import ToolResult, INTERNAL_TOOLS, INTERNAL_ACK, build_tool_list

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = ROOT / "frontend"
API_URL = "http://localhost:5000"
FRONTEND_URL = "http://localhost:3000"
SERVER_STARTUP_TIMEOUT = 60  # seconds
SCREENSHOT_DIR = ROOT / "tools" / "inquisitor_screenshots"


class BrowserLayer:
    """Executes agent tool calls via Playwright + real HTTP requests."""

    def __init__(self, mode_name: str, headless: bool = False):
        self._mode_name = mode_name
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

    def tool_specs(self) -> list:
        return build_tool_list(self._mode_name, use_browser=True)

    def get_initial_state(self) -> str:
        result = self._call_get_game_state()
        return json.dumps(result.data, indent=2)

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> ToolResult:
        if tool_name in INTERNAL_TOOLS:
            return INTERNAL_ACK

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

    def _start_servers(self):
        """Start Flask API and Vite dev server as subprocesses."""
        env = os.environ.copy()
        env["FLASK_ENV"] = "development"
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
        self._browser = self._pw.chromium.launch(headless=self._headless)
        context = self._browser.new_context()
        self._page = context.new_page()

        # Collect JS errors
        self._page.on("console", self._on_console)
        self._page.on("pageerror", self._on_page_error)
        self._page.on("requestfailed", self._on_request_failed)

    def _login(self):
        """Register a fresh test account and extract the auth token."""
        username = f"inquisitor_{uuid.uuid4().hex[:6]}"
        password = "Inquisitor1234!"

        self._page.goto(f"{FRONTEND_URL}/login", wait_until="networkidle")

        # Switch to register mode if needed (look for a "Register" toggle)
        try:
            self._page.get_by_text("Register", exact=False).first.click(timeout=3000)
        except Exception:
            pass  # might already be on register form

        # Fill in the form
        try:
            self._page.locator("input[type='text'], input[name='username']").first.fill(username)
            self._page.locator("input[type='password']").first.fill(password)
            self._page.locator("button[type='submit']").click()
            self._page.wait_for_url("**/menu**", timeout=10000)
        except Exception as exc:
            # Fallback: register via API directly and set token in localStorage
            resp = http_requests.post(
                f"{API_URL}/api/auth/register",
                json={"username": username, "password": password},
                timeout=5,
            )
            if resp.status_code in (200, 201):
                token = resp.json().get("session_id", "")
                self._token = token
                self._page.goto(FRONTEND_URL, wait_until="domcontentloaded")
                self._page.evaluate(
                    f'localStorage.setItem("authToken", {json.dumps(token)})'
                )
                return
            raise RuntimeError(f"Login failed: {exc}") from exc

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

    def _call_get_page_errors(self) -> ToolResult:
        return ToolResult.ok({
            "console_errors": self._console_errors[-50:],  # cap at 50
            "network_failures": self._network_failures[-20:],
            "total_console_errors": len(self._console_errors),
            "total_network_failures": len(self._network_failures),
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
