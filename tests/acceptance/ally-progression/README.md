# Ally Progression — Acceptance Test

Validates the static ally-progression system end-to-end
(design: `docs/development/ally-progression-design.md`).

## Run

```bash
./run.sh
```

Runs two layers:

1. **Unit tests** (`tests/test_ally_progression.py`) — exp curve parity with
   the player formula, level cap at Jean's level, catch-up multiplier,
   deterministic stat growth, skill schedule grants, sync_level, legacy-save
   backfill, pickle round-trip.
2. **Harness scenario** (`tools/harness/scenarios/ally_progression.py`) —
   boots the real Flask app with this directory's `config.ini`
   (`startmap=combat-testing-arena`, `starting_party_members=Gorran`),
   verifies Gorran level-syncs on join, primes his exp via the test-only
   debug endpoint (`/api/debug/allies*`), wins a Fodder Pit fight, and
   asserts he banked/leveled, never exceeds Jean's level, and the level-3
   skill grant applied.

## Manual dev session

```bash
CONFIG_FILE=tests/acceptance/ally-progression/config.ini python tools/run_api.py
```

Jean spawns in the Proving Grounds at level 2 with Gorran in the party.
`GET /api/debug/allies` shows ally level/exp/moves;
`POST /api/debug/allies/progression {"name": "Gorran", "level": N, "exp": M}`
adjusts them (level moves upward only).
