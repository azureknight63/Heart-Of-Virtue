# Beta 2 cutover runbook (2026-09)

One-time move of production from the April beta-1 build (`b57a0ac5`, Python 3.12) to beta 2:
Python 3.13, the chat/Mynx/advisor LLMs on with `auto` model selection, `config_prod.ini`, and
every cloud save cleared. Players stay behind the maintenance page from step 1 until step 9.

The standing mechanics — what each deploy phase does, the stuck-deploy table, and rollback
commands — are in [deployment.md](deployment.md). This page only orders the one-off work around
them.

**Accounts.** `alex@nexusfidei.dev` owns the app and may run exactly
`sudo systemctl restart|status heart-of-virtue` and nothing else under sudo. Package installs and
stopping the unit go through `ubuntu@nexusfidei.dev`. `journalctl -u heart-of-virtue` needs no sudo.

**Before you start (here):**

- PR #723 (the #712–#718 fixes) and this branch are merged. A deploy ships `origin/master` and
  refuses unless the local checkout is exactly there, so run the `deploy.ps1` steps from a
  worktree on an up-to-date `master`.
- `.\deploy.ps1 -KeepMaintenance -DryRun` reads cleanly.
- Groq and Cerebras API keys in hand (step 3). With OpenRouter's free tier alone (50 requests
  a day), chat, Mynx and the advisor share one budget; the other two are the fallback chain.

## 1. Close the doors (here)

```powershell
.\deploy.ps1 -Maintenance On
```

Browsers that already have the game open keep talking to the API until the next step stops it.

## 2. Python 3.13 and the unit stopped (server, as `ubuntu@`)

```bash
sudo systemctl stop heart-of-virtue
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.13 python3.13-venv python3.13-dev
python3.13 --version
```

Stopping the unit now means nothing can write a save between the wipe (step 5) and the new
build's first start, and it lets the old venv be moved safely.

Then, as `alex@`:

```bash
cd ~/heart-of-virtue
mv .venv .venv-py312            # kept for the rollback below; delete once beta 2 has settled
python3.13 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
```

The new venv is empty on purpose: the deploy's own `pip install -r requirements.txt -r
requirements-api.txt` fills it from the new commit's pins.

## 3. `.env` (server, as `alex@`)

Back it up first. Never paste its values into a chat, a ticket or a log.

```bash
cd ~/heart-of-virtue
cp -p .env .env.pre-beta2
grep -c '^ENCRYPTION_KEY=.\+' .env     # expect 0 today
python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'
```

That prints a Fernet key (32 random bytes, url-safe base64) using the standard library alone,
because the new venv has no packages until step 4.

Edit `.env` so it has these lines (add or replace, one of each):

```
CONFIG_FILE=config_prod.ini
ENCRYPTION_KEY=<the key printed above>
NPC_CHAT_LLM_ENABLED=1
MYNX_LLM_ENABLED=1
COMBAT_LLM_ENABLED=1
MYNX_LLM_MODEL=auto
NPC_CHAT_LLM_MODEL=auto
COMBAT_LLM_MODEL=auto
MYNX_LLM_PROVIDER=openrouter
NPC_CHAT_LLM_PROVIDER=openrouter
GROQ_API_KEY=<your Groq key>
CEREBRAS_API_KEY=<your Cerebras key>
```

- **The two `*_PROVIDER` lines are what switch Groq and Cerebras on.** A key alone arms nothing:
  a feature assembles its fallback chain (OpenRouter, then Groq, then Cerebras) only when its
  provider is named explicitly, and NPC chat does *not* count an inherited `MYNX_LLM_PROVIDER`
  as a choice (`.env.example`, "IMPORTANT — a key alone does not arm the fallback chain"). Leave
  `GROQ_MODEL`/`CEREBRAS_MODEL` blank for their defaults.
- The tactical advisor (`COMBAT_LLM_*`) routes OpenRouter or Ollama only; it never uses the
  Groq/Cerebras chain, and naming either there turns it off. Leave `COMBAT_LLM_PROVIDER` unset.

- `ENCRYPTION_KEY` is new and mandatory: the beta-2 code refuses to start in production without
  it (`src/api/config.py`, `AuthService.__init__`). Keep a copy somewhere safe; losing it makes
  every stored email unreadable. It orphans nothing today: nothing in the app decrypts an email,
  and the April build, running without a key, encrypted with a fresh throwaway key on every start.
- `MYNX_LLM_MODEL` is currently pinned to one OpenRouter free model; `auto` replaces that.
- `CONFIG_FILE=config_prod.ini` should already be there. The file itself arrives with the deploy.

## 4. Deploy, keeping the page up (here)

```powershell
.\deploy.ps1 -KeepMaintenance
```

It builds, uploads, installs the requirements into the new venv, restarts the unit (which also
starts it, since step 2 stopped it), proves the new bundle is served, and prints a private
`preview-<token>.html` URL instead of lifting the page. Keep that URL private: it is the only way in.

If it stops early, the table in deployment.md says what state it left and what to do.

Then confirm on the server that the right game is running:

```bash
journalctl -u heart-of-virtue -n 80 --no-pager | grep -iE 'Loaded starting position|config_prod|Traceback|ENCRYPTION_KEY'
```

You want `Loaded starting position from config: (1, 2)` (Grondia, from `config_prod.ini`) and no
traceback. If that line has not appeared yet, it may wait for the first session; check again
during step 6.

## 5. Clear the cloud saves (server, as `alex@`)

```bash
cd ~/heart-of-virtue
.venv/bin/python tools/wipe_cloud_saves.py
```

That is a dry run: it prints the database host (never a credential), the number of saves and
autosaves, how many users hold them, and the oldest and newest timestamps (UTC). The newest
should predate step 1. If it does, delete:

```bash
.venv/bin/python tools/wipe_cloud_saves.py --confirm "DELETE ALL CLOUD SAVES"
```

It deletes every row of `saves` and nothing else; accounts are untouched. **This cannot be
undone**, and a rollback does not bring saves back.

## 6. Test on production (here, a browser)

Open the preview URL from step 4 **in a fresh private window**. A browser still holding an old
sign-in takes the app straight to the game; if the new server rejects that session (401), it is sent to
`/login` by a full page load, which serves the maintenance page. A reload or a sign-out does the
same; reopen the preview URL to get back in.

- Sign in with an existing account. The save list is empty.
- New game: Jean starts in Grondia. The beta briefing's tester notice includes "Saves from the
  earlier beta have been cleared".
- Talk to Jambo in his Grondia tent: an LLM reply, in the third person, about that tent.
- One fight with the tactical advisor open: a suggestion appears.
- Save, reload through the preview URL, load the save.
- `journalctl -u heart-of-virtue -n 200 --no-pager` shows no tracebacks. LLM provider errors
  are worth reading; a 429 means the free-tier budget is the limit.

## 7. Clear the test saves (optional, server)

Step 6 made saves. To reopen with an empty table, repeat step 5: the dry run should show only
today's saves from your own test account.

## 8. Open the doors (here)

```powershell
.\deploy.ps1 -Maintenance Off
```

This restores the real index and deletes the preview file. Then run `.\deploy.ps1 -Status`, and
open the public URL in a fresh private window.

## Rollback

Before step 5, everything can be undone. After it, the saves cannot.

1. `.\deploy.ps1 -Maintenance On`, unless the page is still up.
2. On the server, as `alex@`:
   ```bash
   cd ~/heart-of-virtue
   cp -p .env.pre-beta2 .env
   mv .venv .venv-py313 && mv .venv-py312 .venv
   ```
   Then run deployment.md's backend rollback with `<ROLLBACK_SHA>` = `b57a0ac5`. That is the
   April commit; its full SHA is on the deploy's `HOV_PREV_SHA` line. Go on only once it
   prints `BACKEND_OK`.
3. Run the frontend rollback. Note that it **also lifts the page**, onto the April build. If
   players must stay out (to try a fixed beta-2 build instead), run
   `.\deploy.ps1 -Maintenance On` straight after it.

A second `-KeepMaintenance` deploy over a kept one is refused (`KEPT_FOR_PREVIEW`), so a failed
step 6 means rolling back first and then deploying the fix. deployment.md, "Keeping the page up
for a private test", explains why.

Once beta 2 has run cleanly for a while, delete `.venv-py312` and `.env.pre-beta2`. The backup
still holds the old provider keys.
