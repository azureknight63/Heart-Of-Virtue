import { colorChannels } from './themeAudit'

/**
 * An opaque color token (`#rrggbb`, `#rgb`, `rgb()`) -> the `rgb(r, g, b)`
 * form jsdom normalises inline style colors to.
 *
 * Assert against `hexToRgb(colors.someToken)` rather than a literal `rgb(...)`
 * string: a hardcoded expectation passes just as happily when the component
 * inlines the hex instead of reading the token, which is the thing such a test
 * usually claims to be guarding. A translucent or unreadable token throws:
 * dropping its alpha would make the comparison mean something else.
 */
export const hexToRgb = hex => {
  const channels = colorChannels(hex)
  if (!channels || channels[3] !== 1) {
    throw new Error(`hexToRgb: ${hex} is not an opaque color`)
  }
  return `rgb(${channels.slice(0, 3).join(', ')})`
}

export default hexToRgb
