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
        # The API returns a rich inventory object: {items: [...], item_count, slots_*,
        # weight_*, ...}.  We check the outer wrapper and the items list inside it.
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
            inv = data.get("inventory", {})
            if isinstance(inv, dict):
                bugs += self._check_fields(
                    inv, ["items", "item_count", "slots_total"],
                    "/api/inventory", "GET", "Inventory object", resp,
                )
                if not isinstance(inv.get("items"), list):
                    bugs.append(self._bug(
                        title="Inventory: 'inventory.items' is not a list",
                        severity=BugSeverity.MEDIUM,
                        category=BugCategory.WRONG_RESPONSE,
                        endpoint="/api/inventory",
                        method="GET",
                        expected='"inventory.items" is a JSON array',
                        actual=f'"inventory.items" is {type(inv.get("items")).__name__}',
                        response=resp,
                    ))
            else:
                bugs.append(self._bug(
                    title="Inventory: 'inventory' field is not an object",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/inventory",
                    method="GET",
                    expected='"inventory" is a JSON object with items, item_count, ...',
                    actual=f'"inventory" is {type(inv).__name__}',
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

        # GET /api/status — player status (hp, name, level, ...) ------------
        # /api/status (player_bp) is the correct endpoint.
        # /api/reputation/player is the reputation summary — fixed in b16c05a.
        resp = client.get("/api/status")
        bug = self._check_status(resp, 200, "/api/status", "GET", "Get player status")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success", "status"],
                "/api/status", "GET", "Player status response", resp,
            )
            status = data.get("status", {})
            bugs += self._check_fields(
                status, ["hp", "max_hp", "name"],
                "/api/status", "GET", "Player status object", resp,
            )

        # Pickup non-existent item — should 400/404, not 500 ----------------
        body = {"item_id": "harness_nonexistent_item"}
        resp = client.post("/api/inventory/pickup", json=body)
        bug = self._check_no_crash(resp, "/api/inventory/pickup", "POST",
                                   "Pickup unknown item_id", request_body=body)
        if bug:
            bugs.append(bug)

        # Equip non-existent item — should 400/404, not 500 -----------------
        body = {"item_id": "harness_nonexistent_item", "slot": "weapon"}
        resp = client.post("/api/equipment/equip", json=body)
        bug = self._check_no_crash(resp, "/api/equipment/equip", "POST",
                                   "Equip unknown item_id", request_body=body)
        if bug:
            bugs.append(bug)

        return bugs
