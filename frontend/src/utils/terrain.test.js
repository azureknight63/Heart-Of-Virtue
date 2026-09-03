import { describe, it, expect } from 'vitest';
import {
  hasTerrain, terrainReader, terrainKindAt, terrainElevationAt, terrainVariant, terrainLabel,
  terrainKindsPresent, regionLabel, engagementTone, legendNotes, TERRAIN_KINDS, TERRAIN_STYLE,
} from './terrain';
import { makeTerrain } from '../test/payloads';
import { colors } from '../styles/theme';

describe('utils/terrain', () => {
  it('recognises a usable payload and rejects junk', () => {
    expect(hasTerrain(makeTerrain())).toBe(true);
    expect(hasTerrain(null)).toBe(false);
    expect(hasTerrain({})).toBe(false);
    expect(hasTerrain({ rows: [], codes: {}, width: 0, height: 0 })).toBe(false);
    expect(terrainReader(null)).toBeNull();
  });

  it('decodes kinds and elevation from the compact rows', () => {
    const t = makeTerrain();
    expect(terrainKindAt(t, 0, 0)).toBe('open');
    expect(terrainKindAt(t, 4, 0)).toBe('boulder');
    expect(terrainKindAt(t, 2, 2)).toBe('shelf');
    expect(terrainElevationAt(t, 2, 2)).toBe(1);
    expect(terrainElevationAt(t, 0, 0)).toBe(0);
    const reader = terrainReader(t);
    expect(reader.kindAt(5, 0)).toBe('wall');
    expect(reader.elevationAt(3, 3)).toBe(1);
  });

  it('returns null off-grid, for unknown codes and for kinds the engine never emits', () => {
    const t = makeTerrain({ rows: ['oo?c'], codes: { o: 'open', c: 'constructor' } });
    expect(terrainKindAt(t, -1, 0)).toBeNull();
    expect(terrainKindAt(t, 0, 99)).toBeNull();
    expect(terrainKindAt(t, 2, 0)).toBeNull();
    expect(terrainKindAt(t, 3, 0)).toBeNull();
    expect(terrainElevationAt(t, 0, 99)).toBe(0);
    expect(terrainElevationAt(makeTerrain({ elevation: 'nope' }), 0, 0)).toBe(0);
  });

  it('reads palette and legend with fallbacks', () => {
    const t = makeTerrain();
    expect(terrainVariant(t, 'rough')).toBe('shallow_water');
    expect(terrainVariant(t, 'nonsense')).toBe('nonsense');
    expect(terrainVariant(t, 'constructor')).toBe('constructor');
    expect(terrainLabel(t, 'boulder')).toBe('Boulder');
    expect(terrainLabel(null, 'boulder')).toBe('boulder');
    expect(terrainLabel(t, 'toString')).toBe('toString');
  });

  it('lists the non-open kinds present in legend order, bounded by the declared size', () => {
    expect(terrainKindsPresent(makeTerrain())).toEqual(['rough', 'hazard', 'shelf', 'boulder', 'wall']);
    expect(terrainKindsPresent(null)).toEqual([]);
    // A row longer than the declared width is not scanned past it.
    expect(terrainKindsPresent(makeTerrain({ width: 2, height: 1, rows: ['oowww'] }))).toEqual([]);
  });

  it('labels regions from the engine, falling back to the id', () => {
    expect(regionLabel(makeTerrain())).toBe('Verdette Caverns');
    expect(regionLabel({ region: 'somewhere_else' })).toBe('somewhere else');
    expect(regionLabel('wailing_badlands')).toBe('wailing badlands');
    expect(regionLabel(null)).toBe('');
    expect(regionLabel({})).toBe('');
  });

  it('builds legend notes from the server legend', () => {
    const t = makeTerrain();
    expect(legendNotes(t, 'boulder')).toEqual(['blocks', 'cover -20']);
    expect(legendNotes(t, 'wall')).toEqual(['blocks', 'no line of sight']);
    expect(legendNotes(t, 'hazard')).toEqual(['slow', 'hurts']);
    expect(legendNotes(t, 'shelf')).toEqual(['+10 to hit']);
    expect(legendNotes(t, 'open')).toEqual([]);
    expect(legendNotes({ legend: {} }, 'shelf')).toEqual([]);
  });

  it('tones an engagement by the sign of its hit modifier', () => {
    expect(engagementTone({ hit_modifier: 10 })).toBe(colors.primary);
    expect(engagementTone({ hit_modifier: -20 })).toBe(colors.danger);
    expect(engagementTone({ hit_modifier: 0 })).toBe(colors.text.muted);
    expect(engagementTone(null)).toBe(colors.text.muted);
  });

  it('has a style for every kind the engine emits', () => {
    for (const kind of TERRAIN_KINDS) expect(TERRAIN_STYLE[kind].radius).toBeDefined();
  });
});
