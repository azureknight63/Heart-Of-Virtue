import React, { useState } from 'react'
import { colors, fonts } from '../styles/theme'
import { categoryColor, categoryIcon } from '../utils/categories'
import { displayNameOf } from '../utils/combatMoveStatus'

/**
 * What one cooling move is, in words. Issue #565 polish batch.
 *
 * The collapsed HUD read `COOLDOWN | 1 | ⚔ | 5` and nothing else — which move
 * was cooling could only be worked out by opening a move panel and hovering
 * the disabled card. Shared by the card's `aria-label` and its `title` so the
 * screen-reader name and the sighted hover cannot drift apart.
 *
 * Singular at one beat: "Keep Away: 1 beats" is the sort of thing that reads
 * as a bug in a tooltip.
 */
function cooldownLabel(move) {
  const beats = move.cooldown_remaining
  return `${displayNameOf(move)}: ${beats} ${beats === 1 ? 'beat' : 'beats'}`
}

function CooldownTray({ moves }) {
  const [expanded, setExpanded] = useState(false)

  if (!moves || moves.length === 0) return null

  return (
    <div
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      // "COOLDOWN" beside a bare number is not self-describing — and the
      // number is the move COUNT, which reads as a beat count next to that
      // word. Naming the region says which of the two it is.
      role="group"
      aria-label="Moves on cooldown"
      style={{
        flexShrink: 0,
        borderTop: `1px solid rgba(0,255,136,0.15)`,
        paddingTop: '8px',
      }}
    >
      {/* Section header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '6px',
      }}>
        <span style={{
          fontSize: '0.62rem',
          color: colors.text.muted,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          fontFamily: fonts.main,
        }}>
          Cooldown
        </span>
        <span style={{
          fontSize: '0.62rem',
          color: `${colors.primary}99`,
          fontFamily: fonts.main,
        }}>
          {moves.length}
        </span>
      </div>

      {expanded ? (
        /* Expanded column layout */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {moves.map(move => (
            <ExpandedCard key={move.id} move={move} />
          ))}
        </div>
      ) : (
        /* Collapsed row layout */
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {moves.map(move => (
            <CollapsedCard key={move.id} move={move} />
          ))}
        </div>
      )}
    </div>
  )
}

function CollapsedCard({ move }) {
  const color = categoryColor(move.category)
  const icon = categoryIcon(move.category)
  const label = cooldownLabel(move)

  return (
    <div
      // `role="img"` rather than a bare div with an aria-label: the generic
      // role prohibits naming, so the label would simply be dropped. It also
      // collapses the glyph-and-digit pair into the single thing the card
      // means, instead of announcing "⚔" and "5" as two unrelated scraps.
      //
      // `title` alongside it because the tray only expands to show names on
      // `mouseEnter` — a touch screen has no hover and never reaches them.
      role="img"
      aria-label={label}
      title={label}
      style={{
        width: '44px',
        height: '42px',
        borderRadius: '5px',
        background: 'rgba(0,0,0,0.6)',
        border: `1px solid ${color}99`,
        boxShadow: `0 0 6px ${color}44`,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '2px',
        cursor: 'default',
        flexShrink: 0,
      }}
    >
      <span style={{ fontSize: '0.95rem', lineHeight: 1, color }}>{icon}</span>
      <span style={{
        fontSize: '0.72rem',
        fontWeight: 'bold',
        lineHeight: 1,
        color: `${color}CC`,
        fontFamily: fonts.main,
      }}>
        {move.cooldown_remaining}
      </span>
    </div>
  )
}

function ExpandedCard({ move }) {
  const color = categoryColor(move.category)
  const icon = categoryIcon(move.category)
  const fillPct = move.cooldown_max > 0
    ? Math.round((1 - move.cooldown_remaining / move.cooldown_max) * 100)
    : 0

  return (
    <div style={{
      borderRadius: '5px',
      background: 'rgba(0,0,0,0.7)',
      border: `1px solid ${color}8C`,
      boxShadow: `0 0 8px ${color}33`,
      padding: '7px 9px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
          <span style={{ fontSize: '1rem', lineHeight: 1, color }}>{icon}</span>
          <span style={{
            fontSize: '0.75rem',
            fontWeight: 'bold',
            letterSpacing: '0.04em',
            color: `${color}DD`,
            fontFamily: fonts.main,
          }}>
            {displayNameOf(move)}
          </span>
        </div>
        <div style={{ textAlign: 'right', minWidth: '28px' }}>
          <div style={{
            fontSize: '1.05rem',
            fontWeight: 'bold',
            lineHeight: 1,
            color,
            fontFamily: fonts.main,
          }}>
            {move.cooldown_remaining}
          </div>
          {/* issue #563 item 6: `muted`, not `dim`. This is prose — a unit
              caption — and `dim` is 3.45:1 on the app ground, under WCAG AA.
              `dim` is reserved for inactive controls and decorative marks,
              which SC 1.4.3 exempts; see its note in theme.js. */}
          <div style={{
            fontSize: '0.52rem',
            color: colors.text.muted,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            marginTop: '1px',
          }}>
            beats
          </div>
        </div>
      </div>
      {/* Progress bar — fills as cooldown expires */}
      <div style={{
        marginTop: '6px',
        height: '3px',
        borderRadius: '2px',
        background: 'rgba(255,255,255,0.07)',
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${fillPct}%`,
          height: '100%',
          borderRadius: '2px',
          background: color,
          opacity: 0.75,
          transition: 'width 0.3s ease',
        }} />
      </div>
    </div>
  )
}

export default CooldownTray
