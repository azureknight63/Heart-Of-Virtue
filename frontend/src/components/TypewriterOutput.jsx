import React from 'react'
import useTypewriter from '../hooks/useTypewriter'
import { colors, shadows, spacing, fonts, commonStyles } from '../styles/theme'

/**
 * TypewriterOutput - Reusable component for displaying text with a typewriter effect
 */
export default function TypewriterOutput({ text, speed = 30, style = {}, onComplete }) {
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
                ...commonStyles.typewriterBox,
                cursor: isComplete ? 'default' : 'pointer',
                ...style,
            }}
        >
            {displayedText}
            {!isComplete && (
                <span style={{
                    display: 'inline-block',
                    width: '8px',
                    height: '14px',
                    backgroundColor: colors.secondary,
                    marginLeft: '4px',
                    verticalAlign: 'middle',
                    animation: 'blink 0.8s step-end infinite',
                }} />
            )}
            <style>{`
                @keyframes blink { 50% { opacity: 0; } }
            `}</style>
        </div>
    )
}
