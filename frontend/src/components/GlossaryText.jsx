import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'

import { getGlossaryEntry, splitTextByGlossaryTerms } from '../data/combatGlossary'
import { useGlossary } from '../context/GlossaryContext'
import { useCoarsePointer } from '../hooks/useCoarsePointer'
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
 * appears directly under their thumb. That branch reads the *pointer*, not the
 * viewport width: a 1024px tablet is a touch device, and keying the docked
 * presentation off `useMobile` floated the card under the thumb on exactly the
 * hardware the docked presentation exists for.
 */
export default function GlossaryText({ text, style, className, ...rest }) {
  const isCoarse = useCoarsePointer()
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
  // The rendered <button> for each term index, so the hand-off can put focus
  // back on the word rather than on a button it is about to unmount. A ref and
  // not `activate`'s element argument: mouseenter fires on the wrapper span,
  // which is not focusable.
  const termRefs = useRef(new Map())
  // What `isActive` was when the pointer went *down*. A browser focuses a
  // <button> on pointer-down and React 18 flushes that discrete update before
  // the click arrives, so by the time onClick runs the card the very same tap
  // just opened is already open — toggling on `isActive` there closed it again
  // and made the docked (touch) card unreachable entirely.
  const pointerStateRef = useRef(null)

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

  const handOff = useCallback((entryId, index) => {
    // Focus the term *before* the panel opens. The panel records
    // document.activeElement as the element to return focus to on close, and
    // the "Open glossary" button holding focus right now is unmounted by this
    // same commit — leaving the panel with nothing to restore and the player
    // at <body> mid-fight.
    termRefs.current.get(index)?.focus?.()
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
        const hoverProps = isCoarse ? {} : {
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
              ref={(el) => {
                if (el) termRefs.current.set(index, el)
                else termRefs.current.delete(index)
              }}
              aria-expanded={isActive}
              aria-describedby={isActive ? tipId : undefined}
              aria-label={`${segment.text} — what this means`}
              onPointerDown={() => { pointerStateRef.current = { wasOpen: isActive } }}
              onClick={(event) => {
                const pointerState = pointerStateRef.current
                pointerStateRef.current = null
                // `detail` is 0 only for a click no pointer produced —
                // Enter/Space on the focused term. It is the discriminator
                // rather than "did a pointerdown happen", because a
                // pointerdown the player dragged away from never reaches a
                // click and would otherwise leave stale state behind for the
                // next keyboard press to read.
                const fromPointer = event.detail > 0 && pointerState !== null
                // A pointer click toggles against the state as it was before
                // the pointer went down (see pointerStateRef above); a
                // keyboard click has nothing to correct for, so `isActive` is
                // already the truth.
                const wasOpen = fromPointer ? pointerState.wasOpen : isActive
                // Where the player can hover, the card is already open from
                // mouseenter and closing it here would blank the explainer
                // while the pointer still rests on the word — pointing away or
                // Escape dismisses instead. A keyboard click still toggles.
                const closes = wasOpen && (isCoarse || !fromPointer)
                if (closes) dismiss()
                else activate(index, event.currentTarget)
              }}
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
            {isActive && !isCoarse && (
              <GlossaryTooltipCard
                id={tipId}
                entry={entry}
                placement={active.placement}
                onOpenGlossary={() => handOff(entry.id, index)}
              />
            )}
          </span>
        )
      })}

      {isCoarse && activeEntry && (
        <GlossaryTooltipCard
          docked
          id={`${baseId}-term-${active.index}`}
          entry={activeEntry}
          onOpenGlossary={() => handOff(activeEntry.id, active.index)}
        />
      )}
    </div>
  )
}
