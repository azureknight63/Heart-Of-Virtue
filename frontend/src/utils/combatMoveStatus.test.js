import { describe, it, expect } from 'vitest';
import { displayNameOf, formatCombatMoveStatus } from './combatMoveStatus';

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
