import React, { useState, useEffect, useRef } from 'react'
import { useWorldInteract } from '../hooks/useWorldInteract'
import BaseDialog from './BaseDialog'
import NpcChatPanel from './NpcChatPanel'
import BookReaderDialog, { stripBookWrapper } from './BookReaderDialog'
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
const SHOP_KEYWORDS = new Set(['buy', 'sell', 'trade'])

// Keywords that all open the SAME conversation. `handleActionClick` routes
// every one of them to the LLM chat panel, so an NPC carrying more than one
// rendered two buttons that did the identical thing — which is how the
// nomad-camp NPCs shipped a duplicate "chat" beside their "talk". The backend
// data fix landed, but content drifts and the frontend should not depend on it.
const CHAT_KEYWORDS = new Set(['talk', 'chat'])

/**
 * The action buttons a target actually earns, de-duplicated.
 *
 * Several separate reductions, in one place because they all answer "should
 * this keyword get a button". One bullet per `return false` in the filter,
 * each led by the identifier that clause turns on rather than by its position,
 * so the two lists are matched by name and a reordering cannot transpose them:
 *
 *   - `is_container` — a container's own Loot / Take_all duplicate the
 *     contents list it already renders.
 *   - `action_aliases` — aliases the engine marks as aliases are folded into
 *     their primary. NOTE: this is live for objects and items, whose
 *     serializers forward the field, and INERT for NPCs —
 *     `src/api/serializers/npc_serializer.py` forwards `keywords` and never
 *     emits `action_aliases`, so the check reads `undefined` and passes
 *     everything through. That is why the chat collapse below cannot be
 *     delegated to it.
 *   - `CHAT_KEYWORDS` / `chatKept` — the two chat aliases collapse to ONE
 *     keyword, and the survivor is CHOSEN, not first-won: "talk" beats "chat"
 *     whenever both are served, in whichever order the payload lists them, so
 *     the button always reads "Talk". A lone "chat" survives on its own so the
 *     action stays reachable. A plain `new Set(keywords)` would NOT have
 *     caught the reported duplicate — "talk" and "chat" are distinct strings
 *     that merely share a handler — and this is the half that matters.
 *   - `seen.has` — case-folded duplicates keep their FIRST spelling:
 *     `['Open', 'open']` renders one button reading "Open".
 *
 * `tests/test_jambo_tent_navigation.py` parses these clauses out of the source
 * and asserts every one of them is named above, so a rule added without a
 * bullet fails there rather than leaving this list quietly short.
 *
 * Exported because it is a pure function over one serialized row and is worth
 * asserting on directly — a rendered-button count cannot say WHICH rule
 * dropped a keyword.
 *
 * @param {Object} target - The selected room target as the serializers sent it.
 * @returns {string[]} Keywords to render, in served order and original casing.
 */
export function actionKeywords(target) {
    const seen = new Set()
    const keywords = target?.keywords || []
    // Collapse the "talk"/"chat" aliases into ONE control, independent of the
    // LLM capability flag. Both verbs converge on the backend chat fallback
    // (NPC.talk / ConversationalNPCMixin.chat — the latter calls talk() when
    // the LLM panel is not opened), so rendering both is a duplicate button
    // with no distinct outcome. Prefer the "Talk" spelling when present (keep
    // the first "talk" entry's original casing); a lone legacy "chat" is
    // preserved so the action stays reachable.
    const chatKw = keywords.filter((k) => CHAT_KEYWORDS.has(String(k).toLowerCase()))
    // Prefer the canonical Talk label when both aliases are present, even if
    // an older serialized payload listed Chat first.
    const chatKept = chatKw.find((k) => String(k).toLowerCase() === 'talk') || chatKw[0]
    return keywords.filter((keyword) => {
        const action = String(keyword).toLowerCase()
        if (target?.is_container && (action === 'loot' || action === 'take_all')) return false
        if (target?.action_aliases?.includes(keyword)) return false
        if (CHAT_KEYWORDS.has(action) && keyword !== chatKept) return false
        if (seen.has(action)) return false
        seen.add(action)
        return true
    })
}

function InteractPanel({
    location,
    onInteractionComplete,
    onEventsTriggered,
    onRefetch,
    onClose,
    onOpenShop,
    initialTarget = null,
    onTypingChange
}) {
    const [targets, setTargets] = useState([])
    const [selectedTarget, setSelectedTarget] = useState(initialTarget || null)
    const [showHistory, setShowHistory] = useState(false)
    const [quantity, setQuantity] = useState(1)
    const [showQuantityInput, setShowQuantityInput] = useState(false)
    const [pendingAction, setPendingAction] = useState(null)
    const [showChatPanel, setShowChatPanel] = useState(false)
    const [bookReaderData, setBookReaderData] = useState(null)
    const [searchHovered, setSearchHovered] = useState(false)

    // Guards the location-sync effect against clobbering a local update.
    // Declared above useWorldInteract because onObjectStateUpdate (defined in
    // that call) sets it.
    const isSyncingTarget = useRef(false)

    const {
        loading,
        isLocked,
        error,
        interactionOutput,
        interactionHistory,
        searchLoading,
        searchOutput,
        takingAllItems,
        search: runSearch,
        takeAll: runTakeAll,
        takeOne,
        interact: runInteract,
        reset: resetInteraction,
    } = useWorldInteract({
        onRefetch,
        onEventsTriggered,
        onInteractionComplete,
        onTypingChange,
        onClose,
        onObjectStateUpdate: (objectState) => {
            // Patching selectedTarget changes its identity, and the location-sync
            // effect lists selectedTarget in its deps — so it re-runs immediately,
            // while `location` still holds the PRE-interaction row (the refetch
            // has not landed yet). Its `hasChanged` check then sees
            // stale.state !== patched.state and overwrites the patch with the
            // stale row, so an unlocked chest silently reverted to offering
            // "Unlock" forever — the exact round trip this patch exists to avoid.
            // Raising the same guard the sync path uses makes that re-run a no-op;
            // the next genuine `location` change syncs normally.
            isSyncingTarget.current = true
            setSelectedTarget(prev => prev ? {
                ...prev,
                keywords: objectState.keywords ?? prev.keywords,
                locked: objectState.locked ?? prev.locked,
                state: objectState.state ?? prev.state,
            } : prev)
            setTimeout(() => {
                isSyncingTarget.current = false
            }, 0)
        },
    })

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
                    // Target is gone! Clear it so we don't try to interact with it again.
                    // This also takes NpcChatPanel off screen without routing
                    // through its End Conversation handler — which used to leave
                    // the server-side conversation open. useNpcChat's unmount
                    // cleanup now ends it, so the clear stays unconditional
                    // rather than being gated on `showChatPanel` (a value this
                    // effect does not depend on and must not start reading stale).
                    setSelectedTarget(null)
                }
            }
        }
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
        resetInteraction()
        setShowHistory(false)
        setShowQuantityInput(false)
        setPendingAction(null)
        setQuantity(1)
        setShowChatPanel(false)
    }

    const handleSearch = async () => {
        await runSearch()
    }

    const handleTakeAll = async () => {
        if (isLocked || takingAllItems) return

        const takeableItems = targets.filter(t => t.type === 'item')
        if (takeableItems.length === 0) return

        setShowQuantityInput(false)
        await runTakeAll(takeableItems)
    }

    const handleActionClick = async (action, qty = null) => {
        if (isLocked) return

        // Handle take_all specially for ground items
        if (action === 'take_all_ground') {
            await handleTakeAll()
            return
        }

        // Route shop keywords to ShopDialog instead of world.interact
        if (SHOP_KEYWORDS.has(action.toLowerCase()) && onOpenShop && selectedTarget) {
            const initialTab = action.toLowerCase() === 'sell' ? 'sell' : 'buy'
            onOpenShop(selectedTarget.id, selectedTarget.name, initialTab)
            return
        }

        // Open LLM chat panel for talk or chat action on LLM-capable NPCs
        if (
            CHAT_KEYWORDS.has(action.toLowerCase()) &&
            selectedTarget?.llm_chat_enabled &&
            selectedTarget?.loquacity_available !== false
        ) {
            setShowChatPanel(true)
            return
        }

        // Reading a book (or other readable object) lying in a room should
        // open the same dedicated Read panel as reading from inventory,
        // instead of dumping the full text into the interaction log (issue #326).
        if (action.toLowerCase() === 'read' && selectedTarget) {
            const data = await runInteract(selectedTarget, action, qty)
            if (data?.success) {
                setBookReaderData({ title: selectedTarget.name, text: stripBookWrapper(data.message) })
                resetInteraction()
            }
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

        setShowQuantityInput(false)
        await runInteract(selectedTarget, action, qty)
    }

    const handleBack = () => {
        setSelectedTarget(null)
        resetInteraction()
        setShowHistory(false)
    }

    const getTargetIcon = (type) => {
        switch (type) {
            case 'npc': return '👤'
            case 'item': return '📦'
            case 'object': return '🪵'
            default: return '❓'
        }
    }

    // The NPC's class key, which is what `/api/npc/chat/open` receives as
    // `npc_key`; the instance id would 404 it. `npc_class` is the remap of the
    // serializer's `type` applied above, and the display name is the fallback
    // for a row that predates it. Written once because the panel needs the same
    // value twice — as its React key and as its `npcId` — and the two silently
    // disagreeing would remount on every render.
    const chatNpcId = selectedTarget?.npc_class || selectedTarget?.name

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
                        {/* Search Area Button — room-level action, always visible */}
                        <div style={{ marginBottom: spacing.xs }}>
                            <button
                                onClick={handleSearch}
                                disabled={searchLoading}
                                onMouseEnter={() => setSearchHovered(true)}
                                onMouseLeave={() => setSearchHovered(false)}
                                style={{
                                    width: '100%',
                                    padding: `${spacing.sm} ${spacing.md}`,
                                    backgroundColor: searchHovered ? colors.alpha.info[10] : 'transparent',
                                    border: `1.5px solid ${colors.accent}`,
                                    borderRadius: '8px',
                                    color: colors.accent,
                                    fontFamily: fonts.main,
                                    fontSize: '13px',
                                    fontWeight: 'bold',
                                    cursor: searchLoading ? 'default' : 'pointer',
                                    transition: 'all 0.2s',
                                    textTransform: 'uppercase',
                                    letterSpacing: '1px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: spacing.sm,
                                    opacity: searchLoading ? 0.7 : 1,
                                    boxShadow: searchHovered ? `0 0 10px ${colors.alpha.info[40]}` : 'none',
                                }}
                            >
                                🔍 {searchLoading ? 'Searching...' : 'Search Area'}
                            </button>
                            {searchOutput && (
                                <div style={{
                                    marginTop: spacing.xs,
                                    padding: `${spacing.xs} ${spacing.md}`,
                                    backgroundColor: 'rgba(0, 204, 255, 0.05)',
                                    border: `1px solid ${colors.alpha.info[20]}`,
                                    borderRadius: '6px',
                                    fontSize: '12px',
                                    color: colors.accent,
                                    fontFamily: fonts.main,
                                    fontStyle: 'italic',
                                }}>
                                    {searchOutput}
                                </div>
                            )}
                        </div>
                        {targets.filter(t => t.type === 'item' && !t.is_container).length > 1 && (
                            <GameButton
                                onClick={() => handleActionClick('take_all_ground')}
                                variant="primary"
                                disabled={loading || takingAllItems || isLocked}
                                style={{
                                    padding: spacing.md,
                                    width: '100%',
                                    marginBottom: spacing.xs
                                }}
                            >
                                {takingAllItems ? '⏳ Taking...' : '📦 Take All Items'}
                            </GameButton>
                        )}
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
                                                        await takeOne(item.id, item.name)
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
                                actionKeywords(selectedTarget)
                                    .map((keyword) => (
                                        <GameButton
                                            // Keyed on the keyword, which
                                            // `actionKeywords` has already made
                                            // unique, rather than on the index —
                                            // the list is rebuilt whenever the
                                            // room resyncs.
                                            key={keyword}
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

                {/* Loading indicator */}
                {loading && !interactionOutput && (
                    <div style={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        padding: spacing.xl,
                        gap: spacing.md,
                    }}>
                        <div style={{
                            width: '24px',
                            height: '24px',
                            border: `3px solid ${colors.border.light}`,
                            borderTopColor: colors.secondary,
                            borderRadius: '50%',
                            animation: 'interact-spin 0.8s linear infinite',
                        }} />
                        <GameText variant="muted" size="sm" style={{ fontStyle: 'italic' }}>
                            ...
                        </GameText>
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
                // Keyed on the NPC so switching targets remounts the panel
                // instead of mutating its props in place — a conversation is
                // per-NPC state, and reusing the instance left the previous
                // NPC's portraits and options on screen for the whole of the
                // new `/open` round trip.
                key={chatNpcId}
                npcId={chatNpcId}
                npcName={selectedTarget.name}
                onClose={() => {
                    setShowChatPanel(false)
                    if (onRefetch) onRefetch()
                }}
            />
        )}
        {bookReaderData && (
            <BookReaderDialog
                title={bookReaderData.title}
                text={bookReaderData.text}
                onClose={() => setBookReaderData(null)}
            />
        )}
    </>
    )
}

const spinKeyframes = `
@keyframes interact-spin {
  to { transform: rotate(360deg); }
}
`

// Inject keyframes once
if (typeof document !== 'undefined' && !document.getElementById('interact-panel-styles')) {
    const style = document.createElement('style')
    style.id = 'interact-panel-styles'
    style.textContent = spinKeyframes
    document.head.appendChild(style)
}

export default React.memo(InteractPanel)
