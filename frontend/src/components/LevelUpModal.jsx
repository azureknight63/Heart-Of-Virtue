import React, { useMemo, useState, useEffect } from 'react'
import { useAudio } from '../context/AudioContext'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import GameText from './GameText'
import { colors, spacing, fonts } from '../styles/theme'

/**
 * LevelUpModal - Blocking modal for level-ups that occur outside of combat.
 * Shown whenever player.pending_attribute_points > 0 and no VictoryDialog is active.
 * Closes automatically once all points are spent.
 */
export default function LevelUpModal({ player, onAllocatePoints }) {
  const [selectedAttr, setSelectedAttr] = useState('strength_base')
  const [amount, setAmount] = useState('1')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { playSFX } = useAudio()

  const remainingPoints = Number(player?.pending_attribute_points || 0)
  const levelUps = useMemo(() => player?.pending_level_ups || [], [player])

  const attrOptions = useMemo(() => [
    { key: 'strength_base', label: 'Strength', value: player?.strength_base },
    { key: 'finesse_base', label: 'Finesse', value: player?.finesse_base },
    { key: 'speed_base', label: 'Speed', value: player?.speed_base },
    { key: 'endurance_base', label: 'Endurance', value: player?.endurance_base },
    { key: 'charisma_base', label: 'Charisma', value: player?.charisma_base },
    { key: 'intelligence_base', label: 'Intelligence', value: player?.intelligence_base },
    { key: 'faith_base', label: 'Faith', value: player?.faith_base },
  ], [player])

  const playSFXRef = React.useRef(playSFX)
  useEffect(() => { playSFXRef.current = playSFX }, [playSFX])

  useEffect(() => {
    if (levelUps.length > 0) playSFXRef.current('level_up')
  }, [levelUps.length])

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
      if (result && result.success) {
        setAmount('1')
        setError('')
      } else {
        setError(result?.error || 'Failed to allocate points.')
      }
    } catch (e) {
      setError(e.response?.data?.error || e.message || 'Failed to allocate points.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleRandomize = async () => {
    setError('')
    try {
      setIsSubmitting(true)
      const result = await onAllocatePoints('randomize', remainingPoints)
      if (result && result.success) {
        setAmount('1')
        setError('')
      } else {
        setError(result?.error || 'Failed to randomize points.')
      }
    } catch (e) {
      setError(e.response?.data?.error || e.message || 'Failed to randomize points.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <BaseDialog
      title="⭐ LEVEL UP"
      maxWidth="480px"
      padding="16px"
      zIndex={2600}
      showCloseButton={false}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        {/* Level-up events */}
        {levelUps.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
            {levelUps.map((lu, idx) => (
              <div key={idx} style={{
                padding: spacing.sm,
                backgroundColor: colors.bg.main,
                borderRadius: '8px',
                border: `1px solid ${colors.border.light}`,
                textAlign: 'center',
              }}>
                <GameText variant="success" size="md" weight="bold">
                  LEVEL {lu.old_level} → <GameText variant="primary">{lu.new_level}</GameText>
                </GameText>
                <GameText variant="muted" size="xs">+{lu.points_awarded} attribute points awarded</GameText>
              </div>
            ))}
          </div>
        )}

        {/* Allocation section */}
        <div style={{
          padding: spacing.md,
          backgroundColor: colors.bg.panelDeep,
          border: `1px solid ${colors.border.light}`,
          borderRadius: '12px',
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.md,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <GameText variant="muted" size="sm">Available Points:</GameText>
            <GameText variant="secondary" size="lg" weight="bold" style={{ fontFamily: 'monospace' }}>
              {remainingPoints}
            </GameText>
          </div>

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
                setAmount(e.target.value)
                if (parseInt(e.target.value, 10) <= remainingPoints) setError('')
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

          <div style={{ display: 'flex', gap: '8px' }}>
            <GameButton
              onClick={handleAllocate}
              disabled={isSubmitting || remainingPoints <= 0}
              variant="primary"
              style={{ flex: 2, padding: '10px', fontSize: '12px' }}
            >
              {isSubmitting ? 'ALLOCATING...' : 'ALLOCATE POINTS'}
            </GameButton>
            
            <GameButton
              onClick={handleRandomize}
              disabled={isSubmitting || remainingPoints <= 0}
              variant="secondary"
              style={{ flex: 1, padding: '10px', fontSize: '12px' }}
            >
              RANDOMIZE
            </GameButton>
          </div>

          {error && (
            <div style={{ color: colors.danger, fontSize: '12px', fontFamily: 'monospace', textAlign: 'center' }}>
              ⚠️ {error}
            </div>
          )}

          <div style={{ color: colors.text.muted, fontSize: '11px', textAlign: 'center', fontStyle: 'italic' }}>
            Must spend all points to continue.
          </div>
        </div>
      </div>
    </BaseDialog>
  )
}
