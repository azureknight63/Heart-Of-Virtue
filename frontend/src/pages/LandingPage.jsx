// Heart of Virtue — landing page
// Illuminated-manuscript aesthetic; oil-lamp cursor; calligraphy-swipe portraits;
// hand-drawn world map; inline login/register wired to the real auth API.

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useApi'
import SketchPortrait from '../components/landing/SketchPortrait'
import LandingWorldMap from '../components/landing/LandingWorldMap'
import '../styles/landing.css'

const BASE = import.meta.env.BASE_URL

// ── character data ────────────────────────────────────────────────────────────
const CHARACTERS = [
  {
    key: 'jean',
    name: 'Jean Claire',
    role: 'The Crusader Who Was Not',
    caption: 'fig. i — the pilgrim, rendered in pen and memory',
    prose: [
      'Jean believes he was a crusader. A knight called toward Jerusalem, clearing the enemies of humanity square by square. The memory has the specific weight of something lived. It is not.',
      'He was an HVAC technician. He went to Jerusalem on pilgrimage with his wife Amelia and his daughter Regina. In the crowded lanes of the Old City, a bomb found them. He was holding Regina when it went off. He survived; she did not.',
      "The world of Aurelion receives him now — all of it, every stone and every stranger — while his body lies quiet in a hospital he does not remember. His faith has not broken cleanly. It has collapsed at the center, because he chose the pilgrimage, and he cannot be angry at God without implicating himself.",
    ],
    quote: "I'm sorry.",
    image: `${BASE}assets/landing/portraits/jean.png`,
  },
  {
    key: 'gorran',
    name: 'Gorran',
    role: 'The Golemite — Fifteen Centuries Still',
    caption: 'fig. ii — the steadfast, stone-grown and watchful',
    prose: [
      'Gorran is one thousand five hundred years old, which for a Golemite is adulthood — seasoned, but not ancient. He stood watch over a sealed passage for centuries, companioned only by the slow trickle of water and the grinding of stone. The long quiet taught him to attend.',
      'He wears a star-shaped patch of luminous moss on his shoulder, grown over a wound from the War of the Shifting Sands. He grieves quietly for a companion long dead beneath a rockfall. He sees that grief again in Jean, and so he follows.',
      'He cannot, at first, speak Jean\'s language. He will learn, word by effortful word, until a particular scene at a particular crisis demands the few sentences he has earned. He does not deflect questions. He allows them to stay in the air.',
    ],
    quote: 'He is there, and you may look, and that is all.',
    image: `${BASE}assets/landing/portraits/gorran.png`,
  },
  {
    key: 'mara',
    name: 'Mara',
    role: 'Scavenger, River-Crosser, Reader of Small Things',
    caption: 'fig. iii — the cartographer of unclaimed places',
    prose: [
      'Mara is twenty-seven and occupies exactly as much space as she needs. Her gaze arrives before you do — green, immediate, extracting without cruelty. She is reading. She reads everything. She has not yet admitted to herself that looking is what she is doing.',
      'She works the western approaches: the river crossings, the cave systems, the outer edges of the Wailing Badlands. She charges a fair fee and does not negotiate it down. Her sardonic wit is a walking stick, not a weapon. She uses it to keep a steady pace through terrain that might otherwise give her trouble.',
      'Around her neck, on a worn cord, hangs a crucifix she will call an oddity — something she found in a ruin that felt preserved, and has never catalogued and never sold. It sits outside her system entirely. Jean notices it, and then works not to notice it. She notices him noticing, and notices him look away, and files both without comment.',
    ],
    quote: "The locals call it the Wailing Badlands. They don't come here.",
    image: `${BASE}assets/landing/portraits/mara.png`,
  },
  {
    key: 'devet',
    name: 'Devet',
    role: 'The Cook Who Has Stopped Waiting',
    caption: 'fig. iv — old as mountains, tending the pot',
    prose: [
      'Devet is old in a way that does not invite estimation. He has been old for a long time and has decided this is fine. His expression at rest is not stern but settled. He looks like a man who has stopped waiting.',
      'He cooks. He has elevated it to a form of fluency — he knows what people need from food before they do, and delivers it without being asked. In cold weather, the bowl arrives at the right moment. In grief, the portion is larger and the seasoning simpler. He makes no reference to the calculation.',
      'He finds people endlessly comprehensible. His humor lives in what he leaves out. When Jean first arrives at the camp carrying what he is not yet ready to look at, Devet offers food. This is not a gesture. It is an assessment.',
    ],
    quote: 'Soup.',
    image: `${BASE}assets/landing/portraits/devet.png`,
  },
  {
    key: 'liss',
    name: 'Liss',
    role: 'The Child Who Asks',
    caption: 'fig. v — a pocket of stones, a feather, a question',
    prose: [
      'Liss is old enough to carry her share of camp work and young enough that she has not yet learned which questions are rude to ask. She speaks at the pace of her thinking, which is faster than most conversations. She has started and abandoned more sentences than she has finished.',
      'She collects interesting things — a strangely-colored stone, a feather with a bent shaft, a scrap of something whose origin she has invented a story about. She leaves most of it behind when camp moves. New interesting things will present themselves.',
      'She is not reading Jean\'s grief. She does not have the architecture for it. She asks him where he is going and whether he knows which plants are edible on that route, and this is, paradoxically, a relief. She circles Gorran like a patient project. She has never been this close to a Golemite.',
    ],
    quote: "You look like you're dressed for a different story.",
    image: `${BASE}assets/landing/portraits/liss.png`,
  },
]

// ── embers canvas ─────────────────────────────────────────────────────────────
function useEmbers() {
  useEffect(() => {
    const canvas = document.getElementById('lp-embers')
    if (!canvas) return
    const ctx = canvas.getContext('2d')
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

// ── oil-lamp cursor ───────────────────────────────────────────────────────────
function useCandleCursor() {
  useEffect(() => {
    const glow = document.getElementById('lp-candle-glow')
    const lamp = document.getElementById('lp-oil-lamp')
    const root = document.documentElement
    let tx = window.innerWidth / 2
    let ty = window.innerHeight / 2
    let x = tx,
      y = ty
    let raf

    const onMove = (e) => {
      tx = e.clientX
      ty = e.clientY
    }

    const LAMP_W = 64
    const LAMP_H = 84
    const LAMP_OFFSET_X = 6
    const LAMP_OFFSET_Y = 4

    const tick = () => {
      x += (tx - x) * 0.14
      y += (ty - y) * 0.14
      const t = performance.now() / 320
      const jx = Math.sin(t * 1.7) * 1.2 + Math.sin(t * 3.1) * 0.5
      const jy = Math.cos(t * 2.2) * 1.0 + Math.sin(t * 4.0) * 0.4
      const flick = 0.88 + Math.sin(t * 5.3) * 0.06 + Math.sin(t * 11.1) * 0.04

      const lampX = x + LAMP_OFFSET_X + jx * 0.4
      const lampY = y + LAMP_OFFSET_Y + jy * 0.4
      const flameX = lampX + LAMP_W * 0.5
      const flameY = lampY + LAMP_H * 0.345

      if (lamp) lamp.style.transform = `translate3d(${lampX}px,${lampY}px,0)`
      if (glow)
        glow.style.transform = `translate3d(${flameX - 360}px,${flameY - 360}px,0) scale(${flick})`

      root.style.setProperty('--cx', `${flameX}px`)
      root.style.setProperty('--cy', `${flameY}px`)
      root.style.setProperty('--flick', flick.toFixed(3))

      // Per-element local cursor coords for lit-text and portrait overlays
      document.querySelectorAll('.lit-target').forEach((el) => {
        const r = el.getBoundingClientRect()
        if (r.bottom < -200 || r.top > window.innerHeight + 200) return
        const lx = ((flameX - r.left) / r.width) * 100
        const ly = ((flameY - r.top) / r.height) * 100
        el.style.setProperty('--lcx', `${lx}%`)
        el.style.setProperty('--lcy', `${ly}%`)
      })

      // Proximity reveal for portraits and world map
      document.querySelectorAll('.sketch-portrait, .world-map-wrap').forEach((el) => {
        const r = el.getBoundingClientRect()
        if (r.bottom < -400 || r.top > window.innerHeight + 400) return
        const cx = r.left + r.width / 2
        const cy = r.top + r.height / 2
        const dist = Math.hypot(flameX - cx, flameY - cy)
        const inner = Math.min(r.width, r.height) * 0.25
        const outer = Math.min(r.width, r.height) * 1.1
        const tVal = Math.max(0, Math.min(1, 1 - (dist - inner) / (outer - inner)))
        const eased = tVal * tVal * (3 - 2 * tVal)
        const baseline = 0.55
        el.style.setProperty('--mask-opacity', (baseline + (1 - baseline) * eased).toFixed(3))
      })

      raf = requestAnimationFrame(tick)
    }

    window.addEventListener('pointermove', onMove)
    tick()
    return () => {
      window.removeEventListener('pointermove', onMove)
      cancelAnimationFrame(raf)
    }
  }, [])
}

// ── lit-text: tag elements on mount for the rAF loop ─────────────────────────
function useLitText() {
  useEffect(() => {
    const sel =
      '.hero-title, .hero-sub, .hero-prose p, .section-title, .section-sub, ' +
      '.section-eyebrow, .character-name, .character-role, .character-prose p, ' +
      '.character-quote, .character-caption, .character-initial, .cta, ' +
      '.begin-foot, .hero-eyebrow, footer p, .tabs button, .field label, ' +
      '.foot-license, .sketch-portrait'
    const tag = () =>
      document.querySelectorAll(sel).forEach((el) => el.classList.add('lit-target'))
    tag()
    const mo = new MutationObserver(tag)
    mo.observe(document.body, { childList: true, subtree: true })
    return () => mo.disconnect()
  }, [])
}

// ── scroll reveal ─────────────────────────────────────────────────────────────
function useReveal() {
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('revealed')
            io.unobserve(e.target)
          }
        })
      },
      { threshold: 0.18 },
    )
    document
      .querySelectorAll('.reveal, .character-prose')
      .forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [])
}

// ── tweaks panel ──────────────────────────────────────────────────────────────
const TWEAK_DEFAULTS = {
  accent: '#a8c0d4',
  titleFont: 'Cormorant Garamond',
  sketchSpeed: 0.5,
}

const ACCENT_PRESETS = [
  { value: '#a8c0d4', label: 'Moonlight' },
  { value: '#c9a76a', label: 'Candle' },
  { value: '#b85a3e', label: 'Ember' },
  { value: '#7a8a7a', label: 'Moss' },
  { value: '#e8e4d8', label: 'Chalk' },
]

const FONT_OPTIONS = [
  { value: 'Cormorant Garamond', label: 'Cormorant' },
  { value: 'EB Garamond', label: 'Garamond' },
  { value: 'Cinzel', label: 'Cinzel' },
  { value: 'IM Fell English', label: 'IM Fell' },
  { value: 'Uncial Antiqua', label: 'Uncial' },
]

const tweakPanelStyle = {
  position: 'fixed',
  right: 16,
  bottom: 16,
  width: 280,
  maxHeight: 'calc(100vh - 32px)',
  display: 'flex',
  flexDirection: 'column',
  background: 'rgba(250,249,247,.9)',
  color: '#29261b',
  backdropFilter: 'blur(24px) saturate(160%)',
  WebkitBackdropFilter: 'blur(24px) saturate(160%)',
  border: '.5px solid rgba(255,255,255,.6)',
  borderRadius: 14,
  boxShadow: '0 1px 0 rgba(255,255,255,.5) inset, 0 12px 40px rgba(0,0,0,.18)',
  font: '11.5px/1.4 ui-sans-serif,system-ui,-apple-system,sans-serif',
  overflow: 'hidden',
  zIndex: 2147483646,
  cursor: 'auto',
}

function TweaksPanel({ tweaks, setTweak, open, onClose }) {
  if (!open) return null
  return (
    <div style={tweakPanelStyle}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 8px 10px 14px',
          userSelect: 'none',
          borderBottom: '1px solid rgba(0,0,0,.06)',
        }}
      >
        <b style={{ fontSize: 12, fontWeight: 600 }}>Tweaks</b>
        <button
          onClick={onClose}
          style={{
            appearance: 'none',
            border: 0,
            background: 'transparent',
            color: 'rgba(41,38,27,.55)',
            width: 22,
            height: 22,
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 13,
          }}
          aria-label="Close tweaks"
        >
          ✕
        </button>
      </div>
      <div
        style={{
          padding: '2px 14px 14px',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
          overflowY: 'auto',
        }}
      >
        {/* Accent colour */}
        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', color: 'rgba(41,38,27,.45)', paddingTop: 10 }}>Accent</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 500, fontSize: 11.5 }}>Interaction glow</span>
            <input
              type="color"
              value={tweaks.accent}
              onChange={(e) => setTweak('accent', e.target.value)}
              style={{ width: 56, height: 22, border: '.5px solid rgba(0,0,0,.1)', borderRadius: 6, padding: 0, cursor: 'pointer', background: 'transparent' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontWeight: 500, fontSize: 11.5 }}>Preset</span>
            <select
              value={tweaks.accent}
              onChange={(e) => setTweak('accent', e.target.value)}
              style={{ appearance: 'none', WebkitAppearance: 'none', height: 26, padding: '0 8px', border: '.5px solid rgba(0,0,0,.1)', borderRadius: 7, background: 'rgba(255,255,255,.6)', font: 'inherit', outline: 'none', cursor: 'pointer' }}
            >
              {ACCENT_PRESETS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Title font */}
        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', color: 'rgba(41,38,27,.45)', paddingTop: 10 }}>Title font</div>
        <select
          value={tweaks.titleFont}
          onChange={(e) => setTweak('titleFont', e.target.value)}
          style={{ appearance: 'none', WebkitAppearance: 'none', height: 26, padding: '0 8px', border: '.5px solid rgba(0,0,0,.1)', borderRadius: 7, background: 'rgba(255,255,255,.6)', font: 'inherit', outline: 'none', cursor: 'pointer' }}
        >
          {FONT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        {/* Sketch speed */}
        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', color: 'rgba(41,38,27,.45)', paddingTop: 10 }}>Sketch animation</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 500, fontSize: 11.5 }}>Speed</span>
            <span style={{ color: 'rgba(41,38,27,.5)' }}>{tweaks.sketchSpeed}×</span>
          </div>
          <input
            type="range"
            min={0.4} max={3} step={0.1}
            value={tweaks.sketchSpeed}
            onChange={(e) => setTweak('sketchSpeed', Number(e.target.value))}
            style={{ width: '100%', accentColor: '#a8c0d4', cursor: 'pointer' }}
          />
        </div>
        <p style={{ margin: '8px 0 0', fontSize: 10, color: 'rgba(41,38,27,.4)', lineHeight: 1.5 }}>
          Open with <kbd style={{ background: 'rgba(0,0,0,.06)', padding: '1px 5px', borderRadius: 4, fontFamily: 'monospace' }}>Ctrl+Shift+T</kbd>
        </p>
      </div>
    </div>
  )
}

// ── ornament SVG ──────────────────────────────────────────────────────────────
function Ornament({ className }) {
  return (
    <svg
      viewBox="0 0 320 40"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="0.8"
      strokeLinecap="round"
    >
      <path d="M 0 20 L 100 20" />
      <path d="M 220 20 L 320 20" />
      <path d="M 110 20 C 120 10, 140 10, 150 20 C 160 30, 180 30, 190 20 C 200 10, 210 10, 210 20" />
      <path d="M 160 20 L 160 8 M 160 20 L 160 32" strokeWidth="0.6" />
      <circle cx="160" cy="20" r="2.4" fill="currentColor" stroke="none" />
      <circle cx="105" cy="20" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="215" cy="20" r="1.4" fill="currentColor" stroke="none" />
    </svg>
  )
}

// ── Hero ──────────────────────────────────────────────────────────────────────
function Hero({ onBegin }) {
  return (
    <section className="hero">
      <Ornament className="hero-ornament" />
      <p className="hero-eyebrow">A text adventure of faith, grief &amp; quiet companions</p>
      <h1 className="hero-title">
        Heart
        <span className="of">of</span>
        <em>Virtue</em>
      </h1>
      <div className="hero-rule" />
      <p className="hero-sub">
        A theatre of the mind. All graphics drawn in the ink of sentences —
        rendered, as they always have been, on the page behind your eyes.
      </p>
      <button className="cta" onClick={onBegin}>
        <span className="cta-mark">✦</span>
        Begin The Journey
        <span className="cta-mark">✦</span>
      </button>
      <div className="hero-prose">
        <p>
          Jean Claire opens his eyes to a world that is not his own. The sky above Aurelion is
          the colour of old chalk on slate. A stone-skinned figure waits beside him, patient
          as geology. Somewhere further west — beyond the mountain citadels, across a river
          he cannot yet name — a woman is already reading him before he has registered her
          as a person rather than a feature of the camp.
        </p>
        <p>
          He believes he was a crusader. He carries a mace that was once religious kit. The
          memories he has of a market lane in Jerusalem come back in fragments he is not
          yet ready to assemble. This world has been placed around him with care, although
          he will never know this, and the game will never state it. You will only infer.
        </p>
        <p style={{ textAlign: 'center', fontStyle: 'italic', color: 'var(--ink-faint)', marginTop: 40 }}>
          — what follows is a chronicle of the companions he meets along the way.
        </p>
      </div>
      <div className="hero-scroll-hint">
        <span>scroll onward</span>
        <svg width="14" height="36" viewBox="0 0 14 36" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round">
          <path d="M 7 2 L 7 30" />
          <path d="M 2 24 L 7 30 L 12 24" />
        </svg>
      </div>
    </section>
  )
}

// ── Characters ────────────────────────────────────────────────────────────────
function Characters({ speed }) {
  return (
    <section className="characters" id="characters">
      <div className="reveal">
        <p className="section-eyebrow">Dramatis Personae</p>
        <h2 className="section-title">Those who walk with Jean</h2>
        <div className="section-rule" />
        <p className="section-sub">
          Five companions, each drawn in the same ink. Each is the shape of a
          grief Jean does not yet recognise as his own.
        </p>
      </div>

      {CHARACTERS.map((c, i) => (
        <article key={c.key} className={`character ${i % 2 === 1 ? 'reverse' : ''}`}>
          <div className="character-art">
            <SketchPortrait src={c.image} speed={speed} alt={c.name} />
            <div className="character-caption">{c.caption}</div>
          </div>
          <div className="character-prose">
            <p className="character-initial" aria-hidden="true">
              {c.name.charAt(0)}
            </p>
            <h3 className="character-name">{c.name}</h3>
            <p className="character-role">{c.role}</p>
            {c.prose.map((para, j) => (
              <p key={j}>{para}</p>
            ))}
            <blockquote className="character-quote">{c.quote}</blockquote>
          </div>
        </article>
      ))}
    </section>
  )
}

// ── World ─────────────────────────────────────────────────────────────────────
function WorldSection({ speed }) {
  return (
    <section className="world">
      <div className="reveal">
        <p className="section-eyebrow">Cartography</p>
        <h2 className="section-title">The World of Aurelion</h2>
        <div className="section-rule" />
        <p className="section-sub">
          A land built, some say, by a careful hand for a single soul — and
          kind enough not to say so aloud.
        </p>
      </div>
      <LandingWorldMap speed={speed} />
    </section>
  )
}

// ── Begin (login/register) ────────────────────────────────────────────────────
function BeginSection() {
  const [tab, setTab] = useState('enter')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const { login, register } = useAuth()
  const navigate = useNavigate()

  const handleLogin = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const data = new FormData(e.target)
    try {
      await login(data.get('username'), data.get('password'))
      navigate('/game')
    } catch (err) {
      setError(err?.response?.data?.error || err?.message || 'Invalid credentials.')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const data = new FormData(e.target)
    // AuthContext signature: register(username, password, email)
    try {
      await register(data.get('username'), data.get('password'), data.get('email'))
      navigate('/game')
    } catch (err) {
      setError(err?.response?.data?.error || err?.message || 'Registration failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="begin" id="begin">
      <div className="reveal">
        <p className="section-eyebrow">Threshold</p>
        <h2 className="section-title">Cross the river</h2>
        <div className="section-rule" />
        <p className="section-sub">
          Sign your name into the book. Or take up one already written.
        </p>
      </div>
      <div className="begin-card">
        <div className="tabs">
          <button
            className={tab === 'enter' ? 'active' : ''}
            onClick={() => { setTab('enter'); setError(null) }}
          >
            Return
          </button>
          <button
            className={tab === 'new' ? 'active' : ''}
            onClick={() => { setTab('new'); setError(null) }}
          >
            Begin anew
          </button>
        </div>

        {tab === 'enter' ? (
          <form onSubmit={handleLogin}>
            <div className="field">
              <label>Name of traveller</label>
              <input name="username" type="text" placeholder="Jean, son of…" required />
            </div>
            <div className="field">
              <label>Passphrase</label>
              <input name="password" type="password" placeholder="something you remember" required />
            </div>
            {error && <p className="begin-error">{error}</p>}
            <button className="submit" type="submit" disabled={loading}>
              {loading ? '…' : '✦ Enter Aurelion ✦'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister}>
            <div className="field">
              <label>Name the traveller</label>
              <input name="username" type="text" placeholder="what they will call you at the fire" required />
            </div>
            <div className="field">
              <label>A way to reach you</label>
              <input name="email" type="email" placeholder="your.carrier@pigeon.net" required />
            </div>
            <div className="field">
              <label>Passphrase</label>
              <input name="password" type="password" placeholder="at least a sentence long" minLength={16} required />
            </div>
            {error && <p className="begin-error">{error}</p>}
            <button className="submit" type="submit" disabled={loading}>
              {loading ? '…' : '✦ Take up the lance ✦'}
            </button>
          </form>
        )}

        <p className="begin-foot">
          The journey is free.{' '}
          <a href="https://github.com/azureknight63/Heart-Of-Virtue" target="_blank" rel="noreferrer">
            A closer reckoning of what that means.
          </a>
        </p>
      </div>
    </section>
  )
}

// ── Footer ────────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer>
      <Ornament className="foot-ornament" />
      <p style={{ fontFamily: 'var(--font-title)', fontStyle: 'italic', fontSize: 18, color: 'var(--ink-dim)' }}>
        Heart of Virtue
      </p>
      <p>A text adventure by Alexander Egbert.</p>
      <p>
        <a href="https://github.com/azureknight63/Heart-Of-Virtue" target="_blank" rel="noreferrer">
          github.com/azureknight63/Heart-Of-Virtue
        </a>
      </p>
      <p className="foot-license">
        Code: PolyForm Noncommercial 1.0.0 &nbsp;·&nbsp; Story, Lore &amp; Creative Assets: CC BY-NC-ND 4.0
        <br />
        © 2025 Alexander Egbert. All rights reserved. Rendered in the ink of sentences.
      </p>
    </footer>
  )
}

// ── LandingPage ───────────────────────────────────────────────────────────────
export default function LandingPage() {
  const [tweaks, setTweaksState] = useState(TWEAK_DEFAULTS)
  const [tweaksOpen, setTweaksOpen] = useState(false)

  const setTweak = (key, val) =>
    setTweaksState((prev) => ({ ...prev, [key]: val }))

  // Apply tweaks to CSS custom properties
  useEffect(() => {
    document.documentElement.style.setProperty('--accent', tweaks.accent)
    document.documentElement.style.setProperty('--accent-dim', tweaks.accent + '99')
    document.documentElement.style.setProperty(
      '--font-title',
      `"${tweaks.titleFont}", Georgia, serif`,
    )
    document.documentElement.style.setProperty('--sketch-speed', tweaks.sketchSpeed)
  }, [tweaks])

  // Ctrl+Shift+T toggles the tweaks panel
  useEffect(() => {
    const handler = (e) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'T') {
        setTweaksOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEmbers()
  useReveal()
  useCandleCursor()
  useLitText()

  const handleBegin = (e) => {
    e.preventDefault()
    document.getElementById('begin')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="landing-page">
      {/* Fixed atmospheric layers */}
      <div className="lp-grain" aria-hidden="true" />
      <div className="lp-cursor-shadow" aria-hidden="true" />

      {/* Nexus Fidei logo */}
      <a
        className="nx-logo-link"
        href="https://nexusfidei.dev"
        target="_blank"
        rel="noopener noreferrer"
        title="Go to the developer's page - Nexus Fidei"
        aria-label="Go to the developer's page - Nexus Fidei"
      >
        <span className="nx-logo-glow" aria-hidden="true" />
        <img
          className="nx-logo-img"
          src={`${BASE}assets/landing/nexus-fidei-logo.png`}
          alt="Nexus Fidei"
        />
      </a>

      {/* Canvas / cursor overlays */}
      <canvas id="lp-embers" />
      <div id="lp-candle-glow" aria-hidden="true" />
      <div id="lp-oil-lamp" aria-hidden="true" />

      {/* Page content */}
      <div className="lp-page">
        <Hero onBegin={handleBegin} />
        <Characters speed={tweaks.sketchSpeed} />
        <WorldSection speed={tweaks.sketchSpeed} />
        <BeginSection />
        <Footer />
      </div>

      {/* Tweaks panel (Ctrl+Shift+T) */}
      <TweaksPanel
        tweaks={tweaks}
        setTweak={setTweak}
        open={tweaksOpen}
        onClose={() => setTweaksOpen(false)}
      />
    </div>
  )
}
