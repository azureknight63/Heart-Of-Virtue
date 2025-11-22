/**
 * ActionsPanel - Display available actions player can take
 * Fetches commands from backend and displays all available actions
 */

import { useState, useEffect } from 'react'

// Tooltip descriptions for each command
const COMMAND_TOOLTIPS = {
  'Search': 'Search the current location for hidden items or clues',
  'Menu': 'Open the main menu',
  'Save': 'Save your game progress',
  'Teleport': '[DEBUG] Teleport to a specific location',
  'Alter': '[DEBUG] Change game variables and switches',
  'Showvar': '[DEBUG] Display all game variables',
  'Supersaiyan': '[DEBUG] Max out your stats',
  'TestEvent': '[DEBUG] Trigger test events',
  'SpawnObj': '[DEBUG] Spawn objects on this tile',
  'Refresh Merchants': '[DEBUG] Refresh all merchant inventories',
}

export default function ActionsPanel({ player, location, onClose }) {
  const [commands, setCommands] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [actionMessage, setActionMessage] = useState('')
  const [hoveredCommand, setHoveredCommand] = useState(null)

  // Fetch available commands from backend
  useEffect(() => {
    const fetchCommands = async () => {
      try {
        setLoading(true)
        const token = localStorage.getItem('authToken')
        const response = await fetch('http://localhost:5000/api/world/commands', {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        })

        if (response.ok) {
          const data = await response.json()
          setCommands(data.commands || [])
          setError(null)
        } else {
          setError('Failed to load commands')
          setCommands([])
        }
      } catch (err) {
        console.error('Error fetching commands:', err)
        setError('Error loading commands')
        setCommands([])
      } finally {
        setLoading(false)
      }
    }

    fetchCommands()
  }, [location])

  const handleAction = (command) => {
    setActionMessage(`${command.name}...`)
    setTimeout(() => {
      setActionMessage('')
    }, 1500)
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
          ⚡ COMMANDS
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

      {/* Loading State */}
      {loading && (
        <div style={{
          color: '#ffcc00',
          fontSize: '10px',
          fontFamily: 'monospace',
          textAlign: 'center',
          padding: '8px',
        }}>
          Loading commands...
        </div>
      )}

      {/* Error State */}
      {error && (
        <div style={{
          color: '#ff6666',
          fontSize: '10px',
          fontFamily: 'monospace',
          padding: '8px',
          backgroundColor: 'rgba(100, 0, 0, 0.2)',
          borderRadius: '3px',
        }}>
          {error}
        </div>
      )}

      {/* Commands List - Inline blocks */}
      {!loading && commands.length > 0 && (
        <div style={{
          backgroundColor: 'rgba(30, 15, 0, 0.3)',
          border: '1px solid #664400',
          borderRadius: '4px',
          padding: '6px',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '4px',
          position: 'relative',
        }}>
          {commands.map((command, idx) => {
            // Determine colors based on command type
            const isDebug = command.color === 'silver'
            const bgColor = isDebug ? 'rgba(80, 80, 90, 0.3)' : 'rgba(100, 50, 0, 0.3)'
            const borderColor = isDebug ? '#a9a9a9' : '#ff9933'
            const textColor = isDebug ? '#c0c0c0' : '#ffcc88'
            const hoverBgColor = isDebug ? 'rgba(120, 120, 130, 0.5)' : 'rgba(150, 80, 0, 0.5)'
            const hoverShadow = isDebug 
              ? '0 0 8px rgba(192, 192, 192, 0.4) inset'
              : '0 0 8px rgba(255, 153, 51, 0.4) inset'
            
            return (
              <div key={idx} style={{ position: 'relative', display: 'inline-block' }}>
                <button
                  onClick={() => handleAction(command)}
                  onMouseEnter={(e) => {
                    setHoveredCommand(idx)
                    e.target.style.backgroundColor = hoverBgColor
                    e.target.style.boxShadow = hoverShadow
                  }}
                  onMouseLeave={(e) => {
                    setHoveredCommand(null)
                    e.target.style.backgroundColor = bgColor
                    e.target.style.boxShadow = 'none'
                  }}
                  style={{
                    padding: '8px 14px',
                    backgroundColor: bgColor,
                    border: `1px solid ${borderColor}`,
                    borderRadius: '3px',
                    color: textColor,
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    display: 'inline-block',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {command.name}
                </button>
                
                {/* Tooltip */}
                {hoveredCommand === idx && (
                  <div style={{
                    position: 'absolute',
                    bottom: '100%',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    marginBottom: '8px',
                    backgroundColor: 'rgba(20, 20, 20, 0.95)',
                    border: '1px solid #ffaa00',
                    borderRadius: '4px',
                    padding: '10px 14px',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                    color: '#ffcc88',
                    maxWidth: '280px',
                    whiteSpace: 'normal',
                    zIndex: 1000,
                    textAlign: 'center',
                    boxShadow: '0 0 8px rgba(255, 170, 0, 0.3)',
                    lineHeight: '1.4',
                  }}>
                    {COMMAND_TOOLTIPS[command.name] || 'Unknown command'}
                    {/* Tooltip arrow */}
                    <div style={{
                      position: 'absolute',
                      top: '100%',
                      left: '50%',
                      transform: 'translateX(-50%)',
                      width: '0',
                      height: '0',
                      borderLeft: '6px solid transparent',
                      borderRight: '6px solid transparent',
                      borderTop: '6px solid rgba(20, 20, 20, 0.95)',
                    }} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Empty State */}
      {!loading && commands.length === 0 && !error && (
        <div style={{
          color: '#666666',
          fontSize: '11px',
          fontStyle: 'italic',
          textAlign: 'center',
          padding: '8px',
        }}>
          No commands available
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
        Hover over a command for details
      </div>
    </div>
  )
}
