# Test Coverage Dashboard

Last Updated: 2026-08-23

## Current Coverage State

| Layer | Current | Gate | Status |
|-------|---------|------|--------|
| **Backend (Python)** | 96% | 85% (`--cov-fail-under=85`) | 🟢 Well above gate |
| **Frontend (React)** | 99.4% stmts / 95.1% branch | 95% (`vite.config.js` thresholds) | 🟢 Above gate (branch coverage is the tight margin) |
| **Total Test Count** | 9,967 | — | 🟢 7,671 backend + 2,296 frontend, 0 failing |

## Backend Coverage Details

```
Current: 96% (23,713 lines covered / 24,785 total)
Gate:    85% (enforced by CI via --cov-fail-under=85)

python -m pytest --cov=src --cov=ai --cov-report=term-missing --cov-fail-under=85 -q
7,671 passed, 565 skipped, 0 failed (default suite; excludes tests/api, tests/broken, tests/uat, tests/integration)
```

### Package rollups

| Package | Coverage | Stmts | Missed |
|---|---|---|---|
| `src/moves/` | 99.1% | 4,683 | 41 |
| `src/player/` | 95.7% | 576 | 25 |
| `src/api/` | 95.5% | 6,726 | 305 |
| `ai/` | 95.0% | 1,986 | 100 |
| `src/npc/` | 94.9% | 2,869 | 145 |
| `src` (top-level: `combat.py`, `states.py`, `universe.py`, `items.py`, `objects.py`, …) | 94.9% | 5,975 | 302 |
| `src/story/` | 93.8% | 1,890 | 118 |
| `src/tilesets/` | 55.0% | 80 | 36 |

### Lowest-covered modules

| Module | Coverage | Notes |
|---|---|---|
| `src/_unpickle_worker.py` | 31% (13 stmts) | Subprocess entry point for isolated unpickling — exercised via `save_fuzzer.py`, not unit tests |
| `src/tilesets/grondelith_mineral_pools.py` | 51% (73 stmts) | Map/tileset content — same "intentionally low" category as `src/story/` |
| `src/api/routes/player.py` | 78% |  |
| `src/api/utils/log_cleanup.py` | 80% |  |
| `src/genericng.py` | 80% |  |
| `src/player/_movement.py` | 82% |  |
| `src/api/routes/combat.py` | 83% |  |
| `src/story/ch03.py` | 84% (500 stmts) | Narrative — see FAQ below |
| `src/events.py` | 86% |  |
| `src/map_placeholders.py` | 86% |  |
| `src/objects.py` | 87% (787 stmts) |  |
| `src/api/serializers/_safe.py` | 88% |  |
| `ai/provider_digest.py` | 89% |  |
| `src/npc/_adjutant.py` | 89% |  |
| `src/tiles.py` | 89% |  |

Only 8 of 123 measured modules sit under the 85% file-level figure; every package rollup clears the gate.

## Frontend Coverage Details

```
Current: 99.4% statements / 95.11% branch / 98.26% functions / 99.4% lines
Gate:    95% (vite.config.js thresholds)

cd frontend && npm test -- --run --coverage
Test Files: 107 passed (107)
Tests:      2,296 passed (2,296), 0 failed
```

### Directory rollups

| Directory | Stmts | Branch | Funcs | Lines |
|---|---|---|---|---|
| `src/context/` | 100% | 99.1% | 100% | 100% |
| `src/data/` | 100% | 100% | 100% | 100% |
| `src/styles/` | 100% | 100% | 100% | 100% |
| `src/utils/` | 100% | 99.2% | 100% | 100% |
| `src/components/` | 99.5% | 95.0% | 99.5% | 99.5% |
| `src/hooks/` | 99.4% | 94.1% | 100% | 99.4% |
| `src/pages/` | 98.4% | 92.2% | 90.6% | 98.4% |
| `src/api/` | 96.9% | 98.3% | 95.3% | 96.9% |

### Lowest-covered files

| File | Stmts | Branch | Funcs | Notes |
|---|---|---|---|---|
| `src/api/socketClient.js` | 73.3% | 50% | 50% | Lowest in the tree — socket reconnection edge paths |
| `src/pages/GamePage.jsx` | 95.3% | 89.7% | 87.5% |  |
| `src/hooks/useEventManager.js` | 96.8% | 85.8% | 100% |  |
| `src/components/Battlefield.jsx` | 97.6% | 96.5% | 100% |  |
| `src/components/BattlefieldGrid.jsx` | 97.6% | 84.4% | 100% |  |
| `src/components/DefeatDialog.jsx` | 97.9% | 92.9% | 100% |  |
| `src/components/EventDialog.jsx` | 98.4% | 92.5% | 100% |  |
| `src/components/BaseDialog.jsx` | 98.6% | 91.0% | 100% | Recently reworked (Escape/focus-trap) — new branches, not yet fully exercised |
| `src/hooks/useCombatSocket.js` | 98.7% | 90.6% | 100% |  |
| `src/components/BookReaderDialog.jsx` | 98.7% | 96.6% | 100% |  |

Branch coverage at 95.11% overall sits closest to the 95% gate — `socketClient.js` and `useEventManager.js` are the two files most worth a look if that margin needs padding.

## How Coverage is Measured

### Backend (pytest)

```bash
python -m pytest --cov=src --cov=ai --cov-report=term-missing --cov-report=html --cov-fail-under=85 -q
open htmlcov/index.html
```

**Exclusions** (see `pytest.ini`): `tests/api/`, `tests/broken/`, `tests/uat/`, `tests/integration/`, debug/check/find/reproduce/verify/uat/manual scripts, and a few named tier-4 files.

### Frontend (vitest)

```bash
cd frontend && npm test -- --run --coverage
open coverage/index.html
```

**Included**: all of `src/**/*.{js,jsx}`. **Excluded**: `src/main.jsx`, `src/test/**`.

## Regenerating this dashboard

```bash
python -m pytest --cov=src --cov=ai --cov-report=term-missing -q -p no:cacheprovider
cd frontend && npm test -- --run --coverage
```

Update the headline table, package/directory rollups, and lowest-covered lists from the fresh output; update `CLAUDE.md`'s "Coverage gates" bullet to match.

## FAQ

**Q: Why is `src/story/` (and `src/tilesets/`) coverage lower than everything else?**
A: Narrative and map-placement content is intentionally lower-coverage — story paths branch heavily on player choice and state, and testing every branch has poor ROI versus testing the mechanics (combat, inventory, movement, saves) those branches call into. The engine code those chapters call is itself well-covered.

**Q: Can I run coverage locally without CI?**
A: Yes — see "Regenerating this dashboard" above; add `--cov-report=html` (backend) or open `coverage/index.html` (frontend) for a browsable per-line report.

**Q: What happens if coverage drops on a PR?**
A: `--cov-fail-under=85` fails the backend job outright; the frontend `vite.config.js` thresholds fail the same way. Either add tests to restore coverage or, rarely, get a maintainer exception.
