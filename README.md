# Heart-Of-Virtue
Adventure RPG
Follow former crusader Jean Claire into a strange and dangerous world as he tries to make sense of his situation and piece together the fragments of his tragic past.

This is a text RPG - all graphics are represented using text characters! The human mind is far better at producing images than any pixel editor.

If you like this project and are interested in contributing, please drop me a message.

## Save File Security (Issue #13 Phase 1)
Save files use Python pickle and are considered trusted local artifacts ONLY. A new hardened loader (`secure_pickle.py`) enforces an allow‑list and optional strict mode (see `config_dev.ini: strict_unpickle`). Unknown classes:
- Strict mode: load aborts with an error
- Non‑strict mode: placeholder classes (flag `_legacy_placeholder=True`) are created and logged

Environment override: `HOV_STRICT_UNPICKLE=1` enables strict mode for a run.
Future phases will add integrity headers, size limits, and a data‑only format to deprecate pickle.
