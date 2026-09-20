import { useState, useRef, useEffect, useCallback, useId } from 'react'
import RoomContents from './RoomContents'
import ScrollFadeIndicator from './ScrollFadeIndicator'
import CollapsibleSectionHeader from './CollapsibleSectionHeader'
import useScrollIndicators from '../hooks/useScrollIndicators'
import { colors } from '../styles/theme'

export default function CollapsibleRoomDescription({ location, onInteract, defaultOpen = true }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const bodyId = useId()
  // containerRef holds the DOM node for imperative scrollTop resets without
  // making it a reactive dep (avoids spurious effect re-runs on every render).
  const containerRef = useRef(null)
  const { showTop, showBottom, check, ref: scrollIndicatorRef } = useScrollIndicators()

  // Merged callback ref: keeps containerRef.current in sync AND wires the
  // scroll-indicator hook so it re-subscribes whenever the panel opens/closes.
  const scrollContainerRef = useCallback(node => {
    containerRef.current = node
    scrollIndicatorRef(node)
  }, [scrollIndicatorRef])

  useEffect(() => {
    if (isOpen && containerRef.current) {
      containerRef.current.scrollTop = 0
    }
    check()
  }, [location, isOpen, check])

  if (!location) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <CollapsibleSectionHeader
        expanded={isOpen}
        onToggle={() => setIsOpen(o => !o)}
        controlsId={bodyId}
        style={{
          borderBottom: `1px solid ${colors.primary}33`,
          padding: '6px 8px',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0, flexShrink: 1 }}>
          {location.name || 'Current Location'}
        </span>
      </CollapsibleSectionHeader>

      {/* Always mounted so aria-controls always resolves; the description
          itself comes and goes. Same pattern as InteractPanel's category
          rows and HeatMeter's rules table. */}
      <div id={bodyId}>
        {isOpen && (
          <div style={{ position: 'relative' }}>
            <div
              ref={scrollContainerRef}
              style={{
                // Was a flat 200px — issue #537 measured a 200px clientHeight
                // with 149px of unused panel space sitting empty right below
                // it, clipping NPC/object presence lines (appended after the
                // room description in RoomContents) that never got a chance to
                // render. 360px lets the box grow into that space instead of
                // capping well below what the parent panel already affords.
                maxHeight: '360px',
                overflowY: 'auto',
                // Reserve room for the fade/label ScrollFadeIndicator paints
                // at the top/bottom edge so it overlaps blank padding instead
                // of the last (or first) visible line of real text.
                paddingBottom: showBottom ? '44px' : 0,
                paddingTop: showTop ? '44px' : 0,
              }}
            >
              <RoomContents location={location} onInteract={onInteract} />
            </div>
            {showTop && (
              <ScrollFadeIndicator position="top" color={colors.primary} bgColor="rgb(10, 30, 20)" />
            )}
            {showBottom && (
              <ScrollFadeIndicator position="bottom" color={colors.primary} bgColor="rgb(10, 30, 20)" />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
