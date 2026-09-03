import { describe, it, expect } from 'vitest';
import {
  hasSprite, spriteFor, spriteClipFor, facingRow, facingDegrees, terrainTileUrl, spriteAssetUrl,
  isSafeAssetPath, SPRITE_CLIPS, CLIP_FPS, LOOPING_CLIPS, FACING_DEGREES,
} from './sprites';
import { makeSpriteManifest, makeActiveMove } from '../test/payloads';

describe('utils/sprites', () => {
  it('knows every clip the intake tool writes, with a frame rate each', () => {
    for (const clip of SPRITE_CLIPS) expect(CLIP_FPS[clip]).toBeGreaterThan(0);
    expect(LOOPING_CLIPS.has('idle')).toBe(true);
    expect(LOOPING_CLIPS.has('death')).toBe(false);
  });

  it('resolves a sheet set by sprite_key and rejects unknown or unsafe keys', () => {
    const manifest = makeSpriteManifest();
    expect(hasSprite(manifest, 'jean')).toBe(true);
    expect(spriteFor(manifest, 'jean').clips.idle.frames).toBe(4);
    expect(hasSprite(manifest, 'kingslime')).toBe(false);
    expect(hasSprite(manifest, 'constructor')).toBe(false);
    expect(spriteFor(manifest, null)).toBeNull();
    expect(hasSprite(null, 'jean')).toBe(false);
    expect(hasSprite({ sprites: { x: { clips: {} } } }, 'x')).toBe(false);
    expect(hasSprite({ sprites: { x: { clips: { idle: { file: '../evil.png' } } } } }, 'x')).toBe(false);
  });

  describe('spriteClipFor', () => {
    const src = (type, phase = 'windup') => ({ isSource: true, isTarget: false, anim: { type, phase } });
    const tgt = (phase) => ({ isSource: false, isTarget: true, anim: { type: 'attack', phase } });

    it('dying wins over everything', () => {
      expect(spriteClipFor({ isDying: true, animationStates: [src('attack')] })).toBe('death');
    });
    it('sources strike, cast, walk or defend by config type', () => {
      expect(spriteClipFor({ animationStates: [src('heavy_attack')] })).toBe('attack');
      expect(spriteClipFor({ animationStates: [src('projectile', 'strike')] })).toBe('attack');
      expect(spriteClipFor({ animationStates: [src('buff')] })).toBe('cast');
      expect(spriteClipFor({ animationStates: [src('defend')] })).toBe('defend');
      expect(spriteClipFor({ animationStates: [src('dash')] })).toBe('walk');
      expect(spriteClipFor({ animationStates: [src('mystery')] })).toBe('attack');
      expect(spriteClipFor({ animationStates: [null, { anim: null }, src('drain', 'impact')] })).toBe('cast');
    });
    it('targets flinch only during impact', () => {
      expect(spriteClipFor({ animationStates: [tgt('impact')] })).toBe('hurt');
      expect(spriteClipFor({ animationStates: [tgt('windup')] })).toBe('idle');
    });
    it('a source that is also being hit keeps swinging', () => {
      expect(spriteClipFor({ animationStates: [tgt('impact'), src('attack')] })).toBe('attack');
    });
    it('reads intent off a pending move, using the shared pending rule', () => {
      const move = (o) => makeActiveMove(o);
      expect(spriteClipFor({ currentMove: move({ name: 'Dodge', display_name: 'Dodge', category: 'Maneuver' }) })).toBe('defend');
      expect(spriteClipFor({ currentMove: move({ name: '', display_name: 'Brace Position' }) })).toBe('defend');
      expect(spriteClipFor({ currentMove: move({ name: 'Advance' }) })).toBe('walk');
      expect(spriteClipFor({ currentMove: move({ name: 'Take Ground', current_stage: 0 }) })).toBe('walk');
      expect(spriteClipFor({ currentMove: move({ name: 'Tactical Retreat' }) })).toBe('walk');
      expect(spriteClipFor({ currentMove: move({ name: 'Advance', current_stage: 3 }) })).toBe('idle');
      expect(spriteClipFor({ currentMove: move({ name: 'Advance', current_stage: 2 }) })).toBe('idle');
      expect(spriteClipFor({ currentMove: move({ name: 'Power Strike', category: 'Offensive' }) })).toBe('idle');
      expect(spriteClipFor()).toBe('idle');
    });
  });

  describe('facing', () => {
    it('normalises strings and degrees', () => {
      expect(facingDegrees('E')).toBe(90);
      expect(facingDegrees('ne')).toBe(45);
      expect(facingDegrees(-90)).toBe(270);
      expect(facingDegrees(450)).toBe(90);
      expect(facingDegrees('bogus')).toBe(0);
      expect(facingDegrees(undefined)).toBe(0);
      expect(facingDegrees(NaN)).toBe(0);
      expect(Object.keys(FACING_DEGREES)).toHaveLength(8);
    });
    it('maps cardinal strings to rows and mirrors east', () => {
      expect(facingRow('S')).toEqual({ row: 0, mirror: false });
      expect(facingRow('W')).toEqual({ row: 1, mirror: false });
      expect(facingRow('E')).toEqual({ row: 1, mirror: true });
      expect(facingRow('N')).toEqual({ row: 2, mirror: false });
    });
    it('collapses diagonals unmirrored and accepts degrees', () => {
      expect(facingRow('SE')).toEqual({ row: 0, mirror: false });
      expect(facingRow('NW')).toEqual({ row: 2, mirror: false });
      expect(facingRow('NE')).toEqual({ row: 2, mirror: false });
      expect(facingRow(90)).toEqual({ row: 1, mirror: true });
      expect(facingRow(-90)).toEqual({ row: 1, mirror: false });
    });
    it('honours a custom row order', () => {
      expect(facingRow('W', ['west', 'south', 'north']).row).toBe(0);
    });
  });

  it('only lets plain relative asset paths into a url()', () => {
    expect(isSafeAssetPath('sprites/jean/idle.png')).toBe(true);
    expect(isSafeAssetPath('terrain/verdette_caverns/crystal_wall.png')).toBe(true);
    expect(isSafeAssetPath('../x.png')).toBe(false);
    expect(isSafeAssetPath('/abs.png')).toBe(false);
    expect(isSafeAssetPath('a"),url(x.png')).toBe(false);
    expect(isSafeAssetPath('sprites/jean/idle.svg')).toBe(false);
    expect(isSafeAssetPath(42)).toBe(false);
    expect(spriteAssetUrl('sprites/jean/idle.png')).toMatch(/\/assets\/sprites\/jean\/idle\.png$/);
    expect(spriteAssetUrl('javascript:alert(1)')).toBeNull();
  });

  it('builds tile urls only from own, safe manifest entries', () => {
    const manifest = makeSpriteManifest();
    expect(terrainTileUrl(manifest, 'verdette_caverns', 'crystal_wall')).toMatch(/terrain\/verdette_caverns\/crystal_wall\.png$/);
    expect(terrainTileUrl(manifest, 'verdette_caverns', 'nope')).toBeNull();
    expect(terrainTileUrl(manifest, 'verdette_caverns', 'constructor')).toBeNull();
    expect(terrainTileUrl(manifest, 'toString', 'crystal_wall')).toBeNull();
    expect(terrainTileUrl(null, 'verdette_caverns', 'crystal_wall')).toBeNull();
  });
});
