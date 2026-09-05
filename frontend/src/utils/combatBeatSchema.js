/**
 * Combat beat streaming protocol — frontend mirror (issue #436).
 *
 * Mirror of src/api/schemas/combat_beat.py (the Python source of truth). The
 * event names, error codes, beat fields, outcomes, and SFX kinds MUST match;
 * the Python test tests/test_combat_beat_schema.py parses this file and asserts
 * parity so the wire contract can't silently drift.
 *
 * See docs/development/combat-streaming-plan.md.
 */

export const BEAT_EVENT = 'combat:beat';
export const RESOLVED_EVENT = 'combat:resolved';
export const ENDED_EVENT = 'combat:ended';
export const SUGGESTIONS_EVENT = 'combat:suggestions';
export const ERROR_EVENT = 'error';

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
 * unbounded animation storm. Keep the two values identical.
 */
export const MAX_BEAT_RESOLUTIONS = 16;
