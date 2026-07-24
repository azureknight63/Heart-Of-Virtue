/**
 * Combat stream sequence classification (issue #436).
 *
 * Every combat:* event carries a monotonic `seq`. Classify an incoming seq
 * against the last one processed so the consumer can dedupe and detect a gap
 * (a missed event) that warrants a resync.
 */
export function classifySeq(lastSeq, seq) {
  if (lastSeq == null) return 'next';
  if (seq <= lastSeq) return 'duplicate';
  if (seq > lastSeq + 1) return 'gap';
  return 'next';
}
