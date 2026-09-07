# Gotchas — every one of these cost real budget on 2026-09-06

Read this before starting stacks. Each entry says what happened, why, and what to do instead.

## Environment

**Vite port must be an accepted Socket.IO origin.** `Config.CORS_ORIGINS` in `src/api/config.py` lists localhost/127.0.0.1 on ports 3000 and 3001 only, and `SOCKETIO_CORS_ALLOWED_ORIGINS` mirrors it. A Vite instance on any other port still serves the SPA and every REST call (same-origin via the proxy, no CORS enforcement on same-origin GETs), but Chrome sends `Origin` on same-origin POSTs, so engineio rejects every Socket.IO polling POST with 400 ("http://localhost:3002 is not an accepted origin", logged once at ERROR in the API log). Symptoms look exactly like product bugs: an endless handshake/400 storm in the console, combat that never ends in the client, move buttons dead at combat start, beat counter stuck at 0, "categories unclickable on touch". Three of six testers reported those as Criticals; none reproduced on an accepted port. `start_stack.py` refuses unaccepted ports. With two accepted ports there can be only two Vite instances at a time unless `CORS_ORIGINS` is extended.

**Git Bash mangles POSIX-looking values.** Launching Vite from the Bash tool with `VITE_API_URL=/games/HeartOfVirtue/api` turned it into `C:/Program Files/Git/games/HeartOfVirtue/api` (MSYS path conversion); the SPA hung on "Loading location…" forever. Launch servers through `start_stack.py` (Python passes env verbatim) or `export MSYS_NO_PATHCONV=1` first.

**The Werkzeug reloader drops env vars on this box.** `tools/run_api.py` runs with `use_reloader=True`; the reloader child has come up on the wrong interpreter with `FLASK_ENV` unset. `qa_api.py` calls `create_app` + `socketio.run(use_reloader=False)` instead. It also *assigns* `GITHUB_TOKEN=""` and `FLASK_ENV=testing` — assign, never pop, because dotenv's `override=False` refills popped keys. With the token blank the Feedback button is safe to press; with `tools/run_api.py` it files real issues (that already happened once, #301–#324).

**The Bash tool truncates long heredocs.** A file over ~150 lines written via `cat <<'EOF'` fails with "unexpected EOF while looking for matching `''`" at a line that moves with total length. Write long files with the Write tool. Also, a `cd` inside a compound Bash command persists into parallel calls — the QA configs once landed in `frontend/`. Use absolute paths for every write.

**Memory.** 16 GB box: ~5.3 GB free before launch; four headless-shell Chromiums + two backends + two Vites + six agent processes were fine at ~3 GB free. Headless Chromium crashes indiscriminately under ~1 GB free and leaves orphaned `chrome-headless-shell.exe` processes that eat the next attempt. `preflight.py` checks both.

**Cookies are host-scoped.** `hov_session` is set for `localhost` with no port, so one browser profile cannot be logged into two stacks on different localhost ports at once. Each Playwright context is separate; the in-app Browser pane and real Chrome are not — a pane-based tester must stay on one stack for its whole session.

**Claude in Chrome may not be connected.** `list_connected_browsers` returned `[]`; the in-app Browser pane (`mcp__Claude_Browser__*`) was the fallback and worked for a subagent. Login there: `fetch('/games/HeartOfVirtue/api/test/session', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username})})`, then `localStorage.setItem('username', …)`, then reload.

**Subagents cannot be messaged mid-run in this session type.** `SendMessage` was not available, so a tester on a broken stack could not be redirected; it ran its budget out. Get the stacks right before dispatch, and check the first five minutes of the first tester's event log for socket 400s before launching the rest.

## Reading the game

**Test sessions cannot save.** `/api/test/session` sessions have no `db_user_id`, so cloud saves 403 and there is no autosave recovery — every "Autosave failed" toast and `[Autosave] Cloud sync failed` console error is expected noise. A trapped Jean is a dead session; the tester restarts its driver.

**Seeded configs distort the first screen and difficulty.** `starting_exp = 8000` opens on a blocking LEVEL UP modal with 64–71 points (RANDOMIZE clears it) and a level-10 Jean took zero damage in ordinary fights. Say so in the primer or testers file both as bugs. `config_grondia_beta.ini` as committed cannot drive a live run at all (`skipdialog = True` silences every scene; no Gorran) — issue #547.

**`previous_tile` is only set by directional moves.** `GameService.move_player` sets it; `Player.teleport()` (every passageway) does not. Events gated on it (`GorranGestureEvent`) fire on the real route because the player walked to the gate, but never for a session that *starts* on the gate tile. Start Leg-style configs one tile before the transition.

**Encounters are probabilistic.** The Rock Rumbler at eastern-descent (1,2) engaged on one API move and not on the next; do not build routes that assume either.

**The API accepts `/world/move` during active combat** (#543). A tester that "walked away" from a fight via the API has a session with `combat_active: true` on another tile and a confused UI after reload.

**Text extraction can mojibake.** Two testers reported `â€"` in room descriptions; the JSON file is clean. Check the file before filing an encoding bug.

## Judging findings

**Playwright actionability is not a soft-lock verdict.** `locator.click()` refuses elements another node covers (`<div> intercepts pointer events`) and an agent will call that "unclickable". SELECT TARGET's STRIKE buttons fail `elementsFromPoint` yet a raw `page.mouse.click(x, y)` commits the move. Always confirm with `hit_test()` + `raw_click()` + an engine check before accepting a Critical. It is still a real hit-testing/a11y defect — file it as that.

**Button text is CSS-uppercased.** Match with `re.compile("continue", re.I)`, never `name="CONTINUE"`.

**Keyboard tests need focus inside the dialog** and even then the event dialogs' key hints do nothing (#530); four testers reproduced it. Don't waste budget re-proving it — cite it.

**"Not fired" needs the trigger conditions read from source first.** Half the "event never fires" reports were config artefacts; the one that was real (#528, tile modifications keyed without the map name) was found by reading `game_service.py`, not by the browser.

**Contamination is transitive.** When a stack is found faulty, list every finding from every tester on it and mark each as "re-verified on a clean client", "dropped", or "kept as observation with caveat" in the report. Never let a setup artefact reach the tracker.
