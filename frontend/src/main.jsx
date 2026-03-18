import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import '@fontsource/eb-garamond/400.css'
import '@fontsource/eb-garamond/600.css'
import './styles/index.css'
import logger from './utils/logger.js'
import { ToastProvider } from './context/ToastContext.jsx'

// Initialize browser logging
logger.init()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </React.StrictMode>,
)
