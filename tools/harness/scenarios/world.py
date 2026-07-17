"""World navigation and room exploration checks."""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory

_DIRECTIONS = ("north", "south", "east", "west")


class WorldScenario(Scenario):
    name = "world"
    description = "Verify room data, movement, tile queries, and room search."

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # Current room ------------------------------------------------------
        resp = client.get("/api/world")
        bug = self._check_status(resp, 200, "/api/world", "GET", "Get current room")
        if bug:
            bugs.append(bug)
            return bugs  # can't continue without a room

        data = client.parse(resp)
        bugs += self._check_fields(
            data, ["success", "room"], "/api/world", "GET", "Get current room", resp
        )
        room = data.get("room", {})
        bugs += self._check_fields(
            room, ["x", "y", "exits"],
            "/api/world", "GET", "Room object", resp,
        )
        start_x = room.get("x", 0)
        start_y = room.get("y", 0)

        # Movement ----------------------------------------------------------
        exits = room.get("exits", [])
        moved = False
        for direction in _DIRECTIONS:
            if direction in exits:
                body = {"direction": direction}
                resp = client.post("/api/world/move", json=body)
                bug = self._check_status(
                    resp, 200, "/api/world/move", "POST",
                    f"Move {direction}", request_body=body,
                )
                if bug:
                    bugs.append(bug)
                else:
                    data = client.parse(resp)
                    bugs += self._check_fields(
                        data, ["success", "room"],
                        "/api/world/move", "POST", f"Move {direction} response", resp,
                    )
                    moved = True
                break  # one successful move is enough to validate the flow

        # Invalid direction -------------------------------------------------
        body = {"direction": "diagonal"}
        resp = client.post("/api/world/move", json=body)
        bug = self._check_rejected(
            resp, "/api/world/move", "POST",
            'Move with invalid direction "diagonal" not rejected',
            "HTTP 400 for invalid direction",
            severity=BugSeverity.MEDIUM, request_body=body,
        )
        if bug:
            bugs.append(bug)

        # Tile query --------------------------------------------------------
        resp = client.get(f"/api/world/tile?x={start_x}&y={start_y}")
        bug = self._check_status(
            resp, 200, "/api/world/tile", "GET", "Get tile at starting position"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "tile"],
                "/api/world/tile", "GET", "Tile query", resp,
            )

        # Missing tile coordinates ------------------------------------------
        resp = client.get("/api/world/tile")
        bug = self._check_rejected(
            resp, "/api/world/tile", "GET",
            "Tile query without x/y coordinates not rejected",
            "HTTP 400 when x or y is absent",
        )
        if bug:
            bugs.append(bug)

        # Room search -------------------------------------------------------
        resp = client.post("/api/world/search")
        bug = self._check_status(resp, 200, "/api/world/search", "POST", "Search room")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            # search returns varying shapes; just check success is present
            if "success" not in data:
                bugs += self._check_fields(
                    data, ["success"],
                    "/api/world/search", "POST", "Search room", resp,
                )

        # Available commands ------------------------------------------------
        resp = client.get("/api/world/commands")
        bug = self._check_status(
            resp, 200, "/api/world/commands", "GET", "Get available commands"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "commands"],
                "/api/world/commands", "GET", "Available commands", resp,
            )

        # Explored tiles ------------------------------------------------------
        resp = client.get("/api/world/explored")
        bug = self._check_status(
            resp, 200, "/api/world/explored", "GET", "Get explored tiles"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "explored_tiles"],
                "/api/world/explored", "GET", "Explored tiles", resp,
            )

        # Pending events --------------------------------------------------
        resp = client.get("/api/world/events/pending")
        bug = self._check_status(
            resp, 200, "/api/world/events/pending", "GET", "Get pending events"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "events"],
                "/api/world/events/pending", "GET", "Pending events", resp,
            )

        # Tiles batch — current tile plus a few neighbours -------------------
        body = {"coordinates": [
            {"x": start_x, "y": start_y},
            {"x": start_x + 1, "y": start_y},
        ]}
        resp = client.post("/api/world/tiles/batch", json=body)
        bug = self._check_status(
            resp, 200, "/api/world/tiles/batch", "POST", "Get tiles batch",
            request_body=body,
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "tiles"],
                "/api/world/tiles/batch", "POST", "Tiles batch", resp,
            )
            if not isinstance(data.get("tiles"), list):
                bugs.append(self._bug(
                    title="Tiles batch: 'tiles' field is not a list",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/world/tiles/batch",
                    method="POST",
                    expected='"tiles" is a JSON array',
                    actual=f'"tiles" is {type(data.get("tiles")).__name__}',
                    response=resp,
                    request_body=body,
                ))

        # Tiles batch — missing coordinates ----------------------------------
        resp = client.post("/api/world/tiles/batch", json={})
        bug = self._check_rejected(
            resp, "/api/world/tiles/batch", "POST",
            "Tiles batch without coordinates not rejected",
            "HTTP 400 when coordinates is absent",
        )
        if bug:
            bugs.append(bug)

        # Events on the current tile ------------------------------------------
        resp = client.post("/api/world/events")
        bug = self._check_status(
            resp, 200, "/api/world/events", "POST", "Trigger room events"
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "events"],
                "/api/world/events", "POST", "Trigger room events", resp,
            )

        # Events input — missing event_id/user_input -------------------------
        resp = client.post("/api/world/events/input", json={})
        bug = self._check_rejected(
            resp, "/api/world/events/input", "POST",
            "Events input without event_id/user_input not rejected",
            "HTTP 400 when event_id/user_input is absent",
        )
        if bug:
            bugs.append(bug)

        # Events input — unknown event_id, must not 500 -----------------------
        body = {"event_id": "harness_nonexistent_event", "user_input": "continue"}
        resp = client.post("/api/world/events/input", json=body)
        bug = self._check_no_crash(
            resp, "/api/world/events/input", "POST",
            "Submit input for unknown event_id", request_body=body,
        )
        if bug:
            bugs.append(bug)

        # Interact — unknown target_id, must not 500 (real contract: pickup
        # goes through /api/world/interact, not a dedicated inventory route) --
        body = {"target_id": "harness_nonexistent_target", "action": "take"}
        resp = client.post("/api/world/interact", json=body)
        bug = self._check_status(
            resp, 200, "/api/world/interact", "POST",
            "Interact with unknown target_id", request_body=body,
        )
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"],
                "/api/world/interact", "POST", "Interact (unknown target)", resp,
            )
            if data.get("success"):
                bugs.append(self._bug(
                    title="Interact with unknown target_id returned success=True",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/world/interact",
                    method="POST",
                    expected="success=False (target not found)",
                    actual="success=True",
                    response=resp,
                    request_body=body,
                ))

        # Interact — missing target_id/action ---------------------------------
        resp = client.post("/api/world/interact", json={})
        bug = self._check_rejected(
            resp, "/api/world/interact", "POST",
            "Interact without target_id/action not rejected",
            "HTTP 400 when target_id/action is absent",
        )
        if bug:
            bugs.append(bug)

        # Interact — take a real item from the current room, if one exists ---
        resp = client.get("/api/world")
        if resp.status_code == 200:
            room = client.parse(resp).get("room", {})
            items = room.get("items", [])
            real_item = next(
                (it for it in items if isinstance(it, dict) and it.get("id")), None
            )
            if real_item:
                body = {"target_id": real_item["id"], "action": "take"}
                resp = client.post("/api/world/interact", json=body)
                bug = self._check_status(
                    resp, 200, "/api/world/interact", "POST",
                    f"Take real item '{real_item.get('name', '?')}'",
                    request_body=body,
                )
                if bug:
                    bugs.append(bug)
                else:
                    data = client.parse(resp)
                    bugs += self._check_fields(
                        data, ["success"],
                        "/api/world/interact", "POST", "Interact (take item)", resp,
                    )

        return bugs
