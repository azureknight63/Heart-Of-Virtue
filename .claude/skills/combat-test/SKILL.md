---
name: combat-test
version: 1.0.0
description: |
  Agent-focused combat testing skill. Reads config_combat_testing.ini to set up a
  scenario in the dedicated combat testing arena, then invokes /qa to drive the
  full Flask + React stack through that scenario and return the raw combat log
  and state for agent exploration.
  Use when asked to "test combat", "run a combat scenario", "set up a combat test",
  or "check combat for X".
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Skill
---

# /combat-test: Combat Testing Skill

You are a combat QA specialist for Heart of Virtue. Your job is to set up the
combat testing arena, drive a scenario through the game stack, and surface the
raw results for further investigation or assertion.

**This skill is agent-focused.** Output raw state and logs — do not summarise
or soft-land issues. Surface everything so the calling agent can decide what to
assert.

---

## Step 0: Parse Arguments

The user may invoke with inline overrides:

```
/combat-test
/combat-test scenario=boss
/combat-test scenario=status_dummy hp=50 strength=20
/combat-test scenario=custom custom_enemies=Lurker,GiantSpider max_rounds=10
/combat-test god_mode=True scenario=ally
```

Recognised override keys (all map directly to `config_combat_testing.ini` keys):

| Key | Section | Description |
|-----|---------|-------------|
| `scenario` | `[scenario]` | `fodder` / `boss` / `ally` / `status_dummy` / `custom` |
| `hp` | `[player]` | Starting HP |
| `maxhp` | `[player]` | Max HP |
| `strength` | `[player]` | Attribute |
| `finesse` | `[player]` | Attribute |
| `speed` | `[player]` | Attribute |
| `endurance` | `[player]` | Attribute |
| `charisma` | `[player]` | Attribute |
| `intelligence` | `[player]` | Attribute |
| `faith` | `[player]` | Attribute |
| `level` | `[player]` | Starting level |
| `exp` | `[player]` | Starting EXP |
| `heat` | `[player]` | Starting heat (0.5–10.0) |
| `learn_all_skills` | `[game]` | `True` / `False` |
| `max_rounds` | `[scenario]` | Max rounds before timeout |
| `custom_enemies` | `[scenario]` | Comma-separated NPC class names |
| `god_mode` | `[development]` | `True` / `False` |
| `skip_combat` | `[development]` | `True` / `False` |
| `active_events` | `[combat_events]` | Comma-separated event class names |

Collect overrides. Do **not** apply them yet.

---

## Step 1: Read Current Configuration

Read `config_combat_testing.ini` from the project root.

Print the current effective configuration in a compact table:

```
=== COMBAT TEST CONFIG ===
Scenario:        fodder
Player HP:       100 / 100
Level:           1   EXP: 0
STR:10 FIN:10 SPD:10 END:10 CHA:10 INT:10 FAI:10
Heat:            1.0
Learn all skills: True
Max rounds:      50
God mode:        False
Active events:   (none)
==========================
```

If the user provided overrides, show what will change:

```
OVERRIDES to apply:
  scenario=boss        (was: fodder)
  hp=50                (was: 100)
```

Ask for confirmation only if the override changes `god_mode`, `skip_combat`, or
`active_events` — those carry behaviour risk. For stat and scenario changes,
proceed without asking.

---

## Step 2: Apply Overrides

For each override, locate the correct section and key in
`config_combat_testing.ini` and apply the edit using the Edit tool.

Preserve all comments. Change only the values on the relevant lines.

Example: if `scenario=boss` is passed, edit this line in `[scenario]`:
```
active_scenario = fodder
```
→
```
active_scenario = boss
```

After edits, re-read the file and confirm the effective values match expectations.

---

## Step 3: Identify the Target Arena Tile

Map `active_scenario` to the arena tile and the enemies expected:

| Scenario | Tile | Enemies | Purpose |
|----------|------|---------|---------|
| `fodder` | `(1, 0)` Fodder Pit | Slime, CaveBat | Basic move/damage testing |
| `boss` | `(2, 0)` The Crucible | KingSlime, Lurker | High HP, complex moves, boss pressure |
| `ally` | `(0, 1)` Ally Courtyard | Gorran (ally) + Slime (enemy) | Ally AI, co-op mechanics |
| `status_dummy` | `(1, 1)` Status Chamber | Pell (all resistances 0) | Status effect verification |
| `custom` | `(1, 0)` Fodder Pit | `custom_enemies` value | Custom roster |

Note the tile and enemies. You will reference these when interpreting the QA output.

**If `active_scenario = custom`:** The map JSON hardcodes Slime + CaveBat at tile (1, 0).
Before invoking `/qa`, talk to The Adjutant and use **option [8] Manage arena combatants**:
1. Clear tile (1, 0) — option [3]
2. Add each class from `custom_enemies` — option [1], entering the class name from `npc.py`

Changes take effect immediately. Then proceed to Step 4.

---

## Step 4: Invoke /qa

Before calling `/qa`, ensure the server will boot with the combat testing config.
If the server is not already running, set the env var so it loads the right ini:

```bash
export CONFIG_FILE=config_combat_testing.ini
```

This makes the game respect `startmap = combat-testing-arena`, `startposition = 0, 0`,
and `testmode = True` from the ini. Without it, the game starts on the default map and
the arena is unreachable (it has no link to the main game world).

If the server is already running on a different config, restart it with the env var set
before invoking `/qa`.

Call the `/qa` skill, scoped to the combat arena:

```
/qa target=http://localhost:3000 scope=combat focus="combat-testing-arena scenario={active_scenario}"
```

If the Flask and Vite servers are not already running, `/qa` will start them
automatically (it uses the inquisitor harness) — the `CONFIG_FILE` env var will be
inherited by the child process.

Pass the following context to `/qa` in the prompt:
- The map is `combat-testing-arena` starting at `(0, 0)` (the Proving Grounds)
- The scenario tile is `{tile}` — navigate there to trigger combat
- Enemies expected: `{enemies}`
- Max rounds: `{max_rounds}`
- God mode: `{god_mode}`
- Check: combat start, move execution, status effects if `status_dummy`, ally
  targeting if `ally`, post-combat EXP distribution, and reset (return to
  Proving Grounds after combat ends)

Let `/qa` run to completion. Do not interrupt it.

---

## Step 5: Surface Raw Results

After `/qa` completes, collect and display:

### 5a. Combat Log

Extract the full combat log from `/api/combat/log` (or from `/qa`'s network
capture). Display every entry verbatim:

```
COMBAT LOG (raw):
  [beat 1]  Jean prepares to strike.
  [beat 2]  Slime burbles angrily.
  [beat 3]  Jean strikes! 14 damage. Slime HP: -4 (dead).
  ...
```

### 5b. Combatant State Snapshot

Display the final state of all combatants:

```
COMBATANT STATES (end of combat):
  Jean Claire    HP: 87/100  Fatigue: 110/150  Heat: 1.2  Active states: []
  Slime          HP: 0/10    Status: DEFEATED
  Cave Bat       HP: 0/8     Status: DEFEATED
```

### 5c. EXP & Level-Up Events

```
EXP DISTRIBUTION:
  Basic:    12 EXP
  Unarmed:  0
  Level-up: No
```

### 5d. Flagged Issues

List everything `/qa` flagged — do not filter, do not triage. Include:
- HTTP 5xx responses
- Missing fields in combat API responses
- JS console errors
- Network failures (excluding known noise: fonts.googleapis.com, fonts.gstatic.com, React Router warnings)
- Any unexpected combat_active state changes

Format as a numbered list with endpoint, status, and description.

### 5e. Status Effect Verification (status_dummy scenario only)

For each move Jean used that applies a status effect, report:
- Effect name
- Was it applied? (yes/no)
- Beats it remained active
- Any unexpected interaction

```
STATUS EFFECTS (Pell):
  Poison (from VenomClaw):  APPLIED — 5 beats
  Stun   (from HolyStrike): NOT APPLIED — investigate
```

---

## Step 6: Agent Handoff

End with a structured handoff block for the calling agent:

```
=== COMBAT TEST COMPLETE ===
Scenario:      fodder
Outcome:       VICTORY / DEFEAT / TIMEOUT
Rounds:        3
Bugs flagged:  0
Jean survived: Yes (87 HP remaining)
EXP awarded:   12 (Basic)
Suggested next steps:
  - Try scenario=boss to verify survivability under high damage
  - Test scenario=status_dummy with VenomClaw to verify poison landing
  - Adjust player stats via The Adjutant (talk to NPC at (0,0)) if needed
============================
```

If there were bugs, list them again here with severity (CRITICAL / HIGH / MEDIUM / LOW).

---

## Important Rules

1. **Never filter or suppress raw output.** The calling agent decides what matters.
2. **Do not fix bugs found during this run** unless the user explicitly asks. Surface and hand off.
3. **Restore the ini after the run** if overrides were applied — revert to the pre-run values so the file reflects the intended baseline. Skip restoration if the user says `--keep-overrides`.
4. **Known noise**: ignore `fonts.googleapis.com`, `fonts.gstatic.com`, and React Router future-flag warnings — these are filtered automatically by the harness.
5. **If /qa cannot start the servers**, fall back to the in-process harness: run `python tools/bug_hunt.py --scenario combat --headless --output /tmp/combat_test_results.json` and parse that output instead.
6. **The map is agent-only** — it has no link to the main game world. Do not attempt to navigate there from dark-grotto or any other production map.
7. **The Adjutant** is at `(0, 0)`. Use the `talk` command on that tile to:
   - Set Jean's stats, level, heat, and skills at runtime via menu option [1]–[7]
   - Manage arena combatants via menu option [8]:
     - **Add** any NPC class from `npc.py` to any arena tile by class name
     - **Remove** individual combatants by index
     - **Clear** an entire arena tile's NPC roster
     - **Edit** any combatant's stats (hp, damage, aggro, friend, speed, etc.) in place
   Changes take effect immediately — no restart required.

---

## Preamble (run first)

Print current branch. If not on a combat-related or feature branch, warn but proceed.

Print the current `active_scenario` from the ini so the agent knows what will run.
