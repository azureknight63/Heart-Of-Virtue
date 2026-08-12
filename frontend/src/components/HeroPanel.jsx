import React, { useState } from 'react'
import { colors, spacing, fonts, shadows, accessibility } from '../styles/theme'
import StatusEffectsIconPanel from './StatusEffectsIconPanel'
import GameText from './GameText'

/**
 * VitalBar — one of the two curved bars flanking the hero portrait.
 *
 * The HP and Fatigue bars were ~55-line near-duplicates differing only in the
 * values below. That is a drift risk with a track record here: the divide-by-
 * zero guard on the fill height had to be applied to two separate expressions,
 * and any change to the hover/touch/tooltip behaviour needed both copies edited
 * in lockstep.
 *
 * `side` drives every left/right mirror (position, both border radii, and the
 * tooltip's anchor). `tooltipShadow` is a prop rather than derived from `color`
 * only because the two bars genuinely render different glows today — HP uses a
 * colour-matched shadow, Fatigue uses the orange `shadows.glow` token, which
 * looks like an oversight but is preserved here so this extraction stays purely
 * structural. Unify them in a deliberate visual change, not silently.
 */
function VitalBar({
  side,
  label,
  color,
  trackColor,
  tooltipShadow,
  fillRatio,
  current,
  max,
  active,
  onHoverChange,
  onToggle,
  testId,
}) {
  const isLeft = side === 'left'
  return (
    <div
      onMouseEnter={() => onHoverChange(true)}
      onMouseLeave={() => onHoverChange(false)}
      onClick={onToggle}
      onTouchStart={(e) => {
        e.preventDefault()
        onToggle()
      }}
      style={{
        position: 'absolute',
        [isLeft ? 'left' : 'right']: '-75px',
        top: '50%',
        transform: 'translateY(-50%)',
        width: '15px',
        height: '150px',
        borderRadius: isLeft ? '15px 0 0 15px' : '0 15px 15px 0',
        border: `2px solid ${color}`,
        backgroundColor: trackColor,
        boxShadow: `0 0 10px ${color}88, inset 0 0 8px ${color}44`,
        zIndex: 3,
        display: 'flex',
        flexDirection: 'column-reverse',
        overflow: 'visible',
        cursor: 'pointer',
      }}
      data-testid={testId}
    >
      <div style={{
        width: '100%',
        height: `${fillRatio * 100}%`,
        backgroundColor: color,
        borderRadius: isLeft ? '12px 0 0 12px' : '0 12px 12px 0',
        boxShadow: `0 0 8px ${color}, inset 0 0 4px rgba(255, 255, 255, 0.3)`,
      }} />

      {active && (
        <div style={{
          position: 'absolute',
          [isLeft ? 'left' : 'right']: '50%',
          bottom: '-35px',
          transform: `translateX(${isLeft ? '-50%' : '50%'})`,
          backgroundColor: colors.bg.main,
          border: `1.5px solid ${color}`,
          borderRadius: '3px',
          padding: '4px 6px',
          color,
          fontSize: '8px',
          fontWeight: 'bold',
          fontFamily: fonts.main,
          whiteSpace: 'nowrap',
          boxShadow: tooltipShadow,
          zIndex: 20,
        }}>
          {label}<br />{current.toFixed(0)}/{max}
        </div>
      )}
    </div>
  )
}

function HeroPanel({
  player,
  isMobile,
  inCombat,
  hasSpecialMoves,
  hasDefensiveMoves,
  hasOffensiveMoves,
  hasManeuverMoves,
  hasMiscellaneousMoves,
  onAttributeClick,
  onStatusClick,
  onSkillsClick,
  onSpecialClick,
  onInventoryClick,
  onActionsClick,
  onInteractClick,
  onDefensiveClick,
  onOffensiveClick,
  onManeuverClick,
  onMiscellaneousClick
}) {
  const [hoveredButton, setHoveredButton] = useState(null)
  const [hoveredBar, setHoveredBar] = useState(null)
  const [focusedBar, setFocusedBar] = useState(null)

  // Get player stats or use defaults
  const hp = {
    current: player?.hp ?? 100,
    max: player?.max_hp ?? 100,
  }
  const fatigue = {
    current: player?.fatigue ?? 150,
    max: player?.max_fatigue ?? 150,
  }

  // usePlayer's error fallback ships hp:0/max_hp:0, and `?? 100` lets a real 0
  // through — dividing by it yields NaN, which leaks into height:"NaN%" and
  // animationDuration:"NaNs". Treat a zero/absent max as an empty bar.
  const ratio = (current, max) => (max > 0 ? Math.max(0, Math.min(1, current / max)) : 0)

  // Calculate heart rate based on HP and Combat status
  const hpPercent = ratio(hp.current, hp.max)
  const fatiguePercent = ratio(fatigue.current, fatigue.max)
  const baseBpm = 60
  const combatBonus = inCombat ? 40 : 0
  const stressBonus = (1 - hpPercent) * (inCombat ? 80 : 60)
  const bpm = baseBpm + combatBonus + stressBonus
  const animationDuration = `${60 / bpm}s`

  const explorationButtons = [
    { key: 'attributes', label: 'ATTRIBUTES', top: '0px', left: '20%', transform: 'translateX(-50%)', onClick: onAttributeClick },
    { key: 'status', label: 'PARTY', top: '0px', left: 'calc(50% + 60px)', transform: 'translate(-50%, 0)', onClick: onStatusClick },
    { key: 'inventory', label: 'INVENTORY', top: '50%', left: '-40px', transform: 'translateY(-50%)', onClick: onInventoryClick },
    { key: 'skills', label: 'SKILLS', top: '50%', left: 'calc(50% + 70px)', transform: 'translateY(-50%)', onClick: onSkillsClick },
    { key: 'actions', label: 'COMMANDS', top: 'calc(50% + 80px)', left: '5px', transform: 'translate(0, -50%)', onClick: onActionsClick },
    { key: 'interact', label: 'INTERACT', top: 'calc(50% + 80px)', left: 'calc(50% + 60px)', transform: 'translate(-50%, -50%)', onClick: onInteractClick },
  ]

  const combatButtons = [
    { key: 'offensive', label: 'OFFENSIVE', top: '0px', left: '20%', transform: 'translateX(-50%)', onClick: onOffensiveClick, color: colors.danger, show: hasOffensiveMoves },
    { key: 'maneuver', label: 'MANEUVER', top: '0px', left: 'calc(50% + 60px)', transform: 'translate(-50%, 0)', onClick: onManeuverClick, color: colors.text.highlight, show: hasManeuverMoves },
    { key: 'inventory', label: 'INVENTORY', top: '50%', left: '-40px', transform: 'translateY(-50%)', onClick: onInventoryClick },
    { key: 'special', label: 'SPECIAL', top: '50%', left: 'calc(50% + 70px)', transform: 'translateY(-50%)', onClick: onSpecialClick, color: colors.special, show: hasSpecialMoves },
    { key: 'miscellaneous', label: 'MISC', top: 'calc(50% + 80px)', left: '5px', transform: 'translate(0, -50%)', onClick: onMiscellaneousClick, color: colors.text.muted, show: hasMiscellaneousMoves },
    { key: 'defensive', label: 'DEFENSIVE', top: 'calc(50% + 80px)', left: 'calc(50% + 60px)', transform: 'translate(-50%, -50%)', onClick: onDefensiveClick, color: colors.secondary, show: hasDefensiveMoves },
  ]

  const buttons = inCombat ? combatButtons.filter(btn => btn.show !== false) : explorationButtons

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: spacing.md,
      alignItems: 'center',
      padding: `${spacing.xl} ${spacing.md}`,
      position: 'relative',
    }}>
      {/* Hero Head Container */}
      <div style={{
        position: 'relative',
        width: '200px',
        height: '200px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'visible',
      }}>
        {/* Passive Effects Icons — side column on desktop, hidden here on mobile (shown below) */}
        {!isMobile && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '-135px',
            transform: 'translateY(-50%)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '4px',
            zIndex: 10,
            pointerEvents: 'auto'
          }}>
            {player?.passives?.length > 0 && (
              <GameText variant="muted" size="xs" weight="bold" style={{ fontSize: '7px', marginBottom: '2px' }}>PASSIVES</GameText>
            )}
            <StatusEffectsIconPanel effects={player?.passives} vertical />
          </div>
        )}

        {/* Status Effects Icons — side column on desktop, hidden here on mobile (shown below) */}
        {!isMobile && (
          <div style={{
            position: 'absolute',
            top: '50%',
            right: '-135px',
            transform: 'translateY(-50%)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '4px',
            zIndex: 10,
            pointerEvents: 'auto'
          }}>
            {player?.status_effects?.length > 0 && (
              <GameText variant="muted" size="xs" weight="bold" style={{ fontSize: '7px', marginBottom: '2px' }}>STATUS</GameText>
            )}
            <StatusEffectsIconPanel effects={player?.status_effects} vertical />
          </div>
        )}

        <img
          src={`${import.meta.env.BASE_URL}hero-heart.png`}
          alt="Hero Heart"
          style={{
            width: '140px',
            height: '140px',
            objectFit: 'contain',
            filter: `drop-shadow(0 0 10px ${colors.primary}44)`,
            zIndex: 1,
            animation: `pulse ${animationDuration} infinite ease-in-out`,
          }}
        />
        <style>
          {`
            @keyframes pulse {
              0% { transform: scale(1); filter: drop-shadow(0 0 10px ${colors.primary}44); }
              10% { transform: scale(1.007); filter: drop-shadow(0 0 14px ${colors.primary}66); }
              20% { transform: scale(1); filter: drop-shadow(0 0 10px ${colors.primary}44); }
              30% { transform: scale(1.007); filter: drop-shadow(0 0 14px ${colors.primary}66); }
              50% { transform: scale(1); filter: drop-shadow(0 0 10px ${colors.primary}44); }
              100% { transform: scale(1); filter: drop-shadow(0 0 10px ${colors.primary}44); }
            }
          `}
        </style>

        {/* HP (left) and Fatigue (right) — see VitalBar above. */}
        <VitalBar
          side="left"
          label="HP"
          color={colors.danger}
          trackColor={colors.bg.negativeLight}
          tooltipShadow={`0 0 8px ${colors.danger}99`}
          fillRatio={hpPercent}
          current={hp.current}
          max={hp.max}
          active={hoveredBar === 'hp' || focusedBar === 'hp'}
          onHoverChange={(on) => setHoveredBar(on ? 'hp' : null)}
          onToggle={() => setFocusedBar(focusedBar === 'hp' ? null : 'hp')}
          testId="hp-bar"
        />

        <VitalBar
          side="right"
          label="Fatigue"
          color={colors.secondary}
          trackColor={colors.bg.highlightLight}
          tooltipShadow={shadows.glow}
          fillRatio={fatiguePercent}
          current={fatigue.current}
          max={fatigue.max}
          active={hoveredBar === 'fatigue' || focusedBar === 'fatigue'}
          onHoverChange={(on) => setHoveredBar(on ? 'fatigue' : null)}
          onToggle={() => setFocusedBar(focusedBar === 'fatigue' ? null : 'fatigue')}
          testId="fatigue-bar"
        />

        {/* Surrounding Buttons */}
        {buttons.map(({ key, label, top, left, transform, onClick, color }) => {
          const isHovered = hoveredButton === key
          const baseColor = color || colors.primary
          const hoverColor = color || '#00ffaa'

          return (
            <button
              key={key}
              onClick={onClick}
              onMouseEnter={() => setHoveredButton(key)}
              onMouseLeave={() => setHoveredButton(null)}
              style={{
                position: 'absolute',
                top,
                left,
                transform,
                width: '70px',
                height: accessibility.touchTarget,
                minHeight: accessibility.touchTarget,
                borderRadius: '6px',
                border: `2px solid ${isHovered ? hoverColor : baseColor}`,
                backgroundColor: isHovered
                  ? `${baseColor}4D`
                  : `${baseColor}1A`,
                color: isHovered ? hoverColor : baseColor,
                fontSize: '9px',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: isHovered
                  ? `0 0 12px ${baseColor}B3`
                  : `0 0 6px ${baseColor}44`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: fonts.main,
                zIndex: 5,
                textAlign: 'center',
                padding: '4px',
                lineHeight: '1.2',
                textTransform: 'uppercase'
              }}
            >
              {label}
            </button>
          )
        })}
      </div>

      {/* Mobile-only: passives + status icons as a compact inline row */}
      {isMobile && (player?.passives?.length > 0 || player?.status_effects?.length > 0) && (
        <div style={{ display: 'flex', flexDirection: 'row', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
          {player?.passives?.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}>
              <GameText variant="muted" size="xs" weight="bold" style={{ fontSize: '7px' }}>PASSIVES</GameText>
              <StatusEffectsIconPanel effects={player.passives} />
            </div>
          )}
          {player?.status_effects?.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}>
              <GameText variant="muted" size="xs" weight="bold" style={{ fontSize: '7px' }}>STATUS</GameText>
              <StatusEffectsIconPanel effects={player.status_effects} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default React.memo(HeroPanel)
