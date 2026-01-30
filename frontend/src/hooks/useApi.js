import { useState, useEffect } from 'react'
import apiEndpoints from '../api/endpoints'

// Helper to transform combat data
const transformCombatData = (data) => ({
  ...data.battle_state,
  log: data.log || [],
  beat_states: data.beat_states || [],
  end_state: data.end_state || null,
  combat_active: data.combat_active
})

// Helper to transform location data
const transformLocationData = (room) => {
  // Create a completely new object with new array references
  // This ensures React's shallow comparison detects changes
  const transformed = {
    ...room,
    // Always create new array references to trigger React re-renders
    exits: Array.isArray(room.exits)
      ? [...room.exits]
      : (room.exits && typeof room.exits === 'object' ? Object.keys(room.exits) : []),
    items: room.items ? [...room.items] : [],
    npcs: room.npcs ? [...room.npcs] : [],
    objects: room.objects ? [...room.objects] : [],
    // Add timestamp to guarantee unique object reference
    _fetchedAt: Date.now()
  }

  return transformed
}

export const useAuth = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('authToken')
    setIsAuthenticated(!!token)
    setLoading(false)
  }, [])

  const login = async (username, password) => {
    try {
      const response = await apiEndpoints.auth.login(username, password)
      const { session_id } = response.data.data
      localStorage.setItem('authToken', session_id)
      localStorage.setItem('username', username)
      setIsAuthenticated(true)
      return response.data
    } catch (error) {
      setIsAuthenticated(false)
      throw error
    }
  }

  const logout = async () => {
    try {
      await apiEndpoints.auth.logout()
    } finally {
      localStorage.removeItem('authToken')
      localStorage.removeItem('username')
      setIsAuthenticated(false)
      // Force reload to clear state and redirect to login
      window.location.href = '/login'
    }
  }

  const register = async (username, password, email) => {
    try {
      const response = await apiEndpoints.auth.register(username, password, email)
      const { session_id } = response.data.data
      localStorage.setItem('authToken', session_id)
      localStorage.setItem('username', username)
      setIsAuthenticated(true)
      return response.data
    } catch (error) {
      setIsAuthenticated(false)
      throw error
    }
  }

  return { isAuthenticated, loading, login, logout, register }
}

export const usePlayer = () => {
  const [player, setPlayer] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchPlayer = async () => {
    try {
      setLoading(true)
      const response = await apiEndpoints.player.getFullState()
      const data = response.data

      // Combined payload from consolidated endpoint
      const playerData = {
        ...data.status,
        inventory: data.inventory?.items || [],
        ...data.stats,
        ...data.skills,
      }

      setPlayer(playerData)
      setError(null)
    } catch (err) {
      setError(err.message)
      // Still set a player object so the UI doesn't break completely
      setPlayer({
        name: 'Unknown',
        level: 1,
        exp: 0,
        hp: 0,
        max_hp: 0,
        state: 'normal',
        inventory: [],
        strength: 10,
        strength_base: 10,
        finesse: 10,
        finesse_base: 10,
        speed: 10,
        speed_base: 10,
        endurance: 10,
        endurance_base: 10,
        charisma: 10,
        charisma_base: 10,
        intelligence: 10,
        intelligence_base: 10,
        faith: 10,
        faith_base: 10,
        fatigue: 100,
        max_fatigue: 100,
        weight_current: 0,
        carrying_capacity: 100,
        protection: 0,
        resistance: {},
        status_resistance: {},
        states: [],
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPlayer()
  }, [])

  const allocateLevelUpPoints = async (attribute, amount) => {
    const response = await apiEndpoints.player.allocateLevelUpPoints(attribute, amount)
    // Refresh full player payload after allocation so UI stays consistent
    await fetchPlayer()
    return response.data
  }

  return { player, loading, error, refetch: fetchPlayer, allocateLevelUpPoints }
}

export const useCombat = () => {
  const [combat, setCombat] = useState(null)
  const [loading, setLoading] = useState(false)
  const [inCombat, setInCombat] = useState(false)

  const fetchCombatStatus = async () => {
    try {
      setLoading(true)
      const response = await apiEndpoints.combat.getStatus()
      const data = response.data
      const transformed = transformCombatData(data)
      setCombat(transformed)
      setInCombat(data.combat_active)
    } catch (err) {
      console.error('Combat status error:', err)
    } finally {
      setLoading(false)
    }
  }

  const performAction = async (action, target) => {
    try {
      setLoading(true)
      const response = await apiEndpoints.combat.performAction(action, target)
      const data = response.data
      const transformed = transformCombatData(data)
      setCombat(transformed)
      setInCombat(data.combat_active)
      return data
    } catch (err) {
      console.error('Combat action error:', err)
      throw err
    } finally {
      setLoading(false)
    }
  }

  return { combat, loading, inCombat, fetchCombatStatus, performAction }
}

export const useWorld = () => {
  const [location, setLocation] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchLocation = async () => {
    try {
      setLoading(true)
      const response = await apiEndpoints.world.getCurrentLocation()
      const room = transformLocationData(response.data.room)
      setLocation(room)
      setError(null)

      // Import tile cache and cache current location + prefetch adjacent
      import('../utils/TileCache').then(({ default: tileCache }) => {
        tileCache.set(room.x, room.y, room)
        tileCache.prefetchAdjacent(room.x, room.y)
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const move = async (direction) => {
    try {
      // Import tile cache
      const { default: tileCache } = await import('../utils/TileCache')

      // Calculate target coordinates based on direction
      const directionMap = {
        'north': { dx: 0, dy: -1 },
        'south': { dx: 0, dy: 1 },
        'west': { dx: -1, dy: 0 },
        'east': { dx: 1, dy: 0 },
        'northwest': { dx: -1, dy: -1 },
        'northeast': { dx: 1, dy: -1 },
        'southwest': { dx: -1, dy: 1 },
        'southeast': { dx: 1, dy: 1 },
      }

      const delta = directionMap[direction.toLowerCase()]
      let targetX = location.x
      let targetY = location.y

      if (delta) {
        targetX += delta.dx
        targetY += delta.dy
      }

      // Check if target tile is in cache
      const cachedTile = tileCache.get(targetX, targetY)

      // If we have cached data, optimistically update the UI
      if (cachedTile) {
        // Prepare room data from cache
        const cachedRoom = transformLocationData(cachedTile)

        // Optimistically update location
        setLocation(cachedRoom)

        // Prefetch adjacent tiles in background
        tileCache.prefetchAdjacent(targetX, targetY)
      }

      // Always make the actual move request to get authoritative data
      const response = await apiEndpoints.world.move(direction)

      // Update with authoritative data from server
      const room = transformLocationData(response.data.room)
      setLocation(room)

      // Update cache with fresh data
      tileCache.set(room.x, room.y, room)

      // Prefetch adjacent tiles
      tileCache.prefetchAdjacent(room.x, room.y)

      // Return full response data including combat_started and combat_state
      return {
        ...response.data,
        combat_started: response.data.combat_started || false,
        combat_state: response.data.combat_state || null
      }
    } catch (err) {
      setError(err.message)
      throw err
    }
  }

  useEffect(() => {
    fetchLocation()
  }, [])

  return { location, loading, error, moveToLocation: move, refetch: fetchLocation }
}

export const useExploration = () => {
  const [exploredTiles, setExploredTiles] = useState(new Map())
  const [loading, setLoading] = useState(false)

  const fetchExploredTiles = async () => {
    try {
      setLoading(true)
      const response = await apiEndpoints.world.getExploredTiles()
      const { explored_tiles } = response.data

      const newMap = new Map()
      Object.entries(explored_tiles).forEach(([key, value]) => {
        newMap.set(key, {
          ...value,
          exits: Array.isArray(value.exits)
            ? value.exits
            : (value.exits && typeof value.exits === 'object' ? Object.keys(value.exits) : [])
        })
      })

      setExploredTiles(newMap)
    } catch (err) {
      console.error('Error fetching explored tiles:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchExploredTiles()
  }, [])

  return { exploredTiles, setExploredTiles, loading, refetch: fetchExploredTiles }
}

/**
 * useAutosave - Hybrid persistence hook
 * Saves to LocalStorage every "tick"
 * Saves to Turso Cloud (DB) every 20 "ticks"
 */
export const useAutosave = (player) => {
  const [tickCount, setTickCount] = useState(0)
  const [lastCloudSave, setLastCloudSave] = useState(Date.now())

  // Save to LocalStorage whenever player state changes (every interaction/move)
  useEffect(() => {
    if (player && player.name !== 'Unknown') {
      const saveData = {
        player,
        timestamp: new Date().toISOString(),
        type: 'local_autosave'
      }
      localStorage.setItem('hov_local_autosave', JSON.stringify(saveData))
    }
  }, [player])

  const triggerTick = async () => {
    setTickCount(prev => {
      const newCount = prev + 1

      // Every 20 ticks, trigger a cloud autosave
      if (newCount >= 20) {
        saveToCloud()
        return 0
      }
      return newCount
    })
  }

  const saveToCloud = async () => {
    try {
      console.log('[Autosave] Triggering cloud sync...')
      await apiEndpoints.saves.save('Autosave', true)
      setLastCloudSave(Date.now())
    } catch (err) {
      console.error('[Autosave] Cloud sync failed:', err)
    }
  }

  return { tickCount, lastCloudSave, triggerTick, saveToCloud }
}

