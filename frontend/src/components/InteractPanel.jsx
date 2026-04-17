import React, { useState, useEffect, useRef } from 'react'
import apiEndpoints from '../api/endpoints'
import BaseDialog from './BaseDialog'
import NpcChatPanel from './NpcChatPanel'
import GameButton from './GameButton'
import GameText from './GameText'
import GamePanel from './GamePanel'
import TypewriterOutput from './TypewriterOutput'
import { colors, spacing, commonStyles, fonts, shadows } from '../styles/theme'
import { renderTextWithLinks, getEntityColor } from '../utils/entityUtils'

/**
 * InteractPanel - Dedicated panel for interacting with objects, NPCs, and items
 * Provides target selection, detailed item/object info, and action execution
 */
function InteractPanel({
    location,
    onInteractionComplete,
    onEventsTriggered,
    onRefetch,
    onClose,
    initialTarget = null,
    history = [],
    onTypingChange
}) {
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
    const [showChatPanel, setShowChatPanel] = useState(false)
    const [takingAllItems, setTakingAllItems] = useState(false)

    // Ref to track if we're currently syncing to prevent infinite loops
    const isSyncingTarget = useRef(false)
    // Ref to store previous selected target for comparison
    const prevSelectedTargetRef = useRef(selectedTarget)
    // Tracks whether the panel was ever opened with targets present.
    // Distinguishes "opened on an already-empty tile" (no auto-close) from
    // "opened with targets that later all disappeared" (auto-close allowed).
    const hasHadTargetsRef = useRef(false)

    useEffect(() => {
        if (location) {
            const npcs = (location.npcs || []).map(n => ({ ...n, npc_class: n.type, type: 'npc' }))
            const objects = (location.objects || []).map(o => ({ ...o, type: 'object' }))
            const items = (location.items || []).map(i => ({ ...i, type: 'item' }))

            // Filter out hidden entities if the API sends them
            const allTargets = [...npcs, ...objects, ...items].filter(t => !t.hidden)
            setTargets(allTargets)

            // Update selected target if it's still in the room (to get updated count/desc)
            if (selectedTarget && !isSyncingTarget.current) {
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
                        isSyncingTarget.current = true
                        setSelectedTarget(updatedTarget)
                        // Reset the flag after the state update
                        setTimeout(() => {
                            isSyncingTarget.current = false
                        }, 0)
                    }
                } else {
                    // Target is gone! Clear it so we don't try to interact with it again
                    setSelectedTarget(null)
                }
            }
        }
        // Update the ref for next comparison
        prevSelectedTargetRef.current = selectedTarget
    }, [location, selectedTarget])

    // Track whether we have ever had targets so the auto-close effect can
    // tell apart "opened on empty tile" from "targets disappeared after open".
    useEffect(() => {
        if (targets.length > 0) {
            hasHadTargetsRef.current = true
        }
    }, [targets.length])

    // Automatically close the panel if there is nothing left to interact with,
    // but ONLY if the user has actually performed an action OR if targets were
    // present when the panel opened (to prevent instant closing on empty tiles).
    useEffect(() => {
        if (location && targets.length === 0 && !selectedTarget && !error && !loading && !showHistory) {
            // If the panel was opened on an already-empty tile and no interaction
            // has been performed, don't auto-close — let the user read the message.
            if (!interactionOutput && interactionHistory.length === 0 && !hasHadTargetsRef.current) {
                return;
            }
            
            const delay = interactionOutput ? 3000 : 0;
            const timer = setTimeout(() => {
                if (targets.length === 0 && !selectedTarget && !error && !loading && !showHistory) {
                    onClose();
                }
            }, delay);
            return () => clearTimeout(timer);
        }
    }, [targets.length, selectedTarget, interactionOutput, interactionHistory.length, error, loading, showHistory, location, onClose]);

    const handleTargetClick = (target) => {
        setSelectedTarget(target)
        setInteractionOutput(null)
        setInteractionHistory([])
        setShowHistory(false)
        setError(null)
        setShowQuantityInput(false)
        setPendingAction(null)
        setQuantity(1)
        setIsLocked(false)
        setShowChatPanel(false)
    }

    const handleTakeAll = async () => {
        if (isLocked || takingAllItems) return

        const takeableItems = targets.filter(t => t.type === 'item')
        if (takeableItems.length === 0) return

        setTakingAllItems(true)
        setInteractionOutput(null)
        setError(null)
        setShowQuantityInput(false)

        for (const item of takeableItems) {
            try {
                const response = await apiEndpoints.world.interact(item.id, 'take', item.count)
                const data = response.data

                if (data.success) {
                    const message = data.message || `Took ${item.name}`
                    setInteractionOutput(message)
                    if (onTypingChange) onTypingChange(true)
                    setInteractionHistory(prev => [...prev, message])
                } else {
                    // Stop on error
                    setError(data.error || data.message || 'Failed to take item')
                    break
                }
            } catch (err) {
                console.error('Take all error:', err)
                setError('Network error')
                break
            }
        }

        if (onRefetch) await onRefetch()
        if (onInteractionComplete) onInteractionComplete()
        setTakingAllItems(false)
    }

    const handleActionClick = async (action, qty = null) => {
        if (isLocked) return

        // Handle take_all specially for ground items
        if (action === 'take_all') {
            await handleTakeAll()
            return
        }

        // Open LLM chat panel for talk action on LLM-capable NPCs
        if (action.toLowerCase() === 'talk' && selectedTarget?.llm_chat_enabled && selectedTarget?.loquacity_available !== false) {
            setShowChatPanel(true)
            return
        }

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
                if (onTypingChange) onTypingChange(true)
                setInteractionHistory(prev => [...prev, message])

                // Update local object state immediately from the response so action
                // buttons (e.g. "open" after "unlock") appear without requiring a
                // back-and-re-select round trip.
                if (data.object_state) {
                    setSelectedTarget(prev => prev ? {
                        ...prev,
                        keywords: data.object_state.keywords ?? prev.keywords,
                        locked: data.object_state.locked ?? prev.locked,
                        state: data.object_state.state ?? prev.state,
                    } : prev)
                }

                // Check if this action should lock the panel (e.g. item moved)
                const lockingActions = ['take', 'pickup', 'drop', 'equip', 'unequip', 'consume']
                if (lockingActions.some(a => action.toLowerCase().includes(a))) {
                    const currentCount = parseInt(selectedTarget.count) || 1
                    const requestedQty = parseInt(qty) || 0
                    if (requestedQty > 0 && requestedQty < currentCount) {
                        setIsLocked(false)
                    } else {
                        setIsLocked(true)
                    }
                }

                if (onRefetch) await onRefetch()
                if (data.events_triggered && data.events_triggered.length > 0 && onEventsTriggered) {
                    onEventsTriggered(data.events_triggered)
                }

                // Check for background events
                try {
                    const eventsResponse = await apiEndpoints.world.getEvents()
                    const eventsData = eventsResponse.data
                    if (eventsData.success && eventsData.events && eventsData.events.length > 0) {
                        const eventsWithOutput = eventsData.events.filter(
                            event => (event.output_text && event.output_text.trim().length > 0) || event.needs_input
                        )
                        if (eventsWithOutput.length > 0 && onEventsTriggered) {
                            onEventsTriggered(eventsWithOutput)
                        }
                        if (onRefetch) await onRefetch()
                    }
                } catch (eventsErr) {
                    console.error('Failed to trigger events:', eventsErr)
                }

                if (onInteractionComplete) onInteractionComplete()
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

    return (<>
        <BaseDialog
            title={selectedTarget ? `✨ ${selectedTarget.name}` : "👋 INTERACT"}
            onClose={onClose}
            maxWidth="500px"
            zIndex={2000}
        >
            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
                {/* Error State */}
                {error && (
                    <div style={{
                        ...commonStyles.errorBox,
                        padding: spacing.md,
                    }}>
                        <GameText variant="danger" size="sm" weight="bold">
                            ⚠️ {error}
                        </GameText>
                    </div>
                )}

                {!selectedTarget ? (
                    // Target Selection List
                    <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: spacing.sm,
                        maxHeight: '60vh',
                        overflowY: 'auto',
                        padding: spacing.xs,
                    }}>
                        {targets.length === 0 ? (
                            <div style={{ padding: '40px 20px' }}>
                                <GameText variant="muted" size="md" align="center" style={{ fontStyle: 'italic' }}>
                                    There is nothing here to interact with.
                                </GameText>
                            </div>
                        ) : (
                            targets.map((target, idx) => (
                                <GameButton
                                    key={`${target.id}-${idx}`}
                                    onClick={() => handleTargetClick(target)}
                                    variant="secondary"
                                    style={{
                                        padding: spacing.md,
                                        width: '100%',
                                    }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: spacing.md, width: '100%', textAlign: 'left' }}>
                                        <div style={{ fontSize: '20px' }}>{getTargetIcon(target.type)}</div>
                                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                                            <GameText variant="primary" size="sm" weight="bold">
                                                {target.name} {target.count > 1 ? `(x${target.count})` : ''}
                                            </GameText>
                                            {target.description && (
                                                <GameText variant="muted" size="xs" style={{ fontStyle: 'italic', maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                    {target.description}
                                                </GameText>
                                            )}
                                        </div>
                                        <div style={{
                                            fontSize: '10px',
                                            color: getEntityColor(target.type),
                                            border: `1px solid ${getEntityColor(target.type)}`,
                                            padding: '2px 6px',
                                            borderRadius: '4px',
                                            textTransform: 'uppercase',
                                            fontWeight: 'bold',
                                            letterSpacing: '1px',
                                            fontFamily: fonts.main,
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
                    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
                        <div style={{ display: 'flex', gap: spacing.sm }}>
                            <GameButton onClick={handleBack} variant="secondary" size="small">
                                ← Back
                            </GameButton>
                            {/* Take All Items button for ground items */}
                            {selectedTarget.type === 'item' && !selectedTarget.is_container && targets.filter(t => t.type === 'item').length > 1 && (
                                <GameButton
                                    onClick={() => handleActionClick('take_all')}
                                    variant="primary"
                                    size="small"
                                    disabled={loading || takingAllItems}
                                >
                                    {takingAllItems ? '⏳ Taking...' : '📦 Take All Items'}
                                </GameButton>
                            )}
                        </div>

                        {/* Target Description */}
                        {selectedTarget.description && (
                            <GamePanel variant="retro" style={{ borderLeft: `4px solid ${getEntityColor(selectedTarget.type)}` }}>
                                <GameText variant="primary" size="md" style={{ lineHeight: '1.5' }}>
                                    {renderTextWithLinks(selectedTarget.description, targets, handleTargetClick, selectedTarget)}
                                </GameText>
                            </GamePanel>
                        )}

                        {/* Stackable Action Quantity Input */}
                        {showQuantityInput && (
                            <GamePanel
                                style={{
                                    backgroundColor: 'rgba(255, 170, 0, 0.05)',
                                    borderColor: colors.secondary,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: spacing.md
                                }}
                            >
                                <GameText variant="warning" size="sm" weight="bold">
                                    How many would you like to {pendingAction}?
                                    <GameText variant="muted" size="xs" weight="normal" style={{ display: 'block' }}>
                                        Available: {selectedTarget.count}
                                    </GameText>
                                </GameText>
                                <div style={{ display: 'flex', gap: spacing.sm, alignItems: 'center' }}>
                                    <input
                                        type="number"
                                        min="1"
                                        max={selectedTarget.count}
                                        value={quantity}
                                        onChange={(e) => setQuantity(Math.min(selectedTarget.count, Math.max(1, parseInt(e.target.value) || 1)))}
                                        style={{
                                            backgroundColor: colors.bg.main,
                                            border: `1px solid ${colors.secondary}`,
                                            color: colors.gold,
                                            padding: '8px 12px',
                                            borderRadius: '6px',
                                            width: '80px',
                                            fontSize: '16px',
                                            fontFamily: fonts.main,
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
                            </GamePanel>
                        )}

                        {/* Container Contents */}
                        {selectedTarget.is_container && selectedTarget.opened && selectedTarget.contents && (
                            <GamePanel
                                style={{
                                    backgroundColor: 'rgba(0, 255, 136, 0.05)',
                                    borderColor: 'rgba(0, 255, 136, 0.2)',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: spacing.sm
                                }}
                            >
                                <div style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    borderBottom: `1px solid ${colors.border.light}`,
                                    paddingBottom: spacing.xs,
                                }}>
                                    <GameText variant="success" size="xs" weight="bold" style={{ textTransform: 'uppercase', letterSpacing: '1px' }}>
                                        Container Contents
                                    </GameText>
                                    {selectedTarget.contents.length > 1 && !selectedTarget.locked && (
                                        <GameButton
                                            onClick={() => handleActionClick('take_all')}
                                            disabled={loading}
                                            variant="secondary"
                                            size="small"
                                        >
                                            TAKE ALL
                                        </GameButton>
                                    )}
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
                                    {selectedTarget.contents.length > 0 ? (
                                        selectedTarget.contents.map((item, idx) => (
                                            <div key={idx} style={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                                backgroundColor: 'rgba(0,0,0,0.2)',
                                                padding: '6px 12px',
                                                borderRadius: '6px',
                                            }}>
                                                <GameText variant="primary" size="sm">
                                                    {item.name} {item.count > 1 ? `x${item.count}` : ''}
                                                </GameText>
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
                                                    size="small"
                                                >
                                                    TAKE
                                                </GameButton>
                                            </div>
                                        ))
                                    ) : (
                                        <GameText variant="muted" size="sm" align="center" style={{ fontStyle: 'italic', padding: spacing.md }}>
                                            The container is empty.
                                        </GameText>
                                    )}
                                </div>
                            </GamePanel>
                        )}

                        {/* Action Buttons */}
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing.md }}>
                            {selectedTarget.keywords && selectedTarget.keywords.length > 0 ? (
                                selectedTarget.keywords
                                    .filter(keyword => {
                                        const action = keyword.toLowerCase();
                                        if (selectedTarget.is_container && (action === 'loot' || action === 'take_all')) return false;
                                        return !selectedTarget.action_aliases?.includes(keyword);
                                    })
                                    .map((keyword, idx) => (
                                        <GameButton
                                            key={idx}
                                            onClick={() => handleActionClick(keyword)}
                                            disabled={loading || isLocked}
                                            variant="primary"
                                            style={{
                                                flex: '1 0 120px',
                                                padding: spacing.md,
                                                opacity: (loading || isLocked) ? 0.6 : 1,
                                            }}
                                        >
                                            {keyword}
                                        </GameButton>
                                    ))
                            ) : (
                                <GameText variant="muted" size="sm" align="center" style={{ width: '100%', fontStyle: 'italic', padding: spacing.md }}>
                                    No actions available for this target.
                                </GameText>
                            )}
                        </div>
                    </div>
                )}

                {/* Interaction Output & History */}
                {(interactionOutput || interactionHistory.length > 0) && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
                        {/* History Toggle Header */}
                        {interactionHistory.length > 1 && (
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 4px' }}>
                                <GameText variant="muted" size="xs" weight="bold" style={{ textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                    {showHistory ? 'Interaction History' : 'Last Message'}
                                </GameText>
                                <button
                                    onClick={() => setShowHistory(!showHistory)}
                                    style={{
                                        background: 'none',
                                        border: 'none',
                                        color: colors.secondary,
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        cursor: 'pointer',
                                        padding: '4px 8px',
                                        borderRadius: '4px',
                                        backgroundColor: colors.bg.highlight,
                                        textTransform: 'uppercase',
                                        transition: 'all 0.2s ease',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '4px',
                                        fontFamily: fonts.main,
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
                                    padding: spacing.lg,
                                    backgroundColor: colors.bg.panelHeavy,
                                    border: `1px solid ${colors.border.main}`,
                                    borderRadius: '8px',
                                    maxHeight: '300px',
                                    overflowY: 'auto',
                                    boxShadow: shadows.inset,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: spacing.md,
                                    scrollbarWidth: 'thin',
                                    scrollbarColor: `${colors.secondary} rgba(0,0,0,0.2)`
                                }}
                            >
                                {interactionHistory.map((msg, idx) => (
                                    <div key={idx} style={{
                                        paddingBottom: idx === interactionHistory.length - 1 ? '0' : spacing.md,
                                        borderBottom: idx === interactionHistory.length - 1 ? 'none' : `1px solid ${colors.border.light}`,
                                        whiteSpace: 'pre-wrap',
                                        opacity: idx === interactionHistory.length - 1 ? 1 : 0.7
                                    }}>
                                        <GameText variant="warning" size="md">
                                            {renderTextWithLinks(msg, targets, handleTargetClick)}
                                        </GameText>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            interactionOutput && (
                                <TypewriterOutput
                                    text={interactionOutput}
                                    onComplete={() => {
                                        if (onTypingChange) onTypingChange(false)
                                    }}
                                    formatter={(text) => (
                                        <GameText variant="warning" size="md">
                                            {renderTextWithLinks(text, targets, handleTargetClick)}
                                        </GameText>
                                    )}
                                />
                            )
                        )}
                    </div>
                )}
            </div>
        </BaseDialog>
        {showChatPanel && selectedTarget && (
            <NpcChatPanel
                npcId={selectedTarget.npc_class || selectedTarget.name}
                npcName={selectedTarget.name}
                onClose={() => {
                    setShowChatPanel(false)
                    if (onRefetch) onRefetch()
                }}
            />
        )}
    </>
    )
}

export default React.memo(InteractPanel)
