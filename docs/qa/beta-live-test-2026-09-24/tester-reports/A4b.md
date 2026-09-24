# A4b — Nomad Camp / End of Beta QA Report

## 1. Header

- Tester: A4b, stack `camp0924b`, API `:5004`
- Session: `qa_A4b_267a3`
- Tool calls used: ~110 (well under the 220 budget); wall time well under the 2-hour cap
- Ended: map `eastern-descent-nomad-camp`, tile (0,2) "Water Step" (Ferry Landing), after the beta ended there
- Level 3, HP 74/108 at end, low-water HP during the session was 19 (mid-fight, before recognizing the fatigue block — see Combat Log)
- Request/response log: `RUNS\A4b_api.jsonl`

## 2. Route checklist

| Scene / step | Result | Evidence |
|---|---|---|
| Grondia (14,5) → east → Eastern Gate "enter" → "Step through" | PASS | `output_text` began "The mountain air hits without warning — cold, thin, carrying the smell of raw stone and something older than either." |
| GorranGestureEvent on eastern-descent arrival | PASS — fires in the *same* response as the gate transition, not as a separate pending event | Same response: "Gorran paused at the gate as it sealed. His palm rested flat against the stone — one breath, maybe two. Then he turned without a word and followed.\n\nJean did not ask him." |
| Path to NomadCamp (3,6) | PASS (with 4 random encounters along the way — Rock Rumbler ×2, Scarp Adder ×2, Talus Hound pack) | see Combat Log |
| Camp Entrance "enter" → CampEntryGreeting / NomadCampSmell / JamboTentNoticeEvent | PASS | first line: "The camp's east edge is marked by a line of weathered stakes driven into the gravel at intervals..." — full scene includes the Liss cameo and the "JAMBO HEALS U" tent notice, all in one beat |
| (2,1) Camp [Nomad] | PASS — tile reachable, Nomad NPC present, no scripted beat here | — |
| (1,2) RiversEdge — MaraFirstContact | PASS, fired automatically on first tile entry (before I sent `talk`) | journal log title "RiversEdge", first line: "A woman at the camp's western edge had clocked them while they were still fifty paces out..." |
| (0,2) WaterStep / Ferry Landing, attempted BEFORE Mara's chain completes | PASS (correctly declines) | `interact enter` → "Jean stops at the ferry landing but doesn't go through — not yet. Something else still needs finishing first." |
| (3,2) FireRing — DevetIntro | PASS, fired automatically on entry | first line: "An older man was tending the fire — unhurried, each movement economical..." |
| (3,1) Supply Tents [Nomad Scout, Nomad Boy; Supply Tent, Water Barrel] | PASS — tile reachable; Supply Tent is locked/tied shut ("Someone with access to the camp would have the key") — read as an intentional puzzle, not filed | `check`/`take_all` both return the same tied-shut message |
| (4,1) Nursery [children; Washing Basin] | PASS — reachable, NPCs and object present | — |
| (3,3)/(2,3) Camp [Traveler's Logbook] | PASS | `read` on the logbook: "A child's drawing in the margin: a stick figure with what might be a sword..." |
| (4,3) Tradepost [Kaelen, Vespera, Nomad Trader, Anvil] — IronAndOathIntro/AnvilIntro | PASS, fired automatically on entry | first line: "The metallic scraping of a hand file against steel and the sharp snap of waxed thread echoed beneath the canvas awning..." |
| (3,4) CampFarEdge [Liss] — LissObserving | PASS, fired as part of the CampEntry beat (Liss's cameo) and again as its own scene on tile entry | journal title "CampFarEdge", first line: "Liss was at the camp's far corner — young, dark-haired, turning a stone over in one hand out of habit..." |
| Jambo's Tent — JamboShopIntroEvent | PASS, fired on first tent entry | journal shows the full "Jean smelled the camp..." / tent-teach beat rolled into `Passage_Camp Entrance`'s output, and the tent's own intro plays on stepping through `Jambo's Tent` |
| Jambo shop: open / buy / sell / buyback | PASS — gold arithmetic exact at every step | 315→240 (bought Draught, 75g) →277 (sold Draught back, 37g) →240 (bought back same Draught, 37g); inventory count tracked correctly each time |
| Crate TAKE ALL (#609) | PASS | "Jean takes 2× Slime Flask, Draught, Antidote, Wooden Arrow, Respite, 3× Mineral Solvent, Flare Arrow, Bitterroot, Iron Arrow." — all marked `is_merchandise: true` in `/api/inventory` |
| Jambo's Little Book of Big Deals — "read" (#665) | PASS | `read` accepted; returned full book text starting "JAMBO'S LITTLE BOOK OF BIG DEALS / (Or: How to Turn a Profit Without Losing Your Soul)..." |
| Merchandise-drop-on-crossing rule | PASS (intentional, per primer) | Crossing the tent flap with unpaid stock produced 9 lines of "Jean places X carefully against the wall" / "returns X to the shop floor" / "sets X down; unpaid goods don't leave the shop"; `/api/inventory` afterward shows zero `is_merchandise` items |
| Revisit every scene tile — nothing repeats, `pending` empty | PASS | re-walked FireRing→CampFarEdge→Camp; journal log entry count unchanged (10 before/after), `pending_events` 0 throughout |
| Complete chain (Mara+Devet+Liss) → return to Mara → MaraObservation | PASS, fired automatically on RiversEdge re-entry | first line: "A while later — Jean was sitting with the bowl, Gorran nearby, the fire between them and the river — Mara looked up from what she was sorting." Objective flipped from `ch03_walk_the_camp` (done) to `ch03_ferry_landing` (active) |
| Ferry Landing after the chain completes → ends the demo | PASS | `interact enter` response: `{"beta_end": true, "message": "Jean stops at the ferry landing and looks at what lies beyond. The way is plain enough — but not today."}` |
| Post-end API behavior | PASS-ish, see Findings #4 (observation) | Movement still works (`/api/world/move` succeeds, no lock), `/api/world/events` returns clean empty, a second Ferry Landing `enter` on the same tile replays the identical `beta_end: true` message idempotently (no crash, no duplicate objective completion) |
| /api/journal after each scene | PASS — objectives open/close in correct order | `ch03_canvass_camp` (done at MaraFirstContact) → `ch03_walk_the_camp` (active, done at MaraObservation) → `ch03_ferry_landing` (active, done at the Ferry Landing crossing) |
| NPC chat: Devet open→respond→end | PASS | fallback flavor: "He nods, once. The fire gets another stick." |
| NPC chat: Liss open→respond→end | PASS | fallback flavor: "She repeats the last few words under her breath, trying them out like a new stone." |
| NPC chat: Mara open→respond→end | PASS | fallback flavor: "She looks at Jean a moment longer than necessary and lets the silence answer." |
| NPC chat: error payload (missing `jean_text`) | PASS | 400, `{"error": "jean_text is required"}` |
| NPC chat: second `open` while one is already active | Works, no error — new `open_token` minted each time, old one still endable | see Findings #5 (observation, not a bug — matches #674's documented "stale token is ignored" design) |

## 3. Fix verification

| Issue | Result | Evidence |
|---|---|---|
| #669 Eastern Gate gated on Votha Krr's post-King-Slime talk | N/A for this stack — camp0924b starts with `votha_krr_response_given` already seeded, so the gate was never exercised as a block. Gate did not spuriously block a fresh, pre-seeded session. |
| #665 "read" on Jambo's Little Book accepted | PASS | see checklist above |
| #664 Jambo's Grondia-tent-equivalent intro teaches shop mechanics on first entry | PASS | JamboShopIntroEvent fired on first tent entry (camp version) |
| #663 teleport-to-Jambo's-tent offer | N/A — that beat belongs to Votha Krr's Grondia dialogue, which is pre-seeded past on this stack; not observable here |
| #660 no stray double spaces in Jambo tent entrance/discovery text | PASS — spot-checked the tent-entry and discovery prose, no double spaces found |
| #657 Votha Krr shown as "???" | N/A — pre-seeded past, not observable |
| #650 restock does not litter the floor | Not directly exercised (no restock cycle triggered in this session) |
| #641 item mutations serialized (take/drop/collect/shop don't interleave) | PASS — no interleaving errors across take_all, buy, sell, buyback, crossing-drop |
| #609 TAKE ALL / take_all on containers | PASS | see checklist |
| #610 reload after a fight is clean | PASS | re-GET after each of 4 fights showed correct enemy/ally state, no stale combat residue except the two findings below |

## 4. Findings

### Finding 1 — `/api/inventory/currency` reports gold as 0 while every other source reports it correctly
- **Severity**: Medium
- **Location**: API route, not tile-specific — reproduced repeatedly in the Nomad Camp while carrying real gold (240–315g)
- **Steps to reproduce**:
  1. Log in on any stack with starting gold (all of them have 300+).
  2. `GET /api/inventory` — note the "Gold" item's `quantity` (e.g. 315).
  3. `GET /api/inventory/currency` — `currency.gold` reads `0`.
  4. `GET /api/status` — `status.gold` correctly reads 315 (or whatever the real total is).
- **Expected**: `/api/inventory/currency` reports the same gold total as `/api/inventory` and `/api/status`.
- **Actual**: Always 0, regardless of actual gold held. Confirmed on 5+ separate reads across the session, including after buy/sell/buyback transactions that correctly moved gold everywhere else (`/api/status` tracked 315→240→277→240 correctly the whole time; `/api/inventory/currency` stayed 0 throughout).
- **Confidence**: Reproduced repeatedly, very high confidence — this is a code-level bug, not a fluke.
- **Source**: `src/api/routes/inventory.py:584-587` (`get_currency`) does `"gold": getattr(player, "gold", 0)`. Per CLAUDE.md's own documented attribute traps, `player.gold` does not exist as a live attribute — gold is tracked as a `Gold` item in `player.inventory` and read everywhere else through `game_service`. This route reaches directly into player internals with a `getattr` default, exactly the anti-pattern the API-layer rules warn about (`.claude/rules/api-layer.md`: "Routes must not reach into player internals. No `getattr(player, "attribute", default)` in routes — add a `GameService` method.").

### Finding 2 — Combat `move_type: "item"` is accepted (HTTP 200) but is not a real move type; it silently does nothing
- **Severity**: Low/Medium (API contract mismatch — no data loss, but misleading response)
- **Location**: `/api/combat/move`, exercised during the Talus Hound pack fight at eastern-descent (3,4)
- **Steps to reproduce**:
  1. Enter combat.
  2. `POST /api/combat/move {"move_type":"item","move_id":"Restorative"}`
  3. Response is `200 {"success": true, ..., "message": "Unknown move type: item"}` — no error surfaced as a failure, but nothing happens (HP unchanged).
- **Expected**: Either the documented move_type works, or an unrecognized move_type returns a clear 400.
- **Actual**: The route's own docstring (`src/api/routes/combat.py:88`) states `"move_type": "attack|defend|cast|item|swap_weapon"`, but `game_service.execute_move`'s actual `elif` chain (`src/api/services/game_service.py:3907-4018`) has no branch for `"item"` or `"cast"` at all — it falls through to whatever the default/else case is and returns a soft "Unknown move type" message inside a 200. Separately, the *correct* way to use an item in combat is `move_type: "move", move_id: "Use Item"`, which itself is a flavor-only no-op by design ("Jean opens his bag... closes his bag" — see `src/moves/_utility.py:944-949`, which explicitly documents that the web client should call `/api/inventory/use` directly instead). That second part is intentional and documented in `.claude/rules/combat-engine.md`, so it is not a bug — but the stale docstring claiming `"item"` is a valid `move_type` is.
- **Confidence**: Reproduced twice (once via `move_type:"item"`, again confirming `/api/inventory/use` is the correct path and does work — HP went 29→92 using a Restorative that way).
- **Source**: `src/api/routes/combat.py:88` (stale docstring); `src/api/services/game_service.py:3907-4018` (no `"item"`/`"cast"` branch).

### Finding 3 — `battle_state.status` stays `"active"` after the last enemy in a fight dies, even though `combat_active` (top-level) correctly flips to `false`
- **Severity**: Low
- **Location**: Combat, seen after the Scarp Adder Keri fight at eastern-descent (3,3)
- **Steps to reproduce**:
  1. Win a 1v1 fight down to the last enemy.
  2. Immediately `GET /api/combat/status`.
  3. Top-level `combat_active: false` (correct), but `battle_state.status` still reads `"active"`; `battle_state.enemies` is correctly empty.
- **Expected**: The two status signals agree, or the API only exposes one.
- **Actual**: They disagree for at least one poll after the kill. Not the same as the documented #682 (a corpse still listed as an active combatant) — here the enemy is fully removed from the list, only the redundant status string is stale.
- **Confidence**: Seen once; did not attempt to reproduce a second time (low priority, did not block play).

### Finding 4 (Observation) — Post-`beta_end` API surface is intentionally permissive
- Movement, `/api/world/events`, and re-triggering the Ferry Landing `enter` all continue to work normally after `beta_end: true` is returned. A second `enter` on the Ferry Landing replays the exact same narration and `beta_end: true` idempotently — no crash, no duplicate objective completion (confirmed: `OBJ_CH03_FERRY_LANDING` stayed in `completed`, did not re-appear or duplicate). This looks intentional — the API doesn't hard-lock the session, it just signals the client to show the end-of-beta dialog (`BetaEndDialog`) — but is worth the orchestrator's eyes since nothing stops a player from wandering the whole camp again post-ending.

### Finding 5 (Observation) — NPC chat `open` has no "already active" guard
- Calling `/api/npc/chat/open` twice in a row for the same NPC before `end` succeeds both times and mints two different `open_token`s; the first is left dangling. This matches the documented behavior of issue #674 ("a stale `open_token` is ignored on `end`, not blocked on `open`"), so I'm not filing it as a bug, but flagging it since a careless client could leak an open conversation slot.

### Finding 6 (Low/cosmetic) — The Tradepost's "Anvil" NPC gives a generic fallback for `pet`
- `POST /api/world/interact {"target_id": "<Anvil>", "action": "pet"}` returns the generic engine boilerplate "Jean successfully completes the 'pet' action." instead of any camp-flavored text, even though `pet` is explicitly advertised in its `keywords`. Low severity — cosmetic only.

## 5. Combat log summary

| # | Tile | Enemies | Rounds (beats) | Jean HP low-water | Potions used | Notes |
|---|---|---|---|---|---|---|
| 1 | eastern-descent (1,2) High Ledge | Rock Rumbler Gogij (lvl 5, 88 HP) | 33 | 64 (never dropped below that — Gorran tanked) | 0 | Discovered `Advance` has a beat-cooldown that only drains during active beats — had to feed `Wait`/number_input cycles to progress. See API note below. |
| 2 | eastern-descent (3,3) Scree Shelf | Rock Rumbler Alsavpi (88 HP) | 8 | 47 | 0 | Clean fight once fatigue/cooldown mechanics were understood |
| 3 | eastern-descent (3,4) Hounds Warren | Talus Hound Oharet + Talus Hound Nevior (67 HP each) | ~60 (hit the 40-round safety cap once, resumed) | 19 (before I found the fatigue-Attack-unavailable trap; recovered via `/api/inventory/use`) | 1 Restorative (via `/api/inventory/use`, +63 HP) | Two-enemy pack drained Jean's fatigue below Attack's 93-point cost, which the in-combat `Use Item` move (a flavor no-op — Finding #2) could not fix; switching to `/api/inventory/use` resolved it |
| 4 | eastern-descent (4,5)/(3,5) Nest Hollow area | Scarp Adder Hijliuwhe (60 HP) | 5 | 74 (no further drop) | 0 | Quick, no complications; battle_state.status staleness noted (Finding #3) |

All four encounters were unscripted wilderness fights (no boss/story combat expected in this assignment), fought only because they engaged on approach, per instructions.

## 6. Non-bug observations

- **Combat cooldown/fatigue learning curve via API**: `Advance` and `Attack` both carry real beat-cost cooldowns and fatigue costs (Attack = 93/200 fatigue) that are not obvious from `/api/combat/status` alone until you read `reason`/`reason_code` on each `available_options` entry. A naive move-loop (Advance→Attack→repeat) stalls indefinitely with "Move not ready yet" / "Not enough fatigue" — not a bug, just something worth documenting for future API testers (this primer's combat section could use one line: "check `reason_code` before assuming a move failed").
- Devet's `loquacity_current` dropped from 17 to 9 after a single `/respond` call in one case — noticeably steep, but I did not grade voice/pacing per the primer's instructions, just flagging as a pacing curiosity for the design team.
- Jambo's shop pricing (buy 75g Draught / sell for 37g / buyback at 37g) is internally consistent and the buyback ledger round-tripped perfectly.
- The Nomad Camp's map is dense with automatically-firing tile-entry scenes (CampEntry, RiversEdge, FireRing, Tradepost, CampFarEdge all fire on first entry with zero interaction needed) — good for pacing, but it means a "walk-through" QA pass captures nearly the whole content surface just by moving, with `talk`/`interact` mostly redundant after the fact (confirmed: `talk`-ing Mara after her auto-fired scene just returns idle flavor).

## Where I stopped

Session complete. Assignment finished within budget: reached the Ferry Landing, triggered `beta_end: true`, verified post-end behavior, and revisited scene tiles to confirm no repeats. Stopped naturally at the end of the assigned route rather than at a budget/time cap.
