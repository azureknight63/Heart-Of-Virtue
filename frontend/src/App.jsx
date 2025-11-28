import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useApi'
import LoginPage from './pages/LoginPage'
import GamePage from './pages/GamePage'
import LoadingScreen from './components/LoadingScreen'
import { AudioProvider } from './context/AudioContext'

function App() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  return (
    <AudioProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={isAuthenticated ? <Navigate to="/game" /> : <LoginPage />} />
          <Route path="/game" element={isAuthenticated ? <GamePage /> : <Navigate to="/login" />} />
          <Route path="/" element={<Navigate to={isAuthenticated ? '/game' : '/login'} />} />
          <Route path="*" element={<Navigate to={isAuthenticated ? '/game' : '/login'} />} />
        </Routes>
      </BrowserRouter>
    </AudioProvider>
  )
}

export default App
