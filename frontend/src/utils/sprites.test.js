import { describe, it, expect } from 'vitest';
import {
  hasSprite, spriteFor, spriteClipFor, facingRow, terrainTileUrl, spriteAssetUrl,
  SPRITE_CLIPS, CLIP_FPS, LOOPING_CLIPS,
} from './sprites';
import { makeSpriteManifest } from '../test/payloads';

describe('utils/sprites', () => {
  it('knows every clip the intake tool writes, with a frame rate each', () => {
    for (const clip of SPRITE_CLIPS) expect(CLIP_FPS[clip]).toBeGreaterThan(0);
    expect(LOOPING_CLIPS.has('idle')).toBe(true);
    expect(LOOPING_CLIPS.has('death')).toBe(false);
  });

  it('resolves a sheet set by sprite_key and rejects unknown keys', () => {
    const manifest = makeSpriteManifest();
    expect(hasSprite(manifest, 'jean')).toBe(true);
    expect(spriteFor(manifest, 'jean').clips.idle.frames).toBe(4);
    expect(hasSprite(manifest, 'kingslime')).toBe(false);
    expect(spriteFor(manifest, null)).toBeNull();
    expect(hasSprite(null, 'jean')).toBe(false);
    expect(hasSprite({ sprites: { x: { clips: {} } } }, 'x')).toBe(false);
  });

  describe('spriteClipFor', () => {
    const src = (type, phase = 'windup') => ({ isSource: true, isTarget: false, anim: { type, phase } });
    const tgt = (phase) => ({ isSource: false, isTarget: true, anim: { type: 'attack', phase } });

    it('dying wins over everything', () => {
      expect(spriteClipFor({ isDying: true, animationStates: [src('attack')] })).toBe('death');
    });
    it('sources strike or cast by config type', () => {
      expect(spriteClipFor({ animationStates: [src('heavy_attack')] })).toBe('attack');
      expect(spriteClipFor({ animationStates: [src('projectile', 'strike')] })).toBe('attack');
      expect(spriteClipFor({ animationStates: [src('buff')] })).toBe('cast');
      expect(spriteClipFor({ animationStates: [src('defend')] })).toBe('defend');
      expect(spriteClipFor({ animationStates: [{ isSource: true, anim: { config: { type: 'drain' }, phase: 'impact' } }] })).toBe('cast');
    });
    it('targets flinch only during impact', () => {
      expect(spriteClipFor({ animationStates: [tgt('impact')] })).toBe('hurt');
      expect(spriteClipFor({ animationStates: [tgt('windup')] })).toBe('idle');
    });
    it('a source that is also being hit keeps swinging', () => {
      expect(spriteClipFor({ animationStates: [tgt('impact'), src('attack')] })).toBe('attack');
    });
    it('reads intent off a pending move', () => {
      expect(spriteClipFor({ currentMove: { name: 'Dodge', current_stage: 1 } })).toBe('defend');
      expect(spriteClipFor({ currentMove: { display_name: 'Brace Position' } })).toBe('defend');
      expect(spriteClipFor({ currentMove: { name: 'Advance', current_stage: 1 } })).toBe('walk');
      expect(spriteClipFor({ currentMove: { name: 'Tactical Retreat' } })).toBe('walk');
      expect(spriteClipFor({ currentMove: { name: 'Advance', current_stage: 3 } })).toBe('idle');
      expect(spriteClipFor({ currentMove: { name: 'Power Strike' } })).toBe('idle');
      expect(spriteClipFor()).toBe('idle');
    });
  });

  describe('facingRow', () => {
    it('maps cardinal strings to rows and mirrors east', () => {
      expect(facingRow('S')).toEqual({ row: 0, mirror: false });
      expect(facingRow('W')).toEqual({ row: 1, mirror: false });
      expect(facingRow('E')).toEqual({ row: 1, mirror: true });
      expect(facingRow('N')).toEqual({ row: 2, mirror: false });
    });
    it('collapses diagonals and accepts degrees', () => {
      expect(facingRow('SE')).toEqual({ row: 0, mirror: false });
      expect(facingRow('NW')).toEqual({ row: 2, mirror: false });
      expect(facingRow('NE')).toEqual({ row: 2, mirror: false });
      expect(facingRow(90)).toEqual({ row: 1, mirror: true });
      expect(facingRow(-90)).toEqual({ row: 1, mirror: false });
      expect(facingRow(undefined)).toEqual({ row: 2, mirror: false });
      expect(facingRow('bogus')).toEqual({ row: 2, mirror: false });
    });
    it('honours a custom row order', () => {
      expect(facingRow('W', ['west', 'south', 'north']).row).toBe(0);
    });
  });

  it('builds asset urls and tile urls', () => {
    expect(spriteAssetUrl('sprites/jean/idle.png')).toMatch(/\/assets\/sprites\/jean\/idle\.png$/);
    const manifest = makeSpriteManifest();
    expect(terrainTileUrl(manifest, 'verdette_caverns', 'crystal_wall')).toMatch(/terrain\/verdette_caverns\/crystal_wall\.png$/);
    expect(terrainTileUrl(manifest, 'verdette_caverns', 'nope')).toBeNull();
    expect(terrainTileUrl(null, 'verdette_caverns', 'crystal_wall')).toBeNull();
  });
});
