# Security Policy

## Save File Trust Model
Game save files (`*.sav`) are Python pickle archives intended ONLY for local, trusted use. **Never open a save file obtained from an untrusted source.** Opening a malicious pickle can execute arbitrary code (a Python design limitation).

## Phase 1 Hardening (Issue #13)
Implemented in `src/secure_pickle.py`:
- Allow‑list of permitted (module, class) tuples (items, npc, states, objects, story, player, moves).
- Strict mode (config flag or `HOV_STRICT_UNPICKLE` env var) rejects any class not on the allow‑list.
- Non‑strict mode fabricates clearly tagged placeholder classes (`_legacy_placeholder=True`) for unknown types.
- Event log (`secure_pickle.EVENT_LOG`) records rejections & placeholder creation.

Default strict mode is controlled via `config_dev.ini`:
```
[Startup]
strict_unpickle = False
```
Override per process:
```
HOV_STRICT_UNPICKLE=1 python -m game
```

## Roadmap (Planned Future Phases)
- Integrity header + checksum (tamper detection)
- Maximum save size cap (e.g. 5 MB configurable)
- Narrow & explicit module rewrite map (if still required)
- Deterministic legacy placeholder allow‑list only
- Data‑only (JSON/msgpack) format & automatic migration
- Sandboxed legacy unpickling in a constrained subprocess

## Reporting Vulnerabilities
Open a GitHub issue with a clear title beginning with `[SECURITY]` (avoid including exploit PoCs with live payloads). For sensitive findings you prefer not to disclose immediately, contact the repository owner directly.

## Disclaimer
Even with strict mode, using pickle implies inherent risk if you choose to load untrusted data. Long term migration away from pickle is planned.

