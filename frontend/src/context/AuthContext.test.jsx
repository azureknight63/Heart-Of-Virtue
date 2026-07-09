import { render, screen, act, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { AuthProvider, useAuthContext } from './AuthContext'
import apiEndpoints from '../api/endpoints'

vi.mock('../api/endpoints', () => ({
  default: {
    auth: {
      login: vi.fn(),
      logout: vi.fn(),
      register: vi.fn(),
    },
  },
}))

function AuthConsumer() {
  const auth = useAuthContext()
  return (
    <div>
      <div data-testid="authed">{String(auth.isAuthenticated)}</div>
      <div data-testid="loading">{String(auth.loading)}</div>
      <div data-testid="username">{auth.user?.username || 'none'}</div>
      <button onClick={() => auth.login('jean', 'pw').catch(() => {})}>login</button>
      <button onClick={() => auth.logout().catch(() => {})}>logout</button>
      <button onClick={() => auth.register('jean', 'pw', 'jean@example.com').catch(() => {})}>register</button>
      <button onClick={() => auth.checkAuth()}>recheck</button>
    </div>
  )
}

function ThrowsOutsideProvider() {
  useAuthContext()
  return null
}

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('throws when useAuthContext is called outside an AuthProvider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<ThrowsOutsideProvider />)).toThrow(
      'useAuthContext must be used within an AuthProvider'
    )
    consoleSpy.mockRestore()
  })

  it('starts unauthenticated when there is no stored token', () => {
    render(<AuthProvider><AuthConsumer /></AuthProvider>)
    expect(screen.getByTestId('authed').textContent).toBe('false')
    expect(screen.getByTestId('loading').textContent).toBe('false')
    expect(screen.getByTestId('username').textContent).toBe('none')
  })

  it('hydrates as authenticated when a token is already stored', () => {
    localStorage.setItem('authToken', 'tok-1')
    localStorage.setItem('username', 'gorran')
    render(<AuthProvider><AuthConsumer /></AuthProvider>)
    expect(screen.getByTestId('authed').textContent).toBe('true')
    expect(screen.getByTestId('username').textContent).toBe('gorran')
  })

  it('logs in successfully, storing the session and marking authenticated', async () => {
    apiEndpoints.auth.login.mockResolvedValue({ data: { data: { session_id: 'sess-1' }, success: true } })
    render(<AuthProvider><AuthConsumer /></AuthProvider>)

    await act(async () => {
      fireEvent.click(screen.getByText('login'))
    })

    expect(apiEndpoints.auth.login).toHaveBeenCalledWith('jean', 'pw')
    expect(localStorage.getItem('authToken')).toBe('sess-1')
    expect(localStorage.getItem('username')).toBe('jean')
    expect(screen.getByTestId('authed').textContent).toBe('true')
    expect(screen.getByTestId('username').textContent).toBe('jean')
  })

  it('clears auth state and rethrows when login fails', async () => {
    localStorage.setItem('authToken', 'stale')
    localStorage.setItem('username', 'stale-user')
    apiEndpoints.auth.login.mockRejectedValue(new Error('bad credentials'))

    function Consumer() {
      const auth = useAuthContext()
      return (
        <button
          onClick={async () => {
            try {
              await auth.login('jean', 'wrong')
            } catch (e) {
              // swallow for the test
            }
          }}
        >
          try-login
        </button>
      )
    }

    render(<AuthProvider><Consumer /><AuthConsumer /></AuthProvider>)
    await act(async () => {
      fireEvent.click(screen.getByText('try-login'))
    })

    expect(screen.getByTestId('authed').textContent).toBe('false')
    expect(screen.getByTestId('username').textContent).toBe('none')
  })

  it('registers successfully, storing the session and marking authenticated', async () => {
    apiEndpoints.auth.register.mockResolvedValue({ data: { data: { session_id: 'sess-2' } } })
    render(<AuthProvider><AuthConsumer /></AuthProvider>)

    await act(async () => {
      fireEvent.click(screen.getByText('register'))
    })

    expect(apiEndpoints.auth.register).toHaveBeenCalledWith('jean', 'pw', 'jean@example.com')
    expect(localStorage.getItem('authToken')).toBe('sess-2')
    expect(screen.getByTestId('authed').textContent).toBe('true')
  })

  it('clears auth state when registration fails', async () => {
    apiEndpoints.auth.register.mockRejectedValue(new Error('email taken'))
    render(<AuthProvider><AuthConsumer /></AuthProvider>)

    await act(async () => {
      fireEvent.click(screen.getByText('register'))
    })

    expect(screen.getByTestId('authed').textContent).toBe('false')
  })

  it('logs out, clears storage, and redirects to the login page', async () => {
    localStorage.setItem('authToken', 'tok-1')
    localStorage.setItem('username', 'jean')
    apiEndpoints.auth.logout.mockResolvedValue()

    delete window.location
    window.location = { href: '' }

    render(<AuthProvider><AuthConsumer /></AuthProvider>)
    await act(async () => {
      fireEvent.click(screen.getByText('logout'))
    })

    expect(apiEndpoints.auth.logout).toHaveBeenCalled()
    expect(localStorage.getItem('authToken')).toBeNull()
    expect(localStorage.getItem('username')).toBeNull()
    expect(window.location.href).toContain('login')
  })

  it('still clears state and redirects when the logout request fails', async () => {
    localStorage.setItem('authToken', 'tok-1')
    apiEndpoints.auth.logout.mockRejectedValue(new Error('network error'))

    delete window.location
    window.location = { href: '' }

    render(<AuthProvider><AuthConsumer /></AuthProvider>)
    await act(async () => {
      fireEvent.click(screen.getByText('logout'))
    })

    expect(localStorage.getItem('authToken')).toBeNull()
    expect(window.location.href).toContain('login')
  })

  it('re-runs checkAuth on demand', async () => {
    render(<AuthProvider><AuthConsumer /></AuthProvider>)
    expect(screen.getByTestId('authed').textContent).toBe('false')

    localStorage.setItem('authToken', 'tok-later')
    localStorage.setItem('username', 'later-user')

    await act(async () => {
      fireEvent.click(screen.getByText('recheck'))
    })

    expect(screen.getByTestId('authed').textContent).toBe('true')
    expect(screen.getByTestId('username').textContent).toBe('later-user')
  })
})
