# Heart of Virtue — Documentation

Technical documentation for the Heart of Virtue project. The game is played
entirely through the web app (Flask REST API + React SPA); the terminal/CLI play
mode has been removed.

Start with the root [README.md](../README.md) for setup and a project overview.

## Core Documentation

| Document | Contents |
|---|---|
| [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md) | System architecture and component relationships |
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | Complete REST API reference with all endpoints |
| [BACKEND_API_ARCHITECTURE.md](BACKEND_API_ARCHITECTURE.md) | Backend API internals |
| [BACKEND_API_INTEGRATION.md](BACKEND_API_INTEGRATION.md) | API integration guide and testing |
| [FRONTEND_DOCUMENTATION.md](FRONTEND_DOCUMENTATION.md) | Frontend architecture and component guide |
| [LOCAL_DEV_SETUP.md](LOCAL_DEV_SETUP.md) | Step-by-step local setup for backend and frontend |

## Deployment & Testing

| Document | Contents |
|---|---|
| [DEPLOYMENT_ROADMAP.md](DEPLOYMENT_ROADMAP.md) | Deployment planning and procedures |
| [coverage/coverage-dashboard.md](coverage/coverage-dashboard.md) | Live coverage figures, per-module breakdown, CI enforcement |

## Feature Documentation

| Document | Contents |
|---|---|
| [QUEST_CHAINS_INTEGRATION_EXAMPLES.md](QUEST_CHAINS_INTEGRATION_EXAMPLES.md) | Quest system integration examples |
| [TILE_CACHING.md](TILE_CACHING.md) | Tile caching implementation |
| [combat-map-animation.md](combat-map-animation.md) | Combat and map animation system |
| [book_pagination.md](book_pagination.md) | Book pagination feature |

## Subdirectories

| Directory | Contents |
|---|---|
| [coverage/](coverage/) | Test coverage dashboard (the single live coverage document) |
| [development/](development/) | Design plans, acceptance-test plans, UI mockups, open decisions |
| [lore/](lore/) | World-building: character profiles, creatures, enemies, environments, story |
| [concept-art/](concept-art/) | Character and location concept art (PNG) |
| [qa/](qa/) and [qa-reports/](qa-reports/) | QA session reports |
| [ui-mockups/](ui-mockups/) | Standalone HTML UI mockups |
| [archive/](archive/) | Historical documentation: completed milestones, superseded plans, point-in-time reports. Kept for reference, no longer maintained — treat any figures there as stale. |

### Lore at a glance

`lore/` holds 55 documents across `character-profiles/` (16), `environments/` (18,
including map design documents and audit reports), `enemies/` (12), `story/` (3),
and `creatures/` (2), plus standalone documents on Jean Claire's backstory.

Story, lore, and creative assets are licensed CC BY-NC-ND 4.0 — see
[LICENSE-ASSETS](../LICENSE-ASSETS).

## Finding Documentation

| I want to… | Read |
|---|---|
| Get the app running locally | [LOCAL_DEV_SETUP.md](LOCAL_DEV_SETUP.md), then the root [README.md](../README.md) |
| Understand the system end to end | [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md) |
| Call or extend the API | [API_DOCUMENTATION.md](API_DOCUMENTATION.md), [BACKEND_API_ARCHITECTURE.md](BACKEND_API_ARCHITECTURE.md) |
| Work on the React client | [FRONTEND_DOCUMENTATION.md](FRONTEND_DOCUMENTATION.md), [frontend/README.md](../frontend/README.md) |
| Check test coverage or CI rules | [coverage/coverage-dashboard.md](coverage/coverage-dashboard.md) |
| Deploy | [DEPLOYMENT_ROADMAP.md](DEPLOYMENT_ROADMAP.md) |
| Understand save-file security | [SECURITY.md](../SECURITY.md) |
| Look up world or character canon | [lore/](lore/) |
| Find historical context | [archive/](archive/) |

Project-wide conventions, architectural rules, and known gotchas live in
[CLAUDE.md](../CLAUDE.md) at the repo root.
