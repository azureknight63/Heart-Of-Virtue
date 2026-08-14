import { describe, it, expect } from 'vitest';
import { isLiving } from './combatEntities';

describe('isLiving', () => {
  it('reads the canonical hp field', () => {
    expect(isLiving({ hp: 10 })).toBe(true);
    expect(isLiving({ hp: 0 })).toBe(false);
    expect(isLiving({ hp: -5 })).toBe(false);
  });

  it('falls back to the nested legacy health shape', () => {
    expect(isLiving({ health: { current: 3 } })).toBe(true);
    expect(isLiving({ health: { current: 0 } })).toBe(false);
  });

  it('prefers hp over health.current when both are present', () => {
    expect(isLiving({ hp: 0, health: { current: 99 } })).toBe(false);
    expect(isLiving({ hp: 99, health: { current: 0 } })).toBe(true);
  });

  it('treats a combatant with no HP information as alive', () => {
    // Deliberate: several payload shapes omit HP, and defaulting those to
    // dead would silently drop live combatants off the map.
    expect(isLiving({ name: 'Gorran' })).toBe(true);
  });

  it('is false for a missing entity rather than throwing', () => {
    // Safe to hand straight to .filter() over a list with holes — which the
    // three hand-rolled copies this replaced were not.
    expect(isLiving(null)).toBe(false);
    expect(isLiving(undefined)).toBe(false);
    expect([{ hp: 1 }, null, { hp: 0 }].filter(isLiving)).toEqual([{ hp: 1 }]);
  });
});
