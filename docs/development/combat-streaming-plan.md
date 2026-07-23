# Combat Streaming over SocketIO — Implementation Plan (#436)

Status: **in progress** (Phase 0). Owner: engine/frontend. Tracking issue: #436.

## Goal

Replace the current client-side *replay* of a pre-baked combat resolution with
**engine-driven streaming**: the engine's own beat loop pushes structured beat
events over SocketIO, and the frontend animates + sounds each beat in lockstep,
paced locally. This tightly couples combat visuals **and** SFX to the engine.

## Current state (what we're replacing)

- The engine resolves a whole move **synchronously**, bakes every beat into a
  `beat_states` array + `combat_log` (each entry tagged `beat_index` and
  `animation` metadata), and returns it in one lump HTTP response from
  `POST /api/combat/move`.
- The frontend **replays** that array on timers: `displayedLogCount`,
  `isCombatLogProcessing`, `isBattlefieldAnimating`, gating the victory/defeat
  dialog until the replay drains (`useCombatCoordinator`, `BattlefieldGrid`,
  `Battlefield`, `GamePage`, `RightPanel`, `LeftPanel`, `useApi`).
- SFX is **animation-phase-keyed and client-resolved**: `ANIMATION_CONFIGS[type]
  .sfx = { [phase]: cue }`, with the special cue `'outcome'` resolved via
  `impactSfxFor(outcome)`. `BattlefieldGrid`'s phase machine fires cues through
  `AudioContext.playSFX(name)` → `/assets/sounds/sfx_<name>.wav`.
- The SocketIO **server layer is fully built but has zero consumers**:
  `src/api/sockets.py` handlers + `combat_adapter.py` emits
  (`combat:log/started/update/turn/suggestions_ready`), `socket.io-client` is a
  frontend dependency that is never imported. Config keys
  `SOCKETIO_CORS_ALLOWED_ORIGINS` / `SOCKETIO_MESSAGE_QUEUE` are defined but never
  read (app.py builds the socket from `CORS_ORIGINS`).

## Core design decisions

1. **Socket is the primary transport for combat beats/state.** `POST
   /api/combat/move` shrinks to a lightweight ack (`{success, seq}`).
   `GET /api/combat/status` stays as the **reconnect/initial-load reconciliation**
   path only — never a parallel source of truth.
2. **Engine drives order & semantics; client drives timing** (client-paced).
   The engine emits one `combat:beat` per beat as it computes it (a burst is
   fine). The client enqueues and paces playback from `ANIMATION_CONFIGS`
   durations. No server-side `sleep` between beats (would block
   `async_mode="threading"` threads).
3. **One beat protocol** replaces the five ad-hoc emits:
   - `combat:beat` — `{seq, actor_id, target_id, web_animation, outcome,
     damage, killed, status_applied, healed, log_line, sfx:[...]}`
   - `combat:resolved` — terminal authoritative state `{seq, awaiting_input,
     input_type, available_options, combatants}`
   - `combat:ended` — `{status: victory|defeat, end_state_id, drops, summary}`
   - `combat:suggestions` — replaces `suggestions_ready`
   Every event carries a **monotonic `seq`**; a gap triggers a `status` resync.
4. **SFX: hybrid — engine emits ordered, indexed *semantic* emissions; client
   resolves cue + timing.** Each beat carries
   `sfx: [{index, kind, outcome?}, ...]` (e.g. `swing`, `impact`, `status`,
   `death`) — **not** cue strings. The client maps each `kind` (+ outcome) to a
   concrete cue via a client-side resolver and plays them in the
   **server-assigned index order** with the partial-stack rule below. Server owns
   *what happened and in what order*; client owns *which .wav and its timing*.
5. **Partial-stack SFX sequencing.** Emissions within a beat never play
   simultaneously. Emission *i+1* starts when emission *i* is **75% through its
   playback** (25% overlap tail). Implemented as a pure scheduler
   `scheduleSfxChain(emissions, durationOf) → [{cue, startMs}]` with
   `startMs[i+1] = startMs[i] + 0.75 * durationOf(cue[i])`.
6. **SFX duration source = the shipped `.wav` files, not the synth generator.**
   A script iterates `frontend/public/assets/sounds/sfx_*.wav`, reads the true
   duration from each WAV header (`dataBytes / byteRate`, exact for PCM), and
   writes `frontend/src/utils/sfxDurations.js`. Correct regardless of how the
   file was produced (synthesized, hand-picked among renders, Audacity-trimmed).
   A `--check` mode + `prebuild` hook + a Vitest guard fail on a stale manifest.
7. **Wire the dead config.** `app.py` reads `SOCKETIO_CORS_ALLOWED_ORIGINS` and
   `SOCKETIO_MESSAGE_QUEUE` (optional Redis for multi-worker fan-out; default
   `None` = single-process, unchanged).
8. **Feature-flagged rollout.** `COMBAT_SOCKET_STREAMING` (backend config) +
   `VITE_COMBAT_SOCKET` (frontend). Build/ship dark, run both transports during
   migration, flip, then delete the old replay path (Phase 4). Nothing is removed
   until the new path is green in the browser.

## Phases (each test-first: red → green → refactor)

### Phase 0 — Test scaffolding & flag
- `flask_socketio.SocketIOTestClient` fixture (unpacks `(app, socketio)`).
- Frontend fake-socket util (event-emitter stub for `socket.io-client`,
  fake-timer friendly).
- `COMBAT_SOCKET_STREAMING` (default off) + `VITE_COMBAT_SOCKET`.
- Cleanup: `sockets.py` `print()` → `logging`.
- Smoke test: connect → `join_combat` (valid + invalid session) → assert
  `joined_combat` / `error`.

### Phase 1 — Backend beat protocol (engine → socket)
- Beat JSON schema `src/api/schemas/combat_beat.py` + JS mirror
  `frontend/src/utils/combatBeatSchema.js`; Python contract test asserts field
  parity (mirrors `test_move_web_animations.py`).
- `combat:beat.sfx` = ordered indexed semantic emissions; broaden `outcome`
  (`hit|miss|parry|block|deflect|crit|absorb`) and add `killed` /
  `status_applied` / `healed`.
- Refactor `_add_log_entry` + `process_move` tail to emit the new protocol.
- Emit from background threads via a captured `socketio` instance (not
  `current_app`) — thread-safety fix.
- Wire `SOCKETIO_*` config in `app.py`.
- Tests: ordered `combat:beat` sequence (monotonic seq), terminal
  `combat:resolved`, `combat:ended` on a killing blow, sfx semantics
  (killed/status/healed), config read.

### Phase 2 — Frontend socket client + SFX chain
- `frontend/src/api/socketClient.js` (wraps `socket.io-client`).
- `frontend/src/hooks/useCombatSocket.js`: connect/join/reconnect; beat queue;
  pace by `ANIMATION_CONFIGS` durations; `isBattlefieldAnimating` from the queue;
  dedupe by `seq`; gap/reconnect → `status` resync (silent, SFX suppressed).
- SFX resolver `beatSfxFor(beat) → [{kind→cue, phase}]`; pure
  `scheduleSfxChain(emissions, durationOf)` (75% rule); `sfxDurations.js`
  manifest + generator script + freshness guard.
- Tests (fake socket + fake timers): beat ordering/pacing; sfx chain offsets =
  75% cumulative; `playSFX` order/timing; reconnect suppresses replayed SFX;
  victory dialog gated on queue drain.

### Phase 3 — Rewire combat UI onto the stream
- Point `BattlefieldGrid` animation + SFX triggers and the log spooler at
  `useCombatSocket`'s queue.
- `execute_move` route returns `{success, seq}` (behind flag); response treated
  as an ack.
- Update `useCombatCoordinator`/`GamePage`/`Battlefield` tests accordingly.

### Phase 4 — Cleanup / removal
- Server: delete old `combat:log/started/update/turn/suggestions_ready` emits;
  drop `beat_states` from the move response (survives only in `status`); the two
  config keys are now live; drop "dead infrastructure" comments.
- Client: delete client-side `beat_states` replay + timer log spooler that
  assumed a baked array; delete the `fetchCombatStatus()` resync **hacks** in
  `handleSuggestedMoveClick`/move-failure (centralized in `useCombatSocket`);
  `socket.io-client` becomes a used core dependency.
- Docs/CLAUDE.md: update the "SocketIO is dead" + "frontend polls combat" notes.
- Remove the flag and the old path.

### Phase 5 — Resilience & E2E
- Reconnect mid-combat (join → miss beats → seq gap → status resync → resume);
  drop during victory delay; reinforcement waves; ambient/NPC push SFX.
- `tools/inquisitor.py` browser scenario: no console errors, animations + SFX
  fire over the live socket.
- Coverage gates hold (85% backend / 95% frontend).

## Contract tests (anti-drift)

- **Beat schema parity** (Python ↔ JS mirror).
- **web_animation** — existing `tests/test_move_web_animations.py`.
- **SFX catalog** (hard gates): every emittable cue → a shipped `.wav` → an
  entry in `sfxDurations.js`. Cue → `tools/songs/sfx.py` Song class is
  *informational only* (hand-edited/hand-picked sounds legitimately don't
  round-trip through synthesis).
- **Duration freshness**: committed `sfxDurations.js` matches on-disk WAV headers.

## Risks & mitigations

- Missed/out-of-order beats → monotonic `seq` + gap-triggered `status` resync.
- Dual source of truth → socket authoritative; HTTP acks; status = reconcile.
- Background-thread emits → capture `socketio`, no off-request `current_app`.
- Multi-worker scaling → optional `SOCKETIO_MESSAGE_QUEUE` (Redis); single-proc
  default unchanged.
- Reversibility → everything behind `COMBAT_SOCKET_STREAMING` until Phase 4.

## Decisions locked with product

1. Client-paced playback — **approved**.
2. SFX authority = hybrid (engine emits ordered/indexed semantics; client
   resolves cue) — **approved**.
3. First cut = core move→beats→resolve (+ base impact / death / status / heal
   SFX); ambient/reinforcement SFX in Phase 5 — **approved**.
4. Partial-stack SFX at 75% overlap, server-ordered indices — **approved**.
5. Duration manifest generated from shipped `.wav` files (not the synth
   generator) — **approved**.
