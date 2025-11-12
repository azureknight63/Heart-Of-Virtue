import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useApi'
import LoginPage from './pages/LoginPage'
import GamePage from './pages/GamePage'
import LoadingScreen from './components/LoadingScreen'

function App() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={isAuthenticated ? <Navigate to="/game" /> : <LoginPage />} />
        <Route path="/game" element={isAuthenticated ? <GamePage /> : <Navigate to="/login" />} />
        <Route path="/" element={<Navigate to={isAuthenticated ? '/game' : '/login'} />} />
        <Route path="*" element={<Navigate to={isAuthenticated ? '/game' : '/login'} />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
