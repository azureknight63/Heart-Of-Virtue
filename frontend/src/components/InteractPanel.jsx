import { useState, useEffect } from 'react'

export default function InteractPanel({ location, onClose, onEventsTriggered }) {
    const [targets, setTargets] = useState([])
    const [selectedTarget, setSelectedTarget] = useState(null)
    const [interactionOutput, setInteractionOutput] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    useEffect(() => {
        if (location) {
            const npcs = (location.npcs || []).map(n => ({ ...n, type: 'npc' }))
            const objects = (location.objects || []).map(o => ({ ...o, type: 'object' }))
            const items = (location.items || []).map(i => ({ ...i, type: 'item' }))

            // Filter out hidden entities if the API sends them
            const allTargets = [...npcs, ...objects, ...items].filter(t => !t.hidden)
            setTargets(allTargets)
        }
    }, [location])

    const handleTargetClick = (target) => {
        setSelectedTarget(target)
        setError(null)
    }

    const handleActionClick = async (action) => {
        setLoading(true)
        try {
            const token = localStorage.getItem('authToken')
            const response = await fetch('http://localhost:5000/api/world/interact', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({
                    target_id: selectedTarget.id,
                    action: action
                })
            })

            const data = await response.json()
            if (response.ok) {
                setInteractionOutput(data.message)

                // After interaction, trigger room events
                try {
                    const eventsResponse = await fetch('http://localhost:5000/api/world/events', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`,
                        }
                    })

                    const eventsData = await eventsResponse.json()
                    if (eventsResponse.ok && eventsData.events && eventsData.events.length > 0) {
                        // Filter events with output text
                        const eventsWithOutput = eventsData.events.filter(
                            event => event.output_text && event.output_text.trim().length > 0
                        )

                        if (eventsWithOutput.length > 0 && onEventsTriggered) {
                            onEventsTriggered(eventsWithOutput)
                        }
                    }
                } catch (eventsErr) {
                    console.error('Failed to trigger events:', eventsErr)
                    // Don't show error to user, events are optional
                }
            } else {
                setError(data.error || 'Interaction failed')
            }
        } catch (err) {
            console.error('Interaction error:', err)
            setError('Network error')
        } finally {
            setLoading(false)
        }
    }

    const handleBack = () => {
        setSelectedTarget(null)
        setInteractionOutput(null)
        setError(null)
    }

    const closeOutput = () => {
        setInteractionOutput(null)
    }

    return (
        <div
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.7)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 1000,
            }}
            onClick={onClose}
        >
            <div
                style={{
                    backgroundColor: 'rgba(20, 10, 5, 0.95)',
                    border: '2px solid #ffaa00',
                    borderRadius: '8px',
                    padding: '16px',
                    width: '90%',
                    maxWidth: '500px',
                    maxHeight: '80vh',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    boxShadow: '0 0 20px rgba(255, 170, 0, 0.4)',
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
                    paddingBottom: '8px',
                    marginBottom: '4px',
                }}>
                    <div style={{
                        color: '#ffff00',
                        fontWeight: 'bold',
                        fontSize: '16px',
                        fontFamily: 'monospace',
                    }}>
                        👋 INTERACT
                    </div>
                    <button
                        onClick={onClose}
                        style={{
                            padding: '4px 8px',
                            backgroundColor: '#cc4400',
                            color: '#ffff00',
                            border: '1px solid #ff6600',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                            fontWeight: 'bold',
                        }}
                    >
                        Close
                    </button>
                </div>

                {/* Error State */}
                {error && (
                    <div style={{
                        color: '#ff6666',
                        fontSize: '12px',
                        fontFamily: 'monospace',
                        padding: '8px',
                        backgroundColor: 'rgba(100, 0, 0, 0.2)',
                        borderRadius: '4px',
                        border: '1px solid #ff6666',
                    }}>
                        {error}
                    </div>
                )}

                {/* Content Area */}
                {!selectedTarget ? (
                    // Target List
                    <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '8px',
                        overflowY: 'auto',
                        minHeight: '200px',
                    }}>
                        {targets.length === 0 ? (
                            <div style={{
                                color: '#888',
                                fontSize: '14px',
                                fontStyle: 'italic',
                                textAlign: 'center',
                                padding: '20px',
                            }}>
                                Nothing to interact with here.
                            </div>
                        ) : (
                            targets.map((target, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => handleTargetClick(target)}
                                    style={{
                                        padding: '12px',
                                        backgroundColor: 'rgba(100, 50, 0, 0.3)',
                                        border: '1px solid #ff9933',
                                        borderRadius: '4px',
                                        color: '#ffcc88',
                                        fontFamily: 'monospace',
                                        fontSize: '14px',
                                        cursor: 'pointer',
                                        textAlign: 'left',
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center',
                                        transition: 'all 0.2s',
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.backgroundColor = 'rgba(150, 80, 0, 0.5)'
                                        e.currentTarget.style.borderColor = '#ffff00'
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.backgroundColor = 'rgba(100, 50, 0, 0.3)'
                                        e.currentTarget.style.borderColor = '#ff9933'
                                    }}
                                >
                                    <span style={{ fontWeight: 'bold' }}>{target.name}</span>
                                    <span style={{
                                        fontSize: '10px',
                                        color: target.type === 'npc' ? '#00ff88' : (target.type === 'item' ? '#00ccff' : '#ffaa00'),
                                        border: `1px solid ${target.type === 'npc' ? '#00ff88' : (target.type === 'item' ? '#00ccff' : '#ffaa00')}`,
                                        padding: '2px 4px',
                                        borderRadius: '3px',
                                    }}>
                                        {target.type === 'npc' ? 'NPC' : (target.type === 'item' ? 'ITEM' : 'OBJ')}
                                    </span>
                                </button>
                            ))
                        )}
                    </div>
                ) : (
                    // Action Selection & Output
                    <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '12px',
                    }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '12px',
                            borderBottom: '1px solid #664400',
                            paddingBottom: '8px',
                        }}>
                            <button
                                onClick={handleBack}
                                style={{
                                    padding: '4px 8px',
                                    backgroundColor: 'transparent',
                                    color: '#ffcc88',
                                    border: '1px solid #ff9933',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '12px',
                                    fontFamily: 'monospace',
                                }}
                            >
                                ← Back
                            </button>
                            <span style={{
                                color: '#ffff00',
                                fontWeight: 'bold',
                                fontSize: '14px',
                                fontFamily: 'monospace',
                            }}>
                                {selectedTarget.name}
                            </span>
                        </div>

                        <div style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: '8px',
                        }}>
                            {selectedTarget.keywords && selectedTarget.keywords.length > 0 ? (
                                selectedTarget.keywords.map((keyword, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => handleActionClick(keyword)}
                                        disabled={loading}
                                        style={{
                                            padding: '10px 16px',
                                            backgroundColor: 'rgba(100, 50, 0, 0.3)',
                                            border: '1px solid #ff9933',
                                            borderRadius: '4px',
                                            color: '#ffcc88',
                                            fontFamily: 'monospace',
                                            fontSize: '13px',
                                            cursor: loading ? 'wait' : 'pointer',
                                            textTransform: 'uppercase',
                                            fontWeight: 'bold',
                                            opacity: loading ? 0.7 : 1,
                                            flex: '1 0 auto',
                                            textAlign: 'center',
                                        }}
                                        onMouseEnter={(e) => !loading && (e.target.style.backgroundColor = 'rgba(150, 80, 0, 0.5)')}
                                        onMouseLeave={(e) => !loading && (e.target.style.backgroundColor = 'rgba(100, 50, 0, 0.3)')}
                                    >
                                        {keyword}
                                    </button>
                                ))
                            ) : (
                                <div style={{ color: '#999', fontSize: '12px', fontStyle: 'italic' }}>
                                    No obvious actions available.
                                </div>
                            )}
                        </div>

                        {/* Interaction Output Area - Inline */}
                        {interactionOutput && (
                            <TypewriterOutput text={interactionOutput} />
                        )}
                    </div>
                )}
            </div>
            <style>{`
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(5px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            `}</style>
        </div>
    )
}

// Sub-component for the typewriter effect
function TypewriterOutput({ text }) {
    const [displayedText, setDisplayedText] = useState('')
    const [isComplete, setIsComplete] = useState(false)

    useEffect(() => {
        setDisplayedText('')
        setIsComplete(false)

        if (!text) return

        const words = text.split(' ')
        let currentIndex = 0

        const intervalId = setInterval(() => {
            if (currentIndex >= words.length) {
                setIsComplete(true)
                clearInterval(intervalId)
                return
            }

            // Add next word
            setDisplayedText(prev => {
                const nextWord = words[currentIndex]
                if (nextWord === undefined) return prev
                return prev ? `${prev} ${nextWord}` : nextWord
            })

            currentIndex++
        }, 50) // Adjust speed here (ms per word)

        return () => clearInterval(intervalId)
    }, [text])

    const finishImmediately = () => {
        if (!isComplete) {
            setDisplayedText(text)
            setIsComplete(true)
        }
    }

    return (
        <div
            onClick={finishImmediately}
            style={{
                marginTop: '12px',
                padding: '12px',
                backgroundColor: 'rgba(0, 0, 0, 0.6)',
                border: '1px solid #ffaa00',
                borderRadius: '4px',
                color: '#ffcc88',
                fontFamily: 'monospace',
                fontSize: '14px',
                lineHeight: '1.5',
                whiteSpace: 'pre-wrap',
                maxHeight: '300px',
                overflowY: 'auto',
                boxShadow: 'inset 0 0 10px rgba(0,0,0,0.8)',
                animation: 'fadeIn 0.3s ease-in-out',
                cursor: isComplete ? 'default' : 'pointer',
            }}
        >
            {displayedText}
            {!isComplete && <span style={{ borderRight: '2px solid #ffaa00', marginLeft: '2px', animation: 'blink 1s step-end infinite' }}>&nbsp;</span>}
            <style>{`
                @keyframes blink { 50% { border-color: transparent; } }
            `}</style>
        </div>
    )
}
