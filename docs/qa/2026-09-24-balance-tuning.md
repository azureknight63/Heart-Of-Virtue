# Balance tuning report — #617 enemy levels (#655)

**Date:** 2026-09-24 · **Build:** `ai/compassionate-franklin-zva2gu` (PR #680) with
`config_prod.ini`, the shipped beta-2 start (Jean level 4, Gorran in the party outside the
Pools). This closes the tuning loop #655 set out: arena sweep, full-route validation,
comparison against the targets, and a report.

## Verdict

All four #655 targets are met on the full Grondia → Mineral Pools → King Slime → Eastern
Descent → Ferry Landing route.

| Target | Before (#617 draft, 2026-09-17) | After (this build, 28 runs) |
|---|---|---|
| No deaths | 0 deaths, but the route was "flat" | **0 deaths in 28 runs**; every run reached the Ferry Landing |
| Genuine HP pressure | King Slime dealt **zero** damage in one run; only Pools packs had texture | Median lowest-HP per run: Pools 40–61%, King Slime 39–68%, Eastern Descent 22–67% |
| King Slime's surge matters | Both surges missed, or were dodged without cost | The two closest calls of the pass (2.9% and 3.9% HP) were King Slime fights where surges landed; arena: 4/80 deaths undodged vs 0/80 dodged |
| Fatigue not the only constraint | Fatigue was the binding limit everywhere | HP was the tighter limit in 119 of 160 Eastern Descent fights and 10 of 28 King Slime fights |

## The run

- **Stack:** the real API (`qa_api.py`, `FLASK_ENV=testing`, all LLM gates off) driven over
  HTTP through the same routes the frontend calls. Rendering of this combat UI in a real browser
  was confirmed in the second live run (`2026-09-24-balance-live-run-2.md`); this pass measured
  numbers, so it drove the API directly.
- **Driver:** the second live run's scratch driver, with three of its own bugs fixed first. None
  was an engine bug:
  - It answered the Wait prompt as `number_selection` instead of `number_input`.
  - It followed the advisor into idle moves (Turn, Check, Wait).
  - It answered a target prompt with an out-of-range enemy instead of one the server offered.
- **Policies, 28 full routes:**

  | Group | Runs | Policy | Clear | Spring |
  |---|---|---|---|---|
  | cm | 8 | careful | main route | yes |
  | cf | 8 | careful | every Pools and Eastern Descent enemy, Scarp Adders included | yes |
  | af | 8 | aggressive | every enemy | yes |
  | an | 4 | aggressive | main route | no |

  - **Careful:** drinks a potion under 50% HP and dodges a visible surge tell.
  - **Aggressive:** drinks only under 15% HP and never dodges.
  - **Both:** rest when Attack is fatigue-gated.
- **Fights:** 364 resolved; none stalled, timed out or stuck. The route covered every tuned
  enemy: Slime ×512, Talus Hound ×106, Stone Creature ×88, Rock Rumbler ×59, Cave Bat ×56,
  Scarp Adder ×48, Elder Slime ×32, King Slime ×28.

## Results by region

Lowest HP% and lowest fatigue% are per fight. "HP tighter" counts fights where HP fell further
than fatigue did.

| Group | Region | Fights | Lowest HP% (min / median) | Per-run lowest HP% (median) | Lowest fatigue% (median) | HP tighter |
|---|---|---|---|---|---|---|
| cm | Pools | 32 | 36.7 / 80.5 | 60.7 | 67.0 | 11/32 |
| cf | Pools | 64 | 40.5 / 79.4 | 50.8 | 62.4 | 15/64 |
| af | Pools | 64 | 11.9 / 80.2 | 39.8 | 64.9 | 16/64 |
| an | Pools | 16 | 29.0 / 58.7 | 45.8 | 68.2 | 10/16 |
| cm | King Slime | 8 | 3.9 / 38.9 | 38.9 | 27.1 | 3/8 |
| cf | King Slime | 8 | 33.6 / 68.2 | 68.2 | 30.9 | 0/8 |
| af | King Slime | 8 | 2.9 / 61.9 | 61.9 | 55.3 | 4/8 |
| an | King Slime | 4 | 22.3 / 42.6 | 42.6 | 73.3 | 3/4 |
| cm | Eastern Descent | 23 | 50.7 / 66.4 | 65.4 | 70.5 | 9/23 |
| cf | Eastern Descent | 64 | 50.7 / 67.9 | 67.0 | 96.2 | 50/64 |
| af | Eastern Descent | 64 | 23.5 / 57.6 | 52.2 | 88.6 | 53/64 |
| an | Eastern Descent | 9 | 17.2 / 35.9 | 22.3 | 76.8 | 7/9 |

**King Slime, per run** (lowest HP% · potions used):

| Group | Per-run results |
|---|---|
| cm | 26.9·2, 66.1·0, 24.6·1, 92.4·0, 43.2·2, 34.6·2, 49.2·1, 3.9·2 |
| cf | 45.7·1, 75.4·0, 91.2·0, 72.0·0, 64.5·0, 33.6·2, 90.9·0, 45.7·1 |
| af | 76.2·0, 79.1·0, 91.0·0, 90.0·0, 42.6·0, 47.6·0, 36.4·0, 2.9·2 |
| an | 22.3·0, 49.3·0, 81.0·0, 35.9·0 |

## Reading it

- **The Pools are a fatigue fight, and that is the design.** At the level-4 loadout Attack costs
  89 fatigue, so Pools packs drain fatigue harder than HP (HP tighter in 52 of 176 fights). HP
  still bites there: aggressive runs bottom out at 12–29% in single fights. Careful runs drank
  23 potions over the whole route across 16 runs.
- **King Slime is the spike, as intended, and it is swingy.** Whether surges land decides the fight
  more than the policy does. The worst two results (2.9% and 3.9%) both spent two potions to get
  through. No run died, and every surge is telegraphed, so this meets "no unwarned deaths". It is
  the one place to lower if you want a gentler beta: the lever is `KingSlime`'s damage growth in
  `ENEMY_GROWTH_PROFILES` (`src/npc_level_tables.py`).
- **Eastern Descent now has teeth.** Gorran fights here, and HP is the binding constraint. Clearing
  every tile (Scarp Adders included) takes an aggressive Jean to 23.5% at worst, and the no-spring
  runs to 17.2%. The careful routes stay above 50%.
- **Full clears level faster.** Full-clear runs end at level 6–7; main-route runs end at level 5–6.
  That is expected: more XP, and no region got trivial as a result.

## Not measured, or out of scope

- **The ferry does not go through.** Every run reached the Ferry Landing, which answers "not yet —
  something else still needs finishing". That gate is Mara's conversation. The driver cannot hold
  one with NPC chat off, so this is story gating, not balance.
- **`NPC_LEVEL_VARIANCE`:** the spawn roll's ±1 was swept in the arena
  (`2026-09-24-balance-baseline.md`), and the live runs rolled it naturally.
- **Tactical advisor:** it ranked Turn first mid-fight as "a solid baseline choice". A player who
  follows it idles. This is a follow-up, not a balance number.

## Sources

- `2026-09-24-balance-baseline.md`: the arena sweep, draft vs tuned values, and the dodge vs
  no-dodge King Slime rates.
- `2026-09-24-balance-live-run.md` and `2026-09-24-balance-live-run-2.md`: the two earlier live
  runs. They found the solo-Pools problem and the stuck-combat bug (fixed in PR #680).
