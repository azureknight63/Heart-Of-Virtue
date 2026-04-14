# Changelog

All notable changes to Heart of Virtue will be documented in this file.

## [0.0.4.1] - 2026-04-03

### Fixed
- **Combat API — Event Dialog blocked after post-combat events**: `_handle_victory()` now always called when enemies are defeated, even if post-combat events fire. Frontend now receives both `end_state` (victory) and `events_triggered` correctly, fixing the delay where the Event Dialog wouldn't appear until a follow-up action.
- **Combat API — available moves filtered for suggestions**: Combat suggestions now exclude moves with no viable targets, preventing AI from suggesting attacks that cannot execute.
- **Dark Grotto — exits whitelist from JSON not enforced**: Wall Depression now correctly unlocks the eastward passage when interacted with (NW/SW exit whitelist bug fixed).
- **Dark Grotto — multiple map bugs**: Fixed 14 Dark Grotto issues including wall passages, NPC spawning, tile descriptions, and visual inconsistencies.
- **Inventory — game-logic rejection messages**: Now show narrative messages without the ✗ prefix for better UX feedback on failed item usage.
- **Inventory — ValueError handling**: Return 400 Bad Request instead of 500 Server Error when item usage raises ValueError.
- **Event system — tile resolution**: `process_event_input` now correctly resolves tile coordinates from session payload, fixing events that reference `self.tile`.
- **Game initialization — entry-point events**: Starting tile events now fire on initial game load, fixing intro event sequences that don't trigger when entering a map for the first time.
- **Audio — concurrent BGM switches**: `playSting` now guards the restore logic against race conditions when the player switches tracks during a sting, preventing crashed audio.
- **API — backend errors in EventDialog**: Backend errors and diagnostic output now filtered from event messages sent to the frontend.

### Changed
- Removed "File " prefix regression that appeared in some event messages.
- Event error handling now logs exceptions instead of silently swallowing them.
- Map-entry spawners (NPCSpawnerEvent) now consistently fire during player movement, matching terminal game loop behavior.

### Added
- Audio context `playSting` function for one-shot sting effects (fanfare, etc.) with automatic BGM restoration.
- SFX audio object reference tracking to prevent dangling audio elements.
- Regression tests for inventory error handling (400 vs 500 responses).
- ItemDetailDialog `onBack` prop for navigation back to inventory list after actions.

### Security
- **axios 1.13.5 → 1.15.0**: Updated axios to patch CRITICAL security vulnerability in HTTP client.

## [0.0.4.0] - 2026-03-28

### Fixed
- **Combat API — awaiting_input stale after victory**: `_handle_victory()` now sets `awaiting_input=False` so the API stops returning "awaiting input" once the fight ends.
- **Combat API — awaiting_input stale after defeat**: Defeat path in `_execute_move()` now sets `awaiting_input=False`, matching the victory path.
- **Combat API — proximity gap on reinforcement spawn**: `_synchronize_distances()` is called immediately after new enemies are position-initialized so `Attack.viable()` can target them on the next beat.
- **Combat API — current_stage deadlock after mid-combat event**: When a combat event fires mid-beat, the in-progress move is reset to stage 0 and move selection is refreshed, preventing a permanent deadlock where the interrupted move could never be re-selected.
- **Combat API — pending_move_index not cleared on wave transition**: Clears stale pending move index when a new combat wave is detected.
- **Game Engine — NPCSpawnerEvent tile fallback**: `evaluate_for_map_entry` now falls back to `self.tile` when `spawn_tile` is `None` (set during JSON deserialization), fixing Lurker and other map-entry spawners in the API.
- **Game Engine — game_tick_events not called on player move**: `move_player` in `GameService` now calls `player.universe.game_tick_events()` so map-entry spawners (NPCSpawnerEvent) fire correctly, matching the terminal game loop.
- **Frontend — login flow broken by per-instance auth state**: Restored `AuthContext.jsx` with shared React context so `App.jsx` and `LoginPage.jsx` share the same `isAuthenticated` state. Previously, each component had an independent hook instance and login never navigated away from `/login`.
- **Frontend — logout URL ignored subpath deployment**: `AuthContext.logout()` now uses `import.meta.env.BASE_URL + 'login'` for the redirect, matching the app's `basename="/games/HeartOfVirtue"`.

### Changed
- Default API starting map changed from `"default"` to `"dark-grotto"` to match the actual game world.
- `game_tick_events` failures now emit a `logger.warning` instead of silently swallowing the exception.

### Added
- Test-only `/api/test/heal` endpoint (TESTING mode only) to restore player HP/fatigue mid-QA run.
- 9 regression tests in `tests/test_beta_qa_regressions.py` covering all five bugs found during beta QA.

## [0.0.3.2] - 2026-03-28

### Added
- "Main Menu" navigation button in `AccountDialog`.

### Changed
- Centralized frontend authentication state using `AuthContext` to prevent fragmented rendering gaps.
- Updated login route to drop straight into `/game` default path over `/menu`.
- Modified subpath-aware navigation in logout action.

## [0.0.3.1] - 2026-03-27

### Changed
- CI: removed flake8 line-length (E501) requirement — line length is Black's domain, not flake8's
- CI: suppressed E203 (slice spacing) — Black intentionally formats slices with spaces, creating a known Black/flake8 conflict
- Auto-formatted all `src/` files with Black (whitespace-only changes)
- Resolved all flake8 violations in `src/`: unused imports, dead variable assignments, bare excepts, lambda assignments, ambiguous variable names, and star imports replaced with explicit imports

## [0.0.3.0] - 2026-03-27

### Added
- Terms of Service & Privacy Policy modal on the login/registration screen
- `TermsOfServiceModal` component with tabbed navigation (Terms of Service / Privacy Policy)
- ToS covers: account rules, AI data processing disclosure (OpenAI/OpenRouter), freemium payment model notice, IP licensing, self-service account deletion, US governing law, and children's notice
- Privacy Policy covers: data collection (username, encrypted email, Argon2id hash, save data), AI data transmission, email opt-in/unsubscribe, planned anonymous analytics (pre-disclosed), third-party services (Turso, OpenAI), and self-service deletion without contacting support

### Tests
- 4 unit tests for `TermsOfServiceModal` (default tab, tab switching, onClose callback)
- 3 unit tests in `LoginPage.test.jsx` for ToS link render, modal open, and modal close

## [1.0.1] - 2026-03-26

### Added
- Beta end dialog shown after defeating the Lurker in Verdette Caverns — thanks the tester and offers to send feedback or continue exploring
- `BetaEndDialog` component (no close button; forces an explicit choice)
- `FeedbackDialog` now accepts `initialType` prop to preset the active tab (e.g. `"general"`)
- `_handle_victory()` in `ApiCombatAdapter` sets `beta_end: true` on `combat_end_summary` when the Lurker is defeated on the correct tile

### Changed
- `AfterDefeatingLurker.process()` replaced with a no-op for beta — story continuation to Grondia and passageway spawn are disabled; the Dark Grotto teleport remains functional

### Tests
- 4 backend tests covering `beta_end` detection (positive + 3 negative/edge cases)
- 3 frontend tests for `BetaEndDialog` (render + both button callbacks)
- 3 frontend tests for `FeedbackDialog.initialType` prop (bug/general/feature tabs)
- 1 integration test in `GamePage.test.jsx` — victory dialog with `beta_end=True` transitions to `BetaEndDialog`
