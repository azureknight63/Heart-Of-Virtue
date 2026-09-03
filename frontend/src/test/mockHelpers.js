// Default useCapabilities() mock shape: resolved, streaming disabled. Import
// this instead of hand-rolling the shape in every GamePage test file so the
// mocked contract can't drift from context/CapabilitiesContext.jsx's real one.
export const capabilitiesDisabled = Object.freeze({
  combatSocketStreaming: false,
  capabilitiesLoading: false,
})


/** `#rrggbb` -> `rgb(r, g, b)`, the form jsdom reports for inline colours. */
export function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16)
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
}
