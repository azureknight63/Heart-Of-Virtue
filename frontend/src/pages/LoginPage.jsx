import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useApi'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const navigate = useNavigate()
  const { login, register } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (isRegistering) {
        if (password.length < 16) {
          throw new Error('Password must be at least 16 characters long for cloud security.')
        }
        await register(username, password, email)
      } else {
        await login(username, password)
      }
      // Token is now in localStorage, navigate and page will reload state
      window.location.href = '/menu'
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Invalid username or password; try again or register a new account.')
      } else {
        setError(err.response?.data?.message || err.message || 'Authentication failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#0a0a0a',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem'
    }}>
      <div style={{ width: '100%', maxWidth: '28rem' }}>
        <div className="bg-dark-panel retro-glow animate-fade-in" style={{
          border: '2px solid #00ff88',
          borderRadius: '0.5rem',
          padding: '2rem'
        }}>
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <h1 style={{
              fontSize: '2.25rem',
              fontWeight: 'bold',
              color: '#00ff88',
              marginBottom: '0.5rem'
            }}>Heart of Virtue</h1>
            <p style={{
              color: '#00ccff',
              fontSize: '0.875rem'
            }}>Enter the world of heroism and virtue</p>
          </div>

          {!isRegistering ? (
            <form
              key="login-form"
              id="login-form"
              method="POST"
              action="/login"
              onSubmit={handleSubmit}
              style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}
            >
              <div>
                <label htmlFor="username" style={{
                  display: 'block',
                  color: '#00ff88',
                  fontSize: '0.875rem',
                  fontWeight: 'bold',
                  marginBottom: '0.5rem'
                }}>Username</label>
                <input
                  id="username"
                  name="username"
                  autoComplete="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="input-field"
                  placeholder="Enter your name"
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div>
                <label htmlFor="password" style={{
                  display: 'block',
                  color: '#00ff88',
                  fontSize: '0.875rem',
                  fontWeight: 'bold',
                  marginBottom: '0.5rem'
                }}>Password</label>
                <input
                  id="password"
                  name="password"
                  autoComplete="current-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field"
                  placeholder="Enter your password"
                  style={{ width: '100%' }}
                  required
                  data-lpignore="false"
                  aria-label="Password"
                />
              </div>

              {error && (
                <div style={{
                  padding: '0.75rem',
                  backgroundColor: '#7f1d1d',
                  border: '1px solid #991b1b',
                  borderRadius: '0.25rem',
                  color: '#fecaca',
                  fontSize: '0.875rem'
                }}>
                  {error}
                </div>
              )}

              <button type="submit" style={{ display: 'none' }} aria-hidden="true">Log In</button>
              <button
                type="submit"
                disabled={loading}
                aria-label="Submit login form"
                className="btn btn-primary"
                style={{
                  width: '100%',
                  fontWeight: 'bold',
                  padding: '0.5rem',
                  marginTop: '1.5rem',
                  opacity: loading ? 0.5 : 1
                }}
              >
                {loading ? 'Processing...' : 'Enter Game'}
              </button>

              <button
                type="button"
                onClick={() => {
                  setIsRegistering(true)
                  setError('')
                }}
                className="btn btn-secondary"
                style={{
                  width: '100%',
                  fontSize: '0.875rem',
                  padding: '0.5rem'
                }}
              >
                New to the realm? Create Account
              </button>
            </form>
          ) : (
            <form
              key="register-form"
              id="register-form"
              method="POST"
              action="/register"
              onSubmit={handleSubmit}
              style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}
            >
              <div>
                <label htmlFor="reg-username" style={{
                  display: 'block',
                  color: '#00ff88',
                  fontSize: '0.875rem',
                  fontWeight: 'bold',
                  marginBottom: '0.5rem'
                }}>Username</label>
                <input
                  id="reg-username"
                  name="username"
                  autoComplete="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="input-field"
                  placeholder="Enter your name"
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div>
                <label htmlFor="reg-password" style={{
                  display: 'block',
                  color: '#00ff88',
                  fontSize: '0.875rem',
                  fontWeight: 'bold',
                  marginBottom: '0.5rem'
                }}>Password</label>
                <input
                  id="reg-password"
                  name="password"
                  autoComplete="new-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field"
                  placeholder="Min 16 characters"
                  style={{ width: '100%' }}
                  required
                  data-lpignore="false"
                  aria-label="New Password"
                />
                <span style={{ fontSize: '10px', color: '#666' }}>Security: Argon2id hashing active</span>
              </div>

              <div>
                <label htmlFor="reg-email" style={{
                  display: 'block',
                  color: '#00ff88',
                  fontSize: '0.875rem',
                  fontWeight: 'bold',
                  marginBottom: '0.5rem'
                }}>Email Address</label>
                <input
                  id="reg-email"
                  name="email"
                  autoComplete="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-field"
                  placeholder="For account recovery (encrypted)"
                  style={{ width: '100%' }}
                  required
                />
              </div>

              {error && (
                <div style={{
                  padding: '0.75rem',
                  backgroundColor: '#7f1d1d',
                  border: '1px solid #991b1b',
                  borderRadius: '0.25rem',
                  color: '#fecaca',
                  fontSize: '0.875rem'
                }}>
                  {error}
                </div>
              )}

              <button type="submit" style={{ display: 'none' }} aria-hidden="true">Create Account</button>
              <button
                type="submit"
                disabled={loading}
                aria-label="Submit registration form"
                className="btn btn-primary"
                style={{
                  width: '100%',
                  fontWeight: 'bold',
                  padding: '0.5rem',
                  marginTop: '1.5rem',
                  opacity: loading ? 0.5 : 1
                }}
              >
                {loading ? 'Processing...' : 'Create Account'}
              </button>

              <button
                type="button"
                onClick={() => {
                  setIsRegistering(false)
                  setError('')
                }}
                className="btn btn-secondary"
                style={{
                  width: '100%',
                  fontSize: '0.875rem',
                  padding: '0.5rem'
                }}
              >
                Back to Login
              </button>
            </form>
          )}
        </div>

        <div style={{
          marginTop: '1.5rem',
          textAlign: 'center',
          color: '#666',
          fontSize: '0.75rem',
          fontFamily: 'monospace'
        }}>
          <p>A text-based RPG adventure</p>
        </div>
      </div>
    </div>
  )
}
