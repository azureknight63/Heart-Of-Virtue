import { useState, useEffect } from 'react'

/**
 * EventDialog - Displays event output text and handles player input for events
 * Similar to InteractPanel but specifically for game events
 */
export default function EventDialog({ event, onClose, onChoice }) {
    const [displayedText, setDisplayedText] = useState('')
    const [isComplete, setIsComplete] = useState(false)
    const [showChoices, setShowChoices] = useState(false)

    // Extract event data
    const eventText = event?.output_text || event?.message || event?.description || ''
    const eventChoices = event?.choices || []
    const requiresInput = event?.requires_input || eventChoices.length > 0

    useEffect(() => {
        setDisplayedText('')
        setIsComplete(false)
        setShowChoices(false)

        if (!eventText) return

        const words = eventText.split(' ')
        let currentIndex = 0

        const intervalId = setInterval(() => {
            if (currentIndex >= words.length) {
                setIsComplete(true)
                // Show choices after text is complete if event requires input
                if (requiresInput) {
                    setShowChoices(true)
                }
                clearInterval(intervalId)
                return
            }

            // Add next word
            setDisplayedText(prev => {
                const nextWord = words[currentIndex]
                return prev ? `${prev} ${nextWord}` : nextWord
            })

            currentIndex++
        }, 50) // Adjust speed here (ms per word)

        return () => clearInterval(intervalId)
    }, [eventText, requiresInput])

    const finishImmediately = () => {
        if (!isComplete) {
            setDisplayedText(eventText)
            setIsComplete(true)
            if (requiresInput) {
                setShowChoices(true)
            }
        }
    }

    const handleChoice = (choice) => {
        if (onChoice) {
            onChoice(choice)
        }
    }

    const handleContinue = () => {
        if (!requiresInput && isComplete) {
            onClose()
        }
    }

    return (
        <div
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.85)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 2000,
            }}
            onClick={!requiresInput && isComplete ? handleContinue : finishImmediately}
        >
            <div
                style={{
                    backgroundColor: 'rgba(20, 10, 5, 0.98)',
                    border: '3px solid #ffaa00',
                    borderRadius: '12px',
                    padding: '24px',
                    width: '90%',
                    maxWidth: '700px',
                    maxHeight: '80vh',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '16px',
                    boxShadow: '0 0 30px rgba(255, 170, 0, 0.6), inset 0 0 20px rgba(0, 0, 0, 0.8)',
                    overflowY: 'auto',
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderBottom: '2px solid #ffaa00',
                    paddingBottom: '12px',
                }}>
                    <div style={{
                        color: '#ffff00',
                        fontWeight: 'bold',
                        fontSize: '18px',
                        fontFamily: 'monospace',
                        textShadow: '0 0 8px rgba(255, 255, 0, 0.8)',
                    }}>
                        ✨ {event?.name || 'Event'}
                    </div>
                    {!requiresInput && (
                        <button
                            onClick={onClose}
                            style={{
                                padding: '6px 12px',
                                backgroundColor: '#cc4400',
                                color: '#ffff00',
                                border: '2px solid #ff6600',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                fontSize: '14px',
                                fontFamily: 'monospace',
                                fontWeight: 'bold',
                                transition: 'all 0.2s',
                            }}
                            onMouseEnter={(e) => {
                                e.target.style.backgroundColor = '#ff5500'
                                e.target.style.boxShadow = '0 0 10px rgba(255, 85, 0, 0.8)'
                            }}
                            onMouseLeave={(e) => {
                                e.target.style.backgroundColor = '#cc4400'
                                e.target.style.boxShadow = 'none'
                            }}
                        >
                            Close
                        </button>
                    )}
                </div>

                {/* Event Text Output */}
                <div
                    onClick={finishImmediately}
                    style={{
                        padding: '16px',
                        backgroundColor: 'rgba(0, 0, 0, 0.7)',
                        border: '2px solid #ffaa00',
                        borderRadius: '8px',
                        color: '#ffcc88',
                        fontFamily: 'monospace',
                        fontSize: '16px',
                        lineHeight: '1.8',
                        whiteSpace: 'pre-wrap',
                        minHeight: '120px',
                        maxHeight: '400px',
                        overflowY: 'auto',
                        boxShadow: 'inset 0 0 15px rgba(0,0,0,0.9)',
                        cursor: isComplete ? 'default' : 'pointer',
                    }}
                >
                    {displayedText}
                    {!isComplete && (
                        <span style={{
                            borderRight: '3px solid #ffaa00',
                            marginLeft: '4px',
                            animation: 'blink 1s step-end infinite'
                        }}>&nbsp;</span>
                    )}
                </div>

                {/* Choices (if event requires input) */}
                {showChoices && eventChoices.length > 0 && (
                    <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '12px',
                        marginTop: '8px',
                    }}>
                        <div style={{
                            color: '#ffff00',
                            fontWeight: 'bold',
                            fontSize: '14px',
                            fontFamily: 'monospace',
                            textAlign: 'center',
                            marginBottom: '4px',
                        }}>
                            Choose your response:
                        </div>
                        {eventChoices.map((choice, idx) => (
                            <button
                                key={idx}
                                onClick={() => handleChoice(choice)}
                                style={{
                                    padding: '14px 20px',
                                    backgroundColor: 'rgba(100, 50, 0, 0.4)',
                                    border: '2px solid #ff9933',
                                    borderRadius: '6px',
                                    color: '#ffcc88',
                                    fontFamily: 'monospace',
                                    fontSize: '15px',
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                    fontWeight: 'bold',
                                    transition: 'all 0.2s',
                                }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.backgroundColor = 'rgba(150, 80, 0, 0.6)'
                                    e.currentTarget.style.borderColor = '#ffff00'
                                    e.currentTarget.style.boxShadow = '0 0 12px rgba(255, 255, 0, 0.5)'
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.backgroundColor = 'rgba(100, 50, 0, 0.4)'
                                    e.currentTarget.style.borderColor = '#ff9933'
                                    e.currentTarget.style.boxShadow = 'none'
                                }}
                            >
                                {choice.label || choice.text || choice}
                            </button>
                        ))}
                    </div>
                )}

                {/* Continue hint (if no choices required) */}
                {!requiresInput && isComplete && (
                    <div style={{
                        textAlign: 'center',
                        color: '#888',
                        fontSize: '13px',
                        fontStyle: 'italic',
                        marginTop: '8px',
                    }}>
                        Click anywhere to continue...
                    </div>
                )}

                <style>{`
          @keyframes blink {
            50% { border-color: transparent; }
          }
        `}</style>
            </div>
        </div>
    )
}
