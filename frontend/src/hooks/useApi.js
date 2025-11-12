import { useState, useEffect } from 'react'
import apiEndpoints from '../api/endpoints'

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
      setIsAuthenticated(false)
    }
  }

  const register = async (username, password) => {
    try {
      const response = await apiEndpoints.auth.register(username, password)
      const { session_id } = response.data.data
      localStorage.setItem('authToken', session_id)
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
      const response = await apiEndpoints.player.getStatus()
      setPlayer(response.data.data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPlayer()
  }, [])

  return { player, loading, error, refetch: fetchPlayer }
}

export const useCombat = () => {
  const [combat, setCombat] = useState(null)
  const [loading, setLoading] = useState(false)
  const [inCombat, setInCombat] = useState(false)

  const fetchCombatStatus = async () => {
    try {
      setLoading(true)
      const response = await apiEndpoints.combat.getStatus()
      setCombat(response.data.data)
      setInCombat(response.data.data.in_combat)
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
      setCombat(response.data.data)
      return response.data
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
      setLocation(response.data.data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const move = async (direction) => {
    try {
      const response = await apiEndpoints.world.move(direction)
      setLocation(response.data.data)
      return response.data
    } catch (err) {
      setError(err.message)
      throw err
    }
  }

  useEffect(() => {
    fetchLocation()
  }, [])

  return { location, loading, error, move, refetch: fetchLocation }
}
