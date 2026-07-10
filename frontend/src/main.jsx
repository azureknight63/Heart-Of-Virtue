import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import '@fontsource/eb-garamond/400.css'
import '@fontsource/eb-garamond/600.css'
import './styles/index.css'
import logger from './utils/logger.js'
import { ToastProvider } from './context/ToastContext.jsx'
import { AuthProvider } from './context/AuthContext.jsx'

// Initialize browser logging — dev-only. In production this would ship
// every console.log/debug call (including [DEBUG] dumps) to the backend.
if (import.meta.env.DEV) {
  logger.init()
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </AuthProvider>
  </React.StrictMode>,
)
