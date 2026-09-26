# Switching production to the gthread worker (and Python 3.13)

One maintenance window that moves production from `--worker-class eventlet` to
`--worker-class gthread -w 1 --threads 32`, ships the one-loop database client
with it, and, optionally in the same window, rebuilds the venv on Python 3.13.

**Why these go together.** The new `src/api/db.py` runs the Turso client on one
dedicated event loop, which fixed concurrent requests cancelling each other's
queries: on production (2026-09-26), 2 concurrent calls under eventlet lost 1,
and 16 on threads lost 15. Under eventlet's monkey-patching that design fails
**every** query, so the new code must never start on the old unit. And the unit
file lives in `/etc/systemd/system`, which `deploy.ps1` does not touch. So the
order below matters. Background: #726, #728, [deployment.md](deployment.md)
("The worker is gthread").

`alex` may only `sudo systemctl restart|status heart-of-virtue`. Steps marked
**ubuntu@** need the admin account.

## 0. Before the window (here)

- The change is merged, and a checkout on `master` is level with `origin/master`.
- `.\deploy.ps1 -DryRun` reads cleanly.

## 1. Close the doors (here)

```powershell
.\deploy.ps1 -Maintenance On
```

## 2. Stop the API (server, ubuntu@)

```bash
sudo systemctl stop heart-of-virtue
```

Stopped, the old code cannot come back up under the new unit, and the new code
cannot come up under the old one.

## 3. Optional: rebuild the venv on Python 3.13 (server, alex@)

Skip this to stay on 3.12. The switch stands on its own.

```bash
cd ~/heart-of-virtue
mv .venv .venv-py312-eventlet
python3.13 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
```

The deploy in step 5 installs the requirements into it.

## 4. Install the new unit (server, ubuntu@)

The file arrives with the code in step 5, so until then copy the reviewed file
from this repo (here), then install it:

```powershell
scp deploy/heart-of-virtue.service alex@nexusfidei.dev:/home/alex/heart-of-virtue.service.new
```

```bash
sudo cp /home/alex/heart-of-virtue.service.new /etc/systemd/system/heart-of-virtue.service
sudo systemctl daemon-reload
grep -- --worker-class /etc/systemd/system/heart-of-virtue.service
```

The last line should show `--worker-class gthread -w 1 --threads 32`.

## 5. Deploy, keeping the page up (here)

```powershell
.\deploy.ps1 -KeepMaintenance
```

This pulls the new code, installs the requirements (no eventlet any more), and
restarts the unit, which is the gthread one now. It prints a private preview URL.

## 6. Check (server, alex@; then the preview)

```bash
systemctl show heart-of-virtue -p MainPID -p NRestarts
ps -o args= -p "$(pgrep -P "$(systemctl show heart-of-virtue -p MainPID --value)" | head -1)" | head -c 200; echo
journalctl -u heart-of-virtue --since "-5 min" --no-pager -o cat | grep -E "Loaded starting position|Traceback" | tail
```

Then, through the preview in a fresh private window: sign in, load or start a
game, save, talk to an AI NPC, and save again. All should succeed.

## 7. Open the doors (here)

```powershell
.\deploy.ps1 -Maintenance Off
```

## Rollback

If the new unit or code misbehaves, put both back together, never one without
the other:

1. **ubuntu@:** `sudo systemctl stop heart-of-virtue`, then restore the eventlet
   unit (the previous commit's `deploy/heart-of-virtue.service`, copied the same
   way as step 4) and run `sudo systemctl daemon-reload`.
2. **alex@:** if step 3 ran, `mv .venv .venv-py313-gthread && mv .venv-py312-eventlet .venv`.
3. Use deployment.md's backend rollback to the commit before this change (it
   reinstalls the requirements, eventlet included, and restarts), then its
   frontend rollback, which also lifts the page.
