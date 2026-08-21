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
  it('reports the engine-computed time until the move lands', () => {
    // beats_left is beats left in the CURRENT STAGE — for a move with a
    // 4-beat execute stage the real answer is 9, not 3. The engine computes
    // it (Move.beats_until_resolve); this is a passthrough.
    expect(beatsUntilResolve({ current_stage: 0, beats_left: 3, beats_until_resolve: 9 })).toBe(9);
    expect(beatsUntilResolve({ current_stage: 1, beats_left: 0, beats_until_resolve: 1 })).toBe(1);
  });

  it('never reports the much smaller in-stage count when the real one is present', () => {
    // Guards the regression directly: returning beats_left here would have
    // told the player they had 3 beats to react when they had 9.
    expect(beatsUntilResolve({ current_stage: 0, beats_left: 3, beats_until_resolve: 9 }))
      .not.toBe(3);
  });

  it('reports nothing for a move that has already resolved', () => {
    expect(beatsUntilResolve({ current_stage: 3, beats_left: 4, beats_until_resolve: null })).toBeNull();
  });

  it('reports nothing when the payload carries no countdown', () => {
    expect(beatsUntilResolve({ current_stage: 0 })).toBeNull();
    expect(beatsUntilResolve({ current_stage: 0, beats_left: -1 })).toBeNull();
  });

  it('never renders a zero — "lands this beat" is 1, not 0', () => {
    expect(beatsUntilResolve({ current_stage: 1, beats_left: 0 })).toBeNull();
    expect(beatsUntilResolve({ current_stage: 0, beats_left: 0, beats_until_resolve: 0 })).toBeNull();
  });

  it('falls back to beats_left for a stage-less payload, which carries no better answer', () => {
    expect(beatsUntilResolve({ name: 'Cackle', beats_left: 2 })).toBe(2);
  });
});
