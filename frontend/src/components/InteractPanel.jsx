import { useState, useEffect, useRef } from 'react'
import apiEndpoints from '../api/endpoints'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'

/**
 * InteractPanel - Main interface for interacting with entities in the current room
 * Allows selecting targets (NPCs, Objects, Items) and performing actions on them
 */
export default function InteractPanel({ location, onClose, onEventsTriggered, onInteractionComplete, onRefetch, initialTarget }) {
    const [targets, setTargets] = useState([])
    const [selectedTarget, setSelectedTarget] = useState(initialTarget || null)
    const [interactionOutput, setInteractionOutput] = useState(null)
    const [interactionHistory, setInteractionHistory] = useState([])
    const [showHistory, setShowHistory] = useState(false)
    const [loading, setLoading] = useState(false)
    const [isLocked, setIsLocked] = useState(false)
    const [error, setError] = useState(null)
    const [quantity, setQuantity] = useState(1)
    const [showQuantityInput, setShowQuantityInput] = useState(false)
    const [pendingAction, setPendingAction] = useState(null)
    const historyRef = useRef(null)

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
                    const hasChanged =
                        updatedTarget.count !== selectedTarget.count ||
                        updatedTarget.description !== selectedTarget.description ||
                        updatedTarget.id !== selectedTarget.id ||
                        updatedTarget.state !== selectedTarget.state ||
                        (updatedTarget.contents?.length !== selectedTarget.contents?.length)

                    if (hasChanged) {
                        setSelectedTarget(updatedTarget)
                    }
                } else {
                    // Target is gone! Clear it so we don't try to interact with it again
                    setSelectedTarget(null)
                }
            }
        }
    }, [location, selectedTarget])

    const handleTargetClick = (target) => {
        setSelectedTarget(target)
        setInteractionOutput(null)
        setInteractionHistory([])
        setShowHistory(false)
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
                const message = data.message || 'Action completed.'
                setInteractionOutput(message)
                setInteractionHistory(prev => [...prev, message])

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

                // After interaction, trigger room events if any were returned in the response
                if (data.events_triggered && data.events_triggered.length > 0 && onEventsTriggered) {
                    onEventsTriggered(data.events_triggered)
                }

                // Also check for global room events
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

                        // Refetch location after events process (they may modify world state)
                        if (onRefetch) {
                            await onRefetch()
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
                setError(data.error || data.message || 'Interaction failed')
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
        setInteractionHistory([])
        setShowHistory(false)
        setError(null)
        setIsLocked(false)
    }

    const getTargetIcon = (type) => {
        switch (type) {
            case 'npc': return '👤'
            case 'item': return '📦'
            case 'object': return '🪵'
            default: return '❓'
        }
    }

    const getTargetColor = (type) => {
        switch (type) {
            case 'npc': return '#00ff88'
            case 'item': return '#00ccff'
            case 'object': return '#ffaa00'
            default: return '#ffffff'
        }
    }

    return (
        <BaseDialog
            title={selectedTarget ? `✨ ${selectedTarget.name}` : "👋 INTERACT"}
            onClose={onClose}
            maxWidth="500px"
            zIndex={2000}
        >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {/* Error State */}
                {error && (
                    <div style={{
                        color: '#ff4444',
                        fontSize: '13px',
                        padding: '10px',
                        backgroundColor: 'rgba(255, 0, 0, 0.1)',
                        borderRadius: '6px',
                        border: '1px solid rgba(255, 68, 68, 0.3)',
                        fontFamily: 'monospace',
                    }}>
                        ⚠️ {error}
                    </div>
                )}

                {!selectedTarget ? (
                    // Target Selection List
                    <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '8px',
                        maxHeight: '60vh',
                        overflowY: 'auto',
                        padding: '4px',
                    }}>
                        {targets.length === 0 ? (
                            <div style={{
                                color: '#666',
                                fontSize: '15px',
                                fontStyle: 'italic',
                                textAlign: 'center',
                                padding: '40px 20px',
                            }}>
                                There is nothing here to interact with.
                            </div>
                        ) : (
                            targets.map((target, idx) => (
                                <GameButton
                                    key={`${target.id}-${idx}`}
                                    onClick={() => handleTargetClick(target)}
                                    variant="secondary"
                                    style={{
                                        padding: '12px 16px',
                                        textAlign: 'left',
                                        justifyContent: 'flex-start',
                                        width: '100%',
                                    }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', width: '100%' }}>
                                        <div style={{ fontSize: '20px' }}>{getTargetIcon(target.type)}</div>
                                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                                            <div style={{ fontWeight: 'bold', fontSize: '14px', color: '#ffeeaa' }}>
                                                {target.name} {target.count > 1 ? `(x${target.count})` : ''}
                                            </div>
                                            {target.description && (
                                                <div style={{ fontSize: '11px', color: '#888', fontStyle: 'italic', maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                    {target.description}
                                                </div>
                                            )}
                                        </div>
                                        <div style={{
                                            fontSize: '10px',
                                            color: getTargetColor(target.type),
                                            border: `1px solid ${getTargetColor(target.type)}`,
                                            padding: '2px 6px',
                                            borderRadius: '4px',
                                            textTransform: 'uppercase',
                                            fontWeight: 'bold',
                                            letterSpacing: '1px',
                                        }}>
                                            {target.type}
                                        </div>
                                    </div>
                                </GameButton>
                            ))
                        )}
                    </div>
                ) : (
                    // Interaction View
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div style={{ display: 'flex', gap: '8px' }}>
                            <GameButton onClick={handleBack} variant="secondary" style={{ padding: '4px 12px', fontSize: '12px' }}>
                                ← Back
                            </GameButton>
                        </div>

                        {/* Target Description */}
                        {selectedTarget.description && (
                            <div style={{
                                color: '#ccc',
                                fontSize: '14px',
                                padding: '12px',
                                backgroundColor: 'rgba(0,0,0,0.2)',
                                borderRadius: '8px',
                                borderLeft: `4px solid ${getTargetColor(selectedTarget.type)}`,
                                lineHeight: '1.5',
                            }}>
                                {selectedTarget.description}
                            </div>
                        )}

                        {/* Stackable Action Quantity Input */}
                        {showQuantityInput && (
                            <div style={{
                                backgroundColor: 'rgba(255, 170, 0, 0.1)',
                                border: '1px solid #ffaa00',
                                borderRadius: '8px',
                                padding: '16px',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '12px',
                            }}>
                                <div style={{ color: '#ffcc88', fontSize: '13px', fontWeight: 'bold' }}>
                                    How many would you like to {pendingAction}?
                                    <span style={{ color: '#888', fontWeight: 'normal', display: 'block' }}>Available: {selectedTarget.count}</span>
                                </div>
                                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                    <input
                                        type="number"
                                        min="1"
                                        max={selectedTarget.count}
                                        value={quantity}
                                        onChange={(e) => setQuantity(Math.min(selectedTarget.count, Math.max(1, parseInt(e.target.value) || 1)))}
                                        style={{
                                            backgroundColor: '#1a1a1a',
                                            border: '1px solid #ffaa00',
                                            color: '#ffcc00',
                                            padding: '8px 12px',
                                            borderRadius: '6px',
                                            width: '80px',
                                            fontSize: '16px',
                                            fontFamily: 'monospace',
                                            outline: 'none',
                                        }}
                                        autoFocus
                                    />
                                    <GameButton onClick={() => handleActionClick(pendingAction, quantity)} variant="primary">
                                        Confirm
                                    </GameButton>
                                    <GameButton onClick={() => setShowQuantityInput(false)} variant="secondary">
                                        Cancel
                                    </GameButton>
                                </div>
                            </div>
                        )}

                        {/* Container Contents */}
                        {selectedTarget.is_container && selectedTarget.opened && selectedTarget.contents && (
                            <div style={{
                                padding: '12px',
                                backgroundColor: 'rgba(0, 255, 136, 0.05)',
                                border: '1px solid rgba(0, 255, 136, 0.2)',
                                borderRadius: '8px',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '10px',
                            }}>
                                <div style={{
                                    color: '#00ff88',
                                    fontSize: '11px',
                                    fontWeight: 'bold',
                                    textTransform: 'uppercase',
                                    letterSpacing: '1px',
                                    borderBottom: '1px solid rgba(0, 255, 136, 0.1)',
                                    paddingBottom: '4px',
                                }}>
                                    Container Contents
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    {selectedTarget.contents.length > 0 ? (
                                        selectedTarget.contents.map((item, idx) => (
                                            <div key={idx} style={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                                backgroundColor: 'rgba(0,0,0,0.3)',
                                                padding: '6px 10px',
                                                borderRadius: '6px',
                                            }}>
                                                <span style={{ color: '#ffeeaa', fontSize: '13px' }}>
                                                    {item.name} {item.count > 1 ? `x${item.count}` : ''}
                                                </span>
                                                <GameButton
                                                    onClick={async (e) => {
                                                        e.stopPropagation()
                                                        setLoading(true)
                                                        try {
                                                            const response = await apiEndpoints.world.interact(item.id, 'take')
                                                            if (response.data.success) {
                                                                setInteractionOutput(response.data.message || `Took ${item.name}`)
                                                                if (onRefetch) await onRefetch()
                                                            } else {
                                                                setError(response.data.error || 'Failed to take item')
                                                            }
                                                        } catch (err) {
                                                            setError('Network error')
                                                        } finally {
                                                            setLoading(false)
                                                        }
                                                    }}
                                                    disabled={loading}
                                                    variant="secondary"
                                                    style={{ padding: '2px 8px', fontSize: '10px' }}
                                                >
                                                    TAKE
                                                </GameButton>
                                            </div>
                                        ))
                                    ) : (
                                        <div style={{ color: '#666', fontSize: '13px', fontStyle: 'italic', textAlign: 'center' }}>
                                            The container is empty.
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Action Buttons */}
                        <div style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: '10px',
                        }}>
                            {selectedTarget.keywords && selectedTarget.keywords.length > 0 ? (
                                selectedTarget.keywords
                                    .filter(keyword => !selectedTarget.action_aliases?.includes(keyword))
                                    .map((keyword, idx) => (
                                        <GameButton
                                            key={idx}
                                            onClick={() => handleActionClick(keyword)}
                                            disabled={loading || isLocked}
                                            variant="primary"
                                            style={{
                                                flex: '1 0 120px',
                                                textTransform: 'uppercase',
                                                fontSize: '13px',
                                                padding: '12px',
                                                opacity: (loading || isLocked) ? 0.6 : 1,
                                            }}
                                        >
                                            {keyword}
                                        </GameButton>
                                    ))
                            ) : (
                                <div style={{ color: '#666', fontSize: '13px', fontStyle: 'italic', width: '100%', textAlign: 'center', padding: '10px' }}>
                                    No actions available for this target.
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Interaction Output & History */}
                {(interactionOutput || interactionHistory.length > 0) && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {/* History Toggle Header */}
                        {interactionHistory.length > 1 && (
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 4px' }}>
                                <div style={{ color: '#888', fontSize: '10px', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                    {showHistory ? 'Interaction History' : 'Last Message'}
                                </div>
                                <button
                                    onClick={() => setShowHistory(!showHistory)}
                                    style={{
                                        background: 'none',
                                        border: 'none',
                                        color: '#ffaa00',
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        cursor: 'pointer',
                                        padding: '4px 8px',
                                        borderRadius: '4px',
                                        backgroundColor: 'rgba(255, 170, 0, 0.1)',
                                        textTransform: 'uppercase',
                                        transition: 'all 0.2s ease',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '4px'
                                    }}
                                >
                                    {showHistory ? '↩ Hide History' : `📜 View History (${interactionHistory.length})`}
                                </button>
                            </div>
                        )}

                        {showHistory ? (
                            <div
                                ref={(el) => {
                                    if (el) el.scrollTop = el.scrollHeight;
                                }}
                                style={{
                                    padding: '16px',
                                    backgroundColor: 'rgba(0, 0, 0, 0.4)',
                                    border: '1px solid rgba(255, 170, 0, 0.3)',
                                    borderRadius: '8px',
                                    color: '#ffcc88',
                                    fontFamily: 'monospace',
                                    fontSize: '14px',
                                    lineHeight: '1.6',
                                    maxHeight: '300px',
                                    overflowY: 'auto',
                                    boxShadow: 'inset 0 2px 10px rgba(0,0,0,0.5)',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '12px',
                                    scrollbarWidth: 'thin',
                                    scrollbarColor: '#ffaa00 rgba(0,0,0,0.2)'
                                }}
                            >
                                {interactionHistory.map((msg, idx) => (
                                    <div key={idx} style={{
                                        paddingBottom: idx === interactionHistory.length - 1 ? '0' : '12px',
                                        borderBottom: idx === interactionHistory.length - 1 ? 'none' : '1px solid rgba(255, 170, 0, 0.1)',
                                        whiteSpace: 'pre-wrap',
                                        opacity: idx === interactionHistory.length - 1 ? 1 : 0.7
                                    }}>
                                        {msg}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            interactionOutput && (
                                <TypewriterOutput text={interactionOutput} />
                            )
                        )}
                    </div>
                )}
            </div>
        </BaseDialog>
    )
}

/**
 * TypewriterOutput - Sub-component for displaying interaction messages with a typing effect
 */
function TypewriterOutput({ text }) {
    const [displayedText, setDisplayedText] = useState('')
    const [isComplete, setIsComplete] = useState(false)
    const intervalRef = useRef(null)

    useEffect(() => {
        setDisplayedText('')
        setIsComplete(false)

        if (!text) return

        const words = text.split(' ')
        let wordsAdded = 0

        intervalRef.current = setInterval(() => {
            if (wordsAdded >= words.length) {
                setIsComplete(true)
                if (intervalRef.current) clearInterval(intervalRef.current)
                return
            }

            const wordToAdd = words[wordsAdded]
            setDisplayedText(prev => prev ? `${prev} ${wordToAdd}` : wordToAdd)
            wordsAdded++
        }, 30)

        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current)
        }
    }, [text])

    const finishImmediately = () => {
        if (!isComplete) {
            if (intervalRef.current) clearInterval(intervalRef.current)
            setDisplayedText(text)
            setIsComplete(true)
        }
    }

    return (
        <div
            onClick={finishImmediately}
            style={{
                marginTop: '8px',
                padding: '16px',
                backgroundColor: 'rgba(0, 0, 0, 0.4)',
                border: '1px solid rgba(255, 170, 0, 0.3)',
                borderRadius: '8px',
                color: '#ffcc88',
                fontFamily: 'monospace',
                fontSize: '14px',
                lineHeight: '1.6',
                whiteSpace: 'pre-wrap',
                maxHeight: '200px',
                overflowY: 'auto',
                cursor: isComplete ? 'default' : 'pointer',
                boxShadow: 'inset 0 2px 10px rgba(0,0,0,0.5)',
                position: 'relative',
            }}
        >
            {displayedText}
            {!isComplete && (
                <span style={{
                    display: 'inline-block',
                    width: '8px',
                    height: '14px',
                    backgroundColor: '#ffaa00',
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
