"""API layer: in-process Flask test client used by the Inquisitor agent.

Wraps the existing GameClient and dispatches agent tool calls to the correct
REST endpoints.  No real browser or running servers needed.
"""

import json
import time
from typing import Any, Dict

from tools.harness.client import GameClient
from tools.inquisitor.game_tools import ToolResult, INTERNAL_TOOLS, INTERNAL_ACK, build_tool_list


class ApiLayer:
    """Executes agent tool calls against an in-process Flask test client."""

    def __init__(self, app, mode_name: str):
        self._client = GameClient(app)
        self._mode_name = mode_name
        self._client.create_session("inquisitor_player")

    # ------------------------------------------------------------------
    # Layer contract
    # ------------------------------------------------------------------

    def tool_specs(self) -> list:
        return build_tool_list(self._mode_name, use_browser=False)

    def get_initial_state(self) -> str:
        """Return a JSON description of the starting game state."""
        result = self._call_get_game_state()
        return json.dumps(result.data, indent=2)

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> ToolResult:
        """Dispatch a tool call and return a ToolResult."""
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
        self._client.destroy_session()

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _call_get_game_state(self) -> ToolResult:
        full_state_resp = self._client.get("/api/full-state")
        events_resp = self._client.get("/api/world/events/pending")

        if full_state_resp.status_code >= 500:
            return ToolResult.server_error(
                self._client.parse(full_state_resp).get("error", "server error"),
                "GET /api/full-state returned 5xx",
            )

        data = self._client.parse(full_state_resp)
        events_data = self._client.parse(events_resp)
        data["pending_events"] = events_data.get("events", [])
        return ToolResult.ok(data)

    def _call_move_player(self, direction: str) -> ToolResult:
        resp = self._client.post("/api/world/move", json={"direction": direction})
        return self._wrap(resp, f"POST /api/world/move direction={direction!r}")

    def _call_start_combat(self, enemy_id: str) -> ToolResult:
        resp = self._client.post("/api/combat/start", json={"enemy_id": enemy_id})
        return self._wrap(resp, f"POST /api/combat/start enemy_id={enemy_id!r}")

    def _call_get_combat_status(self) -> ToolResult:
        resp = self._client.get("/api/combat/status")
        return self._wrap(resp, "GET /api/combat/status")

    def _call_execute_combat_move(self, move_id: str, target_id: str) -> ToolResult:
        resp = self._client.post(
            "/api/combat/move",
            json={"move_id": move_id, "target_id": target_id},
        )
        return self._wrap(resp, "POST /api/combat/move")

    def _call_use_item(self, item_id: str) -> ToolResult:
        resp = self._client.post("/api/inventory/use", json={"item_id": item_id})
        return self._wrap(resp, f"POST /api/inventory/use item_id={item_id!r}")

    def _call_equip_item(self, item_id: str) -> ToolResult:
        resp = self._client.post("/api/inventory/equip", json={"item_id": item_id})
        return self._wrap(resp, f"POST /api/inventory/equip item_id={item_id!r}")

    def _call_interact(self, target_id: str) -> ToolResult:
        resp = self._client.post("/api/world/interact", json={"target_id": target_id})
        return self._wrap(resp, f"POST /api/world/interact target_id={target_id!r}")

    def _call_trigger_room_events(self) -> ToolResult:
        resp = self._client.post("/api/world/events")
        return self._wrap(resp, "POST /api/world/events")

    def _call_submit_event_input(self, event_id: str, user_input: str) -> ToolResult:
        resp = self._client.post(
            "/api/world/events/input",
            json={"event_id": event_id, "user_input": user_input},
        )
        return self._wrap(resp, "POST /api/world/events/input")

    def _call_get_pending_events(self) -> ToolResult:
        resp = self._client.get("/api/world/events/pending")
        return self._wrap(resp, "GET /api/world/events/pending")

    def _call_save_game(self) -> ToolResult:
        name = f"inquisitor_{int(time.time())}"
        resp = self._client.post("/api/saves", json={"name": name})
        return self._wrap(resp, "POST /api/saves")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wrap(self, resp, endpoint: str) -> ToolResult:
        """Wrap a Flask test response into a ToolResult."""
        status = resp.status_code
        data = self._client.parse(resp)

        if status >= 500:
            return ToolResult.server_error(
                data.get("error", f"HTTP {status}"),
                f"{endpoint} returned {status}",
            )

        if status >= 400:
            return ToolResult(
                success=False,
                data=data,
                error=data.get("error", f"HTTP {status}"),
                http_status=status,
            )

        return ToolResult(success=True, data=data, http_status=status)
