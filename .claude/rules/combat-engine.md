---
paths:
  - "src/moves/**"
  - "src/combatant.py"
  - "src/states.py"
  - "src/positions.py"
  - "src/npc_ai_config.py"
  - "src/combat_event_config.py"
  - "src/npc/**"
  - "src/api/combat_adapter.py"
---

# Combat engine rules

This is the hot path — weigh Optimization hardest here, and keep every number explainable (pillar 3: tactical, legible combat).

## Moves package (`src/moves/`)
`__init__.py` re-exports every class, so callers keep `import src.moves`-style access unchanged. Put a new move in the submodule that owns its weapon/role: `_base.py` (`Move`, `PassiveMove`, `_ensure_weapon_exp`, `default_animations`, to-hit), `_utility.py` (StrategicInsight, Check, Wait, Rest, UseItem, Attack), `_movement.py` (Dodge, Parry, Advance, Withdraw, BullCharge, TacticalRetreat, …), `_unarmed.py`, `_dagger.py`, `_sword.py`, `_scythe.py`, `_spear.py`, `_pick.py`, `_ranged.py`, `_polearm.py`, `_mastery.py` (the 7 `Mastery` moves — the category below), `_npc.py` (NpcAttack, NpcRest, TelegraphedSurge, SlimeVolley, TidalSurge, …). That is all 13 submodules; if a new move fits none of them, add a submodule rather than a home-of-convenience.

- **Passive moves** (flag-only, never castable, `viable()→False`) inherit `PassiveMove`, not `Move`; subclasses supply only `name` and `description`. `PassiveMove` exists to kill ~200 lines of repeated boilerplate — don't reintroduce it.
- **`web_animation`**: every castable move declares one. Valid values are the keys of `ANIMATION_CONFIGS` in `frontend/src/utils/animationConfigs.js` (attack, quick_attack, heavy_attack, pierce, sweep, charge, projectile, shockwave, dash, defend, buff, debuff, drain, heal, pulse, death); `tests/test_move_web_animations.py` enforces it. Adding a type? Define its config (phases/motion/effect/sfx) in the frontend first. Unknown types fall back to `pulse` client-side; a missing declaration falls back to attack/pulse in the adapter.
- **Categories**: a castable move's category must map to a button group in `frontend/src/utils/categories.js` (`CATEGORY_GROUPS`); `tests/test_move_categories_ui_contract.py` AST-parses `src/moves/` and fails otherwise — that gap is how 8 castable moves (7 `Mastery` + `ReapersMark`) became unreachable.
- **Selections are attributes, not prompts**: the adapter sets `duration` / `distance` / `target_direction` / `target` on the move before its stage runs; read the attribute with a sensible default. `ShootBow` defaults to the preferred/first arrow; in-combat item use is the `/inventory/use` route. `src/` is free of `input()` — keep it that way.
- Cooldowns drain only during active combat beats (root CLAUDE.md, "Cooldown timing trap").

## To-hit arithmetic (`src/moves/_base.py`) — read before touching
`to_hit_chance(user, target, base=, floor=)` is the real roll; `attacker_accuracy(finesse, intelligence, base=)` is the display-only rating the character sheet renders. The expression used to be inlined at ~20 call sites *and* re-implemented in `game_service` — the exact reimplementation the architecture rules forbid. Two traps:
1. **The call sites are not uniform.** Bases of 85/90/95/98/105 and floors of 1/5/none are all in use, and which move takes which is not guessable from its weapon class. Do not trust any enumeration of them — the docstring's list was wrong twice (it named `Riposte` as an 85 site when it takes the default 98, which would have cost 13 points of accuracy; after that fix it still omitted `PowerStrike`) and was deleted. The truth is `grep -rn "to_hit_chance" src/moves/`.
2. **Term order is load-bearing.** `base - target.finesse` is evaluated before the weighted attacker terms are added; folding the attacker terms first shifts the truncated result by one point for ~0.7% of integer stat pairs. `to_hit_chance` must never be "simplified" into `attacker_accuracy(...) - target.finesse`.

Situational modifiers (ranged accuracy decay, Hawkeye, Aimed Shot's flat bonus, the crossbow close-range halving) stay at the call sites because several interpose before `_apply_to_hit_modifiers` and the clamps.

## Combatant / states
- `Combatant` (`src/combatant.py`) owns resistance and status-effect logic shared by `Player` and `NPC`. Never duplicate it in a subclass.
- `states.py` (buffs/debuffs) is a known low-coverage area — new states need tests for apply/tick/expire and for the wire name the frontend reads (`beats_left`, not `duration_remaining`).
- Boss-tier enemies (`KingSlime`, `Lurker`) set `is_boss = True` and take the lower boss status-resistance baseline; `StatusDummy` ("Pell") zeroes every status resistance and sets damage resistance 1.0 so effects land reliably in tests.
- Positional mechanics (distance, facing, flanking, tactical retreat) are gated by `config_*.ini` flags (`enable_flanking_mechanics`, `enable_tactical_positioning`, `npc_flanking_enabled`, `npc_tactical_retreat`, `ai_difficulty`, `show_*`) — `src/config_manager.py` has the full list; don't hardcode what a flag already controls.
- `Check`'s coordinate display must tolerate allies whose proximity data hasn't synced with newly chained enemies (`.get(enemy, 0)`), and `combat_id` must survive wave/reinforcement reinits (`.claude/rules/api-layer.md`).

## NPC AI and chat (`src/npc/`)
- NPCs are a package inheriting `Combatant`; AI decisions honour `npc_ai_config.py` and the config flags above.
- NPC chat / LLM code (`src/npc/_chat_llm.py`, `_llm.py`, `ai/llm_client.py`) must degrade gracefully: provider errors, 429s, truncation, and QC rejections fall back to canned dialogue — never surface a stack trace to the player. Mynx ambient behaviour is off unless `MYNX_LLM_ENABLED=1`.

## Testing combat
`/combat-test` + `config_combat_testing.ini` (arena table in root CLAUDE.md); `python tools/bug_hunt.py --scenario combat` / `combat_edge`; `python tools/combat_command_fuzzer.py`. `combat.log` at the repo root is a scratch artifact, not a fixture. Seed or patch `random` in any test that asserts on a roll.
