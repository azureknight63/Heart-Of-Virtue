import { useState, useEffect } from 'react'
import apiEndpoints from '../api/endpoints'

export default function InteractPanel({ location, onClose, onEventsTriggered, onInteractionComplete, onRefetch }) {
    const [targets, setTargets] = useState([])
    const [selectedTarget, setSelectedTarget] = useState(null)
    const [interactionOutput, setInteractionOutput] = useState(null)
    const [loading, setLoading] = useState(false)
    const [isLocked, setIsLocked] = useState(false)
    const [error, setError] = useState(null)
    const [quantity, setQuantity] = useState(1)
    const [showQuantityInput, setShowQuantityInput] = useState(false)
    const [pendingAction, setPendingAction] = useState(null)

    useEffect(() => {
        if (location) {
            const npcs = (location.npcs || []).map(n => ({ ...n, type: 'npc' }))
            const objects = (location.objects || []).map(o => ({ ...o, type: 'object' }))
            const items = (location.items || []).map(i => ({ ...i, type: 'item' }))

            // Filter out hidden entities if the API sends them
            const allTargets = [...npcs, ...objects, ...items].filter(t => !t.hidden)
            setTargets(allTargets)

            // Update selected target if it's still in the room (to get updated count/desc)
            if (selectedTarget) {
                let updatedTarget = allTargets.find(t => t.id === selectedTarget.id)
                
                // Fallback: if ID changed (e.g. server reloaded objects), try finding by name and type
                if (!updatedTarget) {
                    updatedTarget = allTargets.find(t => t.name === selectedTarget.name && t.type === selectedTarget.type)
                }

                if (updatedTarget) {
                    // Only update if something actually changed to avoid infinite loops
                    const hasChanged = updatedTarget.count !== selectedTarget.count || 
                                     updatedTarget.description !== selectedTarget.description ||
                                     updatedTarget.id !== selectedTarget.id

                    if (hasChanged) {
                        setSelectedTarget(updatedTarget)
                    }
                } else if (!interactionOutput) {
                    // Only clear if we're not showing an interaction result
                    setSelectedTarget(null)
                }
            }
        }
    }, [location, interactionOutput, selectedTarget])

    const handleTargetClick = (target) => {
        setSelectedTarget(target)
        setError(null)
        setShowQuantityInput(false)
    }

    const handleActionClick = async (action, qty = null) => {
        if (isLocked) return

        // Check if we need to ask for quantity
        const isStackableAction = ['take', 'pickup', 'drop'].some(a => action.toLowerCase().includes(a))
        if (isStackableAction && selectedTarget.count > 1 && qty === null) {
            setPendingAction(action)
            setQuantity(selectedTarget.count) // Default to all
            setShowQuantityInput(true)
            return
        }

        setInteractionOutput(null)
        setError(null)
        setLoading(true)
        setShowQuantityInput(false)
        
        try {
            const response = await apiEndpoints.world.interact(selectedTarget.id, action, qty)
            const data = response.data

            if (data.success) {
                setInteractionOutput(data.message || 'Action completed.')

                // Check if this action should lock the panel (e.g. item moved)
                const lockingActions = ['take', 'pickup', 'drop', 'equip', 'unequip', 'consume']
                if (lockingActions.some(a => action.toLowerCase().includes(a))) {
                    // If we took/dropped fewer than all, don't lock
                    const currentCount = parseInt(selectedTarget.count) || 1
                    const requestedQty = parseInt(qty) || 0
                    
                    if (requestedQty > 0 && requestedQty < currentCount) {
                        setIsLocked(false)
                    } else {
                        setIsLocked(true)
                    }
                }

                // Refresh room data to update items/npcs/objects lists
                if (onRefetch) {
                    await onRefetch()
                }

                // After interaction, trigger room events
                try {
                    const eventsResponse = await apiEndpoints.world.getEvents()
                    const eventsData = eventsResponse.data
                    if (eventsData.success && eventsData.events && eventsData.events.length > 0) {
                        // Filter events with output text
                        const eventsWithOutput = eventsData.events.filter(
                            event => (event.output_text && event.output_text.trim().length > 0) || event.needs_input
                        )

                        if (eventsWithOutput.length > 0 && onEventsTriggered) {
                            onEventsTriggered(eventsWithOutput)
                        }
                    }
                } catch (eventsErr) {
                    console.error('Failed to trigger events:', eventsErr)
                    // Don't show error to user, events are optional
                }

                // Notify parent that interaction completed (for combat status check)
                if (onInteractionComplete) {
                    onInteractionComplete()
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
        setIsLocked(false)
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
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                        <span style={{ fontWeight: 'bold' }}>
                                            {target.name} {target.count > 1 ? `(x${target.count})` : ''}
                                        </span>
                                        {target.description && (
                                            <span style={{ 
                                                fontSize: '11px', 
                                                color: '#888', 
                                                maxWidth: '300px',
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                whiteSpace: 'nowrap'
                                            }}>
                                                {target.description}
                                            </span>
                                        )}
                                    </div>
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
                                {selectedTarget.name} {selectedTarget.count > 1 ? `(x${selectedTarget.count})` : ''}
                            </span>
                        </div>

                        {/* Target Description */}
                        {selectedTarget.description && (
                            <div style={{
                                color: '#aaa',
                                fontSize: '13px',
                                fontStyle: 'italic',
                                fontFamily: 'monospace',
                                padding: '0 4px',
                                lineHeight: '1.4',
                            }}>
                                {selectedTarget.description}
                            </div>
                        )}

                        {/* Quantity Input */}
                        {showQuantityInput && (
                            <div style={{
                                backgroundColor: 'rgba(50, 25, 0, 0.5)',
                                border: '1px solid #ff9933',
                                borderRadius: '4px',
                                padding: '12px',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '8px',
                                animation: 'fadeIn 0.3s ease-out',
                            }}>
                                <div style={{ color: '#ffcc88', fontSize: '13px', fontFamily: 'monospace' }}>
                                    How many would you like to {pendingAction}? (Available: {selectedTarget.count})
                                </div>
                                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                    <input
                                        type="number"
                                        min="1"
                                        max={selectedTarget.count}
                                        value={quantity}
                                        onChange={(e) => setQuantity(Math.min(selectedTarget.count, Math.max(1, parseInt(e.target.value) || 1)))}
                                        style={{
                                            backgroundColor: '#221100',
                                            border: '1px solid #ff9933',
                                            color: '#ffff00',
                                            padding: '4px 8px',
                                            borderRadius: '4px',
                                            width: '80px',
                                            fontFamily: 'monospace',
                                        }}
                                        autoFocus
                                    />
                                    <button
                                        onClick={() => handleActionClick(pendingAction, quantity)}
                                        style={{
                                            padding: '4px 12px',
                                            backgroundColor: '#ff9933',
                                            color: '#000',
                                            border: 'none',
                                            borderRadius: '4px',
                                            cursor: 'pointer',
                                            fontWeight: 'bold',
                                            fontFamily: 'monospace',
                                        }}
                                    >
                                        Confirm
                                    </button>
                                    <button
                                        onClick={() => setShowQuantityInput(false)}
                                        style={{
                                            padding: '4px 12px',
                                            backgroundColor: 'transparent',
                                            color: '#ff9933',
                                            border: '1px solid #ff9933',
                                            borderRadius: '4px',
                                            cursor: 'pointer',
                                            fontFamily: 'monospace',
                                        }}
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        )}

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
                                        disabled={loading || isLocked}
                                        style={{
                                            padding: '10px 16px',
                                            backgroundColor: 'rgba(100, 50, 0, 0.3)',
                                            border: `1px solid ${isLocked ? '#444' : '#ff9933'}`,
                                            borderRadius: '4px',
                                            color: isLocked ? '#666' : '#ffcc88',
                                            fontFamily: 'monospace',
                                            fontSize: '13px',
                                            cursor: (loading || isLocked) ? 'not-allowed' : 'pointer',
                                            textTransform: 'uppercase',
                                            fontWeight: 'bold',
                                            opacity: (loading || isLocked) ? 0.6 : 1,
                                            flex: '1 0 auto',
                                            textAlign: 'center',
                                        }}
                                        onMouseEnter={(e) => !loading && !isLocked && (e.target.style.backgroundColor = 'rgba(150, 80, 0, 0.5)')}
                                        onMouseLeave={(e) => !loading && !isLocked && (e.target.style.backgroundColor = 'rgba(100, 50, 0, 0.3)')}
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
        let wordsAdded = 0

        const intervalId = setInterval(() => {
            if (wordsAdded >= words.length) {
                setIsComplete(true)
                clearInterval(intervalId)
                return
            }

            // Capture the word to add in this tick's closure
            const wordToAdd = words[wordsAdded]
            
            setDisplayedText(prev => {
                return prev ? `${prev} ${wordToAdd}` : wordToAdd
            })

            wordsAdded++
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
