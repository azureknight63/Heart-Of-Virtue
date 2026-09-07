---
name: orchestrate-qa-testers
version: 1.0.0
description: |
  Orchestrate a live browser QA run of Heart of Virtue: several tester agents
  play the real React + Flask build concurrently in headless Chromium (and one
  reviewer in the in-app browser), each on its own persistent driver, against
  one backend per start config; the orchestrator verifies contested findings on
  a clean client, files GitHub issues, and writes the docs/qa report. Use this
  whenever the user wants the game *played* rather than unit-tested — "live
  test the beta", "have agents play through X", "QA the camp conversations in
  the browser", "test on a phone viewport", "is this tester's finding real?",
  "run the beta route with subagents", or any request to test a story arc,
  map, or feature end to end with browsers — even if they don't say "QA",
  "orchestrate" or "tester". Not for single-endpoint checks (bug_hunt.py) or
  static review (/code-review).
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
  - Skill
---

# /orchestrate-qa-testers

You are the orchestrator, not a tester. Your product is a verified, deduplicated set of findings — filed issues plus a report under `docs/qa/` — and the discipline that keeps setup artefacts out of the tracker. The 2026-09-06 run (`docs/qa/beta-live-test-2026-09-06.md`, issues #528–#547) is the worked example; three of its six testers spent most of their budget on a fault in *my* setup, and the two real Criticals were found by reading source after a tester's lead. Plan for both.

Bundled with this skill:

| path | what |
|---|---|
| `scripts/preflight.py` | venv, Playwright + Chromium launch, accepted Vite origins, free ports, `.env` facts, memory, stray Chromiums, `gh` auth |
| `scripts/start_stack.py` | one backend (reloader-free, `GITHUB_TOKEN` blanked, `FLASK_ENV=testing`) + one Vite on an accepted port, per start config; refuses ports Socket.IO would reject |
| `scripts/qa_driver.py` / `scripts/qa.py` | a persistent Playwright browser per tester behind a local HTTP port, with `where()`, `aria()`, `shot()`, `hit_test()`, `raw_click()` and automatic console/network capture |
| `scripts/file_issues.py` | idempotent `gh issue create` from a spec module, label and title checks |
| `assets/TESTER_PRIMER.template.md` | the primer every tester reads first — fill the `{{…}}` slots |
| `assets/issues_spec_template.py` | issue body template |
| `references/gotchas.md` | every environment and judgement trap from the last run — **read before starting stacks** |
| `references/tester-roles.md` | roles, models, budgets, the brief skeleton, staggering and contamination handling |
| `references/triage-and-report.md` | verification bar, severity, issue grouping, report sections, teardown |

Scripts resolve the worktree root from their own location (`.claude/skills/…/scripts` → four parents up) or `HOV_QA_ROOT`. Run them with the repo venv's Python and `PYTHONIOENCODING=utf-8`.

## Phase 0 — scope with the user (one AskUserQuestion, four questions)

Read the map JSON, the story module and any test plan for the arc first so the questions are concrete. Then ask, in one call:

1. **Browser surface** — Playwright per agent (parallel, recommended), the in-app Browser pane (one shared pane, sequential), or Claude in Chrome (needs the extension; check `list_connected_browsers`).
2. **Where the scope ends and what counts** — which scripted scenes, whether free-form LLM talk is in (it costs real tokens), which NPCs.
3. **What to do with bugs** — report only, report + file issues, or fix as they go.
4. **How to handle the hard section** (a boss fight, a long combat gauntlet) — one full-route tester plus split legs with pre-seeded flags is the default that worked.

State the defaults you'll assume for everything else (branch, ports, models, tester count, safety: blank GitHub token, no account registration, test-session login) in the same message.

## Phase 1 — stacks

1. `python scripts/preflight.py --ports … --testers N`. Fix every FAIL; read every WARN.
2. Write one game config per start state into the repo root (`*.ini` is gitignored). Fidelity matters more than the committed beta config: `skipdialog = False`, the party members the story assumes (`starting_party_members = Gorran`), worn gear via `starting_equipment`, and **start one tile before any map transition** whose event is gated on `previous_tile` (teleports never set it). Say in the primer what the seed distorts (level-up modal on the first screen, trivial fights).
3. Start each stack in the background: `python scripts/start_stack.py --tag full --api-port 5001 --vite-port 3001 --config config_qa_x.ini`. Only two Vite ports are accepted Socket.IO origins (3000, 3001) — that is the number of stacks you get. Wait for `READY`; confirm `[SessionManager] [OK] Loaded …` lines in `logs/qa/<tag>/api.log`.
4. Smoke it yourself: a throwaway driver, `where`, `text`, `aria`, one click, one `shot`, `quit`. Read the first events for `socket.io` 400s. Ten minutes here is cheaper than three contaminated testers.

## Phase 2 — primer and dispatch

1. Render `assets/TESTER_PRIMER.template.md` into the session scratchpad with absolute paths, the stacks table, verified UI facts from your smoke (button names, dialog shapes, panel names), known noise, the severity scale, LLM exchange budgets, and the report directory.
2. Write one brief per tester from `references/tester-roles.md`: route as tile list with titles and occupants, named events, exchange counts, budget cap, report path, summary request. Opus for the full route and the UX reviewer, Sonnet for breadth/leg/mobile.
3. Dispatch all Playwright testers in one message (`Agent`, background). Give the pane reviewer the login recipe from `gotchas.md` and one stack only.
4. Within five minutes, grep each `<name>_events.jsonl` for `"status": 400` and `socket.io`. If a stack is faulty you cannot redirect running testers; fix the stack, mark the contaminated testers, and plan re-verification.
5. While they run: check memory once, tail API logs for tracebacks, write the memory note for anything you had to discover.

## Phase 3 — triage and verify (this is the job)

Follow `references/triage-and-report.md`. In short: every Critical/High is a lead until it is reproduced on a clean client by you or confirmed in source with file:line; anything from a faulty stack is suspect; "unclickable" needs `hit_test()` + `raw_click()` + an engine check; "never fires" needs the trigger condition read from the story module; dedupe against `gh issue list --state all --search`. Keep a list of what you dropped and why — it goes in the report.

## Phase 4 — deliver

1. `issues_spec.py` from the template, one entry per confirmed defect plus the umbrella groupings; `file_issues.py --spec … ` dry-run, then `--go` once the user's choice in Phase 0 allows filing.
2. Report at `docs/qa/<run>.md` with the sections in `triage-and-report.md`; copy tester reports and only the cited screenshots into `docs/qa/<run>/`.
3. Update the project memory note ("Live browser QA toolkit") with anything new; tear down (kill each stack's API child; confirm no listeners and no stray `chrome-headless-shell`); suggest `/commit` for the report and any code change — never commit the QA configs by accident.
4. Final message: headline findings with issue links, which findings were setup artefacts and how you know, coverage gaps, recommended order of work.

## Judgement calls that recur

- **Cost.** LLM talk is live (OpenRouter). Cap exchanges per NPC in the brief; testers otherwise explore freely.
- **When a tester dies or gets trapped**, the session is gone (test sessions can't save). The brief tells it to restart its driver; you note whether the trap is a bug (#528 was).
- **When two testers disagree** (one saw a talk line render, one didn't), the difference is usually the tile or the payload — read the route's response shape before deciding who's right.
- **When the user's plan document is stale**, the map JSON wins; say so in the primer and note the drift in the report so the plan gets fixed.
