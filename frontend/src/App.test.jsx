import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockUseAuth = vi.fn()

vi.mock('./hooks/useApi', () => ({
  useAuth: () => mockUseAuth()
}))

vi.mock('./pages/LoginPage', () => ({
  default: () => <div>LoginPageStub</div>
}))
vi.mock('./pages/MainMenuPage', () => ({
  default: () => <div>MainMenuPageStub</div>
}))
vi.mock('./pages/GamePage', () => ({
  default: () => <div>GamePageStub</div>
}))
vi.mock('./pages/LandingPage', () => ({
  default: () => <div>LandingPageStub</div>
}))
vi.mock('./components/LoadingScreen', () => ({
  default: () => <div>LoadingScreenStub</div>
}))
vi.mock('./context/AudioContext', () => ({
  AudioProvider: ({ children }) => <div>{children}</div>
}))

import App from './App'

function setLocation(path) {
  window.history.pushState({}, '', path)
}

describe('App', () => {
  beforeEach(() => {
    mockUseAuth.mockReset()
  })

  it('renders the loading screen while auth is loading', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, loading: true })
    setLocation('/games/HeartOfVirtue/')
    render(<App />)
    expect(screen.getByText('LoadingScreenStub')).toBeInTheDocument()
  })

  it('renders LandingPage at root when unauthenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, loading: false })
    setLocation('/games/HeartOfVirtue/')
    render(<App />)
    expect(screen.getByText('LandingPageStub')).toBeInTheDocument()
  })

  it('redirects root to /game when authenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, loading: false })
    setLocation('/games/HeartOfVirtue/')
    render(<App />)
    expect(screen.getByText('GamePageStub')).toBeInTheDocument()
  })

  it('renders LoginPage when unauthenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, loading: false })
    setLocation('/games/HeartOfVirtue/login')
    render(<App />)
    expect(screen.getByText('LoginPageStub')).toBeInTheDocument()
  })

  it('redirects /login to /game when already authenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, loading: false })
    setLocation('/games/HeartOfVirtue/login')
    render(<App />)
    expect(screen.getByText('GamePageStub')).toBeInTheDocument()
  })

  it('renders MainMenuPage when authenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, loading: false })
    setLocation('/games/HeartOfVirtue/menu')
    render(<App />)
    expect(screen.getByText('MainMenuPageStub')).toBeInTheDocument()
  })

  it('redirects /menu to root when unauthenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, loading: false })
    setLocation('/games/HeartOfVirtue/menu')
    render(<App />)
    expect(screen.getByText('LandingPageStub')).toBeInTheDocument()
  })

  it('renders GamePage when authenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, loading: false })
    setLocation('/games/HeartOfVirtue/game')
    render(<App />)
    expect(screen.getByText('GamePageStub')).toBeInTheDocument()
  })

  it('redirects /game to root when unauthenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, loading: false })
    setLocation('/games/HeartOfVirtue/game')
    render(<App />)
    expect(screen.getByText('LandingPageStub')).toBeInTheDocument()
  })

  it('renders LandingPage directly at /landing regardless of auth state', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, loading: false })
    setLocation('/games/HeartOfVirtue/landing')
    render(<App />)
    expect(screen.getByText('LandingPageStub')).toBeInTheDocument()
  })

  it('redirects unknown routes to /game when authenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: true, loading: false })
    setLocation('/games/HeartOfVirtue/does-not-exist')
    render(<App />)
    expect(screen.getByText('GamePageStub')).toBeInTheDocument()
  })

  it('redirects unknown routes to root when unauthenticated', () => {
    mockUseAuth.mockReturnValue({ isAuthenticated: false, loading: false })
    setLocation('/games/HeartOfVirtue/does-not-exist')
    render(<App />)
    expect(screen.getByText('LandingPageStub')).toBeInTheDocument()
  })
})
