# Tile Caching System

## Overview

The tile caching system provides seamless tile loading for players by:
1. **Caching visited tiles** - Tiles you've already visited are stored in memory
2. **Pre-fetching adjacent tiles** - When you visit a tile, all 8 surrounding tiles are loaded in the background
3. **Optimistic UI updates** - Movement feels instant when moving to cached tiles

## Architecture

### Frontend Components

#### `TileCache.js`
- **Location**: `frontend/src/utils/TileCache.js`
- **Purpose**: Singleton cache manager for tile data
- **Features**:
  - LRU (Least Recently Used) eviction when cache is full (default: 200 tiles)
  - Batch fetching of multiple tiles in a single request
  - Background prefetching of adjacent tiles
  - Prevents duplicate requests for the same tile

#### `useWorld` Hook
- **Location**: `frontend/src/hooks/useApi.js`
- **Integration**: Automatically uses tile cache when moving
- **Behavior**:
  - Checks cache before making API requests
  - Optimistically updates UI with cached data
  - Always validates with server for authoritative data
  - Caches fresh data from server responses

### Backend Endpoints

#### Single Tile Fetch
- **Endpoint**: `GET /world/tile?x={x}&y={y}`
- **Purpose**: Fetch a single tile's data
- **Returns**: Tile data including items, NPCs, objects, exits

#### Batch Tile Fetch
- **Endpoint**: `POST /world/tiles/batch`
- **Purpose**: Fetch multiple tiles in one request
- **Body**: `{ "coordinates": [{ "x": 0, "y": 0 }, ...] }`
- **Limit**: Maximum 20 tiles per request
- **Returns**: Array of tile data

## Usage

### Automatic Usage
The caching system works automatically when using the `useWorld` hook:

```javascript
const { location, moveToLocation } = useWorld()

// Movement automatically uses cache
await moveToLocation('north')
```

### Manual Cache Access
You can also access the cache directly:

```javascript
import tileCache from '../utils/TileCache'

// Check if tile is cached
if (tileCache.has(x, y)) {
  const tile = tileCache.get(x, y)
}

// Manually fetch and cache a tile
const tile = await tileCache.fetchTile(x, y)

// Prefetch adjacent tiles
await tileCache.prefetchAdjacent(x, y)

// Get cache statistics
const stats = tileCache.getStats()
console.log(`Cache: ${stats.size}/${stats.maxSize} (${stats.utilizationPercent}%)`)
```

## Performance Benefits

### Before Caching
- Every movement required a network request
- Average movement time: ~100-300ms (network dependent)
- Noticeable lag when exploring

### After Caching
- Cached movements: ~0-5ms (instant)
- Uncached movements: ~100-300ms (same as before)
- Adjacent tiles pre-loaded in background
- **Result**: Most movements feel instant

## Cache Management

### Eviction Policy
- Uses LRU (Least Recently Used) eviction
- Default capacity: 200 tiles
- Automatically evicts oldest tiles when full

### Cache Invalidation
Currently, cached tiles are never invalidated. This is acceptable because:
- Tile data rarely changes during a session
- Cache is cleared on page refresh
- Future enhancement: Add TTL (Time To Live) or manual invalidation

## Future Enhancements

1. **Persistent Cache**: Store cache in localStorage/IndexedDB
2. **Cache Invalidation**: Add TTL or server-side invalidation signals
3. **Predictive Prefetching**: Prefetch based on player movement patterns
4. **Compression**: Compress cached tile data to store more tiles
5. **Priority Queue**: Prioritize prefetching tiles in the direction of movement

## Debugging

Enable cache debugging:

```javascript
import tileCache from '../utils/TileCache'

// Log cache stats
console.log(tileCache.getStats())

// Export cache data
const cacheData = tileCache.export()
console.log('Cached tiles:', Object.keys(cacheData))

// Clear cache
tileCache.clear()
```

## Testing

To test the caching system:

1. **Check cache hits**: Open DevTools Network tab, move around - you should see fewer `/world/tile` requests
2. **Verify prefetching**: After visiting a tile, check Network tab for batch requests to `/world/tiles/batch`
3. **Test optimistic updates**: Movement to adjacent tiles should feel instant
4. **Monitor cache size**: Use `tileCache.getStats()` to ensure cache isn't growing unbounded
