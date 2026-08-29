/**
 * Identity for one combat-log entry, shared by every consumer of the log.
 *
 * Two components need the same notion of "the same log entry": LeftPanel
 * dedups the revealed text by it, and BattlefieldGrid uses it to tell which
 * animation carriers it has already played. They held byte-identical private
 * copies -- the mirrored-constant drift this codebase keeps getting caught by.
 * The two can diverge silently, and the failure (animations leading or
 * trailing the revealed text) reads as a timing bug rather than a definition
 * mismatch.
 *
 * The separator is the ASCII unit separator, which the engine never emits
 * inside a message, so no field value can collide across a boundary. A space
 * would not be safe -- messages are prose and contain spaces. Written as an
 * escape rather than a literal control character so it survives editors and
 * diff tooling.
 *
 * Every consumer must use THIS function rather than an ad-hoc field subset.
 * LeftPanel's pending filter and its append guard once keyed on different
 * field sets, which silently dropped lines matching on message+round but
 * differing in type.
 *
 * NOTE: this key is deliberately NOT unique. The per-target carriers of one
 * multi-target swing are byte-identical on the wire (same round, same type,
 * same "Sweep animation" message), and both callers rely on that: LeftPanel
 * collapses them to one revealed line, while BattlefieldGrid keeps every
 * repeat because each one is a separate landing to animate.
 */
export const LOG_KEY_SEP = '\u001F';

export const logEntryKey = (entry) =>
  [entry?.round ?? '', entry?.type ?? '', entry?.message ?? ''].join(LOG_KEY_SEP);
