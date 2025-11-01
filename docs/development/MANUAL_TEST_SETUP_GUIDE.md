# Manual Combat Testing Setup Guide

## Quick Start (5 minutes)

### Step 1: Verify Test Environment
```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Verify all tests pass
pytest tests/ -q
# Expected: 746 passed, 4 skipped
```

### Step 2: Choose Your Test Mode

#### Option A: Automated Tests (Fastest)
```bash
# Run all 9 automated tests (~30 seconds)
python tests/phase4_test_executor.py

# Expected output:
# RESULTS: 9/9 PASSED
# Results saved to: tests/PHASE4_TEST_RESULTS.json
```

#### Option B: Manual Combat Testing (Most Realistic)
```bash
# Start the game
python src/game.py

# Then follow test procedures below
```

---

## Detailed Setup for Manual Combat Testing

### Prerequisites
- Python 3.13+
- All dependencies installed (see requirements.txt)
- Virtual environment activated
- 746 tests passing (verified above)

### Test Configuration

#### 1. Enable All Flags (Full Testing)
Edit `config_dev.ini` or create test config with:
```ini
[DEBUG]
debug_mode=True
debug_positions=True
debug_ai_decisions=True
debug_movement=True
debug_damage_calc=True
debug_accuracy=True

[LOGGING]
log_combat_moves=True
log_distance_calculations=True
log_angle_calculations=True
log_npc_decisions=True

[DISPLAY]
show_combat_distance=True
show_unit_positions=True
show_combat_rounds=True
show_combat_animations=True
show_damage_numbers=True

[COORDINATE_SYSTEM]
coordinate_grid_size=(50, 50)
```

#### 2. Minimal Testing (Performance)
```ini
[DEBUG]
debug_mode=False

[LOGGING]
log_combat_moves=False
log_distance_calculations=False

[DISPLAY]
show_combat_distance=False
show_unit_positions=False
```

### How to Run Manual Tests

#### Setup Phase
1. Launch game: `python src/game.py`
2. Navigate to combat area (or use debug spawn)
3. Enter combat scenario
4. Observe console output and log files

#### Test Execution Steps

**For Each Test:**
1. Start combat with configured flags
2. Execute the test procedure (see test plan below)
3. Verify expected output
4. Record results in tracking table
5. Move to next test

#### Output Verification

**Check Console Output:**
```bash
# Should see distance displayed
Distance to target: 15.5 units

# Should see positions
Player at (25, 10), Enemy at (25, 40)

# Should see round numbers
=== ROUND 1 ===
```

**Check Log Files:**
```bash
# Find game logs (created during combat)
logs/game_*.log

# Should contain entries like:
[12:34:56] Combat Move: Player used Attack on Enemy (25 damage)
[12:34:57] Distance: From (25,10) to (25,40) = 30.0 units
```

---

## Test Categories & Quick Links

### 1. Display Config Tests (5 tests)
**File:** `tests/PHASE4_MANUAL_TEST_PLAN.md` (Suite 1)
**Tests:** 1.1-1.5
**Duration:** ~15 minutes

**Quick Test: 1.1 - Show Distance**
```
1. Start combat with show_combat_distance=True
2. Execute player attack
3. VERIFY: Distance printed to console
4. Toggle show_combat_distance=False in config
5. Execute attack
6. VERIFY: Distance NOT printed
RESULT: [ ] PASS [ ] FAIL
```

### 2. Logging Tests (5 tests)
**File:** `tests/PHASE4_MANUAL_TEST_PLAN.md` (Suite 2)
**Tests:** 2.1-2.5
**Duration:** ~15 minutes

**Quick Test: 2.1 - Log Combat Moves**
```
1. Start combat with log_combat_moves=True
2. Execute 3 combat rounds
3. Check logs directory for game_*.log file
4. VERIFY: Each move logged with timestamp format
   "[HH:MM:SS] {actor} used {move} on {target}"
RESULT: [ ] PASS [ ] FAIL
```

### 3. Debug Manager Tests (5 tests)
**File:** `tests/PHASE4_MANUAL_TEST_PLAN.md` (Suite 3)
**Tests:** 3.1-3.5
**Duration:** ~20 minutes

**Quick Test: 3.1 - Instant Win Command**
```
1. Start combat with debug_mode=True
2. During combat, enter debug command: "instant_win"
3. VERIFY: Combat ends immediately with victory message
4. VERIFY: No crashes or errors
RESULT: [ ] PASS [ ] FAIL
```

**Quick Test: 3.3 - Damage Output Command**
```
1. Start combat with debug_mode=True
2. Enter debug command: "damage_output Player Enemy"
3. VERIFY: Damage calculation shown (base + modifiers)
4. VERIFY: Format includes final damage value
RESULT: [ ] PASS [ ] FAIL
```

### 4. Coordinate System Tests (5 tests)
**File:** `tests/PHASE4_MANUAL_TEST_PLAN.md` (Suite 4)
**Tests:** 4.1-4.5
**Duration:** ~20 minutes

**Quick Test: 4.1 - Grid Bounds Validation**
```
1. Start combat with show_unit_positions=True
2. VERIFY: Player/enemies spawn at valid coordinates
3. VERIFY: All coordinates within (0-50, 0-50) bounds
4. Try to move outside bounds (should clamp)
RESULT: [ ] PASS [ ] FAIL
```

**Quick Test: 4.2 - Distance Calculations**
```
1. Start combat with show_combat_distance=True
2. Record initial distance: D1
3. Move player closer/further
4. Record new distance: D2
5. VERIFY: D2 reflects movement (decreased/increased)
6. VERIFY: Distance calculations accurate
RESULT: [ ] PASS [ ] FAIL
```

### 5. NPC AI Tests (5 tests)
**File:** `tests/PHASE4_MANUAL_TEST_PLAN.md` (Suite 5)
**Tests:** 5.1-5.5
**Duration:** ~20 minutes

**Quick Test: 5.1 - Flanking Detection**
```
1. Set config: npc_flanking_enabled=True
2. Start combat with 3+ enemies
3. Position allies around player
4. VERIFY: Enemies attempt flanking moves
5. Check logs for flanking decisions
RESULT: [ ] PASS [ ] FAIL
```

**Quick Test: 5.2 - Tactical Retreat**
```
1. Set config: npc_tactical_retreat=True, npc_retreat_health_threshold=0.3
2. Start combat with 1 enemy
3. Damage enemy below 30% health
4. VERIFY: Enemy attempts to retreat/move away
5. Check logs for retreat decision
RESULT: [ ] PASS [ ] FAIL
```

### 6. Scenario Config Tests (5 tests)
**File:** `tests/PHASE4_MANUAL_TEST_PLAN.md` (Suite 6)
**Tests:** 6.1-6.5
**Duration:** ~20 minutes

**Quick Test: 6.1 - Standard Scenario Spawn**
```
1. Set config: current_scenario=standard
2. Start combat
3. VERIFY: Player spawns at expected location
4. VERIFY: Enemy spawns at expected location
5. Check log for scenario initialization
RESULT: [ ] PASS [ ] FAIL
```

**Quick Test: 6.2 - Pincer Scenario**
```
1. Set config: current_scenario=pincer
2. Start combat
3. VERIFY: Multiple enemies flank from sides
4. VERIFY: Player in center, enemies surround
5. Check positioning in logs
RESULT: [ ] PASS [ ] FAIL
```

### 7. Full System Integration Tests (5 tests)
**File:** `tests/PHASE4_MANUAL_TEST_PLAN.md` (Suite 7)
**Tests:** 7.1-7.5
**Duration:** ~20 minutes

**Quick Test: 7.1 - All Flags Enabled**
```
1. Enable all display + logging + debug flags
2. Start combat
3. Execute 10 combat rounds
4. VERIFY: No console spam or crashes
5. VERIFY: All outputs displayed correctly
6. Monitor performance (acceptable speed)
RESULT: [ ] PASS [ ] FAIL
```

---

## Test Tracking Sheet

Copy this table and fill in as you complete tests:

```
PHASE 4 MANUAL TEST RESULTS
Date: _______________
Tester: _______________

| Suite | Test | Status | Notes |
|-------|------|--------|-------|
| 1 | 1.1 Distance Display | [ ] | |
| 1 | 1.2 Positions Display | [ ] | |
| 1 | 1.3 Combat Rounds | [ ] | |
| 1 | 1.4 Animations | [ ] | |
| 1 | 1.5 Damage Numbers | [ ] | |
| 2 | 2.1 Log Moves | [ ] | |
| 2 | 2.2 Log Distance | [ ] | |
| 2 | 2.3 Log Accuracy | [ ] | |
| 2 | 2.4 Log NPC Decisions | [ ] | |
| 2 | 2.5 Log Damage | [ ] | |
| 3 | 3.1 Instant Win | [ ] | |
| 3 | 3.2 Spawn Enemy | [ ] | |
| 3 | 3.3 Damage Output | [ ] | |
| 3 | 3.4 Accuracy Info | [ ] | |
| 3 | 3.5 NPC Decision Trace | [ ] | |
| 4 | 4.1 Grid Bounds | [ ] | |
| 4 | 4.2 Distance Calc | [ ] | |
| 4 | 4.3 Zone Bounds | [ ] | |
| 4 | 4.4 Angle Calc | [ ] | |
| 4 | 4.5 Grid Info | [ ] | |
| 5 | 5.1 Flanking | [ ] | |
| 5 | 5.2 Tactical Retreat | [ ] | |
| 5 | 5.3 AI Difficulty | [ ] | |
| 5 | 5.4 Move Weighting | [ ] | |
| 5 | 5.5 Player Reference | [ ] | |
| 6 | 6.1 Standard Scenario | [ ] | |
| 6 | 6.2 Pincer Scenario | [ ] | |
| 6 | 6.3 Melee Scenario | [ ] | |
| 6 | 6.4 Boss Arena | [ ] | |
| 6 | 6.5 Scenario Rotation | [ ] | |
| 7 | 7.1 All Flags Enabled | [ ] | |
| 7 | 7.2 Mixed Flags | [ ] | |
| 7 | 7.3 All Commands | [ ] | |
| 7 | 7.4 Performance | [ ] | |
| 7 | 7.5 Save/Load | [ ] | |
| 8 | 8.1 Config Missing | [ ] | |
| 8 | 8.2 Player Ref None | [ ] | |
| 8 | 8.3 Invalid Coords | [ ] | |
| 8 | 8.4 Rapid Fire | [ ] | |
| 8 | 8.5 Log File Issues | [ ] | |

SUMMARY:
Total Tests: 40
Passed: ____
Failed: ____
Pass Rate: _____%
```

---

## Troubleshooting Guide

### Problem: Tests Won't Start
```bash
# Solution 1: Verify Python environment
python --version  # Should be 3.13+

# Solution 2: Check virtual environment
.venv\Scripts\Activate.ps1
which python  # Should show .venv path

# Solution 3: Reinstall dependencies
pip install -r requirements.txt
```

### Problem: Logs Not Generated
```
1. Check logs directory exists: logs/
2. Verify log_combat_moves=True in config
3. Check file permissions (write access)
4. Try creating test log manually:
   python -c "import logging; logging.basicConfig(filename='logs/test.log')"
```

### Problem: Config Flags Not Working
```
1. Verify config file syntax (INI format)
2. Check for typos in setting names
3. Ensure GameConfig class accepts the setting
4. Try with config_phase4_testing.ini instead
```

### Problem: Combat Won't Start
```
1. Ensure you're in a valid location
2. Check NPC spawning
3. Try debug command: spawn_enemy
4. Check console for error messages
```

### Problem: Distance Not Showing
```
1. Verify show_combat_distance=True
2. Check display_config is initialized
3. Try debug command: accuracy_info
4. Check logs for distance calculations
```

---

## Performance Benchmarks

**Expected Performance Metrics:**
- Config loading: ~15ms
- Flag checks: < 1ms
- Distance calculations: ~0.1ms per calculation
- Log file writes: ~1ms per entry
- NPC decision-making: 2-5ms per decision
- Full combat round: 100-200ms (depends on number of combatants)

**What to Monitor:**
- Console responsiveness (should be instant)
- No visible lag during combat rounds
- Log file writes complete within combat turn
- Distance updates appear immediately
- Debug commands execute in < 100ms

---

## Next Steps After Manual Testing

1. **Document Results** - Fill in tracking sheet
2. **Report Issues** - Create GitHub issues for any failures
3. **Performance Analysis** - Compare actual vs. expected metrics
4. **Log Analysis** - Verify log file format and completeness
5. **Merge Decision** - Ready to merge if all tests pass

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `pytest tests/ -q` | Run all tests |
| `python tests/phase4_test_executor.py` | Run automated Phase 4 tests |
| `python src/game.py` | Start game for manual testing |
| `.venv\Scripts\Activate.ps1` | Activate environment |
| `git log --oneline -10` | Check recent commits |

---

**For detailed test procedures, see:** `tests/PHASE4_MANUAL_TEST_PLAN.md`
**For full documentation, see:** `tests/PHASE4_COMPLETION_REPORT.md`
