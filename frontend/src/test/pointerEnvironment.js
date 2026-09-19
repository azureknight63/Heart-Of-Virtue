import { vi } from 'vitest'

/**
 * A `window.matchMedia` stub that answers WIDTH and POINTER independently.
 *
 * The shared setup (test/setup.js) answers `matches: false` to every query,
 * which describes a wide mouse-driven desktop and nothing else. The device
 * that issue #639 is about — a tablet wider than 767px being pointed at with
 * a thumb — needs the two axes to disagree, and the only stub in the tree that
 * touched both (Battlefield.camera.test.jsx, #564) matches `max-width` and
 * `pointer: coarse` TOGETHER, so it can express a phone and a desktop and
 * nothing in between. This one splits them.
 *
 * `narrow` drives every `max-width` query (what `useMobile` asks) and `coarse`
 * drives `hover: none` / `pointer: coarse` (what `useCoarsePointer` asks).
 * Anything else answers false rather than guessing — including `min-width`,
 * which means the opposite of `max-width` and would be a lie to answer with
 * the same flag. Nothing in `src/` queries it today; a hook that starts to
 * must be given its own axis here rather than borrowing this one.
 *
 * The listeners a hook registers are collected so a test can flip modality
 * mid-session; `restore` puts the original stub back and must run in an
 * `afterEach`, since the replacement is a global.
 *
 * @param {{narrow?: boolean, coarse?: boolean}} env
 * @returns {{restore: () => void, listeners: Set<Function>, queries: string[]}}
 */
export function stubPointerEnvironment({ narrow = false, coarse = false } = {}) {
  const original = window.matchMedia
  const listeners = new Set()
  const queries = []

  window.matchMedia = vi.fn((query) => {
    queries.push(query)
    const matches = /max-width/.test(query)
      ? narrow
      : (/hover:\s*none|pointer:\s*coarse/.test(query) ? coarse : false)
    return {
      matches,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: (_, handler) => listeners.add(handler),
      removeEventListener: (_, handler) => listeners.delete(handler),
      dispatchEvent: () => false,
    }
  })

  return {
    listeners,
    queries,
    restore: () => { window.matchMedia = original },
  }
}

/** The device issue #639 is about: a ~1024px tablet, pointed at with a thumb. */
export const stubWideTouchTablet = () => stubPointerEnvironment({ narrow: false, coarse: true })

export default stubPointerEnvironment
