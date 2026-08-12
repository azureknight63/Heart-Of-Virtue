import { colors } from '../styles/theme'

const cellStyle = {
  backgroundColor: colors.bg.panelAmber,
  padding: '6px',
  textAlign: 'center',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
}

/**
 * ItemStatGrid - the labelled property cells shown for an item.
 *
 * Drive it with a `stats` array of `{ label, value, color?, show? }`. Entries
 * with `show: false` are omitted, which keeps the conditional properties
 * (subtype, damage, protection, rarity, quantity) declarative at the call site
 * rather than each repeating the cell markup.
 */
export function ItemStatGrid({ stats }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(80px, 1fr))',
      gap: '1px',
      backgroundColor: colors.border.dark,
      padding: '1px',
      borderRadius: '3px',
    }}>
      {stats.filter((s) => s.show !== false).map((s) => (
        <div key={s.label} style={cellStyle}>
          <div style={{ color: colors.secondary, fontWeight: 'bold', fontSize: '13px', marginBottom: '3px' }}>
            {s.label}
          </div>
          <div style={{ color: s.color || colors.text.paleGold, fontSize: '14px' }}>
            {s.value}
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * ItemSection - a titled panel used for the description, effects, requirements
 * and comparison blocks of the item detail view.
 */
export function ItemSection({ title, children, style }) {
  return (
    <div style={{
      backgroundColor: colors.bg.panelAmber,
      border: `1px solid ${colors.border.dark}`,
      borderRadius: '4px',
      padding: '8px 10px',
      ...style,
    }}>
      {title && (
        <div style={{
          color: colors.secondary,
          fontWeight: 'bold',
          fontSize: '13px',
          textTransform: 'uppercase',
          marginBottom: '6px',
        }}>
          {title}
        </div>
      )}
      {children}
    </div>
  )
}

export default ItemStatGrid
