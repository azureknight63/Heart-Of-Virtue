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

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('throws when useAuthContext is called outside an AuthProvider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<ThrowsOutsideProvider />)).toThrow(
      'useAuthContext must be used within an AuthProvider'
    )
    consoleSpy.mockRestore()
  })

  it('starts unauthenticated when there is no stored session marker', () => {
    render(<AuthProvider><AuthConsumer /></AuthProvider>)
    expect(screen.getByTestId('authed').textContent).toBe('false')
    expect(screen.getByTestId('loading').textContent).toBe('false')
    expect(screen.getByTestId('username').textContent).toBe('none')
  })

  it('hydrates as authenticated from the stored username', () => {
    // Since #493 the credential is an HttpOnly cookie the page cannot read, so
    // the stored username is what hydration keys on.
    localStorage.setItem('username', 'gorran')
    render(<AuthProvider><AuthConsumer /></AuthProvider>)
    expect(screen.getByTestId('authed').textContent).toBe('true')
    expect(screen.getByTestId('username').textContent).toBe('gorran')
  })

  it('logs in without ever storing the session id', async () => {
    // The response still carries session_id for non-browser callers. Writing it
    // to localStorage is exactly what #493 removed, so this asserts its
    // absence rather than its value — the cookie set on the same response is
    // the credential.
    localStorage.setItem('authToken', 'pre-493-leftover')
    apiEndpoints.auth.login.mockResolvedValue({ data: { data: { session_id: 'sess-1' }, success: true } })
    render(<AuthProvider><AuthConsumer /></AuthProvider>)

    await act(async () => {
      fireEvent.click(screen.getByText('login'))
    })

    expect(apiEndpoints.auth.login).toHaveBeenCalledWith('jean', 'pw')
    expect(localStorage.getItem('authToken')).toBeNull()
    expect(localStorage.getItem('username')).toBe('jean')
    expect(screen.getByTestId('authed').textContent).toBe('true')
    expect(screen.getByTestId('username').textContent).toBe('jean')
  })

  it('clears auth state and rethrows when login fails', async () => {
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

  it('registers without ever storing the session id', async () => {
    apiEndpoints.auth.register.mockResolvedValue({ data: { data: { session_id: 'sess-2' } } })
    render(<AuthProvider><AuthConsumer /></AuthProvider>)

    await act(async () => {
      fireEvent.click(screen.getByText('register'))
    })

    expect(apiEndpoints.auth.register).toHaveBeenCalledWith('jean', 'pw', 'jean@example.com')
    expect(localStorage.getItem('authToken')).toBeNull()
    expect(localStorage.getItem('username')).toBe('jean')
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
    // A pre-#493 token may still be sitting in storage on an upgrading browser;
    // logout has to take it with everything else.
    localStorage.setItem('authToken', 'pre-493-leftover')
    localStorage.setItem('username', 'jean')
    apiEndpoints.auth.logout.mockResolvedValue()

    delete window.location
    window.location = { href: '' }

    render(<AuthProvider><AuthConsumer /></AuthProvider>)
    await act(async () => {
      fireEvent.click(screen.getByText('logout'))
    })

    // Exactly one server-side logout, and it takes no arguments — the session
    // travels as the HttpOnly cookie, not in the body. That request is also the
    // only thing that can expire the cookie, which is why it is not optional.
    expect(apiEndpoints.auth.logout).toHaveBeenCalledTimes(1)
    expect(apiEndpoints.auth.logout).toHaveBeenCalledWith()
    expect(screen.getByTestId('authed').textContent).toBe('false')
    expect(localStorage.getItem('authToken')).toBeNull()
    expect(localStorage.getItem('username')).toBeNull()
    expect(window.location.href).toContain('login')
  })

  it('falls back to a root base path when BASE_URL is unset', async () => {
    vi.stubEnv('BASE_URL', '')
    localStorage.setItem('username', 'jean')
    apiEndpoints.auth.logout.mockResolvedValue()

    delete window.location
    window.location = { href: '' }

    render(<AuthProvider><AuthConsumer /></AuthProvider>)
    await act(async () => {
      fireEvent.click(screen.getByText('logout'))
    })

    expect(window.location.href).toBe('/login')
  })

  it('still clears state and redirects when the logout request fails', async () => {
    localStorage.setItem('username', 'jean')
    localStorage.setItem('authToken', 'pre-493-leftover')
    apiEndpoints.auth.logout.mockRejectedValue(new Error('network error'))

    delete window.location
    window.location = { href: '' }

    render(<AuthProvider><AuthConsumer /></AuthProvider>)
    await act(async () => {
      fireEvent.click(screen.getByText('logout'))
    })

    expect(localStorage.getItem('authToken')).toBeNull()
    // Even when the network call fails, the session is over locally.
    expect(window.location.href).toContain('login')
  })

  it('re-runs checkAuth on demand', async () => {
    render(<AuthProvider><AuthConsumer /></AuthProvider>)
    expect(screen.getByTestId('authed').textContent).toBe('false')

    localStorage.setItem('username', 'later-user')

    await act(async () => {
      fireEvent.click(screen.getByText('recheck'))
    })

    expect(screen.getByTestId('authed').textContent).toBe('true')
    expect(screen.getByTestId('username').textContent).toBe('later-user')
  })
})
