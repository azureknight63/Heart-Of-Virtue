"""Merchant shop endpoint checks (shop_bp).

No default harness config places the player in front of a live merchant on
session start, so the error-path half of this scenario focuses on the
contract: every route must reject a bad/missing npc_id or item_id gracefully
(400/404), and never 500. If a real merchant NPC happens to be on the current
tile, that half also exercises a real /state fetch against it.

That left the scenario with **no happy path at all** — it never once completed
a purchase or a sale, so every bug in the transaction logic was invisible to
rung 2. ``_check_sell_buyback_round_trip`` closes that: it seats a Merchant on
the player's tile in-process (the same trick ``ch02_events`` uses to stage
story events) and then drives the real HTTP routes for the full
state → sell → buyback loop. The buyback row is read from the ``shop_state``
the sell response carries, which is the state the client renders next, so
there is no second GET /state in between.

It sells from a *stack*, partially, into a stock the merchant already holds,
because that is the arrangement that broke: ``stack_inv_items`` dissolves the
sold object into the merchant's existing same-name stack, so the buyback
ledger can only find its way back by name (#624).
"""

from typing import Any, List, NamedTuple, Optional

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugCategory, BugSeverity

_BAD_NPC = "harness_nonexistent_npc"
_BAD_ITEM = "harness_nonexistent_item"

#: Merchant stock 1 + player stack 5, selling 2. The merged stack (3) differs
#: from the seller's pre-sale count (5) on purpose: a ledger that recorded a
#: stale, count-bearing name cannot then match the surviving stack by accident.
_ROUND_TRIP_MERCHANT_STOCK = 1
_ROUND_TRIP_PLAYER_STACK = 5
_ROUND_TRIP_SELL_QTY = 2
_ROUND_TRIP_MERCHANT_GOLD = 2000
_ROUND_TRIP_PLAYER_GOLD = 1000


class _StagedMerchant(NamedTuple):
    """What ``_stage_round_trip_merchant`` seated, for the round trip."""

    merchant_id: str
    item_name: str
    item_type: str


class ShopScenario(Scenario):
    name = "shop"
    description = (
        "Verify shop state/buy/sell/buyback endpoints reject bad input "
        "gracefully (no 5xx), then sell part of a stack to a staged merchant "
        "and buy it back (#624)."
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

        bugs += self._check_sell_buyback_round_trip(client)

        return bugs

    # ------------------------------------------------------------------
    # Happy path: sell part of a stack, then buy it back
    # ------------------------------------------------------------------

    def _round_trip_bug(self, endpoint: str, method: str, title: str,
                        expected: str, actual: str, response=None,
                        request_body: Optional[dict] = None) -> BugReport:
        """A functional-logic bug in the sell/buyback round trip.

        Pass the ``response`` (and ``request_body``) that showed it, so the
        report carries the payload a fixer needs.
        """
        return self._bug(
            title=title,
            severity=BugSeverity.HIGH,
            category=BugCategory.LOGIC,
            endpoint=endpoint,
            method=method,
            expected=expected,
            actual=actual,
            response=response,
            request_body=request_body,
        )

    def _stage_round_trip_merchant(self, client: GameClient) -> Optional[_StagedMerchant]:
        """Seat a stocked Merchant on the player's tile.

        Returns None when the harness session has no full universe
        (MinimalPlayer) — a harness limitation, not a bug, exactly as
        ``ch02_events`` treats the same case.
        """
        live = self._live_player_tile(client)
        if live is None:
            return None
        player, tile = live.player, live.tile

        # Lazy imports — src modules are shimmed by bug_hunt.py's bootstrap.
        from src.combatant import wire_handle
        from src.items import Gold, MineralPowder
        from src.npc._merchants import Merchant

        def _powder(count: int, merchandise: bool) -> Any:
            item = MineralPowder()
            item.count = count
            item.merchandise = merchandise
            item.stack_grammar()
            return item

        merchant = Merchant(
            name="Harness Trader",
            description="A trader conjured by the bug-hunt harness.",
            damage=1, aggro=False, exp_award=0, stock_count=0,
        )
        merchant.inventory = [
            Gold(amt=_ROUND_TRIP_MERCHANT_GOLD),
            _powder(_ROUND_TRIP_MERCHANT_STOCK, merchandise=True),
        ]
        merchant.current_room = tile
        tile.npcs_here.append(merchant)

        player.current_room = tile
        # Replace the purse outright so the assertions below do not depend on
        # whatever gold the starting config happened to grant. Safe to clobber:
        # bug_hunt.py creates a fresh session per scenario, so nothing after
        # this scenario sees the edit.
        player.inventory = [
            item for item in player.inventory if not isinstance(item, Gold)
        ]
        player.inventory.append(Gold(amt=_ROUND_TRIP_PLAYER_GOLD))
        player.inventory.append(_powder(_ROUND_TRIP_PLAYER_STACK, merchandise=False))

        return _StagedMerchant(
            wire_handle(merchant), MineralPowder().name, MineralPowder.__name__
        )

    def _check_sell_buyback_round_trip(self, client: GameClient) -> List[BugReport]:
        """Sell part of a stack into the merchant's own stock, then redeem it."""
        staged = self._stage_round_trip_merchant(client)
        if staged is None:
            return []
        merchant_id, item_name, item_type = staged
        bugs: List[BugReport] = []

        resp = client.get(f"/api/shop/state?npc_id={merchant_id}")
        bug = self._check_status(
            resp, 200, "/api/shop/state", "GET",
            "Shop state for the harness-staged merchant",
        )
        if bug:
            return [bug]

        # Selected by CLASS, not name: the sell tab is keyed by opaque id in
        # the real UI, so matching the name here would make the arm fail on
        # any cosmetic renaming instead of on the transaction logic it exists
        # to check.
        sellable = [
            entry for entry in client.parse(resp).get("sell_inventory", [])
            if entry.get("type") == item_type
        ]
        if not sellable:
            return [self._round_trip_bug(
                "/api/shop/state", "GET",
                f"Player's {item_name} stack is missing from the sell tab",
                f"sell_inventory lists the player's {item_type} stack",
                "sell_inventory does not list it at all",
                response=resp,
            )]

        body = {
            "npc_id": merchant_id,
            "item_id": sellable[0]["id"],
            "quantity": _ROUND_TRIP_SELL_QTY,
        }
        resp = client.post("/api/shop/sell", json=body)
        bug = self._check_status(
            resp, 200, "/api/shop/sell", "POST",
            f"Sell {_ROUND_TRIP_SELL_QTY} of a {_ROUND_TRIP_PLAYER_STACK}-stack",
            request_body=body,
        )
        if bug:
            return [bug]

        buyback_rows = client.parse(resp).get("shop_state", {}).get(
            "buyback_items", []
        )
        if not buyback_rows:
            return [self._round_trip_bug(
                "/api/shop/sell", "POST",
                "A completed sale produced no buyback offer",
                "shop_state.buyback_items holds one row for the sold units",
                "buyback_items is empty",
                response=resp,
                request_body=body,
            )]

        body = {"npc_id": merchant_id, "item_id": buyback_rows[0]["id"]}
        resp = client.post("/api/shop/buyback", json=body)
        bug = self._check_status(
            resp, 200, "/api/shop/buyback", "POST",
            "Buy back the units just sold from a partial stack",
            request_body=body,
        )
        if bug:
            return [bug]

        data = client.parse(resp)
        if not data.get("success"):
            bugs.append(self._round_trip_bug(
                "/api/shop/buyback", "POST",
                "Buyback of a partially-sold stack was refused",
                "the just-sold units are redeemable from the buyback tab",
                f"buyback refused: {data.get('error')!r}",
                response=resp,
                request_body=body,
            ))
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
