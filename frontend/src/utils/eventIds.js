/**
 * Event identifiers the client has to spell out — both the ids it mints itself
 * and the engine class names it recognises by string.
 *
 * These live in a plain utils module rather than alongside the hook that uses
 * them because `useEventManager` is mocked wholesale — pages/GamePage.handlers
 * .test.jsx does it today (`vi.mock('../hooks/useEventManager', () => ({
 * useEventManager: vi.fn() }))`), and it is the natural thing for the next
 * suite that wants to drive GamePage's own handlers to do. A constant exported
 * from the hook resolves to `undefined` in any such suite, which silently
 * breaks the consumer under test rather than failing where the mock is
 * declared. Nothing mocks this file. Named rather than counted, because a
 * count here rots every time a suite is added or deleted —
 * `grep -rn "vi.mock(.*useEventManager" src/` answers it exactly.
 */

/**
 * The combat-start confirmation prompt.
 *
 * Load-bearing for EventDialog's soft-lock guard: it is the one event id where
 * a falsy submit result means "the dialog unmounted", not "the submit failed".
 * A rename reaching only some of the call sites would silently restore an
 * unrecoverable soft-lock, which is why the string is spelled exactly once and
 * imported everywhere else, fixtures included: a rename that reached the
 * production sites and not the suites would test the old id against the new
 * code and pass.
 */
export const COMBAT_INIT_EVENT_ID = 'combat_init'

/**
 * The engine's passageway-confirmation event, by its Python class name
 * (`PassagewayTransitionEvent`, src/events.py).
 *
 * Not client-minted: the server sends it in `events_triggered[].type`, and the
 * client compares against it to decide that this interaction owns the rest of
 * the flow — close the source-room panel before the confirmation renders, or
 * the panel reappears with the destination room selected. Defined once for the
 * same reason as the id above: a rename reaching only some of its sites leaves
 * the comparison quietly false and the player looking at the wrong room.
 */
export const PASSAGEWAY_TRANSITION_EVENT_TYPE = 'PassagewayTransitionEvent'
