import { useState } from 'react'

const ORANGE = '#FF8800'
const BG = '#0a0a0a'
const MUTED = '#666'

export default function FleeButton({ onFlee, isMobile = false }) {
  const [confirming, setConfirming] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [hovered, setHovered] = useState(false)

  const fontSize = isMobile ? '11px' : '13px'
  const padding = isMobile ? '4px 10px' : '6px 16px'

  const handleConfirm = async () => {
    setIsLoading(true)
    try {
      await onFlee()
    } catch (_err) {
      // flee failed — reset button state; combat status poll reflects current state
    } finally {
      setIsLoading(false)
      setConfirming(false)
    }
  }

  if (confirming) {
    return (
      <div
        data-testid="flee-confirm-prompt"
        style={{
          border: `1px solid ${ORANGE}`,
          background: BG,
          padding: '8px 12px',
          fontFamily: 'monospace',
          fontSize,
          color: ORANGE,
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
        }}
      >
        <span>Flee combat? This will end the fight.</span>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            data-testid="flee-confirm-yes"
            onClick={handleConfirm}
            disabled={isLoading}
            style={{
              background: ORANGE,
              color: BG,
              border: 'none',
              padding,
              fontSize,
              fontFamily: 'monospace',
              fontWeight: 'bold',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              opacity: isLoading ? 0.7 : 1,
            }}
          >
            {isLoading ? 'Fleeing...' : 'Confirm Flee'}
          </button>
          <button
            data-testid="flee-confirm-cancel"
            onClick={() => setConfirming(false)}
            disabled={isLoading}
            style={{
              background: 'transparent',
              color: MUTED,
              border: `1px solid ${MUTED}`,
              padding,
              fontSize,
              fontFamily: 'monospace',
              cursor: isLoading ? 'not-allowed' : 'pointer',
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <button
      data-testid="flee-btn"
      onClick={() => setConfirming(true)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered ? `${ORANGE}22` : BG,
        color: ORANGE,
        border: `1px solid ${ORANGE}66`,
        padding,
        fontSize,
        fontFamily: 'monospace',
        fontWeight: 'bold',
        cursor: 'pointer',
        width: '100%',
        textAlign: 'left',
        boxShadow: hovered ? `0 0 10px ${ORANGE}66` : 'none',
        transition: 'all 0.15s ease',
      }}
    >
      ⚡ FLEE COMBAT
    </button>
  )
}
