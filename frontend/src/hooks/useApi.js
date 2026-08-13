import { useState, useEffect, useCallback, useRef } from 'react'
import apiEndpoints from '../api/endpoints'
import { useAuthContext } from '../context/AuthContext'

// Helper to transform combat data
const transformCombatData = (data) => ({
  ...data.battle_state,
  log: data.log || [],
  beat_states: data.beat_states || [],
  end_state: data.end_state || null,
  combat_active: data.combat_active,
  suggested_moves: data.suggested_moves || [],
  suggestions_loading: data.suggestions_loading || false,
  events_triggered: data.events_triggered || [],
  last_move_outcome: data.last_move_outcome || "",
  last_move_name: data.last_move_name || null,

  last_move_target_id: data.last_move_target_id || null
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
  return useAuthContext()
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
        max_exp: 100,
        exp_to_next_level: 100,
        pending_attribute_points: 0,
        pending_level_ups: [],
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

export const useCombat = (streamingEnabled = false) => {
  const [combat, setCombat] = useState(null)
  const [loading, setLoading] = useState(false)
  const [inCombat, setInCombat] = useState(false)
  const fetchInFlight = useRef(false)

  const fetchCombatStatus = useCallback(async () => {
    if (fetchInFlight.current) return
    fetchInFlight.current = true
    try {
      setLoading(true)
      const response = await apiEndpoints.combat.getStatus()
      const data = response.data
      const transformed = transformCombatData(data)
      setCombat(transformed)
      setInCombat(data.combat_active)
      return transformed
    } catch (err) {
      console.error('Combat status error:', err)
    } finally {
      setLoading(false)
      fetchInFlight.current = false
    }
  }, [])

  // Apply a server combat-state payload (HTTP response or a socket
  // combat:resolved event). combat:ended may carry only the end summary.

  const applyCombatState = useCallback((data) => {
    if (!data) return
    // combat:ended carries the end summary itself rather than a full
    // get_combat_state() response. Normalize it to the same shape so the
    // coordinator can show Victory/Defeat instead of leaving the old move
    // selection state on screen.
    const state = (typeof data.combat_active === 'boolean' || data.battle_state)
      ? data
      : {
          combat_active: false,
          battle_state: { status: 'ended', awaiting_input: false, input_type: null },
          end_state: data,
          log: [],
        }
    setCombat(transformCombatData(state))
    if (typeof state.combat_active === 'boolean') setInCombat(state.combat_active)
  }, [])

  const performAction = useCallback(async (action, target) => {
    try {
      setLoading(true)
      const response = await apiEndpoints.combat.performAction(action, target)
      const data = response.data
      // Game-logic errors (e.g. "no viable targets") return success:false with no
      // combat state payload — don't overwrite current state or drop out of combat.
      if (data.success === false) {
        return data
      }
      // Streaming normally delivers beat/resolution payloads over Socket.IO. The
      // HTTP response remains authoritative for the action, though: a client may
      // miss a socket event, and a victory response must not leave the UI waiting
      // forever in its pre-action state. Non-terminal streaming responses are still
      // applied by the socket when it arrives; terminal responses are applied here
      // immediately as a safety net.
      if (!streamingEnabled || data.combat_active === false || data.end_state) {
        applyCombatState(data)
      }
      return data
    } catch (err) {
      console.error('Combat action error:', err)
      throw err
    } finally {
      setLoading(false)
    }
  }, [applyCombatState, streamingEnabled])

  return {
    combat,
    loading,
    inCombat,
    fetchCombatStatus,
    performAction,
    applyCombatState,
  }
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

// Meaningful transitions (movement, combat actions — see triggerTick's call
// sites in GamePage/useCombatCoordinator) call triggerTick, which throttles
// the actual cloud write to at most once every AUTOSAVE_TICK_THRESHOLD
// transitions. A dead session therefore loses at most
// AUTOSAVE_TICK_THRESHOLD - 1 transitions' worth of progress — down from the
// previous threshold of 20. There is no other durable record of progress
// (issue #489 retired the write-only local autosave blob, see #487), so this
// threshold is the entire bound on unsaved-progress exposure.
const AUTOSAVE_TICK_THRESHOLD = 3

/**
 * useAutosave - Cloud autosave trigger hook.
 *
 * Saves to the Turso cloud autosave slot (server-side UPSERT, so repeated
 * calls are cheap) on a throttled schedule — see AUTOSAVE_TICK_THRESHOLD.
 *
 * @param {Object} [options]
 * @param {(err: Error) => void} [options.onSaveError] called when a cloud
 *   save fails, so the caller can surface it to the player. A failed save is
 *   silent progress loss now that no local backstop exists.
 */
export const useAutosave = ({ onSaveError } = {}) => {
  const [tickCount, setTickCount] = useState(0)
  // Lazy initialiser: a bare useState(Date.now()) re-evaluates Date.now() on
  // every render and throws the result away, which is impure and made the
  // hook non-deterministic to reason about.
  const [lastCloudSave, setLastCloudSave] = useState(() => Date.now())
  // Guards against overlapping cloud saves: at AUTOSAVE_TICK_THRESHOLD=3, a
  // burst of rapid transitions (e.g. spamming combat actions) can trigger a
  // new save before the in-flight one's response lands.
  const saveInFlight = useRef(false)

  const saveToCloud = async () => {
    if (saveInFlight.current) return
    saveInFlight.current = true
    try {
      await apiEndpoints.saves.save('Autosave', true)
      setLastCloudSave(Date.now())
    } catch (err) {
      console.error('[Autosave] Cloud sync failed:', err)
      onSaveError?.(err)
    } finally {
      saveInFlight.current = false
    }
  }

  const triggerTick = async () => {
    setTickCount(prev => {
      const newCount = prev + 1

      if (newCount >= AUTOSAVE_TICK_THRESHOLD) {
        saveToCloud()
        return 0
      }
      return newCount
    })
  }

  return { tickCount, lastCloudSave, triggerTick, saveToCloud }
}

