import { createContext, useContext, useEffect, useId, useRef, useState } from 'react'
import { colors, spacing } from '../styles/theme'

// A dialog's nearest enclosing BaseDialog (if any) is reached through this
// context, so a dialog rendered inside another one's children — e.g.
// NpcChatPanel's conversation history dialog, nested inside NpcChatPanel's
// own BaseDialog — can tell its ancestor to stand down for Escape/Tab while
// it itself is open. This can't be done with a plain "last one to register
// wins" stack: React fires a child component's mount effect *before* its
// parent's, so for a nested pair the parent would always register after
// (and thus "win over") the child, backwards from the visual stacking.
const DialogParentContext = createContext(null)

// Top-level (non-nested) dialogs, most-recently-mounted last. True siblings
// — e.g. InteractPanel's own dialog and the NpcChatPanel dialog it opens
// alongside it (a Fragment sibling, not nested in InteractPanel's children)
// — aren't related by the context above, so ordering them needs this stack
// instead. Sibling mount effects fire in normal temporal order, so "last
// pushed wins" is correct here.
const topLevelStack = []

const FOCUSABLE_SELECTOR =
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

function isVisible(el) {
    if (el.hidden || el.getAttribute('aria-hidden') === 'true') return false
    const { display, visibility } = el.style
    return display !== 'none' && visibility !== 'hidden'
}

function getFocusableElements(container) {
    if (!container) return []
    return Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR)).filter(isVisible)
}

/**
 * BaseDialog - A reusable dialog component to reduce DRY violations in modals.
 */
export default function BaseDialog({
    children,
    title,
    onClose,
    variant = 'default', // 'default', 'danger', 'warning', 'no-blur'
    maxWidth = '400px',
    width = '90%',
    minWidth = '0',
    zIndex = 1000,
    showCloseButton = true,
    padding = spacing.xl,
    className = '',
    contentClassName = '',
    containerCentered = false, // If true, positions relative to parent container instead of viewport
    allowInternalScroll = true, // If false, the children container won't have overflowY: auto
}) {
    // Unique per dialog instance: the NPC chat transcript stacks a second
    // BaseDialog on top of the panel, and a hardcoded id made the inner dialog
    // announce the outer one's title. Also doubles as this instance's entry
    // in topLevelStack below.
    const titleId = useId()
    const containerRef = useRef(null)
    const onCloseRef = useRef(onClose)
    useEffect(() => {
        onCloseRef.current = onClose
    })

    // If this dialog is nested inside another BaseDialog's children, this is
    // that ancestor's registration API; null for a top-level dialog.
    const parentDialog = useContext(DialogParentContext)
    const activeChildCountRef = useRef(0)
    // Lazy initializer runs once, so this stays referentially stable across
    // re-renders without reading a ref during render (refs may only be read
    // in effects/handlers, not render — see react-hooks/refs).
    const [dialogApi] = useState(() => ({
        registerChild: () => {
            activeChildCountRef.current += 1
        },
        unregisterChild: () => {
            activeChildCountRef.current = Math.max(0, activeChildCountRef.current - 1)
        },
    }))

    // Escape-to-close (innermost active dialog only) + a Tab/Shift+Tab focus
    // trap, plus moving focus into the dialog on mount and restoring it on
    // unmount.
    useEffect(() => {
        const container = containerRef.current
        if (!container) return

        const previouslyFocused = document.activeElement

        const focusables = getFocusableElements(container)
        if (focusables.length > 0) {
            focusables[0].focus()
        } else {
            container.focus()
        }

        if (parentDialog) {
            parentDialog.registerChild()
        } else {
            topLevelStack.push(titleId)
        }

        // A dialog only responds to Escape/Tab when it's the innermost
        // active one: it must have no active nested dialog of its own, and
        // (for a top-level dialog) must be the most-recently-mounted sibling.
        const isInnermostActive = () => {
            if (activeChildCountRef.current > 0) return false
            if (parentDialog) return true
            return topLevelStack[topLevelStack.length - 1] === titleId
        }

        const handleKeyDown = (e) => {
            if (!isInnermostActive()) return

            if (e.key === 'Escape') {
                e.stopPropagation()
                onCloseRef.current?.()
                return
            }

            if (e.key === 'Tab') {
                const current = getFocusableElements(container)
                if (current.length === 0) {
                    e.preventDefault()
                    return
                }
                const first = current[0]
                const last = current[current.length - 1]
                const active = document.activeElement
                if (e.shiftKey) {
                    if (active === first || !container.contains(active)) {
                        e.preventDefault()
                        last.focus()
                    }
                } else if (active === last || !container.contains(active)) {
                    e.preventDefault()
                    first.focus()
                }
            }
        }

        document.addEventListener('keydown', handleKeyDown)

        return () => {
            document.removeEventListener('keydown', handleKeyDown)
            if (parentDialog) {
                parentDialog.unregisterChild()
            } else {
                const idx = topLevelStack.indexOf(titleId)
                if (idx !== -1) topLevelStack.splice(idx, 1)
            }
            if (previouslyFocused && document.contains(previouslyFocused) && typeof previouslyFocused.focus === 'function') {
                previouslyFocused.focus()
            }
        }
        // titleId is stable for the component's lifetime (useId), so this
        // still runs exactly once per mount/unmount (plus again if this
        // instance's nesting context ever changes); onClose is read through
        // onCloseRef so it doesn't need to be a dependency here.
    }, [titleId, parentDialog])

    const isDanger = variant === 'danger'
    const isWarning = variant === 'warning'

    const themeStyles = {
        borderColor: isDanger ? colors.danger : (isWarning ? colors.secondary : colors.primary),
        backgroundColor: isDanger ? 'rgba(25, 10, 10, 0.98)' : (isWarning ? 'rgba(30, 15, 0, 0.95)' : colors.bg.main),
        glowColor: isDanger ? 'rgba(204, 0, 0, 0.6)' : (isWarning ? 'rgba(255, 170, 0, 0.5)' : colors.primary),
        titleColor: isDanger ? '#ff5555' : (isWarning ? colors.gold : colors.primary),
        overlayColor: 'rgba(0, 0, 0, 0.7)',
    }

    return (
        <div
            className={`modal-overlay ${className}`}
            style={{
                position: containerCentered ? 'absolute' : 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex,
                backgroundColor: themeStyles.overlayColor,
                backdropFilter: variant === 'no-blur' ? 'none' : 'blur(3px)',
            }}
            onClick={onClose}
        >
            <div
                ref={containerRef}
                className={`modal-content ${contentClassName}`}
                role="dialog"
                aria-modal="true"
                aria-labelledby={title ? titleId : undefined}
                tabIndex={-1}
                style={{
                    maxWidth,
                    minWidth,
                    width,
                    backgroundColor: themeStyles.backgroundColor,
                    border: `3px solid ${themeStyles.borderColor}`,
                    borderRadius: '8px',
                    padding: padding,
                    boxShadow: `0 0 20px ${themeStyles.glowColor}66`,
                    fontFamily: 'monospace',
                    display: 'flex',
                    flexDirection: 'column',
                    maxHeight: '90vh',
                    overflowX: 'auto',
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {(title || showCloseButton) && (
                    <div
                        style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            borderBottom: `2px solid ${themeStyles.borderColor}44`,
                            paddingBottom: spacing.sm,
                            marginBottom: spacing.md,
                        }}
                    >
                        {title && (
                            <div
                                id={titleId}
                                style={{
                                    fontSize: '20px',
                                    fontWeight: 'bold',
                                    color: themeStyles.titleColor,
                                    textAlign: 'center',
                                    flex: 1,
                                    textTransform: 'uppercase',
                                    letterSpacing: '1px'
                                }}
                            >
                                {title}
                            </div>
                        )}
                        {showCloseButton && (
                            <button
                                onClick={onClose}
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    color: colors.text.muted,
                                    cursor: 'pointer',
                                    fontSize: '22px',
                                    marginLeft: spacing.sm,
                                    padding: '4px',
                                    transition: 'color 0.2s'
                                }}
                                onMouseEnter={(e) => e.target.style.color = colors.text.highlight}
                                onMouseLeave={(e) => e.target.style.color = colors.text.muted}
                            >
                                ✕
                            </button>
                        )}
                    </div>
                )}

                <div style={{ flex: 1, overflowY: allowInternalScroll ? 'auto' : 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <DialogParentContext.Provider value={dialogApi}>
                        {children}
                    </DialogParentContext.Provider>
                </div>
            </div>
        </div>
    )
}
