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

  const handleLogout = async () => {
    await logout()
    onClose()
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
          Close
        </GameButton>
        <GameButton onClick={handleLogout} variant="danger">
          Log Out
        </GameButton>
      </div>
    </BaseDialog>
  )
}
