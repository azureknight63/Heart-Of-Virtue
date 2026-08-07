import { useCallback, useMemo, useState } from 'react'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import GameText from './GameText'
import AttributePointAllocator from './AttributePointAllocator'
import { useAttributeAllocation } from '../hooks/useAttributeAllocation'
import { colors, spacing, shadows } from '../styles/theme'

/**
 * VictoryDialog - Shown after combat victory
 * Handles EXP display, loot, and attribute point allocation
 */
export default function VictoryDialog({ endState, onClose, onAllocatePoints, onContinueToLoot }) {
  const [isMinimized, setIsMinimized] = useState(false)

  const remainingPoints = Number(endState?.attribute_points_available || 0)

  const expEntries = useMemo(() => {
    const exp = endState?.exp_gained || {}
    return Object.keys(exp)
      .sort((a, b) => a.localeCompare(b))
      .map((k) => ({ category: k, amount: exp[k] }))
  }, [endState])

  const drops = useMemo(() => endState?.items_dropped || [], [endState])
  const levelUps = useMemo(() => endState?.level_ups || [], [endState])
  const hasLoot = drops.length > 0

  const canClose = remainingPoints <= 0

  const handleAdvance = useCallback(() => {
    if (hasLoot && onContinueToLoot) onContinueToLoot()
    else onClose()
  }, [hasLoot, onContinueToLoot, onClose])

  // Once the last point is spent, advance straight to the loot phase (or close
  // when there is nothing to collect) rather than leaving an empty allocator up.
  const handleAllocated = useCallback((result) => {
    if ((result.remaining_points ?? 1) === 0) {
      handleAdvance()
      return true
    }
    return false
  }, [handleAdvance])

  const allocation = useAttributeAllocation({
    source: endState?.attributes,
    remainingPoints,
    onAllocatePoints,
    levelUpCount: levelUps.length,
    onAllocated: handleAllocated,
  })

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
          <GameButton onClick={() => setIsMinimized(false)} variant="primary" title="Restore dialog">
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
      // BaseDialog fires onClose from both the ✕ button and the backdrop click.
      // Routing those through handleAdvance (rather than the raw onClose) keeps
      // them loot-aware — otherwise dismissing the dialog skips the loot phase
      // entirely and the drops become unrecoverable.
      onClose={canClose ? handleAdvance : () => setIsMinimized(true)}
      maxWidth="720px"
      padding="16px"
      zIndex={2500}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {/* Header Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: spacing.sm }}>
          <GameButton onClick={() => setIsMinimized(true)} variant="secondary" style={{ fontSize: '11px', padding: '4px 10px' }} title="Minimize dialog">
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
            padding: spacing.md,
            backgroundColor: colors.bg.panelDeep,
            border: `1px solid ${colors.border.light}`,
            borderRadius: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.md
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
                  <AttributePointAllocator
                    attrOptions={allocation.attrOptions}
                    selectedAttr={allocation.selectedAttr}
                    onSelectAttr={allocation.setSelectedAttr}
                    amount={allocation.amount}
                    onAmountChange={allocation.handleAmountChange}
                    onAllocate={allocation.handleAllocate}
                    onRandomize={allocation.handleRandomize}
                    remainingPoints={remainingPoints}
                    isSubmitting={allocation.isSubmitting}
                    error={allocation.error}
                  />
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
