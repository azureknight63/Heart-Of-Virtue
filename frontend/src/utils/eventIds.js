/**
 * Synthetic event ids — client-minted, never sent by the engine.
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
