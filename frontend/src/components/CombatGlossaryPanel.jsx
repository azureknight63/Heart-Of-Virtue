import { useEffect, useMemo, useRef, useState } from 'react'

import {
  GLOSSARY_CATEGORIES,
  filterGlossaryEntries,
  glossaryCategory,
} from '../data/combatGlossary'
import useHorizontalScrollEnd from '../hooks/useHorizontalScrollEnd'
import { useMobile } from '../hooks/useMobile'
import { colors, fonts, shadows, spacing } from '../styles/theme'

const ALL = 'all'

/**
 * One glossary entry: name → what it is → how you see it happening.
 *
 * The third line is the part that actually closes the player's question ("how
 * do I know a beat has passed?"), which is why entries are grouped by category
 * rather than alphabetised — a player who does not know what a beat is cannot
 * look it up under B.
 */
function GlossaryEntryRow({ entry, highlighted, rowRef }) {
  const category = glossaryCategory(entry.category)
  const accent = category?.color || colors.primary

  return (
    <li
      ref={rowRef}
      style={{
        padding: `10px ${highlighted ? spacing.sm : '0'}`,
        borderBottom: `1px solid ${colors.border.light}`,
        backgroundColor: highlighted ? colors.bg.highlightLight : 'transparent',
        borderLeft: highlighted ? `2px solid ${accent}` : '2px solid transparent',
        listStyle: 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: spacing.sm, flexWrap: 'wrap' }}>
        <h4 style={{
          margin: 0,
          fontSize: '0.85rem',
          fontWeight: 'bold',
          letterSpacing: '0.05em',
          color: accent,
        }}>
          {entry.term}
        </h4>
        <span style={{
          fontSize: '0.55rem',
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          border: `1px solid ${accent}`,
          color: accent,
          borderRadius: '2px',
          padding: '0 5px',
          lineHeight: 1.6,
        }}>
          {category?.label || entry.category}
        </span>
      </div>

      {entry.body.split('\n').map((line, index) => (
        // Positional lines of one immutable string: the index IS the identity.
        <p key={index} style={{
          fontSize: '0.75rem',
          color: colors.text.main,
          margin: `5px 0 0`,
          lineHeight: 1.55,
        }}>
          {line}
        </p>
      ))}

      <p style={{
        fontSize: '0.7rem',
        color: colors.text.highlight,
        margin: '5px 0 0',
        lineHeight: 1.5,
      }}>
        <span aria-hidden="true" style={{ color: colors.secondary }}>▸ </span>
        {entry.tell}
      </p>
    </li>
  )
}

/**
 * The combat glossary (issue #507).
 *
 * Desktop: a centred dialog. Touch: a full-height sheet with a grabber, which
 * starts below the app header and leaves the tab bar visible but inert.
 *
 * Only the entry list scrolls — the title, search box and category filters stay
 * pinned, so narrowing the list never scrolls its own controls away.
 */
export default function CombatGlossaryPanel({ onClose, focusEntryId = null }) {
  const isMobile = useMobile()
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState(ALL)
  const searchRef = useRef(null)
  const focusedRowRef = useRef(null)
  const { hasMore, ref: filtersRef } = useHorizontalScrollEnd()

  const entries = useMemo(() => filterGlossaryEntries({ category, query }), [category, query])

  useEffect(() => {
    searchRef.current?.focus()
  }, [])

  // A tooltip that handed off names the entry it was explaining; bring it into
  // view rather than making the player find it again in the full list.
  useEffect(() => {
    if (!focusEntryId) return
    focusedRowRef.current?.scrollIntoView?.({ block: 'center' })
  }, [focusEntryId, entries])

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onClose()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const chips = [{ id: ALL, label: 'All', color: colors.secondary }, ...GLOSSARY_CATEGORIES]

  const shellStyle = isMobile
    ? {
        position: 'fixed', left: 0, right: 0, bottom: 0, top: '52px',
        borderRadius: '8px 8px 0 0',
        borderTop: `2px solid ${colors.border.bright}`,
        boxShadow: '0 -6px 24px rgba(0, 0, 0, 0.8)',
      }
    : {
        width: '520px', maxWidth: '92vw', maxHeight: '80vh',
        border: `2px solid ${colors.border.bright}`,
        borderRadius: '8px',
        boxShadow: shadows.glow,
      }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1200,
        display: 'flex',
        alignItems: isMobile ? 'stretch' : 'flex-start',
        justifyContent: 'center',
        padding: isMobile ? 0 : '5vh 16px',
        backgroundColor: colors.bg.overlay,
      }}
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="combat-glossary-title"
        onClick={(event) => event.stopPropagation()}
        style={{
          ...shellStyle,
          backgroundColor: colors.bg.panelDeep,
          fontFamily: fonts.main,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {isMobile && (
          <div
            aria-hidden="true"
            style={{
              width: '44px', height: '4px', borderRadius: '2px',
              backgroundColor: colors.border.dark, margin: '8px auto 4px',
            }}
          />
        )}

        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '14px 16px 10px',
          borderBottom: `1px solid ${colors.border.main}`,
        }}>
          <h3 id="combat-glossary-title" style={{
            margin: 0, fontSize: '0.95rem', fontWeight: 'bold',
            letterSpacing: '0.1em', color: colors.primary,
          }}>
            COMBAT GLOSSARY
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close combat glossary"
            style={{
              background: 'none', border: 'none', color: colors.primary,
              fontSize: '16px', cursor: 'pointer',
              padding: isMobile ? '10px' : '0 4px',
            }}
          >
            ✕
          </button>
        </div>

        <div style={{
          margin: `12px ${spacing.lg} 0`,
          display: 'flex', alignItems: 'center', gap: spacing.sm,
          border: `1px solid ${colors.border.main}`, borderRadius: '4px',
          backgroundColor: colors.bg.input, padding: '7px 10px',
        }}>
          <span aria-hidden="true" style={{ color: colors.text.dim, fontSize: '12px' }}>⌕</span>
          <input
            ref={searchRef}
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Filter glossary terms"
            placeholder="Filter terms…"
            style={{
              flex: 1, background: 'none', border: 'none', outline: 'none',
              color: colors.text.main, fontFamily: fonts.main, fontSize: '0.8rem',
              minWidth: 0,
            }}
          />
        </div>

        {/* The chips overflow on a narrow sheet, so the row scrolls sideways and
            says so at its right edge — until it is scrolled to the end. */}
        <div style={{ position: 'relative' }}>
          <div
            ref={filtersRef}
            role="group"
            aria-label="Filter by category"
            style={{
              display: 'flex', gap: '6px', padding: '10px 16px 2px',
              overflowX: 'auto', flexWrap: 'nowrap', scrollbarWidth: 'none',
            }}
          >
            {chips.map(chip => {
              const selected = category === chip.id
              return (
                <button
                  key={chip.id}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setCategory(chip.id)}
                  style={{
                    flex: '0 0 auto',
                    fontSize: '0.62rem', letterSpacing: '0.1em', textTransform: 'uppercase',
                    padding: '3px 9px', borderRadius: '3px',
                    border: `1px solid ${chip.color}`,
                    backgroundColor: selected ? chip.color : 'rgba(0, 0, 0, 0.4)',
                    color: selected ? colors.text.inverse : chip.color,
                    fontFamily: fonts.main, cursor: 'pointer', whiteSpace: 'nowrap',
                  }}
                >
                  {chip.label}
                </button>
              )
            })}
          </div>
          {hasMore && (
            <>
              <div
                aria-hidden="true"
                style={{
                  position: 'absolute', top: 0, right: 0, bottom: 0, width: '34px',
                  pointerEvents: 'none',
                  background: `linear-gradient(to right, rgba(10,10,10,0), rgba(10,10,10,0.92))`,
                }}
              />
              <span
                aria-hidden="true"
                data-testid="glossary-filter-scroll-cue"
                style={{
                  position: 'absolute', right: '5px', top: '50%', transform: 'translateY(-50%)',
                  pointerEvents: 'none', color: colors.secondary, fontSize: '0.75rem', lineHeight: 1,
                }}
              >
                ›
              </span>
            </>
          )}
        </div>

        <ul style={{
          flex: 1, minHeight: 0, overflowY: 'auto',
          padding: '12px 16px 16px', margin: 0,
        }}>
          {entries.length === 0 ? (
            <li style={{ listStyle: 'none', color: colors.text.muted, fontSize: '0.75rem', fontStyle: 'italic' }}>
              No terms match that filter.
            </li>
          ) : entries.map(entry => (
            <GlossaryEntryRow
              key={entry.id}
              entry={entry}
              highlighted={entry.id === focusEntryId}
              rowRef={entry.id === focusEntryId ? focusedRowRef : undefined}
            />
          ))}
        </ul>

        <div style={{
          padding: '9px 16px',
          borderTop: `1px solid ${colors.border.main}`,
          fontSize: '0.62rem', color: colors.text.dim, letterSpacing: '0.06em',
        }}>
          Also opens from any underlined term · Esc to close
        </div>
      </div>
    </div>
  )
}
