import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useApi'
import LoginPage from './pages/LoginPage'
import MainMenuPage from './pages/MainMenuPage'
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
          <Route path="/login" element={isAuthenticated ? <Navigate to="/menu" /> : <LoginPage />} />
          <Route path="/menu" element={isAuthenticated ? <MainMenuPage /> : <Navigate to="/login" />} />
          <Route path="/game" element={isAuthenticated ? <GamePage /> : <Navigate to="/login" />} />
          <Route path="/" element={<Navigate to={isAuthenticated ? '/menu' : '/login'} />} />
          <Route path="*" element={<Navigate to={isAuthenticated ? '/menu' : '/login'} />} />
        </Routes>
      </BrowserRouter>
    </AudioProvider>
  )
}

export default App
