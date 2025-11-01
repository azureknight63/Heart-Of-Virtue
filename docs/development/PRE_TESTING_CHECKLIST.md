# Pre-Testing Checklist

## ✅ Environment Setup (5 minutes)

- [ ] Virtual environment created (`.venv`)
- [ ] Virtual environment activated
  ```bash
  .venv\Scripts\Activate.ps1
  ```
- [ ] Python version correct (3.13+)
  ```bash
  python --version
  ```
- [ ] Dependencies installed
  ```bash
  pip install -r requirements.txt
  ```
- [ ] All tests passing
  ```bash
  pytest tests/ -q
  ```
  Expected: `746 passed, 4 skipped`

---

## ✅ Verify Test Files Exist

- [ ] `tests/phase4_test_executor.py` exists
- [ ] `tests/PHASE4_MANUAL_TEST_PLAN.md` exists
- [ ] `tests/test_phase3_integration.py` exists
- [ ] `config_dev.ini` or `config_phase4_testing.ini` exists

---

## ✅ Verify Source Code Complete

- [ ] `src/config_manager.py` exists
- [ ] `src/display_config.py` exists
- [ ] `src/game_logger.py` exists
- [ ] `src/coordinate_config.py` exists
- [ ] `src/npc_ai_config.py` exists
- [ ] `src/scenario_config.py` exists
- [ ] `src/debug_manager.py` exists
- [ ] All files compile without errors

---

## ✅ Choose Testing Path

Choose **ONE** of the following:

### Path A: Automated Tests (Recommended - 30 seconds)
- [ ] Ready to run: `python tests/phase4_test_executor.py`
- [ ] Expected result: `9/9 PASSED`
- [ ] Time estimate: 30 seconds

### Path B: Quick Manual Tests (5 minutes)
- [ ] Reviewed: `MANUAL_TESTING_QUICK_REFERENCE.md`
- [ ] Ready to run 5 quick tests
- [ ] Expected result: All 5 PASS
- [ ] Time estimate: 5 minutes

### Path C: Comprehensive Manual Tests (2-3 hours)
- [ ] Reviewed: `PHASE4_MANUAL_TEST_PLAN.md`
- [ ] Printed or available: Test tracking sheet
- [ ] Ready to run all 40 tests
- [ ] Expected result: All 40 PASS
- [ ] Time estimate: 2-3 hours

---

## ✅ Pre-Test Validation

Run these commands to verify setup:

```bash
# 1. Verify environment
.venv\Scripts\Activate.ps1

# 2. Verify Python
python --version

# 3. Verify tests pass
pytest tests/ -q

# 4. Check for errors
python -m py_compile src/config_manager.py
python -m py_compile src/display_config.py
python -m py_compile src/game_logger.py
python -m py_compile src/coordinate_config.py
python -m py_compile src/npc_ai_config.py
python -m py_compile src/scenario_config.py
python -m py_compile src/debug_manager.py
```

All should succeed with no errors.

---

## ✅ Configuration Setup

For testing, you need proper config:

**Option 1: Use Default Config**
```bash
# Tests will use config_dev.ini automatically
python tests/phase4_test_executor.py
```

**Option 2: Use Test Config**
```bash
# Create or edit config_phase4_testing.ini with:
[DEBUG]
debug_mode=True
debug_ai_decisions=True

[LOGGING]
log_combat_moves=True
log_distance_calculations=True

[DISPLAY]
show_combat_distance=True
show_unit_positions=True
```

**Option 3: Customize for Your Tests**
- Edit INI file based on which tests you're running
- See `MANUAL_TEST_SETUP_GUIDE.md` for config examples
- Restart game after config changes

---

## ✅ Ready to Test!

**Choose your path:**

### Fast Path (30 seconds) ⚡
```bash
.venv\Scripts\Activate.ps1
python tests/phase4_test_executor.py
```
- [ ] Run command
- [ ] Verify: 9/9 PASSED
- [ ] Done! ✅

### Quick Path (5 minutes) 📋
```bash
# 1. Start game
.venv\Scripts\Activate.ps1
python src/game.py

# 2. Run quick tests from:
# MANUAL_TESTING_QUICK_REFERENCE.md
```
- [ ] Read quick reference
- [ ] Run 5 quick tests
- [ ] All PASS? ✅

### Comprehensive Path (2-3 hours) 🔍
```bash
# 1. Prepare
.venv\Scripts\Activate.ps1
pytest tests/ -q
# Verify 746 passed

# 2. Follow all tests
# See: PHASE4_MANUAL_TEST_PLAN.md
```
- [ ] Review test plan
- [ ] Complete all 40 tests
- [ ] Record results
- [ ] All PASS? ✅✅✅

---

## ✅ During Testing

### Important Notes
- Console output should be visible (don't minimize)
- Check both console AND log files
- Log files in: `logs/` directory
- Test results saved to: `tests/PHASE4_TEST_RESULTS.json`
- Record all results in tracking sheet

### Troubleshooting
- Tests fail? → Check `MANUAL_TEST_SETUP_GUIDE.md` Troubleshooting section
- Config issue? → Verify INI syntax
- Import error? → Run `pip install -r requirements.txt`
- Still stuck? → Check `HV-1_BRANCH_STATUS.md`

---

## ✅ After Testing

### Record Results
```
Total Tests: ___
Passed: ___
Failed: ___
Pass Rate: ___%
Time Spent: ___
Date: ___________
```

### Save Results
- [ ] Tracking sheet filled in
- [ ] Test results JSON saved
- [ ] Any failures documented
- [ ] Performance notes recorded

### Next Steps
- [ ] All tests PASS? → Ready for merge ✅
- [ ] Some tests FAIL? → Review failures
- [ ] Questions? → Check documentation

---

## ✅ Success Criteria

After testing, you should confirm:

- [ ] All chosen tests passed
- [ ] Console output looks correct
- [ ] Log files were created
- [ ] No crashes or errors
- [ ] Performance acceptable
- [ ] Config flags work
- [ ] All systems integrated
- [ ] Ready for production

---

## ✅ Quick Command Reference

```bash
# Setup (one-time)
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Pre-test validation
pytest tests/ -q
python -m py_compile src/*.py

# Test execution
python tests/phase4_test_executor.py        # Automated
python src/game.py                          # Manual

# Verification
git branch -v
git log --oneline -5
cat tests/PHASE4_TEST_RESULTS.json
```

---

## ✅ Timeline

| Step | Time | Done |
|------|------|------|
| Environment setup | 5 min | [ ] |
| Pre-test validation | 2 min | [ ] |
| Automated tests | 30 sec | [ ] |
| **FAST PATH TOTAL** | **~8 min** | [ ] |
| Quick manual tests | 5 min | [ ] |
| **QUICK PATH TOTAL** | **~13 min** | [ ] |
| Full manual tests | 2-3 hrs | [ ] |
| **FULL PATH TOTAL** | **~2.5-3 hrs** | [ ] |

---

## 🎯 Final Checklist

Before you start testing, confirm:

```
ENVIRONMENT READY:
  [ ] Python 3.13+ installed
  [ ] Virtual environment activated
  [ ] 746 tests passing
  [ ] All source files compile

TESTING MATERIALS READY:
  [ ] Test plan available
  [ ] Tracking sheet printed/ready
  [ ] Config file prepared
  [ ] Documentation reviewed

SUPPORT READY:
  [ ] Quick reference available
  [ ] Setup guide available
  [ ] Troubleshooting guide available
  [ ] Status docs available

DECISION MADE:
  [ ] Chose Path A (Automated) - 30 sec
  [ ] Chose Path B (Quick) - 5 min
  [ ] Chose Path C (Full) - 2-3 hrs

READY TO TEST:
  [ ] YES! Let's go! 🚀
```

---

**You're ready!** Start with your chosen path above.

**First command:**
```bash
.venv\Scripts\Activate.ps1
```

**See you on the other side!** ✅
