# Heart of Virtue — CLAUDE.md

Text-based adventure RPG (retro terminal aesthetic) following the crusader Jean Claire. Played **entirely via the web app**: a Flask REST/Socket.IO API wraps the Python game engine and a React SPA renders it. The terminal play mode is gone (history in `docs/development/engine-history.md`).

**The Python engine is the source of truth.** `src/api/` adapts engine state to JSON; it never reimplements game logic. Engine output flows through the narration sink (`src/narration.py`) as structured `{text, color, type}` messages — nothing scrapes stdout.

Deep, path-specific guidance lives in `.claude/rules/*.md` and loads automatically when you touch matching files (API layer, combat engine, frontend, story/content, saves, testing, audio, LLM prompts). Project skills in `.claude/skills/` self-describe — invoke them instead of re-deriving their workflows (table at the end).

## Design pillars — the decision filter

Derived from `docs/lore/`, `src/resources/outline.md`, and the map-design principles (edit if they misstate the vision). A change that serves none of these is scope creep — not because it's bad, but because it's not this game.

1. **Lore first, mechanics second.** `docs/lore/` is canon; `src/resources/outline.md` is the chapter spine. Check them before writing dialogue, naming anything, or placing content. Contradictions are bugs — `/narrative-review` finds them.
2. **Jean's arc carries the story.** Chapters follow Jean's grief/faith journey; story beats anchor to tiles and events, not detached cutscenes.
3. **Tactical, legible combat.** Turn-based and positional (distance/facing/flanking); every number is explainable and the UI can show every roll. Fairness over spectacle: no unwarned deaths.
4. **Exploration is the UI.** Descriptions, objects, and NPC text teach the rules. Puzzles may look like dead ends, but every puzzle is hinted in-text.
5. **Retro terminal, web-native, mobile-playable.** Lime/cyan/orange on near-black; 44px touch targets; nothing conveyed by color alone.
6. **Ship the game.** Harden the existing vertical slice before adding systems. A new system needs a pillar, a test, and a place in the chapter spine.

## Stack

Python 3.11 engine · Flask 3.1 + Flask-SocketIO API · React 18 + Vite + Tailwind (+ react-three-fiber battlefield) · LibSQL/Turso · pytest / Vitest · black (88) + flake8 (`--extend-ignore=E501`) · OpenRouter/Groq/Cerebras/Ollama for NPC chat and Mynx ambient behaviour (`MYNX_LLM_ENABLED`; see `.env.example`).

## Layout — only the non-obvious parts

- `src/` engine: `moves/` (combat abilities; `_base.py` owns `Move`, `PassiveMove`, to-hit), `player/` and `npc/` (packages; both inherit `combatant.py`), `states.py`, `events.py`, `story/ch0N.py`, `tiles.py`/`universe.py`, `narration.py`, `secure_pickle.py`/`save_format.py`, `resources/maps/*.json`.
- `src/api/`: `app.py` (`create_app`), `combat_adapter.py` (engine→JSON bridge), `routes/`, `services/` (`game_service`, `session_manager`), `serializers/`, `schemas/`, `routes/debug.py` (TESTING-only).
- `frontend/src/`: `pages/`, `components/`, `hooks/` (`useApi`, `useCombat`, …), `utils/` (contracts: `animationConfigs.js`, `categories.js`, `combatBeatSchema.js`), `styles/theme.js` (design tokens), `data/changelog.js`.
- `tools/`: `run_api.py`, `bug_hunt.py` + `harness/scenarios/`, `inquisitor.py`, `*_fuzzer.py`, `audio_engine/` + `songs/`, `acceptance_test_generator.py`.
- `docs/`: `lore/` (canon), `development/` (plans, mockups, history), `coverage/`, `qa/`. Root `config_*.ini` are game configs for dev/test; `.env` from `.env.example` (never commit it).

## Running

```bash
python tools/run_api.py [config_dev.ini]      # API on :5000; arg > CONFIG_FILE env > config_dev.ini
cd frontend && npm install && npm run dev     # SPA on :3000
.\tools\start_servers.ps1 [CONFIG_FILE]       # both, PowerShell
```

## Running Tests

```bash
python -m pytest -q                                   # backend default suite (excludes tests/api, tests/broken, tests/uat, tests/integration)
python -m pytest --cov=src --cov=ai --cov-report=term-missing --cov-fail-under=85 -q   # what CI enforces
cd frontend && npm test -- --run                      # frontend; add --coverage for the 95% thresholds in vite.config.js
flake8 --extend-ignore=E501 src/ && python -m black --check src/
python tools/bug_hunt.py [--scenario NAME] [--headless --output bugs.json]   # in-process API harness, 22 scenarios
python tools/inquisitor.py --headless --output tools/browser_findings.json   # real-browser QA; setup in docs/qa/inquisitor.md
```

- Always `python -m pytest`, never bare `pytest` — the venv may not expose the binary and bare runs fail silently on imports.
- **Full-app integration tests that build a real session/universe** (`create_app(TestingConfig)` + `/api/test/session`) belong in `tests/api/`, which is excluded from the default run: a real session mutates module-level item/merchant registries and pollutes downstream shop/spawn tests. Other route tests use a *mocked* `session_manager`.
- Coverage gates: backend ≥85% (CI), frontend ≥95% (`vite.config.js` thresholds). Measured 2026-08-23: backend 96% (7,671 tests), frontend 99.4% stmts / 95.1% branch (2,296 tests) — re-measure before quoting. Dashboard: `docs/coverage/coverage-dashboard.md`.
- Tests touching randomness must seed or patch `random` — the engine makes ~220 unseeded `random.*` calls (only `positions.py` seeds). Never assert on an unseeded roll.
- Mocks that stub an engine module imported as `import src.x as m` must patch both `sys.modules["src.x"]` *and* the `src` package attribute (see `_fake_engine_modules` in `tests/test_session_manager_coverage.py`); to pass an engine `isinstance`, set `mock.__class__` to the real class or build with `RealClass.__new__(RealClass)`.

## Test-Driven Development (Required)

**All changes to source code (`src/`, `ai/`, `frontend/src/`) follow TDD — test first, then implementation.**

1. **Red** — write a test that expresses the desired behavior (new feature) or reproduces the defect (bug fix). Run it and confirm it fails for the expected reason, not a typo, import error, or unrelated crash.
2. **Green** — write the smallest change that makes the test pass. Don't fix unrelated things in the same step.
3. **Refactor** — clean up with the suite green throughout, re-running after each change.
4. Before considering the task done, run the full relevant suite: `python -m pytest -q` (backend) and/or `cd frontend && npm test` (frontend).

**Bug fixes specifically**: the regression test must fail against the pre-fix code. A fix with no test that fails without it is not verified — it's a guess.

**Exceptions** (test-first doesn't apply, though testable changes still need coverage): pure documentation/comment edits, config-only changes (`.ini` files, static JSON data with no logic), generated/vendored files, and one-off scratch/repro scripts outside `src/`/`frontend/src/`/`ai/`. When in doubt, write the test first.

**Review-gate remediation is the one carve-out**: fixes applied by `/code-review` or `/code-scrubber` to land a finding don't need a preceding failing test, but they must leave the suite green, and if the fix changes behaviour it still needs a regression test before the gate passes.

This is enforced at review time by the Code Review Gate below — a change reported complete without a preceding failing test should be flagged, not waved through.

## Verification ladder — give yourself a check you can run

Pick the cheapest rung that can actually observe the change, run it, and show the output as evidence — don't assert success:
1. Unit and contract tests in `tests/` — the contract guards (`test_wire_field_contract.py`, `test_move_categories_ui_contract.py`, `test_move_web_animations.py`, `test_no_bare_local_imports.py`, `test_player_stat_derivations.py`) exist because mocks agreeing with mocks shipped five silent bugs.
2. `python tools/bug_hunt.py --scenario …` — the real API in-process (combat, events, shop, saves, NPC chat…). Add a scenario when you add a feature.
3. `/combat-test` against `config_combat_testing.ini` (arena table below); `python tools/<x>_fuzzer.py` for input hardening.
4. `python tools/inquisitor.py` or `/qa` — real browser; the only rung that sees JS/rendering bugs.
Balance or behaviour changes need rung 2 or 3, not just rung 1.

## Coding conventions

**Python** — snake_case/PascalCase; keep docstrings on public methods; don't add type annotations to files that don't already use them heavily; black 88; no `###DEBUG###` left behind; try/except with logging — prefer silent recovery over crashing the game loop. Conventional Commits (`feat(frontend):`, `fix(states):`, `refactor(backend):`).
- **All local imports use the canonical `src.` path** — `from src.items import Item`, `importlib.import_module("src.tiles")`, `patch("src.x.y")`. Bare names create a duplicate module object once `src/` is on `sys.path`, silently breaking `isinstance` and registries across the API/engine boundary. Enforced by `tests/test_no_bare_local_imports.py` and `tests/test_import_sync_production.py`. Persisted data (map JSON `__module__`, legacy pickles) stores bare names by contract — resolve via `functions.canonical_module_name()`.
- **Any new top-level `src/` module must be added to `LEGACY_BARE_MODULES` in `src/secure_pickle.py`** (also enforced by `test_no_bare_local_imports.py`).
- `narrate(*parts, color=None)` joins like `print`; color is keyword-only. `cprint(text, color)` keeps the positional signature.

**JavaScript/React** — camelCase/PascalCase; functional components only; stateful logic in custom hooks (no inline API calls in components); Tailwind utilities plus tokens from `styles/theme.js` (lime `#00ff88`, cyan `#00ccff`, orange `#ffaa00`, danger `#ff4444` on `#0a0a0a`).

## Architecture rules (gating in code review)

- Game logic lives in the engine (`src/`); `src/api/` adapts, never reimplements. About to re-derive a stat or roll in a route/serializer? Add a `GameService` method or call the engine helper instead.
- `CombatAdapter` (`src/api/combat_adapter.py`) is the sole engine→JSON bridge for combat; serialization changes go there.
- `Combatant` owns shared resistance/status-effect logic for `Player` and `NPC` — never duplicate it in a subclass.
- New passive moves inherit `PassiveMove` (`src/moves/_base.py`), not `Move`; subclasses supply only `name` and `description`.
- Every castable move declares `web_animation = "<key of ANIMATION_CONFIGS>"` (`frontend/src/utils/animationConfigs.js`); contract-tested by `tests/test_move_web_animations.py`.
- To-hit arithmetic lives only in `src/moves/_base.py` (`to_hit_chance` is the roll, `attacker_accuracy` the display rating). Term order is load-bearing and per-move bases/floors are not uniform — read `.claude/rules/combat-engine.md` before touching it.
- `combat_id` identifies a fight, not a call: minted once in `ApiCombatAdapter.initialize_combat`'s non-reinit branch so it survives wave/reinforcement reinits.
- **GameService patterns:** `GameService.__init__` is `pass` — there is no `self.universe`; use `self._story(player)` / `self._game_tick(player)`. Routes never reach into player internals (`getattr(player, …)`) — call `game_service.method(player)`. Attribute traps: `player.attack` is a method; `player.health`/`stamina`/`defense`/`accuracy`/`evasion` don't exist (HP is `player.hp`); `player.reputation` is absent until written — `getattr(player, 'reputation', {})` to read, `player.reputation = {}` before writing. **Cooldown timing trap:** cooldowns drain only during active combat beats — a drain on rest, world movement, or save/load silently corrupts move availability, so guard every drain call with an active-combat check.
- `/api/debug/*` (`routes/debug.py`) registers only under `app.config["TESTING"]`; never add a debug route outside that gate. Any new deserialization path goes through `src/secure_pickle.py`'s `SafeUnpickler`.

## Game-design rules (content and systems work)

- **Content goes where a data path exists**: maps/tiles/placements in `src/resources/maps/*.json` (`docs/development/map-authored-placeholder-schema.md`), loot in `loot_tables.py`, enchantments in `enchant_tables.py`, books in `src/resources/books/`, AI/combat toggles in `config_*.ini`. Story events in `src/story/ch0N.py` use the staged `say()`/`narrate()`/`begin_conversation()` protocol. Prose never lives in routes or serializers.
- **Tunables are named, centralized, and explained**: balance numbers sit on the move/item/NPC class or in config, never inline in the API; a commit that changes a number says why.
- **Descriptions are permanent**: tile text must stay true after NPCs die and items are taken — describe durable evidence (stains, claw marks, worn stone), never present-tense behaviour.
- **Fairness**: warn before lethal danger; every locked or hidden passage has an in-text hint; a dead end with an interactable is a puzzle, not a bug (QA section below).
- **Save compatibility is a feature**: persisted classes keep backward-compatible defaults (old saves must still load); format changes regenerate the allow-list manifest and get a fixture/fuzz run — `.claude/rules/saves-persistence.md`.
- **Accessibility**: state is never color-only (pair with icon/text); 44px touch targets; 16px inputs on mobile; readable line lengths in dialogue panels.

## Combat testing arena

`config_combat_testing.ini` is the single control surface for `/combat-test` (other agents edit it freely — never assert on its exact values in tests). Start the API with `CONFIG_FILE=config_combat_testing.ini` or `startmap`/`testmode`/`startposition` won't apply — the arena (`src/resources/maps/combat-testing-arena.json`) has no link to the main world. Roster and stats are driven through `/api/debug/*` (the Adjutant's parametrized ops).

| Tile | Name | Combatants | Purpose |
|---|---|---|---|
| (0,0) | Proving Grounds | The Adjutant (ally) | Staging; configure Jean and per-tile rosters |
| (1,0) | Fodder Pit | Slime + CaveBat | Basic move/damage testing |
| (2,0) | The Crucible | KingSlime + Lurker | Boss-tier HP, complex move sets |
| (0,1) | Ally Courtyard | Gorran (ally) + Slime | Ally AI, co-op, `friend=True` |
| (1,1) | Status Chamber | Pell (StatusDummy) | Status effects — all resistances 0, HP 500, dmg 3 |

## Code Review Gate

**Always run the `code-review` skill (or `code-scrubber` for large diffs) after any task that changes code.** Routing is by diff size (`.claude/skills/_shared/review_rules/code_review_rules.py`, `review_depth_for_diff_size()`):

| Diff size | Skill | How it runs |
|---|---|---|
| ≤ 1000 changed lines | `code-review` | Inline, single pass, current conversation |
| > 1000 changed lines | `code-scrubber` | Chunked, 5 dimension subagents per chunk, dispatched as a background Agent |

> The `Code Scrubber` **agent** (`.claude/agents/`) declares VSCode-namespaced tools (`vscode/`, `execute/`, `edit/editFiles`) and refuses to spawn outside the IDE — "zero tools". In a CLI session, review a large diff by scoping `code-review` to file subsets instead.

Both grade DRY, Clean Code, Optimization, Maintainability, Security, AI-Friendliness, plus the Heart of Virtue-specific **Architecture** (the rules above — gating) and **Correctness** (graded, reported). Dimension tables, the ≥80 confidence filter, and grading rules live in the two `SKILL.md` files — don't duplicate them here. Non-trivial changes iterate until every gating dimension is A; don't suggest `/commit` before that. If a dimension can't reach A without a user decision, stop and ask. Trivial changes (config, comments): confirm N/A or A and move on.

## Session workflow

Worktrees can host concurrent sessions: run `git status` before committing, stage only files that are cleanly yours, and never `git stash`.

The goal is to ship and maintain a complete game — housekeeping is part of the work. At the end of a meaningful task, suggest what applies: the review gate; `/commit` for changes worth preserving; `/revise-claude-md` when the session revealed something not yet in CLAUDE.md or `.claude/rules/`; confirm the suite is green (the tests already exist from the red-green cycle); flag newly relevant items from `~/.claude/projects/.../pending-improvements.md`. Use judgment — a two-line fix doesn't need a debrief.

## QA — known intentional behaviors

This is an RPG: many things that look broken are puzzles. Before filing a bug for blocked movement, a missing exit, an unresponsive object, or a dead end: **read** the tile/object/NPC text (it is the UI); **interact** with every object on the tile; treat "dead end with an interactable" as a lead, not a bug; if still unsure, file as "possible intentional mechanic — needs verification" and ask.

| Location | Apparent issue | Actual behavior |
|---|---|---|
| Wall Depression (Dark Grotto) | No eastward exit | Interacting yields "Jean hears a faint 'click.'" and unlocks the eastern passage |

General: locked doors may need a key/quest state/NPC; sparse rooms are only bugs if they also lack a description; some passages are one-way; gated content appears only after story progress.

## Skills (project-local unless noted)

| Skill | Use for |
|---|---|
| `/code-review`, `/code-scrubber` | The review gate above |
| `/combat-test` | Arena scenarios from `config_combat_testing.ini` |
| `/mockup` | Retro-terminal HTML mockups → `docs/development/`, pushed to the branch |
| `/narrative-review` | Lore/character/dialogue audit against `docs/lore/` |
| `/devops-review` | CI, dependency, secrets, deploy audit → `tools/devops-audit-*.md` |
| `/map-design` (user-global) | Map design docs and audits → `docs/lore/environments/<region>/` |
| `/sound-designer`, `/music-designer` | Procedural SFX (Song classes) / BGM blueprints and generation prompts |
| `python tools/acceptance_test_generator.py --feature "…" --output tests/acceptance/<slug>` | Scaffolds config + 2-tile map + harness scenario; register the scenario in `tools/harness/scenarios/__init__.py` |

## Licenses

Code: PolyForm Noncommercial. Story/assets: CC BY-NC-ND 4.0. Flag any open-source-incompatible dependency before adding it.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. The
skill has multi-step workflows, checklists, and quality gates that produce better
results than an ad-hoc answer. When in doubt, invoke the skill. A false positive is
cheaper than a false negative.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke /office-hours
- Strategy, scope, "think bigger", "what should we build" → invoke /plan-ceo-review
- Architecture, "does this design make sense" → invoke /plan-eng-review
- Design system, brand, "how should this look" → invoke /design-consultation
- Design review of a plan → invoke /plan-design-review
- Developer experience of a plan → invoke /plan-devex-review
- "Review everything", full review pipeline → invoke /autoplan
- Bugs, errors, "why is this broken", "wtf", "this doesn't work" → invoke /investigate
- Test the site, find bugs, "does this work" → invoke /qa (or /qa-only for report only)
- Review a GitHub pull request → invoke /review
- Code review, check the diff, "look at my changes" → invoke /code-review (redirects to /code-scrubber automatically for diffs over 1000 lines)
- Visual polish, design audit, "this looks off" → invoke /design-review
- Developer experience audit, try onboarding → invoke /devex-review
- Ship, deploy, create a PR, "send it" → invoke /ship
- Merge + deploy + verify → invoke /land-and-deploy
- Configure deployment → invoke /setup-deploy
- Post-deploy monitoring → invoke /canary
- Update docs after shipping → invoke /document-release
- Weekly retro, "how'd we do" → invoke /retro
- Second opinion, codex review → invoke /codex
- Safety mode, careful mode, lock it down → invoke /careful or /guard
- Restrict edits to a directory → invoke /freeze or /unfreeze
- Upgrade gstack → invoke /gstack-upgrade
- Save progress, "save my work" → invoke /context-save
- Resume, restore, "where was I" → invoke /context-restore
- Security audit, OWASP, "is this secure" → invoke /cso
- Make a PDF, document, publication → invoke /make-pdf
- Launch real browser for QA → invoke /open-gstack-browser
- Import cookies for authenticated testing → invoke /setup-browser-cookies
- Performance regression, page speed, benchmarks → invoke /benchmark
- Review what gstack has learned → invoke /learn
- Tune question sensitivity → invoke /plan-tune
- Code quality dashboard → invoke /health
