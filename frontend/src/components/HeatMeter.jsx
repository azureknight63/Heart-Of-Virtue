import React, { useEffect, useState } from 'react'
import { colors, fonts } from '../styles/theme'
import {
  METER_MAX,
  METER_MIN,
  HEAT_DRIFT_NOTE,
  HEAT_GAINS,
  HEAT_LOSSES,
  NEUTRAL_MARK_RATIO,
  formatHeatDelta,
  formatMultiplier,
  isRenderableHeat,
  heatBand,
  heatDelta,
  heatFillRatio,
} from '../utils/heat'

/** How long the rise/fall chip stays up after the beat that moved heat. */
export const DELTA_HOLD_MS = 1800

const MONO = fonts.main

/**
 * HeatMeter — Jean's heat multiplier, made legible.
 *
 * Heat has always been a full damage multiplier (src/moves/_base.py
 * `standard_execute_attack`) and has never been shown to the player. This
 * renders three things the player needs to steer it:
 *
 *   1. the live multiplier and its named band,
 *   2. where that sits inside the band heat actually occupies in play
 *      (see utils/heat.js on why the bar is not scaled to the [0.5, 10]
 *      engine clamp),
 *   3. a transient ▲/▼ chip on the beat heat moves, plus an expandable
 *      table of what raises and lowers it.
 *
 * The chip only reports the DIRECTION and SIZE of the change, not its cause:
 * the engine calls `change_heat` from ~8 sites in src/moves/_base.py and none
 * of them records a reason on the player, so no reason string exists on the
 * wire to render. The rules table below carries the "why".
 */
function HeatMeter({ heat, beat, combatId }) {
  // Per-beat delta is derived on the client because the server sends no
  // previous-heat or delta field. Tracked with React's adjust-state-during-
  // render idiom, the same pattern LeftPanel uses for its combat_id reset —
  // an effect would render one frame of stale delta first.
  const [tracked, setTracked] = useState({ combatId, beat, heat })
  const [delta, setDelta] = useState(0)

  if (tracked.combatId !== combatId) {
    // New fight: no delta carries over from the last one.
    setTracked({ combatId, beat, heat })
    setDelta(0)
  } else if (tracked.beat !== beat) {
    setDelta(heatDelta(heat, tracked.heat))
    setTracked({ combatId, beat, heat })
  }

  useEffect(() => {
    if (delta === 0) return undefined
    const timer = setTimeout(() => setDelta(0), DELTA_HOLD_MS)
    return () => clearTimeout(timer)
    // `beat` is a dep so two consecutive beats producing the SAME delta value
    // restart the hold instead of expiring on the first beat's timer.
  }, [delta, beat])

  if (!isRenderableHeat(heat)) return null

  const band = heatBand(heat)
  const fill = heatFillRatio(heat)
  const deltaText = formatHeatDelta(delta)
  const rising = delta > 0

  return (
    <div
      style={{
        flexShrink: 0,
        borderTop: `1px solid rgba(0,255,136,0.15)`,
        paddingTop: '8px',
      }}
      data-testid="heat-meter"
    >
      <style>
        {`@keyframes heatChip {
            from { opacity: 0; transform: translateY(2px); }
            to   { opacity: 1; transform: translateY(0); }
          }`}
      </style>

      {/* Header: section label + band name on the left, multiplier + delta right */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '6px',
        gap: '8px',
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', minWidth: 0 }}>
          <span
            data-testid="heat-caption"
            style={{
              fontSize: '0.62rem',
              color: colors.text.muted,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              fontFamily: MONO,
            }}
          >
            Heat
          </span>
          <span
            data-testid="heat-band"
            style={{
              fontSize: '0.62rem',
              fontWeight: 'bold',
              letterSpacing: '0.1em',
              color: band.color,
              fontFamily: MONO,
              whiteSpace: 'nowrap',
            }}
          >
            {band.label}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
          {deltaText && (
            <span
              data-testid="heat-delta"
              style={{
                fontSize: '0.62rem',
                fontWeight: 'bold',
                fontFamily: MONO,
                color: rising ? colors.primary : colors.danger,
                animation: 'heatChip 180ms ease-out',
              }}
            >
              {rising ? '▲' : '▼'}{deltaText}
            </span>
          )}
          <span
            data-testid="heat-value"
            style={{
              fontSize: '0.78rem',
              fontWeight: 'bold',
              lineHeight: 1,
              color: band.color,
              fontFamily: MONO,
            }}
          >
            {formatMultiplier(heat)}
          </span>
        </div>
      </div>

      {/* Bar. Log-scaled across the band heat actually occupies in play. */}
      <div
        role="meter"
        aria-label="Combat heat"
        // Clamped to the meter's own domain: heat runs to the engine's ceiling of
      // 10 while the bar is scaled to 3.5, and role="meter" requires valuenow
      // to sit within [valuemin, valuemax]. aria-valuetext still carries the
      // true multiplier, so nothing is hidden from assistive tech.
      aria-valuenow={Math.min(Math.max(heat, METER_MIN), METER_MAX)}
        aria-valuemin={METER_MIN}
        aria-valuemax={METER_MAX}
        aria-valuetext={`${formatMultiplier(heat)} ${band.label}`}
        style={{
          position: 'relative',
          height: '6px',
          borderRadius: '3px',
          background: 'rgba(255,255,255,0.07)',
          overflow: 'hidden',
        }}
      >
        <div
          data-testid="heat-fill"
          style={{
            width: `${fill * 100}%`,
            height: '100%',
            borderRadius: '3px',
            background: band.color,
            opacity: 0.75,
            transition: 'width 0.3s ease, background 0.3s ease',
          }}
        />
        {/* Neutral reference tick: where decay is always pulling him back to. */}
        <div
          data-testid="heat-neutral-tick"
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: `${NEUTRAL_MARK_RATIO * 100}%`,
            width: '1px',
            background: colors.text.dim,
          }}
        />
      </div>

      <HeatRules band={band} />
    </div>
  )
}

/**
 * The discoverable half: a collapsed one-line hint that expands into the real
 * multipliers. Collapsed by default so the meter costs one line of the panel
 * during a fight; a button (not a hover) so it works on touch.
 */
function HeatRules({ band }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        style={{
          marginTop: '5px',
          padding: 0,
          border: 'none',
          background: 'none',
          color: colors.text.dim,
          fontSize: '0.55rem',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          fontFamily: MONO,
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        {expanded ? '▾ Hide' : '▸ What moves it'}
      </button>

      {expanded && (
        <div
          data-testid="heat-rules"
          style={{
            marginTop: '5px',
            padding: '7px 9px',
            borderRadius: '5px',
            background: 'rgba(0,0,0,0.7)',
            border: `1px solid ${colors.border.light}`,
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}
        >
          <div
            data-testid="heat-band-note"
            style={{
              fontSize: '0.6rem',
              color: band.color,
              fontFamily: MONO,
              lineHeight: 1.4,
            }}
          >
            {band.note}
          </div>
          <RuleGroup title="Gains" color={colors.primary} rules={HEAT_GAINS} />
          <RuleGroup title="Losses" color={colors.danger} rules={HEAT_LOSSES} />
          <div style={{
            fontSize: '0.55rem',
            color: colors.text.dim,
            fontFamily: MONO,
            lineHeight: 1.4,
          }}>
            {HEAT_DRIFT_NOTE}
          </div>
        </div>
      )}
    </>
  )
}

function RuleGroup({ title, color, rules }) {
  return (
    <div>
      <div style={{
        fontSize: '0.55rem',
        color,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        fontFamily: MONO,
        marginBottom: '3px',
      }}>
        {title}
      </div>
      {rules.map(rule => (
        <div
          key={rule.label}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: '10px',
            fontSize: '0.6rem',
            fontFamily: MONO,
            color: colors.text.muted,
            lineHeight: 1.5,
          }}
        >
          <span>{rule.label}</span>
          <span style={{ color, whiteSpace: 'nowrap' }}>{rule.effect}</span>
        </div>
      ))}
    </div>
  )
}

export default HeatMeter
