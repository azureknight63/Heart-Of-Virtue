import { useAuth } from '../hooks/useApi'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'

export default function AccountDialog({ player, onClose }) {
  const { logout } = useAuth()
  const username = localStorage.getItem('username') || 'Unknown'

  const handleLogout = async () => {
    await logout()
    onClose()
  }

  return (
    <BaseDialog title="⚔️ Account Details" onClose={onClose}>
      {/* Content */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ marginBottom: '15px' }}>
          <div style={{ color: '#00ccff', fontSize: '12px', marginBottom: '5px' }}>
            USERNAME
          </div>
          <div
            style={{
              color: '#00ff88',
              fontSize: '16px',
              backgroundColor: 'rgba(0, 100, 50, 0.2)',
              padding: '10px',
              borderLeft: '3px solid #00ff88',
              borderRadius: '4px',
            }}
          >
            {username}
          </div>
        </div>

        <div style={{ marginBottom: '15px' }}>
          <div style={{ color: '#00ccff', fontSize: '12px', marginBottom: '5px' }}>
            ACCOUNT STATUS
          </div>
          <div
            style={{
              color: '#ffaa00',
              fontSize: '14px',
              backgroundColor: 'rgba(100, 50, 0, 0.2)',
              padding: '10px',
              borderLeft: '3px solid #ffaa00',
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
        }}
      >
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
