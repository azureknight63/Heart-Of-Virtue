import { vi } from 'vitest'

/**
 * A `window.matchMedia` stub that answers WIDTH and POINTER independently.
 *
 * The shared setup (test/setup.js) answers `matches: false` to every query,
 * which describes a wide mouse-driven desktop and nothing else. The device
 * that issue #639 is about — a tablet wider than 767px being pointed at with
 * a thumb — needs the two axes to disagree, and the only stub in the tree that
 * touched both (Battlefield.camera.test.jsx, #564) matched `max-width` and
 * `pointer: coarse` off ONE regex, so it could express a phone and a desktop
 * and nothing in between. This one splits them, and that stub now calls this.
 *
 * `narrow` drives every `max-width` query (what `useMobile` asks) and `coarse`
 * drives `hover: none` / `pointer: coarse` (what `useCoarsePointer` asks).
 * Anything else answers false rather than guessing — including `min-width`,
 * which means the opposite of `max-width` and would be a lie to answer with
 * the same flag. Nothing in `src/` queries it today; a hook that starts to
 * must be given its own axis here rather than borrowing this one.
 *
 * `queries` records what was asked, so a test can assert a hook really put
 * both questions to `matchMedia` rather than inferring one from the other.
 * `restore` puts the original stub back and must run in an `afterEach`, since
 * the replacement is a global.
 *
 * MODALITY DOES NOT CHANGE MID-SESSION here. The registered listeners used to
 * be collected and handed back "so a test can flip modality", which this stub
 * could not deliver: `matches` is computed from the closed-over `narrow` and
 * `coarse`, so invoking a collected handler cannot change what a re-query
 * answers, and no test ever read the Set. Rather than leave a promise the code
 * does not keep, the Set is gone. A test that genuinely needs a mid-session
 * flip should make the two axes mutable and expose a setter that also fires
 * the handlers — at which point the promise would be real.
 *
 * @param {{narrow?: boolean, coarse?: boolean}} env
 * @returns {{restore: () => void, queries: string[]}}
 */
export function stubPointerEnvironment({ narrow = false, coarse = false } = {}) {
  const original = window.matchMedia
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
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }
  })

  return {
    queries,
    restore: () => { window.matchMedia = original },
  }
}

/** The device issue #639 is about: a ~1024px tablet, pointed at with a thumb. */
export const stubWideTouchTablet = () => stubPointerEnvironment({ narrow: false, coarse: true })

export default stubPointerEnvironment
