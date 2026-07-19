import { useState } from 'react'
import { colors, fonts, spacing, shadows, accessibility } from '../styles/theme'
import { CHANGELOG } from '../data/changelog'

export default function ChangelogPanel({ defaultOpen = false, style = {} }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const latest = CHANGELOG[0]

  return (
    <div style={{ position: 'relative', display: 'inline-block', ...style }}>
      <button
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        aria-expanded={isOpen}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.xs,
          minHeight: accessibility.touchTarget,
          background: colors.bg.panelLight,
          border: `1px solid ${colors.border.light}`,
          borderRadius: '0.25rem',
          color: colors.text.dim,
          cursor: 'pointer',
          fontFamily: fonts.main,
          fontSize: '11px',
          padding: `4px ${spacing.sm}`,
          whiteSpace: 'nowrap',
          transition: 'color 0.2s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = colors.text.muted)}
        onMouseLeave={(e) => (e.currentTarget.style.color = colors.text.dim)}
      >
        <span>Changelog{latest ? ` (v${latest.version})` : ''}</span>
        <span
          style={{
            display: 'inline-block',
            fontSize: '10px',
            transition: 'transform 0.2s',
            transform: isOpen ? 'rotate(180deg)' : 'none',
          }}
        >
          ▼
        </span>
      </button>

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            width: '22rem',
            maxWidth: '90vw',
            maxHeight: '80vh',
            overflowY: 'auto',
            scrollbarWidth: 'thin',
            scrollbarColor: `${colors.secondary} rgba(0, 0, 0, 0.3)`,
            textAlign: 'left',
            padding: spacing.md,
            backgroundColor: colors.bg.main,
            border: `1px solid ${colors.border.success}`,
            borderRadius: '0.25rem',
            boxShadow: shadows.main,
            zIndex: 20,
          }}
        >
          {CHANGELOG.map((entry) => (
            <div key={entry.version} style={{ marginBottom: spacing.md }}>
              <div
                style={{
                  color: colors.secondary,
                  fontFamily: fonts.main,
                  fontSize: '11px',
                  fontWeight: 'bold',
                  marginBottom: spacing.xs,
                }}
              >
                v{entry.version} — {entry.date}
              </div>
              <ul style={{ margin: 0, paddingLeft: spacing.lg }}>
                {entry.highlights.map((highlight, i) => (
                  <li
                    key={i}
                    style={{
                      color: colors.text.dim,
                      fontFamily: fonts.main,
                      fontSize: '11px',
                      lineHeight: '1.5',
                    }}
                  >
                    {highlight}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
