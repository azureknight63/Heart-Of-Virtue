import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useApi'
import { useCapabilities } from './context/CapabilitiesContext'
import LoginPage from './pages/LoginPage'
import MainMenuPage from './pages/MainMenuPage'
import GamePage from './pages/GamePage'
import LandingPage from './pages/LandingPage'
import LoadingScreen from './components/LoadingScreen'
import { AudioProvider } from './context/AudioContext'
import { GlossaryProvider } from './context/GlossaryContext'

function App() {
  const { isAuthenticated, loading } = useAuth()
  const { capabilitiesLoading } = useCapabilities()

  if (loading) {
    return <LoadingScreen />
  }

  // Resolving capabilities before the authenticated surface mounts means
  // combat's streaming flag never flips true mid-session (e.g. a mid-combat
  // reload) — it is known one way or the other before GamePage renders
  // (#496 item 7). HTTP combat state stays authoritative regardless of the
  // outcome. Scoped to isAuthenticated so an unauthenticated visitor hitting
  // landing/login — who will never reach combat — isn't held up by a fetch
  // they don't need.
  if (isAuthenticated && capabilitiesLoading) {
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
          {/* The combat glossary (#507) is scoped to the game surface: it owns a
              "?" keyboard shortcut, which has no business being live on the
              landing or login pages. */}
          <Route path="/game" element={isAuthenticated ? <GlossaryProvider><GamePage /></GlossaryProvider> : <Navigate to="/" />} />
          <Route path="*" element={<Navigate to={isAuthenticated ? '/game' : '/'} />} />
        </Routes>
      </BrowserRouter>
    </AudioProvider>
  )
}

export default App
