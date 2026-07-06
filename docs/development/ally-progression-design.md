# Ally NPC Progression — Design Document

**Status:** Implemented (signature moves pending collaborative design)
**Branch:** `claude/ally-npc-progression-eooks1`

> Implementation notes (deltas from the original proposal below):
> - **No UI surface.** Per user decision, ally growth is surfaced through the
>   LLM ally chat instead of exp bars/level badges: progressing allies get a
>   `COMBAT SELF-KNOWLEDGE` block in their chat system prompt
>   (`HumanNPCLLMMixin._build_combat_knowledge_block`) so the player can ask
>   them about their techniques in character. Combat-log lines
>   ("Gorran reached level 5!", "Gorran has learned X!") still appear.
> - **KO policy confirmed:** KO'd allies keep their full exp share.
> - `NPCCombatMixin.refresh_moves()` now syncs targeted moves to the NPC's
>   current target before viability filtering — fixes a latent bug where
>   target-dependent moves (Bull Charge, Flanking Maneuver) were never viable
>   at selection time and went stale between fights.
> - Session setup ordering fix: `_apply_player_stats_from_config` now runs
>   *before* `_apply_starting_party_members` so allies level-sync against
>   Jean's configured level (found by the harness scenario).
> - Signature moves implemented (src/moves/_npc.py, states in src/states.py):
>   - **Gorran L9 — Seismic Slam**: telegraphed radial ground slam (prep 4 /
>     recoil 6), ~0.7× damage (crushing) to every enemy within 6 ft, 25%
>     Stagger chance per target rolled through `inflict()` (respects stun
>     resistance, same profile as the Heavy Handed passive).
>   - **Gorran L12 — Stone Bulwark**: self-cast (`targeted=False`, honoring
>     the refresh_moves single-target contract) party ward — every ally gains
>     `StoneBulwarkState` (+6 + 50% of Gorran's protection, 20 beats); won't
>     recast while any ward is up; 25-beat cooldown.
>   - **Mara L9 — Marked Quarry**: applies `Quarried` to one enemy (−25%
>     protection, 15 beats) with `force=True` — a perception mark, not a
>     resistible status. The whole party benefits via the stat machinery
>     (chosen over the original party-accuracy sketch, which would have
>     required touching the to-hit path of every attack move).
>   - **Mara L12 — Twin Fangs**: fast close-range finisher (range 0–3,
>     prep 1), 1.2× damage, ×1.5 more against a Quarried target — her kit
>     is a deliberate hunt: mark, then execute.
>   - Verified live in the arena: Gorran L12's AI selected and resolved
>     Seismic Slam mid-fight through the full stage pipeline; a Crucible
>     boss fight ran 47–87 rounds with the new moves in the pool, no errors.
> - Test surface: `tests/test_ally_progression.py` (unit),
>   `tests/acceptance/ally-progression/` (config + run.sh), and the
>   `ally_progression` bug-hunt scenario (debug endpoints
>   `GET /api/debug/allies`, `POST /api/debug/allies/progression`).

## Goals

- Ally NPCs (party members in `player.combat_list_allies`) gain experience from
  battles they participate in and grow stronger over time.
- The **player never controls** ally growth: no attribute-point allocation, no
  skill menu. Stat gains and skill acquisitions are statically determined per
  ally class.
- Allies grow at **roughly the same rate as Jean** — never dead weight, never
  outshining him.
- Growth is visible: level-ups and learned skills are narrated in combat results.

## Non-goals

- No ally equipment/inventory management (allies keep using the flat `damage`
  stat, not weapons).
- No respec, no player-facing ally skill tree UI.
- Enemy NPCs do not level (only `Friend` subclasses that opt in).

---

## 1. Current state of the engine (facts this design builds on)

| Concern | Where it lives today |
|---|---|
| Party membership | `player.combat_list_allies` (index 0 is the player himself). Story code appends/removes Friend instances (`ch01.py:733`, `ch02.py:646`). Allies follow Jean via `Player.recall_friends()` (`src/player/_movement.py:111`). |
| Ally combat AI | `NPCCombatMixin.select_move()` (`src/npc/_combat.py`) — weighted random pick from `known_moves`; weights set at construction via `add_move(move, weight)`. Mara overrides `select_move()` entirely. |
| Ally damage | Flat `self.damage` stat (`NpcAttack`: `user.damage * uniform(0.8, 1.2)`), **not** derived from strength or weapons. `protection` subtracts from incoming damage. |
| NPC stats | Flat attributes with `_base` twins: `maxhp`, `damage`, `protection`, `speed`, `finesse`, `endurance`, `strength`, `charisma`, `intelligence`, `faith`, `maxfatigue`, `awareness` (`src/npc/_base.py`). `functions.refresh_stat_bonuses()` recomputes live values from `_base` + states. |
| Player exp | Moves bank `player.combat_exp[subtype]` during combat. On victory, `ApiCombatAdapter._handle_victory()` (`src/api/combat_adapter.py:1781`) calls `player.gain_exp(pool, exp_type=subtype)` per subtype; each call adds the amount to `player.exp`. |
| Player leveling | `exp_to_level = level * max(1, 165 - intelligence)` (`src/player/_leveling.py:73`). Per level: +0–2 random to each of 7 base stats (~7 avg) plus 6–9 allocatable points (~7.5 avg). |
| Player skills | Bought manually from `skill_exp` pools via the skill menu (`game_service.learn_skill`). Allies get nothing analogous. |
| Persistence | Whole-player pickle (`game_service.save_game`); allies ride along inside `combat_list_allies` and `npcs_here`. Legacy-save resilience via `getattr` defaults and `_patch_player_integrity`-style patches (`src/functions.py:657`). |
| KO state | `Friend.knocked_out` exists (`src/npc/_base.py:186`) but is barely used. |

**Key insight:** `_handle_victory()` is the single choke point where combat exp
becomes level exp. Ally progression hooks there and nowhere else (same
discipline as the cooldown-drain rule in CLAUDE.md: progression only advances
on real combat victories).

---

## 2. Design overview

Three pieces, all on the `Friend` class (new mixin `src/npc/_progression.py`):

1. **Exp track** — `level`, `exp`, `exp_to_level` on every progressing ally.
   On victory, each ally in the party receives the **same total exp Jean banked
   to his level track that fight**. Same income + same curve ⇒ same pace.
2. **Static growth profile** — a per-class table of deterministic per-level
   stat increments. No randomness, no allocation.
3. **Skill schedule** — a per-class table of `level → moves/weight changes`.
   Applied automatically on level-up via the existing `add_move()` mechanism.

Progression is **opt-in**: a `Friend` subclass with no `growth_profile` never
levels (this keeps TheAdjutant, Grondite citizens, merchants, and other
flavor-Friends inert without any flags).

---

## 3. Data model

```python
class Friend(NPC):
    # class-level declarations, overridden per companion
    growth_profile: dict | None = None   # {"maxhp": 14.0, "damage": 3.0, ...} per-level rates
    skill_schedule: dict | None = None   # {level: [SkillGrant(...), ...]}

    def __init__(self, ...):
        ...
        self.level = 1
        self.exp = 0
        self.knocked_out = False
```

`exp_to_level` is a computed property reusing the **player's exact formula**
with the ally's own (static) intelligence:

```python
@property
def exp_to_level(self):
    return self.level * max(1, 165 - self.intelligence)
```

One curve definition in the codebase's terms; at intelligence 10 (all current
companions) this is `155 × level`, identical to Jean at parity.

### SkillGrant

A schedule entry is one of:

- `("NewMove", MoveClass, weight)` — instantiate `MoveClass(self)` and
  `add_move(move, weight)`; narrate *"Gorran has learned Boulder Heave!"*
- `("WeightUp", "MoveName", new_weight)` — find the move in `known_moves` by
  name and raise its weight (the ally "favors" a technique more as they grow).
  Silent (no narration) — it's a tuning knob, not a story beat.

Represent as a tiny frozen dataclass or plain tuples; tuples are fine given the
codebase's style.

---

## 4. Exp flow and pacing math

### Award point

In `ApiCombatAdapter._handle_victory()`, immediately after the player exp loop:

```python
total_gained = sum(exp_gained.values())
ally_progression = []
for ally in self.player.combat_list_allies[1:]:
    if getattr(ally, "growth_profile", None):
        events = ally.gain_exp(total_gained, player_level=self.player.level)
        ally_progression.extend(events)
self.player.combat_end_summary["ally_progression"] = ally_progression
```

### Why "Jean's total" and not a share of `exp_award`

`exp_gained` (what Jean banks toward his level) is exactly the sum of the
per-subtype `combat_exp` pools — the fight's true difficulty/length signal.
Enemy `exp_award` is a separate legacy stat that is `0` on many NPCs and
unused by the victory path. Mirroring Jean's income guarantees "same rate"
**by construction** with zero new tuning surface.

### Pacing analysis

- Same income, same curve, same starting level ⇒ allies level in lockstep at
  intelligence parity.
- Divergence source: Jean's `exp_to_level` shrinks as his intelligence grows;
  allies' intelligence is static. Jean will slowly out-pace allies at high
  intelligence builds. This is bounded by two mechanisms below and is
  acceptable ("roughly the same rate").

### Level band: clamp + catch-up

- **Hard cap:** an ally never levels past `player.level`. `gain_exp` loops
  `while self.exp >= self.exp_to_level and self.level < player_level`. Banked
  exp is retained, so a capped ally pops its pending level the first victory
  after Jean levels.
- **Catch-up:** if `ally.level < player.level - 1` (joined late, or lagged from
  Jean's intelligence growth), exp gains are multiplied ×1.5 until the ally is
  within 1 level. Keeps the party in a `[player-1, player]` band without ever
  feeling scripted.
- **Join-level sync:** when a story event adds an ally to the party for the
  first time, it should call `ally.sync_level(player.level)` — deterministic
  level-ups applied silently up to Jean's level. Late-game companions arrive
  battle-ready; the catch-up multiplier alone would take too long.

### Ally `gain_exp` (mirrors `PlayerLevelingMixin.gain_exp`, minus menus)

```python
def gain_exp(self, amt, player_level):
    """Deterministic ally exp gain. Returns a list of level-up event dicts."""
    if self.level >= min(player_level, 100):
        # still bank exp so a pending level resolves after Jean levels
        self.exp += amt
        return []
    if self.level < player_level - 1:
        amt = int(amt * 1.5)          # catch-up band
    self.exp += amt
    events = []
    while self.exp >= self.exp_to_level and self.level < min(player_level, 100):
        events.append(self._level_up())
    return events
```

### KO policy

KO'd/dead-at-victory allies still receive the full award. Rationale: docking
exp for KOs makes a struggling ally *weaker* relative to the party (snowball),
and the band clamp makes over-reward impossible anyway. Tunable later if it
feels wrong.

---

## 5. Static stat growth

### Mechanism: recompute-from-spawn, never accumulate

On first level-up, snapshot spawn bases; every level recomputes absolutely so
fractional rates never drift and the math is save/load-proof:

```python
def _apply_growth(self):
    if not hasattr(self, "_spawn_bases"):
        self._spawn_bases = {
            stat: getattr(self, f"{stat}_base") for stat in self.growth_profile
        }
    for stat, rate in self.growth_profile.items():
        new_base = self._spawn_bases[stat] + int(rate * (self.level - 1))
        old_base = getattr(self, f"{stat}_base")
        setattr(self, f"{stat}_base", new_base)
        setattr(self, stat, getattr(self, stat) + (new_base - old_base))
    functions.refresh_stat_bonuses(self)
```

- Fractional rates (e.g. `"protection": 0.5`) give a point every other level
  via the `int()` floor — designer-legible without float stats.
- `maxhp` growth also raises current `hp` by the delta (leveling never leaves
  an ally proportionally more wounded); no full heal, matching Jean.

### Anchoring the numbers to Jean's growth

Jean gains ~14.5 attribute points per level (7 random + 7.5 allocated) on a
~70-point starting pool — roughly **+2% effective power per level**, amplified
by weapon upgrades. Allies have no equipment ladder, so their per-level rates
should carry the whole curve: **~6–8% of spawn stats per level** keeps an ally
at a stable fraction of Jean's power through the campaign. Playtest via the
combat-testing arena and adjust per class.

### Proposed profiles for current companions

**Gorran** (tank/bruiser — spawn: 200 hp, 55 dmg, 0 prot, 5 spd, 10 fin, 100 fat):

```python
growth_profile = {
    "maxhp": 14,        # 7% of spawn
    "damage": 3,        # 5.5%
    "protection": 0.5,  # +1 every 2 levels
    "speed": 0.25,      # slow forever, but not static
    "finesse": 0.5,
    "maxfatigue": 5,
}
```

**Mara** (skirmisher — spawn: 95 hp, 38 dmg, 12 prot, 8 spd, 8 fin):

```python
growth_profile = {
    "maxhp": 6,
    "damage": 2.5,
    "protection": 0.5,
    "speed": 0.75,
    "finesse": 1,
    "maxfatigue": 6,
}
```

At level 10: Gorran ≈ 326 hp / 82 dmg / +4 prot; Mara ≈ 149 hp / 60 dmg —
both roughly ×1.6 spawn power, tracking Jean's unmodified stat growth.

---

## 6. Skill schedules

Applied inside `_level_up()` after stat growth:

```python
def _apply_skill_schedule(self):
    for grant in (self.skill_schedule or {}).get(self.level, []):
        kind = grant[0]
        if kind == "NewMove":
            _, move_cls, weight = grant
            if not any(m.name == move_cls(self).name for m in self.known_moves):
                self.add_move(move_cls(self), weight)
                cprint(f"{self.name} has learned {self.known_moves[-1].name}!", "magenta")
        elif kind == "WeightUp":
            _, move_name, new_weight = grant
            for m in self.known_moves:
                if m.name == move_name:
                    m.weight = new_weight
```

### Example schedules (mechanism-proof; final content TBD)

```python
# Gorran — deepens what he already does
skill_schedule = {
    3: [("WeightUp", "Parry", 3)],
    5: [("NewMove", moves.GorranSlam, 3)],       # NEW move: AoE ground slam, long recoil
    8: [("WeightUp", "Gorran Club", 4)],
    12: [("NewMove", moves.StoneBulwark, 2)],    # NEW move: brief party protection buff
}

# Mara — sharpens precision and mobility
skill_schedule = {
    3: [("WeightUp", "Dodge", 4)],
    5: [("NewMove", moves.AimedShot, 2)],        # existing move, works for NPCs w/ combat_range
    9: [("NewMove", moves.FeintAndPivot, 2)],
}
```

Reuse existing move classes where they already support NPC users; net-new
moves (`GorranSlam`, `StoneBulwark`) are ordinary content additions in
`src/moves/_npc.py`. **Compatibility note:** Mara's custom `select_move()`
reads `known_moves`, so scheduled grants flow into her AI automatically.

---

## 7. Surfacing progression (API + frontend)

- `combat_end_summary` gains an `ally_progression` key:
  `[{"name": "Gorran", "old_level": 4, "new_level": 5, "skills_learned": ["Gorran Slam"]}]`.
  The frontend combat-summary modal renders these under the player's level-up
  block.
- `CombatantSerializer.serialize_combatant()` adds `"level"` for allies
  (`getattr(combatant, "level", None)`) so the battlefield/party UI can show it.
- Level-up and skill-learn narration goes through `cprint(..., "magenta")` —
  the same channel as Jean's — so the combat log picks it up with zero extra
  plumbing.
- No new routes needed. If a party panel later wants exp bars, add a
  `GameService.get_party_status(player)` method (per the "routes don't reach
  into player internals" rule).

---

## 8. Persistence & backward compatibility

- Saves are whole-player pickles: `level`, `exp`, `_spawn_bases`, and granted
  moves persist automatically on the ally instances.
- **Old saves** lack the new attributes. Guard every read with `getattr`
  defaults (`getattr(ally, "level", 1)`) and add the fields to an
  ally-integrity pass alongside `_patch_player_integrity` in
  `src/functions.py` (iterate `combat_list_allies[1:]`, backfill
  `level=1, exp=0`).
- Story code that removes/re-adds the **same instance** (Gorran in ch01/ch02)
  keeps progression for free. Any event that spawns a *fresh* instance of a
  returning companion must copy or re-sync level — prefer `sync_level(player.level)`
  at join time, which also covers this case.

---

## 9. Edge cases

| Case | Handling |
|---|---|
| Ally at cap when Jean levels mid-fight | Banked exp resolves at next victory's `gain_exp` call. Acceptable one-fight latency. |
| Multiple level-ups from one big fight | `while` loop in `gain_exp`, same as Jean. |
| Level 100 | Same terminal cap as the player (`min(player_level, 100)`). |
| TheAdjutant / merchants / citizens | No `growth_profile` ⇒ opted out automatically. |
| Testing | Add a `set_ally_level` operation to the Adjutant debug endpoint (`/api/debug`) mirroring `set_level`; Ally Courtyard `(0,1)` in the arena is the venue. |
| Non-combat exp (`gain_exp` from events/quests to Jean) | Not mirrored — ally progression is combat-only by design ("gain exp in battle"). Story rewards that should touch allies can call `ally.gain_exp` explicitly. |

---

## 10. Implementation checklist

1. `src/npc/_progression.py` — `AllyProgressionMixin` (`gain_exp`,
   `_level_up`, `_apply_growth`, `_apply_skill_schedule`, `sync_level`,
   `exp_to_level` property). Mix into `Friend` in `_base.py`; init
   `level`/`exp` in `Friend.__init__`.
2. `growth_profile` + `skill_schedule` on `Gorran` and `Mara`
   (`src/npc/_friends.py`); new NPC moves in `src/moves/_npc.py` as needed.
3. Hook in `ApiCombatAdapter._handle_victory()` + `ally_progression` in
   `combat_end_summary`.
4. `sync_level` calls at party-join points (`story/ch01.py` Gorran joins).
5. Serializer: `level` on ally combatants; frontend combat-summary rendering.
6. Adjutant debug op `set_ally_level`; legacy-save integrity backfill.
7. Tests: unit (curve parity with player formula, clamp, catch-up multiplier,
   deterministic growth recompute, schedule idempotence on re-grant, pickle
   round-trip); harness scenario in the arena (ally levels after N fodder
   fights, learns scheduled move, never exceeds Jean's level).

## Open questions (need a call before/while implementing)

1. **KO exp policy** — full share recommended (above); alternative is half.
2. **Growth magnitudes** — the 6–8%/level anchor is a starting point; final
   numbers come from arena playtests (`/combat-test scenario=ally`).
3. **Skill schedule content** — which new NPC moves are worth authoring for
   Gorran/Mara at which levels (narrative call as much as mechanical).
4. **Should allies show exp bars in the UI**, or is level + "learned X"
   narration enough? (Recommend the latter to start.)
