# Beta Test Scope — Grondia Arc

**Build:** v0.0.5-beta  
**Date:** 2026-05-07  
**Tester profile:** Solo, internal  
**Primary focus:** NPC dialogue and quest progression  
**Arc scope:** Grondia entrance → river crossing with Mara (Eastern Descent)

---

## Prerequisites

Before beginning, confirm the following:

- [ ] A fresh save is loaded (or an existing save with the Lurker already defeated in Verdette Caverns).
- [ ] Jean is positioned at or able to reach Grondia tile `(1, 2)` — the first passage tile of the Grondia map.
- [ ] The API server is running (`python tools/run_api.py`) and the frontend is accessible.
- [ ] The Feedback button is visible in the left panel of the game UI.

---

## Scene-by-Scene Test Cases

### Scene 0 — Beta Briefing (Grondia `(1, 2)`)

The `BetaTesterBriefing` event fires on first entry.

| # | Action | Expected result | Pass / Fail |
|---|--------|-----------------|-------------|
| 0.1 | Enter Grondia tile `(1, 2)` for the first time | Briefing event fires immediately; story recap text appears | |
| 0.2 | Read stage 1 (story recap) and click **Continue** | Stage 2 (beta notice) appears with the five test steps, feedback instructions, and credits notice | |
| 0.3 | Click **Begin** on stage 2 | Event completes; Jean is free to move | |
| 0.4 | Leave tile and return to `(1, 2)` | Briefing does **not** fire again | |

**Bug criteria:** Any stage that fails to advance, any text that is blank or garbled, or the event repeating on revisit.

---

### Scene 1 — Grondia Navigation

Explore key district tiles and verify NPCSpawner population and interactive objects.

| # | Action | Expected result | Pass / Fail |
|---|--------|-----------------|-------------|
| 1.1 | Move through passage tiles toward Arcology | Tile descriptions load; no blank descriptions | |
| 1.2 | Enter any Arcology tile (`(8, 4)`, `(8, 5)`, `(9, 5)`) | NPCSpawnerEvent fires; Grondite NPCs appear on tile | |
| 1.3 | Interact with a named object (e.g. Cold Hearth at `(8, 5)`) | Object description displays; no crash | |
| 1.4 | Enter Ecumerium tiles (`(11, 5)`, `(12, 4)`, `(12, 5)`) | Market objects present; NPCs spawn where expected | |
| 1.5 | Attempt `talk` with a Grondite NPC | Dialogue fires without crash | |
| 1.6 | Enter Conclave tile `(9, 3)` and talk to the Conclave Elder | Placeholder intro fires; `conclave_elder_intro` flag set | |

**Known gap:** Conclave Elder side quest is stubbed — no quest mechanics, placeholder interaction only. Do not file this as a bug.

**Bug criteria:** Blank tile descriptions, NPCs not spawning where spawners exist, object interactions crashing, dialogue not loading.

---

### Scene 2 — Grondelith Mineral Pools / King Slime

| # | Action | Expected result | Pass / Fail |
|---|--------|-----------------|-------------|
| 2.1 | Navigate to Grondelith Entrance at `(7, 9)` | Tile loads; passage to Mineral Pools available | |
| 2.2 | Enter the King Slime arena | `Ch02ArenaEntrance` event fires; corruption narrative displays; King Slime is present | |
| 2.3 | Defeat the King Slime | `AfterDefeatingKingSlime` fires; pools cleanse; MineralFragment spawns on island | |
| 2.4 | Pick up the MineralFragment | `Ch02KingSlimeMemoryFlash` fires; explosion memory sequence plays | |
| 2.5 | After pickup, confirm `king_slime_defeated` story flag is set | Gorran arrives at arena; pool tile description updates to clean state | |

**Bug criteria:** Arena event not firing, King Slime not entering combat, pools not cleansing after defeat, MineralFragment not spawning, memory flash not triggering.

---

### Scene 3 — Citadel Return / Votha Krr (`(10, 5)`)

| # | Action | Expected result | Pass / Fail |
|---|--------|-----------------|-------------|
| 3.1 | Return to Citadel tile `(10, 5)` with MineralFragment in inventory | `AfterKingSlimeReturn` fires; Votha Krr rises and addresses Jean | |
| 3.2 | Choose any dialogue option for the fragment | Votha Krr consumes the fragment; dialogue plays to completion | |
| 3.3 | Votha Krr delivers his directive (Echoing Caves / river) | Full speech plays; `votha_krr_response_given` flag set | |
| 3.4 | Leave and re-enter `(10, 5)` | `AfterKingSlimeReturn` does **not** fire again | |
| 3.5 | Confirm MineralFragment removed from inventory | Item absent from inventory screen | |

**Bug criteria:** Event not firing, event repeating on revisit, fragment remaining in inventory after scene, missing dialogue lines.

---

### Scene 4 — Grondia Exit → Gorran Farewell (Eastern Descent `(0, 0)`)

| # | Action | Expected result | Pass / Fail |
|---|--------|-----------------|-------------|
| 4.1 | Exit Grondia heading east | Map transition to Eastern Descent loads without crash | |
| 4.2 | Arrive at Eastern Descent tile `(0, 0)` | `GorranGestureEvent` fires; Gorran places palm on the sealed gate — farewell scene plays | |
| 4.3 | Confirm `player.previous_tile` was in Grondia | Event fires only when arriving from Grondia (not from other directions) | |

**Bug criteria:** Map transition crash, farewell scene not firing, farewell scene firing when arriving from a non-Grondia tile.

---

### Scene 5 — Eastern Descent Map Entry / Mara Spawn

| # | Action | Expected result | Pass / Fail |
|---|--------|-----------------|-------------|
| 5.1 | Confirm Mara spawns at NomadCamp `(2, 5)` on map entry | Mara is present at the river camp tile | |
| 5.2 | Confirm Devet is also present at `(2, 5)` | Devet (cook) appears alongside Mara | |
| 5.3 | Confirm Liss is present | Liss (young observer) appears at camp | |

**Bug criteria:** Any camp NPC missing after map entry.

---

### Scene 6 — Mara Dialogue

| # | Action | Expected result | Pass / Fail |
|---|--------|-----------------|-------------|
| 6.1 | `talk` with Mara (first interaction) | Canned line 1 plays: observation/glance line | |
| 6.2 | `talk` with Mara (second interaction) | Canned line 2 plays: the nod line | |
| 6.3 | `talk` with Mara (third interaction) | River-crossing line surfaces: *"The river's crossable this time of year. Careful of the current at the bend."* | |
| 6.4 | `talk` with Mara (fourth interaction) | Line 4 plays: the studying/returning-to-sorting line | |
| 6.5 | Assess voice consistency | Mara is sparse, sardonic, practical; no warmth, no exposition dumps; consistent with `ai/npc/human/mara.json` loquacity (60) and prohibited phrases | |
| 6.6 | `talk` with Devet | Dialogue fires; camp cook voice (older, practical, offers food/lodging) | |
| 6.7 | `talk` with Liss | Dialogue fires; young observer voice; may reference people going west | |

**Bug criteria:** Any `talk` crashing, LLM dialogue that breaks Mara's voice (overly warm, verbose, using prohibited phrases), missing canned lines.

---

### Scene 7 — River Area and Story Gate

| # | Action | Expected result | Pass / Fail |
|---|--------|-----------------|-------------|
| 7.1 | Navigate to RiverBank tile | Tile loads with correct description; Mara's raft interaction available | |
| 7.2 | Navigate to RiversBend tile | Tile loads; river-crossing option present | |
| 7.3 | Attempt to move east past `(5, 2)` | `EasternRoadTurnbackEvent` fires and blocks the exit; Jean is turned back | |
| 7.4 | Confirm turnback event is repeating | Attempting to go east again re-triggers the block | |

**Known gap:** There is no dedicated river-crossing completion event. Crossing is a narrative/dialogue beat via Mara, not a hard story-state transition. Do not file the absence of a post-crossing story flag as a bug.

**Bug criteria:** River tiles missing descriptions, raft interaction crashing, turnback event not firing at `(5, 2)`, turnback event firing only once instead of repeating.

---

## Known Gaps (Intentionally Not Tested)

| Gap | Status |
|-----|--------|
| `AfterDefeatingLurker` event is a no-op | Disabled for this beta — story continuation from Verdette Caverns is not in scope |
| No river-crossing completion event | Not yet implemented; the crossing is narrative only |
| Grondia quest chain JSON not defined | Formal chain tracking (`active_chains`, `chain_progress`) not wired for this arc |
| Conclave Elder side quest `(9, 3)` | Placeholder only — quest mechanics not implemented |

---

## Bug Filing Template

```
Severity: Critical / High / Low
Location: <map name> tile (<x>, <y>)
Steps to reproduce:
  1.
  2.
Expected: 
Actual: 
Screenshot: (attach or paste path)
```

**Severity guide:**
- **Critical** — game crash, soft-lock, or data loss
- **High** — wrong story flag, event not firing, NPC missing, dialogue truncated
- **Low** — typo, visual glitch, pacing issue, voice inconsistency

Use the **Feedback** button in the left panel to submit. Include your name or contact if you want to appear in the credits.
