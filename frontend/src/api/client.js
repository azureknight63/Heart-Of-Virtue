import axios from 'axios'
import { AUTH_TOKEN_KEY, clearLocalSession } from '../utils/session'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle auth errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Only redirect if we get a 401 and we're NOT on the login page
    // This allows the login page to handle its own 401s (bad credentials)
    // without triggering a circular redirect/reload.
    if (error.response?.status === 401 && !window.location.pathname.includes('/login')) {
      // Shared with logout() rather than restated: the key list is the
      // invariant, and a comment saying "match logout()" was the only thing
      // keeping the two in step.
      clearLocalSession()
      window.location.href = `${import.meta.env.BASE_URL}login`
    }
    return Promise.reject(error)
  }
)

export default apiClient
