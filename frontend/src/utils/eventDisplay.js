/**
 * Shared "is this triggered event actually worth showing?" predicate.
 *
 * The engine reports every tile event it re-checked in `events_triggered` /
 * `GET /world/events`, including ones whose gate wasn't met -- a dormant
 * event's check_conditions() runs as a plain no-op, leaving it with no
 * narration and no input prompt (see AfterKingSlimeReturn, src/story/ch02.py,
 * and issue #371, which deliberately never self-destructs while dormant so it
 * gets rechecked on every single tile-entry / interact call).
 *
 * Two call sites each grew their own copy of the "did this event actually do
 * anything" check (useEventManager's queue filter, useWorldInteract's
 * background-poll filter) and a THIRD call site (useWorldInteract's
 * interact() `hasPendingEvents` gate) used a bare `.length > 0` instead --
 * "an entry exists" rather than "an entry is displayable". Issue #544: that
 * bare check treated a dormant entry as "an event is pending" and blanked out
 * the real interact message, while the event queue's own (correct) filter
 * dropped the same entry as non-displayable -- so NEITHER the message nor an
 * event dialog rendered. This module is the one place that predicate is
 * spelled out, so the three call sites cannot drift apart again.
 *
 * @param {Object} event - A serialized event entry (events_triggered[] /
 *   GET /world/events response shape).
 * @returns {boolean} True when the event has narration to show or is asking
 *   for input -- i.e. it actually fired, rather than being checked and
 *   found dormant.
 */
export function isDisplayableEvent(event) {
    if (!event) return false
    const hasOutput = Boolean(event.output_text && event.output_text.trim().length > 0)
    const needsInput = Boolean(event.needs_input)
    return hasOutput || needsInput
}

/**
 * Filters a list of triggered events down to the ones worth displaying.
 * Non-array input (e.g. a missing/malformed `events_triggered`) yields `[]`
 * rather than throwing.
 *
 * @param {Array} events
 * @returns {Array}
 */
export function filterDisplayableEvents(events) {
    if (!Array.isArray(events)) return []
    return events.filter(isDisplayableEvent)
}
