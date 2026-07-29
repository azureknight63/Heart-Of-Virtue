# Open Issues Requiring Human Input

Triage of the 90 open issues on `azureknight63/Heart-Of-Virtue`. The issues below were
**deliberately not auto-fixed** — each needs a design, balance, scope, or creative decision
that an agent shouldn't invent. Everything else was dispatched to fix agents.

Grouped by the kind of decision needed.

---

## A. Game-balance decisions (numbers you have to choose)

### #391 — Ordinary NPCs are immune to every status effect
`Combatant._init_resistances()` seeds **every** status resistance at `1.0`, and
`inflict()` computes `chance * (1 - resistance)` — so `1.0` = guaranteed immunity.
`Player.__init__` explicitly zeroes seven types; `NPC.__init__` never does. Result:
**no status effect has ever landed on an ordinary enemy.** Reproduced live in the issue.

This is the single highest-impact open bug, but the fix is a balance question, not a
code question: what should the NPC baseline be? Options:
- `0.0` across the board (fully susceptible) with per-class overrides for real immunities
- a mid baseline (e.g. `0.3–0.5`) so status effects are useful but not dominant
- per-status baselines (e.g. poison easy to land, stun hard)

Whatever you pick, every existing per-enemy override (incl. #389's stone creature) needs
re-checking against the corrected convention, and encounter difficulty shifts noticeably.
**Decision needed: the baseline number(s).**

### #423 — Enchantment rarity system is a no-op
All 32 enchantment subclasses hardcode `rarity=0`, and the gate is
`random.randint(0,100) >= ench.rarity` — always true. The mechanic exists but has never
differentiated anything. Either assign real per-class rarity values (**a 32-entry balance
table only you can write**) or delete the field if tiers alone should gate rarity now.

### #454 (part 2) — `calculate_retreat_priority` baseline
The comment claims priority ≈ 0.3 at the retreat threshold; the formula gives 0.0.
An agent is fixing the comment to match the formula. If the *comment* was the intent,
the formula needs a nonzero baseline — **that's a balance call.**

---

## B. Content / design decisions (what should exist)

### #337 — Halberd is mechanically a Spear
Description says "an axe mounted on a large pole" (slashing) but it's built with
`subtype="Spear"` → **piercing** damage, and the file's own taxonomy has a dead
`"Halberd"` slashing subtype nothing uses. Two clean resolutions, opposite outcomes:
1. Make it a real slashing Halberd (wires up whatever move/mastery interactions that implies), or
2. Rewrite the description to match its spear mechanics and delete the dead taxonomy entry.

### #340 — Status-cure consumables are unobtainable
`SlimeFlask`, `MineralSolvent`, `Respite`, `Relic` are fully working cures for states that
live combat moves genuinely inflict — but **none is placed in any map, shop, loot table, or
event.** Players get Petrified/Slimed with no cure available. Needs you to decide *where*
they go (which Grondelith shops, which enemy loot tables) or to confirm they're cut content.

### #342 — `DragonHeartGem` / `CrystalTear` resistance bonuses are inert
Special-class relics set `add_resistance`, but `refresh_stat_bonuses` only reads
`isequipped=True` items and Special items have **no equip path at all**. Three ways out,
each a different system: give Special relics a passive-while-carried aggregation path,
make them equippable accessories, or strip the advertised bonus. **Which system do you want?**

### #343 — FlareArrow's fire effect isn't implemented
Constructed with `effects=None` plus a `# todo add fire effect on impact`. The delivery
mechanism works (`_ranged.py` consumes `effects`), so this is purely "which burn state,
how much damage, how many turns" — a design/balance call.

### #350 — `WailStrike` references a `WailWraith` NPC that doesn't exist
Dead move, no NPC uses it. Implement the WailWraith enemy or delete the move.
**Content decision.**

### #367 + #384 — Gorran's staged dialogue and flavor system are unreachable
`gorran_language_stage` is written exactly twice in the codebase, both setting it to `"1"`.
Nothing ever advances it, so Gorran's stage 2–4 dialogue and the *entire* `gorran_flavor.py`
ambient system (hundreds of lines of authored content, never called by any loop) are dead.
Needs narrative design: **what beats in ch02/ch03 advance the stage**, and where the flavor
hooks fire (combat beat loop, `move_player`). Alternatively, annotate as staged-for-future.

### #418 — Arrow recovery + Hawkeye
Arrows that *hit* are tracked as `arrow_location="target"` but nothing ever recovers them
(the miss path works). And ShootBow checks for a "Hawkeye" state nothing in the game grants.
Both are half-features: recover-from-corpse vs. drop the tracking; wire Hawkeye into the
skilltree vs. delete the check.

### #427 — `CombatEventConfig`: 4 of 6 fields silently ignored
`ally_list`, `grid_size_override`, `scenario_type`, `on_victory_text` have no consumer —
and `testing-map.json` **already authors** `scenario_type`/`grid_size_override` values that
do nothing. Wire them into `CombatEvent` (each implies real design: what *is* a
`scenario_type`?) or delete them so authoring fails loudly.

### #453 — `locked_dialogue` is a phantom mechanic
Computed and serialized claiming "dialogue locked at negative reputation," but nothing
reads or enforces it. Implement the gate or remove the field. **Do you want reputation to
lock dialogue?**

### #445 — Whole tileset modules are dead
`grondia.py` (12 classes), `verdette_caverns.py` (6), plus several others never match any
shipped map's `title` field, so every one of those tiles instantiates as generic `MapTile`
and their custom behavior never runs. Per-module decision: **align the map JSON titles to
the class names, or delete the modules.** (A companion fix for #444 is landing now to make
this failure log loudly instead of silently — run a map load afterward and the mismatches
will list themselves.)

---

## C. Engine-architecture decisions (risky, want your sign-off)

### #417 — WarCry's headline "interrupt" mechanic is inert
Sets `move.interrupted = True`; **nothing anywhere reads that flag.** The in-progress move
continues through its beats unaffected. This is a 2500-skill-point purchase. Implementing
interrupts means touching the beat loop (cancel the move, reset `current_stage`, clear
`current_move`, decide beat refund/penalty) — a real combat-engine feature. Alternative:
delete the flag and rewrite the move description around its stun.

### #421 — HauntingPresence only protects against 3 of the game's attack moves
Enforced solely in `standard_execute_attack`, which only `PommelStrike`, `Thrust`, and
`OverheadSmash` call. Every other attack ignores it. The right fix — move the check into
the shared `hit()`/to-hit path — is blocked on the duplicated damage pipelines, i.e. it
really wants **#464** landed first.

### #464 — Extract shared combat-damage pipeline helpers
Filed by the code-scrubber and explicitly deferred: the duplication is real, but it touches
the most-used combat path and `src/moves/_base.py`. Wants its own reviewed chunk with focused
tests. **I'd recommend doing this one next, with you watching — it unblocks #421.**

### #394 (part) — `get_accuracy_modifier` is implemented, tested, and never called
The facing/angle system wires only `get_damage_modifier` into moves; the accuracy half is
inert despite docstrings claiming attack angle affects accuracy. Wiring it in changes
hit rates across the board. (The unambiguous half — deleting dead `distance_squared` — is
already dispatched.) **Decision: wire it in, or delete it?**

### #435 — OpenAPI schema is comprehensively out of sync
Every documented path 404s (missing `/api` prefix), `/auth/login` bears no resemblance to
reality, and the shared `Player` schema documents a **mana system that doesn't exist**.
Approach decision: hand-correct it, or generate it programmatically from the registered
blueprints so it can't drift again? The second is more work now and permanent after.

### #437 — Most registered API error handlers are unreachable
Routes build JSON errors inline; the 400/401/403/422/429/503 handlers never fire, and the
real 401 body doesn't match what the handler would produce. **Pick a convention** — route
everything through `abort()`/handlers, or delete the handlers and keep the inline style.
Either is fine; the mixture isn't.

### #433 — Large dead-serializer surface
`MoveSerializer`, the whole `npc_ai.py` module (~395 lines, 3 classes), and a dozen unused
`serialize_*` methods across NPC/event/item/object serializers — all written against a data
model the engine doesn't have, none wired to a route. Deleting is straightforward but it's
~600+ lines and inflates the coverage numbers you're tracking. **Confirm you want it gone**
(vs. rewritten against real attributes and wired up).

### #450 — Large config surface parsed but never consumed
Three findings: most of `GameConfig` (display/logging/debug groups, `starting_story_flags`,
autosave/quicksave flags, `skip_combat`, …), the **entire** `ScenarioConfig` file, and most
of `CoordinateSystemConfig`. Content/config authors currently get silent no-ops. Wire vs.
prune is a per-group product decision — some of these (`autosave_enabled`, `skip_combat`)
sound like things you actually want working.

### #328 — Object-removal tile persistence *(dispatched, may bounce back)*
Read path uses `id(obj)` (unsound across sessions), write path is a `pass` stub. I gave an
agent a shot at implementing stable identifiers, with instructions to skip rather than
half-land it. **If it comes back skipped, it's yours** — the alternative is deleting the
dead read branch until the feature is real.

---

## D. Map Editor

### #463 — Save authored placeholders instead of full runtime instances
**The issue itself mandates human approval**: the agent must surface a per-class audit report
(proposed authored params, omitted runtime fields, nested handling, migration risks, classes
that can't be represented) for your sign-off *before* finalizing metadata across the codebase.
It's also large: versioned schema, class metadata across `src/npc`/`items`/`objects`/`events`,
a **Convert Elements** UX, and legacy-format compatibility. Worth doing — but as its own
session where you're reviewing the audit.

*(#462, the Friend-NPC chooser bug, had clear acceptance criteria and was dispatched.)*

---

## E. Creative / asset work (not code)

- **#457** — Character portraits for Kaelen & Vespera: 8 emotion variants each, transparent PNG. Art commission.
- **#458** — Iron & Oath tradepost BGM. The issue has a strong brief (anvil-strike rhythm accents, string/woodwind duet, river-breeze layer, bittersweet minor turns). Could be attempted with `/music-designer` or `/sound-designer` — **want me to?**
- **#466** — Jambo shop BGM. **Issue body is empty** — needs a brief before anything can happen.
- **#459** — Pack animal for Kaelen & Vespera. The issue explicitly says "Human Design Required": species, name, disposition, interaction flavor. Once you decide those three things, the NPC class + map placement is a 20-minute job.

---

## F. Deferred by design

### #460 — Combat speed slider
Marked **"deferred — do not implement yet"** and blocked on #436 (engine-driven combat
streaming) providing the beat queue, duration manifest, and SFX chain. Left alone
deliberately. Ready when #436's Phase 2 timing seam lands.

### #326 — Nomad Camp polish
Mostly done — 8 of 10 checkboxes complete. Two remain:
- *"It's unclear what the player should do when entering the camp"* — **needs your direction**
  on what the entrance event should actually tell the player.
- *"Books: the READ interaction outputs to the Interaction panel but should open the Read
  panel like inventory does"* — this one is a well-specified frontend fix; **say the word and
  I'll dispatch it.**
