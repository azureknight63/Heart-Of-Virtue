// Visually hidden, and specifically NOT `display: none`: a display:none
// subtree is removed from the accessibility tree entirely, so a live region
// inside one never announces anything. Clipping it leaves the region present
// and silent to sighted players, which is the whole trick.
const VISUALLY_HIDDEN = {
  position: 'absolute',
  width: '1px',
  height: '1px',
  margin: '-1px',
  padding: 0,
  border: 0,
  overflow: 'hidden',
  clip: 'rect(0 0 0 0)',
  clipPath: 'inset(50%)',
  whiteSpace: 'nowrap',
}

/**
 * A visually-hidden polite live region — the screen-reader channel for content
 * that appears without focus moving.
 *
 * CombatLog and NpcChatPanel both announce through this one region, so the
 * hidden-style block and the "announce the newest one" shape exist once.
 *
 * `seq` is load-bearing. A polite region announces a DOM CHANGE, not a value —
 * re-feeding it an identical string writes the same text node, mutates
 * nothing, and says nothing. Combat repeats itself constantly ("Jean misses"
 * twice running) and so does dialogue, so the child is keyed on a caller
 * supplied sequence number: a new key replaces the node, which is a childList
 * addition the region does pick up.
 *
 * @param {string} text the line to announce; falsy renders no child at all
 * @param {number} seq a counter the caller bumps per new line — see above
 * @param {string} testId `data-testid` for the region
 */
export default function LiveAnnouncer({ text, seq, testId }) {
  return (
    <div data-testid={testId} aria-live="polite" aria-atomic="true" style={VISUALLY_HIDDEN}>
      {text ? <span key={seq} data-seq={seq}>{text}</span> : null}
    </div>
  )
}
