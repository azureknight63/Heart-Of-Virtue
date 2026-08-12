import GameButton from './GameButton'
import { colors, fonts } from '../styles/theme'

const fieldStyle = {
  padding: '10px',
  backgroundColor: colors.bg.main,
  color: colors.text.highlight,
  border: `1px solid ${colors.border.main}`,
  borderRadius: '8px',
  fontFamily: fonts.main,
  outline: 'none',
}

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

  return (
    <>
      <div style={{ display: 'flex', gap: '8px' }}>
        <select
          value={selectedAttr}
          onChange={(e) => onSelectAttr(e.target.value)}
          style={{ ...fieldStyle, flex: 1, fontSize: '13px' }}
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
          onChange={(e) => onAmountChange(e.target.value)}
          style={{ ...fieldStyle, width: '70px', textAlign: 'center' }}
        />
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
