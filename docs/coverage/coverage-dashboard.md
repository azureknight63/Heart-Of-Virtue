# Test Coverage Dashboard

**Last measured:** 2026-09-02 on `claude/readme-update-nvkwt7`

## Current State

| Layer | Coverage | CI minimum | Tests | Status |
|-------|----------|-----------|-------|--------|
| **Backend (Python)** | **96%** (23,582 / 24,448 statements) | 85% | 10,419 passed, 1 xfailed, 0 failed | 🟢 11 points of headroom |
| **Frontend (React)** | **99.46%** lines / ~95.3% branches | 95% (all four metrics) | 2,664 passed across 116 files | 🟡 Passing, but branch margin is thin |

Both suites are green with zero failures and zero skips.

> **Watch the frontend branch metric.** Lines, statements, and functions all sit
> comfortably above their thresholds, but *branch* coverage measured 95.29% and
> 95.27% on two consecutive runs of identical source — roughly a quarter-point of
> headroom over the 95% floor, with run-to-run variance in the v8 provider large
> enough to matter. A single new unbranched-but-untested path can turn CI red.
> Adding branch coverage in `src/api/` (96.72%) and `src/pages/` (92.50%) is the
> cheapest way to buy margin.

> **Historical note.** Through mid-2026 this dashboard tracked a backend coverage
> push from 51% toward a 60% target. That effort completed and substantially
> overshot: backend coverage is now 96% against an 85% CI floor. The
> point-in-time reports from that campaign (`COVERAGE_REPORT.md`,
> `COVERAGE_AT_A_GLANCE.md`, `TESTING_ACTION_PLAN.md`) have moved to
> [`docs/archive/`](../archive/) — their "URGENT" and "CRITICAL" gap lists
> describe a codebase state that no longer exists. This file is the single live
> coverage document.

## How to reproduce these numbers

### Backend (pytest)

```bash
python -m pytest --cov=src --cov=ai --cov-report=term-missing
```

Use `python -m pytest`, never bare `pytest` — the virtualenv may not expose the
`pytest` binary on PATH, which causes silent import failures. Install
`requirements-dev.txt` first; a partial install (missing `pytest-asyncio`, for
example) produces dozens of spurious failures that look like real regressions.

`pytest.ini` sets `-n auto --dist loadfile`, so the suite runs in parallel across
cores (~100s wall clock). Pass `-n0` when debugging a single test.

**Excluded from the default run** (`norecursedirs`): `tests/api`, `tests/broken`,
`tests/uat`, `tests/integration`. `testpaths = tests` restricts collection to the
`tests/` tree, which also structurally prevents stray rootdir scripts from being
collected.

For an HTML report:

```bash
python -m pytest --cov=src --cov=ai --cov-report=html
# open htmlcov/index.html
```

`htmlcov/` is gitignored — generated reports are not committed to this directory.

### Frontend (vitest)

```bash
cd frontend && npm test -- --run --coverage
# open frontend/coverage/index.html
```

Thresholds are enforced by `coverage.thresholds` in `frontend/vite.config.js`
(95% lines, statements, functions, and branches); the run fails below any of them.
Coverage includes `frontend/src/**/*.{js,jsx}` and excludes `frontend/src/main.jsx` and `frontend/src/test/**`.

## Backend coverage by module

Aggregated from the run above. Percentages are statement coverage.

| Module | Statements | Coverage |
|--------|-----------:|---------:|
| `src/moves/` | 5,032 | 98% |
| `src/npc/` | 2,512 | 96% |
| `src/api/services/` | 2,486 | 96% |
| `src/api/` (app, adapters, schemas, utils) | 2,248 | 97% |
| `src/story/` | 1,890 | 95% |
| `src/api/routes/` | 1,537 | 93% |
| `src/items.py` | 1,229 | 99% |
| `ai/` | 1,171 | 99% |
| `src/api/serializers/` | 861 | 98% |
| `src/objects.py` | 787 | 87% |
| `src/player/` | 576 | 97% |
| `src/functions.py` | 555 | 98% |
| `src/enchant_tables.py` | 400 | 100% |
| `src/states.py` | 359 | 99% |
| `src/positions.py` | 334 | 99% |
| `src/universe.py` | 298 | 99% |
| `src/config_manager.py` | 249 | 98% |
| `src/tiles.py` | 203 | 93% |
| `src/map_placeholders.py` | 187 | 86% |
| `src/secure_pickle.py` | 176 | 97% |
| `src/save_format.py` | 163 | 100% |
| `src/inventory_utils.py` | 158 | 93% |
| `src/events.py` | 150 | 87% |
| `src/narration.py` | 117 | 100% |
| `src/tilesets/` | 80 | 58% |

26 of 98 backend files with 20+ statements are at 100%.

### Lowest-coverage backend files

These are the remaining gaps, not blockers — every one sits above the 85% CI floor
in aggregate.

| File | Statements | Missed | Coverage |
|------|-----------:|-------:|---------:|
| `src/tilesets/grondelith_mineral_pools.py` | 73 | 34 | 53% |
| `src/api/routes/combat.py` | 110 | 29 | 74% |
| `src/api/routes/player.py` | 110 | 24 | 78% |
| `src/genericng.py` | 44 | 9 | 80% |
| `src/api/utils/log_cleanup.py` | 104 | 20 | 81% |
| `src/player/_movement.py` | 51 | 9 | 82% |
| `src/story/ch03.py` | 500 | 78 | 84% |
| `src/map_placeholders.py` | 187 | 26 | 86% |
| `src/events.py` | 150 | 19 | 87% |
| `src/objects.py` | 787 | 104 | 87% |

Note that `src/story/` is at 95% overall. Earlier revisions of this dashboard and
of CLAUDE.md described narrative code as intentionally low-coverage (18-21%); that
is no longer true and should not be cited as a reason to skip story tests.

## Frontend coverage by directory

| Directory | Lines | Branches | Functions |
|-----------|------:|---------:|----------:|
| `frontend/src/` (root) | 100% | 100% | 100% |
| `frontend/src/components/` | 99.57% | 95.60% | 99.34% |
| `frontend/src/hooks/` | 99.31% | 95.11% | 97.67% |
| `frontend/src/utils/` | 99.84% | 94.58% | 100% |
| `frontend/src/context/` | 100% | 99.13% | 100% |
| `frontend/src/pages/` | 98.40% | 92.50% | 90.62% |
| `frontend/src/api/` | 95.81% | 96.72% | 93.18% |
| `frontend/src/data/` | 100% | 100% | 100% |
| `frontend/src/styles/` | 100% | 100% | 100% |
| **All files** | **99.46%** | **~95.3%** | **98%** |

### Lowest-coverage frontend files

Branches are listed alongside lines because branch coverage is the metric with the
thinnest margin over its threshold.

| File | Lines | Branches |
|------|------:|---------:|
| `frontend/src/api/socketClient.js` | 71.42% | 50.00% |
| `frontend/src/pages/GamePage.jsx` | 95.26% | 89.61% |
| `frontend/src/utils/featureFlags.js` | 96.89% | 86.84% |
| `frontend/src/hooks/useEventManager.js` | 96.97% | 86.17% |
| `frontend/src/components/DefeatDialog.jsx` | 97.94% | 93.02% |
| `frontend/src/components/Battlefield.jsx` | 98.08% | 97.93% |
| `frontend/src/components/LeftPanel.jsx` | 98.18% | 95.01% |
| `frontend/src/hooks/useCombatSocket.js` | 98.57% | 90.62% |

`socketClient.js` is the one file meaningfully below the project norm — 71% lines
and 50% branches, because its reconnection and error paths are hard to exercise in
jsdom. It is also the single cheapest place to buy back branch-coverage margin.

## CI enforcement

| Workflow | Enforces |
|----------|----------|
| [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) | Backend pytest + `flake8 --extend-ignore=E501 src/`; frontend vitest. Runs on push to `master`/`web-api` and on PRs to `master`. |
| [`.github/workflows/test-coverage.yml`](../../.github/workflows/test-coverage.yml) | Backend coverage via `--cov-fail-under=85`; frontend `npm test -- --run --coverage` (thresholds from `vite.config.js`). |
| [`.github/workflows/bug-hunt.yml`](../../.github/workflows/bug-hunt.yml) | Automated bug-hunt harness. |

CI runs Python 3.11 and Node 22. `.python-version` pins 3.13 for local
development, so keep backend code compatible with 3.11.

## README badges — manually maintained

The two coverage badges at the top of the root [README.md](../../README.md) are
**static shields.io URLs with the percentage hardcoded**. Nothing updates them
automatically. This is how the previous badge sat at 47% long after real coverage
had reached 96%.

When you re-measure, update all three places together:

1. `README.md` — the `backend--coverage-<N>%25` and `frontend--coverage-<N>%25` badge URLs
2. `README.md` — the Coverage table under "Development"
3. This file — the Current State table and the per-module breakdowns

The CI badge is a real GitHub Actions status badge and *is* self-updating; only the
coverage ones are manual.

`.github/workflows/test-coverage.yml` uploads to Codecov and posts a computed badge as a PR comment,
so per-PR figures are automatic even though the README's are not. If the Codecov
project is active, replacing the static badges with Codecov's dynamic badge would
remove this failure mode entirely.

## Guidance

**Do not add blanket skips.** The suite previously carried 565 skips, roughly 517
of them whole-file or whole-class `pytestmark = pytest.mark.skip` with reasons like
"coverage requirements already met" and "test isolation issues". Those reasons were
without exception false — the tests were failing on stale API signatures,
mislabelled story flags, an unrestored class attribute, and one infinite loop. A
blanket skip hides defects for years and the count only ever grows. The suite now
has zero skips; keep it that way.

**Where new tests go.** Full-app integration tests that build a real
session/universe (via `create_app(TestingConfig)` + `/api/test/session`) belong in
`tests/api/`, which is excluded from the default run: creating a real session
mutates module-level item and merchant registries and pollutes downstream shop and
spawn tests. Other route tests avoid this by using a mocked `session_manager`.

**Contract tests.** Three tests guard this codebase's recurring failure modes and
should be extended rather than worked around:

- `tests/test_wire_field_contract.py` — builds payloads from real engine objects and
  asserts the frontend's declared field list is a subset of what the API actually
  emits. Wire-field-name drift is this project's dominant bug class, and it is
  invisible to ordinary tests because fixtures encode the same wrong name as the
  component.
- `tests/test_move_categories_ui_contract.py` — AST-parses `src/moves/` and fails if
  a castable move category maps to no UI group.
- `tests/test_move_web_animations.py` — asserts every castable move declares a
  `web_animation` matching a key in `frontend/src/utils/animationConfigs.js`.

## FAQ

**Can I run coverage locally without CI?** Yes — see "How to reproduce these
numbers" above. Both commands work offline.

**What happens if coverage drops on a PR?** `test-coverage.yml` fails the run.
Either add tests to restore coverage, or discuss an exception with the maintainer.

**Why does a full run show failures on my machine when CI is green?** Almost always
an incomplete dependency install. Run `pip install -r requirements-dev.txt` and
re-run. A partial install missing `pytest-asyncio` alone accounts for ~95 spurious
failures.

## Resources

- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Vitest coverage guide](https://vitest.dev/guide/coverage)
- Project testing conventions: see `CLAUDE.md`
