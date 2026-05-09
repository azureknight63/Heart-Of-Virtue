import { useState, useRef, useEffect } from 'react'
import RoomContents from './RoomContents'
import { colors, fonts, accessibility } from '../styles/theme'

export default function CollapsibleRoomDescription({ location, onInteract, defaultOpen = true }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const scrollContainerRef = useRef(null)

  useEffect(() => {
    if (isOpen && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = 0
    }
  }, [location, isOpen])

  if (!location) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <button
        onClick={() => setIsOpen(o => !o)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'none',
          border: 'none',
          borderBottom: `1px solid ${colors.primary}33`,
          padding: '6px 8px',
          cursor: 'pointer',
          color: colors.primary,
          fontFamily: fonts.main,
          fontSize: '11px',
          fontWeight: 'bold',
          textTransform: 'uppercase',
          letterSpacing: '1px',
          touchAction: 'manipulation',
          minHeight: accessibility.touchTarget,
          width: '100%',
          textAlign: 'left',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0, flexShrink: 1 }}>
          {location.name || 'Current Location'}
        </span>
        <span style={{
          marginLeft: '8px',
          flexShrink: 0,
          display: 'inline-block',
          transition: 'transform 0.2s',
          transform: isOpen ? 'rotate(180deg)' : 'none',
          fontSize: '10px',
        }}>▼</span>
      </button>

      {isOpen && (
        <div ref={scrollContainerRef} style={{ maxHeight: '200px', overflowY: 'auto' }}>
          <RoomContents location={location} onInteract={onInteract} />
        </div>
      )}
    </div>
  )
}
