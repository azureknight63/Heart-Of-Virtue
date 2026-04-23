import React, { useState } from 'react'
import { colors } from '../styles/theme'

const CATEGORY_ICONS = {
  Offensive: '⚔',
  Maneuver: '↯',
  Defensive: '◈',
  Special: '✦',
  Supernatural: '⬡',
  Miscellaneous: '◈',
  Utility: '◈',
}

const CATEGORY_COLORS = {
  Offensive: colors.danger,
  Maneuver: colors.primary,
  Defensive: colors.primary,
  Special: colors.special,
  Supernatural: colors.info,
  Miscellaneous: colors.gold,
  Utility: colors.gold,
}

function getColor(category) {
  return CATEGORY_COLORS[category] || colors.text.muted
}

function getIcon(category) {
  return CATEGORY_ICONS[category] || '◈'
}

function CooldownTray({ moves }) {
  const [expanded, setExpanded] = useState(false)

  if (!moves || moves.length === 0) return null

  return (
    <div
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
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
          fontFamily: "'Courier New', monospace",
        }}>
          Cooldown
        </span>
        <span style={{
          fontSize: '0.62rem',
          color: `${colors.primary}99`,
          fontFamily: "'Courier New', monospace",
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
  const color = getColor(move.category)
  const icon = getIcon(move.category)

  return (
    <div style={{
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
    }}>
      <span style={{ fontSize: '0.95rem', lineHeight: 1, color }}>{icon}</span>
      <span style={{
        fontSize: '0.72rem',
        fontWeight: 'bold',
        lineHeight: 1,
        color: `${color}CC`,
        fontFamily: "'Courier New', monospace",
      }}>
        {move.cooldown_remaining}
      </span>
    </div>
  )
}

function ExpandedCard({ move }) {
  const color = getColor(move.category)
  const icon = getIcon(move.category)
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
            fontFamily: "'Courier New', monospace",
          }}>
            {move.name}
          </span>
        </div>
        <div style={{ textAlign: 'right', minWidth: '28px' }}>
          <div style={{
            fontSize: '1.05rem',
            fontWeight: 'bold',
            lineHeight: 1,
            color,
            fontFamily: "'Courier New', monospace",
          }}>
            {move.cooldown_remaining}
          </div>
          <div style={{
            fontSize: '0.52rem',
            color: colors.text.dim,
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
