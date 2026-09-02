import { describe, it, expect } from 'vitest';
import {
  hasTerrain, terrainKindAt, terrainElevationAt, terrainVariant, terrainLabel,
  terrainKindsPresent, regionLabel, engagementTone, TERRAIN_KINDS, TERRAIN_STYLE,
} from './terrain';
import { makeTerrain } from '../test/payloads';
import { colors } from '../styles/theme';

describe('utils/terrain', () => {
  it('recognises a usable payload and rejects junk', () => {
    expect(hasTerrain(makeTerrain())).toBe(true);
    expect(hasTerrain(null)).toBe(false);
    expect(hasTerrain({})).toBe(false);
    expect(hasTerrain({ rows: [], codes: {}, width: 0, height: 0 })).toBe(false);
  });

  it('decodes kinds and elevation from the compact rows', () => {
    const t = makeTerrain();
    expect(terrainKindAt(t, 0, 0)).toBe('open');
    expect(terrainKindAt(t, 4, 0)).toBe('boulder');
    expect(terrainKindAt(t, 2, 2)).toBe('shelf');
    expect(terrainElevationAt(t, 2, 2)).toBe(1);
    expect(terrainElevationAt(t, 0, 0)).toBe(0);
  });

  it('returns null off-grid and for unknown codes', () => {
    const t = makeTerrain({ rows: ['oo?'] });
    expect(terrainKindAt(t, -1, 0)).toBeNull();
    expect(terrainKindAt(t, 0, 99)).toBeNull();
    expect(terrainKindAt(t, 2, 0)).toBeNull();
    expect(terrainElevationAt(t, 0, 99)).toBe(0);
  });

  it('reads palette and legend with fallbacks', () => {
    const t = makeTerrain();
    expect(terrainVariant(t, 'rough')).toBe('shallow_water');
    expect(terrainVariant(t, 'nonsense')).toBe('nonsense');
    expect(terrainLabel(t, 'boulder')).toBe('Boulder');
    expect(terrainLabel(null, 'boulder')).toBe('boulder');
  });

  it('lists the non-open kinds present in legend order', () => {
    expect(terrainKindsPresent(makeTerrain())).toEqual(['rough', 'hazard', 'shelf', 'boulder', 'wall']);
    expect(terrainKindsPresent(null)).toEqual([]);
  });

  it('labels regions', () => {
    expect(regionLabel('verdette_caverns')).toBe('Verdette Caverns');
    expect(regionLabel('somewhere_else')).toBe('somewhere else');
    expect(regionLabel(null)).toBe('');
  });

  it('tones an engagement by the sign of its hit modifier', () => {
    expect(engagementTone({ hit_modifier: 10 }, colors)).toBe(colors.primary);
    expect(engagementTone({ hit_modifier: -20 }, colors)).toBe(colors.danger);
    expect(engagementTone({ hit_modifier: 0 }, colors)).toBe(colors.text.muted);
    expect(engagementTone(null, colors)).toBe(colors.text.muted);
  });

  it('has a style for every kind the engine emits', () => {
    for (const kind of TERRAIN_KINDS) expect(TERRAIN_STYLE[kind]).toBeDefined();
  });
});
