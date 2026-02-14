import { useState, useRef, useEffect } from 'react'
import { colors, spacing, fonts, shadows } from '../styles/theme'
import GameText from './GameText'

export default function CombatLog({ log, className = '', allowResize = true, isMyTurn = false }) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [height, setHeight] = useState(150)
  const [isResizing, setIsResizing] = useState(false)
  const logRef = useRef(null)
  const contentRef = useRef(null)

  const handleMouseDown = () => {
    if (allowResize) setIsResizing(true)
  }

  useEffect(() => {
    const handleMouseUp = () => setIsResizing(false)
    const handleMouseMove = (e) => {
      if (!isResizing) return
      const delta = e.clientY - (logRef.current?.getBoundingClientRect().bottom || 0)
      setHeight(Math.max(50, Math.min(400, height - delta)))
    }

    document.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('mousemove', handleMouseMove)
    return () => {
      document.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('mousemove', handleMouseMove)
    }
  }, [isResizing, height])

  // Auto-scroll to bottom when log updates
  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [log])

  // Auto-scroll to bottom when it becomes player's turn
  useEffect(() => {
    if (isMyTurn && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [isMyTurn])

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
        transition: 'height 0.3s ease',
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
          <div
            ref={contentRef}
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: spacing.sm,
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              fontFamily: fonts.main,
              scrollbarWidth: 'thin',
              scrollbarColor: `${colors.border.main} transparent`
            }}
          >
            {log?.length === 0 && (
              <GameText variant="muted" size="sm" align="center" style={{ fontStyle: 'italic', padding: spacing.sm }}>
                Combat started...
              </GameText>
            )}
            {log?.filter(entry => entry.type !== 'animation').map((entry, idx) => {
              let textColor = colors.text.main
              if (entry.type === 'damage') textColor = colors.danger
              else if (entry.type === 'heal') textColor = colors.success
              else if (entry.type === 'ability') textColor = colors.accent
              else if (entry.type === 'info') textColor = colors.text.muted
              else if (entry.type === 'system') textColor = colors.gold

              return (
                <div key={idx} style={{ fontSize: '13px', lineHeight: '1.4' }}>
                  <span style={{ opacity: 0.5, marginRight: spacing.sm, color: colors.text.muted, fontSize: '11px' }}>
                    [{entry.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}]
                  </span>
                  <span
                    style={{ color: textColor }}
                    dangerouslySetInnerHTML={{ __html: entry.message }}
                  />
                </div>
              )
            })}
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
