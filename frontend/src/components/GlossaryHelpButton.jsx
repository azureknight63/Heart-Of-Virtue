import { useState } from 'react'

import { useGlossary } from '../context/GlossaryContext'
import { useMobile } from '../hooks/useMobile'
import { accessibility, colors, fonts } from '../styles/theme'

/**
 * The "?" that opens the combat glossary (issue #507).
 *
 * It lives at the right end of the fight-status strip — the one place the word
 * "Beat" already appears on screen, so the answer sits beside the question —
 * and again in the move panel's header.
 *
 * On touch it grows to the platform minimum target (44px, from
 * `accessibility.touchTarget`); on a pointer device it is an 18px circle sized
 * to the 10px uppercase strip it sits in.
 */
export default function GlossaryHelpButton({ label = 'Open combat glossary', entryId = null, style }) {
  const { openGlossary } = useGlossary()
  const isMobile = useMobile()
  const [hovered, setHovered] = useState(false)

  const size = isMobile ? accessibility.touchTarget : '18px'

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={() => openGlossary(entryId)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flex: '0 0 auto',
        width: size,
        height: size,
        borderRadius: isMobile ? '6px' : '50%',
        border: `1px solid ${hovered ? colors.accent : colors.alpha.info[60]}`,
        backgroundColor: hovered ? colors.alpha.info[20] : colors.alpha.info[10],
        boxShadow: hovered ? `0 0 8px ${colors.alpha.info[60]}` : 'none',
        color: hovered ? colors.text.bright : colors.accent,
        fontFamily: fonts.main,
        fontSize: isMobile ? '16px' : '11px',
        fontWeight: 'bold',
        lineHeight: 1,
        cursor: 'pointer',
        padding: 0,
        ...style,
      }}
    >
      ?
    </button>
  )
}
