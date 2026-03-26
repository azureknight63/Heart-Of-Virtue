# Changelog

All notable changes to Heart of Virtue will be documented in this file.

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
