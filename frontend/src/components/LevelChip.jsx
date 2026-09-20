import { colors, spacing } from '../styles/theme'

/**
 * The combatant level badge, in one place.
 *
 * Modeled on `HostilityChip`'s glyph+word+colour pattern (state is never
 * colour-only) but level has no `HOSTILITY_TOKENS`-style vocabulary to key
 * off — it's just an integer every combatant's wire payload always carries
 * (`CombatantSerializer.serialize_combatant` defaults it to 1, issue #617),
 * so this chip takes the level directly instead of a lookup token.
 *
 * @param {number} level entity.level, straight off the wire.
 * @param {'inline'|'block'} variant `inline` sits after a name in a header;
 *   `block` stands alone in a detail card.
 */
export default function LevelChip({ level, variant = 'inline' }) {
  const inline = variant === 'inline'
  return (
    <span
      data-level={level}
      style={{
        ...(inline
          ? { marginLeft: spacing.xs, padding: '0 4px', fontSize: '11px', letterSpacing: '0.05em' }
          : { alignSelf: 'flex-start', padding: '2px 6px', fontSize: '10px', letterSpacing: '0.08em' }),
        borderRadius: inline ? '3px' : '4px',
        border: `1px solid ${colors.info}`,
        backgroundColor: colors.alpha.info[10],
        color: colors.info,
        // The generic stack, NOT fonts.main — matches HostilityChip, which
        // this badge sits directly beside in both the tooltip and the panel.
        fontFamily: 'monospace',
        fontStyle: 'normal',
        fontWeight: 'bold',
        whiteSpace: 'nowrap',
      }}
    >
      {'✦'} Lv {level}
    </span>
  )
}
