// Default useCapabilities() mock shape: resolved, streaming disabled. Import
// this instead of hand-rolling the shape in every GamePage test file so the
// mocked contract can't drift from context/CapabilitiesContext.jsx's real one.
export const capabilitiesDisabled = Object.freeze({
  combatSocketStreaming: false,
  capabilitiesLoading: false,
})
