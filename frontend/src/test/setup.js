import '@testing-library/jest-dom'
import { configure } from '@testing-library/react'

// Many tests wait on typewriter-style animations (character-by-character
// text). RTL's default 1s async timeout expires mid-animation on slower or
// loaded machines, flaking a different timing test on each full-suite run
// (observed: EventDialog paced narration, InteractPanel action results —
// each showed partially-typed text in the failure DOM). Raise the default;
// genuinely-failing waits just take 5s to report instead of 1s.
configure({ asyncUtilTimeout: 5000 })

// jsdom does not implement ResizeObserver — provide a no-op stub
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// jsdom does not implement scrollIntoView — provide a no-op stub
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// jsdom does not implement window.matchMedia — provide a stub that always returns desktop (non-mobile)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})
