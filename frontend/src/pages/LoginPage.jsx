import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useApi'
import { useMobile } from '../hooks/useMobile'
import { colors, spacing } from '../styles/theme'
import GameButton from '../components/GameButton'
import GamePanel from '../components/GamePanel'
import GameInput from '../components/GameInput'
import GameText from '../components/GameText'
import TermsOfServiceModal from '../components/TermsOfServiceModal'
import ChangelogPanel from '../components/ChangelogPanel'

function useEmbers() {
  useEffect(() => {
    const canvas = document.getElementById('login-embers')
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    let raf
    let particles = []

    const resize = () => {
      canvas.width = window.innerWidth * window.devicePixelRatio
      canvas.height = window.innerHeight * window.devicePixelRatio
      canvas.style.width = window.innerWidth + 'px'
      canvas.style.height = window.innerHeight + 'px'
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
    }
    resize()
    window.addEventListener('resize', resize)

    const spawn = () => ({
      x: Math.random() * window.innerWidth,
      y: window.innerHeight + Math.random() * 40,
      vy: -0.15 - Math.random() * 0.35,
      vx: (Math.random() - 0.5) * 0.15,
      r: 0.6 + Math.random() * 1.4,
      life: 0,
      maxLife: 400 + Math.random() * 900,
      hue: Math.random() < 0.25 ? 'ember' : 'dust',
    })

    for (let i = 0; i < 60; i++) {
      const p = spawn()
      p.y = Math.random() * window.innerHeight
      p.life = Math.random() * p.maxLife
      particles.push(p)
    }

    const tick = () => {
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight)
      particles.forEach((p) => {
        p.x += p.vx
        p.y += p.vy
        p.life += 1
        const alpha = Math.sin((p.life / p.maxLife) * Math.PI) * 0.5
        ctx.fillStyle =
          p.hue === 'ember'
            ? `rgba(200,170,130,${alpha * 0.7})`
            : `rgba(232,228,216,${alpha * 0.4})`
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fill()
      })
      particles = particles.filter((p) => p.life < p.maxLife && p.y > -20)
      while (particles.length < 60) particles.push(spawn())
      raf = requestAnimationFrame(tick)
    }
    tick()

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
    }
  }, [])
}

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
  const isMobile = useMobile()
  useEmbers()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (isRegistering && password.length < 16) {
      setError('Password must be at least 16 characters long for cloud security.')
      return
    }

    setLoading(true)

    try {
      if (isRegistering) {
        await register(username, password, email)
      } else {
        await login(username, password)
      }
      // Token is now in localStorage, navigate and page will reload state
      navigate('/menu')
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Invalid username or password; try again or register a new account.')
      } else if (!err.response || err.response.status >= 500) {
        setError('The game server is unreachable. Please try again later.')
      } else {
        setError(err.response?.data?.message || 'Authentication failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#0d0d10',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: spacing.lg,
      position: 'relative',
    }}>
      <canvas
        id="login-embers"
        style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 2 }}
      />
      <div style={{
        position: 'fixed',
        bottom: 0, left: 0, right: 0,
        height: '320px',
        background: 'radial-gradient(ellipse at 50% 100%, rgba(168,192,212,0.07), transparent 70%)',
        pointerEvents: 'none',
        zIndex: 1,
      }} />
      {!isMobile && (
        <ChangelogPanel style={{ position: 'fixed', top: spacing.xl, right: spacing.xl, zIndex: 10 }} />
      )}
      <div style={{ width: '100%', maxWidth: '28rem', position: 'relative', zIndex: 3 }}>
        {isMobile && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: spacing.sm }}>
            <ChangelogPanel />
          </div>
        )}
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
          <button
            onClick={() => navigate('/landing')}
            style={{
              background: 'none',
              border: 'none',
              color: '#8a8578',
              cursor: 'pointer',
              fontFamily: 'monospace',
              fontSize: '11px',
              padding: 0,
              marginBottom: spacing.xs,
              transition: 'color 0.2s',
            }}
            onMouseEnter={(e) => e.target.style.color = '#b8b2a3'}
            onMouseLeave={(e) => e.target.style.color = '#8a8578'}
          >
            ← Back to home
          </button>
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
          <a
            href="https://nexusfidei.dev"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: colors.text.dim,
              fontFamily: 'monospace',
              fontSize: '11px',
              textDecoration: 'underline',
              transition: 'color 0.2s',
            }}
            onMouseEnter={(e) => e.target.style.color = colors.text.muted}
            onMouseLeave={(e) => e.target.style.color = colors.text.dim}
          >
            Nexus Fidei
          </a>
        </div>
      </div>

      {showTos && <TermsOfServiceModal onClose={() => setShowTos(false)} />}
    </div>
  )
}
