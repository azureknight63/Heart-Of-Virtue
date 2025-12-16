import { useState } from 'react'

export default function HeroPanel({
  player,
  inCombat,
  hasSpecialMoves,
  hasDefensiveMoves,
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
    current: player?.hp || 100,
    max: player?.max_hp || 100,
  }
  const fatigue = {
    current: player?.fatigue || 150,
    max: player?.max_fatigue || 150,
  }

  // Calculate heart rate based on HP and Combat status
  // Base: 60 BPM
  // Combat: +40 BPM
  // Low HP: Up to +60 BPM (Exploration) or +80 BPM (Combat)
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
    { key: 'offensive', label: 'OFFENSIVE', top: '0px', left: '20%', transform: 'translateX(-50%)', onClick: onOffensiveClick, color: '#ff4444' },
    { key: 'maneuver', label: 'MANEUVER', top: '0px', left: 'calc(50% + 60px)', transform: 'translate(-50%, 0)', onClick: onManeuverClick, color: '#4444ff' },
    { key: 'inventory', label: 'INVENTORY', top: '50%', left: '-40px', transform: 'translateY(-50%)', onClick: onInventoryClick },
    { key: 'special', label: 'SPECIAL', top: '50%', left: 'calc(50% + 70px)', transform: 'translateY(-50%)', onClick: onSpecialClick, color: '#9944ff', show: hasSpecialMoves },
    { key: 'miscellaneous', label: 'MISC', top: 'calc(50% + 80px)', left: '5px', transform: 'translate(0, -50%)', onClick: onMiscellaneousClick, color: '#aaaaaa' },
    { key: 'defensive', label: 'DEFENSIVE', top: 'calc(50% + 80px)', left: 'calc(50% + 60px)', transform: 'translate(-50%, -50%)', onClick: onDefensiveClick, color: '#eebb00', show: hasDefensiveMoves },
  ]

  const buttons = inCombat ? combatButtons.filter(btn => btn.show !== false) : explorationButtons

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
      alignItems: 'center',
      padding: '24px 16px',
      position: 'relative',
    }}>
      {/* Hero Head Container */}
      <div style={{
        position: 'relative',
        width: '200px',
        height: '200px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'visible',
      }}>
        {/* Hero Heart Image */}
        <img
          src="/hero-heart.png"
          alt="Hero Heart"
          style={{
            width: '140px',
            height: '140px',
            objectFit: 'contain',
            filter: 'drop-shadow(0 0 10px rgba(0, 255, 136, 0.3))',
            zIndex: 10,
            animation: `pulse ${animationDuration} infinite ease-in-out`,
          }}
        />
        <style>
          {`
            @keyframes pulse {
              0% { transform: scale(1); filter: drop-shadow(0 0 10px rgba(0, 255, 136, 0.3)); }
              10% { transform: scale(1.007); filter: drop-shadow(0 0 14px rgba(0, 255, 136, 0.25)); }
              20% { transform: scale(1); filter: drop-shadow(0 0 10px rgba(0, 255, 136, 0.3)); }
              30% { transform: scale(1.007); filter: drop-shadow(0 0 14px rgba(0, 255, 136, 0.25)); }
              50% { transform: scale(1); filter: drop-shadow(0 0 10px rgba(0, 255, 136, 0.3)); }
              100% { transform: scale(1); filter: drop-shadow(0 0 10px rgba(0, 255, 136, 0.3)); }
            }
          `}
        </style>

        {/* HP Bar - Left Side Curved */}
        <div
          onMouseEnter={() => setHoveredBar('hp')}
          onMouseLeave={() => setHoveredBar(null)}
          onClick={() => setFocusedBar(focusedBar === 'hp' ? null : 'hp')}
          onTouchStart={() => setFocusedBar(focusedBar === 'hp' ? null : 'hp')}
          style={{
            position: 'absolute',
            left: '-75px',
            top: '50%',
            transform: 'translateY(-50%)',
            width: '15px',
            height: '150px',
            borderRadius: '15px 0 0 15px',
            border: '2px solid #ff4444',
            backgroundColor: 'rgba(255, 68, 68, 0.1)',
            boxShadow: '0 0 10px rgba(255, 68, 68, 0.5), inset 0 0 8px rgba(255, 68, 68, 0.3)',
            zIndex: 3,
            display: 'flex',
            flexDirection: 'column-reverse',
            overflow: 'visible',
            cursor: 'pointer',
          }}>
          {/* HP Fill */}
          <div style={{
            width: '100%',
            height: `${(hp.current / hp.max) * 100}%`,
            backgroundColor: '#ff4444',
            borderRadius: '12px 0 0 12px',
            boxShadow: '0 0 8px rgba(255, 68, 68, 0.8), inset 0 0 4px rgba(255, 255, 255, 0.3)',
          }} />

          {/* HP Tooltip */}
          {(hoveredBar === 'hp' || focusedBar === 'hp') && (
            <div style={{
              position: 'absolute',
              left: '50%',
              bottom: '-35px',
              transform: 'translateX(-50%)',
              backgroundColor: '#1a1a1a',
              border: '1.5px solid #ff4444',
              borderRadius: '3px',
              padding: '4px 6px',
              color: '#ff4444',
              fontSize: '8px',
              fontWeight: 'bold',
              fontFamily: 'monospace',
              whiteSpace: 'nowrap',
              boxShadow: '0 0 8px rgba(255, 68, 68, 0.6)',
              zIndex: 20,
            }}>
              HP<br />{hp.current}/{hp.max}
            </div>
          )}
        </div>

        {/* Fatigue Bar - Right Side Curved */}
        <div
          onMouseEnter={() => setHoveredBar('fatigue')}
          onMouseLeave={() => setHoveredBar(null)}
          onClick={() => setFocusedBar(focusedBar === 'fatigue' ? null : 'fatigue')}
          onTouchStart={() => setFocusedBar(focusedBar === 'fatigue' ? null : 'fatigue')}
          style={{
            position: 'absolute',
            right: '-75px',
            top: '50%',
            transform: 'translateY(-50%)',
            width: '15px',
            height: '150px',
            borderRadius: '0 15px 15px 0',
            border: '2px solid #ffaa00',
            backgroundColor: 'rgba(255, 170, 0, 0.1)',
            boxShadow: '0 0 10px rgba(255, 170, 0, 0.5), inset 0 0 8px rgba(255, 170, 0, 0.3)',
            zIndex: 3,
            display: 'flex',
            flexDirection: 'column-reverse',
            overflow: 'visible',
            cursor: 'pointer',
          }}>
          {/* Fatigue Fill */}
          <div style={{
            width: '100%',
            height: `${(fatigue.current / fatigue.max) * 100}%`,
            backgroundColor: '#ffaa00',
            borderRadius: '0 12px 12px 0',
            boxShadow: '0 0 8px rgba(255, 170, 0, 0.8), inset 0 0 4px rgba(255, 255, 255, 0.3)',
          }} />

          {/* Fatigue Tooltip */}
          {(hoveredBar === 'fatigue' || focusedBar === 'fatigue') && (
            <div style={{
              position: 'absolute',
              right: '50%',
              bottom: '-35px',
              transform: 'translateX(50%)',
              backgroundColor: '#1a1a1a',
              border: '1.5px solid #ffaa00',
              borderRadius: '3px',
              padding: '4px 6px',
              color: '#ffaa00',
              fontSize: '8px',
              fontWeight: 'bold',
              fontFamily: 'monospace',
              whiteSpace: 'nowrap',
              boxShadow: '0 0 8px rgba(255, 170, 0, 0.6)',
              zIndex: 20,
            }}>
              Fatigue<br />{fatigue.current}/{fatigue.max}
            </div>
          )}
        </div>

        {/* Surrounding Buttons */}
        {buttons.map(({ key, label, top, left, transform, onClick, color }) => {
          const isHovered = hoveredButton === key
          const baseColor = color || '#00aa55'
          const hoverColor = color || '#00ff88'

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
                borderRadius: '4px',
                border: `2px solid ${isHovered ? hoverColor : baseColor}`,
                backgroundColor: isHovered
                  ? `${baseColor}4D` // 30% opacity
                  : `${baseColor}1A`, // 10% opacity
                color: isHovered ? hoverColor : baseColor,
                fontSize: '9px',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: isHovered
                  ? `0 0 12px ${baseColor}B3` // 70% opacity
                  : `0 0 6px ${baseColor}4D`, // 30% opacity
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: 'monospace',
                zIndex: 5,
                textAlign: 'center',
                padding: '4px',
                lineHeight: '1.2',
              }}
            >
              {label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
