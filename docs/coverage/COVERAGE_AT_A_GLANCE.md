# Coverage At a Glance: Quick Reference

**Last Updated:** 2026-05-15 | **Coverage:** 51% | **Target:** 60% | **Gap:** 9 points

---

## 🎯 Coverage by Layer

| Layer | Status | Coverage | Tests | Priority |
|-------|--------|----------|-------|----------|
| **Backend (Python)** | ⚠️ Needs work | **51%** (11,837/24,347 lines) | 1,903 tests | URGENT |
| **Frontend (React)** | ✓ Good | **~75%** (est.) | 1,185 tests | Medium |
| **Game Engine** | ⚠️ Needs work | **56%** | 200+ | URGENT |
| **API Routes** | 🔴 Critical gap | **11-23%** | <50 | CRITICAL |
| **NPC Systems** | 🔴 Critical gap | **25-43%** | <100 | CRITICAL |

---

## 🚨 Critical Gaps (0% Coverage)

These files have **zero test coverage** and are actively used:

| File | Type | Impact | Easy Fix? |
|------|------|--------|-----------|
| `src/api/routes/npc_chat.py` | Chat API | Medium | Yes |
| `src/api/sockets.py` | WebSocket | Low | Complex |
| `src/api/utils/input_sanitizer.py` | Validation | High | Yes |
| `src/verify_combat_event.py` | Verification | Low | Yes |
| `src/open_terminal.py` | CLI | N/A | N/A |

---

## 📊 Modules Ranking (Highest to Lowest Coverage)

### Tier 1: Well-Tested (75%+)

- ✓ src/moves/__init__.py (100%)
- ✓ src/loot_tables.py (100%)
- ✓ src/skilltree.py (100%)
- ✓ src/npc/_base.py (100%)
- ✓ src/events.py (97%)
- ✓ src/scenario_config.py (91%)
- ✓ src/player/__init__.py (96%)
- ✓ src/combatant.py (89%)

### Tier 2: Decent Coverage (60-75%)

- ~ src/player/_debug.py (88%)
- ~ src/player/_movement.py (84%)
- ~ src/moves/_unarmed.py (84%)
- ~ src/interface.py (65%)
- ~ src/universe.py (68%)
- ~ src/enchant_tables.py (74%)
- ~ src/npc/_shop.py (83%)
- ~ src/items.py (67%)

### Tier 3: Poor Coverage (40-60%)

- ⚠️ src/moves/_movement.py (68%)
- ⚠️ src/combat_battlefield.py (44%)
- ⚠️ src/moves/_npc.py (67%)
- ⚠️ src/moves/_sword.py (65%)
- ⚠️ src/states.py (55%)
- ⚠️ src/api/serializers/combat.py (64%)
- ⚠️ src/functions.py (74%)

### Tier 4: Critical Gaps (<40%)

- 🔴 src/api/routes/ (11-23%) — **CRITICAL**
- 🔴 src/api/services/game_service.py (56%) — **CRITICAL**
- 🔴 src/api/services/session_manager.py (24%)
- 🔴 src/npc/_chat_llm.py (11%)
- 🔴 src/npc/_adjutant.py (10%)
- 🔴 src/npc/_combat.py (28%)
- 🔴 src/npc/_llm.py (43%)
- 🔴 src/combat.py (7%)
- 🔴 src/story/ch02.py (12%)

---

## 💪 High-ROI Tests (Easiest Wins)

### Tier 1: Quick Wins (10 tests, 3 hours, +2-3% coverage)

| Test | Effort | Lines | Priority |
|------|--------|-------|----------|
| GameService.execute_move() | 45 min | 30 | **CRITICAL** |
| GameService.apply_status_effect() | 60 min | 40 | **CRITICAL** |
| GameService cooldown drain | 30 min | 11 | **HIGH** |
| API route integration (world) | 40 min | 25 | **HIGH** |
| API route integration (combat) | 35 min | 30 | **HIGH** |
| API route integration (inventory) | 50 min | 50 | **HIGH** |
| Status effects core logic | 45 min | 25 | **MEDIUM** |
| Combat beat progression | 45 min | 60 | **HIGH** |
| Move validation edge cases | 40 min | 35 | **MEDIUM** |
| NPC action selection | 50 min | 40 | **MEDIUM** |

**Total: 11 tests, 6 hours, +5-7% coverage → 56-58% overall**

---

## 🗺️ Execution Plan

### Week 1: Tier 1 (Foundation)
- **Mon-Tue:** GameService core methods (6 tests, 3.5 hours)
- **Wed:** API route integration (3 tests, 2 hours)
- **Thu:** Cleanup & status effects (2 tests, 1.5 hours)
- **Fri:** Review, debug, commit
- **Result:** 56-58% coverage

### Week 2-3: Tier 2 (Features)
- NPC Combat AI (4 hours)
- Ranged mechanics (3 hours)
- Movement system (3 hours)
- Shop system (3 hours)
- Quest completion (2 hours)
- **Result:** 65-75% coverage

### Week 4-6: Tier 3 (Completeness)
- All move types (8 hours)
- NPC dialogue (6 hours)
- Serializers (5 hours)
- Error handling (6 hours)
- **Result:** 80-92% coverage

### Week 7+: Polish
- Remaining edge cases
- Integration scenarios
- **Result:** 95%+ coverage

---

## 📋 Test Infrastructure Checklist

- [x] Pytest configured (1,903 tests)
- [x] Pytest fixtures available (conftest.py)
- [x] Coverage reporting enabled (htmlcov/)
- [x] CI/CD pipeline has coverage checks
- [x] Vitest setup for frontend
- [x] React Testing Library available

**Ready to start writing tests immediately.**

---

## 🔧 Common Test Patterns

### GameService Pattern

```python
def test_my_feature(client, test_player):
    """Test description."""
    game_service = GameService()
    
    # Setup
    player = create_test_player()
    npc = create_test_npc()
    
    # Execute
    result = game_service.some_method(player, npc)
    
    # Assert
    assert result['success'] == True
```

### API Route Pattern

```python
def test_my_route(client, test_player):
    """Test description."""
    response = client.get(
        '/api/endpoint',
        headers={'Authorization': f'Bearer {test_player.token}'}
    )
    
    assert response.status_code == 200
    assert 'expected_field' in response.json
```

### Frontend Component Pattern

```javascript
import { render, screen } from '@testing-library/react';
import MyComponent from './MyComponent';

test('renders correctly', () => {
  render(<MyComponent />);
  expect(screen.getByText('Expected text')).toBeInTheDocument();
});
```

---

## 📈 Progress Tracking

Track your progress with this simple formula:

```
New Coverage = (Covered + Δ Covered) / (Total + Δ Total) × 100%

Current:  51% = 12,510 / 24,347
Tier 1:   57% = 12,880 / 24,347 (+370 lines covered)
Tier 2:   68% = 16,556 / 24,347 (+3,676 lines covered)
Tier 3:   85% = 20,695 / 24,347 (+4,139 lines covered)
Final:    95% = 23,130 / 24,347 (+2,435 lines covered)
```

---

## 🚀 Next Steps

1. **Create test files** for Tier 1 tests (10 minutes)
   ```bash
   mkdir -p tests/api/services tests/api/routes
   touch tests/api/services/test_game_service_moves.py
   touch tests/api/routes/test_world_routes.py
   ```

2. **Write first test** (GameService.execute_move) — 45 minutes
   - Follow the pattern in TESTING_ACTION_PLAN.md
   - Use existing fixtures from conftest.py

3. **Run and verify**
   ```bash
   python -m pytest tests/api/services/test_game_service_moves.py -v
   python -m pytest --cov=src/api/services/game_service -v
   ```

4. **Commit** after each test file
   ```bash
   git add tests/api/services/
   git commit -m "test(game-service): Add move execution tests"
   ```

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| **COVERAGE_REPORT.md** | Detailed analysis by module, untested lines, recommendations |
| **TESTING_ACTION_PLAN.md** | Step-by-step implementation guide with code samples |
| **COVERAGE_AT_A_GLANCE.md** | This file — quick reference and next steps |
| **index.html** | Interactive coverage viewer (click to see line-level details) |

---

## 💬 FAQ

**Q: Where do I start?**
A: Start with `TESTING_ACTION_PLAN.md`, Test 1 (GameService.execute_move). Estimated 45 minutes.

**Q: How much time to reach 60%?**
A: Tier 1 tests only = 6 hours of focused work.

**Q: What's the most impactful test?**
A: GameService.execute_move() — 217 untested lines, called every turn.

**Q: Can I test the LLM stuff?**
A: Yes, mock the OpenRouter API with `pytest.mock`.

**Q: Should I test the terminal UI?**
A: No. Focus on game logic (API layer) — terminal UI is getting replaced by React.

**Q: How do I know coverage improved?**
A: Run `python -m pytest --cov=src --cov-report=term-missing` after each commit.

---

## 🎓 Learning Resources

- **pytest docs:** https://docs.pytest.org/
- **pytest-cov:** https://pytest-cov.readthedocs.io/
- **Testing best practices:** `CLAUDE.md` (Code Quality section)
- **Existing tests:** Look at `tests/api/routes/test_*.py` for examples

---

**Your current coverage is 51%. Let's get it to 95% in 3-4 weeks of focused work.**

**Start now → 45 minutes → First test passing → +0.5% coverage → Keep momentum.**
