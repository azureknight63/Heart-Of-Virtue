import React, { useRef, useEffect } from 'react'
import useTypewriter from '../hooks/useTypewriter'
import { colors, spacing, fonts } from '../styles/theme'

const DAMAGE_PATTERN = /Jean suffers \d+ damage!/gi

/**
 * TypewriterOutput - Reusable component for displaying text with a typewriter effect
 *
 * @param {Function} [onDamageHit] - Called each time a "Jean suffers N damage!" line
 *                                   becomes fully visible in the typewriter output.
 *                                   Multiple hits in one stage stagger 300 ms apart.
 */
export default function TypewriterOutput({ text, speed = 30, style = {}, onComplete, formatter, onDamageHit }) {
    const { displayedText, isComplete, finishImmediately } = useTypewriter(text, speed)
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
                    animation: 'blink 1s step-end infinite'
                }}>&nbsp;</span>
            )}
            <div ref={bottomRef} style={{ height: 0, overflow: 'hidden' }} />
            <style>{`
                @keyframes blink { 50% { opacity: 0; } }
            `}</style>
        </div>
    )
}
