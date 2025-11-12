import { useAuth } from '../hooks/useApi'

export default function AccountDialog({ player, onClose }) {
  const { logout } = useAuth()
  const username = localStorage.getItem('username') || 'Unknown'

  const handleLogout = async () => {
    await logout()
    onClose()
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: '#1a1a2e',
          border: '3px solid #00ff88',
          borderRadius: '8px',
          padding: '24px',
          maxWidth: '400px',
          width: '90%',
          boxShadow: '0 0 20px #00ff88',
          fontFamily: 'monospace',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Title */}
        <div
          style={{
            fontSize: '20px',
            fontWeight: 'bold',
            color: '#00ff88',
            marginBottom: '20px',
            textAlign: 'center',
            borderBottom: '2px solid #00ff88',
            paddingBottom: '10px',
          }}
        >
          ⚔️ Account Details
        </div>

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
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              backgroundColor: 'transparent',
              color: '#00ccff',
              border: '2px solid #00ccff',
              borderRadius: '4px',
              cursor: 'pointer',
              fontFamily: 'monospace',
              fontSize: '14px',
              fontWeight: 'bold',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = 'rgba(0, 204, 255, 0.2)'
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = 'transparent'
            }}
          >
            Close
          </button>
          <button
            onClick={handleLogout}
            style={{
              padding: '8px 16px',
              backgroundColor: '#cc0000',
              color: '#ffff00',
              border: '2px solid #ff0000',
              borderRadius: '4px',
              cursor: 'pointer',
              fontFamily: 'monospace',
              fontSize: '14px',
              fontWeight: 'bold',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = '#ff0000'
              e.target.style.boxShadow = '0 0 10px #ff0000'
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = '#cc0000'
              e.target.style.boxShadow = 'none'
            }}
          >
            Log Out
          </button>
        </div>
      </div>
    </div>
  )
}
