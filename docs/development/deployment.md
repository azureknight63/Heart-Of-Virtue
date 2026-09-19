# Deploying to nexusfidei.dev

`deploy.ps1` ships the game to `https://nexusfidei.dev/games/HeartOfVirtue`
behind a maintenance page. This is the runbook: what it does, what it needs,
what "green" means, and what to do when it stops.

## Topology (what the script assumes)

| Piece | Where | Notes |
|---|---|---|
| SPA (built `frontend/dist`) | container `webserver`, `/var/www/html/wp-content/HeartOfVirtue` | static files beside WordPress; the web server must rewrite every `/games/HeartOfVirtue/*` route to `index.html` |
| API (gunicorn, `wsgi.py`) | host, systemd unit `heart-of-virtue`, port 5000 | checkout at `/home/alex/heart-of-virtue`, `.venv`; `FLASK_ENV=production` comes from the unit or the server's `.env` (`wsgi.py` refuses anything else) |
| `/games/HeartOfVirtue/api/*` | proxied by the web server to the host API | the SPA's own `/api/info` fetch proves this path works |

Not in this repo and not visible from here: the web server's config inside the
container (the stock WordPress image is Apache; the CSP doc assumes nginx) and
the systemd unit. `-Status` reports what can be observed from outside.

Every build the script deploys carries the commit it was built from, in a
`.hov-commit` file beside its `index.html`. That is how a rollback names the
backend that matches the frontend it restores, and how `-Status` says whether
the live frontend and backend are the same commit.

## Modes

```powershell
.\deploy.ps1 -Status               # drift report — run this first; read-only on the server
.\deploy.ps1 -DryRun               # print every remote script; no build, no network, no .env
.\deploy.ps1                       # full deploy; -Version defaults to the VERSION file
.\deploy.ps1 -Maintenance On       # raise the page by hand
.\deploy.ps1 -Maintenance Off      # lift it by hand
```

Run from a checkout that **is** `origin/master` (the `Alpha` worktree). The
deploy refuses, listing what it found, unless nothing outside `HEAD` can reach
the bundle:

- no modified tracked files, and no file flagged `--assume-unchanged` or
  `--skip-worktree` (git stops comparing those, so it cannot tell whether they
  differ from `HEAD`);
- no untracked files under `frontend/`;
- no ignored files under `frontend/public/` (Vite copies that directory
  verbatim, `.gitignore` or not) or in the env files a production build reads
  (`frontend/.env`, `.env.local`, `.env.production.local`);
- no `VITE_*` variable in the environment (Vite prefers it to every `.env`
  file and bakes it into the bundle), no `NODE_ENV` other than exactly
  `production`, and no `NODE_OPTIONS`.

It checks again after the build, in case `HEAD` moved while it ran. The
frontend is built from the local tree and the backend is pinned to the same
commit on the server, so the two are provably the same code. A failure
anywhere before ssh #1 — the checks, the build, the upload — touches nothing on
the server but the uploaded tarball.

Needs locally: PowerShell 7.4+, git, node/npm, `tar`, `ssh`/`scp`. Optionally
`sshpass`, in which case `NEXUS_PASS` is read from `.env` (or `-EnvFile`) and
passed via `SSHPASS` around each remote call; without it, ssh and scp prompt.
A deploy is one `scp` and two `ssh` calls: three prompts. **The third comes
while the maintenance page is up** — be at the keyboard for it.

Needs on the server (`-Status` checks the ones it can; the deploy refuses
before the window on the two marked ★):
- `alex`'s login shell is **bash** (the remote scripts use `set -o pipefail`);
- `alex` runs `docker` without `sudo`;
- passwordless `sudo systemctl restart heart-of-virtue`. This is the only
  `sudo` the deploy runs or prints, and sudoers must match it exactly.
  `alex`'s password is locked, so any other `sudo` command fails
  (`test_every_sudo_command_is_one_the_deploy_account_may_run`). Server
  administration, such as `apt`, goes through the admin account;
- ★ `curl` on the host, and the host can reach its **own public URL**
  (`HOV_STATUS_HOST_REACHES_PUBLIC`) — ssh #2 fetches the new bundle through it;
- ★ the live directory is not itself a mount point
  (`HOV_STATUS_LIVE_IS_MOUNTPOINT`) — the promote renames it;
- the `.venv` under the app checkout;
- the app's `.env` sets `CONFIG_FILE=config_prod.ini`, the tracked beta-2
  config (`tests/test_prod_config.py`). Before beta 2 it named an untracked
  `config_dev.ini` that started at the Dark Grotto; nothing the deploy
  checks reads this line, so after changing it confirm the start in a
  browser.

## The deploy, step by step

1. **Preflight** — `git fetch`; refuse unless `HEAD == origin/master` and nothing
   unpinned can reach the bundle (see above).
2. **Build** — `npm ci --include=dev`, `npm run build` (the `prebuild` gate
   requires the newest `CHANGELOG.md` version to appear in the login-screen
   changelog). Vite copies `frontend/public/maintenance.html` into `dist/`, so
   the page ships inside the tarball. Then the checkout is checked again, and
   both remote scripts are rendered — before anything touches production.
3. **Upload** — `scp` the tarball to `~/hov_dist.tar` (prompt 1).
4. **ssh #1: stage, raise, replace** (prompt 2). Everything before the raise
   is invisible to players.
   - **Refuse** (and change nothing) if `index.html.parked` sits in the live
     directory — a previous deploy promoted its build and stopped before the
     lift, and its `.prev` is the last build known to work, which promoting
     again would delete — or if the live directory is a mount point, or if the
     host cannot reach its own public URL.
   - Record what is running: the live build's commit (`HOV_LIVE_COMMIT`),
     whether a maintenance page was already up (`HOV_PAGE_WAS_UP`), and the
     backend's HEAD (`HOV_PREV_SHA`). Then `git fetch`, and check that the
     commit being deployed exists on the server.
   - `docker cp` the tarball in (the host copy is removed); extract into
     `HeartOfVirtue.new` beside the live directory and stamp it with its
     commit. In `.new`, park the real `index.html` as `index.html.parked` and
     put the maintenance page in its place, so promoting the directory later
     cannot lift maintenance by accident.
   - **The window opens.** In the live directory, save `index.html` as
     `index.html.pre-maintenance` — unless a save already exists or the index
     already *is* the page — and overwrite it with the maintenance page. Every
     SPA route now shows the page: `HOV_MAINTENANCE=ON`. (A first deploy has
     no live index to front: `HOV_MAINTENANCE=NO_LIVE_INDEX`.)
   - Backend: `git reset --hard <sha>` — tracked edits and local commits on
     the server are discarded (the reflog keeps the commits); the commit is
     the source of truth — then `pip install`.
   - `systemctl restart`, 3 s settle, `is-active`, then poll
     `http://127.0.0.1:5000/health` (10 attempts, 2 s apart, 5 s curl timeout
     each; `-DryRun` prints the worst case).
5. **From your machine** — `GET https://nexusfidei.dev/games/HeartOfVirtue/api/info`
   must be 200 and name the API. This is the hard gate: it proves the proxy
   path works. It does not say *which* build answers (`/api/info`'s version is
   a constant); that the restart replaced the old process is what step 4's
   `/health` proves. When the page was raised, the public `index.html` is also
   fetched once and should show it; if it does not, a cache is in front of the
   document root, the doc root differs, or the request failed — a warning.
6. **ssh #2: promote, prove, lift** (prompt 3 — the page is up)
   - Check the staged build is the one **this run built** (its index names the
     chunk this run's build produced) — a tarball from another run is never
     promoted in its place. Then `rm -rf .prev`, `mv live .prev` and
     `mv .new live`, chained with `&&` so a failed first rename stops the
     phase (the live rename is skipped when there is no live directory yet).
     If the second rename fails, the first is undone. `HOV_PROMOTED=yes`. The
     previous build's saved index is put back so a rollback serves a real
     page. (Between the two renames the live path does not exist for a moment;
     the page is up either side of it.)
   - Check the promoted index still names this run's chunk (the race), then
     fetch that chunk through the **public** URL, HTTPS only. The response
     must be JavaScript, not just 200: the SPA fallback answers a missing
     asset with `index.html` and 200.
   - `mv index.html.parked index.html`. That rename is the lift, and only its
     marker follows it. `HOV_MAINTENANCE=OFF`.
7. **Post-lift** — `/api/info` again, and the public `index.html` should now
   reference the new chunk (cache-busted request; a stale cache is a warning,
   because the lift has already happened on the server). A failing `/api/info`
   here is **not** green: the deploy stops with the commands to put the page
   back up. If ssh #2 exits non-zero after reporting `HOV_MAINTENANCE=OFF` (a
   dropped connection), that is a warning and the post-lift checks still run.

### Why an `index.html` swap and not a 503

The static host is a container whose web-server config this repo cannot see
or edit. Replacing `index.html` needs nothing but the files, works with any
SPA fallback rule, and leaves the API up for anyone mid-session until the
restart. The cost: the page is served with HTTP 200, so it carries
`<meta name="robots" content="noindex">` and a 30 s refresh. A proper 503 with
`Retry-After` is the upgrade once the web-server config is in reach.

### What players experience

Sessions are in-memory (`SessionManager`), so the backend restart signs
everyone out and unsaved progress is lost. The page says so. Anyone who
already had the app loaded keeps a working page until their next API call
fails; new visitors see the maintenance page on every route.

## When it stops (red)

A failure once the page is up **stays in maintenance and stops**; nothing
automatic touches production again. The script prints the state it stopped in
and the exact commands for that state, labelled **(here)** for your machine and
**(on the server)** for after `ssh alex@nexusfidei.dev`.

**Frontend and backend move together.** Every way out keeps players on a
frontend and a backend from the same commit: either fix the cause and run the
deploy again (new + new), or go back to the previous release (old + old) — and
going back always puts the **backend first**, and waits for it to answer,
before anything lifts the page, because lifting onto a mismatched or failing
backend shows players exactly what the page is there to hide.

Backend rollback (on the server). The script prints it with `<ROLLBACK_SHA>`
filled in: the commit stamped into the previous frontend, or — for a build
from before stamping — the backend's HEAD when the run began, but only if no
page was already up (a page left up means an earlier run stopped part-way and
may have moved HEAD). It never names the commit being deployed, and prints only
a full commit id. **Go on only if it printed `BACKEND_OK`.**

```bash
cd /home/alex/heart-of-virtue && git reset --hard <ROLLBACK_SHA> && .venv/bin/pip install -q -r requirements.txt -r requirements-api.txt && sudo systemctl restart heart-of-virtue && sleep 3 && { ok=; for i in $(seq 10); do curl -fsS --max-time 5 -o /dev/null http://127.0.0.1:5000/health && { ok=1; break; }; sleep 2; done; [ -n "$ok" ] && echo BACKEND_OK || echo BACKEND_FAILED; }
```

When it cannot name the commit, it says why and points here instead —
`/var/www/html/wp-content/HeartOfVirtue.prev/.hov-commit` holds it when the
previous build was stamped:

```bash
git -C /home/alex/heart-of-virtue reflog -n 10
```

Frontend rollback, once a build has been promoted (on the server). It restores
the previous build's real index too, so it also lifts the page:

```bash
docker exec webserver sh -c 'test -d /var/www/html/wp-content/HeartOfVirtue.prev && rm -rf /var/www/html/wp-content/HeartOfVirtue && mv /var/www/html/wp-content/HeartOfVirtue.prev /var/www/html/wp-content/HeartOfVirtue && { [ ! -f /var/www/html/wp-content/HeartOfVirtue/index.html.pre-maintenance ] || mv /var/www/html/wp-content/HeartOfVirtue/index.html.pre-maintenance /var/www/html/wp-content/HeartOfVirtue/index.html; }'
```

| Stopped | State | Live frontend | Backend | Ways out |
|---|---|---|---|---|
| ssh #1 refused: `UNLIFTED_PROMOTE` | Promoted | an earlier deploy's build, behind the page | that deploy's commit | keep it: `-Maintenance Off` (here) once its chunk loads; or go back: backend rollback, then frontend rollback |
| ssh #1 refused: mount point, or host cannot reach its public URL | NotRaised | old, untouched | old, untouched | fix the server, re-run |
| ssh #1, before `HOV_MAINTENANCE=ON` | NotRaised | old, untouched | old, untouched — except on a first deploy (`NO_LIVE_INDEX`), where it may be new or partial | re-run; on a first deploy, backend rollback if it is unhealthy |
| ssh #1, after it (backend failed) | Raised | old, behind the page; new build in `.new` | new or partial checkout; the old process may still be running (a failed `pip install` stops before the restart), or the new one is unhealthy | re-run the deploy (here) — safe from here; or backend rollback, then `-Maintenance Off` |
| public `/api/info` check | Raised | same as above | new, healthy on localhost only | fix the proxy and re-run; or backend rollback, then `-Maintenance Off` |
| ssh #2 before the promote (no `HOV_PROMOTED`, incl. `MISMATCH (staged)`) | Raised | old, behind the page; new build in `.new`; `.prev` possibly deleted | new, healthy | re-run the deploy; or backend rollback, then `-Maintenance Off`. There is no frontend rollback: the old build is the live one |
| ssh #2 after the promote | Promoted | new, behind the page; old in `.prev` | new, healthy | keep it: once `-Status`'s chunk loads as JavaScript, `-Maintenance Off`; or go back: backend rollback, then frontend rollback |
| ssh #2 after the promote, `MISMATCH (promoted: …)` | Foreign | another run's build, behind the page; old in `.prev` | this run's commit | do not lift it: backend rollback, then frontend rollback |
| post-lift `/api/info` | Lifted | new, lifted | new | `.\deploy.ps1 -Maintenance On` (here) first; then re-run, or backend rollback followed by frontend rollback |
| a phase cut off: ssh exit 255 after that phase's `HOV_PHASE` line (except after ssh #1's `HOV_BACKEND_HEALTH=OK` or ssh #2's `HOV_MAINTENANCE=OFF`, which count as finished), or the run ended unexpectedly mid-phase | Unknown | not observed | not observed | `.\deploy.ps1 -Status` (here) first; its `MAINTENANCE` / `UNLIFTED_PROMOTE` lines and the commits it reports say which row above applies |

On a first deploy there is no live directory to lift back to: the stops after
the stage report NotRaised, and a re-run is the way out.

An error between phases — after one phase reported its end and before the next
began — prints the help for the last state observed; after the lift, just a note
that the release is live.

Diagnose the backend with `journalctl -u heart-of-virtue -n 50`, without
`sudo`: the service runs as `alex`, so its output is `alex`'s to read, and
`alex` has no password `sudo` could accept. The usual cause is `FLASK_ENV`
not being exactly `production` in the unit or the server's `.env`, which
`wsgi.py` reports by name. Then `.\deploy.ps1 -Status`.

## Caveats worth knowing before the first run

- **Mount point.** The promote renames the live directory, which a mount point
  refuses. The deploy checks for that before the window and refuses; `-Status`
  reports `HOV_STATUS_LIVE_IS_MOUNTPOINT`, read from the container's mount
  table, so it is known beforehand.
- **Caches.** Anything caching `index.html` (a CDN, WordPress caching, a
  browser's heuristic cache when the server sends no `Cache-Control`) delays
  both the page appearing and the new bundle appearing, and can show the page
  for a while after the lift. Only a server-side `Cache-Control: no-cache` on
  `index.html` prevents that; the page cannot set it for itself. Hashed asset
  names make the bundle check immune; the two `index.html` checks are warnings
  for this reason.
- **Old builds.** Only one previous build is kept (`.prev`). Before this
  change, every past build's hashed assets accumulated in the live directory;
  the first deploy with this script replaces that directory wholesale.
- **The first deploy with this script** finds a live build with no `.hov-commit`:
  its rollback line falls back to the backend's HEAD at the start (see above).
- **First deploy to a fresh server** works: the raise step reports
  `NO_LIVE_INDEX` and skips, and the promote step skips the `.prev` rename.
- **Port.** The health poll targets `127.0.0.1:5000`. A unit bound elsewhere
  stops the deploy in maintenance at the health poll (`HOV_BACKEND_HEALTH=FAIL`);
  change `$BackendPort`.

## Cutting a version

Bump three files together: `VERSION`, the newest heading in `CHANGELOG.md`,
and the first entry in `frontend/src/data/changelog.js`.
`tests/test_deploy_script.py` fails if they disagree, and `npm run build`
refuses if the newest `CHANGELOG.md` version is missing from `changelog.js`.
Commit as `chore: bump version and changelog (vX.Y.Z.W)`.

The maintenance page tells players their saved games are kept. Save
compatibility is suspended during the beta, so a release that makes old saves
unloadable should say so on the page (`frontend/public/maintenance.html`)
before it is deployed.

## Tests

`tests/test_deploy_script.py` renders every remote script through `pwsh` and
pins their order and scope: the refusals and every read before the page is
up, and nothing players see changed before it; health before the stage ends;
only this run's build promoted, and its chunk served before the lift; nothing
after the lift but its marker; `-Status` limited to an allow-list of read-only
commands. It drives `Invoke-Deploy`, `Invoke-StatusMode` and
`Invoke-MaintenanceMode` with the network stubbed out, to pin that a red phase
never reaches the next one and prints the right help for its state — including
the rollback commit chosen — and it runs the dry run behind a sandbox that
refuses ssh, scp, npm, docker and network git. It also checks that the three
emergency commands above are the ones the script prints.

It needs PowerShell 7.4+. Without `pwsh` those tests skip locally (and fail on
CI), so a local run with the pwsh tests skipped is not a green one. Run with
`python -m pytest tests/test_deploy_script.py -n0`.
`frontend/src/test/maintenancePage.test.js` holds the page's colours, font and
paths to `styles/theme.js` and `vite.config.js`.
