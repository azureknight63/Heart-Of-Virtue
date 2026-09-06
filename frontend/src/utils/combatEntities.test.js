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

  it('treats EVERY way of carrying no HP number as alive', () => {
    // The previous case hand-picked one spelling of "no HP" — an absent `hp`
    // with no `health` block — and passed while three of the other seven
    // spellings returned dead. A hand-listed subset of a product is the shape
    // that lets a predicate contradict its own docstring, so the product is
    // enumerated instead of sampled.
    //
    // The rule under test is the docstring's, not the implementation's: an
    // entity is alive unless it carries an HP NUMBER that is <= 0. So every
    // combination of a non-numeric `hp` with a non-numeric `health.current`
    // must be alive, whichever nullish spelling each one uses.
    const noHp = [
      ['absent', {}],
      ['null', { hp: null }],
      ['undefined', { hp: undefined }],
    ];
    const noHealth = [
      ['absent', {}],
      ['empty block', { health: {} }],
      ['null current', { health: { current: null } }],
      ['undefined current', { health: { current: undefined } }],
    ];
    const dead = [];
    for (const [hpLabel, hpPart] of noHp) {
      for (const [healthLabel, healthPart] of noHealth) {
        const entity = { name: 'Gorran', ...hpPart, ...healthPart };
        if (!isLiving(entity)) dead.push(`hp ${hpLabel} + health ${healthLabel}`);
      }
    }
    // Guard-the-guard: an empty product would agree with any predicate at all.
    expect(noHp.length * noHealth.length).toBe(12);
    expect(
      dead,
      'combatEntities.js isLiving() reported these HP-less shapes as DEAD, but its '
      + 'docstring promises "alive, or carries no HP information at all": '
      + dead.join(' | ')
    ).toEqual([]);
  });

  it('still reads a real zero through either spelling', () => {
    // The other direction of the same widening: loosening the nullish check
    // must not start treating an actual 0 as "no information".
    expect(isLiving({ hp: 0, health: { current: null } })).toBe(false);
    expect(isLiving({ hp: null, health: { current: 0 } })).toBe(false);
  });

  it('is false for a missing entity rather than throwing', () => {
    // Safe to hand straight to .filter() over a list with holes — which the
    // three hand-rolled copies this replaced were not.
    expect(isLiving(null)).toBe(false);
    expect(isLiving(undefined)).toBe(false);
    expect([{ hp: 1 }, null, { hp: 0 }].filter(isLiving)).toEqual([{ hp: 1 }]);
  });
});
