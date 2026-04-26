import { useMemo, useState, useEffect } from 'react'
import { useAudio } from '../context/AudioContext'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import GameText from './GameText'
import { colors, spacing, fonts, shadows } from '../styles/theme'

/**
 * VictoryDialog - Shown after combat victory
 * Handles EXP display, loot, and attribute point allocation
 */
export default function VictoryDialog({ endState, onClose, onAllocatePoints, onContinueToLoot }) {
  const [selectedAttr, setSelectedAttr] = useState('strength_base')
  const [amount, setAmount] = useState('1')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)

  const { playSFX } = useAudio()

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
  const hasLoot = drops.length > 0

  useEffect(() => {
    if (levelUps.length > 0) playSFX('level_up')
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const canClose = remainingPoints <= 0

  const handleAdvance = () => {
    if (hasLoot && onContinueToLoot) onContinueToLoot()
    else onClose()
  }

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
        // If all points are now spent, advance to loot phase (or close if no loot).
        if ((result.remaining_points ?? 1) === 0) {
          setIsSubmitting(false)
          if (hasLoot && onContinueToLoot) {
            onContinueToLoot()
          } else {
            onClose()
          }
          return
        }
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
        backgroundColor: colors.bg.panelDeep,
        border: `2px solid ${colors.secondary}`,
        borderBottom: 'none',
        borderRadius: '12px 12px 0 0',
        padding: `${spacing.md} ${spacing.lg}`,
        zIndex: 2500,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: `0 -4px 30px ${colors.secondary}44`,
        animation: 'slideUp 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.lg }}>
          <GameText variant="secondary" size="lg" weight="bold" style={{ textShadow: `0 0 10px ${colors.secondary}88` }}>
            ⚔️ VICTORY!
          </GameText>
          {remainingPoints > 0 && (
            <GameText variant="primary" size="sm" style={{ animation: 'victory-pulse 2s infinite' }}>
              ⚠️ {remainingPoints} point{remainingPoints !== 1 ? 's' : ''} to allocate
            </GameText>
          )}
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <GameButton onClick={() => setIsMinimized(false)} variant="primary">
            RESTORE
          </GameButton>
          {canClose && (
            <GameButton onClick={handleAdvance} variant="secondary">
              {hasLoot ? 'COLLECT LOOT →' : 'CONTINUE'}
            </GameButton>
          )}
        </div>
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
          <GameButton
            onClick={handleAdvance}
            disabled={!canClose}
            variant={canClose ? 'primary' : 'secondary'}
            style={{ fontSize: '11px', padding: '4px 10px' }}
          >
            {hasLoot ? 'COLLECT LOOT →' : 'CLOSE'}
          </GameButton>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: spacing.md }}>
          {/* EXP & Loot Section */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
            {/* EXP Section */}
            <div style={{
              padding: spacing.md,
              backgroundColor: colors.bg.panelDeep,
              border: `1px solid ${colors.border.light}`,
              borderRadius: '12px'
            }}>
              <GameText variant="primary" size="xs" weight="bold" style={{ marginBottom: spacing.sm, textTransform: 'uppercase', letterSpacing: '1px' }}>
                📈 Experience Gained
              </GameText>
              <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
                {expEntries.length > 0 ? expEntries.map((e) => (
                  <div key={e.category} style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <GameText variant="muted" size="xs">{e.category}</GameText>
                    <GameText variant="primary" size="xs" weight="bold">+{e.amount}</GameText>
                  </div>
                )) : <GameText variant="muted" size="xs" style={{ fontStyle: 'italic' }}>None</GameText>}
              </div>
            </div>

            {/* Loot is handled in the separate LootDialog (Phase 2) */}
            {hasLoot && (
              <div style={{ padding: spacing.sm, background: `${colors.secondary}11`, border: `1px solid ${colors.secondary}44`, borderRadius: '8px' }}>
                <GameText variant="secondary" size="xs" style={{ fontStyle: 'italic' }}>
                  🎁 {drops.length} item{drops.length !== 1 ? 's' : ''} available to collect — next step
                </GameText>
              </div>
            )}
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
            <GameText variant="accent" size="xs" weight="bold" style={{ textTransform: 'uppercase', letterSpacing: '1px' }}>
              ⭐ Level Ups & Growth
            </GameText>

            {levelUps.map((lu, idx) => (
              <div key={idx} style={{
                padding: spacing.sm,
                backgroundColor: colors.bg.main,
                borderRadius: '8px',
                border: `1px solid ${colors.border.light}`,
                textAlign: 'center'
              }}>
                <GameText variant="success" size="md" weight="bold">
                  LEVEL {lu.old_level} → <GameText variant="primary">{lu.new_level}</GameText>
                </GameText>
                <GameText variant="muted" size="xs">+{lu.points_awarded} Points awarded</GameText>
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
                        backgroundColor: colors.bg.main,
                        color: colors.text.highlight,
                        border: `1px solid ${colors.border.main}`,
                        borderRadius: '8px',
                        fontFamily: fonts.main,
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
                        backgroundColor: colors.bg.main,
                        color: colors.text.highlight,
                        border: `1px solid ${colors.border.main}`,
                        borderRadius: '8px',
                        fontFamily: fonts.main,
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
