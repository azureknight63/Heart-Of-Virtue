"""Inventory and equipment checks."""

from typing import List, Optional

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class InventoryScenario(Scenario):
    name = "inventory"
    description = "Verify inventory listing, item pickup, and equipment endpoints."

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # GET /api/inventory ------------------------------------------------
        resp = client.get("/api/inventory")
        bug = self._check_status(resp, 200, "/api/inventory", "GET", "Get inventory")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "inventory"],
                "/api/inventory", "GET", "Inventory response", resp,
            )
            if not isinstance(data.get("inventory"), list):
                bugs.append(self._bug(
                    title="Inventory: 'inventory' field is not a list",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/inventory",
                    method="GET",
                    expected='"inventory" is a JSON array',
                    actual=f'"inventory" is {type(data.get("inventory")).__name__}',
                    response=resp,
                ))

        # GET /api/equipment ------------------------------------------------
        resp = client.get("/api/equipment")
        bug = self._check_status(resp, 200, "/api/equipment", "GET", "Get equipment")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"],
                "/api/equipment", "GET", "Equipment response", resp,
            )

        # GET /api/player ---------------------------------------------------
        resp = client.get("/api/player")
        bug = self._check_status(resp, 200, "/api/player", "GET", "Get player status")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "player"],
                "/api/player", "GET", "Player status response", resp,
            )
            player = data.get("player", {})
            bugs += self._check_fields(
                player, ["hp", "max_hp", "name"],
                "/api/player", "GET", "Player object", resp,
            )

        # Pickup non-existent item — should 400/404, not 500 ----------------
        body = {"item_id": "harness_nonexistent_item"}
        resp = client.post("/api/inventory/pickup", json=body)
        if resp.status_code == 500:
            bugs.append(self._bug(
                title="Pickup unknown item_id returns 500",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="/api/inventory/pickup",
                method="POST",
                expected="HTTP 400 or 404 (graceful rejection)",
                actual="HTTP 500 (unhandled exception)",
                response=resp,
                request_body=body,
            ))

        # Equip non-existent item — should 400/404, not 500 -----------------
        body = {"item_id": "harness_nonexistent_item", "slot": "weapon"}
        resp = client.post("/api/equipment/equip", json=body)
        if resp.status_code == 500:
            bugs.append(self._bug(
                title="Equip unknown item_id returns 500",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="/api/equipment/equip",
                method="POST",
                expected="HTTP 400 or 404 (graceful rejection)",
                actual="HTTP 500 (unhandled exception)",
                response=resp,
                request_body=body,
            ))

        return bugs
