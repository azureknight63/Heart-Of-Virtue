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
        if resp.status_code not in (400, 422):
            bugs.append(self._bug(
                title='Move with invalid direction "diagonal" not rejected',
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world/move",
                method="POST",
                expected="HTTP 400 for invalid direction",
                actual=f"HTTP {resp.status_code}",
                response=resp,
                request_body=body,
            ))

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
        if resp.status_code not in (400, 422):
            bugs.append(self._bug(
                title="Tile query without x/y coordinates not rejected",
                severity=BugSeverity.LOW,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world/tile",
                method="GET",
                expected="HTTP 400 when x or y is absent",
                actual=f"HTTP {resp.status_code}",
                response=resp,
            ))

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

        return bugs
