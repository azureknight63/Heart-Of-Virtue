import { colors, fonts } from '../styles/theme'

export const MOBILE_TAB_BAR_HEIGHT = '56px'

function MobileTabBar({ activeTab, onTabChange, mode }) {
  const isExploration = mode === 'exploration'
  const tab1Key = isExploration ? 'character' : 'combat'
  const tab2Key = isExploration ? 'map' : 'battlefield'

  const isTab1Active = activeTab === tab1Key
  const isTab2Active = activeTab === tab2Key

  const tabStyle = (active, accentColor) => ({
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'none',
    border: 'none',
    borderTop: active ? `3px solid ${accentColor}` : '3px solid transparent',
    cursor: 'pointer',
    fontFamily: fonts.main,
    color: active ? accentColor : colors.text.muted,
    fontSize: '11px',
    fontWeight: 'bold',
    gap: '2px',
    touchAction: 'manipulation',
    transition: 'color 0.2s',
    padding: '6px 0',
    WebkitTapHighlightColor: 'transparent',
  })

  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      height: MOBILE_TAB_BAR_HEIGHT,
      display: 'flex',
      backgroundColor: colors.bg.panelDeep,
      borderTop: `2px solid ${colors.border.main}`,
      zIndex: 1000,
      paddingBottom: 'env(safe-area-inset-bottom)',
    }}>
      <button onClick={() => onTabChange(tab1Key)} style={tabStyle(isTab1Active, colors.primary)}>
        <span style={{ fontSize: '20px', lineHeight: 1 }}>🧝</span>
        <span>{isExploration ? 'CHARACTER' : 'COMBAT'}</span>
      </button>
      <button onClick={() => onTabChange(tab2Key)} style={tabStyle(isTab2Active, colors.secondary)}>
        <span style={{ fontSize: '20px', lineHeight: 1 }}>🗺️</span>
        <span>{isExploration ? 'MAP' : 'BATTLEFIELD'}</span>
      </button>
    </div>
  )
}

export default MobileTabBar
