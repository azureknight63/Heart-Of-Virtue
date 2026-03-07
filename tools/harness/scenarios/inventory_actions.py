"""Inventory action endpoint checks.

Tests the inventory verb routes not covered by the main inventory scenario:
take, drop, use, unequip, examine, compare, stats, and currency.

All "bad ID" tests check that the server returns 4xx, not 500.
Read-only endpoints (stats, currency) check for a 200 and required fields.
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity

_BAD_ITEM = "harness_nonexistent_item_99"
_BAD_SLOT = "harness_nonexistent_slot"


class InventoryActionsScenario(Scenario):
    name = "inventory_actions"
    description = (
        "Verify inventory take/drop/use/unequip/examine/compare/stats/currency "
        "endpoints do not crash on bad input."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # GET /api/inventory/stats ----------------------------------------
        resp = client.get("/api/inventory/stats")
        bug = self._check_status(resp, 200, "/api/inventory/stats", "GET",
                                 "Inventory stats")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"],
                "/api/inventory/stats", "GET", "Inventory stats response", resp,
            )

        # GET /api/inventory/currency -------------------------------------
        resp = client.get("/api/inventory/currency")
        bug = self._check_status(resp, 200, "/api/inventory/currency", "GET",
                                 "Inventory currency")
        if bug:
            bugs.append(bug)
        else:
            data = client.parse(resp)
            bugs += self._check_fields(
                data, ["success"],
                "/api/inventory/currency", "GET", "Inventory currency response", resp,
            )

        # GET /api/inventory/examine — bad item_id -------------------------
        resp = client.get(f"/api/inventory/examine?item_id={_BAD_ITEM}")
        bug = self._check_no_crash(resp, "/api/inventory/examine", "GET",
                                   f"Examine unknown item '{_BAD_ITEM}'")
        if bug:
            bugs.append(bug)

        # GET /api/inventory/compare — bad item IDs -------------------------
        resp = client.get(
            f"/api/inventory/compare?item1={_BAD_ITEM}&item2={_BAD_ITEM}"
        )
        bug = self._check_no_crash(resp, "/api/inventory/compare", "GET",
                                   "Compare two unknown items")
        if bug:
            bugs.append(bug)

        # POST /api/inventory/take — bad item_id ---------------------------
        body = {"item_id": _BAD_ITEM}
        resp = client.post("/api/inventory/take", json=body)
        bug = self._check_no_crash(resp, "/api/inventory/take", "POST",
                                   f"Take unknown item '{_BAD_ITEM}'",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        # POST /api/inventory/drop — bad item_id ---------------------------
        body = {"item_id": _BAD_ITEM}
        resp = client.post("/api/inventory/drop", json=body)
        bug = self._check_no_crash(resp, "/api/inventory/drop", "POST",
                                   f"Drop unknown item '{_BAD_ITEM}'",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        # POST /api/inventory/use — bad item_id ----------------------------
        body = {"item_id": _BAD_ITEM}
        resp = client.post("/api/inventory/use", json=body)
        bug = self._check_no_crash(resp, "/api/inventory/use", "POST",
                                   f"Use unknown item '{_BAD_ITEM}'",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        # POST /api/inventory/unequip — bad slot ---------------------------
        body = {"slot": _BAD_SLOT}
        resp = client.post("/api/inventory/unequip", json=body)
        bug = self._check_no_crash(resp, "/api/inventory/unequip", "POST",
                                   f"Unequip unknown slot '{_BAD_SLOT}'",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        # POST /api/inventory/equip — bad item_id (inventory-side route) --
        body = {"item_id": _BAD_ITEM}
        resp = client.post("/api/inventory/equip", json=body)
        bug = self._check_no_crash(resp, "/api/inventory/equip", "POST",
                                   f"Equip (inventory route) unknown item '{_BAD_ITEM}'",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        # POST /api/equipment/unequip — bad slot (equipment blueprint) ----
        body = {"slot": _BAD_SLOT}
        resp = client.post("/api/equipment/unequip", json=body)
        bug = self._check_no_crash(resp, "/api/equipment/unequip", "POST",
                                   f"Unequip (equipment route) unknown slot '{_BAD_SLOT}'",
                                   request_body=body)
        if bug:
            bugs.append(bug)

        return bugs
