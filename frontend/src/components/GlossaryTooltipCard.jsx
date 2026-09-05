import { colors, fonts, shadows, spacing } from '../styles/theme'

/**
 * The one-sentence answer to "what is this word?", shown against a combat term.
 *
 * Two presentations, one component (issue #507):
 *  - floating (desktop) — anchored to the term, arrow pointing back at it;
 *  - docked (touch) — a full-width card in normal flow beneath the line the
 *    term sits on, so a thumb resting on the word it just tapped cannot cover
 *    the answer to its own question.
 *
 * The copy is `entry.short` + `entry.tell`, never a second wording: the panel
 * renders the long form of the same entry, so the two densities cannot drift.
 */
const CARD_WIDTH = 266

export default function GlossaryTooltipCard({
  entry,
  id,
  docked = false,
  placement = 'bottom',
  onOpenGlossary,
}) {
  const above = placement === 'top'

  const position = docked
    ? { position: 'relative', width: '100%', marginTop: spacing.sm }
    : {
        position: 'absolute',
        left: 0,
        zIndex: 40,
        width: `${CARD_WIDTH}px`,
        maxWidth: '90vw',
        ...(above ? { bottom: 'calc(100% + 9px)' } : { top: 'calc(100% + 9px)' }),
      }

  return (
    <div
      id={id}
      role="tooltip"
      style={{
        ...position,
        backgroundColor: colors.bg.main,
        border: `1.5px solid ${colors.accent}`,
        borderRadius: '5px',
        boxShadow: `0 0 12px ${colors.alpha.info[30]}, ${shadows.main}`,
        padding: '9px 11px',
        textAlign: 'left',
        fontFamily: fonts.main,
        fontStyle: 'normal',
        whiteSpace: 'normal',
      }}
    >
      <div style={{
        fontSize: '0.65rem',
        color: colors.accent,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        fontWeight: 'bold',
        marginBottom: '5px',
      }}>
        {entry.term}
      </div>

      <div style={{ fontSize: '0.72rem', color: colors.text.main, lineHeight: 1.5 }}>
        {entry.short}
      </div>

      <div style={{
        fontSize: '0.68rem',
        color: colors.text.highlight,
        marginTop: '7px',
        lineHeight: 1.5,
        borderTop: `1px solid ${colors.bg.muted}`,
        paddingTop: '6px',
      }}>
        {entry.tell}
      </div>

      <button
        type="button"
        onClick={onOpenGlossary}
        style={{
          background: 'none',
          border: 'none',
          padding: `${spacing.xs} 0 0`,
          marginTop: '3px',
          fontFamily: fonts.main,
          fontSize: '0.65rem',
          letterSpacing: '0.05em',
          color: colors.primary,
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        Open glossary →
      </button>

      {/* Decorative pointer back at the term. Docked cards sit directly under
          the line they explain and need no pointer. */}
      {!docked && (
        <span
          aria-hidden="true"
          style={{
            position: 'absolute',
            left: '26px',
            width: 0,
            height: 0,
            borderLeft: '6px solid transparent',
            borderRight: '6px solid transparent',
            ...(above
              ? { bottom: '-7px', borderTop: `7px solid ${colors.accent}` }
              : { top: '-7px', borderBottom: `7px solid ${colors.accent}` }),
          }}
        />
      )}
    </div>
  )
}
