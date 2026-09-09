/**
 * A visually-hidden polite live region — the screen-reader channel for content
 * that appears without focus moving.
 *
 * Shared because CombatLog and NpcChatPanel had grown byte-identical copies of
 * the same 11-property hidden style block and the same "announce the newest
 * one" shape, and they had already drifted: only one of them carried the
 * re-announce key below.
 *
 * `seq` is load-bearing. A polite region announces a DOM CHANGE, not a value —
 * re-feeding it an identical string writes the same text node, mutates
 * nothing, and says nothing. Combat repeats itself constantly ("Jean misses"
 * twice running) and so does dialogue, so the child is keyed on a caller
 * supplied sequence number: a new key replaces the node, which is a childList
 * addition the region does pick up.
 */
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

export default function LiveAnnouncer({ text, seq, testId }) {
  return (
    <div data-testid={testId} aria-live="polite" aria-atomic="true" style={VISUALLY_HIDDEN}>
      {text ? <span key={seq} data-seq={seq}>{text}</span> : null}
    </div>
  )
}
