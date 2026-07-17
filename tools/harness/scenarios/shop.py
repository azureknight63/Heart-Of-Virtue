"""Merchant shop endpoint checks (shop_bp).

No default harness config places the player in front of a live merchant on
session start, so this scenario focuses on the contract's error paths: every
route must reject a bad/missing npc_id or item_id gracefully (400/404), and
never 500. If a real merchant NPC happens to be on the current tile, the
scenario also exercises a real /state fetch against it.
"""

from typing import List, Optional

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport

_BAD_NPC = "harness_nonexistent_npc"
_BAD_ITEM = "harness_nonexistent_item"


class ShopScenario(Scenario):
    name = "shop"
    description = (
        "Verify shop state/buy/sell/buyback endpoints reject bad input "
        "gracefully (no 5xx)."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # GET /api/shop/state — missing npc_id ------------------------------
        resp = client.get("/api/shop/state")
        bug = self._check_rejected(
            resp, "/api/shop/state", "GET",
            "Shop state without npc_id query param not rejected",
            "HTTP 400 when npc_id is absent",
        )
        if bug:
            bugs.append(bug)

        # GET /api/shop/state — unknown npc_id, must not 500 -----------------
        resp = client.get(f"/api/shop/state?npc_id={_BAD_NPC}")
        bug = self._check_no_crash(
            resp, "/api/shop/state", "GET", f"Shop state for unknown npc '{_BAD_NPC}'"
        )
        if bug:
            bugs.append(bug)

        # POST /api/shop/buy — missing fields ---------------------------------
        resp = client.post("/api/shop/buy", json={})
        bug = self._check_rejected(
            resp, "/api/shop/buy", "POST",
            "Shop buy without npc_id/item_id not rejected",
            "HTTP 400 when npc_id/item_id is absent",
        )
        if bug:
            bugs.append(bug)

        # POST /api/shop/buy — unknown npc/item, must not 500 ----------------
        body = {"npc_id": _BAD_NPC, "item_id": _BAD_ITEM, "quantity": 1}
        resp = client.post("/api/shop/buy", json=body)
        bug = self._check_no_crash(
            resp, "/api/shop/buy", "POST", "Buy from unknown npc/item",
            request_body=body,
        )
        if bug:
            bugs.append(bug)

        # POST /api/shop/buy — invalid quantity (non-numeric), must not 500 --
        body = {"npc_id": _BAD_NPC, "item_id": _BAD_ITEM, "quantity": "not-a-number"}
        resp = client.post("/api/shop/buy", json=body)
        bug = self._check_no_crash(
            resp, "/api/shop/buy", "POST", "Buy with non-numeric quantity",
            request_body=body,
        )
        if bug:
            bugs.append(bug)

        # POST /api/shop/sell — missing fields --------------------------------
        resp = client.post("/api/shop/sell", json={})
        bug = self._check_rejected(
            resp, "/api/shop/sell", "POST",
            "Shop sell without npc_id/item_id not rejected",
            "HTTP 400 when npc_id/item_id is absent",
        )
        if bug:
            bugs.append(bug)

        # POST /api/shop/sell — unknown npc/item, must not 500 ---------------
        body = {"npc_id": _BAD_NPC, "item_id": _BAD_ITEM, "quantity": 1}
        resp = client.post("/api/shop/sell", json=body)
        bug = self._check_no_crash(
            resp, "/api/shop/sell", "POST", "Sell to unknown npc/item",
            request_body=body,
        )
        if bug:
            bugs.append(bug)

        # POST /api/shop/buyback — missing fields -----------------------------
        resp = client.post("/api/shop/buyback", json={})
        bug = self._check_rejected(
            resp, "/api/shop/buyback", "POST",
            "Shop buyback without npc_id/item_id not rejected",
            "HTTP 400 when npc_id/item_id is absent",
        )
        if bug:
            bugs.append(bug)

        # POST /api/shop/buyback — unknown npc/item, must not 500 ------------
        body = {"npc_id": _BAD_NPC, "item_id": _BAD_ITEM}
        resp = client.post("/api/shop/buyback", json=body)
        bug = self._check_no_crash(
            resp, "/api/shop/buyback", "POST", "Buyback from unknown npc/item",
            request_body=body,
        )
        if bug:
            bugs.append(bug)

        # Bonus: if a real merchant NPC is present on the current tile, hit
        # /state for real and sanity-check the response shape.
        real_npc_id = self._find_merchant(client)
        if real_npc_id:
            resp = client.get(f"/api/shop/state?npc_id={real_npc_id}")
            bug = self._check_status(
                resp, 200, "/api/shop/state", "GET",
                "Shop state for real merchant on current tile",
            )
            if bug:
                bugs.append(bug)
            else:
                data = client.parse(resp)
                bugs += self._check_fields(
                    data, ["success", "shop_state"],
                    "/api/shop/state", "GET", "Shop state (real merchant)", resp,
                )

        return bugs

    # NPCSerializer.serialize() (used for room.npcs) never emits `is_merchant`/
    # `shop_name` — those only appear via serialize_merchant(), which room
    # serialization doesn't call. The room payload's `type` field (the leaf
    # class name) is the only signal available, so match against the current
    # concrete Merchant subclasses (src/npc/_merchants.py). Update this set if
    # a new merchant subclass is added, or the real-merchant bonus check below
    # silently stops firing again.
    _MERCHANT_TYPES = {"Merchant", "MiloCurioDealer", "JamboHealsU"}

    def _find_merchant(self, client: GameClient) -> Optional[str]:
        """Return the id of a merchant NPC on the current tile, if any."""
        resp = client.get("/api/world")
        if resp.status_code != 200:
            return None
        data = client.parse(resp)
        for npc in data.get("room", {}).get("npcs", []):
            if isinstance(npc, dict) and npc.get("type") in self._MERCHANT_TYPES:
                return npc.get("id") or npc.get("npc_id")
        return None
