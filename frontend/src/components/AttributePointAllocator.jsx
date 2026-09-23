import { useId } from 'react'
import GameButton from './GameButton'
import { accessibility, colors, fonts } from '../styles/theme'

// 16px keeps iOS from zooming the page on focus; the 44px floor is
// unconditional, matching the GameButtons beneath these fields.
const fieldStyle = {
  padding: '10px',
  minHeight: accessibility.touchTarget,
  fontSize: '16px',
  backgroundColor: colors.bg.main,
  color: colors.text.highlight,
  border: `1px solid ${colors.border.main}`,
  borderRadius: '8px',
  fontFamily: fonts.main,
  outline: 'none',
  touchAction: 'manipulation',
}

const labelStyle = {
  color: colors.text.muted,
  fontSize: '11px',
  fontFamily: fonts.main,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
}

const fieldColumnStyle = { display: 'flex', flexDirection: 'column', gap: '4px' }

/**
 * AttributePointAllocator - the attribute picker, amount input, and
 * allocate/randomize controls shared by LevelUpModal and VictoryDialog.
 *
 * Presentational only; drive it with the `useAttributeAllocation` hook.
 */
export default function AttributePointAllocator({
  attrOptions,
  selectedAttr,
  onSelectAttr,
  amount,
  onAmountChange,
  onAllocate,
  onRandomize,
  remainingPoints,
  isSubmitting,
  error,
  allocateLabel = 'ALLOCATE POINTS',
}) {
  const disabled = isSubmitting || remainingPoints <= 0
  // Per-instance ids: a fixed id would point every label at the first
  // allocator on the page and leave the rest unnamed.
  const attrId = useId()
  const amountId = useId()

  return (
    <>
      <div style={{ display: 'flex', gap: '8px' }}>
        <div style={{ ...fieldColumnStyle, flex: 1, minWidth: 0 }}>
          <label htmlFor={attrId} style={labelStyle}>Attribute</label>
          <select
            id={attrId}
            value={selectedAttr}
            onChange={(e) => onSelectAttr(e.target.value)}
            style={fieldStyle}
          >
            {attrOptions.map((o) => (
              <option key={o.key} value={o.key}>
                {o.label}{typeof o.value === 'number' ? ` (${o.value})` : ''}
              </option>
            ))}
          </select>
        </div>

        <div style={fieldColumnStyle}>
          <label htmlFor={amountId} style={labelStyle}>Points</label>
          <input
            id={amountId}
            type="number"
            min="1"
            max={Math.max(1, remainingPoints)}
            value={amount}
            onChange={(e) => onAmountChange(e.target.value)}
            style={{ ...fieldStyle, width: '70px', textAlign: 'center' }}
          />
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px' }}>
        <GameButton
          onClick={onAllocate}
          disabled={disabled}
          variant="primary"
          style={{ flex: 2, padding: '10px', fontSize: '12px' }}
        >
          {isSubmitting ? 'ALLOCATING...' : allocateLabel}
        </GameButton>

        <GameButton
          onClick={onRandomize}
          disabled={disabled}
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
    </>
  )
}
