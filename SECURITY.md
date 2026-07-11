# Security

## Save Data Trust Model

Heart of Virtue persists game state as Python pickle blobs:

- **Local saves** — `.sav` files written by `src/functions.py` `save()`/`autosave()`.
- **Cloud saves** — blobs written to the game's own LibSQL/Turso database by
  `GameService.save_game` and read back by `GameService.load_game`.

Both are **trusted server-side artifacts**: they are produced exclusively by
this codebase from the live `Player` object graph. There is no API route that
accepts raw save bytes from a client — players reference saves by ID, and the
bytes never leave the server's custody.

Pickle is unsafe by design when fed untrusted bytes (deserialization can
execute arbitrary code). **Never load a save file obtained from an untrusted
party.** If a save-import feature is ever added, it must not go through the
pickle path — see "Migration plan" below.

## Defenses in `src/secure_pickle.py`

All save deserialization flows through `src.secure_pickle` (via
`functions._safe_pickle_load`), which applies defense-in-depth on top of the
trust model:

1. **Class allowlist (always on).** `SafeUnpickler.find_class` only resolves:
   - classes defined in engine modules (`src.*`, after legacy bare-name
     remapping via `canonical_module_name`), and
   - a curated set of stdlib support globals (`STDLIB_ALLOWLIST`) that real
     Player graphs need (container types, `copyreg` machinery,
     `builtins.getattr` for pickled bound methods, `re._compile` for compiled
     patterns).

   Everything else — `os.system`, `subprocess.*`, `builtins.eval`, arbitrary
   third-party imports — is **never resolved**. In legacy mode it degrades to
   an inert placeholder class; in strict mode it raises
   `RestrictedUnpicklingError`. Engine module-level *functions* are refused
   too (only classes may be reconstructed).

2. **Integrity header.** New saves are prefixed with `HOVS` magic, a format
   version byte, and a SHA-256 digest of the pickle payload. The digest is
   verified before unpickling; mismatches raise `SaveIntegrityError`.
   Headerless blobs are accepted as legacy saves (and logged) so existing
   saves keep loading.

3. **Size cap.** Blobs larger than 32 MB (override with `HOV_MAX_SAVE_BYTES`)
   are rejected before deserialization.

4. **Strict mode.** Set `strict_unpickle = True` under `[game]` in the config
   INI, or export `HOV_STRICT_UNPICKLE=1`, to disable placeholder synthesis
   entirely: any unresolvable or disallowed global raises instead of being
   papered over. Recommended for CI and for any environment where saves might
   not be pristine. Default is legacy mode, which preserves compatibility
   with old saves whose classes have since been renamed or removed.

5. **Diagnostics.** Every module rewrite, placeholder synthesis, and rejection
   is recorded on `SafeUnpickler.events` and logged through the
   `hov.secure_pickle` logger.

### Known residual risk

- `builtins.getattr` is required by legitimate saves (bound methods pickle as
  `getattr(obj, name)`), and `getattr` is a classic gadget primitive. The
  allowlist therefore reduces, but does not eliminate, what a fully
  attacker-controlled blob could do. The integrity checksum and the
  server-side-only trust model remain load-bearing.
- Even allowlisted engine classes run engine code (`__setstate__`, attribute
  machinery) during reconstruction. Allowlisting constrains *which* code, not
  *whether* code runs.

### Migration plan (issue #13, Phase 3)

The long-term exit is a data-only save format (JSON/msgpack of primitives)
with schema validation, keeping pickle solely as a legacy import path. Until
then, the rules above apply.

## Reporting a Vulnerability

Open a GitHub issue (or contact the repository owner privately for anything
sensitive) at https://github.com/azureknight63/Heart-Of-Virtue.
