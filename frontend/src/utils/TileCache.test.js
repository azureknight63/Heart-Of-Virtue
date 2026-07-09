import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TileCache } from './TileCache';
import apiEndpoints from '../api/endpoints';

// Mock apiEndpoints
vi.mock('../api/endpoints', () => ({
  default: {
    world: {
      getTile: vi.fn(),
      getTilesBatch: vi.fn()
    }
  }
}));

describe('TileCache', () => {
  let tileCache;

  beforeEach(() => {
    tileCache = new TileCache(3); // Small cache for testing eviction
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  it('sets and gets tiles', () => {
    const tileData = { name: 'Forest' };
    tileCache.set(0, 0, tileData);
    expect(tileCache.has(0, 0)).toBe(true);
    expect(tileCache.get(0, 0).name).toBe('Forest');
  });

  it('returns null for non-existent tiles', () => {
    expect(tileCache.get(1, 1)).toBeNull();
  });

  it('evicts oldest tiles when max size is reached', () => {
    tileCache.set(0, 0, { id: 0 });
    vi.advanceTimersByTime(100);
    tileCache.set(1, 1, { id: 1 });
    vi.advanceTimersByTime(100);
    tileCache.set(2, 2, { id: 2 });
    vi.advanceTimersByTime(100);
    
    // Access 0,0 to make it newer than 1,1
    tileCache.get(0, 0);
    vi.advanceTimersByTime(100);
    
    // Add 4th tile, should evict 1,1 (oldest)
    tileCache.set(3, 3, { id: 3 });
    
    expect(tileCache.has(1, 1)).toBe(false);
    expect(tileCache.has(0, 0)).toBe(true);
    expect(tileCache.has(2, 2)).toBe(true);
    expect(tileCache.has(3, 3)).toBe(true);
  });

  it('gets adjacent coordinates', () => {
    const adj = tileCache.getAdjacentCoordinates(0, 0);
    expect(adj).toHaveLength(8);
    expect(adj).toContainEqual({ x: 0, y: -1 });
    expect(adj).toContainEqual({ x: 1, y: 1 });
  });

  it('fetches a tile from API if not in cache', async () => {
    const mockTile = { id: 'tile1', name: 'Mountain' };
    apiEndpoints.world.getTile.mockResolvedValue({
      data: { success: true, tile: mockTile }
    });

    const tile = await tileCache.fetchTile(5, 5);
    
    expect(apiEndpoints.world.getTile).toHaveBeenCalledWith(5, 5);
    expect(tile.name).toBe('Mountain');
    expect(tileCache.has(5, 5)).toBe(true);
  });

  it('handles API failure when fetching tile', async () => {
    apiEndpoints.world.getTile.mockRejectedValue(new Error('API Error'));
    
    const tile = await tileCache.fetchTile(5, 5);
    expect(tile).toBeNull();
    expect(tileCache.has(5, 5)).toBe(false);
  });

  it('fetches tiles in batch', async () => {
    const mockTiles = [
      { x: 0, y: 0, id: 't1' },
      { x: 0, y: 1, id: 't2' }
    ];
    apiEndpoints.world.getTilesBatch.mockResolvedValue({
      data: { success: true, tiles: mockTiles }
    });

    const tiles = await tileCache.fetchTiles([{ x: 0, y: 0 }, { x: 0, y: 1 }]);
    
    expect(apiEndpoints.world.getTilesBatch).toHaveBeenCalled();
    expect(tiles).toHaveLength(2);
    expect(tileCache.has(0, 0)).toBe(true);
    expect(tileCache.has(0, 1)).toBe(true);
  });

  it('clears the cache', () => {
    tileCache.set(0, 0, { id: 0 });
    tileCache.clear();
    expect(tileCache.has(0, 0)).toBe(false);
    expect(tileCache.getStats().size).toBe(0);
  });

  it('returns an already-cached tile without calling the API', async () => {
    tileCache.set(5, 5, { name: 'Cached Mountain' });
    const tile = await tileCache.fetchTile(5, 5);

    expect(tile.name).toBe('Cached Mountain');
    expect(apiEndpoints.world.getTile).not.toHaveBeenCalled();
  });

  it('returns null when the tile fetch succeeds but the server reports failure', async () => {
    apiEndpoints.world.getTile.mockResolvedValue({ data: { success: false } });
    const tile = await tileCache.fetchTile(2, 2);

    expect(tile).toBeNull();
    expect(tileCache.has(2, 2)).toBe(false);
  });

  it('waits for an in-flight fetch of the same tile instead of firing a second request', async () => {
    let resolveFetch;
    apiEndpoints.world.getTile.mockReturnValue(new Promise((r) => { resolveFetch = r; }));

    const first = tileCache.fetchTile(7, 7);
    const second = tileCache.fetchTile(7, 7);

    resolveFetch({ data: { success: true, tile: { name: 'Shared Tile' } } });
    await vi.advanceTimersByTimeAsync(50);

    const [firstResult, secondResult] = await Promise.all([first, second]);
    expect(apiEndpoints.world.getTile).toHaveBeenCalledTimes(1);
    expect(firstResult.name).toBe('Shared Tile');
    expect(secondResult.name).toBe('Shared Tile');
  });

  it('resolves the waiting caller with null when the in-flight fetch ultimately fails', async () => {
    let rejectFetch;
    apiEndpoints.world.getTile.mockReturnValue(new Promise((_, r) => { rejectFetch = r; }));

    const first = tileCache.fetchTile(8, 8);
    const second = tileCache.fetchTile(8, 8);

    rejectFetch(new Error('offline'));
    await vi.advanceTimersByTimeAsync(50);

    const [firstResult, secondResult] = await Promise.all([first, second]);
    expect(firstResult).toBeNull();
    expect(secondResult).toBeNull();
  });

  it('skips the batch request entirely when every coordinate is already cached', async () => {
    tileCache.set(0, 0, { id: 'cached' });
    const tiles = await tileCache.fetchTiles([{ x: 0, y: 0 }]);

    expect(tiles).toEqual([]);
    expect(apiEndpoints.world.getTilesBatch).not.toHaveBeenCalled();
  });

  it('returns an empty array when the batch endpoint reports failure', async () => {
    apiEndpoints.world.getTilesBatch.mockResolvedValue({ data: { success: false } });
    const tiles = await tileCache.fetchTiles([{ x: 3, y: 3 }]);

    expect(tiles).toEqual([]);
    expect(tileCache.has(3, 3)).toBe(false);
  });

  it('falls back to individual fetches when the batch endpoint fails', async () => {
    apiEndpoints.world.getTilesBatch.mockRejectedValue(new Error('batch offline'));
    apiEndpoints.world.getTile.mockResolvedValue({ data: { success: true, tile: { name: 'Solo' } } });

    const tiles = await tileCache.fetchTiles([{ x: 9, y: 9 }]);

    expect(apiEndpoints.world.getTile).toHaveBeenCalledWith(9, 9);
    expect(tiles[0].name).toBe('Solo');
  });

  it('logs a warning when the background prefetch itself rejects', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(tileCache, 'fetchTiles').mockRejectedValue(new Error('prefetch exploded'));

    await tileCache.prefetchAdjacent(0, 0);
    await vi.advanceTimersByTimeAsync(0);
    expect(warnSpy).toHaveBeenCalledWith('Background tile prefetch failed:', expect.any(Error));
    warnSpy.mockRestore();
  });

  it('prefetches uncached adjacent tiles in the background', async () => {
    apiEndpoints.world.getTilesBatch.mockResolvedValue({ data: { success: true, tiles: [] } });
    await tileCache.prefetchAdjacent(0, 0);

    expect(apiEndpoints.world.getTilesBatch).toHaveBeenCalled();
  });

  it('does not prefetch when all adjacent tiles are already cached', async () => {
    const bigCache = new TileCache(20);
    bigCache.getAdjacentCoordinates(0, 0).forEach(({ x, y }) => bigCache.set(x, y, { id: `${x},${y}` }));
    await bigCache.prefetchAdjacent(0, 0);

    expect(apiEndpoints.world.getTilesBatch).not.toHaveBeenCalled();
  });

  it('fetches a tile and triggers adjacent prefetch via getTileWithPrefetch', async () => {
    apiEndpoints.world.getTile.mockResolvedValue({ data: { success: true, tile: { name: 'Center' } } });
    apiEndpoints.world.getTilesBatch.mockResolvedValue({ data: { success: true, tiles: [] } });

    const tile = await tileCache.getTileWithPrefetch(0, 0);

    expect(tile.name).toBe('Center');
    expect(apiEndpoints.world.getTilesBatch).toHaveBeenCalled();
  });

  it('exports and imports cache data', () => {
    tileCache.set(0, 0, { id: 0, name: 'Start' });
    const exported = tileCache.export();
    
    const newCache = new TileCache();
    newCache.import(exported);
    
    expect(newCache.has(0, 0)).toBe(true);
    expect(newCache.get(0, 0).name).toBe('Start');
  });
});
