# Manual Testing Quick Reference Card

## Fastest Setup (2 steps)

```bash
# Step 1: Activate environment
.venv\Scripts\Activate.ps1

# Step 2: Run automated tests
python tests/phase4_test_executor.py
```

**Result:** 9/9 tests pass in ~30 seconds ✅

---

## Game-Based Manual Testing (3 steps)

```bash
# Step 1: Activate environment
.venv\Scripts\Activate.ps1

# Step 2: Start the game
python src/game.py

# Step 3: Navigate to combat and test
# (Follow procedures from PHASE4_MANUAL_TEST_PLAN.md)
```

---

## What You're Testing

### Config System Integration
- ✅ Display flags control what's shown
- ✅ Logging respects all flags
- ✅ Debug commands available and working
- ✅ Coordinate system calculates positions/distances
- ✅ NPC AI uses configuration
- ✅ Scenarios spawn correctly
- ✅ All systems work together

### Test Coverage
- **9 Automated tests** - Quick validation (30 seconds)
- **40 Manual tests** - Detailed validation (2-3 hours)
- **9 Test suites** - Organized by functionality

---

## Quick Test Examples

### Test 1: Display Config (30 seconds)
```
1. Start combat with show_combat_distance=True
2. Attack enemy
3. Look for "Distance: X units" in output
4. PASS if distance shown
```

### Test 2: Logging (1 minute)
```
1. Start combat with log_combat_moves=True
2. Execute 3 combat rounds
3. Check logs/game_*.log
4. PASS if moves logged with timestamps
```

### Test 3: Debug Commands (1 minute)
```
1. During combat with debug_mode=True
2. Enter: "instant_win"
3. PASS if combat ends immediately
```

### Test 4: Coordinates (1 minute)
```
1. Start combat with show_unit_positions=True
2. PASS if all units at valid (0-50, 0-50) coordinates
3. PASS if distance calculations look reasonable
```

### Test 5: NPC AI (1 minute)
```
1. Start combat with debug_ai_decisions=True
2. Watch NPC make move
3. Check logs for AI reasoning
4. PASS if decisions make sense
```

---

## Key Files

| File | Purpose |
|------|---------|
| `MANUAL_TEST_SETUP_GUIDE.md` | Full setup instructions |
| `PHASE4_MANUAL_TEST_PLAN.md` | 40 detailed test procedures |
| `PHASE4_COMPLETION_REPORT.md` | Testing results summary |
| `phase4_test_executor.py` | Automated test runner |

---

## Expected Output Examples

### Console Output (Combat Starting)
```
=== COMBAT STARTED ===
Grid: 50x50
Player at (25, 10)
Enemy at (25, 40)
Distance: 30.0 units
=== ROUND 1 ===
```

### Log File Output
```
[12:34:56] Combat Move: Player used Attack on Enemy (25 damage)
[12:34:57] Distance: From (25,10) to (25,40) = 30.0 units
[12:34:58] NPC Bat decided to Attack (flanking: NO)
[12:34:59] Combat Move: Bat used Bite on Player (15 damage)
```

### Debug Command Output
```
> damage_output Player Enemy
Base Damage: 25
Modifiers: +0 (no buffs)
Resistances: -0 (no resists)
Final Damage: 25
```

---

## Status Checkpoints

### ✅ Pre-Testing (Verify Setup)
- [ ] Virtual environment activated
- [ ] 746 tests passing (`pytest tests/ -q`)
- [ ] Python 3.13+ installed
- [ ] requirements.txt dependencies installed

### ✅ Automated Testing (Quick Validation)
- [ ] Run `python tests/phase4_test_executor.py`
- [ ] All 9 tests PASS
- [ ] Results saved to JSON

### ✅ Manual Testing (Full Validation)
- [ ] Display tests: Distance, positions, animations
- [ ] Logging tests: Moves, calculations, decisions
- [ ] Debug tests: Commands execute successfully
- [ ] Coordinate tests: Positioning and distances correct
- [ ] NPC AI tests: Behavior respects configuration
- [ ] Scenario tests: Spawns work correctly
- [ ] Integration tests: All systems work together
- [ ] Edge case tests: Graceful handling of errors

---

## Troubleshooting (Common Issues)

| Issue | Solution |
|-------|----------|
| Tests won't start | Activate environment: `.venv\Scripts\Activate.ps1` |
| Import errors | Run: `pip install -r requirements.txt` |
| Logs not generated | Check `log_combat_moves=True` in config |
| Config not loading | Verify INI syntax, try `config_phase4_testing.ini` |
| Distance not showing | Verify `show_combat_distance=True` in config |
| Combat won't start | Use debug command `spawn_enemy` to force spawn |

---

## Time Estimates

| Activity | Time | Type |
|----------|------|------|
| Automated Tests | 30 sec | Quick |
| Quick Manual Tests (5) | 5 min | Fast |
| Standard Manual Tests (15) | 30 min | Medium |
| Full Manual Tests (40) | 2-3 hrs | Comprehensive |

---

## Success Criteria

✅ **Automated Tests**: All 9 pass
✅ **Display Output**: Correct flags control visibility
✅ **Logging**: Events logged with correct format
✅ **Coordinates**: Positions within bounds, distances accurate
✅ **NPC AI**: Behavior respects configuration
✅ **Scenarios**: All 4 scenarios spawn correctly
✅ **Performance**: No lag or slowdown
✅ **Integration**: All systems work together
✅ **Edge Cases**: Graceful error handling

---

## Quick Commands Reference

```bash
# Activate environment
.venv\Scripts\Activate.ps1

# Run all tests
pytest tests/ -q

# Run Phase 4 automated tests
python tests/phase4_test_executor.py

# Start game
python src/game.py

# Check branch status
git log --oneline -5

# View test results
cat tests/PHASE4_TEST_RESULTS.json
```

---

**Next Step:** Read `MANUAL_TEST_SETUP_GUIDE.md` for detailed setup, or run `python tests/phase4_test_executor.py` for quick validation.
