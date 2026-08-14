import { describe, it, expect } from 'vitest';
import { displayNameOf, formatCombatMoveStatus, isMovePending, beatsUntilResolve } from './combatMoveStatus';

describe('formatCombatMoveStatus', () => {
  it.each([
    [0, 'Preparing: Attack'],
    [1, 'Using: Attack'],
    [2, 'Just used: Attack'],
    [3, 'Cooling down from: Attack'],
  ])('formats stage %s as %s', (stage, expected) => {
    expect(formatCombatMoveStatus({ name: 'NPC_Attack', display_name: 'Attack', current_stage: stage })).toBe(expected);
  });

  it('returns null when no move is present', () => {
    expect(formatCombatMoveStatus(null)).toBeNull();
  });

  it('accepts a legacy move name without a known stage', () => {
    expect(formatCombatMoveStatus('Attacking')).toBe('Attacking');
  });

  it('prefers an explicitly supplied display name over the internal name', () => {
    expect(formatCombatMoveStatus({ name: 'NPC_Attack', current_stage: 1 }, undefined, 'Attack'))
      .toBe('Using: Attack');
  });

  it('resolves a player-facing display name with an internal fallback', () => {
    expect(displayNameOf({ name: 'NPC_Attack', display_name: 'Attack' })).toBe('Attack');
    expect(displayNameOf({ name: 'LegacyMove' })).toBe('LegacyMove');
  });
});

describe('isMovePending', () => {
  it.each([[0], [1]])('treats stage %s as unresolved intent', (stage) => {
    expect(isMovePending({ name: 'Reap', current_stage: stage })).toBe(true);
  });

  it.each([[2], [3]])('treats stage %s as aftermath, not a threat', (stage) => {
    expect(isMovePending({ name: 'Reap', current_stage: stage })).toBe(false);
  });

  it('treats a stage-less move as pending rather than dropping the telegraph', () => {
    expect(isMovePending({ name: 'Cackle' })).toBe(true);
  });

  it('is false for absent or legacy string moves', () => {
    expect(isMovePending(null)).toBe(false);
    expect(isMovePending('Attacking')).toBe(false);
  });
});

describe('beatsUntilResolve', () => {
  it('reports the countdown for a pending move', () => {
    expect(beatsUntilResolve({ current_stage: 0, beats_left: 3 })).toBe(3);
    expect(beatsUntilResolve({ current_stage: 1, beats_left: 0 })).toBe(0);
  });

  it('reports nothing for a move that has already resolved', () => {
    expect(beatsUntilResolve({ current_stage: 3, beats_left: 4 })).toBeNull();
  });

  it('reports nothing when the payload carries no countdown', () => {
    expect(beatsUntilResolve({ current_stage: 0 })).toBeNull();
    expect(beatsUntilResolve({ current_stage: 0, beats_left: -1 })).toBeNull();
  });
});
