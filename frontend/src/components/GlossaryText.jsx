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

  // `{ index, placement, text }` — index into `segments`, so the same word
  // appearing twice in one string gets its own independently-openable
  // explainer, and `text` so an explainer opened against one string is not
  // still showing over the next one (the ConversationStage trap in CLAUDE.md,
  // in miniature). Recorded on the state rather than cleared by an effect:
  // resetting state from an effect costs an extra render pass, and a stale
  // explainer would be visible for that frame.
  const [openTerm, setOpenTerm] = useState(null)
  const active = openTerm?.text === text ? openTerm : null

  const segments = useMemo(() => splitTextByGlossaryTerms(text), [text])

  const dismiss = useCallback(() => setOpenTerm(null), [])

  const activate = useCallback((index, element) => {
    const top = element?.getBoundingClientRect?.().top ?? 0
    setOpenTerm({ index, text, placement: top > TOOLTIP_CLEARANCE_PX ? 'top' : 'bottom' })
  }, [text])

  // Tapping (or clicking) anywhere else dismisses, as does Escape.
  useEffect(() => {
    if (!active) return undefined
    const onPointerDown = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpenTerm(null)
    }
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setOpenTerm(null)
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
    setOpenTerm(null)
    openGlossary(entryId)
  }, [openGlossary])

  return (
    <div ref={rootRef} className={className} style={style} {...rest}>
      {segments.map((segment, index) => {
        const entry = segment.entryId ? getGlossaryEntry(segment.entryId) : null
        if (!entry) {
          // Positional runs of one immutable string: the index IS the identity,
          // and the list is rebuilt whenever the string changes.
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
            if (!event.currentTarget.contains(event.relatedTarget)) setOpenTerm(null)
          },
        }

        return (
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
