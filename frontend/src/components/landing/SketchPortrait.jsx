// Calligraphy-swipe sketch reveal.
// Renders a portrait image into a canvas via successive ink-brush strokes that
// sweep at random angles, each stroke uncovering a band of the image.  The
// final stroke is a wide vertical swipe through the centre to guarantee the
// character's face is fully visible.

import { useRef, useState, useEffect } from 'react'

function mulberry32(a) {
  return function () {
    let t = (a += 0x6d2b79f5)
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export default function SketchPortrait({ src, speed = 1, alt = '' }) {
  const wrapRef = useRef(null)
  const canvasRef = useRef(null)
  const [revealed, setRevealed] = useState(false)

  // Trigger the animation when the element enters the viewport
  useEffect(() => {
    if (!wrapRef.current) return
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            setRevealed(true)
            io.disconnect()
          }
        })
      },
      { threshold: 0.25 },
    )
    io.observe(wrapRef.current)
    return () => io.disconnect()
  }, [])

  // Run the calligraphy-swipe animation once revealed
  useEffect(() => {
    if (!revealed || !canvasRef.current) return
    const canvas = canvasRef.current
    const W = (canvas.width = 700)
    const H = (canvas.height = 700)
    const ctx = canvas.getContext('2d')

    let cancelled = false
    let raf

    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      if (cancelled) return

      // Offscreen canvas with the source image
      const off = document.createElement('canvas')
      off.width = W
      off.height = H
      const octx = off.getContext('2d')
      octx.drawImage(img, 0, 0, W, H)

      // Mask canvas — alpha grows where strokes are painted
      const mask = document.createElement('canvas')
      mask.width = W
      mask.height = H
      const mctx = mask.getContext('2d')
      mctx.fillStyle = 'rgba(0,0,0,0)'
      mctx.fillRect(0, 0, W, H)

      // Seeded RNG for stable per-image stroke patterns
      const rng = mulberry32(
        Math.floor(src.charCodeAt(src.length - 6) * 9301 + 49297),
      )

      // Coverage grid — plan strokes until most cells are covered
      const GRID = 14
      const cells = new Uint8Array(GRID * GRID)

      const planStroke = () => {
        const dirs = [
          Math.PI * 0.18,
          Math.PI * 0.82,
          Math.PI * 1.18,
          Math.PI * 1.82,
        ]
        const baseAngle =
          dirs[Math.floor(rng() * dirs.length)] + (rng() - 0.5) * 0.4

        // Stroke centres are weighted toward uncovered cells in the top/bottom
        // thirds — keeping the face area free of dense calligraphy texture.
        const TOP_END = Math.floor(GRID / 3)
        const BOT_START = GRID - TOP_END
        const pickRow = () =>
          rng() < 0.5
            ? Math.floor(rng() * TOP_END)
            : BOT_START + Math.floor(rng() * (GRID - BOT_START))

        let bestX = W * 0.5,
          bestY = H * 0.5,
          bestScore = -1
        for (let t = 0; t < 8; t++) {
          const cx = Math.floor(rng() * GRID)
          const cy = pickRow()
          if (!cells[cy * GRID + cx]) {
            bestX = (cx + 0.5) * (W / GRID)
            bestY = (cy + 0.5) * (H / GRID)
            bestScore = 1
            break
          }
          const score = rng()
          if (score > bestScore) {
            bestScore = score
            bestX = (cx + 0.5) * (W / GRID)
            bestY = (cy + 0.5) * (H / GRID)
          }
        }

        // Length exceeds the canvas diagonal so endpoints always fall outside
        const length = Math.hypot(W, H) * 1.4 + rng() * 200
        const width = 32 + rng() * 70
        return { x: bestX, y: bestY, angle: baseAngle, length, width }
      }

      const strokes = []
      const TOTAL = 70
      for (let i = 0; i < TOTAL; i++) {
        const s = planStroke()
        strokes.push(s)
        const dx = Math.cos(s.angle),
          dy = Math.sin(s.angle)
        for (let t = -s.length / 2; t <= s.length / 2; t += 16) {
          const px = s.x + dx * t,
            py = s.y + dy * t
          const gx = Math.floor((px / W) * GRID)
          const gy = Math.floor((py / H) * GRID)
          if (gx >= 0 && gx < GRID && gy >= 0 && gy < GRID)
            cells[gy * GRID + gx] = 1
        }
      }

      // Final stroke: wide vertical swipe through the centre to reveal the face
      strokes.push({
        x: W * 0.5,
        y: H * 0.5,
        angle: Math.PI * 0.5 + (rng() - 0.5) * 0.08,
        length: H * 1.6,
        width: W * 0.55,
      })

      const totalDuration = 2400 / Math.max(0.1, speed)
      const start = performance.now()

      const drawStroke = (s, progress) => {
        const dx = Math.cos(s.angle),
          dy = Math.sin(s.angle)
        const x0 = s.x - (dx * s.length) / 2
        const y0 = s.y - (dy * s.length) / 2
        const x1 = x0 + dx * s.length * progress
        const y1 = y0 + dy * s.length * progress

        mctx.save()
        mctx.lineCap = 'round'
        mctx.lineJoin = 'round'
        for (let pass = 0; pass < 3; pass++) {
          mctx.globalAlpha = 0.55 - pass * 0.12
          mctx.strokeStyle = 'rgba(0,0,0,1)'
          mctx.lineWidth = s.width * (1 + pass * 0.18)
          mctx.beginPath()
          mctx.moveTo(x0, y0)
          mctx.lineTo(x1, y1)
          mctx.stroke()
        }
        mctx.restore()
      }

      const tick = () => {
        if (cancelled) return
        const now = performance.now()
        const t = Math.min(1, (now - start) / totalDuration)
        const target = Math.floor(t * strokes.length)

        for (let k = 0; k <= target && k < strokes.length; k++) {
          if (k < target) continue
          const localStart = (k / strokes.length) * totalDuration
          const localT = Math.min(
            1,
            (now - start - localStart) /
              ((totalDuration / strokes.length) * 1.6),
          )
          if (localT > 0) drawStroke(strokes[k], localT)
        }

        ctx.clearRect(0, 0, W, H)
        ctx.drawImage(off, 0, 0)
        ctx.globalCompositeOperation = 'destination-in'
        ctx.drawImage(mask, 0, 0)
        ctx.globalCompositeOperation = 'source-over'

        if (t < 1) raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
    }
    img.src = src

    return () => {
      cancelled = true
      if (raf) cancelAnimationFrame(raf)
    }
  }, [revealed, src, speed])

  return (
    <div ref={wrapRef} className="sketch-portrait">
      <canvas ref={canvasRef} className="sketch-portrait-canvas" aria-label={alt} />
      <svg
        viewBox="0 0 400 520"
        className="sketch-portrait-corners"
        aria-hidden="true"
      >
        <g
          stroke="currentColor"
          fill="none"
          strokeWidth="0.8"
          strokeLinecap="round"
          opacity="0.5"
        >
          <path d="M 12 12 L 44 12 M 12 12 L 12 44" />
          <path d="M 388 12 L 356 12 M 388 12 L 388 44" />
          <path d="M 12 508 L 44 508 M 12 508 L 12 476" />
          <path d="M 388 508 L 356 508 M 388 508 L 388 476" />
        </g>
      </svg>
    </div>
  )
}
