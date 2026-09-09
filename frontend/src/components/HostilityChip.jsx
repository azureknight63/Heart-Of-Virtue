import { spacing } from '../styles/theme'

/**
 * The friend-or-foe badge, in one place.
 *
 * `combatEntities.js` centralised the hostility VOCABULARY (see
 * `HOSTILITY_TOKENS` there for why this state gets a glyph and a word, not
 * just a colour) but the presentation was copy-pasted into the room panel and
 * the combat target picker, differing only in padding, font size and letter
 * spacing — which is the half that drifts.
 *
 * @param {object} token one of HOSTILITY_TOKENS
 * @param {'inline'|'block'} variant `inline` sits after a name in a sentence;
 *   `block` stands alone in a target card.
 */
export default function HostilityChip({ token, variant = 'inline' }) {
  const inline = variant === 'inline'
  return (
    <span
      data-hostility={token.key}
      style={{
        ...(inline
          ? { marginLeft: spacing.xs, padding: '0 4px', fontSize: '11px', letterSpacing: '0.05em' }
          : { alignSelf: 'flex-start', padding: '2px 6px', fontSize: '10px', letterSpacing: '0.08em' }),
        borderRadius: inline ? '3px' : '4px',
        border: `1px solid ${token.color}`,
        backgroundColor: token.tint,
        color: token.color,
        // The generic stack, NOT fonts.main: the chip sits inside italic
        // serif prose in RoomContents, and a Courier-first stack there reads
        // as a different typeface rather than as a badge. Left alone
        // deliberately -- do not let a fonts.main sweep "fix" it.
        fontFamily: 'monospace',
        fontStyle: 'normal',
        fontWeight: 'bold',
        whiteSpace: 'nowrap',
      }}
    >
      {token.glyph} {token.label}
    </span>
  )
}
