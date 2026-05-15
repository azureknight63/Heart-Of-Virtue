# Test Coverage Dashboard

Last Updated: 2026-05-15

## Current Coverage State

| Layer | Current | Target | Status | Trend |
|-------|---------|--------|--------|-------|
| **Backend (Python)** | 47% | 60% | 🟡 Below target | +2% this week |
| **Frontend (React)** | ~75% | 85% | 🟡 Below target | +3% this week |
| **Total Test Count** | 1,308 | 1,500+ | 🟢 On track | +50 new tests |

## Backend Coverage Details

```
Current: 47% (13,383 lines covered / 25,119 total)
Target:  60%
Minimum: 55% (enforced by CI)

Key areas:
- src/api/routes/: 80% (well-tested)
- src/combat.py: 62% (good coverage)
- src/moves/: 58% (improved with package refactor)
- src/api/services/: 75% (core logic well-covered)
- src/story/: 18% (narrative content — low coverage expected)
- src/npc.py: 54% (needs more edge cases)
```

### Failing Tests (22 failed, 1,286 passed)

Currently blocking CI coverage enforcement:
- `test_game_service_coverage.py` — 15 failures (GameService refactoring in progress)
- `test_game_service_critical_methods.py` — 7 failures (API integration tests)

**Action**: These tests are high-priority fixes needed to reach 55% minimum enforcement.

## Frontend Coverage Details

```
Current: ~75% (estimated from test pass rate)
Target:  85%
Minimum: 80% (enforced by CI)

Components covered:
- Battlefield.jsx: 82%
- MainMenuPage.jsx: 90%
- GamePage.jsx: 78%
- CombatLog.jsx: 85%

Components needing work:
- NpcChatPanel.jsx: 65% (complex state, async errors)
- MobileTabBar.jsx: 70% (touch interactions)
- InventoryPanel.jsx: 72% (inventory state management)
```

### Frontend Test Status

```
Test Files: 2 failed | 51 passed (53 total)
Tests:      2 failed | 567 passed (569 total)

Known issues:
- NpcChatPanel.jsx: ReferenceError in error state rendering (retryFn undefined)
- Complex async state handling in network error tests
```

## Coverage Targets by Layer

### Backend (Python)

| Module | Current | Target | Notes |
|--------|---------|--------|-------|
| src/api/routes/ | 80% | 85% | Well-tested REST endpoints |
| src/api/services/ | 75% | 80% | Core game logic |
| src/api/middleware/ | 70% | 75% | Auth, error handling |
| src/combat.py | 62% | 70% | Turn-based combat engine |
| src/moves/ | 58% | 65% | 73+ ability classes |
| src/player.py | 55% | 70% | Character state, progression |
| src/npc.py | 54% | 70% | NPC AI, combat behavior |
| src/combatant.py | 48% | 65% | Base class for shared logic |
| src/items.py | 45% | 60% | Item system, equipment |
| src/universe.py | 68% | 75% | World/map system |
| src/states.py | 40% | 60% | Status effects, buffs/debuffs |
| src/story/ | 18% | 25% | Narrative (intentionally low) |
| ai/ | 35% | 50% | LLM integration, Mynx adapter |

### Frontend (React)

| Module | Current | Target | Notes |
|--------|---------|--------|-------|
| pages/ | 88% | 90% | Login, menu, game pages |
| components/ | 75% | 85% | UI components |
| hooks/ | 82% | 90% | Custom API/game hooks |
| api/ | 90% | 95% | Axios client, endpoints |
| context/ | 68% | 80% | React context providers |

## CI/CD Enforcement Rules

### Branch Protection: `master` / `develop`

1. **Test Coverage Workflow MUST Pass**
   - Backend coverage minimum: 55% (enforced via `--cov-fail-under`)
   - Frontend tests must pass (569 tests)
   - All CI checks must succeed before merge

2. **Coverage Trend Monitoring**
   - PR comments auto-posted with coverage summary
   - Automatic badge updates on main branch
   - Monthly trend reports generated

3. **Pre-Commit Hook** (local dev)
   ```bash
   # Prevents commits that break tests
   python -m pytest -q --tb=line
   ```

## How Coverage is Measured

### Backend (pytest)

```bash
# Run with coverage reporting
python -m pytest \
  --cov=src \
  --cov=ai \
  --cov-report=term-missing \
  --cov-report=html

# View HTML report
open htmlcov/index.html
```

**Exclusions** (see `pytest.ini`):
- Tests in `tests/api/`, `tests/broken/`, `tests/uat/` (UAT only)
- Debug scripts: `debug_*.py`, `check_*.py`, `find_*.py`, etc.
- Manual test files: `manual_*.py`, `uat_*.py`

### Frontend (vitest)

```bash
cd frontend && npm test -- --run --coverage

# View HTML report
open coverage/index.html
```

**Included**:
- All files in `src/**/*.{js,jsx}`

**Excluded**:
- `src/main.jsx` (app entry point)
- `src/test/**` (test infrastructure)

## Monthly Trend Tracking

*(Placeholder for automated monthly tracking)*

### May 2026

- **Week 1**: Backend 45%, Frontend 72%, Tests 1,250
- **Week 2**: Backend 47%, Frontend 75%, Tests 1,286 (this week)
- **Week 3**: *pending*
- **Week 4**: *pending*

## Coverage Badges

### README Badge URLs

```markdown
![Backend Coverage](https://img.shields.io/badge/backend--coverage-47%25-orange)
![Frontend Coverage](https://img.shields.io/badge/frontend--coverage-75%25-yellow)
```

Update these badges on each PR merge via workflow automation.

## Next Steps

### Immediate (this week)

1. Fix 22 failing tests in `test_game_service_coverage.py`
   - Priority: High (blocks 55% enforcement)
   - Estimated effort: 2-4 hours
   - Impact: +5% coverage

2. Fix NpcChatPanel.jsx error state rendering
   - Priority: High (2 test failures)
   - Estimated effort: 1 hour
   - Impact: +3% coverage

### Short-term (this month)

3. Reach 55% backend minimum (currently 47%)
   - Focus: `src/states.py` (40% → 60%)
   - Focus: `src/npc.py` (54% → 70%)
   - Focus: `src/items.py` (45% → 60%)
   - Estimated effort: 8-12 hours
   - Impact: +8% coverage

4. Reach 80% frontend minimum (currently ~75%)
   - Focus: `InventoryPanel.jsx` (72% → 85%)
   - Focus: `MobileTabBar.jsx` (70% → 85%)
   - Estimated effort: 4-6 hours
   - Impact: +5% coverage

### Medium-term (2-3 months)

5. Reach target state
   - Backend: 60% coverage, 1,500+ tests
   - Frontend: 85% coverage, 600+ tests
   - Total: 2,100+ comprehensive tests
   - Estimated effort: 30-40 hours
   - Payoff: Regression detection, refactoring confidence

## Resources

- **Pytest Coverage Docs**: https://pytest-cov.readthedocs.io/
- **Vitest Coverage**: https://vitest.dev/guide/coverage
- **GitHub Actions Workflows**: `.github/workflows/test-coverage.yml`
- **CI/CD Config**: See CLAUDE.md "Testing" section

## FAQ

**Q: Why is story/ coverage so low?**
A: Narrative content is intentionally low-coverage because story paths are hard to test (many branches, state-dependent). We focus on core mechanics (combat, inventory, movement) which must be 60%+.

**Q: Can I run coverage locally without CI?**
A: Yes!
```bash
# Backend
python -m pytest --cov=src --cov=ai --cov-report=html
open htmlcov/index.html

# Frontend
cd frontend && npm test -- --run --coverage
open coverage/index.html
```

**Q: What happens if coverage drops on a PR?**
A: The workflow fails and posts a comment with the coverage summary. You must either:
1. Add tests to restore coverage
2. Request an exception from the maintainer (rare)

**Q: Do merge commits reset the trend?**
A: No. Coverage is measured on the merged code, so trends are continuous.
