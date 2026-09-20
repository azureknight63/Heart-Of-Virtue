import { useState } from 'react'

import { useGlossary } from '../context/GlossaryContext'
import { useLargeTouchTargets } from '../hooks/useLargeTouchTargets'
import { accessibility, colors, fonts } from '../styles/theme'

/**
 * The "?" that opens the combat glossary (issue #507).
 *
 * Sized to sit inline in a 10px monospace status strip without changing its
 * line box, so it can be dropped beside a label rather than needing a row of
 * its own: an 18px circle under a mouse, growing on touch to the platform
 * minimum target (44px, from `accessibility.touchTarget`). "On touch" is the
 * POINTER, not the viewport width — a landscape tablet is a thumb on an 18px
 * circle otherwise (issue #639).
 *
 * `style` is a layout escape hatch for the container — margin and alignment.
 * It is spread *before* the button's own rules so it cannot silently shrink the
 * touch target or undo the circle.
 */
export default function GlossaryHelpButton({ label = 'Open combat glossary', entryId = null, style }) {
  const { openGlossary } = useGlossary()
  const needsLargeTargets = useLargeTouchTargets()
  // Also set on focus/blur: this is "the button is calling attention to
  // itself", by pointer or by keyboard, not a pointer-only hover state.
  const [highlighted, setHighlighted] = useState(false)

  const size = needsLargeTargets ? accessibility.touchTarget : '18px'

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={() => openGlossary(entryId)}
      onMouseEnter={() => setHighlighted(true)}
      onMouseLeave={() => setHighlighted(false)}
      onFocus={() => setHighlighted(true)}
      onBlur={() => setHighlighted(false)}
      style={{
        ...style,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flex: '0 0 auto',
        width: size,
        height: size,
        borderRadius: needsLargeTargets ? '6px' : '50%',
        border: `1px solid ${highlighted ? colors.accent : colors.alpha.info[60]}`,
        backgroundColor: highlighted ? colors.alpha.info[20] : colors.alpha.info[10],
        boxShadow: highlighted ? `0 0 8px ${colors.alpha.info[60]}` : 'none',
        color: highlighted ? colors.text.bright : colors.accent,
        fontFamily: fonts.main,
        fontSize: needsLargeTargets ? '16px' : '11px',
        fontWeight: 'bold',
        lineHeight: 1,
        cursor: 'pointer',
        padding: 0,
      }}
    >
      ?
    </button>
  )
}
