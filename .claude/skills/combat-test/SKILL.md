---
name: combat-test
version: 1.1.0
description: |
  Agent-focused combat testing skill. Reads config_combat_testing.ini to set up a
  scenario in the dedicated combat testing arena, then runs the scenario via the
  bug_hunt harness (primary) or /qa browser stack (escalation for UI bugs) and
  returns raw combat logs and state for assertion.
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
combat testing arena, drive a scenario, and surface the raw results for further
investigation or assertion.

**This skill is agent-focused.** Output raw state and logs — do not summarise
or soft-land issues. Surface everything so the calling agent can decide what to
assert.

**Testing tier:**
- **Primary** — `python tools/bug_hunt.py` (fast, in-process, no browser). Use
  this for all logic/mechanics verification: damage, status effects, EXP, cooldowns.
- **Escalation** — `/qa` browser stack. Use only when the bug is clearly UI-layer
  (React rendering, network failures, JS errors). Do not escalate by default.

---

## Preamble (run immediately)

Print the current branch:
```bash
git branch --show-current
```
If not on a combat-related or feature branch, warn the user but proceed.

Print the `active_scenario` from `config_combat_testing.ini` so the agent knows
what will run before any changes are applied.

---

## Step 1: Read Config and Apply Overrides

The user may invoke with inline overrides:

```
/combat-test
/combat-test scenario=boss
/combat-test scenario=status_dummy hp=50 strength=20
/combat-test scenario=custom custom_enemies=Lurker,GiantSpider max_rounds=10
/combat-test god_mode=True scenario=ally
```

Recognised override keys (all map directly to `config_combat_testing.ini`):

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

**Do this in one pass:**

1. Read `config_combat_testing.ini`.
2. Print the current effective configuration:

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

3. If the user provided overrides, show the diff:

```
OVERRIDES to apply:
  scenario=boss        (was: fodder)
  hp=50                (was: 100)
```

4. **Record the original values** for every key you are about to change — you
   will need them to restore the ini in Step 4.

5. Ask for confirmation **only** if the override changes `god_mode`,
   `skip_combat`, or `active_events`. For stat and scenario changes, proceed
   without asking.

6. Apply each override: locate the correct section and key, edit with the Edit
   tool. Preserve all comments. Change only the relevant values.

7. Re-read the file and confirm effective values match expectations.

---

## Step 2: Identify the Target Arena Tile

Map `active_scenario` to the arena tile and the enemies expected:

| Scenario | Tile | Enemies | Purpose |
|----------|------|---------|---------|
| `fodder` | `(1, 0)` Fodder Pit | Slime, CaveBat | Basic move/damage testing |
| `boss` | `(2, 0)` The Crucible | KingSlime, Lurker | High HP, complex moves, boss pressure |
| `ally` | `(0, 1)` Ally Courtyard | Gorran (ally) + Slime (enemy) | Ally AI, co-op mechanics |
| `status_dummy` | `(1, 1)` Status Chamber | Pell (all resistances 0) | Status effect verification |
| `custom` | `(1, 0)` Fodder Pit | `custom_enemies` value | Custom roster |

**If `active_scenario = custom`:** Edit the map JSON directly
(`src/resources/maps/combat-testing-arena.json`, tile `(1, 0)`, `"npcs"` array)
to replace the roster with the class names from `custom_enemies`. This is faster
and more reliable than driving The Adjutant's runtime menu via the browser. Restart
the server after the edit if it is already running.

Note the tile and enemies — reference them when interpreting results.

---

## Step 3: Run the Scenario

### Primary path — bug_hunt harness

Set the environment variable and run the harness:

```bash
CONFIG_FILE=config_combat_testing.ini python tools/bug_hunt.py --headless --output /tmp/combat_results.json
```

This is faster, needs no browser, and produces structured JSON output. Use this
for all logic/mechanics verification.

If the harness has no dedicated combat scenario, run the general harness and
filter results by combat-related endpoints (`/api/combat/*`).

### Escalation path — full browser /qa

Use this **only** if the bug is clearly UI-layer (React rendering, JS console
errors, network failures visible only in the browser). Before calling `/qa`,
ensure the server boots with the combat testing config:

```bash
export CONFIG_FILE=config_combat_testing.ini
```

Then call:
```
/qa target=http://localhost:3000 scope=combat focus="combat-testing-arena scenario={active_scenario}"
```

Pass this context to `/qa`:
- Map is `combat-testing-arena` starting at `(0, 0)` (the Proving Grounds)
- Scenario tile is `{tile}` — navigate there to trigger combat
- Enemies expected: `{enemies}`
- Max rounds: `{max_rounds}`, God mode: `{god_mode}`
- Check: combat start, move execution, status effects (if `status_dummy`), ally
  targeting (if `ally`), post-combat EXP distribution, reset to Proving Grounds

Let `/qa` run to completion. Do not interrupt it.

---

## Step 4: Restore the Ini

Revert every key you changed in Step 1 back to the original values you recorded.
Use the Edit tool, one key at a time. Re-read the file to confirm restoration.

Skip restoration if the user passed `--keep-overrides`.

---

## Step 5: Surface Raw Results

Read `/tmp/combat_results.json` (harness path) or collect from `/qa`'s output
(browser path). Display everything verbatim.

### 5a. Combat Log

```
COMBAT LOG (raw):
  [beat 1]  Jean prepares to strike.
  [beat 2]  Slime burbles angrily.
  [beat 3]  Jean strikes! 14 damage. Slime HP: -4 (dead).
  ...
```

### 5b. Combatant State Snapshot

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

List everything the harness or `/qa` flagged — do not filter, do not triage:
- HTTP 5xx responses
- Missing fields in combat API responses
- JS console errors (browser path only)
- Network failures (excluding known noise: fonts.googleapis.com, fonts.gstatic.com, React Router warnings)
- Unexpected `combat_active` state changes

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

End with a structured handoff block:

```
=== COMBAT TEST COMPLETE ===
Scenario:      fodder
Runner:        bug_hunt harness / /qa browser
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
3. **Restore the ini after the run** — you recorded the original values in Step 1 before applying overrides. Revert them in Step 4. Skip only if `--keep-overrides` was passed.
4. **Known noise**: ignore `fonts.googleapis.com`, `fonts.gstatic.com`, and React Router future-flag warnings — filtered automatically.
5. **Prefer the harness over the browser stack** for combat logic. Only escalate to `/qa` when the issue is clearly UI-layer.
6. **The map is agent-only** — it has no link to the main game world. Do not attempt to navigate there from dark-grotto or any other production map.
7. **The Adjutant** is at `(0, 0)`. Use the `talk` command on that tile (in a running game session) to:
   - Set Jean's stats, level, heat, and skills at runtime via menu options [1]–[7]
   - Manage arena combatants via menu option [8]: add/remove/clear/edit by NPC class name
   Changes take effect immediately — no restart required.
   For automated runs, prefer editing the map JSON or ini directly instead of driving the menu.
