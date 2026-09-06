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
 * diff tooling. Control characters (the separator included) are stripped
 * from each field before joining, so no field VALUE can forge a boundary
 * either -- the key always holds exactly three separators.
 *
 * Fields: round, type, message, and the animation carrier's `source_id` (''
 * when the entry carries no animation). The source matters because two
 * same-named NPCs acting in the same round emit byte-identical carriers --
 * without the actor in the key they collapsed into one revealed line and one
 * swing. One swing's own per-target carriers share their source, so they
 * still collapse (see the NOTE below).
 *
 * Every consumer must use THIS function rather than an ad-hoc field subset.
 * LeftPanel's pending filter and its append guard once keyed on different
 * field sets, which silently dropped lines matching on message+round but
 * differing in type.
 *
 * NOTE: this key is deliberately NOT unique. The per-target carriers of one
 * multi-target swing are byte-identical on the wire (same round, same type,
 * same "Sweep animation" message, same source), and both callers rely on that: LeftPanel
 * collapses them to one revealed line, while BattlefieldGrid keeps every
 * repeat because each one is a separate landing to animate.
 */
export const LOG_KEY_SEP = '\u001F';

// eslint-disable-next-line no-control-regex -- matching control characters is the point: LOG_KEY_SEP is \u001F, so a control char left in a field could forge a separator and collide two distinct log entries onto one key.
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/g;
const cleanField = (value) => String(value ?? '').replace(CONTROL_CHARS, '');

export const logEntryKey = (entry) =>
  [
    entry?.round ?? '',
    entry?.type ?? '',
    entry?.message ?? '',
    entry?.animation?.source_id ?? '',
  ].map(cleanField).join(LOG_KEY_SEP);

/**
 * How many *distinct* entries a combat log holds.
 *
 * The raw `log.length` and the number of lines a reader actually sees are
 * different quantities, because this key is deliberately not unique: the
 * per-target carriers of one swing are byte-identical and are emitted with
 * `allow_duplicate=True`, so a four-target sweep adds four raw entries and
 * one revealed line.
 *
 * Anything comparing "how much log is there" against LeftPanel's revealed
 * count must compare like with like. Comparing the raw length instead meant
 * the gate could never close after any multi-target resolution -- which held
 * the victory/defeat dialog shut for the rest of the session.
 */
export const distinctLogCount = (log) =>
  new Set((log || []).map(logEntryKey)).size;
