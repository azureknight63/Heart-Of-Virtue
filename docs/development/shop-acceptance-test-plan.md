# Shop System — Acceptance Test Plan

**Branch:** `claude/jambo-shop-ui-mockup-I2uda`  
**Feature:** Jambo shop dialog (backend API + React UI)  
**Config:** `config_shop_testing.ini`

---

## Test Environment Setup

### Start the API server

```bash
CONFIG_FILE=config_shop_testing.ini python tools/run_api.py
```

The server starts with:
- Player at `(0, 0)` on `shop-testing` map (a single tile with Jambo)
- 200 gold in inventory
- Shortsword (auto-equipped, weight 2 kg) + Leather Armor (auto-equipped, weight 2.5 kg)

### Start the frontend dev server

```bash
cd frontend && npm run dev
```

### Obtain a session token

All API requests require `Authorization: Bearer <session_id>`.

```bash
# Register/login
curl -s -X POST http://localhost:5000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"shoptest","password":"test123","email":"t@t.com"}' \
  | jq '.session_id'
```

Or in test mode (no DB needed):

```bash
curl -s -X POST http://localhost:5000/api/test/session \
  -H 'Content-Type: application/json' \
  -d '{"username":"shoptest"}' \
  | jq '.session_id'
```

Set the token:
```bash
export TOKEN="<session_id from above>"
```

### Obtain Jambo's npc_id

```bash
JAMBO_ID=$(curl -s http://localhost:5000/api/world \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.location.npcs[0].id')
echo "Jambo npc_id: $JAMBO_ID"
```

---

## Reference Prices

| Item | Buy price | Sell offer | Weight |
|---|---|---|---|
| Restorative (×1) | 100 💰 | 50 💰 | 0.25 kg |
| Draught (×1) | 75 💰 | 37 💰 | 0.25 kg |
| Antidote (×1) | 175 💰 | 87 💰 | 0.25 kg |
| Shortsword (equipped) | — | blocked | 2.0 kg |
| Leather Armor (equipped) | — | blocked | 2.5 kg |

Player start state: **200 💰**, **4.5 kg** carried.

---

## API Test Cases

### TC-001 — GET shop state (happy path)

```bash
curl -s "http://localhost:5000/api/shop/state?npc_id=$JAMBO_ID" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected:**
- `success: true`
- `shop_state.npc_name = "Jambo"`
- `shop_state.shop_name = "Jambo Heals U"`
- `shop_state.buy_modifier = 1.0`
- `shop_state.sell_modifier = 0.5`
- `shop_state.stock` contains Restorative (×5), Draught (×4), Antidote (×3) and random extras
- `shop_state.buyback_items = []` (no sales yet)
- `shop_state.player_gold = 200`
- `shop_state.merchant_gold = 800`
- `sell_inventory` contains Shortsword and Leather Armor entries **— wait, these are equipped; they should NOT appear**

> **PASS CRITERION:** `sell_inventory` must be an empty list — equipped items are filtered.

---

### TC-002 — GET shop state: missing npc_id

```bash
curl -s "http://localhost:5000/api/shop/state" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected:** `400`, `success: false`, error mentions `npc_id`.

---

### TC-003 — GET shop state: wrong npc_id

```bash
curl -s "http://localhost:5000/api/shop/state?npc_id=000000" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected:** `404`, `success: false`, error mentions "Merchant not found".

---

### TC-004 — Buy 1× Restorative (happy path)

First capture a Restorative item_id from the stock list:

```bash
RESTORATIVE_ID=$(curl -s "http://localhost:5000/api/shop/state?npc_id=$JAMBO_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.shop_state.stock[] | select(.name=="Restorative") | .id')
```

```bash
curl -s -X POST http://localhost:5000/api/shop/buy \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"npc_id\":\"$JAMBO_ID\",\"item_id\":\"$RESTORATIVE_ID\",\"quantity\":1}" | jq .
```

**Expected:**
- `success: true`
- `gold_spent = 100`
- `shop_state.player_gold = 100` (200 − 100)
- `shop_state.stock` Restorative count drops from 5 → 4
- `sell_inventory` now contains the purchased Restorative

---

### TC-005 — Buy: insufficient gold

(Run after TC-004 — player has 100 gold left. Try to buy an Antidote costing 175.)

```bash
ANTIDOTE_ID=$(curl -s "http://localhost:5000/api/shop/state?npc_id=$JAMBO_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.shop_state.stock[] | select(.name=="Antidote") | .id')

curl -s -X POST http://localhost:5000/api/shop/buy \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"npc_id\":\"$JAMBO_ID\",\"item_id\":\"$ANTIDOTE_ID\",\"quantity\":1}" | jq .
```

**Expected:** `400`, `success: false`, error = `"Not enough gold — need 75 more"`.

---

### TC-006 — Buy: quantity > 1

(Fresh state or after TC-004 with 100 gold — buy 1 Draught costing 75.)

```bash
DRAUGHT_ID=$(curl -s "http://localhost:5000/api/shop/state?npc_id=$JAMBO_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.shop_state.stock[] | select(.name=="Draught") | .id')

curl -s -X POST http://localhost:5000/api/shop/buy \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"npc_id\":\"$JAMBO_ID\",\"item_id\":\"$DRAUGHT_ID\",\"quantity\":2}" | jq .
```

**Expected:**
- `success: true`, `gold_spent = 150` (75 × 2)
- `shop_state.stock` Draught count drops by 2

---

### TC-007 — Sell 1× Restorative (happy path)

(Run after TC-004 — player has a Restorative in sell_inventory.)

```bash
# Get the player's Restorative item_id from sell_inventory
PLAYER_RESTORATIVE_ID=$(curl -s "http://localhost:5000/api/shop/state?npc_id=$JAMBO_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.sell_inventory[] | select(.name=="Restorative") | .id')

curl -s -X POST http://localhost:5000/api/shop/sell \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"npc_id\":\"$JAMBO_ID\",\"item_id\":\"$PLAYER_RESTORATIVE_ID\",\"quantity\":1}" | jq .
```

**Expected:**
- `success: true`, `gold_gained = 50`
- `shop_state.player_gold` increases by 50
- `shop_state.buyback_items` now has 1 entry for Restorative at price 50
- Restorative disappears from `sell_inventory`
- The buyback entry has `is_buyback: true`

---

### TC-008 — Sell: cannot sell equipped item

```bash
# Get Shortsword id from player inventory via world state
SWORD_ID=$(curl -s http://localhost:5000/api/inventory \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.inventory[] | select(.name=="Shortsword") | .id')

curl -s -X POST http://localhost:5000/api/shop/sell \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"npc_id\":\"$JAMBO_ID\",\"item_id\":\"$SWORD_ID\",\"quantity\":1}" | jq .
```

**Expected:** `400`, `success: false`, error = `"Cannot sell equipped items"`.

---

### TC-009 — Buyback (happy path)

(Run after TC-007 — buyback_items has a Restorative at price 50.)

```bash
BUYBACK_ID=$(curl -s "http://localhost:5000/api/shop/state?npc_id=$JAMBO_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.shop_state.buyback_items[0].id')

curl -s -X POST http://localhost:5000/api/shop/buyback \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"npc_id\":\"$JAMBO_ID\",\"item_id\":\"$BUYBACK_ID\"}" | jq .
```

**Expected:**
- `success: true`, `gold_spent = 50`
- `shop_state.buyback_items = []` (entry removed after buyback)
- Restorative reappears in `sell_inventory`

---

### TC-010 — Buyback: wrong item_id

```bash
curl -s -X POST http://localhost:5000/api/shop/buyback \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"npc_id\":\"$JAMBO_ID\",\"item_id\":\"000000\"}" | jq .
```

**Expected:** `400`, `success: false`, error mentions "expired" or "not found".

---

### TC-011 — Buyback expiry on game_tick advance

This requires moving the player (increments `game_tick`).

```bash
# 1. Sell a Restorative to create a buyback entry (requires buying one first)
# ... (TC-004 then TC-007)

# 2. Confirm buyback entry exists
curl -s "http://localhost:5000/api/shop/state?npc_id=$JAMBO_ID" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.shop_state.buyback_items | length'
# Expected: 1

# 3. Buyback entries are scoped to the current game_tick.
#    Because the shop-testing map has no exits, game_tick cannot increment
#    without a combat event. Simulate a tick change by calling a world move
#    on a map that has exits, OR verify this behavior via unit test.
```

> **NOTE:** The shop-testing map is intentionally a single tile with no exits (to keep the player next to Jambo). TC-011 is best verified via a unit test or by temporarily adding an exit and moving back.

---

### TC-012 — Unauthenticated request

```bash
curl -s "http://localhost:5000/api/shop/state?npc_id=$JAMBO_ID" | jq .
```

**Expected:** `401`, `success: false`, error = `"Missing authorization"`.

---

## Frontend UI Test Cases

### UI-001 — Open shop via "trade" keyword

1. Open the game in the browser at `http://localhost:3000`
2. Log in; verify the player is at the Market Stall with Jambo present
3. Click **Interact** → select **Jambo** → click **trade**
4. **PASS:** `ShopDialog` opens with title "🏪 JAMBO HEALS U" on the **Buy** tab

---

### UI-002 — Open shop via "sell" keyword (opens on Sell tab)

1. Click **Interact** → select **Jambo** → click **sell**
2. **PASS:** `ShopDialog` opens directly on the **Sell** tab

---

### UI-003 — Open shop via "buy" keyword (opens on Buy tab)

1. Click **Interact** → select **Jambo** → click **buy**
2. **PASS:** `ShopDialog` opens on the **Buy** tab

---

### UI-004 — NPC strip and player gold

1. Open shop (any keyword)
2. **PASS:** 
   - Jambo avatar visible (🧕), name "Jambo", tagline `"When you blue, Jambo Heals U!"`
   - Player gold shows **200 💰**

---

### UI-005 — Weight bar shows current weight

1. Open shop
2. **PASS:** Weight bar shows current carried weight (≈ 4.5 kg from Shortsword + Leather Armor) against player max

---

### UI-006 — Weight bar pending delta on item selection (buy)

1. Open shop on Buy tab
2. Click a Restorative row
3. **PASS:**
   - Weight bar shows a pending orange segment (`+0.25 kg`)
   - Text: `4.5 + (+0.25) → 4.75 kg after`

---

### UI-007 — Buy tab: stock items visible

1. Open shop on Buy tab
2. **PASS:**
   - Restorative ×5, Draught ×4, Antidote ×3 visible in item list
   - Prices displayed: 100 💰, 75 💰, 175 💰
   - No equipped items (Shortsword, Leather Armor) in the list

---

### UI-008 — Buy action with sufficient gold

1. Open shop → Buy tab → select Restorative
2. Click **Buy · 100 💰**
3. **PASS:**
   - Transaction message: "Purchased 1× Restorative for 100 gold."
   - Player gold updates to **100 💰** in NPC strip
   - Restorative count in stock drops to ×4

---

### UI-009 — Insufficient gold: Buy button disabled

1. After TC-008/UI-008 (100 gold remaining), select Antidote (costs 175)
2. **PASS:**
   - Buy button is **disabled** (red border/color)
   - Message below selected item: `⚠ Not enough gold — need 75 more`

---

### UI-010 — Quantity picker appears for stackable items

1. Open shop → Buy tab → select Restorative (×4 or more in stock)
2. **PASS:**
   - `QtyPicker` component appears with `−` / `+` buttons and a number input
   - No native browser up/down spinner arrows on the input
   - `−` button disabled at qty=1

---

### UI-011 — Quantity picker: price updates live

1. With Restorative selected, set qty to 2 using `+`
2. **PASS:** Button label updates to `Buy 2 · 200 💰`

---

### UI-012 — Sell tab: equipped items not listed

1. Open shop → Sell tab
2. **PASS:**
   - Neither Shortsword nor Leather Armor appears in the sell inventory
   - "Nothing to sell" message OR only items bought from Jambo are listed

---

### UI-013 — Sell tab: merchant gold bar

1. Open shop → Sell tab
2. **PASS:** Merchant gold bar shows Jambo's current gold (800 at start)

---

### UI-014 — Sell flow end-to-end

1. Buy a Restorative (from UI-008)
2. Open Sell tab → select the Restorative → click **Sell · +50 💰**
3. **PASS:**
   - Transaction message: "Sold 1× Restorative for 50 gold."
   - Player gold increases by 50
   - Restorative disappears from sell inventory

---

### UI-015 — Buyback section appears after selling

1. After UI-014 (just sold a Restorative)
2. Switch to Buy tab
3. **PASS:**
   - A `↩ Buyback Available (until next beat)` section header appears in **cyan**
   - Restorative row shows `↩ BUYBACK` badge in cyan
   - Price shown is **50 💰** (the sell price, not the buy price)

---

### UI-016 — Weight bar delta on sell selection

1. After UI-014, open Sell tab → select an item
2. **PASS:**
   - Weight bar shows a **faded green segment** indicating weight that will be freed
   - No "Exceeds carry limit" warning

---

### UI-017 — Buyback flow end-to-end

1. After UI-015, switch to Buy tab → click the buyback Restorative row → click **Buyback · 50 💰**
2. **PASS:**
   - Transaction message: "Purchased …" or equivalent
   - Buyback section disappears
   - Player gold decreases by 50
   - Restorative reappears in sell inventory

---

### UI-018 — Tab state resets on switch

1. Buy tab → select an item → switch to Sell tab
2. **PASS:** No item is selected on the Sell tab; qty resets to 1

---

### UI-019 — Close button

1. Open shop → click **×** (BaseDialog close)
2. **PASS:** Dialog closes; InteractPanel does not reopen automatically

---

### UI-020 — Mobile layout (isMobile = true)

*Resize browser to < 480 px width or use DevTools device emulation.*

1. Open shop
2. **PASS:**
   - Item rows have min-height ≥ 44 px (accessible touch targets)
   - Quantity step buttons are 44 × 44 px
   - Tab buttons have larger padding (≥ 10 px vertical)
   - Action row stacks vertically (button full-width below item label)
   - Modal max-height is 92 vh with scroll

---

## Edge Case Notes

| Scenario | Where to test |
|---|---|
| Buyback entry expires on game_tick advance | Unit test or TC-011 workaround |
| Player at exact weight limit (overweight) | Send raw API call with mock high weight; UI shows "Exceeds carry limit" |
| Merchant runs out of gold (sell many items) | Buy 16 Draughts with another session, then sell; merchant gold → 0 |
| Buying a full stack (e.g. Restorative ×5 all at once) | qty picker max = 5 (or affordability-capped); buy all → stock empty |
| Stale session after shop transaction | Load page in second tab; gold sync via `onRefetch` keeps both tabs consistent |

---

## Definition of Done

All TC-001 – TC-012 API tests pass with the correct HTTP status codes and response bodies.  
All UI-001 – UI-020 pass with no console errors.  
No regressions in the existing test suite (`python -m pytest -q` — 1083 passed).
