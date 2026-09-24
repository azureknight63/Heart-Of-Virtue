# A3c — Votha Krr's response, Eastern Gate, Gorran's farewell, Eastern Descent breadth

## Header

- Tester: A3c, stack `leg0924c` (:5003, `config_qa_leg_0924.ini`)
- Tool calls used: ~95 of 220 budget
- Ended: map `eastern-descent-nomad-camp`, tile Camp Entry (3,0)
- Level 6, HP 107/116, gold 625
- Start confirmed pre-seeded as briefed: Grondia (7,9) GrondelithEntrance, level 6, Gorran in party, `Rare Mineral Fragment` in inventory, Votha Krr's response NOT yet given.

## Route checklist

| Step | Result | Evidence |
|---|---|---|
| 1. Quick gate check (14,5)->(15,5), interact once | PASS (refuses) | `"Jean runs a hand along the seam in the stone, but the gate gives no purchase — whatever seals it hasn't yielded yet."` |
| 2. Citadel (10,5) AfterKingSlimeReturn, full stages | PASS | see below |
| 2b. Fragment leaves inventory | PASS | `Rare Mineral Fragment` absent from `/api/inventory` after the scene |
| 2c. Ch02FragmentReminder does not nag after | PASS | no nag on 2 subsequent visits/moves |
| 2d. Revisit (10,5) does not repeat | PASS | `pending()` empty on return |
| 3. Walk to gate, "Step through", eastern-descent (0,2) | PASS | see below |
| 3b. GorranGestureEvent fires on arrival | PASS | fired inline inside the transition event's own output, not as a separate pending event (see Finding 2) |
| 3c. Try going back west through the gate | PASS | works both ways; lever/teleport intact |
| 4. Eastern Descent — all 32 tiles | PASS (all 32 visited, described below) | tile table below |
| 5. Enter Nomad Camp, stop after CampEntry | PASS | arrived `eastern-descent-nomad-camp` (3,0) "Camp Entry"; Liss intro scene fired and completed |

## Votha Krr scene (AfterKingSlimeReturn) — full transcript

Named "Votha Krr" throughout (never "???") — consistent with #657 since the intro already happened earlier in this pre-seeded run.

Stage 1 (choice — picked non-default option **b**, "What is this thing, exactly?"):
> "Votha Krr rose from his throne as Jean entered. His deep-set eyes took in the bleeding finger, the fragment in Jean's hand, and Jean's expression — all at once.
> The pools are clean, little one. You have done well.
> Jean still held the mineral fragment. The cut on his finger had stopped bleeding but hadn't stopped hurting."
> Options: a) "Hand it over." b) "What is this thing, exactly?" c) [Set it on the edge of the throne without a word.]

Stage 2 (after choosing b):
> "What is this thing, exactly?
> A memory, made stone. The mineral pools do not merely hold water — they record what passes through them. Light, creature, time. This fragment carries something very old. It is right that it returns to stone.
> He took the fragment from Jean's hand."

Stage 3:
> "Votha regarded the fragment for a single moment — then placed it in his mouth.
> A soft, contented rumble escaped him. The fragment was gone."

Stage 4:
> "The pools are clean. You have done what we could not do alone, little one.
> He studied Jean's face. Then — the bleeding finger. He regarded it for a moment without comment.
> You came back.
> He said it simply. As an observation, not a compliment."

Stage 5:
> "To mend what is broken, one must first understand the cracks. Go now. Seek the Echoing Caves to the west, beyond the river. There, the earth sings the songs of lost things. Perhaps you will find a different kind of strength there — or, at the very least, a clearer path."

Stage 6 (final):
> "He did not elaborate. When Jean opened his mouth, Votha Krr's only answer was to press two fingers briefly to his own chest — over the place a human would call the heart — and then withdraw."

Event then completes (`needs_input: false`). **Observation**: Votha Krr's own send-off text points Jean toward "the Echoing Caves to the west, beyond the river" — geographically opposite the Eastern Descent this beta scopes. Likely intentional flavor/foreshadowing for a later chapter, not a bug, but flagging in case it's meant to gate differently.

## Gate transition / Gorran's farewell

Interacting with the Eastern Gate ("enter") after the Votha Krr scene produces a `PassagewayTransitionEvent` ("Step through?"); answering "continue" delivers the transition text **and** the farewell in the same `output_text`/`segments` payload — there is no separate pending `GorranGestureEvent` to poll for:

> "The mountain air hits without warning — cold, thin, carrying the smell of raw stone and something older than either. Behind Jean, the Eastern Gate of Grondia has drawn itself shut: a slow grinding of counterweights that finishes with a sound like a word being swallowed. The rock face here is dressed stone giving way to undressed rock within a few paces.
> A worn path descends east along the bluff's edge. Set into the stone beside the gate, a counterweight lever still moves freely — whatever sealed the gate can be worked again from this side.
>
> Gorran paused at the gate as it sealed. His palm rested flat against the stone — one breath, maybe two. Then he turned without a word and followed.
>
> Jean did not ask him."

This matches the primer's expected start/end verbatim. Checked `pending()` immediately after arrival, again after a `POST /api/world/events`, and again on a later poll — all empty, confirming the farewell is emitted synchronously as part of the transition event's segments rather than queued separately (the orchestrator's "zero pending events" observation in the smoke test is explained: there's nothing *to* be pending — it already fired). Read `src/story/ch03.py::GorranGestureEvent.check_conditions` (lines ~49-89): it requires `player.previous_tile` to resolve to a Grondia-prefixed map via `map_name_for_tile`, is one-shot (`gorran_gesture_done` flag), and explicitly guards against a stale `previous_tile` left over from wandering the destination map itself (per the code comment, referencing issue #547). Walking (14,5)->(15,5) before entering the gate (as instructed) satisfies this; the event fired correctly.

Going back west through the gate from (0,2) works: same transition-event/confirm flow, returns to Grondia (15,5) "Gate East" with matching description. Re-entering east works too and does not re-fire the farewell (one-shot flag holds).

## Eastern Descent tile table (32/32 tiles)

| Tile | Title | Match to JSON | NPCs/objects | Notes |
|---|---|---|---|---|
| (0,2) | GrondiaEasternGate | PASS | Eastern Gate | entry point |
| (1,2) | HighLedge | PASS | RockRumbler (fought) | see Finding 1 (combat stall) |
| (2,2) | Windbreak | PASS | none | |
| (3,2) | WaymarkerStone | PASS | Carved Stone Marker (read, text matches JSON) | |
| (3,1) | WaymarkerCave | PASS | Shadowed Bundle (hidden, found via search + take_all: 12 Gold, Iron Ration) | |
| (4,2) | CrowsPerch | PASS | none | |
| (4,1) | UpperRidge | PASS | none | |
| (5,1) | NorthFaceTrail | PASS | RockRumbler (fought, dropped Polished Rusted Iron Mace) | |
| (5,0) | EagleNest | PASS | Sheltered Corner (take_all: 20 Gold, Iron Ration) | |
| (5,2) | LookoutCrack | PASS | none | |
| (6,1) | Precipice | PASS | none | |
| (7,1) | EasternOverlook | PASS | none | dead-end view tile, matches design |
| (4,3) | FirstSwitchback | PASS | none | |
| (3,3) | ScreeShelf | PASS | RockRumbler (fought — see Finding 1, stalled twice, also hit fatigue exhaustion) | |
| (2,3) | BoulderGate | PASS | none | |
| (1,3) | RainCatch | PASS | Muddy Ledge (take_all: Iron Ration) | |
| (2,4) | HollowClearing | PASS | 2x TalusHound (fought clean, dropped Rock of Perseverance + Gold) | |
| (1,4) | MossShelf | PASS | Mynx Pag (ambient, `llm_chat_enabled: false`), HealingSpring, Mossy Crack (take_all: Bitterroot, 8 Gold) | see below |
| (3,4) | HoundsWarren | PASS | 2x TalusHound (fought, low-water HP 107) | |
| (5,3) | DeepCrack | PASS | ScarpAdder (fought, no poison landed) | |
| (6,3) | FarReach | PASS | Shallow Recess (take_all: 40 Gold, Longsword, Merchant's Journal Fragment) | |
| (4,4) | EasternTrailhead | PASS | none | |
| (5,4) | AddersShelf | PASS | ScarpAdder (fought — **poisoned Jean**, see combat log; cured with Antidote) | |
| (6,4) | RoadEast | PASS | Eastern_Road_Turnback event fires, turns Jean back | see Finding 3 (`new_position` mismatch) |
| (3,5) | LowerBend | PASS | none | |
| (4,5) | NestHollow | PASS | ScarpAdder (fought clean) | |
| (2,5) | LowerSlope | PASS | none | |
| (1,5) | GrassBreak | PASS | none | |
| (1,6) | BankApproach | PASS | none | |
| (2,6) | EasternBank | PASS | none | |
| (3,6) | NomadCamp | PASS | Camp Entrance (entered last, per assignment) | |
| (4,6) | CampsEdge | PASS | none | |

Every tile's live `description` matched the map JSON verbatim (spot-checked full text on ~10 tiles, exits/title matched on all 32). No missing exits, no unexpected dead ends beyond the two by-design ones (EasternOverlook's cliff-edge view, RoadEast's turnback).

### Mynx (1,4)

`llm_chat_enabled: false` confirmed (ambient LLM off, as expected on this stack). `talk`/`play` both produce deterministic fallback flavor text:
- play: "Jean tries to play with the mynx.\nMynx Pag crouches low, tail twitching, then pounces at the object with a playful yip."
- talk: "Jean interacts with the mynx.\nMynx Pag tilts its head, watching your every move with bright, intelligent eyes."

No crash, no stub/placeholder text leaking through.

### HealingSpring (1,4)

`drink`/`clean` heals to full HP and is freely repeatable (drank twice back-to-back; first restored 113->116, second was a no-op since already at max — did not overheal). Not abusable for farming since it caps at max HP, but it is an unlimited free full-heal available before every fight past that point on the route — flagged as a balance observation, not a bug.

## Fix verification (known-fixed issues)

| Issue | Result | Evidence |
|---|---|---|
| #669 Eastern Gate refuses until Votha Krr | PASS | quoted refusal text above; confirmed both before Votha's scene and re-confirmed structurally by reading `src/story/ch03.py` |
| #609 TAKE ALL / take_all on containers | PASS | used successfully on 5 different containers (Shadowed Bundle, Sheltered Corner, Muddy Ledge, Mossy Crack, Shallow Recess), all correct contents |
| #657 Votha Krr named, not "???" | PASS | named throughout (see above) |

## Findings

### Finding 1 — Severity: High — Player Attack move can stall permanently in recoil, blocking all further player input until an unrelated move is issued

**Location**: Combat, first observed at Eastern Descent (1,2) HighLedge vs. Rock Rumbler, recurred at (3,3) ScreeShelf vs. Rock Rumbler.

**Steps to reproduce**:
1. Enter combat, Advance into range, cast Attack, and let it land (hit confirmed in `last_move_outcome`).
2. Immediately after the hit resolves, the player's `move_in_process` remains `{"current_stage": 3, "beats_left": 4, "name": "Attack"}` ("bracing for recoil").
3. Poll `GET /api/combat/status` repeatedly, including with real 6+ second sleeps between polls — `beats_left`/`current_stage` never change.
4. Any further `POST /api/combat/move {"move_type":"move","move_id":"Attack",...}` returns `{"error": "Move not ready yet", "success": false}` indefinitely (confirmed over 25+ consecutive attempts with 1.5s waits = ~40s of real time).

**Expected**: Recoil resolves after its stated `beats_left` and the player can act again (or beats progress with real time / subsequent poll, per the "combat beats" model).

**Actual**: Recoil never resolves through server-side idle polling or repeated same-move resubmission. The only way found to unstick it is to submit a **different** move (`Wait`, which needs a `number_input` follow-up for beat count) — that resets `current_stage` to 0 and combat proceeds. This happened twice independently in this run (both times against a Rock Rumbler, both times immediately after the player's first successful Attack landed).

**Evidence**: `/api/combat/status` log entries at (1,2): `"Jean braces himself as his weapon recoils."` at `round: 16`, then no further `combat`-type log entries appear until `"Jean uses Wait!"` at a wall-clock timestamp ~3m12s later (18:02:51 vs 18:06:03) — during that gap combat was fully live (`combat_active: true`) and 25+ Attack submissions all bounced off "Move not ready yet". Full `battle_state` payload captured in run log `RUNS\A3c_api.jsonl`.

**Confidence**: reproduced twice independently, same mechanism both times (first successful Attack after entering recoil never clears). Distinct from the primer's #682 description (which is about a corpse-stash resume or a stuck `direction_selection`) but is very likely the same family of stall — a move stuck in a cycle stage with nothing ever ticking it down outside of an unrelated move selection forcing a state reset. Combining this with the second run: when combined with fatigue exhaustion (Finding-adjacent, see below), the workaround loop (Wait -> number -> retry) can itself spend fatigue, making the stall costlier than it looks from the first case.

**Source**: `src/api/combat_adapter.py:2080-2127` (`_check_move_preconditions`, the "Move not ready yet" gate on `move.current_stage != 0`) and whatever normally decrements `current_stage`/`beats_left` outside of a fresh `select_move`/`select_move_and_target` call — I did not find the decrement path in the time budget available; flagging the symptom precisely so it's easy to locate.

### Finding 2 — Severity: Observation — GorranGestureEvent is not exposed as a separate pending event

Not a bug functionally (the farewell text does fire, verbatim, and only once), but worth noting for anyone building a client against the "poll pending events after arrival" pattern the primer describes: the farewell is bundled into the *same* response as the `PassagewayTransitionEvent`'s "Step through" confirmation (`POST /api/world/events/input` with `user_input: "continue"`), not surfaced via a subsequent `GET /api/world/events/pending`. A client that renders the transition event fully then separately polls `pending()` expecting a second scene (as this assignment initially suspected, given the orchestrator's "zero pending events" smoke-test note) will simply see nothing more — correctly, because there is nothing more to see. Confirmed this is consistent (checked pending() 3 times across the arrival: immediately, after `POST /api/world/events`, and after a later unrelated call — all empty both times I made this transition).

### Finding 3 — Severity: Low — `new_position` in the move response can diverge from the actual `room` in the same response

**Location**: (5,4) AddersShelf -> east -> (6,4) RoadEast, triggering `EasternRoadTurnbackEvent`.

**Steps to reproduce**:
1. Stand at (5,4) AddersShelf with `Eastern_Road_Turnback` not yet triggered (it's `repeat: true` so this reproduces every time).
2. `POST /api/world/move {"direction": "east"}`.

**Expected**: `new_position` and `room.x`/`room.y` in the same response describe the same tile the player ends up on.

**Actual**: The response's top-level `new_position` is `{"x": 6, "y": 4}` (the tile the move nominally targeted) while `room` in the same payload is still Adders Shelf at `x: 5, y: 4` (where `EasternRoadTurnbackEvent.process()` teleports the player back to, per `src/story/ch03.py:149-150`). A client trusting `new_position` over `room` would show the wrong tile. `where()`/`GET /api/world` immediately after both correctly report (5,4), so the final state is right — only the single response's two fields disagree with each other.

**Confidence**: reproduced once (event is repeat:true, easily reproducible again, did not re-test given budget). Design-intentional turnback confirmed correct (`src/story/ch03.py:110-150`, docstring: "the player is always turned back west to the preceding tile") — only the field-consistency issue is being reported.

**Source**: wherever `new_position` is set in the move route relative to when tile events are processed — likely `src/api/routes/world.py` or `GameService.move_player`, not directly inspected due to budget.

## Combat log summary

| Tile | Enemies | Rounds/beats | Jean HP low-water | Potions used | Notes |
|---|---|---|---|---|---|
| (1,2) HighLedge | 1x Rock Rumbler | stalled ~3min real time then resolved via Gorran finishing it | 116 (untouched — Gorran did the kill) | none | Finding 1 first occurrence |
| (5,1) NorthFaceTrail | 1x Rock Rumbler | clean | 116 | none | dropped Polished Rusted Iron Mace |
| (5,3) DeepCrack | 1x ScarpAdder | clean | 113 | none | no poison landed |
| (3,3) ScreeShelf | 1x Rock Rumbler | stalled again, also ran out of fatigue mid-fight (Attack: "Not enough fatigue" after repeated failed retries), used Rest to recover | 113 | none | Finding 1 second occurrence |
| (2,4) HollowClearing | 2x TalusHound | clean, fast (4 iterations) | 113 | none | dropped Rock of Perseverance + Gold |
| (3,4) HoundsWarren | 2x TalusHound | clean | 107 | none | |
| (5,4) AddersShelf | 1x ScarpAdder | clean but landed Poisoned (severe, escalating DoT, 44 beats) | 90 | 1x Antidote (cured Poisoned, restored HP to 107) | see status-effect note below |
| (4,5) NestHollow | 1x ScarpAdder | clean, 1 iteration | 107 | none | no poison landed |

Gorran confirmed as an active combat ally throughout — present in `battle_state.allies` every fight, HP visibly dropping across the run (270 -> 233 by (1,4)) from tanking hits, consistent with him being a full party member post-King-Slime. `/api/status` `party_members` also lists Gorran with `in_range: true` throughout.

ScarpAdder poison: only 1 of 3 ScarpAdder fights actually applied Poisoned to Jean (at AddersShelf); the other two (DeepCrack, NestHollow) resolved with no status effect, so it reads as a chance-based on-hit effect rather than guaranteed. Antidote correctly removed the status and restored a small amount of HP per its stated effect (`{"power": 15, "range": [12,18], "stat": "hp", "type": "heal"}` plus `status_remove` on Poisoned) — worked as described, no bug.

## Non-bug observations

- Votha Krr's farewell line points Jean toward "the Echoing Caves to the west, beyond the river" — the opposite direction from this beta's actual content (east). Likely intentional foreshadowing/red herring, flagging only because it reads as a possible content/scope mismatch.
- HealingSpring at (1,4) is an unlimited, unrestricted full-heal directly upstream of 5 more fights (HoundsWarren, DeepCrack/FarReach, AddersShelf, NestHollow) — makes that back half of the Descent meaningfully easier than the front half. Balance note, not a bug.
- The combat-stall bug (Finding 1) makes early fights feel much harder than intended if the player doesn't know to try a different move — a first-time player hitting this with no dev knowledge would likely believe combat is broken/frozen, since the UI (per the API contract) would show no cooldown countdown reaching zero.
