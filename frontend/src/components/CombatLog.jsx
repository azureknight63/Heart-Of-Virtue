import { useState, useRef, useEffect, useCallback } from 'react'
import DOMPurify from 'dompurify'
import { colors, spacing, fonts, shadows } from '../styles/theme'
import GameText from './GameText'
import ScrollFadeIndicator from './ScrollFadeIndicator'
import useScrollIndicators from '../hooks/useScrollIndicators'

const LOG_ENTRY_COLORS = {
  damage: colors.danger,
  heal: colors.success,
  ability: colors.accent,
  info: colors.text.muted,
  system: colors.gold
}

export default function CombatLog({ log, className = '', allowResize = true, isMyTurn = false }) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [height, setHeight] = useState(150)
  const [isResizing, setIsResizing] = useState(false)
  const logRef = useRef(null)
  const contentRef = useRef(null)
  const { showTop, showBottom, check, ref: scrollIndicatorRef } = useScrollIndicators()

  // Merged callback ref: keeps contentRef.current for imperative auto-scroll
  // AND wires the indicator hook so it re-subscribes after collapse/expand cycles.
  const setContentRef = useCallback(node => {
    contentRef.current = node
    scrollIndicatorRef(node)
  }, [scrollIndicatorRef])

  const handleMouseDown = () => {
    if (allowResize) setIsResizing(true)
  }

  // Use a ref so the mousemove handler always reads the *current* height
  // without being stale and without needing height in the effect deps.
  const heightRef = useRef(height)
  useEffect(() => { heightRef.current = height }, [height])

  useEffect(() => {
    const handleMouseUp = () => setIsResizing(false)
    const handleMouseMove = (e) => {
      if (!isResizing) return
      const delta = e.clientY - (logRef.current?.getBoundingClientRect().bottom || 0)
      setHeight(Math.max(50, Math.min(400, heightRef.current - delta)))
    }

    document.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('mousemove', handleMouseMove)
    return () => {
      document.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('mousemove', handleMouseMove)
    }
  }, [isResizing]) // height intentionally omitted — read via heightRef

  // Auto-scroll to bottom when log updates or it becomes the player's turn
  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
    check()
  }, [log, isMyTurn, check])

  return (
    <div
      ref={logRef}
      style={{
        height: isCollapsed ? '32px' : allowResize ? `${height}px` : '100%',
        backgroundColor: colors.bg.panelHeavy,
        border: `1px solid ${colors.border.main}`,
        borderRadius: '4px',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: shadows.main,
        overflow: 'hidden',
        transition: allowResize ? 'none' : 'height 0.3s ease',
      }}
      className={className}
    >
      <div
        onClick={() => setIsCollapsed(!isCollapsed)}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: `${spacing.xs} ${spacing.md}`,
          backgroundColor: colors.bg.panel,
          borderBottom: isCollapsed ? 'none' : `1px solid ${colors.border.light}`,
          cursor: 'pointer',
        }}
      >
        <GameText variant="secondary" size="xs" weight="bold" style={{ tracking: 'wider', textTransform: 'uppercase' }}>
          Combat Log
        </GameText>
        <GameText variant="secondary" size="xs">
          {isCollapsed ? '▶' : '▼'}
        </GameText>
      </div>

      {!isCollapsed && (
        <>
          <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
            <div
              ref={setContentRef}
              style={{
                height: '100%',
                overflowY: 'auto',
                padding: spacing.sm,
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                fontFamily: fonts.main,
                scrollbarWidth: 'thin',
                scrollbarColor: `${colors.border.main} transparent`,
                WebkitOverflowScrolling: 'touch',
                touchAction: 'pan-y',
              }}
            >
              {log?.length === 0 && (
                <GameText variant="muted" size="sm" align="center" style={{ fontStyle: 'italic', padding: spacing.sm }}>
                  Combat started...
                </GameText>
              )}
              {log?.filter(entry => entry.type !== 'animation').map((entry, idx) => {
                const textColor = LOG_ENTRY_COLORS[entry.type] || colors.text.main

                return (
                  <div key={entry.id ?? `${entry.timestamp}-${idx}`} style={{ fontSize: '13px', lineHeight: '1.4' }}>
                    <span style={{ opacity: 0.5, marginRight: spacing.sm, color: colors.text.muted, fontSize: '11px' }}>
                      [{entry.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}]
                    </span>
                    <span
                      style={{ color: textColor }}
                      dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(entry.message) }}
                    />
                  </div>
                )
              })}
            </div>
            {showTop && (
              <ScrollFadeIndicator position="top" color={colors.secondary} bgColor="#030303" />
            )}
            {showBottom && (
              <ScrollFadeIndicator position="bottom" color={colors.secondary} bgColor="#030303" />
            )}
          </div>
          {allowResize && (
            <div
              onMouseDown={handleMouseDown}
              style={{
                height: '6px',
                background: `linear-gradient(to right, transparent, ${colors.border.main}, transparent)`,
                cursor: 'ns-resize',
                opacity: 0.3,
              }}
            ></div>
          )}
        </>
      )}
    </div>
  )
}
