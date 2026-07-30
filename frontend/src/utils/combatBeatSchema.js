/**
 * Combat beat streaming protocol — frontend mirror (issue #436).
 *
 * Mirror of src/api/schemas/combat_beat.py (the Python source of truth). The
 * event names, beat fields, outcomes, and SFX kinds MUST match; the Python test
 * tests/test_combat_beat_schema.py parses this file and asserts parity so the
 * wire contract can't silently drift.
 *
 * See docs/development/combat-streaming-plan.md.
 */

export const BEAT_EVENT = 'combat:beat';
export const RESOLVED_EVENT = 'combat:resolved';
export const ENDED_EVENT = 'combat:ended';
export const SUGGESTIONS_EVENT = 'combat:suggestions';

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

/** Outcomes an `impact` SFX emission resolves against. */
export const OUTCOMES = [
  'hit',
  'miss',
  'parry',
  'block',
  'deflect',
  'crit',
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
