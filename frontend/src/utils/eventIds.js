/**
 * Event identifiers the client has to spell out — both the ids it mints itself
 * and the engine class names it recognises by string.
 *
 * These live in a plain utils module rather than alongside the hook that uses
 * them because `useEventManager` is mocked wholesale in several suites
 * (`vi.mock('../hooks/useEventManager', () => ({ useEventManager: vi.fn() }))`).
 * A constant exported from there resolves to `undefined` in every one of those
 * tests, which silently breaks the consumer under test rather than failing
 * where the mock is declared. Nothing mocks this file.
 */

/**
 * The combat-start confirmation prompt.
 *
 * Load-bearing for EventDialog's soft-lock guard: it is the one event id where
 * a falsy submit result means "the dialog unmounted", not "the submit failed".
 * A rename reaching only some of the call sites would silently restore an
 * unrecoverable soft-lock, which is why the string is defined exactly once.
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
 * same reason as the id above: it was spelled at five sites across the hook
 * and two suites, and a rename that reached only some of them would leave the
 * comparison quietly false and the player looking at the wrong room.
 */
export const PASSAGEWAY_TRANSITION_EVENT_TYPE = 'PassagewayTransitionEvent'
