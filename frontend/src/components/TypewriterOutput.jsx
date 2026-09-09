import React, { useRef, useEffect } from 'react'
import useTypewriter from '../hooks/useTypewriter'
import { colors, spacing, fonts } from '../styles/theme'
import { usePreferences } from '../context/PreferencesContext'
import { msPerChar } from '../utils/textPacing'

const DAMAGE_PATTERN = /Jean suffers \d+ damage!/gi

/**
 * TypewriterOutput - Reusable component for displaying text with a typewriter effect
 *
 * Speed comes from the player's TEXT SPEED setting unless a caller passes one
 * (issue #538 item 1). Every narrative typewriter in the app renders through
 * this component, so honouring the setting here is what makes one control
 * govern all of them -- an explicit `speed` is for a caller that must pin the
 * rate for a reason of its own, such as skipping a scene with `0`.
 *
 * @param {Function} [onDamageHit] - Called each time a "Jean suffers N damage!" line
 *                                   becomes fully visible in the typewriter output.
 *                                   Multiple hits in one stage stagger 300 ms apart.
 */
export default function TypewriterOutput({ text, speed, style = {}, onComplete, formatter, onDamageHit }) {
    const { textSpeed } = usePreferences()
    // `??` not `||`: a caller-supplied 0 means "instant", not "unset".
    const { displayedText, isComplete, finishImmediately } = useTypewriter(text, speed ?? msPerChar(textSpeed))
    const bottomRef = React.useRef(null)
    const triggeredDamageCount = useRef(0)

    // Reset damage tracker whenever a new text block starts
    useEffect(() => {
        triggeredDamageCount.current = 0
    }, [text])

    // Fire onDamageHit each time a new damage line appears in the scrolling text
    useEffect(() => {
        if (!onDamageHit) return
        const matches = displayedText.match(DAMAGE_PATTERN) || []
        const newHits = matches.length - triggeredDamageCount.current
        if (newHits > 0) {
            for (let i = 0; i < newHits; i++) {
                setTimeout(() => onDamageHit(), i * 300)
            }
            triggeredDamageCount.current = matches.length
        }
    }, [displayedText, onDamageHit])

    React.useEffect(() => {
        if (!isComplete) {
            bottomRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' })
        }
    }, [displayedText, isComplete])

    React.useEffect(() => {
        if (isComplete && onComplete) {
            onComplete()
            // Final scroll to ensure everything is visible
            bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
        }
    }, [isComplete, onComplete])

    return (
        <div
            data-testid="event-text-container"
            onClick={finishImmediately}
            style={{
                padding: spacing.md,
                backgroundColor: colors.bg.panelDeep,
                border: `1px solid ${colors.border.light}`,
                borderRadius: '8px',
                color: colors.text.main,
                fontFamily: fonts.main,
                fontSize: '14px',
                lineHeight: '1.6',
                whiteSpace: 'pre-wrap',
                minHeight: '4em',
                cursor: isComplete ? 'default' : 'pointer',
                position: 'relative',
                ...style,
            }}
        >
            {formatter ? formatter(displayedText) : displayedText}
            {!isComplete && (
                <span style={{
                    borderRight: `3px solid ${colors.secondary}`,
                    marginLeft: '4px',
                    // `blink` is index.css's, not a component-local copy.
                    // Keyframe names are document-global no matter which
                    // element injects them, so the `@keyframes blink` that used
                    // to sit right here shadowed the stylesheet's definition
                    // app-wide for as long as any typewriter was mid-line —
                    // the same collision the NPC chat panel's `pulse` caused
                    // for BattlefieldGrid's reticle.
                    animation: 'blink 1s step-end infinite'
                }}>&nbsp;</span>
            )}
            <div ref={bottomRef} style={{ height: 0, overflow: 'hidden' }} />
        </div>
    )
}
