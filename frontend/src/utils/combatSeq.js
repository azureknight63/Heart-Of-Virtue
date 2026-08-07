/**
 * Combat stream sequence classification (issue #436).
 *
 * Every combat:* event carries a monotonic `seq`. Classify an incoming seq
 * against the last one processed so the consumer can dedupe and detect a gap
 * (a missed event) that warrants a resync.
 */
export function classifySeq(lastSeq, seq) {
  // A malformed/absent seq must never be treated as 'next': the consumer would
  // then store it as lastSeq and every later comparison against that garbage
  // silently disables both gap and duplicate detection for the socket's life.
  // 'gap' is the safe direction — it forces a resync instead.
  if (typeof seq !== 'number' || !Number.isFinite(seq)) return 'gap';
  if (lastSeq == null) return 'next';
  if (seq <= lastSeq) return 'duplicate';
  if (seq > lastSeq + 1) return 'gap';
  return 'next';
}
