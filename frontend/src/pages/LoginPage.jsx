import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useApi'
import { colors, spacing } from '../styles/theme'
import GameButton from '../components/GameButton'
import GamePanel from '../components/GamePanel'
import GameInput from '../components/GameInput'
import GameText from '../components/GameText'
import TermsOfServiceModal from '../components/TermsOfServiceModal'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [showTos, setShowTos] = useState(false)
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
      navigate('/menu')
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
      backgroundColor: colors.bg.main,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: spacing.lg
    }}>
      <div style={{ width: '100%', maxWidth: '28rem' }}>
        <GamePanel padding="xxl" borderVariant="success" className="animate-fade-in">
          <div style={{ textAlign: 'center', marginBottom: spacing.xxl }}>
            <GameText variant="primary" size="xxl" weight="bold" as="h1" style={{ textAlign: 'center', marginBottom: spacing.xs }}>
              Heart of Virtue
            </GameText>
            <GameText variant="accent" size="sm" style={{ textAlign: 'center' }}>
              Enter the world of heroism and virtue
            </GameText>
          </div>

          {!isRegistering ? (
            <form
              key="login-form"
              id="login-form"
              method="POST"
              action="/login"
              onSubmit={handleSubmit}
              style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}
            >
              <GameInput
                label="Username"
                id="username"
                name="username"
                autoComplete="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your name"
                required
              />

              <GameInput
                label="Password"
                id="password"
                name="password"
                autoComplete="current-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                aria-label="Password"
              />

              {error && (
                <div style={{
                  padding: spacing.md,
                  backgroundColor: colors.bg.error,
                  border: `1px solid ${colors.border.danger}`,
                  borderRadius: '0.25rem',
                  textAlign: 'center',
                }}>
                  <GameText variant="danger" size="sm">
                    {error}
                  </GameText>
                </div>
              )}

              <div style={{ marginTop: spacing.lg, display: 'flex', flexDirection: 'column', gap: spacing.md }}>
                <GameButton
                  type="submit"
                  variant="primary"
                  disabled={loading}
                  aria-label="Submit login form"
                  style={{ width: '100%' }}
                >
                  {loading ? 'Processing...' : 'Enter Game'}
                </GameButton>

                <GameButton
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setIsRegistering(true)
                    setError('')
                  }}
                  style={{ width: '100%' }}
                  size="small"
                >
                  New to the realm? Create Account
                </GameButton>
              </div>
            </form>
          ) : (
            <form
              key="register-form"
              id="register-form"
              method="POST"
              action="/register"
              onSubmit={handleSubmit}
              style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}
            >
              <GameInput
                label="Username"
                id="reg-username"
                name="username"
                autoComplete="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your name"
                required
              />

              <div>
                <GameInput
                  label="Password"
                  id="reg-password"
                  name="password"
                  autoComplete="new-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 16 characters"
                  required
                  minLength={16}
                  aria-label="New Password"
                />
                <GameText variant="dim" size="xs" style={{ marginTop: spacing.xs }}>
                  Security: Argon2id hashing active
                </GameText>
              </div>

              <GameInput
                label="Email Address"
                id="reg-email"
                name="email"
                autoComplete="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="For account recovery (encrypted)"
                required
              />

              {error && (
                <div style={{
                  padding: spacing.md,
                  backgroundColor: colors.bg.error,
                  border: `1px solid ${colors.border.danger}`,
                  borderRadius: '0.25rem',
                  textAlign: 'center',
                }}>
                  <GameText variant="danger" size="sm">
                    {error}
                  </GameText>
                </div>
              )}

              <div style={{ marginTop: spacing.lg, display: 'flex', flexDirection: 'column', gap: spacing.md }}>
                <GameButton
                  type="submit"
                  variant="primary"
                  disabled={loading}
                  aria-label="Submit registration form"
                  style={{ width: '100%' }}
                >
                  {loading ? 'Processing...' : 'Create Account'}
                </GameButton>

                <GameButton
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setIsRegistering(false)
                    setError('')
                  }}
                  style={{ width: '100%' }}
                  size="small"
                >
                  Back to Login
                </GameButton>
              </div>
            </form>
          )}
        </GamePanel>

        <div style={{
          marginTop: spacing.xxl,
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: spacing.sm,
        }}>
          <GameText variant="dim" size="xs" style={{ fontFamily: 'monospace' }}>
            A text-based RPG adventure
          </GameText>
          <button
            onClick={() => setShowTos(true)}
            style={{
              background: 'none',
              border: 'none',
              color: colors.text.dim,
              cursor: 'pointer',
              fontFamily: 'monospace',
              fontSize: '11px',
              textDecoration: 'underline',
              padding: 0,
              transition: 'color 0.2s',
            }}
            onMouseEnter={(e) => e.target.style.color = colors.text.muted}
            onMouseLeave={(e) => e.target.style.color = colors.text.dim}
          >
            Terms of Service &amp; Privacy Policy
          </button>
        </div>
      </div>

      {showTos && <TermsOfServiceModal onClose={() => setShowTos(false)} />}
    </div>
  )
}
