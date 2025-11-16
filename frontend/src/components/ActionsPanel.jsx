/**
 * ActionsPanel - Display available actions player can take
 * Shows movement directions, rest, wait, and other exploration actions
 */

import { useState } from 'react'

export default function ActionsPanel({ player, location, onClose }) {
  const [actionMessage, setActionMessage] = useState('')

  if (!location) return null

  // Standard actions available
  const standardActions = [
    { name: 'Rest', description: 'Take a break to recover', icon: '🛌', action: 'rest' },
    { name: 'Look Around', description: 'Examine the area more carefully', icon: '👁️', action: 'look' },
  ]

  const handleAction = (action) => {
    // Other actions (for now, just show message)
    setActionMessage(`${action.name}...`)
    setTimeout(() => {
      setActionMessage('')
    }, 2000)
  }

  return (
    <div style={{
      backgroundColor: 'rgba(50, 20, 0, 0.3)',
      border: '2px solid #ffaa00',
      borderRadius: '6px',
      padding: '8px',
      display: 'flex',
      flexDirection: 'column',
      gap: '6px',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '2px solid #ffaa00',
        paddingBottom: '4px',
        marginBottom: '2px',
      }}>
        <div style={{
          color: '#ffff00',
          fontWeight: 'bold',
          fontSize: '13px',
          fontFamily: 'monospace',
        }}>
          ⚡ ACTIONS
        </div>
        <button
          onClick={onClose}
          style={{
            padding: '2px 6px',
            backgroundColor: '#cc4400',
            color: '#ffff00',
            border: '1px solid #ff6600',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '10px',
            fontFamily: 'monospace',
            fontWeight: 'bold',
          }}
          onMouseEnter={(e) => {
            e.target.style.backgroundColor = '#ff6600'
          }}
          onMouseLeave={(e) => {
            e.target.style.backgroundColor = '#cc4400'
          }}
        >
          ✕
        </button>
      </div>

      {/* Action Message */}
      {actionMessage && (
        <div style={{
          backgroundColor: 'rgba(100, 50, 0, 0.5)',
          border: '1px solid #ffaa00',
          borderRadius: '3px',
          padding: '4px 6px',
          fontSize: '10px',
          fontFamily: 'monospace',
          color: '#ffff00',
          textAlign: 'center',
        }}>
          {actionMessage}
        </div>
      )}

      {/* Standard Actions */}
      {standardActions.length > 0 && (
        <div style={{
          backgroundColor: 'rgba(30, 15, 0, 0.3)',
          border: '1px solid #664400',
          borderRadius: '4px',
          padding: '6px',
        }}>
          <div style={{
            color: '#ffcc00',
            fontWeight: 'bold',
            fontSize: '10px',
            fontFamily: 'monospace',
            marginBottom: '4px',
          }}>
            🎯 Actions
          </div>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '3px',
          }}>
            {standardActions.map((action, idx) => (
              <button
                key={idx}
                onClick={() => handleAction(action)}
                style={{
                  padding: '6px 8px',
                  backgroundColor: 'rgba(100, 50, 0, 0.3)',
                  border: '1px solid #ff9933',
                  borderRadius: '3px',
                  color: '#ffcc88',
                  fontFamily: 'monospace',
                  fontSize: '10px',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = 'rgba(150, 80, 0, 0.5)'
                  e.target.style.boxShadow = '0 0 8px rgba(255, 153, 51, 0.4) inset'
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = 'rgba(100, 50, 0, 0.3)'
                  e.target.style.boxShadow = 'none'
                }}
              >
                <span style={{ fontWeight: 'bold', marginRight: '4px' }}>
                  {action.icon}
                </span>
                {action.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Help Text */}
      <div style={{
        fontSize: '9px',
        color: '#999999',
        fontFamily: 'monospace',
        marginTop: '2px',
        padding: '4px',
        borderTop: '1px solid #664400',
        textAlign: 'center',
      }}>
        Interactions with objects/NPCs in the Interactions menu
      </div>
    </div>
  )
}
