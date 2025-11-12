import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useApi'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
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
        await register(username, password)
      } else {
        await login(username, password)
      }
      // Token is now in localStorage, navigate and page will reload state
      window.location.href = '/game'
    } catch (err) {
      setError(err.response?.data?.message || 'Authentication failed. Please try again.')
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

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={{
                display: 'block',
                color: '#00ff88',
                fontSize: '0.875rem',
                fontWeight: 'bold',
                marginBottom: '0.5rem'
              }}>Username</label>
              <input
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
              <label style={{
                display: 'block',
                color: '#00ff88',
                fontSize: '0.875rem',
                fontWeight: 'bold',
                marginBottom: '0.5rem'
              }}>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field"
                placeholder="Enter your password"
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

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary"
              style={{
                width: '100%',
                fontWeight: 'bold',
                padding: '0.5rem',
                marginTop: '1.5rem',
                opacity: loading ? 0.5 : 1
              }}
            >
              {loading ? 'Processing...' : isRegistering ? 'Create Account' : 'Enter Game'}
            </button>

            <button
              type="button"
              onClick={() => {
                setIsRegistering(!isRegistering)
                setError('')
              }}
              className="btn btn-secondary"
              style={{
                width: '100%',
                fontSize: '0.875rem',
                padding: '0.5rem'
              }}
            >
              {isRegistering ? 'Back to Login' : 'New to the realm? Create Account'}
            </button>
          </form>
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
