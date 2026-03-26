import React, { useState } from 'react'
import { colors, spacing, fonts, shadows } from '../styles/theme'
import StatusEffectsIconPanel from './StatusEffectsIconPanel'
import GameText from './GameText'

function HeroPanel({
  player,
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

  // Calculate heart rate based on HP and Combat status
  const hpPercent = Math.max(0, Math.min(1, hp.current / hp.max))
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
        {/* Passive Effects Icons (Left Side) */}
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

        {/* Status Effects Icons (Right Side) */}
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

        {/* HP Bar - Left Side Curved */}
        <div
          onMouseEnter={() => setHoveredBar('hp')}
          onMouseLeave={() => setHoveredBar(null)}
          onClick={() => setFocusedBar(focusedBar === 'hp' ? null : 'hp')}
          onTouchStart={(e) => {
            e.preventDefault();
            setFocusedBar(focusedBar === 'hp' ? null : 'hp');
          }}
          style={{
            position: 'absolute',
            left: '-75px',
            top: '50%',
            transform: 'translateY(-50%)',
            width: '15px',
            height: '150px',
            borderRadius: '15px 0 0 15px',
            border: `2px solid ${colors.danger}`,
            backgroundColor: colors.bg.negativeLight,
            boxShadow: `0 0 10px ${colors.danger}88, inset 0 0 8px ${colors.danger}44`,
            zIndex: 3,
            display: 'flex',
            flexDirection: 'column-reverse',
            overflow: 'visible',
            cursor: 'pointer',
          }}
          data-testid="hp-bar"
        >
          <div style={{
            width: '100%',
            height: `${(hp.current / hp.max) * 100}%`,
            backgroundColor: colors.danger,
            borderRadius: '12px 0 0 12px',
            boxShadow: `0 0 8px ${colors.danger}, inset 0 0 4px rgba(255, 255, 255, 0.3)`,
          }} />

          {(hoveredBar === 'hp' || focusedBar === 'hp') && (
            <div style={{
              position: 'absolute',
              left: '50%',
              bottom: '-35px',
              transform: 'translateX(-50%)',
              backgroundColor: colors.bg.main,
              border: `1.5px solid ${colors.danger}`,
              borderRadius: '3px',
              padding: '4px 6px',
              color: colors.danger,
              fontSize: '8px',
              fontWeight: 'bold',
              fontFamily: fonts.main,
              whiteSpace: 'nowrap',
              boxShadow: `0 0 8px ${colors.danger}99`,
              zIndex: 20,
            }}>
              HP<br />{hp.current.toFixed(0)}/{hp.max}
            </div>
          )}
        </div>

        <div
          onMouseEnter={() => setHoveredBar('fatigue')}
          onMouseLeave={() => setHoveredBar(null)}
          onClick={() => setFocusedBar(focusedBar === 'fatigue' ? null : 'fatigue')}
          onTouchStart={(e) => {
            e.preventDefault();
            setFocusedBar(focusedBar === 'fatigue' ? null : 'fatigue');
          }}
          style={{
            position: 'absolute',
            right: '-75px',
            top: '50%',
            transform: 'translateY(-50%)',
            width: '15px',
            height: '150px',
            borderRadius: '0 15px 15px 0',
            border: `2px solid ${colors.secondary}`,
            backgroundColor: colors.bg.highlightLight,
            boxShadow: `0 0 10px ${colors.secondary}88, inset 0 0 8px ${colors.secondary}44`,
            zIndex: 3,
            display: 'flex',
            flexDirection: 'column-reverse',
            overflow: 'visible',
            cursor: 'pointer',
          }}
          data-testid="fatigue-bar"
        >
          <div style={{
            width: '100%',
            height: `${(fatigue.current / fatigue.max) * 100}%`,
            backgroundColor: colors.secondary,
            borderRadius: '0 12px 12px 0',
            boxShadow: `0 0 8px ${colors.secondary}, inset 0 0 4px rgba(255, 255, 255, 0.3)`,
          }} />

          {(hoveredBar === 'fatigue' || focusedBar === 'fatigue') && (
            <div style={{
              position: 'absolute',
              right: '50%',
              bottom: '-35px',
              transform: 'translateX(50%)',
              backgroundColor: colors.bg.main,
              border: `1.5px solid ${colors.secondary}`,
              borderRadius: '3px',
              padding: '4px 6px',
              color: colors.secondary,
              fontSize: '8px',
              fontWeight: 'bold',
              fontFamily: fonts.main,
              whiteSpace: 'nowrap',
              boxShadow: shadows.glow,
              zIndex: 20,
            }}>
              Fatigue<br />{fatigue.current.toFixed(0)}/{fatigue.max}
            </div>
          )}
        </div>

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
                height: '40px',
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
    </div >
  )
}

export default React.memo(HeroPanel)
