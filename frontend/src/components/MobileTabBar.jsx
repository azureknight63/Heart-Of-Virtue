import React from 'react'
import { colors, fonts } from '../styles/theme'

function MobileTabBar({ activeTab, onTabChange, mode }) {
  const isCharActive = activeTab === 'character'
  const isMapActive = activeTab === 'map'

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
      height: '56px',
      display: 'flex',
      backgroundColor: '#0d0d1a',
      borderTop: `2px solid ${colors.border.main}`,
      zIndex: 1000,
      paddingBottom: 'env(safe-area-inset-bottom)',
    }}>
      <button onClick={() => onTabChange('character')} style={tabStyle(isCharActive, colors.primary)}>
        <span style={{ fontSize: '20px', lineHeight: 1 }}>🧝</span>
        <span>{mode === 'combat' ? 'COMBAT' : 'CHARACTER'}</span>
      </button>
      <button onClick={() => onTabChange('map')} style={tabStyle(isMapActive, colors.secondary)}>
        <span style={{ fontSize: '20px', lineHeight: 1 }}>🗺️</span>
        <span>{mode === 'combat' ? 'BATTLEFIELD' : 'MAP'}</span>
      </button>
    </div>
  )
}

export default MobileTabBar
