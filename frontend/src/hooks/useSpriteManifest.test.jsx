import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useSpriteManifest, loadSpriteManifest, normalizeManifest, resetSpriteManifestCache } from './useSpriteManifest';
import { makeSpriteManifest } from '../test/payloads';

describe('useSpriteManifest', () => {
  beforeEach(() => resetSpriteManifestCache());
  afterEach(() => { vi.unstubAllGlobals(); });

  it('normalizes only the shape the intake tool writes', () => {
    expect(normalizeManifest(null)).toBeNull();
    expect(normalizeManifest('x')).toBeNull();
    const n = normalizeManifest({ frame_size: '32', facings: ['a'], sprites: 'bad', terrain: null });
    expect(n).toEqual({ frame_size: 32, facings: ['south', 'west', 'north'], sprites: {}, terrain: {} });
    expect(normalizeManifest({}).frame_size).toBe(64);
    expect(normalizeManifest({ facings: ['s', 'w', 'n'] }).facings).toEqual(['s', 'w', 'n']);
  });

  it('drops unsafe file paths, unbounded counts and empty entries', () => {
    const n = normalizeManifest({
      sprites: {
        jean: { clips: { idle: { file: 'sprites/jean/idle.png', frames: '4', rows: 3, placeholder: true }, walk: { file: '../x.png' } } },
        ghost: { clips: { idle: { file: 'a"),url(x.png' } } },
        weird: { clips: { idle: { file: 'sprites/w/idle.png', frames: 1e9, rows: 'x' } } },
      },
      terrain: {
        verdette_caverns: { tiles: { crystal_wall: 'terrain/v/crystal_wall.png', bad: '//evil/x.png' } },
        empty: { tiles: { bad: 'javascript:x' } },
        broken: 'nope',
      },
    });
    expect(n.sprites.jean.clips).toEqual({ idle: { file: 'sprites/jean/idle.png', frames: 4, rows: 3, placeholder: true } });
    expect(n.sprites.ghost).toBeUndefined();
    expect(n.sprites.weird.clips.idle).toEqual({ file: 'sprites/w/idle.png', frames: 1, rows: 3 });
    expect(n.terrain).toEqual({ verdette_caverns: { tiles: { crystal_wall: 'terrain/v/crystal_wall.png' } } });
  });

  it('loads once, shares the result, and exposes it through the hook', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(makeSpriteManifest()) });
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useSpriteManifest());
    expect(result.current).toBeNull();
    await waitFor(() => expect(result.current?.sprites?.jean).toBeDefined());
    const second = renderHook(() => useSpriteManifest());
    expect(second.result.current?.sprites?.jean).toBeDefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await expect(loadSpriteManifest()).resolves.toBe(result.current);
  });

  it('settles on a missing manifest and never refetches it', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false });
    vi.stubGlobal('fetch', fetchMock);
    await expect(loadSpriteManifest()).resolves.toBeNull();
    renderHook(() => useSpriteManifest());
    renderHook(() => useSpriteManifest());
    await expect(loadSpriteManifest()).resolves.toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('yields null on a rejected fetch', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    await expect(loadSpriteManifest()).resolves.toBeNull();
  });

  it('yields null when there is no fetch at all', async () => {
    vi.stubGlobal('fetch', undefined);
    await expect(loadSpriteManifest()).resolves.toBeNull();
    const { result } = renderHook(() => useSpriteManifest());
    expect(result.current).toBeNull();
  });

  it('dedupes concurrent loads', async () => {
    let resolve;
    const fetchMock = vi.fn(() => new Promise((r) => { resolve = r; }));
    vi.stubGlobal('fetch', fetchMock);
    const a = loadSpriteManifest();
    const b = loadSpriteManifest();
    expect(a).toBe(b);
    resolve({ ok: true, json: () => Promise.resolve(makeSpriteManifest()) });
    await a;
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
