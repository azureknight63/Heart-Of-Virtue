import { colors, fonts } from '../styles/theme'

/**
 * Absolute-positioned gradient overlay signalling scrollable content above/below.
 * Must be placed inside a position:relative wrapper that is a sibling of (not inside)
 * the scroll container — otherwise the overlay will scroll with the content.
 */
export default function ScrollFadeIndicator({
  position = 'bottom',
  color = colors.primary,
  bgColor = '#0a0a0a',
}) {
  const isBottom = position === 'bottom'
  return (
    <div
      style={{
        position: 'absolute',
        [isBottom ? 'bottom' : 'top']: 0,
        left: 0,
        right: 0,
        height: '48px',
        background: `linear-gradient(to ${isBottom ? 'bottom' : 'top'}, transparent 0%, ${bgColor} 75%)`,
        display: 'flex',
        alignItems: isBottom ? 'flex-end' : 'flex-start',
        justifyContent: 'center',
        paddingBottom: isBottom ? '4px' : 0,
        paddingTop: isBottom ? 0 : '4px',
        pointerEvents: 'none',
        zIndex: 10,
      }}
    >
      <span
        className="scroll-indicator-label"
        style={{ color, fontSize: '0.62rem', letterSpacing: '1.5px', fontFamily: fonts.main }}
      >
        {isBottom ? '▼  scroll  ▼' : '▲  scroll  ▲'}
      </span>
    </div>
  )
}
