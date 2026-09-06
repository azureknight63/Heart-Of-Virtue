---
paths:
  - "src/secure_pickle.py"
  - "src/save_format.py"
  - "src/_unpickle_worker.py"
  - "src/functions.py"
  - "src/universe.py"
  - "src/api/services/game_service.py"
  - "src/api/routes/saves.py"
  - "tools/save_fuzzer.py"
  - "tools/save_v2_fuzzer.py"
  - "tools/gen_allowlist_manifest.py"
  - "docs/development/save-allowlist-manifest.json"
  - "tests/test_save_fuzz.py"
---

# Saves and persistence rules

Saves are pickles loaded through `src/secure_pickle.py`. Treat every save as untrusted input and every persisted-class change as a compatibility event. `SECURITY.md` has the threat model (issue #13, all phases).

## Loader (`src/secure_pickle.py`)
- `SafeUnpickler` + legacy-module resolution live here; `functions.py` re-exports the old names and routes `_safe_pickle_load`/`save` through it. **Any new deserialization path goes through `SafeUnpickler`** — never bare `pickle.load`.
- **Strict mode is opt-in and nothing turns it on.** `safe_pickle_load(fp)` is called with `strict=None`, which resolves through `strict_mode_enabled()` → the `HOV_STRICT_UNPICKLE` env var, and that variable is set in no config, no `.env.example`, and no CI workflow. On a default load `SafeUnpickler.find_class` returns any global it can resolve, unchecked, and synthesizes a placeholder for any it cannot. What is actually protecting a default load is the sha256 integrity header, the 5 MB size cap, and legacy-module rewriting — not the allow-list. Treat that as the baseline when you reason about a new deserialization path, and set `HOV_STRICT_UNPICKLE=1` when you want the gate.
- With strict mode **on**, enforcement is engine-module-based: any global from an `src.<engine module>` is trusted (classes and functions/methods) plus a curated `_SAFE_STDLIB` set; `os`, `subprocess`, `builtins.eval`, `getattr` are blocked. `_resolved_global_is_trusted` re-checks the *resolved* object's own `__module__`, which is what closes protocol 4's dotted-attribute traversal — a stream naming `("src.secure_pickle", "os.system")` passes the module check and is still rejected. `find_class` catches `ImportError/AttributeError/ValueError/TypeError` for malformed module paths.
- **`LEGACY_BARE_MODULES`**: legacy pickles store bare module names by contract. Every new top-level `src/` module must be added here (enforced by `tests/test_no_bare_local_imports.py`); `functions.canonical_module_name()` is the resolver (also used by `Universe._deserialize_saved_instance`).
- Tagged legacy placeholders (`_legacy_placeholder=True`) get per-class fresh mutable containers; serializers must tolerate them (serializer contract in `.claude/rules/api-layer.md`).
- New saves carry a `HOVS` magic + version + **sha256 integrity header** (`serialize_for_save()`); the loader validates it and still reads legacy headerless saves. 5 MB size cap. Structured event logging + process telemetry on load. Optional sandboxed-subprocess loader: `load_in_subprocess` → `src/_unpickle_worker.py` (sets `RLIMIT_AS` — fuzzing found an allocation-DoS).
- `game_service.save_game` writes headered saves; cloud saves are one row per named save plus one `is_autosave=TRUE` row per user (UPSERT every 3 transitions). `list_saves` emits `timestamp_ms` computed *before* `astimezone(user_tz)`.

## Data-only format prototype (`src/save_format.py`, behind `HOV_SAVE_V2`)
`player_to_data`, schema validation, version negotiation, one-shot sidecar conversion — captures a documented player+world **subset**; pickle remains the source of truth. Extend the subset deliberately and bump the schema version; `tools/save_v2_fuzzer.py` covers it.

## Compatibility rules
- Persisted classes keep **backward-compatible defaults**: add attributes with class-level defaults or `getattr` fallbacks in the reader; never rename or remove a persisted attribute without a default-for-one-release; never reorder positional pickle state.
- Persist authoritative state only; derived values (caches, proximity tables, cooldown views) are rebuilt on load.
- A format or allow-list change regenerates the manifest: `python tools/gen_allowlist_manifest.py` → `docs/development/save-allowlist-manifest.json` (drift is test-guarded). The manifest is an **inventory for drift detection, not the enforcement gate** — nothing on the load path consults `get_allowlist()`; `_is_allowed` is the gate, and only in strict mode. Regenerate the file, never hand-edit it. **Check your interpreter first:** CI runs 3.11 and the manifest is derived from `__module__`, which CPython moves between releases (`pathlib.Path` → `pathlib._local` on 3.13+). Regenerating on a newer Python fixes your box by breaking CI — verify with `py -3.11 tools/gen_allowlist_manifest.py --check`. `_public_module()` canonicalizes the known cases; extend it rather than regenerating.
- Run the fuzzer after touching the loader: `python tools/save_fuzzer.py` / `python -m pytest tests/test_save_fuzz.py -q`. It populates saves with random real classes/values and adversarial payloads (disallowed globals, malicious `__reduce__`, tampered headers, oversize, garbage) and asserts zero **security** invariant breaches; benign strict-mode rejections are reported as coverage gaps, not failures.
- Keep at least one real legacy save fixture loading in tests when you change the header or allow-list — a save that loaded yesterday must load tomorrow.
