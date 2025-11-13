import { useState } from 'react'

export default function HeroPanel({ onAttributeClick, onStatusClick, onSkillsClick, onInventoryClick, onActionsClick, onInteractClick }) {
  const [hoveredButton, setHoveredButton] = useState(null)
  const [hoveredBar, setHoveredBar] = useState(null)
  const [focusedBar, setFocusedBar] = useState(null)

  // Mock values - replace with actual player stats
  const hp = { current: 70, max: 100 }
  const fatigue = { current: 55, max: 100 }

  const buttons = [
    { key: 'attributes', label: 'ATTRIBUTES', top: '0px', left: '20%', transform: 'translateX(-50%)', onClick: onAttributeClick },
    { key: 'status', label: 'STATUS', top: '0px', left: 'calc(50% + 60px)', transform: 'translate(-50%, 0)', onClick: onStatusClick },
    { key: 'inventory', label: 'INVENTORY', top: '50%', left: '-40px', transform: 'translateY(-50%)', onClick: onInventoryClick },
    { key: 'skills', label: 'SKILLS', top: '50%', left: 'calc(50% + 70px)', transform: 'translateY(-50%)', onClick: onSkillsClick },
    { key: 'actions', label: 'ACTIONS', top: 'calc(50% + 80px)', left: '5px', transform: 'translate(0, -50%)', onClick: onActionsClick },
    { key: 'interact', label: 'INTERACT', top: 'calc(50% + 80px)', left: 'calc(50% + 60px)', transform: 'translate(-50%, -50%)', onClick: onInteractClick },
  ]

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
      }}>
        {/* Hero Silhouette */}
        <div style={{
          width: '60px',
          height: '70px',
          backgroundColor: '#1a1a1a',
          borderRadius: '50% 50% 45% 45%',
          border: '2px solid #00ff88',
          boxShadow: '0 0 15px rgba(0, 255, 136, 0.5), inset 0 0 10px rgba(0, 0, 0, 0.8)',
          position: 'absolute',
          zIndex: 10,
        }} />

        {/* Hero Shoulders */}
        <div style={{
          width: '90px',
          height: '45px',
          backgroundColor: '#1a1a1a',
          borderRadius: '30px 30px 0 0',
          border: '2px solid #00ff88',
          borderBottom: 'none',
          boxShadow: '0 0 15px rgba(0, 255, 136, 0.5), inset 0 0 10px rgba(0, 0, 0, 0.8)',
          position: 'absolute',
          top: '120px',
          zIndex: 9,
          maskImage: 'linear-gradient(to bottom, rgba(0, 0, 0, 1) 0%, rgba(0, 0, 0, 0.01) 100%)',
          WebkitMaskImage: 'linear-gradient(to bottom, rgba(0, 0, 0, 1) 0%, rgba(0, 0, 0, 0.01) 100%)',
        }} />

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
              left: '-65px',
              top: '50%',
              transform: 'translateY(-50%)',
              backgroundColor: '#1a1a1a',
              border: '2px solid #ff4444',
              borderRadius: '4px',
              padding: '6px 8px',
              color: '#ff4444',
              fontSize: '11px',
              fontWeight: 'bold',
              fontFamily: 'monospace',
              whiteSpace: 'nowrap',
              boxShadow: '0 0 10px rgba(255, 68, 68, 0.6)',
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
              right: '-75px',
              top: '50%',
              transform: 'translateY(-50%)',
              backgroundColor: '#1a1a1a',
              border: '2px solid #ffaa00',
              borderRadius: '4px',
              padding: '6px 8px',
              color: '#ffaa00',
              fontSize: '11px',
              fontWeight: 'bold',
              fontFamily: 'monospace',
              whiteSpace: 'nowrap',
              boxShadow: '0 0 10px rgba(255, 170, 0, 0.6)',
              zIndex: 20,
            }}>
              Fatigue<br />{fatigue.current}/{fatigue.max}
            </div>
          )}
        </div>

        {/* Surrounding Buttons */}
        {buttons.map(({ key, label, top, left, transform, onClick }) => {
          const isHovered = hoveredButton === key

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
                border: `2px solid ${isHovered ? '#00ff88' : '#00aa55'}`,
                backgroundColor: isHovered
                  ? 'rgba(0, 255, 136, 0.3)'
                  : 'rgba(0, 170, 85, 0.1)',
                color: isHovered ? '#00ff88' : '#00aa55',
                fontSize: '9px',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: isHovered
                  ? '0 0 12px rgba(0, 255, 136, 0.7)'
                  : '0 0 6px rgba(0, 170, 85, 0.3)',
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
