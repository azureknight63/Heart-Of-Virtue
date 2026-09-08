import { describe, it, expect } from 'vitest';
import { isLiving, isHostileEntity, hostilityTokenFor, HOSTILITY_TOKENS } from './combatEntities';

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

describe('isHostileEntity', () => {
  it('reads the room-NPC spelling', () => {
    expect(isHostileEntity({ is_hostile: true })).toBe(true);
    expect(isHostileEntity({ is_hostile: false })).toBe(false);
  });

  it('reads the combat-target-card spelling as its complement', () => {
    expect(isHostileEntity({ is_ally: false })).toBe(true);
    expect(isHostileEntity({ is_ally: true })).toBe(false);
  });

  it('prefers the direct statement when a payload carries both', () => {
    expect(isHostileEntity({ is_hostile: true, is_ally: true })).toBe(true);
  });

  it('answers null — never a guess — when the payload is silent', () => {
    // The whole point: a default of "friendly" is how a hostile ends up
    // wearing an ally badge.
    expect(isHostileEntity({ name: 'Stranger' })).toBeNull();
    expect(isHostileEntity({ is_hostile: 'yes' })).toBeNull();
    expect(isHostileEntity({ is_ally: null })).toBeNull();
    expect(isHostileEntity(null)).toBeNull();
    expect(isHostileEntity(undefined)).toBeNull();
  });
});

describe('hostilityTokenFor', () => {
  it('carries a word and a glyph as well as a colour', () => {
    // State is never conveyed by colour alone, and this is the state that
    // decides whether the player swings at their own ally.
    for (const token of Object.values(HOSTILITY_TOKENS)) {
      expect(token.label).toMatch(/^[A-Z]+$/);
      expect(token.glyph.length).toBeGreaterThan(0);
      expect(token.color).toMatch(/^#/);
      expect(token.tint).toMatch(/^#/);
    }
    expect(HOSTILITY_TOKENS.hostile.label).not.toBe(HOSTILITY_TOKENS.ally.label);
    expect(HOSTILITY_TOKENS.hostile.color).not.toBe(HOSTILITY_TOKENS.ally.color);
  });

  it('maps each side to its own token', () => {
    expect(hostilityTokenFor({ is_ally: false })).toBe(HOSTILITY_TOKENS.hostile);
    expect(hostilityTokenFor({ is_hostile: true })).toBe(HOSTILITY_TOKENS.hostile);
    expect(hostilityTokenFor({ is_ally: true })).toBe(HOSTILITY_TOKENS.ally);
    // NOT ally: `is_hostile: false` is "not aggressive", not "on Jean's side".
    // This line asserted the ally badge and was written alongside the code
    // that produced it, so it pinned the defect rather than catching it.
    expect(hostilityTokenFor({ is_hostile: false })).toBeNull();
  });

  it('has no token for a silent payload', () => {
    expect(hostilityTokenFor({ name: 'Stranger' })).toBeNull();
    expect(hostilityTokenFor(null)).toBeNull();
  });
});

describe('hostilityTokenFor — ALLY needs a positive ally signal', () => {
  // RoomContents documents the reasoning and then hostilityTokenFor broke it:
  // `is_hostile: false` means "not aggressive" — a villager, a merchant — not
  // "on Jean's side". Badging those ALLY states something the payload never
  // said, which is the same class of mistake as badging a hostile friendly.
  // Latent rather than live (the two spellings never co-occur today: only
  // NPCSerializer emits is_hostile and only _build_target_entry emits
  // is_ally), so this guards the invariant before a serializer change makes
  // it reachable.
  it('gives a non-aggressive room NPC no token rather than an ALLY badge', () => {
    expect(hostilityTokenFor({ is_hostile: false })).toBeNull();
  });

  it('still badges a genuine party member from the target picker', () => {
    expect(hostilityTokenFor({ is_ally: true })?.label).toBe('ALLY');
  });

  it('still badges a hostile from either spelling', () => {
    expect(hostilityTokenFor({ is_hostile: true })?.label).toBe('HOSTILE');
    expect(hostilityTokenFor({ is_ally: false })?.label).toBe('HOSTILE');
  });

  it('shows nothing when the payload is silent', () => {
    expect(hostilityTokenFor({})).toBeNull();
    expect(hostilityTokenFor(null)).toBeNull();
  });
});
