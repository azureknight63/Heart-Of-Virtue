import React from 'react'
import useTypewriter from '../hooks/useTypewriter'
import { colors } from '../styles/theme'

/**
 * TypewriterOutput - Reusable component for displaying text with a typewriter effect
 */
export default function TypewriterOutput({ text, speed = 30, style = {}, onComplete, formatter }) {
    const { displayedText, isComplete, finishImmediately } = useTypewriter(text, speed)

    React.useEffect(() => {
        if (isComplete && onComplete) {
            onComplete()
        }
    }, [isComplete, onComplete])

    return (
        <div
            onClick={finishImmediately}
            style={{
                padding: '12px',
                backgroundColor: 'rgba(0, 0, 0, 0.7)',
                border: `1px solid ${colors.secondary}`,
                borderRadius: '8px',
                color: colors.gold,
                fontFamily: 'monospace',
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
                    borderRight: `3px solid ${colors.primary}`,
                    marginLeft: '4px',
                    animation: 'blink 1s step-end infinite'
                }}>&nbsp;</span>
            )}
            <style>{`
                @keyframes blink { 50% { opacity: 0; } }
            `}</style>
        </div>
    )
}
