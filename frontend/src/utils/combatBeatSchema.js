/**
 * Combat beat streaming protocol — frontend mirror (issue #436).
 *
 * Mirror of src/api/schemas/combat_beat.py (the Python source of truth). EVERY
 * module-level constant defined there must be exported here with the same
 * value; the Python test tests/test_combat_beat_schema.py derives that list
 * from the Python module and parses this file, so a constant added on the
 * Python side and forgotten here fails the suite rather than drifting quietly.
 * The handful of deliberate Python-only names live in that test's
 * _PY_ONLY_CONSTANTS set, each with its reason. The check runs the other way
 * too: an `export const` here with no Python counterpart fails as well, so
 * nothing client-only accumulates in this file unannounced.
 *
 * See docs/development/combat-streaming-plan.md.
 */

/** The ordered beat stream (server -> client). */
export const BEAT_EVENT = 'combat:beat';
export const RESOLVED_EVENT = 'combat:resolved';
export const ENDED_EVENT = 'combat:ended';
export const SUGGESTIONS_EVENT = 'combat:suggestions';
export const ERROR_EVENT = 'error';

/**
 * Room membership handshake. `JOINED_EVENT` is what resets the re-handshake
 * budget in useCombatSocket.js, so a server-side rename does not fail loudly:
 * the ack never arrives, the three retries burn down and the fight silently
 * falls back to the 8s HTTP poll for the rest of the session.
 *
 * The server-only names (combat:started, combat:log, combat:turn,
 * leave_combat/left_combat, ping_combat/pong_combat) deliberately have no
 * mirror here -- nothing in this app listens for or emits them. They live in
 * combat_beat.py's _PY_ONLY_CONSTANTS; mirror one here the moment a client
 * consumer appears.
 */
export const JOIN_EVENT = 'join_combat';
export const JOINED_EVENT = 'joined_combat';

/**
 * Legacy recovery channel: a full serialized battle state, emitted only when
 * the server has no beat streamer attached.
 */
export const UPDATE_EVENT = 'combat:update';

/**
 * Codes on the socket `error` payload. Rationale for the split lives with the
 * Python source of truth (src/api/schemas/combat_beat.py); the short version is
 * that these two conditions call for opposite responses and the client must key
 * off the code, never off the human-readable `message`.
 *
 * `ERROR_SESSION_MISSING` — the handshake carried no credential. HTTP is
 * unaffected, so this is a transport fault: re-handshake, then degrade to the
 * HTTP polling path. It must NOT log the player out.
 *
 * `ERROR_SESSION_INVALID` — a credential arrived and names no live session.
 * The player really is signed out; this is the only code that may reach
 * `onSessionInvalid` -> redirectToLogin.
 */
export const ERROR_SESSION_MISSING = 'session_missing';
export const ERROR_SESSION_INVALID = 'session_invalid';

/** Top-level combat:beat fields (documents the shape). */
export const BEAT_FIELDS = [
  'seq',
  'actor_id',
  'target_id',
  'web_animation',
  'outcome',
  'hp_changes',
  'killed',
  'departed',
  'status_changes',
  'log_line',
  'sfx',
];

/**
 * Reasons a combatant leaves the battlefield. `death` is the only fatal one
 * (drives the death animation + SFX via `killed`); the rest are alive-exits
 * that drop the token without a death animation/sound.
 */
export const DEPARTURE_REASONS = ['death', 'fled', 'warped', 'removed'];

/**
 * Outcomes an `impact` SFX emission resolves against.
 * `glance` is a blow that landed but deflected for half damage — a distinct
 * sonic and visual event from a solid `hit`; `absorb` is a blow the target
 * shrugged off entirely and must never play the flesh-impact cue.
 */
export const OUTCOMES = [
  'hit',
  'miss',
  'parry',
  'block',
  'deflect',
  'crit',
  'glance',
  'absorb',
];

/** Semantic SFX emission kinds the client resolves to concrete cues. */
export const SFX_KINDS = [
  'swing',
  'impact',
  'status',
  'heal',
  'death',
];

/**
 * Ceiling on the per-target resolutions one beat may fan out into. The server
 * truncates the beat's impact emissions at this constant (build_sfx_chain in
 * src/api/schemas/combat_beat.py) and beatToAnimations caps its per-resolution
 * animation fan-out to match — a degenerate payload must not become an
 * unbounded animation storm. tests/test_combat_beat_schema.py asserts the two
 * values stay identical.
 */
export const MAX_BEAT_RESOLUTIONS = 16;
