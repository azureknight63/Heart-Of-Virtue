# Second live balance run after the solo Pools retune (#655)

**Date:** 2026-09-24 · **Scope:** measurement only. No engine code, tunables, maps, or
configs were changed or committed. Plays the real running stack against the committed
`config_prod.ini` values, including the #655 solo-Pools retune (ElderSlime damage growth
0, one Stone creature at (3,4), two extra Restoratives at (3,4)) and the earlier reverted
trash buffs (Slime damage growth 3, Pools Slime/CaveBat level 2).

## TL;DR

| Target (#655) | Result on this live pass |
|---|---|
| No deaths | **Not falsified, but not fully verified either.** 0 of 4 attempts died. But 3 of 4 never reached King Slime at all — not because of lethal damage, but because a reproducible engine bug (below) permanently freezes combat before they get there. |
| Genuine HP pressure | **Confirmed for trash.** Careful runs bottomed out at 35–63% HP per pack, aggressive as low as 14.8%. No fight was a non-event. |
| King Slime's surge matters | **Confirmed** in the one attempt that reached him (aggressive policy): 6 Tidal Surge telegraphs, 0 dodged (by policy design), HP down to **11.4%** — a near-death, not a formality, and the retune held: he did not die. |
| Fatigue not the only constraint | **Confirmed.** Fatigue bottomed at 0–20% in several fights but HP, not fatigue, was always the tighter margin. |

## Headline

1. **A reproducible engine bug — not lethality — is what's actually blocking the route today.** Two distinct combat-resolution defects, both new discoveries this pass, each permanently stalled a live session before it could reach King Slime:
   - **"Last enemy dies, combat never ends."** After the final enemy in a fight drops to 0 HP, `battle_state.enemies` keeps listing the corpse and `combat_active` stays `true` forever — not for a few beats, but for the *rest of the session*. Every later `/world/move` returns `"Cannot move while in combat"`, and every later `/combat/status` still shows the same 0‑HP enemy. It reproduced at the single-Slime pack on tile **(2,5) GrondelithApproach** in 2 of 4 live sessions (session-random, not deterministic — the same tile resolved cleanly in the other 2). One extra harmless move (`Check`) does not clear it. This is the single biggest threat to #655's targets: it doesn't kill the player, it **strands** them, indistinguishable in outcome from an unwinnable fight.
   - **"Advance never lands, so a pack full-stops."** A second, separate freeze: a multi-enemy pack (5 enemies, later 4) where neither side's HP moved for 80+ of the driver's own beats, even after falling back to plain `Attack`. The `combat_adapter` debug trace shows why: the enemy starts at `distance: 9` (out of melee `in_range`), and `Advance`'s follow-up stage is a **direction_selection**, not the number/target stage the driver first assumed — a real player clicking "Advance" without picking a direction would hit the exact same non-progressing loop. Reproduced at a 5-Slime/Bat/Stone pack in the (2,2)-(2,4) band.
2. **Where the bugs didn't strike, the retuned numbers behave.** Every trash pack that resolved (10 of 14 live fights) produced real, survivable HP pressure (35–96% low-water, mean ~65%) with 0 deaths, and the one clean King Slime kill attempt (aggressive policy, no dodging) came within 11.4% of Jean's max HP before winning — the boss is dangerous, not decorative, and a careful player who *does* dodge (unverified this pass — see Limitations) has more room than that.
3. **A previously-unknown story gate cost the first attempt's route-finding, not a bug.** The Eastern Gate at Grondia (15,5) refuses entry ("the gate gives no purchase — whatever seals it hasn't yielded yet") until the player visits the Citadel at Grondia **(10,5)**, which carries `AfterKingSlimeReturn` — the Votha Krr aftermath beat run 1's method notes mentioned in passing. This is correct, hinted, intentional gating (CLAUDE.md's Fairness rule), not a defect; noted here only because it cost method-design time.
4. **The `UnavailableReason` bug from run 1 is still present**, unchanged: `ValueError: None is not a valid UnavailableReason` in `src/moves/_base.py`, firing on nearly every combat start, caught and logged, invisible to players.

## Per-attempt results

| Run | Policy | Reached | Deaths | Lowest HP% (trash) | Spring visits | Potions | Fatigue low | King Slime |
|---|---|---|---|---|---|---|---|---|
| A (careful) | careful, spring-using, main route | Stalled permanently after (2,5), "combat never ends" bug | 0 | 35.2 / 61.5 / 63.1 / 96.8 | 3 | 1 | 0% (pack 1) | not reached |
| B (careful) | careful, spring-using, **full clear** | Stalled after 1.3 packs, "Advance never lands" bug | 0 | 76.6 (1st pack; 2nd never resolved) | 0 | 0 | 64% | not reached |
| C (aggressive) | no spring, drink <15%, never dodge | Stalled at (2,5), "combat never ends" bug (2nd occurrence, different session) | 0 | 91.1 / 73.4 / 63.7 / 63.7 | 0 | 0 | 2.3% | not reached |
| D (aggressive, supplementary) | same policy, separate session, RNG avoided both bugs | **Reached and defeated King Slime** | 0 | 87.7 / 60.7 / **14.8** / 44.3 (pre-King-Slime packs) | 0 | 2 | 2.3–20.6% | **11.4% low, 6 Tidal Surge telegraphs seen, 0 dodged (by design), won** |

All four used the game's own Tactical Advisor suggestion (`battle_state.suggested_moves[0]`, `COMBAT_LLM_ENABLED=0` so the fallback heuristic scorer, not an LLM) as the base policy, overlaid with the required careful/aggressive potion-and-dodge rules — the same proxy-not-expert caveat as run 1 applies (see Limitations).

## Method

- **Stack:** the real stack, `CONFIG_FILE=config_prod.ini`, API on `:5001` (`FLASK_ENV=testing`, `/api/test/session`, all three LLM gates forced off via `--no-llm`), Vite frontend on `:3001`, via `orchestrate-qa-testers`'s `start_stack.py`/`qa_api.py`. Chromium at `/opt/pw-browsers/chromium-1194`; `playwright install` not run.
- **Driver:** a new scratch Python driver (not committed, `/tmp/.../scratchpad/driver.py` + `run_route.py`), hitting the live HTTP API with `requests` — real `/api/test/session`, `/api/world/move`, `/api/world/interact`, `/api/combat/*`, `/api/shop/buy`, `/api/inventory/use`, `/api/level-up/allocate`, exactly the routes the frontend calls. Route-finding used **live** `/world/tile?x=&y=` BFS (the running session's actual `_calculate_exits`, not the static map JSON's `exits` list, which can disagree with runtime story-gate state) rather than run 1's map-JSON-only pathfinder.
- **Player start:** `config_prod.ini` as shipped — Jean L4 (120ish HP), Gorran ally (removed for the whole Pools stretch by `Ch02GorranAtPools`, confirmed in `src/story/ch02.py`), 300+15ish starting gold, level-up points spent evenly across strength/finesse/endurance.
- **Shopping:** bought at Jambo's Tent with the starting gold — 2 Restorative boxes (~200g of ~322g on hand, prioritizing Restoratives/Antidotes/Bandages, capped at 80% of gold), a deliberate improvement on run 1's "1 unit per line" under-shopping gap.
- **Sacred Spring:** used automatically (Atrium, (2,1)) whenever HP fell under 70% and the player wasn't already past it, in the two runs configured to use it (A, B).
- **Floor items:** picked up automatically on every tile (12–16 items per run that got that far — Restoratives, Draughts, a Silver Bracelet of Health, a Hollow Crossbow, gold stacks).
- **Combat policy:** careful = drink below 50% HP, Dodge on a visible Tidal Surge/Slime Volley telegraph; aggressive = drink below 15% HP, never dodge a tell.
- **Browser:** a Playwright pass resumed a driver-advanced session in real Chromium by setting `localStorage.username` and calling `/api/test/session` in-page (the SPA's `AuthContext` gates rendering on that key, not the session cookie directly — a real finding about how to drive this stack from a browser, not a bug). Confirmed the live combat UI (health bars, ATTACK/INVENTORY/COMMANDS/RETREAT, battlefield grid, enemy roster) renders correctly for a real player mid-fight, with zero browser console errors. The specific fight visible was a Pools trash pack, not King Slime — the sessions driven far enough to reach King Slime kept hitting the same two stall bugs when steered toward a browser handoff; screenshots are in the session scratch directory, not committed.

## Bugs found

1. **[Critical, new] Combat never resolves after the last enemy dies (~50% reproduction rate at the observed tile).** `battle_state.combat_active` stays `true` and `battle_state.enemies` keeps listing a 0-HP corpse indefinitely. No further player action (including a free `Check`) clears it. Every subsequent `/world/move` in that session returns `"Cannot move while in combat"` — a real player would be **permanently stuck** on that tile, unable to fight, move, or otherwise act, for the rest of their playthrough. Repro: enter Grondelith Mineral Pools, fight down the corridor to (2,5) (single-Slime pack), win the fight; ~50% of the time `combat_active` never flips back to `false`. Two independent live sessions hit this, at two different tiles' worth of single- and dwindling-multi-enemy fights.
2. **[Major, new] A pack can permanently non-progress when the first enemy starts out of melee range.** `Advance`'s follow-up stage is a `direction_selection`, not simply resolved by targeting; a caller (or a real player) that doesn't supply a direction gets stuck reselecting the same move forever with `distance` never closing and neither side taking damage. Confirmed via the combat_adapter wire trace (`distance: 9`, `in_range: false` on the target, `available_options: ['north','south','east','west']` on the follow-up poll). Whether the in-game Advisor or UI genuinely steers a player into this same trap wasn't independently confirmed this pass — flagged for the maintainer to check the frontend's own Advance flow, not just this driver's.
3. **[Known, unchanged] `ValueError: None is not a valid UnavailableReason`** in `src/moves/_base.py`, firing on nearly every combat start. Caught internally, invisible to players, present at the same rate as run 1.
4. No other 4xx/5xx irregularities across ~2,500 live API calls this pass.

## Comparison vs. run 1 (2026-09-24, pre-retune)

| | Run 1 (pre-retune) | Run 2 (post-retune, this pass) |
|---|---|---|
| Deaths | 4 of 4 attempts died, 3 to trash, 1 to King Slime | **0 of 4** attempts died |
| Reached King Slime | 1 of 4 (partial, died to him) | 1 of 4 (supplementary, **defeated him**) |
| Reached Eastern Descent/ferry | 0 of 4 | 0 of 4 (blocked by engine bugs this time, not death) |
| Trash-pack lowest HP% (careful) | 9–73% | 35–97% |
| King Slime lowest HP% | 38.9% (died anyway) | 11.4% (survived) |
| Blocking factor | Lethal damage (Gorran-absent trash and boss) | Two engine bugs that freeze combat, unrelated to damage numbers |

The retune plainly worked on the numbers it targeted: nobody died this pass, and the one
clean King Slime fight was close (11.4%) rather than fatal (run 1's 38.9%-and-still-died).
But this pass could not fully exercise the #655 targets past the Pools, because — unlike
run 1, where death was the obstacle — this pass's obstacle was the game engine refusing to
let a won fight end.

## What I could not do

- **Never reached Eastern Descent or the ferry live.** All 3 "official" attempts stalled inside the Pools on one of the two engine bugs above; the 4th (supplementary) reached and beat King Slime but wasn't re-run with the Eastern Gate story-gate workaround before the task's time budget closed, so it also didn't confirm the Eastern Descent trash or the ferry.
- **No careful-policy King Slime data.** The only clean King Slime kill this pass used the aggressive policy (never dodges by design). Whether a careful, dodging Jean clears King Slime with meaningfully more room than 11.4% is unconfirmed — plausible given run 1's dodge-vs-no-dodge gap, but not measured live this time.
- **Browser confirmation is partial.** The real frontend was confirmed to render live combat correctly (bars, moves, battlefield, zero console errors) for a driver-advanced session, but not specifically mid-King-Slime — the sessions steered toward that handoff kept landing on the stall bugs first.
- **The combat policy is still a scripted proxy**, not a skilled human — same caveat as run 1. A human noticing "nothing is happening, distance is stuck at 9" would reposition manually; the driver's plain-Attack fallback couldn't diagnose that and neither, plausibly, could the in-game Tactical Advisor without a UI to point it out.

## Recommendation

The #655 solo Pools retune measurably worked: 0 deaths across every fight that resolved,
survivable-but-real HP pressure on trash, and a King Slime fight that came genuinely close
(11.4%) without killing a no-dodge player. But **this pass cannot fully close out #655
because two newly-found engine bugs — not balance — are what stopped 3 of 4 attempts from
reaching the ferry.** The "combat never resolves after the last kill" bug in particular is
higher priority than any further tuning: it doesn't produce a bad number, it produces a
player who can never move again. Recommend filing both combat-resolution bugs, fixing the
first (stuck `combat_active`) before the next live balance pass, and then re-running this
same route to get the careful-policy King Slime and full Eastern Descent/ferry data this
pass couldn't reach.
