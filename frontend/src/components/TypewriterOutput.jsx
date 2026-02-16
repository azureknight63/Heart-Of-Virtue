import React from 'react'
import useTypewriter from '../hooks/useTypewriter'
import { colors, spacing, fonts } from '../styles/theme'

/**
 * TypewriterOutput - Reusable component for displaying text with a typewriter effect
 */
export default function TypewriterOutput({ text, speed = 30, style = {}, onComplete, formatter }) {
    const { displayedText, isComplete, finishImmediately } = useTypewriter(text, speed)
    const bottomRef = React.useRef(null)

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
