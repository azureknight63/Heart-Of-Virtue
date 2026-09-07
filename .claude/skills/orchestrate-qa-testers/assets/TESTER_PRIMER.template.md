# {{GAME}} — live browser QA, tester primer ({{DATE}})

You are one of several tester agents playing the build through a real browser, in parallel.
Repo worktree: `{{ROOT}}` ({{BRANCH}}). Everything below uses absolute paths; do not rely on the shell cwd.

```
ROOT    = {{ROOT}}
PY      = {{PY}}
SCRIPTS = {{SCRIPTS}}
RUNS    = {{RUNS}}          (screenshots and event logs land here)
REPORTS = {{REPORTS}}       (write your report here)
```

## The server stacks (already running — never start, stop or restart them)

{{STACKS_TABLE}}

Each stack is one backend process; every tester gets an independent session/universe on it, so you cannot interfere with another tester's game. Any port not listed here belongs to someone else — never touch it.

## Your browser: qa_driver.py + qa.py

Start your driver ONCE, in a Bash call with `run_in_background: true` (it stays alive across your later Bash calls):

```
PYTHONIOENCODING=utf-8 "<PY>" "<SCRIPTS>\qa_driver.py" --name T3 --frontend http://localhost:PORT --api http://localhost:PORT --ctrl 7003
```
(add `--mobile` only if your assignment says so). Then wait for it:
```
until curl -s -o /dev/null http://127.0.0.1:7003/ping; do sleep 2; done
```
It logs in through the testing-mode session bypass and lands on the game page. Every later call goes through the client (always set `PYTHONIOENCODING=utf-8`):

```
"<PY>" "<SCRIPTS>\qa.py" 7003 where        # engine truth: map, x, y, title, exits, npcs, objects, items, hp, pending events
"<PY>" "<SCRIPTS>\qa.py" 7003 text         # visible page text (innerText)
"<PY>" "<SCRIPTS>\qa.py" 7003 aria         # accessibility tree: every button/dialog with its accessible name — use this to find controls
"<PY>" "<SCRIPTS>\qa.py" 7003 shot label   # screenshot -> prints the png path (put it in your report)
"<PY>" "<SCRIPTS>\qa.py" 7003 pending      # GET /api/world/events/pending
"<PY>" "<SCRIPTS>\qa.py" 7003 allerrors    # every non-noise console/network event so far
"<PY>" "<SCRIPTS>\qa.py" 7003 -c "page.get_by_role('button', name='Move South').click()"
"<PY>" "<SCRIPTS>\qa.py" 7003 exec <<'PYCODE'
page.get_by_role("button", name=re.compile("continue", re.I)).click()
wait(1500)
print(text()[:1500])
result = where()
PYCODE
"<PY>" "<SCRIPTS>\qa.py" 7003 quit         # at the very end
```

Inside `-c`/`exec` code you have Playwright's `page`, `context`, `browser`, plus helpers `text()`, `aria()`, `shot(label)`, `wait(ms)`, `where()`, `state()`, `pending()`, `all_errors()`, `get(path)`, `post(path, payload)` (API calls with your session's Bearer token), `hit_test(locator)`, `raw_click(locator)`, and `json`, `re`, `time`. A single expression is returned; statements can `print()` or assign `result = ...`.

Every client call also prints **"new browser events"**: console errors/warnings, page errors, failed requests and 4xx/5xx responses since your previous call. Read them every time; they are evidence.

### UI facts (verified)
{{UI_FACTS}}

### Before you call anything "unclickable"
Playwright refuses to click an element that another node covers, and reports `<div> intercepts pointer events`. That is not proof a player is stuck: run `hit_test(page.get_by_role("button", name="X", exact=True))` to see the stack at its centre, then `raw_click(...)` to send a real pointer event, and check the engine (`where()`, `get("/api/combat/status")`) to see whether the action happened. Report all three results. Only a control that fails the raw click too is a soft-lock.

### Cross-checking and fallbacks
- `where()` after every move: if the UI and the engine disagree about position, exits, NPCs or HP, that is a finding.
- If a click silently does nothing, cross-check the same action through the API (`post("/api/world/move", {"direction": "south"})`, `post("/api/world/interact", {...})`, `post("/api/world/events/input", {"event_id": ..., "user_input": "continue"})`). If the API works and the UI didn't, it is a frontend bug; record both. Use the API to *verify*, not to play — advance through the UI. Only if the UI is truly stuck: record the finding, then advance via API so the rest of your route still gets tested.
- Save/Load will fail (403) for test sessions — out of scope, not a bug. Do not use the login/register form (it writes to the live database).
- The Feedback button is safe: the GitHub token is blanked on these servers. Open it once, submit once, and report what the UI does.
- NPC "talk" on named NPCs is LLM-backed and costs real tokens: {{LLM_BUDGET}}. Scripted story scenes are not LLM.

### Known noise — do not report
{{KNOWN_NOISE}}

## Ground rules
- Do not edit ANY file under `ROOT` (source, configs, tests), do not run git, do not kill or start servers, do not install packages. Reading source is encouraged: {{SOURCE_HINTS}} tell you what *should* happen.
- Read `ROOT\CLAUDE.md` section "QA — known intentional behaviors" and {{TEST_PLAN}} before filing anything about blocked exits, dead ends or unresponsive objects.
- Budget: the tool-call cap in your assignment, or {{TIME_BUDGET}}, whichever first. Stop and write the report even if incomplete. A partial report with evidence beats a complete run without it.
- Screenshot at every scene transition, every dialog, every anomaly.
- Do NOT file GitHub issues and do not write anything into the repo. The orchestrator triages and files.

## Report — write it to `<REPORTS>\<YOURNAME>.md`

1. **Header**: tester name, stack, viewport, tool calls used, where you ended (map, x, y), whether the driver survived.
2. **Route checklist**: a table of every scene/step in your assignment → PASS / FAIL / BLOCKED / NOT REACHED with one line of evidence each.
3. **Findings**, one `###` heading per finding:
   - Severity: {{SEVERITY_SCALE}}
   - Location: map + tile (x, y)
   - Steps to reproduce: numbered, from session start
   - Expected / Actual
   - Evidence: screenshot paths, console/network events verbatim, API response excerpts
   - Confidence: reproduced twice / seen once / possibly intentional (say why)
4. **Dialogue voice notes**: quote the LLM lines you got; say whether each NPC held character; check `ai/npc/human/<name>.json` for `prohibited_phrases` and flag any that appear.
5. **Non-bug observations**: UX friction, pacing, wording — short list.
