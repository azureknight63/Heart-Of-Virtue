# Test Coverage Dashboard

**This is the only place coverage numbers live.** Root `CLAUDE.md` carries the gates and
links here; it deliberately keeps no second copy, because the copy it used to keep went
45 points stale in three months. Same reason the three files that used to sit beside this
one in `docs/coverage/` are now stubs — they were a second, third and fourth account of
the same measurement, and readers reaching for the one named "at a glance" got the worst
of them.

## Gates (these are stable; the numbers below are not)

| Layer | Gate | Enforced by |
|---|---|---|
| Backend (Python) | ≥ 85% | `--cov-fail-under=85` in `.github/workflows/test-coverage.yml` |
| Frontend (React) | ≥ 95% lines/statements/functions/branches | `vite.config.js` thresholds — the build fails below them |

## Test counts — measured 2026-08-28

| Suite | Result | Command |
|---|---|---|
| Backend (default suite) | **10,434 passed, 0 failed** | `python -m pytest -q` |
| Frontend | **2,600 passed, 0 failed** across **116 test files** | `cd frontend && npm test -- --run` |

The default backend suite excludes `tests/api`, `tests/broken`, `tests/uat` and
`tests/integration` (`pytest.ini`'s `norecursedirs`).

## Coverage percentages — NOT measured in this pass

The percentages and rollups below are from the **2026-08-23** run. The backend suite has
grown from 7,671 to 10,434 tests since then and the frontend from 2,296 to 2,600, so
treat every number in this section as **unverified**: it is the last known measurement,
not the current one. Re-run the commands under "Regenerating this dashboard" before
quoting any of it, and update this heading when you do.

Last measured coverage (2026-08-23): backend 96% (23,713 / 24,785 lines);
frontend 99.4% statements / 95.11% branch / 98.26% functions / 99.4% lines.

### Backend package rollups (2026-08-23, unverified)

| Package | Coverage | Stmts | Missed |
|---|---|---|---|
| `src/moves/` | 99.1% | 4,683 | 41 |
| `src/player/` | 95.7% | 576 | 25 |
| `src/api/` | 95.5% | 6,726 | 305 |
| `ai/` | 95.0% | 1,986 | 100 |
| `src/npc/` | 94.9% | 2,869 | 145 |
| `src` (top-level: `states.py`, `universe.py`, `items.py`, `objects.py`, `functions.py`, …) | 94.9% | 5,975 | 302 |
| `src/story/` | 93.8% | 1,890 | 118 |
| `src/tilesets/` | 55.0% | 80 | 36 |

### Backend lowest-covered modules (2026-08-23, unverified)

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

At that measurement, 8 of 123 measured modules sat under the 85% file-level figure and
every package rollup cleared the gate.

### Frontend directory rollups (2026-08-23, unverified)

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

### Frontend lowest-covered files (2026-08-23, unverified)

| File | Stmts | Branch | Funcs | Notes |
|---|---|---|---|---|
| `src/api/socketClient.js` | 73.3% | 50% | 50% | Lowest in the tree — socket reconnection edge paths |
| `src/pages/GamePage.jsx` | 95.3% | 89.7% | 87.5% |  |
| `src/hooks/useEventManager.js` | 96.8% | 85.8% | 100% |  |
| `src/components/Battlefield.jsx` | 97.6% | 96.5% | 100% |  |
| `src/components/BattlefieldGrid.jsx` | 97.6% | 84.4% | 100% |  |
| `src/components/DefeatDialog.jsx` | 97.9% | 92.9% | 100% |  |
| `src/components/EventDialog.jsx` | 98.4% | 92.5% | 100% |  |
| `src/components/BaseDialog.jsx` | 98.6% | 91.0% | 100% | Escape/focus-trap rework — new branches |
| `src/hooks/useCombatSocket.js` | 98.7% | 90.6% | 100% |  |
| `src/components/BookReaderDialog.jsx` | 98.7% | 96.6% | 100% |  |

Branch coverage was the tight margin at 95.11% against a 95% gate; `socketClient.js` and
`useEventManager.js` were the two files most worth padding it with.

## Regenerating this dashboard

```bash
python -m pytest --cov=src --cov=ai --cov-report=term-missing -q -p no:cacheprovider
cd frontend && npm test -- --run --coverage
```

Update the test-count table, the "measured" dates, and the rollup/lowest-covered lists
from the fresh output — then move the percentage section back out of "NOT measured".
Do **not** copy the numbers into `CLAUDE.md`; it links here on purpose.

Add `--cov-report=html` (backend, → `htmlcov/index.html`) or open
`frontend/coverage/index.html` for a browsable per-line report. Neither is checked in:
a generated HTML report in `docs/` goes stale silently and cannot be diffed.

**Backend exclusions** (`pytest.ini`): `tests/api/`, `tests/broken/`, `tests/uat/`,
`tests/integration/`. **Frontend**: all of `src/**/*.{js,jsx}` except `src/main.jsx` and
`src/test/**`.

## FAQ

**Q: Why is `src/story/` (and `src/tilesets/`) coverage lower than everything else?**
A: Narrative and map-placement content is intentionally lower-coverage — story paths
branch heavily on player choice and state, and testing every branch has poor ROI versus
testing the mechanics (combat, inventory, movement, saves) those branches call into. The
engine code those chapters call is itself well-covered.

**Q: What happens if coverage drops on a PR?**
A: `--cov-fail-under=85` fails the backend job outright; the frontend `vite.config.js`
thresholds fail the same way. Either add tests to restore coverage or, rarely, get a
maintainer exception.
