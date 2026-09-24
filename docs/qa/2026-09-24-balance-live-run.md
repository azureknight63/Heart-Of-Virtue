# Live balance run on the tuned enemy levels (#655 step 2)

**Date:** 2026-09-24 · **Scope:** measurement only. No engine code, tunables, or committed
configs were changed. This run plays the real, running API + React stack against the
committed `config_prod.ini` values (the ones landed in #655 step 2 / `src/npc_level_tables.py`)
and reads whatever the game actually does — it does not re-run the isolated arena harness
from `docs/qa/2026-09-24-balance-baseline.md`.

## TL;DR

| Target (#655) | Result on the live route |
|---|---|
| No deaths | **Failed, badly.** 4 of 4 attempts to play the shipped Grondia → Grondelith Mineral Pools → Eastern Descent → ferry route died. 3 died to ordinary Mineral Pools trash packs; the 4th reached King Slime and died to him. **None reached Eastern Descent or the ferry.** |
| Genuine HP pressure | Overshot into lethal. The pressure the arena baseline measured as "genuine but survivable" assumed an ally that the real story does not provide for this stretch of the route (see Headline #1). |
| King Slime's surge matters | Confirmed, in the one run that reached him. 4 Tidal Surge telegraphs, 2 dodged; the tell was visible and dodging cut the damage taken, but wasn't enough by itself for a solo Jean. |
| Fatigue not the only constraint | Confirmed, but not for the intended reason. Fatigue was never the bottleneck in any death (26–100% remaining every time) — HP ran out first, because Jean is fighting most of the route's hardest content alone. |

## Headline

1. **Gorran is absent for the entire Mineral Pools sequence, including King Slime — the arena baseline mostly measured this stretch with him present.** `Ch02GorranAtPools` (`src/story/ch02.py`) fires the instant Jean steps past the pools' threshold tile: it pulls every Gorran out of `combat_list_allies` and seats him at the arch to wait, and only `AfterDefeatingKingSlime` puts him back — after King Slime is dead, not before. I confirmed this directly against the live API: `battle_state.allies` was `[]` in every Mineral Pools fight I checked, trash and boss alike. The #655 step 1 arena baseline's headline numbers (0 deaths in 80 King Slime fights, low pack death rates) are the *with-Gorran* configurations; its own `_solo` rows for the same encounters — `KingSlime_L5_j4_solo` (19/20 deaths), `P_pack_3_4_max_j4_solo` (19/20 deaths) — are the ones that actually describe the Mineral Pools as the story plays it, and my 4 live runs land squarely in that band, not the reported "tuned and safe" one.
2. **All 4 attempts died inside the Mineral Pools.** 3 of 4 died to ordinary trash packs (4–5 enemies at once, spawned by stacked `NPCSpawnerEvent`s on the same tile) before ever reaching King Slime; the 4th reached him relatively fresh and still died. Eastern Descent and the ferry were never exercised live in this run.
3. **Fatigue was never the limiting resource.** Every death happened with 26–100% fatigue still in the tank. The constraint that actually killed Jean was HP/potions, and the deciding factor was being alone against packs the arena baseline's headline table assumed he'd fight with a 242-HP ally beside him.
4. **One backend bug seen (non-fatal, log-only):** `ValueError: None is not a valid UnavailableReason` in `src/moves/_base.py:1971` (`unavailability_reason`), firing repeatedly on the `Attack` move at the start of every combat. It's caught and logged (`"unavailability diagnosis failed for Attack"`), not something a player would notice, but it fired on essentially every fight and should get a ticket.

## Method

- **Stack:** the real running stack, not the isolated arena harness — `CONFIG_FILE=config_prod.ini` API on `:5001` (`FLASK_ENV=testing`, `/api/test/session` login, all three LLM gates forced off) and the real Vite frontend on `:3001`, started via the `orchestrate-qa-testers` skill's `start_stack.py`/`qa_api.py`. Chromium at `/opt/pw-browsers/chromium-1194` for the browser check; no `playwright install` run.
- **Driver:** a scratch Python driver (not committed) hitting the live HTTP API directly with `requests` — real session creation, real `/api/world/move`, `/api/world/interact`, `/api/combat/*`, `/api/shop/*`, `/api/inventory/use`, exactly the routes the frontend calls. Route-finding used a BFS pathfinder built from the actual map JSON (`src/resources/maps/*.json`) plus the real `Passageway` objects' `teleport_map`/`teleport_tile` (Grondia (7,9) → Mineral Pools (2,0) → arena (2,6) → back → Grondia (10,5) for the Votha Krr aftermath → (15,5) Eastern Gate → Eastern Descent (3,6) Camp Entrance → Nomad Camp (0,2) Ferry Landing). Story/dialogue events were answered generically (first "continue"/"begin"/"done"-shaped option), matching a player clicking through prose without making narrative choices.
- **Combat policy:** primarily the game's own Tactical Advisor suggestion (`battle_state.suggested_moves[0]`, the same heuristic the in-game advisor panel shows), which already attacks when affordable and rests when fatigue is tight, overlaid with the two policies below. This is a reasonable-but-not-expert proxy, not a skilled human — see Limitations.
  - **Careful:** drink a Restorative below 35% HP; Dodge when an enemy's `current_move` is a Tidal Surge or Slime Volley tell.
  - **Aggressive:** drink a Restorative only below 15% HP; never dodges a telegraphed tell.
- **Player start:** `config_prod.ini` as shipped — Jean L4 (110ish HP), Gorran ally, Rusted Iron Mace + full leather, 300 gold, 3 starting Restoratives + an Antidote. Pending level-up points spent evenly across strength/finesse/endurance. Shopped at Jambo's Tent with the starting gold (bought 1 more Restorative box, 100g — the driver only buys one unit per stock line, so it under-shops relative to the 315g on hand; see Limitations).
- **Runs:** 4 full-route attempts — 3 with the fixed death-stops-the-run logic (2 careful, 1 aggressive), plus 1 earlier careful attempt whose death-detection had a bug (it kept re-starting combat against an already-dead Jean afterward, producing garbage repeat rows) but whose *first* King Slime encounter, before that bug triggered, is genuine and is reported as a supplementary data point.
- **Browser:** a Playwright pass confirmed the stack renders for real players (login, the beta briefing dialog) at `logs/qa`-adjacent scratch screenshots (not committed). A second, dedicated in-browser King Slime pass — using `/api/debug/player/restore` between Pools trash fights *only* to reliably reach the boss, since a live solo Jean usually dies before getting there — was still running past this report's time budget; see Limitations for what it did and didn't confirm.

## Per-run results

| Run | Policy | Reached | Deaths | Lowest HP% | Fights (rounds) | Potions used | Fatigue low point | King Slime surge telegraph |
|---|---|---|---|---|---|---|---|---|
| A (careful, partial) | careful | King Slime fight | 1 (King Slime) | 38.9% before the killing blow | 5 trash fights (6–21 rounds each, all survived, lowest 17–73%) then King Slime (10 rounds) | 0 in the King Slime fight (3 used earlier) | 79% (never low) | **Yes — 4 tells seen, 2 dodged**, still died |
| B (careful) | careful | Pools trash, 3rd pack | 1 | 9.4% (died) | 3 fights: 24 rounds (25% low), 20 rounds (17% low), 17 rounds (died at 9%) | 6 (ran out before the 3rd fight) | 47% | not reached |
| C (careful) | careful | Pools trash, 3rd pack | 1 | 13.9% (died) | 3 fights: 20 rounds (25% low), 24 rounds (25% low), 12 rounds (died at 14%) | 6 (ran out before the 3rd fight) | 78% | not reached |
| D (aggressive) | aggressive | Pools trash, 2nd pack | 1 | 12.3% (died) | 2 fights: 29 rounds (12% low, survived), 3 rounds (died at 20%→0%, overwhelmed fast) | 1 | 26% | not reached |

Every "Pools trash" fight above was a stacked `NPCSpawnerEvent` pack of 4–5 enemies (Slime/Cave Bat/Corrupted Stone Creature combinations) attacking a Gorran-less Jean simultaneously — this matches the map data: several Mineral Pools tiles author two or three separate spawner events on the same coordinate (e.g. (4,2): 4 Slime; (3,4): 1 ElderSlime + 2 Slime + 2 Corrupted Stone Creature, matching the baseline's own "(3,4) pack").

Run A's King Slime fight is the only live confirmation of the boss this pass got: reached with 73% HP and full fatigue after one easy trash fight, King Slime went 10 rounds, telegraphed Tidal Surge 4 times, Jean dodged 2 of them, and still died with a 38.9% low-water mark just before the end — the tell mattered (dodging visibly reduced landed hits) but did not save a solo player.

## Bugs seen

- **`ValueError: None is not a valid UnavailableReason`** — `src/moves/_base.py:1971`, `unavailability_reason()`. Fires on essentially every combat start (`"unavailability diagnosis failed for Attack"` in the API log), caught internally so it never surfaces to the player or breaks a fight, but it's a real defect worth a ticket: the enum lookup doesn't treat `None` (i.e. "no reason, the move is available") as a valid input.
- No other 4xx/5xx irregularities across the ~400+ live API calls in these 4 runs, aside from the harness's own bug (see Method) re-issuing `/api/combat/start` against an already-dead player and getting trivial instant "victories"/"deaths" back — that's a driver defect, not a game one.

## What I could not do

- **Never reached Eastern Descent or the ferry.** All 4 attempts died inside the Mineral Pools. The route beyond King Slime (Eastern Gate, RockRumbler/TalusHound/ScarpAdder trash, the camp, the Ferry Landing) is unmeasured by this live pass.
- **The dedicated in-browser King Slime confirmation did not finish inside this task's time budget.** It was running against the live stack (with `/api/debug/player/restore` between Pools trash fights, deliberately *not* part of the balance numbers above, to get past the same Gorran-absence problem reliably) but had not produced its telegraph screenshot when this report was written. The plain Playwright login/briefing screenshot did succeed, confirming the real frontend renders correctly against `config_prod.ini` on this stack. If it completes after this report is filed, the screenshots (if any) will be in the session's scratch directory, not committed.
- **Shopping was under-done.** The driver only buys one unit per stock line at Jambo's, so it spent 100 of Jean's 315 starting gold on a single extra Restorative box rather than stacking up supplies — a real player optimizing their shopping could plausibly survive runs B and C, which died only after burning through all 6 available charges. That caveat does **not** cover run D (aggressive), which died in 3 rounds to a burst of simultaneous attacks with fatigue and most of its HP still in reserve — more potions wouldn't have bought more than a beat or two there.
- **The combat policy is a scripted proxy** (the game's own Tactical Advisor suggestion plus a potion/dodge overlay), not a skilled human. A player who disengages, repositions, or retreats from an unfavorable pack — none of which this driver's policy does — would likely survive some of the trash-pack deaths above. So these numbers are closer to a lower bound on survivability than a hard ceiling, but the Gorran-absence finding (Headline #1) is a structural fact about the route, not an artifact of the policy: no combat skill compensates for the ally the arena baseline credited with roughly a third of the party's effective HP and a lot of the aggro simply not being there.
- Didn't check the specific named packs `(2,3)`/`(4,2)` the baseline table used — the live NPCSpawnerEvent rolls landed on comparable-sized packs, but not verified to be the exact same rosters.

## Recommendation

The #655 tuning pass measured the Mineral Pools (including King Slime) as if Gorran fights alongside Jean there. He doesn't — the story removes him at the threshold and returns him only after the boss dies. Re-running the arena baseline's Pools/King Slime rows in the `_solo` configuration (which the baseline already has, and which already shows near-total death rates) is the number that actually describes what a live player experiences on this stretch of the route. This is a maintainer decision, not a code fix from this pass: either retune the Pools/King Slime numbers around a solo Jean, or reconsider whether Gorran should sit out the whole interior.
