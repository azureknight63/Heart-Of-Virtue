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

  it('yields null on a missing manifest, a bad status, or no fetch at all', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    await expect(loadSpriteManifest()).resolves.toBeNull();
    resetSpriteManifestCache();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    await expect(loadSpriteManifest()).resolves.toBeNull();
    resetSpriteManifestCache();
    await expect(loadSpriteManifest(undefined)).resolves.toBeNull();
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
