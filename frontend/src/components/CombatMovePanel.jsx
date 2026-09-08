import React, { useState, useMemo, useEffect, useRef, useId } from 'react';
import { useAudio } from '../context/AudioContext';
import { colors, spacing, shadows, fonts } from '../styles/theme';
import GamePanel from './GamePanel';
import GameText from './GameText';
import GlossaryHelpButton from './GlossaryHelpButton';
import GlossaryText from './GlossaryText';
import { movesInGroup } from '../utils/categories';
import { displayNameOf, moveAvailability } from '../utils/combatMoveStatus';
import {
    STAGE_KEYS,
    getStageBeats,
    totalStageBeats,
    formatBeats,
    maxTotalStageBeats,
} from '../utils/moveCommitment';

// Stage -> color. Deliberately distinct from MOVE_CATEGORY_COLOR (categories.js) —
// this palette reads as a timeline (winding up -> striking -> recovering ->
// locked out), not a move-type identity, so it must not be confused with the
// category coloring used elsewhere on the same card.
const STAGE_COLORS = {
    prep: colors.accent,
    execute: colors.primary,
    recoil: colors.danger,
    cooldown: colors.text.muted,
};

const STAGE_LABELS = {
    prep: 'Prep',
    execute: 'Execute',
    recoil: 'Recoil',
    cooldown: 'Cooldown',
};

// Width of the fullest bar in the visible list (the move at maxTotal beats).
// Every other bar in the same panel is scaled relative to this, not to its
// own total — see maxTotalStageBeats' docstring for why per-card
// normalization would defeat the purpose.
const COMMITMENT_BAR_MAX_WIDTH = 120;
// Floor so a very cheap (or 0-beat) move still shows a visible sliver
// instead of disappearing next to a heavy move's full-width bar.
const COMMITMENT_BAR_MIN_WIDTH = 3;

/**
 * Compact "how long does this lock me out for" visual: a four-segment bar
 * (prep/execute/recoil/cooldown) whose overall length is proportioned
 * against `maxTotal` — the heaviest move currently visible in this panel —
 * so relative cost is readable without reading any numbers, plus a total
 * beat count for players who want the exact figure.
 */
const MoveCommitmentBar = ({ move, maxTotal }) => {
    const stageBeats = getStageBeats(move);
    const total = totalStageBeats(stageBeats);

    // Nothing in the visible list declares a duration (e.g. every move here
    // is missing stage_beats) — draw nothing rather than a row of empty bars.
    if (maxTotal <= 0) return null;

    const barWidth = total <= 0
        ? COMMITMENT_BAR_MIN_WIDTH
        : Math.max(COMMITMENT_BAR_MIN_WIDTH, (total / maxTotal) * COMMITMENT_BAR_MAX_WIDTH);

    const breakdown = STAGE_KEYS
        .map((key) => `${STAGE_LABELS[key]} ${formatBeats(stageBeats[key])}`)
        .join(' · ');

    return (
        <div
            data-testid="move-commitment-bar"
            data-total-beats={total}
            title={`${breakdown} (${formatBeats(total)} beats total lockout)`}
            style={{ display: 'flex', alignItems: 'center', gap: spacing.xs }}
        >
            <div
                style={{
                    width: `${COMMITMENT_BAR_MAX_WIDTH}px`,
                    height: '6px',
                    backgroundColor: 'rgba(255, 255, 255, 0.06)',
                    borderRadius: '2px',
                    overflow: 'hidden',
                    flexShrink: 0,
                }}
            >
                <div style={{ display: 'flex', width: `${barWidth}px`, height: '100%' }}>
                    {STAGE_KEYS.map((key) => {
                        const segmentWidth = total > 0 ? (stageBeats[key] / total) * barWidth : 0;
                        if (segmentWidth <= 0) return null;
                        return (
                            <div
                                key={key}
                                data-testid={`commitment-segment-${key}`}
                                style={{
                                    width: `${segmentWidth}px`,
                                    height: '100%',
                                    backgroundColor: STAGE_COLORS[key],
                                }}
                            />
                        );
                    })}
                </div>
            </div>
            <GameText variant="muted" size="xs" style={{ fontFamily: fonts.main, whiteSpace: 'nowrap' }}>
                {formatBeats(total)} beats
            </GameText>
        </div>
    );
};

// HeroPanel's radial category ring — the `<nav>` landmark it renders around the
// hero head. Read, never written: this panel needs to know where those buttons
// ARE (see useOccludedNavHandoff), and it must not reach into HeroPanel to
// restyle them.
const CATEGORY_NAV_SELECTOR = 'nav[aria-label="Game actions"] button';

// A click that lands on any of these inside the panel is the panel's own
// business, whatever it happens to be covering.
const PANEL_CONTROL_SELECTOR = 'button, a, input, select, textarea, [role="button"], [tabindex]';

/** The category nav button under a viewport point, or null. */
function categoryNavButtonAt(clientX, clientY) {
    if (typeof clientX !== 'number' || typeof clientY !== 'number') return null;
    for (const button of document.querySelectorAll(CATEGORY_NAV_SELECTOR)) {
        const rect = button.getBoundingClientRect();
        // A zero-sized rect means the button is not laid out (or jsdom gave up
        // on it); treating a point as "inside" it would hand every click to a
        // button nobody can see.
        if (rect.width <= 0 || rect.height <= 0) continue;
        if (clientX >= rect.left && clientX <= rect.right && clientY >= rect.top && clientY <= rect.bottom) {
            return button;
        }
    }
    return null;
}

/**
 * Give back the category-tab clicks this flyout steals (issue #557).
 *
 * The panel is `zIndex: 100` and centered over the whole left column; the
 * category buttons it opens from are `zIndex: 5` inside HeroPanel's hero-head
 * box, which sits in that same region. So a player who clicks a *different*
 * category tab while a panel is open hits the panel instead, and nothing at
 * all happens — a hit-test at the tab's centre reports the panel on top. The
 * handler that would have done the right thing already exists
 * (`LeftPanel.handleCombatMoveClick` swaps the open category, or closes the
 * panel when the same tab is clicked twice); it simply never hears the click.
 *
 * Raising the nav bar's z-index would be the structural fix, but it lives in
 * HeroPanel — so the panel takes responsibility for what it occludes instead:
 * on a click that lands on the panel's own inert chrome, hit-test the category
 * buttons and, if one is underneath, activate it.
 *
 * Only inert chrome is forwarded. Where the panel has its own control at that
 * point the intent is genuinely ambiguous, and a click that both cast a move
 * and switched category would be far worse than one dead click — so the
 * panel's control wins, and a tab fully covered by a move card stays occluded
 * until the nav bar is raised above the panel.
 *
 * `click`, deliberately, and not `pointerdown`: pointerdown is the FIRST event
 * of the gesture, and stopping it does not stop the mousedown/mouseup/click
 * that follow. Forwarding there swapped the open category and then let the
 * trailing click land on whatever the *replacement* panel had put under the
 * pointer — a move card, at which point one tap both switched category and
 * cast a move. Click is the last event of the gesture, so there is nothing
 * left behind it to misfire.
 */
function useOccludedNavHandoff(contentRef) {
    useEffect(() => {
        // GamePanel accepts no ref, so the ref sits on the header row and the
        // panel ROOT — whose padding ring is exactly the inert chrome the
        // reported hit-test landed on — is resolved from it.
        const content = contentRef.current;
        const panel = content?.closest('.game-panel') ?? content;
        if (!panel) return undefined;

        const handOff = (event) => {
            if (!panel.contains(event.target)) return;
            if (event.target.closest?.(PANEL_CONTROL_SELECTOR)) return;
            const navButton = categoryNavButtonAt(event.clientX, event.clientY);
            if (!navButton) return;
            // Capture phase on `document` runs before React's delegated
            // handler at the app root, so stopping here means the panel never
            // sees the click at all — then activate what the player aimed at.
            // The synthetic click this dispatches re-enters this handler with
            // the nav button as its target, which the containment check above
            // rejects immediately.
            event.stopPropagation();
            navButton.click();
        };

        document.addEventListener('click', handOff, true);
        return () => document.removeEventListener('click', handOff, true);
    }, [contentRef]);
}

// `isProcessing` is passed by LeftPanel while a move submission is in flight.
// Without it the panel stays live during the API round trip and a double-click
// submits two actions for one turn.
// `category` is a radial *button group* key, not an engine move category — the
// group → category mapping lives in utils/categories.js (CATEGORY_GROUPS), which
// LeftPanel's button gating reads too, so the two can never drift apart.
const CombatMovePanel = ({ moves, category, onMoveClick, onClose, onTargetHover, isProcessing = false }) => {
    const { playSFX } = useAudio();
    const [hoveredMoveName, setHoveredMoveName] = useState(null);
    const contentRef = useRef(null);
    // Base for the per-card reason ids that aria-describedby points at. useId
    // keeps them unique across concurrent panels and stable across re-renders.
    const reasonIdBase = useId();
    useOccludedNavHandoff(contentRef);

    const filteredMoves = useMemo(() => movesInGroup(moves, category), [moves, category]);
    // Shared scale across THIS panel's visible moves, not per-card — see
    // MoveCommitmentBar/maxTotalStageBeats for why per-card normalization
    // would make every move's bar look identical.
    const maxCommitmentBeats = useMemo(() => maxTotalStageBeats(filteredMoves), [filteredMoves]);

    return (
        <GamePanel
            glow
            borderVariant="bright"
            style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                zIndex: 100,
                minWidth: '320px',
                maxWidth: '450px',
                maxHeight: '80vh',
                display: 'flex',
                flexDirection: 'column',
                backgroundColor: colors.bg.panelDeep,
            }}
        >
            {/* ref: useOccludedNavHandoff resolves the panel root from here,
                because GamePanel takes no ref of its own. */}
            <div ref={contentRef} style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: spacing.md,
                borderBottom: `1px solid ${colors.border.light}`,
                paddingBottom: spacing.sm,
                flexShrink: 0,
            }}>
                <GameText variant="secondary" weight="bold" style={{ textTransform: 'uppercase' }}>
                    {category} MOVES
                </GameText>
                <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                    {/* Second entry point to the same glossary as the fight-status
                        strip's "?" — this panel is where the cooldown wording the
                        player asked about (#507) actually appears. */}
                    <GlossaryHelpButton />
                    <button
                        onClick={onClose}
                        style={{
                            background: 'none',
                            border: 'none',
                            color: colors.text.muted,
                            cursor: 'pointer',
                            fontSize: '18px',
                            padding: spacing.xs,
                        }}
                    >
                        ✕
                    </button>
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm, overflowY: 'auto', flex: 1, minHeight: 0 /* Critical: flex children need minHeight:0 to shrink below content size and enable scrolling */, paddingRight: spacing.sm, marginRight: `-${spacing.sm}` }}>
                {filteredMoves.length === 0 ? (
                    <GameText variant="muted" align="center" style={{ fontStyle: 'italic', padding: spacing.md }}>
                        No moves available in this category.
                    </GameText>
                ) : (
                    filteredMoves.map((move, index) => {
                        // Not `move.available !== false`: a targeted move can
                        // arrive advertised as available with nothing actually
                        // in reach, and casting it only earns a server refusal
                        // (issue #554) — see moveAvailability.
                        const { available: isAvailable, reason } = moveAvailability(move);
                        const moveKey = move.name || move.display_name;
                        const isHovered = hoveredMoveName === moveKey;
                        // Referenced by the button so the reason is exposed
                        // with it, not only in a title tooltip a touch device
                        // can never show (issue #565).
                        const reasonId = `${reasonIdBase}-reason-${index}`;

                        // Single target detection for hover effect
                        const firstTarget = move.viable_targets?.[0];
                        const singleTargetId = (move.targeted && !move.requires_target_selection && move.viable_targets?.length === 1 && firstTarget?.id?.startsWith('enemy_'))
                            ? firstTarget.id
                            : null;

                        // The card is a wrapper, not the button itself: the
                        // unavailability reason carries interactive glossary terms
                        // (#507), and a disabled <button> does not dispatch pointer
                        // or keyboard events to anything nested inside it — so a
                        // term rendered in there would be inert exactly when it is
                        // needed, besides being a nested interactive control.
                        //
                        // Two seams that restructure opened, both fixed here: the
                        // wrapper carries no padding (the button pads itself, so the
                        // whole card face casts the move and shows the right cursor
                        // instead of a 12px dead ring), and the hover handlers sit on
                        // the wrapper — the element the hover chrome is drawn on — so
                        // crossing from the button onto the ring or the reason line
                        // cannot blink the card highlight and the battlefield's enemy
                        // highlight off under a pointer that never left the card.
                        return (
                          <div
                            key={moveKey}
                            data-testid="move-card"
                            data-available={isAvailable ? 'true' : 'false'}
                            onMouseEnter={() => {
                                if (isAvailable) {
                                    setHoveredMoveName(moveKey);
                                    if (singleTargetId && onTargetHover) {
                                        onTargetHover(singleTargetId);
                                    }
                                }
                            }}
                            onMouseLeave={() => {
                                setHoveredMoveName(null);
                                if (onTargetHover) {
                                    onTargetHover(null);
                                }
                            }}
                            style={{
                                backgroundColor: isHovered ? 'rgba(255, 170, 0, 0.1)' : 'rgba(255, 255, 255, 0.03)',
                                // Dashed, desaturated and dimmed: three cues
                                // that survive a colour-blind or greyscale
                                // reading of the card, on top of the LOCKED
                                // chip below (issue #565).
                                border: `1px ${isAvailable ? 'solid' : 'dashed'} ${isHovered ? colors.secondary : colors.border.light}`,
                                borderRadius: '4px',
                                padding: 0,
                                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: spacing.xs,
                                opacity: isAvailable ? 1 : 0.55,
                                filter: isAvailable ? 'none' : 'grayscale(0.5)',
                                boxShadow: isHovered ? shadows.glow : 'none',
                                width: '100%',
                            }}
                          >
                            <button
                                onClick={() => {
                                    if (isAvailable && !isProcessing) {
                                        playSFX('attack');
                                        if (onTargetHover) onTargetHover(null);
                                        onMoveClick(move);
                                    }
                                }}
                                disabled={!isAvailable || isProcessing}
                                title={!isAvailable ? reason : ''}
                                aria-describedby={!isAvailable && reason ? reasonId : undefined}
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    padding: spacing.md,
                                    color: 'inherit',
                                    textAlign: 'left',
                                    cursor: isProcessing ? 'wait' : (isAvailable ? 'pointer' : 'not-allowed'),
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: spacing.xs,
                                    width: '100%',
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                                    <GameText
                                        variant={isHovered ? 'highlight' : (isAvailable ? 'bright' : 'dim')}
                                        weight="bold"
                                    >
                                        {displayNameOf(move)}
                                    </GameText>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs, flexShrink: 0 }}>
                                        {/* A word and a glyph, not just the
                                            dimming: "state is never conveyed
                                            by colour alone". It sits inside
                                            the button so the card's accessible
                                            name carries it too. */}
                                        {!isAvailable && (
                                            <GameText variant="dim" size="xs" weight="bold" style={{ letterSpacing: '0.05em' }}>
                                                ⛔ LOCKED
                                            </GameText>
                                        )}
                                        {move.fatigue_cost > 0 && (
                                            <GameText variant="muted" size="xs">
                                                Fatigue: {move.fatigue_cost}
                                            </GameText>
                                        )}
                                    </div>
                                </div>
                                <MoveCommitmentBar move={move} maxTotal={maxCommitmentBeats} />
                                <GameText variant={isAvailable ? 'muted' : 'dim'} size="sm">
                                    {move.description}
                                </GameText>
                            </button>
                            {!isAvailable && reason && (
                                <GlossaryText
                                    id={reasonId}
                                    text={`⚠ ${reason}`}
                                    style={{
                                        color: colors.text.danger,
                                        fontSize: '0.75rem',
                                        fontStyle: 'italic',
                                        fontFamily: '"Courier New", monospace',
                                        // The wrapper pads nothing now, so the
                                        // reason line pays for its own inset.
                                        padding: `0 ${spacing.md} ${spacing.md}`,
                                    }}
                                />
                            )}
                          </div>
                        );
                    })
                )}
            </div>
        </GamePanel>
    );
};

export default React.memo(CombatMovePanel);
