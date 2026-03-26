import { useState } from 'react'
import { useAudio } from '../context/AudioContext'

export default function MovementStar({ exits = [], onMove, loading = false }) {
  const [hoveredDirection, setHoveredDirection] = useState(null)
  const { playSFX } = useAudio()

  // Determine which directions are valid (available in exits)
  const isDirectionValid = (direction) => exits && exits.includes(direction)

  // Direction configuration with positions for proper 8-point star layout
  // Container is 220x220px, button is 40x40px
  // Calculations center button around the star using calc()
  const directions = [
    // Cardinal directions (distance: 80px from center, accounting for 40px button size)
    { key: 'north', label: '↑', top: 'calc(50% - 65px)', left: 'calc(50% - 20px)', transform: 'translate(0, 0)', ariaLabel: 'Move North' },
    { key: 'east', label: '→', top: 'calc(50% - 20px)', left: 'calc(50% + 25px)', transform: 'translate(0, 0)', ariaLabel: 'Move East' },
    { key: 'south', label: '↓', top: 'calc(50% + 25px)', left: 'calc(50% - 20px)', transform: 'translate(0, 0)', ariaLabel: 'Move South' },
    { key: 'west', label: '←', top: 'calc(50% - 20px)', left: 'calc(50% - 65px)', transform: 'translate(0, 0)', ariaLabel: 'Move West' },
    // Diagonal directions (distance: ~57px at 45 degrees)
    { key: 'northeast', label: '↗', top: 'calc(50% - 65px)', left: 'calc(50% + 25px)', transform: 'translate(0, 0)', ariaLabel: 'Move Northeast' },
    { key: 'northwest', label: '↖', top: 'calc(50% - 65px)', left: 'calc(50% - 65px)', transform: 'translate(0, 0)', ariaLabel: 'Move Northwest' },
    { key: 'southeast', label: '↘', top: 'calc(50% + 25px)', left: 'calc(50% + 25px)', transform: 'translate(0, 0)', ariaLabel: 'Move Southeast' },
    { key: 'southwest', label: '↙', top: 'calc(50% + 25px)', left: 'calc(50% - 65px)', transform: 'translate(0, 0)', ariaLabel: 'Move Southwest' },
  ]

  const handleMove = async (direction) => {
    if (!isDirectionValid(direction) || loading) return
    playSFX('move')
    try {
      await onMove(direction)
    } catch (err) {
      console.error(`Failed to move ${direction}:`, err)
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      alignItems: 'center',
      padding: '0',
    }}>
      <div style={{
        color: '#00ff88',
        fontSize: '12px',
        fontWeight: 'bold',
        textTransform: 'uppercase',
        letterSpacing: '1px',
      }}>
        Movement
      </div>

      {/* Star Container */}
      <div style={{
        position: 'relative',
        width: '220px',
        height: '120px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        {/* Center indicator */}
        <div style={{
          width: '30px',
          height: '30px',
          borderRadius: '50%',
          backgroundColor: '#00ff88',
          boxShadow: '0 0 20px rgba(0, 255, 136, 0.8), inset 0 0 10px rgba(0, 0, 0, 0.5)',
          position: 'absolute',
          zIndex: 10,
          border: '2px solid #00aa55',
        }} />

        {/* Direction arrows */}
        {directions.map(({ key, label, top, left, transform, ariaLabel }) => {
          const isValid = isDirectionValid(key)
          const isHovered = hoveredDirection === key

          return (
            <button
              key={key}
              aria-label={ariaLabel}
              onClick={() => handleMove(key)}
              onMouseEnter={() => !loading && isValid && setHoveredDirection(key)}
              onMouseLeave={() => setHoveredDirection(null)}
              disabled={!isValid || loading}
              style={{
                position: 'absolute',
                top,
                left,
                transform,
                width: '40px',
                height: '40px',
                borderRadius: '4px',
                border: `2px solid ${isValid ? '#00ff88' : '#666666'}`,
                backgroundColor: isValid
                  ? isHovered
                    ? '#00ff88'
                    : 'rgba(0, 255, 136, 0.2)'
                  : 'rgba(100, 100, 100, 0.1)',
                color: isValid
                  ? isHovered
                    ? '#000000'
                    : '#00ff88'
                  : '#666666',
                fontSize: '20px',
                fontWeight: 'bold',
                cursor: isValid && !loading ? 'pointer' : 'not-allowed',
                transition: 'all 0.2s ease',
                boxShadow: isValid
                  ? isHovered
                    ? '0 0 15px rgba(0, 255, 136, 0.9), inset 0 0 8px rgba(0, 255, 136, 0.4)'
                    : '0 0 8px rgba(0, 255, 136, 0.5)'
                  : 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: 'monospace',
                zIndex: 5,
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
