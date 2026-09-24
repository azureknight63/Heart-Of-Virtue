# Arena balance baseline for the #617 enemy levels (#655, step 1)

**Date:** 2026-09-24 · **Scope:** measurement only. No engine code or tunables were changed. The values under "Proposed tuning" were tried with in-process overrides in a scratch driver, and none of them has been applied to `src/npc_level_tables.py`.

## TL;DR

| Target (#655) | Draft values as measured |
|---|---|
| No deaths | **Failed.** King Slime at its draft level 6 killed Jean in **9 of 20** fights at Jean level 5, and **14 of 20** at level 4 (10/20 when the player dodges the tell). The Pools (3,4) pack at the top of its level roll killed him in **6 of 40**. |
| Genuine HP pressure | **Failed everywhere except those two lethal cases.** Every other enemy, one at a time or in its authored pack, left Jean at ≥ 68% HP at his lowest point on average. Talus Hounds cannot damage Jean at all, since their damage is below his armour. |
| King Slime's surge matters | **Too much.** At level 6 (100 damage) a landed Tidal Surge rolls 144–216 raw, which is more than Jean has at full health. **Tidal Surge was the killing blow in 11 of 14 deaths.** This recreates the full-HP-to-dead hit that #586 part B removed. `tests/test_tidal_surge_balance.py` misses it because it builds a level-1 King Slime. |
| Fatigue is not the only constraint | Mixed. Trash fights end with fatigue at 55–90%. Only the boss and the (3,4) pack pull fatigue low (lowest point 10–50%). |

With the proposed values below, King Slime at level 5 had **0 deaths in 80 fights** (Jean at level 4 or 5, dodging or not). His lowest HP averaged 52–73%, with minimums of 1–18%, and the biggest landed surge was 65–75% of Jean's HP. The (3,4) pack had 0 deaths in 120 fights, lowest HP averaging 65–74%. The Pools and Eastern Descent trash now land real damage without killing him.

## Method

- **Harness:** `create_app(TestingConfig)` with a `tools/harness` `GameClient`, in-process, following `tools/bug_hunt.py`'s combat scenario. Each fight starts a fresh session from a scratch config (`startmap = combat-testing-arena`). The enemy is staged on the Fodder Pit (1,0), Jean walks east (the enemy is aggro, so combat opens on arrival), and the fight is driven only through `GET /api/combat/status`, `POST /api/combat/move` and `POST /api/inventory/use`.
- **Enemy level:** each enemy is built by class, given `growth_profile = ENEMY_GROWTH_PROFILES[cls]`, and then `sync_level(L)` is called. That is exactly what `apply_enemy_level` does, minus the roll, so the level is pinned. The debug op could not be used; see "What didn't work".
- **Levels swept:** each enemy's `REGION_ENEMY_LEVELS` base and base ± `NPC_LEVEL_VARIANCE` (1). King Slime is `is_boss` and never rolls, but 5/6/7 was swept anyway, plus level 1 as the pre-#617 reference.
- **Randomness:** `random.seed(4242)` before session creation, so every run has the same Jean with the same level-up stat rolls. Then `random.seed(1000+i)` per fight. Runs are 20 per configuration, and 40 for the pack follow-ups. Seeding does **not** make a fight fully reproducible: two runs of the same (3,4) max-roll configuration gave 0/20 and 6/40 deaths, most likely because combatant handles are UUIDs and some ordering depends on them. Read death counts as rates with a wide band, not exact values.
- **Player policy** (a competent but unexceptional player):
  1. Below 35% HP, drink a Restorative (3 carried; free on Jean's turn, as the client does it).
  2. Only in `--dodge` runs: if an enemy's current move is a Tidal Surge or Slime Volley still in its prep stage, Dodge.
  3. Otherwise use the first available Offensive move, aimed at the lowest-HP enemy in range.
  4. If an enemy is in reach but no attack is affordable or off cooldown, Rest.
  5. Otherwise Advance; failing that, Wait.

  Jean's L4 kit is Attack, Dodge, Crusader's Oath, Advance, Withdraw, Rest and Wait (`learn_all_skills = False`). The policy uses only Attack, Dodge, Rest and Advance.
- **Instrumentation:** each hostile move class's `execute` was wrapped at runtime to record the damage Jean took, the killing blow and surge outcomes, and `Player.gain_exp` was wrapped to record exp. HP% is sampled at every decision point (Jean's turns). Deaths are counted from the engine outcome.
- **Enemy card columns:** "hit%→Jean" is `to_hit_chance(enemy, Jean, base=NPC_HIT_CHANCE_BASE, floor=1)`, so it leaves out facing modifiers.

## Assumptions: Jean on the beta route

| Point on route | Jean | Why |
|---|---|---|
| Grondelith Mineral Pools, early | **Level 4**: 110 HP, protection 23.3, finesse 17, fatigue 208 | `config_prod.ini`: `starting_level = 4`, points spent by the player (modelled with the `even` policy). Loadout: RustedIronMace in hand, Shortsword in pack, full leather set, 3 Restoratives + Antidote. Gorran joins at level 4 (242 HP, 64 damage). |
| Pools, late / King Slime | **Level 4–5** (both measured; L5: 114 HP, protection 24.9) | Measured exp per fight: a single Slime ≈ 24, the (4,2) 4-Slime pack ≈ 107, the (2,3) pack ≈ 136, the (3,4) pack ≈ 207, an ElderSlime ≈ 58. Summing the map's `NPCSpawnerEvent`/gland spawns gives ≈ 1,000 exp before King Slime. Level 4→5 costs ~604–620, so Jean usually reaches **L5 before the boss**, which matches #617's "two levels inside the dungeon" from an L3 start. |
| Eastern Descent | **Level 5** (near 6) | King Slime pays ≈ 150–230 exp, which is not enough for L6 (another ~755). |
| All | **Gorran in the party** | Prod sets `starting_party_members = Gorran`, and he walks the descent until the gate farewell. `_solo` rows are sensitivity checks only. |

Not modelled: gear bought with the 300 starting gold, enemies spawned mid-fight by the pulsing glands, damage carried over between Pools fights, and the player spending points on something other than an even split.

## Results — draft values (as merged)

Tag format: `<Enemy>_L<enemy level>_j<Jean level>[_dodge][_solo]`. Pack tags use the map tile. `pack_pools_3_4` is ElderSlime + 2 Slime + 2 CorruptedStoneCreature, and `_max` rolls every member at base+1. HP% columns are percentages of Jean's max HP.

**Reading guide:**
- Every Slime, CaveBat, CorruptedStoneCreature, RockRumbler, ScarpAdder and TalusHound row with Gorran ends with Jean's lowest HP averaging ≥ 97%.
- TalusHound shows **0 landed damage in every configuration**: 16 + 3/level damage never beats 23 protection.
- King Slime at 5, 6 and 7 is lethal with or without Gorran.

| Config | n | Enemy @ level: HP / dmg / prot / hit%→Jean | Win % | Deaths | Jean HP% at end, mean (min) | Lowest HP% in fight, mean (min) | Beats | Potions | Lowest fatigue % | Biggest hit | Surges at Jean: landed/aimed (biggest) | Killing blows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CaveBat_L1_j4 | 20 | CaveBat@1: 15 / 23 / 0 / 78% | 100 | 0 | 100 (100) | 100 (100) | 21 | 0.00 | 82 | 0 | — | — |
| CaveBat_L2_j4 | 20 | CaveBat@2: 19 / 28 / 0 / 78% | 100 | 0 | 100 (98) | 100 (98) | 21 | 0.00 | 82 | 2 | — | — |
| CaveBat_L2_j4_solo | 20 | CaveBat@2: 19 / 28 / 0 / 78% | 100 | 0 | 100 (96) | 100 (96) | 22 | 0.00 | 80 | 4 | — | — |
| CaveBat_L3_j4 | 20 | CaveBat@3: 23 / 33 / 0 / 78% | 100 | 0 | 99 (91) | 99 (91) | 21 | 0.00 | 82 | 7 | — | — |
| CorruptedStoneCreature_L3_j4 | 20 | CorruptedStoneCreature@3: 84 / 30 / 24 / 65% | 100 | 0 | 100 (100) | 100 (100) | 29 | 0.00 | 64 | 0 | — | — |
| CorruptedStoneCreature_L4_j4 | 20 | CorruptedStoneCreature@4: 96 / 34 / 27 / 65% | 100 | 0 | 100 (97) | 100 (97) | 32 | 0.00 | 63 | 3 | — | — |
| CorruptedStoneCreature_L4_j4_solo | 20 | CorruptedStoneCreature@4: 96 / 34 / 27 / 65% | 100 | 0 | 99 (91) | 99 (91) | 38 | 0.00 | 56 | 10 | — | — |
| CorruptedStoneCreature_L5_j4 | 20 | CorruptedStoneCreature@5: 108 / 38 / 30 / 65% | 100 | 0 | 99 (95) | 99 (95) | 34 | 0.00 | 61 | 6 | — | — |
| ElderSlime_L3_j4 | 20 | ElderSlime@3: 98 / 40 / 16 / 66% | 100 | 0 | 97 (62) | 97 (62) | 34 | 0.00 | 63 | 42 | 1/3 (42) | — |
| ElderSlime_L3_j4_dodge | 20 | ElderSlime@3: 98 / 40 / 16 / 66% | 100 | 0 | 98 (62) | 98 (62) | 40 | 0.00 | 58 | 42 | 1/6 (42) | — |
| ElderSlime_L4_j4 | 20 | ElderSlime@4: 112 / 46 / 18 / 66% | 100 | 0 | 96 (53) | 93 (35) | 40 | 0.05 | 61 | 72 | 2/5 (72) | — |
| ElderSlime_L4_j4_dodge | 20 | ElderSlime@4: 112 / 46 / 18 / 66% | 100 | 0 | 96 (53) | 94 (35) | 46 | 0.05 | 49 | 72 | 2/7 (72) | — |
| ElderSlime_L4_j4_solo | 20 | ElderSlime@4: 112 / 46 / 18 / 66% | 90 | 2 | 63 (0) | 48 (0) | 58 | 0.30 | 54 | 73 | 19/24 (73) | Slime Volley ×2 |
| ElderSlime_L5_j4 | 20 | ElderSlime@5: 126 / 52 / 20 / 66% | 100 | 0 | 94 (45) | 88 (21) | 45 | 0.10 | 60 | 84 | 3/8 (84) | — |
| ElderSlime_L5_j4_dodge | 20 | ElderSlime@5: 126 / 52 / 20 / 66% | 100 | 0 | 95 (45) | 92 (24) | 49 | 0.05 | 47 | 84 | 2/7 (84) | — |
| KingSlime_L1_j4 | 20 | KingSlime@1: 400 / 50 / 15 / 64% | 95 | 1 | 78 (0) | 76 (0) | 105 | 0.05 | 51 | 67 | 7/13 (67) | Tidal Surge ×1 |
| KingSlime_L1_j4_dodge | 20 | KingSlime@1: 400 / 50 / 15 / 64% | 100 | 0 | 86 (50) | 81 (28) | 115 | 0.10 | 27 | 55 | 5/13 (55) | — |
| KingSlime_L5_j4 | 20 | KingSlime@5: 640 / 90 / 27 / 64% | 45 | 11 | 30 (0) | 20 (0) | 173 | 0.55 | 47 | 110 | 14/22 (110) | NPC_Attack ×2, Tidal Surge ×9 |
| KingSlime_L5_j4_dodge | 20 | KingSlime@5: 640 / 90 / 27 / 64% | 75 | 5 | 52 (0) | 32 (0) | 210 | 0.65 | 14 | 110 | 8/22 (110) | Tidal Surge ×5 |
| KingSlime_L5_j4_solo | 20 | KingSlime@5: 640 / 90 / 27 / 64% | 5 | 19 | 1 (0) | 0 (0) | 125 | 0.85 | 50 | 110 | 21/36 (110) | NPC_Attack ×3, Tidal Surge ×16 |
| KingSlime_L5_j5 | 20 | KingSlime@5: 640 / 90 / 27 / 63% | 70 | 6 | 53 (0) | 44 (0) | 165 | 0.35 | 61 | 114 | 10/16 (114) | Tidal Surge ×6 |
| KingSlime_L6_j4 | 20 | KingSlime@6: 700 / 100 / 30 / 64% | 30 | 14 | 20 (0) | 17 (0) | 177 | 0.35 | 48 | 110 | 16/25 (110) | NPC_Attack ×3, Tidal Surge ×11 |
| KingSlime_L6_j4_dodge | 20 | KingSlime@6: 700 / 100 / 30 / 64% | 50 | 10 | 32 (0) | 23 (0) | 212 | 0.30 | 12 | 110 | 7/22 (110) | Tidal Surge ×5, NPC_Attack ×5 |
| KingSlime_L6_j4_solo | 20 | KingSlime@6: 700 / 100 / 30 / 64% | 0 | 20 | 0 (0) | 0 (0) | 97 | 0.35 | 52 | 110 | 19/34 (110) | Tidal Surge ×17, NPC_Attack ×3 |
| KingSlime_L6_j5 | 20 | KingSlime@6: 700 / 100 / 30 / 63% | 55 | 9 | 39 (0) | 25 (0) | 177 | 0.40 | 61 | 114 | 13/20 (114) | Tidal Surge ×9 |
| KingSlime_L7_j4 | 20 | KingSlime@7: 760 / 110 / 33 / 64% | 35 | 13 | 23 (0) | 20 (0) | 169 | 0.25 | 49 | 110 | 12/18 (110) | NPC_Attack ×4, Tidal Surge ×9 |
| KingSlime_L7_j4_dodge | 20 | KingSlime@7: 760 / 110 / 33 / 64% | 35 | 13 | 21 (0) | 13 (0) | 251 | 0.50 | 14 | 110 | 7/24 (110) | NPC_Attack ×8, Tidal Surge ×5 |
| KingSlime_L7_j4_solo | 20 | KingSlime@7: 760 / 110 / 33 / 64% | 0 | 20 | 0 (0) | 0 (0) | 87 | 0.30 | 53 | 110 | 16/29 (110) | Tidal Surge ×15, NPC_Attack ×5 |
| KingSlime_L7_j5 | 20 | KingSlime@7: 760 / 110 / 33 / 63% | 40 | 12 | 21 (0) | 18 (0) | 193 | 0.15 | 61 | 114 | 9/15 (114) | NPC_Attack ×4, Tidal Surge ×8 |
| RockRumbler_L2_j4 | 20 | RockRumbler@2: 58 / 34 / 31 / 66% | 100 | 0 | 100 (95) | 100 (95) | 26 | 0.00 | 67 | 5 | — | — |
| RockRumbler_L2_j5 | 20 | RockRumbler@2: 58 / 34 / 31 / 65% | 100 | 0 | 100 (96) | 100 (96) | 25 | 0.00 | 70 | 4 | — | — |
| RockRumbler_L3_j4 | 20 | RockRumbler@3: 68 / 40 / 34 / 66% | 100 | 0 | 99 (91) | 99 (91) | 27 | 0.00 | 67 | 10 | — | — |
| RockRumbler_L3_j4_solo | 20 | RockRumbler@3: 68 / 40 / 34 / 66% | 100 | 0 | 93 (85) | 93 (85) | 38 | 0.00 | 57 | 15 | — | — |
| RockRumbler_L3_j5 | 20 | RockRumbler@3: 68 / 40 / 34 / 65% | 100 | 0 | 99 (92) | 99 (92) | 26 | 0.00 | 70 | 9 | — | — |
| RockRumbler_L4_j4 | 20 | RockRumbler@4: 78 / 46 / 37 / 66% | 100 | 0 | 99 (86) | 99 (86) | 31 | 0.00 | 65 | 15 | — | — |
| RockRumbler_L4_j5 | 20 | RockRumbler@4: 78 / 46 / 37 / 65% | 100 | 0 | 97 (88) | 97 (88) | 28 | 0.00 | 68 | 14 | — | — |
| ScarpAdder_L2_j4 | 20 | ScarpAdder@2: 44 / 26 / 6 / 76% | 100 | 0 | 100 (99) | 100 (99) | 24 | 0.00 | 74 | 1 | — | — |
| ScarpAdder_L2_j5 | 20 | ScarpAdder@2: 44 / 26 / 6 / 75% | 100 | 0 | 100 (100) | 100 (100) | 22 | 0.00 | 80 | 0 | — | — |
| ScarpAdder_L3_j4 | 20 | ScarpAdder@3: 52 / 30 / 7 / 76% | 100 | 0 | 100 (96) | 100 (96) | 29 | 0.00 | 65 | 4 | — | — |
| ScarpAdder_L3_j4_solo | 20 | ScarpAdder@3: 52 / 30 / 7 / 76% | 100 | 0 | 97 (54) | 97 (54) | 34 | 0.00 | 65 | 4 | — | — |
| ScarpAdder_L3_j5 | 20 | ScarpAdder@3: 52 / 30 / 7 / 75% | 100 | 0 | 100 (96) | 100 (96) | 26 | 0.00 | 80 | 4 | — | — |
| ScarpAdder_L4_j4 | 20 | ScarpAdder@4: 60 / 34 / 8 / 76% | 100 | 0 | 98 (87) | 98 (87) | 32 | 0.00 | 63 | 8 | — | — |
| ScarpAdder_L4_j5 | 20 | ScarpAdder@4: 60 / 34 / 8 / 75% | 100 | 0 | 99 (93) | 99 (93) | 31 | 0.00 | 70 | 8 | — | — |
| Slime_L1_j4 | 20 | Slime@1: 20 / 26 / 0 / 69% | 100 | 0 | 100 (100) | 100 (100) | 15 | 0.00 | 90 | 0 | — | — |
| Slime_L2_j4 | 20 | Slime@2: 26 / 29 / 0 / 69% | 100 | 0 | 100 (100) | 100 (100) | 15 | 0.00 | 90 | 0 | — | — |
| Slime_L2_j4_solo | 20 | Slime@2: 26 / 29 / 0 / 69% | 100 | 0 | 100 (98) | 100 (98) | 16 | 0.00 | 87 | 2 | — | — |
| Slime_L3_j4 | 20 | Slime@3: 32 / 32 / 0 / 69% | 100 | 0 | 100 (100) | 100 (100) | 15 | 0.00 | 90 | 0 | — | — |
| TalusHound_L2_j4 | 20 | TalusHound@2: 43 / 19 / 7 / 77% | 100 | 0 | 100 (100) | 100 (100) | 20 | 0.00 | 82 | 0 | — | — |
| TalusHound_L2_j5 | 20 | TalusHound@2: 43 / 19 / 7 / 76% | 100 | 0 | 100 (100) | 100 (100) | 19 | 0.00 | 82 | 0 | — | — |
| TalusHound_L3_j4 | 20 | TalusHound@3: 51 / 22 / 8 / 77% | 100 | 0 | 100 (100) | 100 (100) | 24 | 0.00 | 70 | 0 | — | — |
| TalusHound_L3_j4_solo | 20 | TalusHound@3: 51 / 22 / 8 / 77% | 100 | 0 | 100 (100) | 100 (100) | 44 | 0.00 | 57 | 0 | — | — |
| TalusHound_L3_j5 | 20 | TalusHound@3: 51 / 22 / 8 / 76% | 100 | 0 | 100 (100) | 100 (100) | 22 | 0.00 | 73 | 0 | — | — |
| TalusHound_L4_j4 | 20 | TalusHound@4: 59 / 25 / 9 / 77% | 100 | 0 | 100 (100) | 100 (100) | 24 | 0.00 | 70 | 0 | — | — |
| TalusHound_L4_j5 | 20 | TalusHound@4: 59 / 25 / 9 / 76% | 100 | 0 | 100 (100) | 100 (100) | 26 | 0.00 | 68 | 0 | — | — |
| pack_ed_2_4 | 20 | TalusHound@3: 51 / 22 / 8 / 77% | 100 | 0 | 99 (95) | 99 (95) | 64 | 0.00 | 55 | 5 | — | — |
| pack_ed_2_4_max | 20 | TalusHound@4: 59 / 25 / 9 / 77% | 100 | 0 | 98 (91) | 98 (91) | 64 | 0.00 | 55 | 10 | — | — |
| pack_ed_2_4_solo | 20 | TalusHound@3: 51 / 22 / 8 / 77% | 100 | 0 | 94 (80) | 94 (80) | 92 | 0.00 | 51 | 11 | — | — |
| pack_pools_2_3 | 20 | Slime@2: 26 / 29 / 0 / 69%; CaveBat@2: 19 / 28 / 0 / 78% | 100 | 0 | 91 (66) | 91 (66) | 96 | 0.00 | 54 | 22 | — | — |
| pack_pools_3_4 | 20 | ElderSlime@4: 112 / 46 / 18 / 66%; Slime@2: 26 / 29 / 0 / 69%; CorruptedStoneCreature@4: 96 / 34 / 27 / 65% | 95 | 1 | 85 (0) | 74 (0) | 146 | 0.25 | 47 | 96 | 5/8 (96) | NPC_Attack ×1 |
| pack_pools_3_4_max | 20 | ElderSlime@5: 126 / 52 / 20 / 66%; Slime@3: 32 / 32 / 0 / 69%; CorruptedStoneCreature@5: 108 / 38 / 30 / 65% | 100 | 0 | 76 (37) | 68 (12) | 167 | 0.25 | 47 | 78 | 6/8 (78) | — |
| pack_pools_4_2 | 20 | Slime@2: 26 / 29 / 0 / 69% | 100 | 0 | 94 (75) | 94 (75) | 69 | 0.00 | 54 | 17 | — | — |

40-run follow-up on the (3,4) pack, draft values, run to check the 20-run pack row above:

| Config | Deaths / n | Lowest HP%, mean (min) | Killing blows |
|---|---|---|---|
| R_pack_3_4_max_draft_all | **6 / 40** | 55 (0) | Slime Volley ×6 |
| R_pack_3_4_max_draft_all_dodge | 1 / 40 | 65 (0) | Slime Volley ×1 |
| Q_pack_3_4_base_draftElder (Slime/Stone also at proposed values) | 1 / 40 | 64 (0) | Slime Volley ×1 |

### What the baseline says

1. **Jean's armour swallows most of the trash growth.** `_npc_flat_damage` is `power − protection` with no resistance scaling, and Jean wears 23.3 protection (24.9 at L5).
   - A level-3 Slime (32 damage, rolled ×0.8–1.2) lands 2–15.
   - A TalusHound at any level on the table (19–25 damage) lands **0**.
   - Adding damage per level moves the threat only once it clears the armour. Adding HP per level only makes the fight longer.
2. **Gorran is most of the margin.** He has 242 HP and a 64-damage club, and he takes a large share of the aggro. The `_solo` rows are much harsher; King Slime at level 5 kills a solo Jean 19 times out of 20.
3. **King Slime scales past the surge cap.** `TidalSurge` deals 1.8 × damage × (0.8–1.2). #586 set that multiplier so a full-HP arena Jean survives the worst roll *of a 50-damage King Slime*. The level growth of +10 damage per level undoes that:

   | King Slime level | Damage | Surge max, raw | Surge max, landed | Jean max HP |
   |---|---|---|---|---|
   | 5 | 90 | 194 | ~170 | 110 |
   | 6 | 100 | 216 | ~190 | 110 |

   On the measured runs, **every surge that landed on Jean took all the HP he had left.**
4. **The (3,4) pack's danger is the ElderSlime's Slime Volley** (×2.2 at 46–52 damage, up to ~114 landed), stacked on top of chip damage from the Slimes and Stones. The max roll is where Jean dies.
5. **Dodging the tell helps but doesn't save him.** Dodge cut King Slime's landed surges from 64% to about 35% of those aimed at Jean. At level 6 that still left 10 deaths in 20. The dodge window has to line up with Jean's own recoil, so a tell he sees mid-swing can't always be answered.

## Proposed tuning (for maintainer approval — nothing applied)

These changes were verified in-process with `driver.py --profile` overrides, which replace `ENEMY_GROWTH_PROFILES` entries inside the scratch process only, and with pinned levels standing in for a `REGION_ENEMY_LEVELS` change. Results follow the table.

| # | Change in `src/npc_level_tables.py` | Reason |
|---|---|---|
| 1 | `"KingSlime": {"maxhp": 60, "damage": 10, "protection": 3}` → **`{"maxhp": 40, "damage": 2, "protection": 2}`** | Keeps the surge under the #586 cap: at level 5, damage is 58, so the surge max is 125 raw, ~100 landed, below Jean's 110–114 HP. The fight's pressure moves to length instead: 560 HP means more wind-ups per fight (11–21 aimed at Jean across 20 fights), and each one that lands takes 65–75% of Jean's HP, so the tell matters again. |
| 2 | `grondelith-mineral-pools` `"KingSlime": 6` → **`5`** | Pairs with #1. The level-6 variant (`{"maxhp": 50, …}`, P2) still killed Jean 4 times in 20 at L4 and once in 20 at L5 while dodging. At level 5 (P1) there were 0 deaths in 80 fights across Jean L4/L5, dodging or not. |
| 3 | `"ElderSlime": {"maxhp": 14, "damage": 6, …}` → **`{"maxhp": 14, "damage": 2, "protection": 2}`** | The volley is what kills Jean in the (3,4) pack. With damage 2 per level (34/36 damage at L4/L5, volley max ~70 landed), that pack went from 6/40 deaths at the max roll to **0/40**, and 0/40 at base. Jean's lowest HP still averages 65–74%, down to 10–15%, so the volley still hurts. |
| 4 | `"Slime": {"maxhp": 6, "damage": 3}` → **`{"maxhp": 6, "damage": 5}`**, and Pools `"Slime": 2` → **`3`** | Puts Slime damage above Jean's armour (36 at L3, 41 at L4) so packs are the pressure #617 wanted. (4,2) pack lowest HP: 94% on the draft → **86% (min 49%)** at base 3 → 80% (min 32%) at the max roll, 0 deaths. |
| 5 | `"CaveBat": {"maxhp": 4, "damage": 5}` unchanged; Pools `"CaveBat": 2` → **`3`** | Pairs with #4. (2,3) pack (3 Slime + 2 Bat) lowest HP: 91% → **83% (min 49%)** at base 3 → 75% (min 36%) at the max roll, 0 deaths. The 5-damage growth already sat right; the bat only needed the level. |
| 6 | `"CorruptedStoneCreature": {"maxhp": 12, "damage": 4, …}` → **`{"maxhp": 12, "damage": 6, "protection": 3}`** | At the draft values its biggest hit was 3–10, so it did nothing. This was measured only inside the (3,4) pack, together with #3/#4, and was not isolated. |
| 7 | `"TalusHound": {"maxhp": 8, "damage": 3, …}` → **`{"maxhp": 8, "damage": 7, "protection": 1}`** | At the draft values hounds **cannot damage Jean**. With 7 per level, a hound pair (their authored pack) at L4 with Jean L5 bottoms out at 93% mean / 66% min, and at L5 at 89% / 49%, with 0 deaths. |
| 8 | `"ScarpAdder": {"maxhp": 8, "damage": 4, …}` → **`{"maxhp": 8, "damage": 6, "protection": 1}`** | A small bump. With Gorran, adders remain mild (≥ 82% lowest HP at L5). They carry VenomClaw poison, which this driver did not measure. |
| 9 | `eastern-descent` default / RockRumbler / TalusHound / ScarpAdder `3` → **`4`** | Jean reaches the descent at L5 (see Assumptions), so the draft's "match the player's start level" rationale now points at 4–5, not 3. RockRumbler needs no profile change: at L4–5 it lands 14–27 per hit (lowest HP 97% / 94% mean). |
| 10 | `NPC_LEVEL_VARIANCE = 1`: **keep** | With #3 in place, the +1 roll is where the real pressure is, and it no longer kills Jean. Anything wider would bring the (3,4) max-roll death risk back. |

**Also recommended (not a table value):**
- Extend `tests/test_tidal_surge_balance.py` to build King Slime at `resolve_base_level("grondelith-mineral-pools", "KingSlime")` with its growth profile applied, rather than at level 1. That puts the level table under #586's survivability guard.
- Consider the same guard for Slime Volley at ElderSlime's base + variance.

**Where the proposals still miss the target:**
- Eastern Descent stays soft with Gorran (lowest HP ≥ 66%). That may be right for roadside trash; going harder needs more hounds per pack rather than more damage per hound.
- A solo Jean still dies to King Slime at level 5 (5/20 while dodging), but the beta route always has Gorran with him.
- Fatigue pressure only really appears in the boss and the (3,4) pack.

### Proposal verification runs

The `KS_P1` / `KS_P2` rows are proposals #1+#2 and the rejected P2 alternative. `P_`/`R_`/`S_` rows are #3–#6: the `P_` packs use the draft ElderSlime, the `S_` packs use proposal #3. `E_` rows are #7–#9 at Jean L5. All use `--heal`.

| Config | n | Enemy @ level: HP / dmg / prot / hit%→Jean | Win % | Deaths | Jean HP% at end, mean (min) | Lowest HP% in fight, mean (min) | Beats | Potions | Lowest fatigue % | Biggest hit | Surges at Jean: landed/aimed (biggest) | Killing blows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E_adder_L3_j5 | 20 | ScarpAdder@3: 52 / 34 / 7 / 75% | 100 | 0 | 99 (93) | 99 (93) | 26 | 0.00 | 80 | 8 | — | — |
| E_adder_L4_j5 | 20 | ScarpAdder@4: 60 / 40 / 8 / 75% | 100 | 0 | 98 (88) | 98 (88) | 31 | 0.00 | 70 | 14 | — | — |
| E_adder_L5_j5 | 20 | ScarpAdder@5: 68 / 46 / 9 / 75% | 100 | 0 | 96 (82) | 96 (82) | 31 | 0.00 | 70 | 20 | — | — |
| E_adder_L5_j5_solo | 20 | ScarpAdder@5: 68 / 46 / 9 / 75% | 100 | 0 | 90 (75) | 90 (75) | 35 | 0.00 | 63 | 19 | — | — |
| E_hounds2_L3_j5 | 20 | TalusHound@3: 51 / 30 / 8 / 76% | 100 | 0 | 96 (82) | 96 (82) | 50 | 0.00 | 62 | 19 | — | — |
| E_hounds2_L4_j5 | 20 | TalusHound@4: 59 / 37 / 9 / 76% | 100 | 0 | 93 (66) | 93 (66) | 53 | 0.00 | 62 | 30 | — | — |
| E_hounds2_L5_j5 | 20 | TalusHound@5: 67 / 44 / 10 / 76% | 100 | 0 | 89 (49) | 89 (49) | 57 | 0.00 | 62 | 40 | — | — |
| E_hounds2_L5_j5_solo | 20 | TalusHound@5: 67 / 44 / 10 / 76% | 100 | 0 | 63 (37) | 48 (19) | 97 | 0.40 | 62 | 46 | — | — |
| E_rumbler_L3_j5 | 20 | RockRumbler@3: 68 / 40 / 34 / 65% | 100 | 0 | 99 (92) | 99 (92) | 26 | 0.00 | 70 | 9 | — | — |
| E_rumbler_L4_j5 | 20 | RockRumbler@4: 78 / 46 / 37 / 65% | 100 | 0 | 97 (88) | 97 (88) | 28 | 0.00 | 68 | 14 | — | — |
| E_rumbler_L5_j5 | 20 | RockRumbler@5: 88 / 52 / 40 / 65% | 100 | 0 | 94 (76) | 94 (76) | 37 | 0.00 | 68 | 27 | — | — |
| E_rumbler_L5_j5_solo | 20 | RockRumbler@5: 88 / 52 / 40 / 65% | 100 | 0 | 84 (68) | 84 (68) | 49 | 0.00 | 63 | 26 | — | — |
| KS_P1_L5_j4 | 20 | KingSlime@5: 560 / 58 / 23 / 64% | 100 | 0 | 73 (38) | 52 (1) | 180 | 0.55 | 47 | 82 | 13/21 (82) | — |
| KS_P1_L5_j4_dodge | 20 | KingSlime@5: 560 / 58 / 23 / 64% | 100 | 0 | 72 (13) | 61 (6) | 193 | 0.35 | 15 | 75 | 8/18 (75) | — |
| KS_P1_L5_j5 | 20 | KingSlime@5: 560 / 58 / 23 / 63% | 100 | 0 | 81 (45) | 69 (12) | 160 | 0.25 | 61 | 74 | 8/11 (74) | — |
| KS_P1_L5_j5_dodge | 20 | KingSlime@5: 560 / 58 / 23 / 63% | 100 | 0 | 80 (52) | 73 (18) | 163 | 0.15 | 25 | 77 | 5/15 (77) | — |
| KS_P1_L5_j5_solo_dodge | 20 | KingSlime@5: 560 / 58 / 23 / 63% | 75 | 5 | 45 (0) | 16 (0) | 255 | 1.35 | 24 | 79 | 31/56 (79) | Tidal Surge ×5 |
| KS_P2_L6_j4 | 20 | KingSlime@6: 650 / 60 / 25 / 64% | 80 | 4 | 58 (0) | 40 (0) | 199 | 0.55 | 45 | 85 | 17/24 (85) | Tidal Surge ×4 |
| KS_P2_L6_j4_dodge | 20 | KingSlime@6: 650 / 60 / 25 / 64% | 100 | 0 | 67 (36) | 53 (3) | 242 | 0.40 | 9 | 79 | 8/19 (79) | — |
| KS_P2_L6_j5 | 20 | KingSlime@6: 650 / 60 / 25 / 63% | 100 | 0 | 77 (39) | 66 (8) | 193 | 0.40 | 61 | 78 | 10/16 (78) | — |
| KS_P2_L6_j5_dodge | 20 | KingSlime@6: 650 / 60 / 25 / 63% | 95 | 1 | 69 (0) | 60 (0) | 206 | 0.20 | 23 | 81 | 9/23 (81) | Tidal Surge ×1 |
| KS_P2_L6_j5_solo_dodge | 20 | KingSlime@6: 650 / 60 / 25 / 63% | 60 | 8 | 33 (0) | 13 (0) | 298 | 1.65 | 20 | 82 | 34/63 (82) | Tidal Surge ×7, NPC_Attack ×1 |
| P_pack_2_3_slime2_j4 | 20 | Slime@2: 26 / 31 / 0 / 69%; CaveBat@2: 19 / 28 / 0 / 78% | 100 | 0 | 90 (64) | 90 (64) | 96 | 0.00 | 54 | 22 | — | — |
| P_pack_2_3_slime3_j4 | 20 | Slime@3: 32 / 36 / 0 / 69%; CaveBat@3: 23 / 33 / 0 / 78% | 100 | 0 | 83 (49) | 83 (49) | 96 | 0.00 | 54 | 31 | — | — |
| P_pack_2_3_slime4_j4 | 20 | Slime@4: 38 / 41 / 0 / 69%; CaveBat@4: 27 / 38 / 0 / 78% | 100 | 0 | 75 (36) | 75 (36) | 97 | 0.00 | 53 | 39 | — | — |
| P_pack_3_4_base_j4 | 20 | ElderSlime@4: 112 / 46 / 18 / 66%; Slime@3: 32 / 36 / 0 / 69%; CorruptedStoneCreature@4: 96 / 40 / 27 / 65% | 95 | 1 | 79 (0) | 68 (0) | 150 | 0.25 | 47 | 96 | 6/10 (96) | Slime Volley ×1 |
| P_pack_3_4_max_j4 | 20 | ElderSlime@5: 126 / 52 / 20 / 66%; Slime@4: 38 / 41 / 0 / 69%; CorruptedStoneCreature@5: 108 / 46 / 30 / 65% | 95 | 1 | 69 (0) | 60 (0) | 163 | 0.25 | 47 | 78 | 6/9 (78) | Slime Volley ×1 |
| P_pack_3_4_max_j4_solo | 20 | ElderSlime@5: 126 / 52 / 20 / 66%; Slime@4: 38 / 41 / 0 / 69%; CorruptedStoneCreature@5: 108 / 46 / 30 / 65% | 5 | 19 | 2 (0) | 0 (0) | 51 | 0.55 | 54 | 110 | 21/26 (110) | NPC_Attack ×4, Slime Volley ×15 |
| P_pack_4_2_slime2_j4 | 20 | Slime@2: 26 / 31 / 0 / 69% | 100 | 0 | 93 (72) | 93 (72) | 69 | 0.00 | 54 | 19 | — | — |
| P_pack_4_2_slime3_j4 | 20 | Slime@3: 32 / 36 / 0 / 69% | 100 | 0 | 86 (49) | 86 (49) | 72 | 0.00 | 55 | 30 | — | — |
| P_pack_4_2_slime4_j4 | 20 | Slime@4: 38 / 41 / 0 / 69% | 100 | 0 | 82 (35) | 80 (32) | 73 | 0.05 | 54 | 38 | — | — |
| R_pack_3_4_base_proposal_dodge | 40 | ElderSlime@4: 112 / 46 / 18 / 66%; Slime@3: 32 / 36 / 0 / 69%; CorruptedStoneCreature@4: 96 / 40 / 27 / 65% | 100 | 0 | 82 (13) | 73 (13) | 164 | 0.20 | 19 | 77 | 5/15 (77) | — |
| R_pack_3_4_max_draft_all | 40 | ElderSlime@5: 126 / 52 / 20 / 66%; Slime@4: 38 / 35 / 0 / 69%; CorruptedStoneCreature@5: 108 / 38 / 30 / 65% | 85 | 6 | 62 (0) | 55 (0) | 161 | 0.25 | 47 | 110 | 21/27 (110) | Slime Volley ×6 |
| R_pack_3_4_max_draft_all_dodge | 40 | ElderSlime@5: 126 / 52 / 20 / 66%; Slime@4: 38 / 35 / 0 / 69%; CorruptedStoneCreature@5: 108 / 38 / 30 / 65% | 98 | 1 | 76 (0) | 65 (0) | 193 | 0.33 | 16 | 91 | 13/33 (91) | Slime Volley ×1 |
| R_pack_3_4_max_proposal_dodge | 40 | ElderSlime@5: 126 / 52 / 20 / 66%; Slime@4: 38 / 41 / 0 / 69%; CorruptedStoneCreature@5: 108 / 46 / 30 / 65% | 98 | 1 | 73 (0) | 59 (0) | 199 | 0.33 | 15 | 91 | 9/32 (91) | Slime Volley ×1 |
| S_elder_L5_elder2_solo | 40 | ElderSlime@5: 126 / 36 / 20 / 66% | 98 | 1 | 72 (0) | 67 (0) | 65 | 0.12 | 54 | 54 | 35/49 (54) | Slime Volley ×1 |
| S_pack_3_4_base_elder2 | 40 | ElderSlime@4: 112 / 34 / 18 / 66%; Slime@3: 32 / 36 / 0 / 69%; CorruptedStoneCreature@4: 96 / 40 / 27 / 65% | 100 | 0 | 83 (41) | 74 (12) | 150 | 0.17 | 46 | 73 | 12/18 (73) | — |
| S_pack_3_4_max_elder2 | 40 | ElderSlime@5: 126 / 36 / 20 / 66%; Slime@4: 38 / 41 / 0 / 69%; CorruptedStoneCreature@5: 108 / 46 / 30 / 65% | 100 | 0 | 76 (39) | 65 (15) | 168 | 0.25 | 47 | 78 | 17/22 (78) | — |
| S_pack_3_4_max_elder2_dodge | 40 | ElderSlime@5: 126 / 36 / 20 / 66%; Slime@4: 38 / 41 / 0 / 69%; CorruptedStoneCreature@5: 108 / 46 / 30 / 65% | 100 | 0 | 80 (37) | 69 (10) | 190 | 0.25 | 14 | 55 | 9/23 (55) | — |

ElderSlime growth check (40 runs each, with Slime/Stone at the proposed values). `elder4` = damage 4 per level, and it was **not** enough:

| Config | n | Enemy @ level: HP / dmg / prot / hit%→Jean | Win % | Deaths | Jean HP% at end, mean (min) | Lowest HP% in fight, mean (min) | Beats | Potions | Lowest fatigue % | Biggest hit | Surges at Jean: landed/aimed (biggest) | Killing blows |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Q_elder_L5_draft_solo | 40 | ElderSlime@5: 126 / 52 / 20 / 66% | 98 | 1 | 69 (0) | 51 (0) | 67 | 0.47 | 55 | 87 | 31/46 (87) | Slime Volley ×1 |
| Q_elder_L5_elder4_solo | 40 | ElderSlime@5: 126 / 44 / 20 / 66% | 90 | 4 | 60 (0) | 56 (0) | 63 | 0.15 | 54 | 70 | 36/50 (70) | Slime Volley ×4 |
| Q_pack_3_4_base_draftElder | 40 | ElderSlime@4: 112 / 46 / 18 / 66%; Slime@3: 32 / 36 / 0 / 69%; CorruptedStoneCreature@4: 96 / 40 / 27 / 65% | 98 | 1 | 77 (0) | 64 (0) | 153 | 0.25 | 46 | 107 | 14/20 (107) | Slime Volley ×1 |
| Q_pack_3_4_base_elder4 | 40 | ElderSlime@4: 112 / 40 / 18 / 66%; Slime@3: 32 / 36 / 0 / 69%; CorruptedStoneCreature@4: 96 / 40 / 27 / 65% | 100 | 0 | 81 (37) | 72 (16) | 150 | 0.17 | 47 | 90 | 11/15 (90) | — |
| Q_pack_3_4_max_draftElder | 40 | ElderSlime@5: 126 / 52 / 20 / 66%; Slime@4: 38 / 41 / 0 / 69%; CorruptedStoneCreature@5: 108 / 46 / 30 / 65% | 88 | 5 | 61 (0) | 52 (0) | 160 | 0.30 | 46 | 110 | 20/24 (110) | Slime Volley ×5 |
| Q_pack_3_4_max_elder4 | 40 | ElderSlime@5: 126 / 44 / 20 / 66%; Slime@4: 38 / 41 / 0 / 69%; CorruptedStoneCreature@5: 108 / 46 / 30 / 65% | 88 | 5 | 64 (0) | 52 (0) | 167 | 0.35 | 45 | 101 | 24/30 (101) | Slime Volley ×5 |

## What didn't work / tooling gaps found

1. **`POST /api/debug/arena/stats {"level": N}` does nothing on arena enemies.**
   - `TheAdjutant.add_combatant` builds `cls()`, which leaves `growth_profile = None`.
   - `set_combatant_stats` then routes `level` through `sync_level`, which returns early without a profile.
   - The op reports `{"updated": {"level": 1}}` with `success: true`. Checked on King Slime: before and after the call it had 400 HP, 50 damage and 15 protection at level 1.
   - #655 step 1 as written ("dial its level in the arena via the debug op") therefore cannot work today. This baseline sets the profile in-process instead.
   - The fix belongs in the engine: `add_combatant` or `set_combatant_stats` should attach `ENEMY_GROWTH_PROFILES[cls]` the way `apply_enemy_level` does.
2. **`ADD_COMBATANT_ALLOWED_CLASSES` lacks TalusHound, ScarpAdder and CorruptedStoneCreature**, so three of the eight tuned enemies can't be staged through the debug API at all. The driver appends them to the tile in-process.
3. **`tools/bug_hunt.py --scenario combat` doesn't fit balance work.** It caps at 20 rounds, picks the first offensive move with no healing or fatigue handling, and reports bugs rather than outcomes. A scratch driver (`scratch_balance/driver.py`, uncommitted) reuses its `GameClient` and its routes instead. If this loop is going to be repeated for #655 step 3, it would be worth promoting that driver into `tools/`.
4. **Seeding doesn't give exact reproducibility.** See Method: two identical-looking configurations gave 0/20 and 6/40 deaths. Use n ≥ 40 for any configuration near the death threshold.
5. **Limits of the model:**
   - Enemies spawned mid-fight by pulsing glands are not included.
   - Every fight starts at full HP and fatigue, with 3 fresh Restoratives.
   - Poison and Slimed ticks are counted only when they lower HP between Jean's turns.
   - Rung 4 (a live browser run through `/orchestrate-qa-testers`) is still needed to confirm the pacing people actually feel.
