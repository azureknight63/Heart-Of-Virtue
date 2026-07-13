# Security Policy

## Save File Trust Model

Heart of Virtue persists game state using Python's `pickle` module (`.sav`
files on disk and the `data` column of the Turso `saves` table). **Unpickling
executes arbitrary code by design** — this is an intrinsic property of the
pickle format, not a bug in this project. See the
[Python pickle security warning](https://docs.python.org/3/library/pickle.html#module-pickle).

### Trust boundary

> **Pickle saves are trusted local artifacts only.**
> A save file is only safe to load if it was produced by this game engine for
> the player who owns it. Never load a `.sav` file — or import save bytes —
> that originated from an untrusted third party. Doing so can result in
> arbitrary code execution on the loader's machine.

In the deployed web app, saves are scoped to a registered account: `load_game`
queries `WHERE id = ? AND user_id = ?`, so a player can only load their own
rows. There is no feature that ingests a save uploaded by another user. If such
a feature is ever added, it **must not** use the pickle loader — it must go
through the data-only format (see Roadmap, Phase 3).

## Deserialization Hardening

Save deserialization is encapsulated in [`src/secure_pickle.py`](src/secure_pickle.py).
It reduces — but does not eliminate — the risk of loading a malformed or
tampered save:

| Control | Behavior |
|---|---|
| **Controlled module rewrite** | Legacy bare module paths (`items`, `story.ch01`) are rewritten to canonical `src.*` paths via an explicit `LEGACY_BARE_MODULES` allow-set. No other module path is redirected. |
| **Class allow-list** | Derived automatically at first use by introspecting the engine modules (`src.items`, `src.npc`, `src.player`, `src.story`, …). Entries are `(module, class_name)` tuples keyed on each class's real `__module__`. |
| **Strict mode** | Opt-in via the `HOV_STRICT_UNPICKLE` environment variable (`1`/`true`/`yes`/`on`). Rejects any class not on the allow-list and **disables placeholder synthesis**, raising `RestrictedUnpicklingError`. |
| **Legacy (default) mode** | Unresolved classes become benign placeholder objects tagged `_legacy_placeholder = True` so old saves still load; every synthesis is logged. |
| **Size cap** | Payloads larger than `DEFAULT_MAX_SAVE_BYTES` (5 MB) are rejected *before* unpickling with `SaveTooLargeError`. |
| **Structured logging** | Every module rewrite, placeholder creation, and rejection is recorded on `SafeUnpickler.events` and emitted through the `logging` module for debug/UI inspection. |

### Enabling strict mode

```bash
# Reject any class not on the engine allow-list; no placeholder synthesis.
HOV_STRICT_UNPICKLE=1 python tools/run_api.py
```

Strict mode is intended for development, CI, and any future path that loads
saves of uncertain provenance. It is **off by default** so that legacy saves
referencing removed classes continue to load in normal play.

> ⚠️ **Remaining risk (inherent to pickle):** even with the allow-list, a
> crafted pickle can invoke allowed classes' `__reduce__`/`__setstate__` in
> unexpected ways. Strict mode narrows the attack surface; it does not make
> untrusted pickle loading safe. The only complete fix is migrating off pickle.

## Roadmap (issue #13)

- **Phase 1 (done):** trust-model documentation, class allow-list, strict-mode
  flag, placeholder gating + logging, controlled rewrite map.
- **Phase 2 (partial):** size cap and structured event logging are in place.
  A magic-bytes + checksum integrity header for new saves is still pending.
- **Phase 3 (planned):** a data-only (JSON/msgpack) save format containing only
  primitive types. Pickle is retained solely for one-shot legacy import, which
  immediately rewrites the save in the new format.
- **Phase 4 (optional):** sandboxed legacy unpickling in a restricted
  subprocess; automated allow-list manifest generation.

## Reporting a Vulnerability

This is a noncommercial hobby project (see `LICENSE-CODE`). If you discover a
security issue, please open a GitHub issue describing the problem and, where
possible, a reproduction. Do not include working exploit payloads in public
issues.
