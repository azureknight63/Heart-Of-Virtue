# Rumbler Loot Bug — Reproduction & Testing Guide

**Issue**: Any loot equipment item dropped from defeating a Rumbler causes errors on all interactions (equip, take)
- Error 1: `'dict' object has no attribute 'maintype'`
- Error 2: `list.remove(x): x not in list`

## Quick Start

### 1. Using the Automated Test Script

The fastest way to reproduce and test:

```bash
# Single test run
python tools/test_rumbler_loot.py

# Run 10 times (to catch intermittent bugs)
python tools/test_rumbler_loot.py --repeat 10 --verbose
```

**What it does**:
1. Spawns a RockRumbler on a dedicated test map
2. Defeats it (forces equipment drop)
3. Attempts to equip/take the loot
4. Reports success or error

### 2. Manual Reproduction (Terminal Game)

Start the game at the Rumbler test arena:

```bash
CONFIG_FILE=config_rumbler_loot_test.ini python src/game.py
```

**Steps**:
1. You'll spawn in the "Rumbler Arena"
2. Engage and defeat the RockRumbler
3. Attempt to pick up the dropped item (`take`)
4. Attempt to equip it (`equip` or just interact with it)

**What to watch for**:
- Does the item appear on the ground after the Rumbler dies?
- Can you `take` it into inventory?
- Can you `equip` it?
- If errors occur, what is the exact error message?

### 3. API-Based Testing

To test through the REST API (closest to how the web frontend operates):

```bash
# In one terminal: start the Flask API
python tools/run_api.py

# In another terminal: run the test
python tools/test_rumbler_loot.py --repeat 5 --verbose
```

The test script will use the GameService to call `interact_with_target()`, which mimics the actual frontend flow.

## Test Configuration

### config_rumbler_loot_test.ini
- **Purpose**: Pre-configured game state optimized for loot testing
- **Differences from default**:
  - Starts on `rumbler-loot-test` map
  - Player has 500 HP (survives easily)
  - No starting equipment (clean slate for testing pickup)
  - High attributes (reliable damage to Rumbler)
  - All skills learned (can equip any item)
  - Test mode enabled (skip dialogs, disable animations)

### rumbler-loot-test.json Map
- **Description**: Minimal arena with single RockRumbler
- **Layout**: Single tile `(0, 0)` with one NPC
- **Purpose**: No distractions, focused on loot drop and interaction

## Debugging Output

### When the test script runs, you'll see:
```
======================================================================
RUMBLER LOOT BUG REPRODUCTION TEST
======================================================================
Running 5 test iteration(s)...

Run 1: [PASS] - 1 item(s) tested
Run 2: [PASS] - 1 item(s) tested
Run 3: [PASS] - 1 item(s) tested
Run 4: [FAIL] - Equip failed for Silver Bracelet: 'dict' object has no attribute 'maintype'
Run 5: [PASS] - 1 item(s) tested

======================================================================
TEST SUMMARY
======================================================================
Total runs:   5
Passed:       4
Failed:       1

Errors encountered:
  - 'dict' object has no attribute 'maintype': 1

✗ Bug reproduced in 1 run(s)!
```

### Additional Logging

**Terminal game**:
```bash
# Check the game log (if debug mode is enabled)
cat game.log
```

**API tests**:
```bash
# Check Flask error log
cat flask_error.log

# Or run with verbose logging
FLASK_ENV=development python tools/run_api.py
```

## What to Report

If you reproduce the bug, please capture:

1. **Exact error message** — Copy the full traceback
2. **Item that caused it** — What item name was dropped? (e.g., "Crossbow of Insight")
3. **Action sequence** — Exactly what did you do?
   - Defeated Rumbler via combat or direct call to `roll_loot()`?
   - Did you try `take` first or `equip` first?
   - Did you have other items in inventory?
4. **Number of runs** — Did it happen on first try or after multiple attempts?
5. **Test method** — Terminal game, test script, or API?

## Investigation Notes

### Known Facts
- ✓ Equipment items with enchantments are created correctly
- ✓ Items have proper attributes: `maintype`, `isequipped`, `interactions`
- ✓ Simple loot drop + interact succeeds in controlled test
- ✗ Bug may only occur during actual combat or specific state combinations

### Likely Root Causes
1. **Actual Combat Flow** — Bug might only happen via `ApiCombatAdapter.execute()` → `enemy.die()`
2. **State Persistence** — Save/load cycle corruption
3. **Race Condition** — Concurrent item operations
4. **Specific Item/Enchantment** — Certain configurations break interaction

### Code Locations to Monitor
- `src/api/combat_adapter.py:1299` — `enemy.die()` during victory
- `src/npc.py:128` — `NPC.die()` calls `before_death()` → `roll_loot()`
- `src/loot_tables.py:38` — `random_equipment()` returns from `spawn_item()`
- `src/items.py:272` — `take()` method removes from room
- `src/player/_inventory.py:192` — `equip_item()` accesses `maintype`

## Advanced Testing

### Force Specific Equipment
Edit `tools/test_rumbler_loot.py` line ~120:

```python
rumbler.loot = {
    "Equipment_0_1": {"chance": 100, "qty": 1},  # Change Equipment tier here
}
```

Equipment tiers:
- `Equipment_0_0` — Level 0, no enchantments
- `Equipment_0_1` — Level 0, 1 enchantment
- `Equipment_1_0` — Level 1, no enchantments
- `Equipment_1_1` — Level 1, 1 enchantment

### Stress Testing
Run many iterations to find race conditions:

```bash
python tools/test_rumbler_loot.py --repeat 100 --verbose
```

### Manual API Testing
Using curl:

```bash
# Start API server
python tools/run_api.py

# Create session (or use existing)
curl -X POST http://localhost:5000/api/auth/session

# Get current room (should show dropped items)
curl http://localhost:5000/api/world/room \
  -H "Authorization: Bearer <session_id>"

# Try to equip item (use id from room response)
curl -X POST http://localhost:5000/api/world/interact \
  -H "Authorization: Bearer <session_id>" \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": "<item_id_from_room>",
    "action": "equip"
  }'
```

---

**Last Updated**: 2026-04-03  
**Created for**: Rumbler Loot Equipment Bug Investigation
