import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useApi'
import LoginPage from './pages/LoginPage'
import MainMenuPage from './pages/MainMenuPage'
import GamePage from './pages/GamePage'
import LandingPage from './pages/LandingPage'
import LoadingScreen from './components/LoadingScreen'
import { AudioProvider } from './context/AudioContext'

function App() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  return (
    <AudioProvider>
      <BrowserRouter basename="/games/HeartOfVirtue">
        <Routes>
          <Route path="/" element={isAuthenticated ? <Navigate to="/game" /> : <LandingPage />} />
          <Route path="/home" element={isAuthenticated ? <Navigate to="/game" /> : <LandingPage />} />
          <Route path="/landing" element={<LandingPage />} />
          <Route path="/login" element={isAuthenticated ? <Navigate to="/game" /> : <LoginPage />} />
          <Route path="/menu" element={isAuthenticated ? <MainMenuPage /> : <Navigate to="/" />} />
          <Route path="/game" element={isAuthenticated ? <GamePage /> : <Navigate to="/" />} />
          <Route path="*" element={<Navigate to={isAuthenticated ? '/game' : '/'} />} />
        </Routes>
      </BrowserRouter>
    </AudioProvider>
  )
}

export default App
