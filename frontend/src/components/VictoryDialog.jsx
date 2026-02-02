import { useMemo, useState } from 'react'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import { colors, spacing } from '../styles/theme'

/**
 * VictoryDialog - Shown after combat victory
 * Handles EXP display, loot, and attribute point allocation
 */
export default function VictoryDialog({ endState, onClose, onAllocatePoints }) {
  const [selectedAttr, setSelectedAttr] = useState('strength_base')
  const [amount, setAmount] = useState('1')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)

  const remainingPoints = Number(endState?.attribute_points_available || 0)

  const attrOptions = useMemo(() => {
    return [
      { key: 'strength_base', label: 'Strength', value: endState?.attributes?.strength_base },
      { key: 'finesse_base', label: 'Finesse', value: endState?.attributes?.finesse_base },
      { key: 'speed_base', label: 'Speed', value: endState?.attributes?.speed_base },
      { key: 'endurance_base', label: 'Endurance', value: endState?.attributes?.endurance_base },
      { key: 'charisma_base', label: 'Charisma', value: endState?.attributes?.charisma_base },
      { key: 'intelligence_base', label: 'Intelligence', value: endState?.attributes?.intelligence_base },
    ]
  }, [endState])

  const expEntries = useMemo(() => {
    const exp = endState?.exp_gained || {}
    return Object.keys(exp)
      .sort((a, b) => a.localeCompare(b))
      .map((k) => ({ category: k, amount: exp[k] }))
  }, [endState])

  const drops = useMemo(() => endState?.items_dropped || [], [endState])
  const levelUps = useMemo(() => endState?.level_ups || [], [endState])

  const canClose = remainingPoints <= 0

  const handleAllocate = async () => {
    setError('')

    const amt = parseInt(amount, 10)
    if (Number.isNaN(amt) || amt <= 0) {
      setError('Enter a valid point amount.')
      return
    }
    if (amt > remainingPoints) {
      setError('Not enough points available.')
      return
    }

    try {
      setIsSubmitting(true)
      const result = await onAllocatePoints(selectedAttr, amt)

      // Check for backend success (some APIs might return result directly or result.data)
      // Based on GamePage.jsx, it returns result.data which should have .success
      if (result && result.success) {
        // Success - reset amount to 1 and the parent will refresh endState
        setAmount('1')
        setError('')
      } else {
        setError(result?.error || 'Failed to allocate points.')
      }
    } catch (e) {
      // Handle axios error specifically if available
      const apiError = e.response?.data?.error || e.message
      setError(apiError || 'Failed to allocate points.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Minimized View (Bottom Bar)
  if (isMinimized) {
    return (
      <div style={{
        position: 'fixed',
        bottom: 0,
        left: '50%',
        transform: 'translateX(-50%)',
        width: '100%',
        maxWidth: '800px',
        backgroundColor: 'rgba(5, 15, 5, 0.95)',
        border: `2px solid ${colors.primary}`,
        borderBottom: 'none',
        borderRadius: '12px 12px 0 0',
        padding: '12px 24px',
        zIndex: 2500,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: `0 -4px 30px ${colors.primary}44`,
        animation: 'slideUp 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ color: colors.primary, fontWeight: 'bold', fontSize: '18px', fontFamily: 'monospace', textShadow: `0 0 10px ${colors.primary}88` }}>
            ⚔️ VICTORY!
          </div>
          {remainingPoints > 0 && (
            <div style={{ color: colors.secondary, fontFamily: 'monospace', fontSize: '14px', animation: 'pulse 2s infinite' }}>
              ⚠️ {remainingPoints} point{remainingPoints !== 1 ? 's' : ''} to allocate
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <GameButton onClick={() => setIsMinimized(false)} variant="primary">
            RESTORE
          </GameButton>
          {canClose && (
            <GameButton onClick={onClose} variant="secondary">
              CONTINUE
            </GameButton>
          )}
        </div>
        <style>{`
                    @keyframes slideUp { from { transform: translate(-50%, 100%); } to { transform: translate(-50%, 0); } }
                    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
                `}</style>
      </div>
    )
  }

  return (
    <BaseDialog
      title={`✨ ${endState?.message || 'Combat Victory'}`}
      onClose={canClose ? onClose : () => setIsMinimized(true)}
      maxWidth="720px"
      padding="16px"
      zIndex={2500}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {/* Header Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: spacing.sm }}>
          <GameButton onClick={() => setIsMinimized(true)} variant="secondary" style={{ fontSize: '11px', padding: '4px 10px' }}>
            MINIMIZE
          </GameButton>
          <GameButton onClick={onClose} disabled={!canClose} variant={canClose ? 'primary' : 'secondary'} style={{ fontSize: '11px', padding: '4px 10px' }}>
            CLOSE
          </GameButton>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: spacing.md }}>
          {/* EXP & Loot Section */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
            {/* EXP Section */}
            <div style={{
              padding: '12px',
              backgroundColor: colors.bg.panelLight,
              border: `1px solid ${colors.primary}33`,
              borderRadius: '12px'
            }}>
              <div style={{ color: colors.primary, fontWeight: 'bold', fontSize: '13px', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                📈 Experience Gained
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {expEntries.length > 0 ? expEntries.map((e) => (
                  <div key={e.category} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'monospace' }}>
                    <span style={{ color: colors.text.muted, fontSize: '12px' }}>{e.category}</span>
                    <span style={{ color: colors.primary, fontWeight: 'bold', fontSize: '12px' }}>+{e.amount}</span>
                  </div>
                )) : <div style={{ color: colors.text.muted, fontStyle: 'italic', fontSize: '12px' }}>None</div>}
              </div>
            </div>

            {/* Loot Section */}
            <div style={{
              padding: '12px',
              backgroundColor: 'rgba(255, 170, 0, 0.05)',
              border: `1px solid ${colors.secondary}33`,
              borderRadius: '12px'
            }}>
              <div style={{ color: colors.secondary, fontWeight: 'bold', fontSize: '13px', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                🎁 Loot Collected
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {drops.length > 0 ? drops.map((d, idx) => (
                  <div key={`${d.name}-${idx}`} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'monospace' }}>
                    <span style={{ color: colors.text.muted, fontSize: '12px' }}>{d.name}</span>
                    <span style={{ color: colors.secondary, fontWeight: 'bold', fontSize: '12px' }}>x{d.quantity}</span>
                  </div>
                )) : <div style={{ color: colors.text.muted, fontStyle: 'italic', fontSize: '12px' }}>None</div>}
              </div>
            </div>
          </div>

          {/* Level Up & Attributes Section */}
          <div style={{
            padding: '12px',
            backgroundColor: 'rgba(0, 204, 255, 0.05)',
            border: `1px solid ${colors.text.highlight}33`,
            borderRadius: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ color: colors.text.highlight, fontWeight: 'bold', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '1px' }}>
              ⭐ Level Ups & Growth
            </div>

            {levelUps.map((lu, idx) => (
              <div key={idx} style={{
                padding: '10px',
                backgroundColor: 'rgba(0,0,0,0.3)',
                borderRadius: '8px',
                border: `1px solid ${colors.text.highlight}11`,
                textAlign: 'center'
              }}>
                <div style={{ color: '#fff', fontSize: '15px', fontWeight: 'bold' }}>
                  LEVEL {lu.old_level} → <span style={{ color: colors.primary }}>{lu.new_level}</span>
                </div>
                <div style={{ color: colors.text.muted, fontSize: '12px' }}>+{lu.points_awarded} Points awarded</div>
              </div>
            ))}

            <div style={{ marginTop: '2px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span style={{ color: colors.text.muted, fontSize: '11px' }}>EXP to Next Level:</span>
                <span style={{ color: colors.text.highlight, fontSize: '12px', fontWeight: 'bold', fontFamily: 'monospace' }}>{endState?.exp_to_next_level || 0}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ color: colors.text.muted, fontSize: '12px' }}>Available Points:</span>
                <span style={{ color: colors.secondary, fontSize: '18px', fontWeight: 'bold', fontFamily: 'monospace' }}>{remainingPoints}</span>
              </div>

              {remainingPoints > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <select
                      value={selectedAttr}
                      onChange={(e) => setSelectedAttr(e.target.value)}
                      style={{
                        flex: 1,
                        padding: '10px',
                        backgroundColor: '#1a1a1a',
                        color: colors.text.highlight,
                        border: `1px solid ${colors.text.highlight}55`,
                        borderRadius: '8px',
                        fontFamily: 'monospace',
                        fontSize: '13px',
                        outline: 'none',
                      }}
                    >
                      {attrOptions.map((o) => (
                        <option key={o.key} value={o.key}>
                          {o.label}{typeof o.value === 'number' ? ` (${o.value})` : ''}
                        </option>
                      ))}
                    </select>

                    <input
                      type="number"
                      min="1"
                      max={Math.max(1, remainingPoints)}
                      value={amount}
                      onChange={(e) => {
                        const val = e.target.value;
                        setAmount(val);
                        // Clear error if they fix the amount
                        if (parseInt(val, 10) <= remainingPoints) {
                          setError('');
                        }
                      }}
                      style={{
                        width: '70px',
                        padding: '10px',
                        backgroundColor: '#1a1a1a',
                        color: colors.text.highlight,
                        border: `1px solid ${colors.text.highlight}55`,
                        borderRadius: '8px',
                        fontFamily: 'monospace',
                        textAlign: 'center',
                        outline: 'none',
                      }}
                    />
                  </div>

                  <GameButton
                    onClick={handleAllocate}
                    disabled={isSubmitting || remainingPoints <= 0}
                    variant={remainingPoints > 0 ? 'primary' : 'secondary'}
                    style={{ width: '100%', padding: '10px', fontSize: '12px' }}
                  >
                    {isSubmitting ? 'ALLOCATING...' : 'ALLOCATE POINTS'}
                  </GameButton>
                </div>
              )}

              {error && (
                <div style={{ marginTop: '12px', color: colors.danger, fontSize: '12px', fontFamily: 'monospace', textAlign: 'center' }}>
                  ⚠️ {error}
                </div>
              )}

              {!canClose && (
                <div style={{ marginTop: '12px', color: colors.text.muted, fontSize: '11px', textAlign: 'center', fontStyle: 'italic' }}>
                  Must spend all points to continue expedition.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </BaseDialog>
  )
}
