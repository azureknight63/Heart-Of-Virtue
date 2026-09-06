/**
 * `#rrggbb` -> the `rgb(r, g, b)` form jsdom normalises inline style colours to.
 *
 * Assert against `hexToRgb(colors.someToken)` rather than a literal `rgb(...)`
 * string: a hardcoded expectation passes just as happily when the component
 * inlines the hex instead of reading the token, which is the thing such a test
 * usually claims to be guarding.
 */
export const hexToRgb = hex =>
  `rgb(${[1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16)).join(', ')})`

export default hexToRgb
