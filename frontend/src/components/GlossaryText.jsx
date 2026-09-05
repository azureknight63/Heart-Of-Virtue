import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'

import { getGlossaryEntry, splitTextByGlossaryTerms } from '../data/combatGlossary'
import { useGlossary } from '../context/GlossaryContext'
import { useMobile } from '../hooks/useMobile'
import { colors } from '../styles/theme'
import GlossaryTooltipCard from './GlossaryTooltipCard'

// Roughly how tall a tooltip card gets. Used only to decide whether there is
// room above the term; being a little wrong flips the card to the side with
// more space, which is the same answer either way.
const TOOLTIP_CLEARANCE_PX = 190

/**
 * Renders engine-authored combat text, turning any word the glossary defines
 * into an inline explainer (issue #507 — "What the Heck are Beats?").
 *
 * The string arrives from the engine (a move's `reason`, e.g.
 * "Available in 5 beats") and is rendered verbatim: this component only wraps
 * the words `combatGlossary.splitTextByGlossaryTerms` recognises, so no copy
 * is invented here and text with no known terms renders exactly as it did
 * before.
 *
 * Touch does not get a floating popover. The card docks in flow underneath the
 * line instead, because a popover anchored to the word the player just tapped
 * appears directly under their thumb.
 */
export default function GlossaryText({ text, style, className, ...rest }) {
  const isMobile = useMobile()
  const { openGlossary } = useGlossary()
  const rootRef = useRef(null)
  const baseId = useId()

  // `{ index, placement }` — index into `segments`, so the same word appearing
  // twice in one string gets its own independently-openable explainer.
  const [active, setActive] = useState(null)

  const segments = useMemo(() => splitTextByGlossaryTerms(text), [text])

  // A new string is a new set of terms; without this the open explainer would
  // survive into text it no longer belongs to (the ConversationStage trap in
  // CLAUDE.md, in miniature).
  useEffect(() => {
    setActive(null)
  }, [segments])

  const dismiss = useCallback(() => setActive(null), [])

  const activate = useCallback((index, element) => {
    const top = element?.getBoundingClientRect?.().top ?? 0
    setActive({ index, placement: top > TOOLTIP_CLEARANCE_PX ? 'top' : 'bottom' })
  }, [])

  // Tapping (or clicking) anywhere else dismisses, as does Escape.
  useEffect(() => {
    if (!active) return undefined
    const onPointerDown = (event) => {
      if (!rootRef.current?.contains(event.target)) setActive(null)
    }
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setActive(null)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('touchstart', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('touchstart', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [active])

  const activeEntry = active ? getGlossaryEntry(segments[active.index]?.entryId) : null

  const handOff = useCallback((entryId) => {
    setActive(null)
    openGlossary(entryId)
  }, [openGlossary])

  return (
    <div ref={rootRef} className={className} style={style} {...rest}>
      {segments.map((segment, index) => {
        const entry = segment.entryId ? getGlossaryEntry(segment.entryId) : null
        if (!entry) {
          // eslint-disable-next-line react/no-array-index-key -- segments are positional runs of one immutable string; there is no other stable identity, and the list is rebuilt whenever the string changes.
          return <span key={index}>{segment.text}</span>
        }

        const isActive = active?.index === index
        const tipId = `${baseId}-term-${index}`
        const hoverProps = isMobile ? {} : {
          onMouseEnter: (event) => activate(index, event.currentTarget),
          onMouseLeave: dismiss,
          onBlur: (event) => {
            // Tabbing from the term into the tooltip's own "Open glossary"
            // button must not close the thing being tabbed into.
            if (!event.currentTarget.contains(event.relatedTarget)) setActive(null)
          },
        }

        return (
          // eslint-disable-next-line react/no-array-index-key -- see above.
          <span key={index} style={{ position: 'relative', display: 'inline-block' }} {...hoverProps}>
            <button
              type="button"
              aria-expanded={isActive}
              aria-describedby={isActive ? tipId : undefined}
              aria-label={`${segment.text} — what this means`}
              onClick={(event) => (isActive ? dismiss() : activate(index, event.currentTarget))}
              onFocus={(event) => activate(index, event.currentTarget)}
              style={{
                background: 'none',
                border: 'none',
                borderBottom: `1px dotted ${colors.alpha.info[80]}`,
                padding: 0,
                font: 'inherit',
                color: isActive ? colors.text.bright : colors.accent,
                cursor: 'help',
              }}
            >
              {segment.text}
            </button>
            {isActive && !isMobile && (
              <GlossaryTooltipCard
                id={tipId}
                entry={entry}
                placement={active.placement}
                onOpenGlossary={() => handOff(entry.id)}
              />
            )}
          </span>
        )
      })}

      {isMobile && activeEntry && (
        <GlossaryTooltipCard
          docked
          id={`${baseId}-term-${active.index}`}
          entry={activeEntry}
          onOpenGlossary={() => handOff(activeEntry.id)}
        />
      )}
    </div>
  )
}
