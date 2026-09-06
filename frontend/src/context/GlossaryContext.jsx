import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

import CombatGlossaryPanel from '../components/CombatGlossaryPanel'

// Rendered outside a provider — a component test, or any surface that shows a
// combat string without the game shell — the affordances are inert rather than
// fatal. A dead "?" is a missing feature; a thrown error mid-fight is a lost
// session. `App.test.jsx` asserts the real game route is wrapped, so the wiring
// itself is still guarded.
const INERT_GLOSSARY = Object.freeze({
  openGlossary: () => {},
  closeGlossary: () => {},
  isGlossaryOpen: false,
})

const GlossaryContext = createContext(INERT_GLOSSARY)

export function useGlossary() {
  return useContext(GlossaryContext)
}

/** True for a target where "?" is a character the player is typing, not a shortcut. */
function isTypingTarget(target) {
  if (!target || !target.tagName) return false
  const tag = target.tagName.toUpperCase()
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable === true
}

/**
 * Owns the combat glossary panel (issue #507).
 *
 * The panel is rendered here rather than by whichever component opened it:
 * the two entry points sit in different subtrees — the `?` in the fight-status
 * strip (RightPanel → Battlefield) and every dotted term in a move card's
 * unavailability reason (LeftPanel → CombatMovePanel) — and both must open the
 * *same* panel, above both panels' stacking contexts.
 *
 * `openGlossary(entryId)` scrolls the panel to that entry, which is how a
 * tooltip hands off from its one-sentence answer to the full one.
 */
export function GlossaryProvider({ children }) {
  const [openState, setOpenState] = useState(null)
  // Where focus was when the panel opened, so closing returns it there rather
  // than dumping the player at the top of the document mid-fight.
  const openerRef = useRef(null)
  // Mirrors `openState !== null` so re-opening an already-open panel (a second
  // "?" press, or a tooltip handing off) does not overwrite the recorded opener
  // with something inside the panel itself.
  const isOpenRef = useRef(false)

  const openGlossary = useCallback((entryId = null) => {
    if (!isOpenRef.current) {
      isOpenRef.current = true
      openerRef.current = document.activeElement
    }
    setOpenState({ entryId: typeof entryId === 'string' ? entryId : null })
  }, [])

  const closeGlossary = useCallback(() => {
    isOpenRef.current = false
    setOpenState(null)
    const opener = openerRef.current
    openerRef.current = null
    if (opener && typeof opener.focus === 'function' && document.contains(opener)) {
      opener.focus()
    }
  }, [])

  // "?" opens the glossary from anywhere. Guarded on the event target so it
  // stays a literal question mark inside any field the player is typing in
  // (the glossary's own search box included).
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key !== '?' || event.ctrlKey || event.metaKey || event.altKey) return
      if (isTypingTarget(event.target)) return
      event.preventDefault()
      openGlossary(null)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [openGlossary])

  const value = useMemo(
    () => ({ openGlossary, closeGlossary, isGlossaryOpen: openState !== null }),
    [openGlossary, closeGlossary, openState]
  )

  return (
    <GlossaryContext.Provider value={value}>
      {children}
      {openState && (
        <CombatGlossaryPanel focusEntryId={openState.entryId} onClose={closeGlossary} />
      )}
    </GlossaryContext.Provider>
  )
}

export default GlossaryContext
