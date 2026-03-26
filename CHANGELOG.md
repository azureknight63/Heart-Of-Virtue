# Changelog

All notable changes to Heart of Virtue are documented here.

## [0.0.1.0] - 2026-03-26

### Added
- **In-game feedback form** — players can submit bug reports, feature requests, and general feedback without leaving the game. Accessible via the Feedback button in the LeftPanel header.
  - Bug report form: steps to reproduce, expected/actual behavior, severity (low/medium/high)
  - Feature request form: description + use case
  - General feedback form: message + optional 5-dimension star ratings (story, combat, audio, visuals, difficulty)
  - Anonymous toggle: omits the player's username from the GitHub issue body
  - Submissions create real GitHub issues on `azureknight63/heart-of-virtue` via the GitHub REST API
  - Graceful 503 degradation when `GITHUB_TOKEN` is not configured — game loop unaffected
- **Beta-mode feedback button glow** — animated yellow shimmering border on the Feedback button, gated behind `VITE_BETA_MODE=true` env var. Easy to disable for production builds.
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
