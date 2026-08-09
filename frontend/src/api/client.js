import axios from 'axios'
import { LOCAL_SAVE_KEY } from '../utils/localSave'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken')
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
      localStorage.removeItem('authToken')
      // Match logout() exactly: leaving `username` behind hands the prior
      // account's identifier to the next user on a shared machine.
      localStorage.removeItem('username')
      // Match logout(): the local autosave belongs to the session that just
      // ended, and must not be offered to whoever signs in next.
      localStorage.removeItem(LOCAL_SAVE_KEY)
      window.location.href = `${import.meta.env.BASE_URL}login`
    }
    return Promise.reject(error)
  }
)

export default apiClient
