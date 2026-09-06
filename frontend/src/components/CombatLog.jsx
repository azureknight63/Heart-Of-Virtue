import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import DOMPurify from 'dompurify'
import { colors, spacing, fonts, shadows } from '../styles/theme'
import GameText from './GameText'
import ScrollFadeIndicator from './ScrollFadeIndicator'
import useScrollIndicators from '../hooks/useScrollIndicators'
import { lookupOr } from '../utils/lookup'

/**
 * Colour per log-entry `type`, keyed on the ENGINE'S vocabulary.
 *
 * It used to be keyed `damage`/`heal`/`ability`/`info`/`system`, which is a
 * vocabulary nothing emits three-fifths of: no combat-log writer anywhere in
 * the engine has ever produced `damage`, `heal` or `ability`. Meanwhile
 * `combat` — `_add_log_entry`'s default in src/api/combat_adapter.py, and so
 * the type of very nearly every line the player reads — was absent, and fell
 * through to the fallback. The table was, in effect, doing nothing.
 *
 * The whole vocabulary, and where each is minted:
 *   combat         src/api/combat_adapter.py's `_add_log_entry` default, plus
 *                  the narration replayed by src/api/services/game_service.py.
 *                  The body text of the fight; deliberately the plain reading
 *                  colour, since colouring the majority colours nothing.
 *   player_action  the adapter's echo of the move Jean committed to.
 *   system         victory, defeat, and enemy-alert lines.
 *   info           the Check-battlefield readouts in src/moves/_utility.py.
 *   animation      bookkeeping for the battlefield, never rendered — filtered
 *                  out of `visibleEntries` below, which is why it is the one
 *                  engine type with no colour here.
 *
 * CombatLog.test.jsx derives that list from the Python and fails if this table
 * and the engine stop agreeing in either direction.
 */
export const LOG_ENTRY_COLORS = {
  combat: colors.text.main,
  player_action: colors.primary,
  system: colors.gold,
  info: colors.text.muted
}

export default function CombatLog({ log, className = '', allowResize = true, isMyTurn = false }) {
  // Animation entries are bookkeeping for the battlefield, never lines of text,
  // so they are excluded from the rendered log. Deriving the visible list once
  // keeps the empty-state check and the render in agreement: gating the
  // placeholder on the raw `log.length` instead meant a log holding only
  // animation entries -- reachable at combat start, since the reveal loop adds
  // entries one at a time -- rendered an empty panel with no placeholder at
  // all. `log?.length === 0` also missed an absent log entirely, because
  // `undefined === 0` is false.
  const visibleEntries = useMemo(
    () => (log || []).filter(entry => entry.type !== 'animation'),
    [log]
  )

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
              {visibleEntries.length === 0 && (
                <GameText variant="muted" size="sm" align="center" style={{ fontStyle: 'italic', padding: spacing.sm }}>
                  Combat started...
                </GameText>
              )}
              {visibleEntries.map((entry, idx) => {
                const textColor = lookupOr(LOG_ENTRY_COLORS, entry.type, colors.text.main)

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
