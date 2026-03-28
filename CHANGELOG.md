# Changelog

All notable changes to Heart of Virtue will be documented in this file.

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
