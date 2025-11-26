/**
 * TileCache - Manages caching of visited and adjacent tiles
 * 
 * Features:
 * - Stores visited tiles in memory
 * - Pre-fetches adjacent unexplored tiles
 * - Provides instant tile data from cache
 * - Automatically manages cache size
 */

import apiEndpoints from '../api/endpoints'

class TileCache {
    constructor(maxCacheSize = 200) {
        // Map of "x,y" -> tile data
        this.cache = new Map()
        // Map of "x,y" -> timestamp (for LRU eviction)
        this.accessTimes = new Map()
        // Set of "x,y" for tiles currently being fetched
        this.pendingFetches = new Set()
        this.maxCacheSize = maxCacheSize
    }

    /**
     * Get a tile key from coordinates
     */
    getTileKey(x, y) {
        return `${x},${y}`
    }

    /**
     * Check if a tile is in cache
     */
    has(x, y) {
        return this.cache.has(this.getTileKey(x, y))
    }

    /**
     * Get a tile from cache
     */
    get(x, y) {
        const key = this.getTileKey(x, y)
        if (this.cache.has(key)) {
            // Update access time for LRU
            this.accessTimes.set(key, Date.now())
            return this.cache.get(key)
        }
        return null
    }

    /**
     * Add a tile to cache
     */
    set(x, y, tileData) {
        const key = this.getTileKey(x, y)

        // Evict oldest entries if cache is full
        if (this.cache.size >= this.maxCacheSize && !this.cache.has(key)) {
            this.evictOldest()
        }

        this.cache.set(key, {
            ...tileData,
            x,
            y,
            cachedAt: Date.now()
        })
        this.accessTimes.set(key, Date.now())
    }

    /**
     * Evict the oldest accessed tile from cache
     */
    evictOldest() {
        let oldestKey = null
        let oldestTime = Infinity

        for (const [key, time] of this.accessTimes.entries()) {
            if (time < oldestTime) {
                oldestTime = time
                oldestKey = key
            }
        }

        if (oldestKey) {
            this.cache.delete(oldestKey)
            this.accessTimes.delete(oldestKey)
        }
    }

    /**
     * Get adjacent tile coordinates (8 directions)
     */
    getAdjacentCoordinates(x, y) {
        return [
            { x: x, y: y - 1 },     // north
            { x: x, y: y + 1 },     // south
            { x: x - 1, y: y },     // west
            { x: x + 1, y: y },     // east
            { x: x - 1, y: y - 1 }, // northwest
            { x: x + 1, y: y - 1 }, // northeast
            { x: x - 1, y: y + 1 }, // southwest
            { x: x + 1, y: y + 1 }, // southeast
        ]
    }

    /**
     * Fetch a single tile from the API
     */
    async fetchTile(x, y) {
        const key = this.getTileKey(x, y)

        // Check if already in cache
        if (this.cache.has(key)) {
            return this.cache.get(key)
        }

        // Check if already being fetched
        if (this.pendingFetches.has(key)) {
            // Wait for the pending fetch to complete
            return new Promise((resolve) => {
                const checkInterval = setInterval(() => {
                    if (!this.pendingFetches.has(key)) {
                        clearInterval(checkInterval)
                        resolve(this.cache.get(key) || null)
                    }
                }, 50)
            })
        }

        // Mark as pending
        this.pendingFetches.add(key)

        try {
            const response = await apiEndpoints.world.getTile(x, y)
            if (response.data.success && response.data.tile) {
                this.set(x, y, response.data.tile)
                return response.data.tile
            }
            return null
        } catch (error) {
            console.error(`Failed to fetch tile at (${x}, ${y}):`, error)
            return null
        } finally {
            this.pendingFetches.delete(key)
        }
    }

    /**
     * Fetch multiple tiles in batch using the batch API endpoint
     */
    async fetchTiles(coordinates) {
        // Filter out tiles that are already cached or being fetched
        const toFetch = coordinates.filter(({ x, y }) => {
            const key = this.getTileKey(x, y)
            return !this.cache.has(key) && !this.pendingFetches.has(key)
        })

        if (toFetch.length === 0) {
            return []
        }

        // Mark all as pending
        toFetch.forEach(({ x, y }) => {
            this.pendingFetches.add(this.getTileKey(x, y))
        })

        try {
            const response = await apiEndpoints.world.getTilesBatch(toFetch)

            if (response.data.success && response.data.tiles) {
                // Cache all fetched tiles
                response.data.tiles.forEach(tile => {
                    this.set(tile.x, tile.y, tile)
                })

                return response.data.tiles
            }

            return []
        } catch (error) {
            console.error('Batch tile fetch failed, falling back to individual fetches:', error)

            // Fallback to individual fetches if batch fails
            const promises = toFetch.map(({ x, y }) => this.fetchTile(x, y))
            return Promise.all(promises)
        } finally {
            // Clear pending status for all
            toFetch.forEach(({ x, y }) => {
                this.pendingFetches.delete(this.getTileKey(x, y))
            })
        }
    }

    /**
     * Pre-fetch adjacent tiles for a given position
     * Only fetches tiles that aren't already cached or pending
     */
    async prefetchAdjacent(x, y) {
        const adjacent = this.getAdjacentCoordinates(x, y)
        const toFetch = adjacent.filter(
            ({ x, y }) => !this.has(x, y) && !this.pendingFetches.has(this.getTileKey(x, y))
        )

        if (toFetch.length > 0) {
            // Fetch in background without blocking
            this.fetchTiles(toFetch).catch(err => {
                console.warn('Background tile prefetch failed:', err)
            })
        }
    }

    /**
     * Get a tile, fetching from API if not in cache
     * Also triggers prefetch of adjacent tiles
     */
    async getTileWithPrefetch(x, y) {
        // Get the requested tile
        const tile = await this.fetchTile(x, y)

        // Trigger background prefetch of adjacent tiles
        this.prefetchAdjacent(x, y)

        return tile
    }

    /**
     * Clear the entire cache
     */
    clear() {
        this.cache.clear()
        this.accessTimes.clear()
        this.pendingFetches.clear()
    }

    /**
     * Get cache statistics
     */
    getStats() {
        return {
            size: this.cache.size,
            maxSize: this.maxCacheSize,
            pendingFetches: this.pendingFetches.size,
            utilizationPercent: Math.round((this.cache.size / this.maxCacheSize) * 100)
        }
    }

    /**
     * Export cache data (for debugging or persistence)
     */
    export() {
        const data = {}
        for (const [key, value] of this.cache.entries()) {
            data[key] = value
        }
        return data
    }

    /**
     * Import cache data (for restoring from persistence)
     */
    import(data) {
        for (const [key, value] of Object.entries(data)) {
            this.cache.set(key, value)
            this.accessTimes.set(key, Date.now())
        }
    }
}

// Create a singleton instance
const tileCache = new TileCache()

export default tileCache
