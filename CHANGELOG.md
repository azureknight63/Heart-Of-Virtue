# Changelog

All notable changes to Heart of Virtue will be documented in this file.

## [0.0.5.0] - 2026-04-13

### Added
- **Eastern Descent map**: New 35-tile environment for Chapter 3 spanning 5 zones (Gate Approach, Upper Boulder Field, Deep Labyrinth, Lower Slope, Nomad Camp) with descriptive prose and environmental storytelling
- **TalusHound enemy class**: Pack hunter with pack-aware tactical AI — flanking and coordinated strikes in groups, hit-and-run tactics when solo
- **ScarpAdder enemy class**: Ambush serpent with venom attacks and earth affinity, solitary and patient in strategy
- **Mara full combatant upgrade**: Scavenger companion with weapon-switching tactics (bow 8–25 range for precision, dagger 0–3 range for close quarters), tactical positioning, and observant dialogue
- **Devet Friend NPC**: Camp cook, older and unhurried, with gentle dialogue and presence at the nomad camp
- **Liss Friend NPC**: Young, curious, observant (age 9), present at camp's edge with inquisitive character-driven dialogue
- **Chapter 3 story events**: GorranGestureEvent (Gorran touches the sealed gate on exit from Grondia), EasternRoadTurnbackEvent (Jean reaches eastern road stub, pulled by desire to escape, then turned back by Gorran's presence)
- **New consumable items**: IronRation (HP +30, travel provisions), Bitterroot (HP +60, mountain herb), MerchantJournalFragment (readable lore item with creature observations and references to Mara)
- **Nomad camp resident NPCs**: NomadCamper, NomadScout, NomadTrader — background population with gesture-based interaction

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
