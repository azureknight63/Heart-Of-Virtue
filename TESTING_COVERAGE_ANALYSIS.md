# Heart of Virtue — Testing Coverage Analysis & Action Plan

**Generated:** 2026-05-14  
**Current Coverage:** Backend: 45% | Frontend: ~60%  
**Target:** 85%+ (critical modules at 80%+)

---

## Executive Summary

The project has strong test infrastructure in place (45 test files in tests/api/, Vitest + React Testing Library frontend tests), but tests are organizationally separated from coverage measurement. The largest gaps are:

1. **Backend P0 (Critical):** 
   - `src/api/services/game_service.py`: 8% (1,610 lines untested)
   - `src/combat.py`: 7% (323 lines untested)
   - `src/api/handlers/error_handler.py`: 0% (31 lines)

2. **Backend P1 (High Impact):**
   - 18 route modules: 11-19% coverage across 1,600+ lines
   - `src/api/combat_adapter.py`: 19% (777 lines)

3. **Frontend Critical:**
   - CooldownTray.jsx: 2.72% (complex cooldown state)
   - ShopDialog.jsx: 0.8% (transaction logic)
   - NpcChatPanel.jsx: 2.06% (dialogue flow)
   - LootDialog.jsx: 2.43% (item selection)
   - LevelUpModal.jsx: 3.92% (attribute allocation)

---

## Phase 1: Backend Infrastructure Issues

### Current Blocker: tests/api/ Tests

**Status:** 45 test files exist with ~880 tests, BUT:
- Excluded from default pytest run by `pytest.ini` norecursedirs
- 187 failed + 105 errored tests when run explicitly
- Infrastructure issues: import hooks, async handling, fixtures

**Root Causes:**
1. Tests/api tests try to run ALL integration tests at once
2. They depend on a fragile game engine initialization cascade
3. Async route handling requires `asgiref` (listed in requirements but test runner doesn't load it)
4. Shared conftest.py has complex sys.modules shims that conflict

**Recommendation:** 
Rather than fix all 187 failing tests (weeks of work), create focused unit tests in `tests/` that:
- Target high-impact methods directly (not through Flask routes)
- Use realistic mocks instead of integration fixtures
- Can run in <30 seconds and pass consistently

---

## Phase 2: High-ROI Testing Targets (Est. 40-50 hours)

### A. Backend P0: game_service.py (8% → 90%, ~20h effort)

**Highest-Impact Public Methods to Test:**

| Method | Lines | Impact | Test Strategy |
|--------|-------|--------|----------------|
| `move_player()` | 80 | Movement foundation | Test: cardinal directions, blocked moves, boundary crossing, event triggers |
| `execute_move()` | 150 | Combat core | Test: damage calc, cooldown, status effects, accuracy, critical hits |
| `get_inventory()` | 40 | Inventory API | Test: full inventory, serialization, weight calc |
| `equip_item()` | 50 | Equipment system | Test: valid equipment, invalid slot, stat bonuses, dual-wield |
| `interact_with_target()` | 120 | NPC/object interaction | Test: NPC dialogue, object actions, combat initiation |
| `start_combat()` | 100 | Combat initiation | Test: enemy spawning, reinforcements, combat state |

**Test File Structure:**
```
tests/test_game_service_movement.py       (20-25 tests, ~300 lines)
tests/test_game_service_combat.py          (30-35 tests, ~500 lines)
tests/test_game_service_inventory.py       (15-20 tests, ~250 lines)
tests/test_game_service_interaction.py     (20-25 tests, ~350 lines)
```

**Mock Strategy:**
- Use `unittest.mock.MagicMock` with spec=Player/Universe to catch attribute errors
- Pre-populate mock with realistic state (hp, inventory, location, equipment)
- Mock external dependencies (universe, items, npcs) at boundaries only
- Avoid mocking internal GameService methods to test real logic

**Test Examples:**

```python
# Test successful move
def test_move_player_north_success(self, game_service, player_in_open_area):
    result = game_service.move_player(player_in_open_area, "north")
    assert result["success"] == True
    assert result["new_position"] == (2, 1)
    assert player_in_open_area.location_y == 1

# Test blocked move
def test_move_player_into_wall(self, game_service, player_facing_wall):
    result = game_service.move_player(player_facing_wall, "east")
    assert result["success"] == False
    assert result["reason"] == "blocked"
    assert player_facing_wall.location_x == 0  # unchanged
```

### B. Backend P1: Route Tests (11-19% → 70-80%, ~15h effort)

**Scope:** 18 route modules, ~1,600 lines collectively

**Recommend:** Rather than write 500+ new tests, **enable existing tests/api tests** by:

1. **Create `tests/api_integration_enabled.py`** that:
   - Imports only 3-4 highest-impact route modules (auth, player, world, combat)
   - Uses the existing test fixtures from `tests/api/conftest.py`
   - Runs subset of critical tests from `/tests/api/` that pass

2. **Selectively fix broken tests:**
   - Fix 20-30 highest-impact failing tests from tests/api/
   - Leave rest for future work (they have dependencies on other gaps)

3. **Expected gains:**
   - auth.py: 35% → 80%
   - player.py: 13% → 75%
   - world.py: 11% → 70%
   - combat.py: 14% → 75%

---

## Phase 3: Frontend Component Tests (Est. 15-20 hours)

### Target Components & Test Approach

**1. CooldownTray.jsx (2.72% → 95%)**

```jsx
describe('CooldownTray', () => {
  // State variations
  it('renders collapsed moves list', () => { ... })
  it('expands on click', async () => { ... })
  it('shows cooldown progress bars', () => { ... })
  it('updates cooldowns on tick', async () => { ... })
  
  // Edge cases
  it('handles empty moves', () => { ... })
  it('shows completed moves', () => { ... })
  it('disables unavailable moves', () => { ... })
})
```

**Test Setup:**
```javascript
const mockMoves = [
  { name: 'Slash', cooldown: 2, maxCooldown: 3 },
  { name: 'Parry', cooldown: 0, maxCooldown: 2 },
]
const { rerender } = render(<CooldownTray moves={mockMoves} />)
```

**2. ShopDialog.jsx (0.8% → 90%)**

- Tab switching (buy/sell/buyback)
- Item selection and details
- Weight bar + overweight state
- Transaction preview (cost, item result)
- Buy/sell button states
- Error handling (inventory full, insufficient funds)

**3. NpcChatPanel.jsx (2.06% → 85%)**

- Conversation flow states
- Message rendering (jean vs npc speaker)
- Option selection (click + keyboard)
- Loquacity tracking (UI shows remaining talks)
- Error recovery (retry button)

**4. LootDialog.jsx (2.43% → 90%)**

- Item selection UI
- Enchantment display
- Weight calculation
- Accept/decline actions

**5. LevelUpModal.jsx (3.92% → 90%)**

- Attribute selection
- Point input validation
- Submit handler

**Common Patterns:**
```javascript
// Setup with providers
const renderWithProviders = (component) => {
  return render(
    <AudioContext.Provider value={mockAudio}>
      <ThemeProvider value={theme}>
        {component}
      </ThemeProvider>
    </AudioContext.Provider>
  )
}

// Mock API calls
vi.mock('../../api/endpoints', () => ({
  npcChat: { open: vi.fn(), respond: vi.fn() },
  shop: { buy: vi.fn(), sell: vi.fn() },
}))

// Async waiting
await waitFor(() => expect(screen.getByText('Confirm')).toBeInTheDocument())
```

---

## Phase 4: Coverage Tracking Setup (Est. 2-3 hours)

### 1. GitHub Actions CI Integration

**Add to `.github/workflows/test.yml`:**

```yaml
- name: Backend Coverage
  run: |
    python -m pytest tests/ \
      --cov=src/api/services \
      --cov=src/api/routes \
      --cov-report=term-missing \
      --cov-fail-under=70

- name: Frontend Coverage
  run: |
    cd frontend
    npm run test:cov -- --lines 70 --functions 70
```

### 2. Coverage Badges

**In README.md:**
```markdown
![Backend Coverage](https://img.shields.io/badge/coverage-70%25-yellow?style=flat)
![Frontend Coverage](https://img.shields.io/badge/coverage-75%25-yellow?style=flat)
```

### 3. Coverage Trend Tracking

Create `docs/coverage/COVERAGE_TREND.md`:
```
| Date | Backend | Frontend | Delta |
|------|---------|----------|-------|
| 2026-05-14 | 45% | 60% | Baseline |
| 2026-05-21 | 65% | 72% | +20%/+12% (Phase 1-2) |
```

---

## Implementation Roadmap

### Week 1: Backend (P0)
- **Day 1-2:** game_service.py focused tests (300 lines, 20 tests)
  - move_player, equip_item, interact_with_target, start_combat
  - Target: 20+ passing tests, 15% coverage gain
- **Day 3:** auth/player routes (existing tests, selective fixes)
  - Target: Fix 10 tests, enable tests/api subset
- **Day 4:** world/combat routes
- **Day 5:** Integration run, coverage reporting

### Week 2: Frontend + Wrap-Up
- **Day 1-3:** CooldownTray + ShopDialog tests (200+ lines, 25-30 tests)
- **Day 4:** NpcChatPanel + LootDialog + LevelUpModal
- **Day 5:** Coverage CI setup, final verification, commit

---

## Testing Best Practices Applied

### Backend Unit Tests
✅ Use direct method calls (not HTTP routes)  
✅ Mock external dependencies (universe, items, npcs)  
✅ Test both success and error paths  
✅ Use descriptive test names (what/when/then)  
✅ Fixtures for reusable mock state  
✅ Parametrized tests for multiple cases  

### Frontend Component Tests
✅ Test user interactions (click, type, hover)  
✅ Verify async operations (wait, waitFor)  
✅ Mock API calls at module boundary  
✅ Test component state changes  
✅ Cover error states + empty states  
✅ Use React Testing Library best practices (getByRole, getByText)  

---

## Known Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| game_service.py methods have interdependencies | Tests may need state setup | Use fixtures to pre-populate realistic state |
| Frontend components depend on complex context | Mocking is error-prone | Use renderWithProviders helper |
| tests/api tests have flaky infrastructure | CI will fail unpredictably | Run only critical tests, skip flaky ones |
| Combat logic is highly stateful | Unit tests may not catch edge cases | Add integration tests later, focus on happy path now |

---

## Success Criteria

**By end of Phase 2 (2 weeks):**
- Backend: 45% → 65% (game_service 8%→50%, routes 11-19%→60%)
- Frontend: 60% → 72% (critical components 0-3%→85%)

**By end of Phase 3 (4 weeks):**
- Backend: 65% → 80%
- Frontend: 72% → 82%

**Full coverage (8+ weeks, future work):**
- Backend: 80% → 95%
- Frontend: 82% → 95%

---

## Summary: What to Do Next

### Immediate Actions (Next Session)

1. **Create `tests/test_game_service_focused.py`** with 20-25 tests for:
   - move_player() — 5 tests (valid, blocked, boundary, events)
   - execute_move() — 5 tests (damage, cooldown, accuracy)
   - equip_item() — 3 tests (valid, invalid slot, stats)
   - interact_with_target() — 4 tests (npc, object, combat)
   - get_inventory() — 3 tests (empty, full, serialization)

2. **Fix test_app.py blueprint test** (already done ✅)

3. **Create `frontend/src/components/CooldownTray.test.jsx`** with 15-20 tests

4. **Add pytest configuration** to measure coverage from tests/ directory only

5. **Commit with detailed message** referencing this analysis

### For Future Sessions

- Selectively enable critical tests from tests/api/ (fix 10-15 failing tests)
- Add route tests (auth, player, world, combat)
- Complete frontend component coverage (ShopDialog, NpcChatPanel, etc.)
- Set up CI + coverage tracking
- Document findings in CLAUDE.md

---

## Files Modified/Created This Session

- ✅ `tests/api/test_app.py` — Fixed blueprint test
- ⚠️ `tests/test_game_service_coverage.py` — Partial (needs method-specific updates)
- 📋 `TESTING_COVERAGE_ANALYSIS.md` — This document

---

**Contact:** Refer to CLAUDE.md for project conventions and architecture rules.
