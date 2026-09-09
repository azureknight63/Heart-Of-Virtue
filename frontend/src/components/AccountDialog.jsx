import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useApi'
import { colors } from '../styles/theme'
import { USERNAME_KEY } from '../utils/session'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'

export default function AccountDialog({ player, onClose }) {
  const navigate = useNavigate()
  const { logout } = useAuth()
  // Read by its named key, like every other consumer. The literal is the
  // session module's to own -- a read that spells it inline is one more place
  // to update if the key ever changes, and the one that gets missed.
  const username = localStorage.getItem(USERNAME_KEY) || 'Unknown'
  // #540 item 10: LOG OUT used to fire on a single click, with no
  // confirmation, next to an outline CLOSE — a destructive-ish action (it
  // ends the session) deserves a guard the way "Drop Item?" and other
  // confirm-before-acting flows in this app already get.
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)

  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      await logout()
      onClose()
    } finally {
      setLoggingOut(false)
    }
  }

  const handleGoToMenu = () => {
    navigate('/menu')
    onClose()
  }

  return (
    <BaseDialog title="⚔️ Account Details" onClose={onClose}>
      {/* Content */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ marginBottom: '15px' }}>
          <div style={{ color: colors.accent, fontSize: '12px', marginBottom: '5px' }}>
            USERNAME
          </div>
          <div
            style={{
              color: colors.primary,
              fontSize: '16px',
              backgroundColor: colors.bg.positive,
              padding: '10px',
              borderLeft: `3px solid ${colors.primary}`,
              borderRadius: '4px',
            }}
          >
            {username}
          </div>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <div style={{ color: colors.accent, fontSize: '12px', marginBottom: '5px' }}>
            ACCOUNT STATUS
          </div>
          <div
            style={{
              color: colors.secondary,
              fontSize: '14px',
              backgroundColor: colors.bg.highlight,
              padding: '10px',
              borderLeft: `3px solid ${colors.secondary}`,
              borderRadius: '4px',
            }}
          >
            {player?.premium ? '👑 Premium' : '⭐ Standard'}
          </div>
        </div>
      </div>

      {/* Buttons */}
      <div
        style={{
          display: 'flex',
          gap: '10px',
          justifyContent: 'flex-end',
          flexWrap: 'wrap'
        }}
      >
        <GameButton onClick={handleGoToMenu} variant="secondary">
          Main Menu
        </GameButton>
        <GameButton onClick={onClose} variant="secondary">
          CLOSE
        </GameButton>
        {/* An outline danger button, not a solid fill — it should read as
            "this is the destructive one", not "this is the most important
            button on the panel", which a solid-red fill next to an outline
            CLOSE did. */}
        <GameButton
          onClick={() => setShowLogoutConfirm(true)}
          variant="danger"
          style={{ backgroundColor: 'transparent', color: colors.danger }}
        >
          Log Out
        </GameButton>
      </div>

      {showLogoutConfirm && (
        <div
          role="dialog"
          aria-label="Confirm log out"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1600,
          }}
        >
          <div
            style={{
              backgroundColor: 'rgba(40, 0, 0, 0.95)',
              border: `2px solid ${colors.danger}`,
              borderRadius: '8px',
              padding: '24px',
              maxWidth: '380px',
              width: '90%',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              color: colors.text.bright,
              fontFamily: 'monospace',
            }}
          >
            <div
              style={{
                fontSize: '18px',
                fontWeight: 'bold',
                color: colors.danger,
                borderBottom: `1px solid ${colors.danger}`,
                paddingBottom: '12px',
              }}
            >
              Log Out?
            </div>
            <div style={{ fontSize: '14px', lineHeight: '1.5' }}>
              You'll need to sign in again to continue as <strong>{username}</strong>.
            </div>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <GameButton
                onClick={() => setShowLogoutConfirm(false)}
                variant="secondary"
                disabled={loggingOut}
              >
                Cancel
              </GameButton>
              <GameButton onClick={handleLogout} variant="danger" disabled={loggingOut}>
                {loggingOut ? 'Logging Out...' : 'Yes, Log Out'}
              </GameButton>
            </div>
          </div>
        </div>
      )}
    </BaseDialog>
  )
}
