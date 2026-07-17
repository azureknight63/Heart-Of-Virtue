import { useState } from 'react'
import { colors, fonts, spacing, accessibility } from '../styles/theme'
import { CHANGELOG } from '../data/changelog'

export default function ChangelogPanel({ defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const latest = CHANGELOG[0]

  return (
    <div style={{ width: '100%', maxWidth: '20rem' }}>
      <button
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        aria-expanded={isOpen}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: spacing.xs,
          width: '100%',
          minHeight: accessibility.touchTarget,
          background: 'none',
          border: 'none',
          color: colors.text.dim,
          cursor: 'pointer',
          fontFamily: fonts.main,
          fontSize: '11px',
          padding: 0,
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
            marginTop: spacing.xs,
            maxHeight: '220px',
            overflowY: 'auto',
            textAlign: 'left',
            padding: spacing.md,
            backgroundColor: colors.bg.panel,
            border: `1px solid ${colors.border.light}`,
            borderRadius: '0.25rem',
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
