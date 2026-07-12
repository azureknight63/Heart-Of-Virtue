import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAudio } from '../context/AudioContext'
import apiEndpoints from '../api/endpoints'
import BaseDialog from './BaseDialog'
import { colors, spacing } from '../styles/theme'

// Tooltip descriptions for each command
const COMMAND_TOOLTIPS = {
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

function isDebugMode() {
  // Show debug label when running in development mode
  return import.meta.env.DEV;
}

// Debug commands advertised by the backend (Teleport, Alter, Showvar, etc.) have
// no wired handler and no execute endpoint — COMMAND_HANDLERS only supports Menu
// and Save, so anything else falls through to a fake "..." toast that does
// nothing. Filter them out so the panel doesn't show convincing-but-inert
// buttons. Primary signal is the API's `debug` flag; the name set is a fallback
// for any command payload that omits it.
const KNOWN_DEBUG_COMMAND_NAMES = new Set([
  'Teleport',
  'Alter',
  'Showvar',
  'Supersaiyan',
  'TestEvent',
  'SpawnObj',
  'Refresh Merchants',
])

function isInertDebugCommand(command) {
  return command.debug === true || KNOWN_DEBUG_COMMAND_NAMES.has(command.name)
}

/**
 * ActionsPanel - Display available actions player can take
 */
export default function ActionsPanel({ player, location, onClose, onRefetch, onMove }) {
  const [commands, setCommands] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [actionMessage, setActionMessage] = useState('')
  const [hoveredCommand, setHoveredCommand] = useState(null)
  const { playSFX } = useAudio()
  const navigate = useNavigate()
  const timerRef = useRef(null)

  // Helper to show a timed action message without leaking setTimeout callbacks
  const setTimedMessage = (msg, delay = 2000) => {
    setActionMessage(msg)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setActionMessage(''), delay)
  }

  // Clean up any pending timer when the component unmounts
  useEffect(() => () => clearTimeout(timerRef.current), [])

  // Fetch available commands from backend
  useEffect(() => {
    const fetchCommands = async () => {
      try {
        setLoading(true)
        const response = await apiEndpoints.world.getCommands()

        if (response.data) {
          setCommands(response.data.commands || [])
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

  const handleMenu = () => {
    setActionMessage('Opening menu...')
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => navigate('/menu'), 300)
  }

  const handleSave = async () => {
    setActionMessage('Saving game...')
    const saveName = `Save_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}`

    try {
      const response = await apiEndpoints.saves.save(saveName)

      if (response.data && response.data.success) {
        setTimedMessage(response.data.message || 'Game saved successfully!', 3000)
      } else {
        setTimedMessage(response.data?.error || 'Save failed.', 3000)
      }
    } catch (err) {
      // apiEndpoints.saves.save() rejects for any non-2xx response (403 no
      // account / save-limit reached, 500 server error, etc). Without this
      // catch, the rejection bubbles up to handleAction()'s generic handler
      // and gets replaced with an uninformative "Command failed." toast that
      // hides the real, often actionable, backend error message (e.g. "Maximum
      // number of manual saves reached (20)."). Surface it here instead.
      const backendMessage = err.response?.data?.error
      setTimedMessage(backendMessage || 'Save failed. Please try again.', 3000)
    }
  }

  const COMMAND_HANDLERS = {
    'Menu': handleMenu,
    'Save': handleSave
  }

  const handleAction = async (command) => {
    playSFX('click')

    try {
      const handler = COMMAND_HANDLERS[command.name]
      if (handler) {
        await handler()
      } else {
        // Default behavior for other commands
        setTimedMessage(`${command.name}...`, 1500)
      }
    } catch (err) {
      console.error('Error executing command:', err)
      setTimedMessage('Command failed.', 2000)
    }
  }

  return (
    <BaseDialog
      title="⚡ COMMANDS"
      onClose={onClose}
      variant="warning"
      maxWidth="600px"
      padding="16px"
      zIndex={2000}
    >
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
        paddingTop: actionMessage ? '20px' : '48px' // Added headroom to prevent tooltip clipping
      }}>
        {/* Action Message */}
        {actionMessage && (
          <div style={{
            backgroundColor: 'rgba(255, 170, 0, 0.1)',
            border: '1px solid rgba(255, 170, 0, 0.3)',
            borderRadius: '8px',
            padding: '12px',
            fontSize: '14px',
            fontFamily: 'monospace',
            color: colors.gold,
            textAlign: 'center',
            boxShadow: '0 0 15px rgba(255, 170, 0, 0.2)',
            animation: 'fadeIn 0.3s ease-out'
          }}>
            {actionMessage}
          </div>
        )}

        {/* Commands Container */}
        <div style={{
          backgroundColor: 'rgba(0, 0, 0, 0.4)',
          border: '1px solid rgba(255, 170, 0, 0.2)',
          borderRadius: '12px',
          padding: '16px',
          minHeight: '200px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}>
          {loading ? (
            <div style={{ color: colors.gold, fontStyle: 'italic', textAlign: 'center', padding: '40px' }}>
              Communicating with world spirits...
            </div>
          ) : error ? (
            <div style={{ color: colors.danger, textAlign: 'center', padding: '40px' }}>
              ⚠️ {error}
            </div>
          ) : commands.length === 0 ? (
            <div style={{ color: colors.text.muted, fontStyle: 'italic', textAlign: 'center', padding: '40px' }}>
              No commands currently available.
            </div>
          ) : (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
              gap: '10px'
            }}>
              {commands
                .filter(cmd => cmd.name !== 'Search' && !isInertDebugCommand(cmd))
                .map((command, idx) => {
                const isHovered = hoveredCommand === idx

                return (
                  <div key={command.name} style={{ position: 'relative' }}>
                    <button
                      onClick={() => handleAction(command)}
                      onMouseEnter={() => setHoveredCommand(idx)}
                      onMouseLeave={() => setHoveredCommand(null)}
                      style={{
                        width: '100%',
                        padding: '12px 8px',
                        backgroundColor: isHovered ? 'rgba(255, 170, 0, 0.1)' : 'transparent',
                        border: `1.5px solid ${isHovered ? colors.primary : colors.secondary}`,
                        borderRadius: '8px',
                        color: isHovered ? colors.primary : colors.gold,
                        fontFamily: 'monospace',
                        fontSize: '13px',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        textTransform: 'uppercase',
                        boxShadow: isHovered ? `0 0 10px ${colors.primary}44` : 'none'
                      }}
                    >
                      {command.name}
                    </button>

                    {/* Tooltip */}
                    {isHovered && (
                      <div style={{
                        position: 'absolute',
                        bottom: 'calc(100% + 10px)',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        width: '200px',
                        backgroundColor: 'rgba(0, 0, 0, 0.95)',
                        border: `1px solid ${colors.primary}`,
                        borderRadius: '6px',
                        padding: '10px',
                        fontSize: '11px',
                        color: '#fff',
                        zIndex: 3000,
                        textAlign: 'center',
                        boxShadow: `0 0 15px ${colors.primary}66`,
                        pointerEvents: 'none'
                      }}>
                        {COMMAND_TOOLTIPS[command.name] || 'General interaction command.'}
                        {/* Arrow */}
                        <div style={{
                          position: 'absolute',
                          top: '100%',
                          left: '50%',
                          transform: 'translateX(-50%)',
                          borderLeft: '6px solid transparent',
                          borderRight: '6px solid transparent',
                          borderTop: `6px solid ${colors.primary}`
                        }} />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div style={{
          fontSize: '10px',
          color: colors.text.muted,
          textAlign: 'center',
          fontStyle: 'italic',
          padding: '4px'
        }}>
          {isDebugMode() ? "[DEBUG MODE ACTIVE]" : "Available Commands"}
        </div>
      </div>
    </BaseDialog>
  )
}
