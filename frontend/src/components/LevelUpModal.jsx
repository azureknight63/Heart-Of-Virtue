import { useMemo } from 'react'
import BaseDialog from './BaseDialog'
import GameText from './GameText'
import AttributePointAllocator from './AttributePointAllocator'
import { useAttributeAllocation } from '../hooks/useAttributeAllocation'
import { colors, spacing } from '../styles/theme'

/**
 * LevelUpModal - Blocking modal for level-ups that occur outside of combat.
 * Shown whenever player.pending_attribute_points > 0 and no VictoryDialog is active.
 * Closes automatically once all points are spent.
 */
export default function LevelUpModal({ player, onAllocatePoints }) {
  const remainingPoints = Number(player?.pending_attribute_points || 0)
  const levelUps = useMemo(() => player?.pending_level_ups || [], [player])

  const allocation = useAttributeAllocation({
    source: player,
    remainingPoints,
    onAllocatePoints,
    levelUpCount: levelUps.length,
  })

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

          <div style={{ color: colors.text.muted, fontSize: '11px', textAlign: 'center', fontStyle: 'italic' }}>
            Must spend all points to continue.
          </div>
        </div>
      </div>
    </BaseDialog>
  )
}
