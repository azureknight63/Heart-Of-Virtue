import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import DOMPurify from 'dompurify'
import { colors, spacing, fonts, shadows } from '../styles/theme'
import GameText from './GameText'
import ScrollFadeIndicator from './ScrollFadeIndicator'
import useScrollIndicators from '../hooks/useScrollIndicators'
import { lookupOr } from '../utils/lookup'
import LiveAnnouncer from './LiveAnnouncer'

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

/**
 * One log entry's message as plain speech: no markup, no entities.
 *
 * Entries reach the list through `dangerouslySetInnerHTML`, so the engine
 * really does emit markup and a reader handed the raw string would spell out
 * the tags. Sanitised first and then read back as `textContent`, which both
 * drops the tags and decodes the entities — `DOMPurify.sanitize` with an empty
 * tag allow-list returns ESCAPED text, so `&amp;` would be announced
 * literally. The element is detached and never inserted, so nothing in it runs.
 */
function spokenText(message) {
  const scratch = document.createElement('div')
  // The empty allow-list is passed EXPLICITLY. Without it DOMPurify's default
  // config keeps <img src>, <source> and <video poster>, and parsing those into
  // this div fetches their subresources even though only textContent is read --
  // so a log line could beacon out, and LogAnnouncer runs even while the log is
  // collapsed and rendering nothing.
  scratch.innerHTML = DOMPurify.sanitize(String(message ?? ''), {
    ALLOWED_TAGS: [],
    ALLOWED_ATTR: [],
  })
  return scratch.textContent || ''
}

/**
 * LogAnnouncer — the screen-reader channel for the fight's own narration.
 *
 * Issue #563 item 1. The log is the game's primary feedback surface and it was
 * not announced at all: a screen-reader user committed a move and was told
 * nothing, then had to go hunting through the panel to learn whether they hit.
 *
 * WHY A SEPARATE REGION, AND NOT `aria-live` ON THE LIST. The list is not an
 * append-only stream. `useCombatLogPlayback` reveals entries a batch at a time,
 * and a beat scrub replaces the rendered slice wholesale — so a live region
 * around the list re-narrates lines the reader already heard, and on a scrub
 * re-narrates all of them. Battlefield.jsx's note on the beat counter names
 * the cost of getting this wrong ("a live region would make a screen reader
 * narrate the counter continuously over the combat log it should be reading");
 * a chatty log does the same thing to itself. This follows the pattern already
 * established for the same problem in NpcChatPanel's `ReplyAnnouncer`: one
 * hidden region, fed the newest completed line and nothing else.
 *
 * The timestamp is dropped deliberately. It renders beside every line, and
 * spoken aloud it prefixes each announcement with eight digits before any of
 * the content.
 *
 * `seq` is the revealed-line COUNT; why a polite region needs it, and why the
 * region is visually hidden rather than `display: none`, are documented on
 * LiveAnnouncer.
 *
 * @param {Object} props
 * @param {Array} props.entries - the revealed, renderable entries; only the
 *   newest is ever announced, and `animation` carriers are already gone.
 */
function LogAnnouncer({ entries }) {
  const latest = entries[entries.length - 1]
  const spoken = useMemo(() => (latest ? spokenText(latest.message) : ''), [latest])

  return <LiveAnnouncer text={spoken} seq={entries.length} testId="combat-log-announcer" />
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
      {/* Outside the collapse gate: hiding the lines is a request for room on
          screen, not a request to stop being told what is happening. */}
      <LogAnnouncer entries={visibleEntries} />

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
              // The announcer above necessarily holds a second copy of the
              // newest line's text, so "is this line rendered?" has to ask
              // about the LIST rather than the document — see the scoped
              // queries in CombatLog.test.jsx.
              data-testid="combat-log-entries"
              style={{
                height: '100%',
                overflowY: 'auto',
                padding: spacing.sm,
                // Shares ScrollFadeIndicator/useScrollIndicators with
                // CollapsibleRoomDescription (issue #537): the same
                // fade+label overlay paints over the last/first visible log
                // line unless extra space is reserved for it here.
                paddingBottom: showBottom ? '44px' : spacing.sm,
                paddingTop: showTop ? '44px' : spacing.sm,
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
