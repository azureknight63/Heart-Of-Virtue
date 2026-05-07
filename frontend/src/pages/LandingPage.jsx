// Heart of Virtue — landing page
// Illuminated-manuscript aesthetic; oil-lamp cursor; calligraphy-swipe portraits;
// hand-drawn world map; inline login/register wired to the real auth API.

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import SketchPortrait from '../components/landing/SketchPortrait'
import LandingWorldMap from '../components/landing/LandingWorldMap'
import '../styles/landing.css'

const BASE = import.meta.env.BASE_URL

// ── character data ────────────────────────────────────────────────────────────
const CHARACTERS = [
  {
    key: 'jean',
    name: 'Jean Claire',
    role: 'The Crusader Adrift',
    caption: 'fig. i — the pilgrim, rendered in pen and memory',
    prose: [
      'Jean remembers he was a crusader. A knight called toward Jerusalem, clearing the enemies of humanity square by square. The memory has the specific weight of something lived.',
      'In the crowded lanes of the Old City, chaos and fury found him. Suddenly, all went dark.',
      "The world of Aurelion receives him now — all of it, every stone and every stranger. He knows he must find his way home. He knows there are some waiting for him there - if only he could remember.",
    ],
    quote: "I can figure out what's broken and fix it.",
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
      'He is not one for many words and cannot speak Jean\'s language. He tends to let questions hang in the air or eventually answer themselves.',
    ],
    quote: '*Unintelligible rumbling*',
    image: `${BASE}assets/landing/portraits/gorran.png`,
  },
  {
    key: 'mara',
    name: 'Mara',
    role: 'Scavenger, River-Crosser, Reader of Small Things',
    caption: 'fig. iii — the cartographer of unclaimed places',
    prose: [
      'Mara occupies exactly as much space as she needs. Her gaze arrives before you do — sharp, immediate, extracting without cruelty, like a surgeon\'s scalpel. She is reading - she reads everything.',
      'She works the western approaches: the river crossings, the cave systems, the outer edges of the Wailing Badlands. She charges a fair fee and does not negotiate it down. Her sardonic wit is a walking stick, not a weapon. She uses it to keep a steady pace through terrain that might otherwise give her trouble.',
      'Around her neck, on a worn cord, hangs a crucifix she will call an oddity — in truth, a mystery she cannot read. That is why she keeps it.',
    ],
    quote: "The locals call it the Wailing Badlands. Not sure if it's the lands that wail, or those who flee it.",
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
      'Liss is old enough to carry her share of camp work and young enough for unbridled questions. She speaks at the pace of thought. She has started and abandoned more sentences than she has finished.',
      'She collects interesting things — a strangely-colored stone, a feather with a bent shaft, a scrap of some unknown material - about whose origin she has invented a story. She leaves most of it behind when camp moves. New interesting things will always present themselves.',
      'She does not read grief. She does not have the architecture for it. She asks where one is going and whether one knows which plants are edible on that route. She circles Gorran like a curious cat. She has never been this close to a Golemite.',
    ],
    quote: "You look like you're dressed for a very strange party.",
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

const SKETCH_SPEED = 0.5

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
      <p className="hero-eyebrow">An adventure of wonder, faith, grief, &amp; companionship</p>
      <h1 className="hero-title">
        Heart
        <span className="of">of</span>
        <em>Virtue</em>
      </h1>
      <div className="hero-rule" />
      <p className="hero-sub">
        A theatre of the mind. Most graphics drawn in the ink of sentences —
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
          the colour of old chalk on slate.
        </p>
        <div style={{ textAlign: 'center', color: 'var(--ink-faint)', margin: '20px 0', fontSize: '12px' }}>◆</div>
        <p>
          A stone-skinned figure, patient as geology, becomes his timely savior.
        </p>
        <div style={{ textAlign: 'center', color: 'var(--ink-faint)', margin: '20px 0', fontSize: '12px' }}>◆</div>
        <p>
          Somewhere to the southwest — beyond the mountain citadels, across a river
          he cannot yet name — a woman is moving travelers for a price, waiting to discover her true purpose.
        </p>
        <div style={{ textAlign: 'center', color: 'var(--ink-faint)', margin: '20px 0', fontSize: '12px' }}>◆</div>
        <p>
          Jean remembers he was a crusader. It's etched into the depths of his mind. The
          memories he has of a market lane in Jerusalem come back in fragments he is not
          yet ready to assemble. This world seems to have been placed around him with care.
        </p>
        <div style={{ textAlign: 'center', color: 'var(--ink-faint)', margin: '20px 0', fontSize: '12px' }}>◆</div>
        <p style={{ textAlign: 'center', fontStyle: 'italic', color: 'var(--ink-faint)', marginTop: 40 }}>
          — what will he discover as his story unfolds?
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
        <h2 className="section-title">Those who walk the path</h2>
        <div className="section-rule" />
        <p className="section-sub">
          Five companions, each drawn in the same ink. Each ready to turn the page.
        </p>
      </div>

      {CHARACTERS.map((c, i) => (
        <article key={c.key} className={`character ${i % 2 === 1 ? 'reverse' : ''}`}>
          <div className="character-art">
            <SketchPortrait src={c.image} speed={speed} alt={c.name} />
            <div className="character-caption">{c.caption}</div>
          </div>
          <div className="character-prose">
            <div className="character-name-group">
              <h2 className="character-initial" aria-hidden="true">
                {c.name.charAt(0)}
              </h2>
              <h3 className="character-name">{c.name.slice(1)}</h3>
            </div>
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
          A land of darkness and light - of strife and peace - of grief and hope.
        </p>
      </div>
      <LandingWorldMap speed={speed} />
    </section>
  )
}

// ── Begin ─────────────────────────────────────────────────────────────────────
function BeginSection({ onBegin }) {
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
      <button className="cta" onClick={onBegin}>
        <span className="cta-mark">✦</span>
        Begin The Journey
        <span className="cta-mark">✦</span>
      </button>
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
  useEmbers()
  useReveal()
  useCandleCursor()
  useLitText()

  const navigate = useNavigate()
  const handleBegin = (e) => {
    e.preventDefault()
    navigate('/login')
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
        <Characters speed={SKETCH_SPEED} />
        <WorldSection speed={SKETCH_SPEED} />
        <BeginSection onBegin={handleBegin} />
        <Footer />
      </div>
    </div>
  )
}
