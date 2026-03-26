# Changelog

All notable changes to Heart of Virtue will be documented in this file.

## [0.0.3.0] - 2026-03-26

### Fixed
- **Deployment: Vite base path** — API client base URL, audio BGM/SFX paths, and hero panel image now all respect `BASE_URL` for subpath deployments (e.g. `/games/HeartOfVirtue/`). Used `getAssetPath()` helper for robust trailing-slash handling.
- **Deployment: Procfile** — removed `--worker-class eventlet` from gunicorn invocation (eventlet removed from requirements); threading mode with long-polling is correct for single-player.
- **Deployment: logout redirect** — `window.location.href` was building `${BASE_URL}login` which 404s on subpath deployments; hardcoded to `/login` which React Router always serves.
- **Combat: wave spawn positions** — `initialize_combat_positions()` was unconditionally overwriting `combat_position` on all combatants including already-positioned ones; now passes only newly-spawned enemies without existing positions.
- **Combat: flee loop** — fixed infinite loop when flee succeeds; added fatigue guard.
- **Combat: exception recovery** — `_execute_move()` failure no longer leaves adapter in corrupted state; falls back to empty `available_options`.
- **Combat: consecutive defeat dialog** — defeat fallback event `id` changed from literal `"defeat"` to `uuid4()` so `sessionStorage` de-duplication doesn't suppress a second consecutive defeat.
- **Combat: debug log flood** — 9× `logger.info/warning("DEBUG: ...")` calls demoted to `logger.debug(...)`.
- **Story: NPCSpawnerEvent dict class name** — added `.strip()` to class name extraction from deserialized dicts; whitespace was causing `AttributeError` on lookup.
- **Story: NPCSpawnerEvent blocking event queue** — spawner events were incorrectly holding the queue; fixed.
- **NPC: Rock Rumbler AI** — fixed stop-attacking regression at high beat counts; added `getattr` guard on `m.category` for partial Move init.
- **Frontend: post-login redirect** — switched from `window.location.href` to React Router `navigate('/menu')` to avoid full page reloads.
- **Frontend: sessionStorage persistence for lastEndStateId** — prevents duplicate victory/defeat dialog on React re-mount.
- **Security: auth exception masking** — restored masked error responses, admin endpoint guards, and split requirements files.
- **Tests: useApi logout** — updated assertion to match `/login` redirect.
- **Tests: LoginPage navigate mock** — switched `window.location.href` assertions to `mockNavigate` after login now uses React Router.

### Changed
- `wsgi.py` docstring updated to document threading mode and remove eventlet references.
- Ch01 story: added `Ch01GorranCautionJunction`, `Ch01GorranMarkings`, `Ch01GorranDarkChamber` narrative beats (from master merge).

## [0.0.2.0] - 2026-03-26

### Fixed
- **Duplicate Gorran NPC bug** — removed `NPCSpawnerEvent` from tile (2,1) in Verdette Caverns. `recall_friends()` already moves the ally Gorran there on every game loop tick before `evaluate_events()` runs; the spawner was creating a second non-ally Gorran instance that would corrupt the combat roster.
- **Tile description voice** — removed a Jean-POV sentence from the (3,6) ceiling-collapse description and reworded the (1,4) cross-carving description to comply with the "descriptions are permanent" principle.

### Changed
- **Gorran traversal events escalate toward the Lurker** — the three Chapter 1 Gorran events now build a genuine arc:
  - `(4,3)` Caution Junction: subtle — Gorran slows, reads the violence-marked floor, raises a hand briefly
  - `(5,6)` Crystal Markings: building — his touch lingers on the Golemite crystal; when he moves on, his gaze stays ahead
  - `(7,6)` Dark Chamber: pronounced — full stop, deliberate stillness, a firm stay signal before the Lurker encounter

### Tests
- Added `tests/test_ch01_gorran_traversal_events.py` — 14 unit tests covering instantiation, immediate fire, output line count, and minimum sleep duration for all three events
- Added `tests/test_verdette_caverns_map.py` — 4 structural regression tests confirming the (2,1) spawner is absent and all three traversal events are correctly placed

## [0.0.1.0] - 2026-03-26

### Added
- **In-game feedback form** — players can submit bug reports, feature requests, and general feedback without leaving the game. Accessible via the Feedback button in the LeftPanel header.
  - Bug report form: steps to reproduce, expected/actual behavior, severity (low/medium/high)
  - Feature request form: description + use case
  - General feedback form: message + optional 5-dimension star ratings (story, combat, audio, visuals, difficulty)
  - Anonymous toggle: omits the player's username from the GitHub issue body
  - Submissions create real GitHub issues on `azureknight63/heart-of-virtue` via the GitHub REST API
  - Graceful 503 degradation when `GITHUB_TOKEN` is not configured — game loop unaffected
- **Beta-mode feedback button glow** — animated cyan shimmering border on the Feedback button, gated behind `VITE_BETA_MODE=true` env var. Easy to disable for production builds.
- `GITHUB_TOKEN` documented in `.env.example` with setup instructions

### Security / Hardening
- Per-session rate limit (10 submissions/hour) to prevent GitHub token exhaustion
- Player usernames sanitized of Markdown metacharacters before embedding in issue body
- Title length capped at 256 characters (GitHub API limit)
- Field values truncated at 2000 characters each
- Non-dict `fields` payload guarded against `AttributeError` crash
- GitHub API error responses no longer logged in full (avoids leaking API response data)
- GitHub API timeout reduced 10s → 5s to limit Gunicorn worker starvation
- Double-submit guard via `useRef` for rapid-click / slow-network races

## [0.0.0.1] - 2026-03-26

### Fixed
- Fixed 1,359 flake8 linting errors (41.6% reduction)
  - Auto-formatted 83 files with black (line length 79)
  - Removed 31 unused imports across the codebase
  - Fixed exception handling patterns (unused exception variables)
  - Fixed f-strings missing placeholders
  - Removed 11 unused variable assignments

### Changed
- Improved code quality and linting compliance
