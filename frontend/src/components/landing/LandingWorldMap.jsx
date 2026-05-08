// Hand-drawn cartography of Aurelion.
// SVG paths animate stroke-dashoffset to 0 on scroll-entry, giving the effect
// of ink being drawn onto the map in real time.

import { useRef, useState, useEffect } from 'react'

export default function LandingWorldMap({ speed = 1 }) {
  const ref = useRef(null)
  const [drawn, setDrawn] = useState(false)

  useEffect(() => {
    if (!ref.current) return
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            setDrawn(true)
            io.disconnect()
          }
        })
      },
      { threshold: 0.2 },
    )
    io.observe(ref.current)
    return () => io.disconnect()
  }, [])

  useEffect(() => {
    if (!ref.current || !drawn) return
    const paths = ref.current.querySelectorAll('[data-ink]')
    const base = 2400 / Math.max(0.1, speed)
    paths.forEach((p, i) => {
      try {
        const len = p.getTotalLength ? p.getTotalLength() : 400
        p.style.strokeDasharray = `${len}`
        p.style.strokeDashoffset = `${len}`
        p.style.transition = 'none'
        p.getBoundingClientRect()
        const delay = (i * 18) / Math.max(0.1, speed)
        p.style.transition = `stroke-dashoffset ${base}ms cubic-bezier(.6,.1,.2,1) ${delay}ms, opacity 800ms ease ${delay}ms`
        p.style.opacity = p.getAttribute('data-opacity') || '1'
        requestAnimationFrame(() => {
          p.style.strokeDashoffset = '0'
        })
      } catch (_) {}
    })
    const labels = ref.current.querySelectorAll('[data-label]')
    labels.forEach((el, i) => {
      el.style.opacity = '0'
      el.style.transition = `opacity 900ms ease ${1400 + i * 140}ms`
      requestAnimationFrame(() => {
        el.style.opacity = '1'
      })
    })
  }, [drawn, speed])

  const ink = (extra = {}) => ({
    stroke: 'currentColor',
    fill: 'none',
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    style: { opacity: 0 },
    'data-ink': true,
    ...extra,
  })

  return (
    <div ref={ref} className="world-map-wrap">
      <svg
        viewBox="0 0 1200 720"
        xmlns="http://www.w3.org/2000/svg"
        className="world-map-svg"
      >
        <defs>
          <pattern
            id="mapParchment"
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 0 3 L 6 3"
              stroke="currentColor"
              strokeWidth="0.15"
              opacity="0.18"
            />
          </pattern>
        </defs>

        {/* decorative border */}
        <path {...ink({ strokeWidth: 0.8 })} d="M 24 24 L 1176 24 L 1176 696 L 24 696 Z" />
        <path {...ink({ strokeWidth: 0.4 })} d="M 32 32 L 1168 32 L 1168 688 L 32 688 Z" opacity="0.6" data-opacity="0.6" />

        {/* corner flourishes */}
        <path {...ink({ strokeWidth: 0.7 })} d="M 40 40 C 60 42, 72 52, 72 72 M 40 40 C 42 60, 52 72, 72 72" />
        <path {...ink({ strokeWidth: 0.7 })} d="M 1160 40 C 1140 42, 1128 52, 1128 72 M 1160 40 C 1158 60, 1148 72, 1128 72" />
        <path {...ink({ strokeWidth: 0.7 })} d="M 40 680 C 60 678, 72 668, 72 648 M 40 680 C 42 660, 52 648, 72 648" />
        <path {...ink({ strokeWidth: 0.7 })} d="M 1160 680 C 1140 678, 1128 668, 1128 648 M 1160 680 C 1158 660, 1148 648, 1128 648" />

        {/* compass rose */}
        <g transform="translate(1050, 120)">
          <path {...ink({ strokeWidth: 0.7 })} d="M 0 -50 L 0 50 M -50 0 L 50 0" />
          <path {...ink({ strokeWidth: 0.9 })} d="M 0 -40 L 10 0 L 0 40 L -10 0 Z" />
          <path {...ink({ strokeWidth: 0.9 })} d="M -40 0 L 0 10 L 40 0 L 0 -10 Z" />
          <path {...ink({ strokeWidth: 0.5 })} d="M 0 -55 L 0 -45 M 0 45 L 0 55 M -55 0 L -45 0 M 45 0 L 55 0" />
          <text data-label x="0" y="-58" textAnchor="middle" className="map-label compass-letter">N</text>
          <text data-label x="0" y="66" textAnchor="middle" className="map-label compass-letter">S</text>
          <text data-label x="-58" y="4" textAnchor="middle" className="map-label compass-letter">W</text>
          <text data-label x="58" y="4" textAnchor="middle" className="map-label compass-letter">E</text>
          <circle {...ink({ strokeWidth: 0.6 })} cx="0" cy="0" r="56" />
        </g>

        {/* COASTLINES */}
        <path {...ink({ strokeWidth: 1.2 })} d="M 80 200 C 120 230, 100 280, 130 320 C 160 360, 140 420, 170 460 C 190 490, 170 540, 200 580 C 230 610, 220 650, 260 660" />
        <path {...ink({ strokeWidth: 0.6 })} d="M 95 220 L 90 230 M 115 250 L 108 256 M 130 290 L 124 296 M 150 340 L 144 348 M 170 400 L 162 406 M 180 450 L 172 456 M 195 500 L 188 508 M 210 560 L 204 568 M 230 610 L 224 618" opacity="0.7" data-opacity="0.7" />
        <path {...ink({ strokeWidth: 1.2 })} d="M 1130 180 C 1100 230, 1110 300, 1080 360 C 1060 400, 1080 440, 1060 490 C 1040 530, 1060 580, 1030 630 C 1010 650, 1000 670, 980 680" />
        <path {...ink({ strokeWidth: 0.6 })} d="M 1110 220 L 1118 226 M 1096 270 L 1104 276 M 1084 330 L 1092 336 M 1070 390 L 1078 396 M 1056 450 L 1064 456 M 1044 510 L 1052 516 M 1030 570 L 1038 576 M 1020 620 L 1028 626" opacity="0.7" data-opacity="0.7" />

        {/* Wailing Badlands */}
        <path {...ink({ strokeWidth: 1 })} d="M 180 260 C 220 250, 280 260, 320 280 C 340 300, 330 340, 310 370 C 290 400, 260 410, 230 400 C 200 390, 180 360, 180 320 Z" />
        <path {...ink({ strokeWidth: 0.7 })} d="M 220 300 L 228 288 L 236 300 M 250 310 L 258 296 L 266 310 M 280 300 L 288 286 L 296 300 M 230 340 L 238 326 L 246 340 M 260 350 L 268 336 L 276 350 M 290 340 L 298 326 L 306 340" opacity="0.85" data-opacity="0.85" />

        {/* Echoing Caves */}
        <path {...ink({ strokeWidth: 1 })} d="M 330 340 C 360 340, 380 360, 384 384 C 378 400, 356 408, 338 400 C 326 388, 326 360, 330 340 Z" />
        <path {...ink({ strokeWidth: 0.6 })} d="M 344 358 C 348 370, 356 374, 362 372 M 344 380 C 348 388, 356 390, 364 384" opacity="0.8" data-opacity="0.8" />

        {/* River */}
        <path {...ink({ strokeWidth: 1.1 })} d="M 480 150 C 470 200, 450 240, 430 280 C 410 320, 400 360, 380 400 C 360 440, 320 470, 270 500 C 230 520, 200 560, 180 600" />
        <path {...ink({ strokeWidth: 0.7 })} d="M 460 220 C 440 220, 420 214, 400 210 M 430 280 C 410 280, 390 274, 370 270 M 400 360 C 380 360, 360 356, 340 354 M 360 420 C 340 420, 320 414, 300 408" opacity="0.85" data-opacity="0.85" />
        <path {...ink({ strokeWidth: 0.4 })} d="M 470 180 L 474 186 M 455 230 L 460 236 M 435 280 L 440 286 M 420 320 L 424 326 M 395 380 L 400 386 M 370 420 L 374 426 M 340 460 L 344 466 M 300 490 L 304 496 M 240 520 L 244 526 M 210 560 L 214 566" opacity="0.6" data-opacity="0.6" />

        {/* Central mountains */}
        <path {...ink({ strokeWidth: 1 })} d="M 460 170 L 495 120 L 530 170" />
        <path {...ink({ strokeWidth: 1 })} d="M 490 200 L 540 138 L 590 205" />
        <path {...ink({ strokeWidth: 1 })} d="M 540 190 L 590 110 L 650 200" />
        <path {...ink({ strokeWidth: 1 })} d="M 600 210 L 660 130 L 720 215" />
        <path {...ink({ strokeWidth: 1 })} d="M 660 180 L 720 108 L 790 190" />
        <path {...ink({ strokeWidth: 1 })} d="M 720 205 L 780 138 L 840 210" />
        {/* Dark Grotto */}
        <path {...ink({ strokeWidth: 1 })} d="M 360 230 L 410 150 L 460 232" />
        <path {...ink({ strokeWidth: 0.5 })} d="M 396 200 L 410 172 L 426 196" opacity="0.7" data-opacity="0.7" />
        <path {...ink({ strokeWidth: 0.8 })} d="M 404 158 L 410 148 L 416 158" />
        {/* mountain shading */}
        <path {...ink({ strokeWidth: 0.5 })} d="M 510 160 L 495 140 L 520 148 M 560 170 L 540 150 L 565 160 M 610 170 L 590 140 L 620 158 M 670 186 L 660 164 L 690 178 M 740 166 L 720 138 L 755 158 M 790 186 L 780 164 L 810 180" opacity="0.7" data-opacity="0.7" />
        {/* snowcaps */}
        <path {...ink({ strokeWidth: 0.8 })} d="M 492 126 L 498 118 L 504 126 M 586 118 L 592 108 L 598 120 M 716 118 L 722 108 L 728 120" />

        {/* Resolute Plains — grass tufts */}
        <path {...ink({ strokeWidth: 0.5 })} d="M 820 300 C 822 296, 824 296, 826 300 M 840 320 C 842 316, 844 316, 846 320 M 820 340 C 822 336, 824 336, 826 340 M 860 310 C 862 306, 864 306, 866 310 M 880 330 C 882 326, 884 326, 886 330 M 900 320 C 902 316, 904 316, 906 320 M 860 350 C 862 346, 864 346, 866 350 M 900 360 C 902 356, 904 356, 906 360 M 840 380 C 842 376, 844 376, 846 380 M 880 400 C 882 396, 884 396, 886 400 M 920 390 C 922 386, 924 386, 926 390 M 960 380 C 962 376, 964 376, 966 380 M 840 420 C 842 416, 844 416, 846 420 M 880 440 C 882 436, 884 436, 886 440 M 920 430 C 922 426, 924 426, 926 430 M 960 420 C 962 416, 964 416, 966 420 M 940 360 C 942 356, 944 356, 946 360" opacity="0.85" data-opacity="0.85" />
        {/* caravan road */}
        <path {...ink({ strokeWidth: 0.6, strokeDasharray: '4 6' })} d="M 650 230 C 720 260, 800 300, 900 360 C 960 400, 1020 440, 1060 500" opacity="0.8" data-opacity="0.8" />

        {/* Forests */}
        <g>
          {[
            [260, 160], [290, 150], [320, 158], [350, 148],
            [270, 180], [300, 172], [340, 178], [380, 170],
            [200, 200], [240, 210], [300, 208],
            [420, 100], [460, 90],
          ].map((xy, i) => (
            <g key={i} transform={`translate(${xy[0]}, ${xy[1]})`}>
              <path {...ink({ strokeWidth: 0.7 })} d="M 0 10 L 6 -6 L 12 10 Z" />
              <path {...ink({ strokeWidth: 0.5 })} d="M 6 10 L 6 14" opacity="0.7" data-opacity="0.7" />
            </g>
          ))}
        </g>

        {/* Sanctuary of Illusions */}
        <g>
          <path {...ink({ strokeWidth: 0.8 })} d="M 320 560 m -26 0 a 26 16 0 1 0 52 0 a 26 16 0 1 0 -52 0" />
          <path {...ink({ strokeWidth: 0.6 })} d="M 320 554 L 324 544 L 328 554 L 338 556 L 330 562 L 332 572 L 322 568 L 312 572 L 314 562 L 306 556 Z" />
        </g>

        {/* Dry Wastes — dunes */}
        <g>
          <path {...ink({ strokeWidth: 0.6 })} d="M 560 470 C 620 460, 700 470, 760 462 M 580 490 C 640 482, 720 492, 790 485 M 540 510 C 620 502, 710 512, 820 505 M 620 530 C 700 524, 790 532, 880 526" opacity="0.85" data-opacity="0.85" />
          <path {...ink({ strokeWidth: 0.6 })} d="M 670 476 L 670 466 M 668 468 L 672 468 M 740 496 L 740 486 M 738 488 L 742 488 M 810 510 L 810 502" opacity="0.8" data-opacity="0.8" />
        </g>

        {/* Grondia City — stone archway at foot of mountains */}
        <g transform="translate(650, 240)">
          <path {...ink({ strokeWidth: 0.9 })} d="M -12 8 L -12 -10 L -6 -10 L -6 8 Z" />
          <path {...ink({ strokeWidth: 0.9 })} d="M 6 8 L 6 -10 L 12 -10 L 12 8 Z" />
          <path {...ink({ strokeWidth: 0.9 })} d="M -14 -10 C -14 -22, 14 -22, 14 -10" />
          <path {...ink({ strokeWidth: 0.6 })} d="M -3 -19 L -3 -14 L 3 -14 L 3 -19" opacity="0.8" data-opacity="0.8" />
          <path {...ink({ strokeWidth: 0.4 })} d="M -10 -6 L -10 6 M -8 -8 L -8 6 M 8 -8 L 8 6 M 10 -6 L 10 6" opacity="0.6" data-opacity="0.6" />
        </g>

        {/* Wayfarers' Stand */}
        <g transform="translate(1020, 290)">
          <path {...ink({ strokeWidth: 0.8 })} d="M -6 6 L 0 -4 L 6 6 Z M -2 6 L -2 12 L 2 12 L 2 6" />
        </g>

        {/* Nomad camp */}
        <g transform="translate(420, 410)">
          <path {...ink({ strokeWidth: 0.8 })} d="M -10 6 L 0 -8 L 10 6 Z" />
          <path {...ink({ strokeWidth: 0.8 })} d="M 12 8 L 22 -4 L 28 8 Z" />
          <path {...ink({ strokeWidth: 0.5 })} d="M 4 8 C 4 2, 8 0, 10 4" opacity="0.8" data-opacity="0.8" />
        </g>

        {/* Jerusalem hint marker */}
        <g transform="translate(1000, 80)" opacity="0.5">
          <path {...ink({ strokeWidth: 0.5 })} d="M -8 0 L 8 0 M 0 -8 L 0 8" data-opacity="0.5" />
          <path {...ink({ strokeWidth: 0.5 })} d="M -12 0 a 12 12 0 1 0 24 0 a 12 12 0 1 0 -24 0" data-opacity="0.5" />
        </g>

        {/* Sea monster flourish */}
        <g transform="translate(120, 600)" opacity="0.7">
          <path {...ink({ strokeWidth: 0.7 })} d="M -20 0 C -14 -6, -6 -6, 0 0 C 6 6, 14 6, 20 0" data-opacity="0.7" />
          <path {...ink({ strokeWidth: 0.6 })} d="M -10 -4 L -8 -8 M 2 -4 L 4 -8" data-opacity="0.7" />
        </g>

        {/* Wave lines */}
        <g opacity="0.5">
          <path {...ink({ strokeWidth: 0.5 })} d="M 40 400 C 48 396, 56 400, 64 396 M 38 440 C 46 436, 54 440, 62 436 M 40 480 C 48 476, 56 480, 64 476" data-opacity="0.55" />
          <path {...ink({ strokeWidth: 0.5 })} d="M 1140 380 C 1148 376, 1156 380, 1164 376 M 1140 420 C 1148 416, 1156 420, 1164 416 M 1140 460 C 1148 456, 1156 460, 1164 456" data-opacity="0.55" />
        </g>

        {/* Labels */}
        <text data-label x="600" y="80"  textAnchor="middle" className="map-title">AURELION</text>
        <text data-label x="600" y="100" textAnchor="middle" className="map-subtitle">— a charting of the realm —</text>
        <text data-label x="248" y="340" textAnchor="middle" className="map-region">The Wailing Badlands</text>
        <text data-label x="358" y="418" textAnchor="middle" className="map-place">Echoing Caves</text>
        <text data-label x="410" y="248" textAnchor="middle" className="map-place">Dark Grotto</text>
        <text data-label x="1040" y="180" textAnchor="middle" className="map-region">The Resolute Plains</text>
        <text data-label x="650" y="276" textAnchor="middle" className="map-place">Grondia City</text>
        <text data-label x="1030" y="316" textAnchor="start"  className="map-place">Wayfarers&apos; Stand</text>
        <text data-label x="445" y="430"  textAnchor="start"  className="map-place">Mara&apos;s Camp</text>
        <text data-label x="700" y="500"  textAnchor="middle" className="map-region">Dry Wastes</text>
        <text data-label x="320" y="540"  textAnchor="middle" className="map-place">Sanctuary of Illusions</text>
        <text data-label x="300" y="140"  textAnchor="middle" className="map-region">Verdant Folk Forests</text>
        <text data-label x="160" y="480"  textAnchor="middle" className="map-region map-sea">Sundering Sea</text>
        <text data-label x="1060" y="480" textAnchor="middle" className="map-region map-sea">Sea of Ash</text>
        <text data-label x="478" y="146"  textAnchor="start"  className="map-route-label">Jean&apos;s road</text>

        {/* Jean's dotted route */}
        <path {...ink({ strokeWidth: 0.5, strokeDasharray: '2 4' })} d="M 615 230 C 560 280, 500 340, 440 400 C 400 440, 350 440, 320 420 C 290 400, 260 380, 250 340" opacity="0.8" data-opacity="0.8" />

        {/* Scale */}
        <g transform="translate(60, 640)">
          <path {...ink({ strokeWidth: 0.6 })} d="M 0 0 L 120 0 M 0 -3 L 0 3 M 30 -2 L 30 2 M 60 -3 L 60 3 M 90 -2 L 90 2 M 120 -3 L 120 3" />
          <text data-label x="60" y="18" textAnchor="middle" className="map-scale">— leagues —</text>
        </g>
      </svg>
    </div>
  )
}
