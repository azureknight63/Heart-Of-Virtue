import { describe, it, expect } from 'vitest';
import {
  BEAT_EVENT,
  RESOLVED_EVENT,
  ENDED_EVENT,
  SUGGESTIONS_EVENT,
  BEAT_FIELDS,
  OUTCOMES,
  SFX_KINDS,
} from './combatBeatSchema';

// This mirror is kept in parity with src/api/schemas/combat_beat.py by the
// Python contract test tests/test_combat_beat_schema.py. These assertions pin
// the JS side so a local edit that breaks the shape fails here too.
describe('combatBeatSchema', () => {
  it('exposes the streaming event names', () => {
    expect(BEAT_EVENT).toBe('combat:beat');
    expect(RESOLVED_EVENT).toBe('combat:resolved');
    expect(ENDED_EVENT).toBe('combat:ended');
    expect(SUGGESTIONS_EVENT).toBe('combat:suggestions');
  });

  it('declares the combat:beat fields in order', () => {
    expect(BEAT_FIELDS).toEqual([
      'seq',
      'actor_id',
      'target_id',
      'web_animation',
      'outcome',
      'hp_changes',
      'killed',
      'status_changes',
      'log_line',
      'sfx',
    ]);
  });

  it('declares the outcome vocabulary', () => {
    expect(OUTCOMES).toEqual([
      'hit',
      'miss',
      'parry',
      'block',
      'deflect',
      'crit',
      'absorb',
    ]);
  });

  it('declares the SFX kinds', () => {
    expect(SFX_KINDS).toEqual(['swing', 'impact', 'status', 'heal', 'death']);
  });
});
