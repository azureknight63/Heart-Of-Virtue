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

  it('exports and imports cache data', () => {
    tileCache.set(0, 0, { id: 0, name: 'Start' });
    const exported = tileCache.export();
    
    const newCache = new TileCache();
    newCache.import(exported);
    
    expect(newCache.has(0, 0)).toBe(true);
    expect(newCache.get(0, 0).name).toBe('Start');
  });
});
