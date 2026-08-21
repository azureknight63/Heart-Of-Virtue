import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LeftPanel from './LeftPanel';
import React from 'react';
import { CATEGORY_GROUPS } from '../utils/categories';
import { colors } from '../styles/theme';

// Mock child components
vi.mock('./PartyPanel', () => ({ default: ({ onClose }) => <div data-testid="party-panel"><button onClick={onClose}>Close Party</button></div> }));
vi.mock('./InventoryDialog', () => ({ default: ({ onClose }) => <div data-testid="inventory-dialog"><button onClick={onClose}>Close Inv</button></div> }));
vi.mock('./AccountDialog', () => ({ default: ({ onClose }) => <div data-testid="account-dialog"><button onClick={onClose}>Close Acc</button></div> }));
vi.mock('./SettingsDialog', () => ({ default: ({ onClose }) => <div data-testid="audio-dialog"><button onClick={onClose}>Close Aud</button></div> }));
vi.mock('./StatsPanel', () => ({ default: ({ onClose }) => <div data-testid="stats-panel"><button onClick={onClose}>Close Stats</button></div> }));
vi.mock('./SkillsPanel', () => ({ default: ({ onClose }) => <div data-testid="skills-panel"><button onClick={onClose}>Close Skills</button></div> }));
vi.mock('./CollapsibleRoomDescription', () => ({
    default: ({ onInteract }) => (
        <div data-testid="room-contents">
            <button onClick={() => onInteract()}>Interact Button</button>
            <button onClick={() => onInteract('a rusty lever')}>Interact With Lever</button>
        </div>
    )
}));
vi.mock('./ActionsPanel', () => ({ default: ({ onClose }) => <div data-testid="actions-panel"><button onClick={onClose}>Close Actions</button></div> }));
vi.mock('./InteractPanel', () => ({
    default: ({ onClose, onOpenShop, initialTarget }) => (
        <div data-testid="interact-panel">
            {initialTarget && <span>target:{initialTarget}</span>}
            <button onClick={onClose}>Close Interact</button>
            <button onClick={() => onOpenShop('npc-1', 'Jambo', 'buy')}>Open Shop</button>
        </div>
    )
}));
vi.mock('./HeroPanel', () => ({
    default: (props) => (
        <div data-testid="hero-panel">
            <button onClick={props.onStatusClick}>Status Btn</button>
            <button onClick={props.onInventoryClick}>Inventory Btn</button>
            <button onClick={props.onSkillsClick}>Skills Btn</button>
            <button onClick={props.onAttributeClick}>Attributes Btn</button>
            <button onClick={props.onActionsClick}>Actions Btn</button>
            <button onClick={props.onInteractClick}>Interact Btn</button>
            <button onClick={props.onOffensiveClick}>Offensive Btn</button>
            <button onClick={props.onDefensiveClick}>Defensive Btn</button>
            <button onClick={props.onManeuverClick}>Maneuver Btn</button>
            <button onClick={props.onMiscellaneousClick}>Miscellaneous Btn</button>
            <button onClick={props.onSpecialClick}>Special Btn</button>
            <span data-testid="hero-player-hp">{props.player?.hp}</span>
            <span data-testid="hero-flags">
                {[
                    props.hasOffensiveMoves && 'offensive',
                    props.hasDefensiveMoves && 'defensive',
                    props.hasManeuverMoves && 'maneuver',
                    props.hasMiscellaneousMoves && 'misc',
                    props.hasSpecialMoves && 'special',
                ].filter(Boolean).join(',')}
            </span>
        </div>
    )
}));
vi.mock('./CombatLog', () => ({ default: ({ log }) => <div data-testid="combat-log">{log.map((e, i) => <div key={i}>{e.message}</div>)}</div> }));
vi.mock('./CombatInputDialog', () => ({
    default: ({ onSelect, onCancel }) => (
        <div data-testid="combat-input-dialog">
            <button onClick={() => onSelect('target-1')}>Select Target</button>
            <button onClick={onCancel}>Cancel Input</button>
        </div>
    )
}));
vi.mock('./CombatMovePanel', () => ({
    default: ({ moves, category, onMoveClick, onClose }) => (
        <div data-testid="combat-move-panel">
            <span>{category}</span>
            {moves.map((m) => (
                <button key={m.id || m.name} onClick={() => onMoveClick(m)}>{m.name}</button>
            ))}
            <button onClick={onClose}>Close Moves</button>
        </div>
    )
}));
vi.mock('./FeedbackDialog', () => ({ default: ({ onClose }) => <div data-testid="feedback-dialog"><button onClick={onClose}>Close Feedback</button></div> }));
vi.mock('./CooldownTray', () => ({ default: ({ moves }) => <div data-testid="cooldown-tray">{moves.length} on cooldown</div> }));
vi.mock('./FleeButton', () => ({ default: ({ onFlee }) => <button data-testid="flee-button" onClick={onFlee}>Flee</button> }));
vi.mock('./SuggestedMovesPanel', () => ({
    default: ({ onSuggestClick }) => (
        <div data-testid="suggested-moves-panel">
            <button onClick={() => onSuggestClick({ move_name: 'repeat_last' })}>Repeat Last</button>
            <button onClick={() => onSuggestClick({ move_name: 'Slash', target_id: 'enemy_1' })}>Suggest Slash</button>
        </div>
    )
}));
vi.mock('./ShopDialog', () => ({ default: ({ npcName, onClose }) => <div data-testid="shop-dialog">{npcName}<button onClick={onClose}>Close Shop</button></div> }));
vi.mock('./CombatCheckDialog', () => ({ default: ({ onClose }) => <div data-testid="combat-check-dialog"><button onClick={onClose}>Close Check</button></div> }));

// Mock useAudio
const mockPlaySFX = vi.fn();
const mockPlaySting = vi.fn();
vi.mock('../context/AudioContext', () => ({
    useAudio: () => ({
        playSFX: mockPlaySFX,
        playSting: mockPlaySting,
        playBGM: vi.fn(),
    }),
}));

const mockPlayer = {
    name: 'Jean',
    level: 1,
    hp: 100,
    max_hp: 100,
    inventory: []
};

const mockLocation = {
    name: 'Forest',
    description: 'Green trees.'
};

/**
 * One entry of `available_options` exactly as ApiCombatAdapter
 * ._get_available_moves emits it (src/api/combat_adapter.py). Two details the
 * hand-written literals here used to get wrong, which is the fixture-agreeing-
 * with-itself failure CLAUDE.md warns about:
 *   * `id` is a STRING (`str(i)`), never an int.
 *   * every gating field is always present — `available`, `targeted`,
 *     `viable_targets`, `requires_target_selection`, `cooldown_remaining` —
 *     so a fixture that omits one describes a payload the adapter cannot send.
 */
const makeCombatMove = (overrides = {}) => ({
    id: '0',
    index: 0,
    name: 'Attack',
    display_name: 'Attack',
    description: 'A basic attack.',
    category: 'Offensive',
    fatigue_cost: 5,
    available: true,
    reason: null,
    targeted: false,
    viable_targets: [],
    requires_target_selection: false,
    cooldown_remaining: 0,
    cooldown_max: 0,
    ...overrides,
});

/** A combatant id as CombatantSerializer emits it: 'player' / 'enemy_<n>'. */
const enemyId = (n) => `enemy_${n}`;

describe('LeftPanel', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it.each([
        // [mode, header, panel shown below the hero, panel hidden]
        ['exploration', 'Heart of Virtue - Exploration', 'room-contents', 'combat-log'],
        ['combat', 'Heart of Virtue - Combat', 'combat-log', 'room-contents'],
    ])('titles the panel for %s mode and forwards the live player to HeroPanel', (mode, title, shown, hidden) => {
        render(
            <LeftPanel
                player={mockPlayer}
                location={mockLocation}
                mode={mode}
                combat={{ log: [], beat_states: [{ enemies: [] }] }}
            />
        );
        // The exact header string (and the absence of the other mode's), not a
        // substring match behind a `toBeDefined()`: the old check passed as
        // long as SOME node matched /Heart of Virtue - Exploration/i.
        const other = mode === 'combat' ? 'Heart of Virtue - Exploration' : 'Heart of Virtue - Combat';
        expect(screen.getByText(title)).toBeInTheDocument();
        expect(screen.queryByText(other)).toBeNull();
        // ...and the player really reaches HeroPanel rather than the panel just
        // being present with an undefined player.
        expect(screen.getByTestId('hero-player-hp')).toHaveTextContent('100');
        // Each mode swaps the lower half: room contents while exploring, the
        // combat log while fighting.
        expect(screen.getByTestId(shown)).toBeInTheDocument();
        expect(screen.queryByTestId(hidden)).toBeNull();
    });

    // Each hero-panel button owns one panel; clicking it twice must close it
    // again. The old version clicked all six in a row and only checked each
    // panel appeared — it would have passed with every button wired to the
    // SAME panel, since nothing asserted the others stayed shut or that a
    // second click closed anything.
    it.each([
        ['Status Btn', 'party-panel'],
        ['Inventory Btn', 'inventory-dialog'],
        ['Skills Btn', 'skills-panel'],
        ['Attributes Btn', 'stats-panel'],
        ['Actions Btn', 'actions-panel'],
        ['Interact Btn', 'interact-panel'],
    ])('%s opens exactly %s and toggles it shut again', (button, testId) => {
        const ALL = [
            'party-panel', 'inventory-dialog', 'skills-panel',
            'stats-panel', 'actions-panel', 'interact-panel',
        ];
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);

        fireEvent.click(screen.getByText(button));
        const open = ALL.filter((id) => screen.queryByTestId(id) !== null);
        expect(open).toEqual([testId]);

        fireEvent.click(screen.getByText(button));
        expect(screen.queryByTestId(testId)).not.toBeInTheDocument();
    });

    it('opens audio and account dialogs from header', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);

        fireEvent.click(screen.getByTitle(/^Settings$/i));
        expect(screen.getByTestId('audio-dialog')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Aud'));
        expect(screen.queryByTestId('audio-dialog')).toBeNull();

        fireEvent.click(screen.getByText('Account'));
        expect(screen.getByTestId('account-dialog')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Acc'));
        expect(screen.queryByTestId('account-dialog')).toBeNull();
    });

    it('closes panels when their close buttons are clicked', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);

        fireEvent.click(screen.getByText('Status Btn'));
        expect(screen.getByTestId('party-panel')).toBeDefined();
        fireEvent.click(screen.getByText('Close Party'));
        expect(screen.queryByTestId('party-panel')).toBeNull();

        fireEvent.click(screen.getByText('Inventory Btn'));
        expect(screen.getByTestId('inventory-dialog')).toBeDefined();
        fireEvent.click(screen.getByText('Close Inv'));
        expect(screen.queryByTestId('inventory-dialog')).toBeNull();
    });

    it('handles combat mode and log processing', async () => {
        const combat = {
            log: [
                { message: 'Jean attacks Slime', round: 1, type: 'action' },
                { message: 'Jean hit Slime for 10 damage', round: 1, type: 'result' }
            ],
            awaiting_input: true,
            input_type: 'move_selection',
            beat_states: [{ enemies: [] }]
        };

        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);

        expect(await screen.findByText('Jean hit Slime for 10 damage', {}, { timeout: 3000 }))
            .toBeInTheDocument();
        // The log must render in the order the backend sent it — checking each
        // line's mere presence passes for a reversed or reordered log.
        expect(
            [...screen.getByTestId('combat-log').children].map((n) => n.textContent)
        ).toEqual(['Jean attacks Slime', 'Jean hit Slime for 10 damage']);
    });

    it('calls onMoveSubmitted when a target is selected via CombatInputDialog', async () => {
        const onMoveSubmitted = vi.fn()
        const onCombatAction = vi.fn().mockResolvedValue({})
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'target_selection',
            available_options: [{ id: 'target-1', name: 'Slime' }],
            beat_states: [{ enemies: [] }]
        }
        render(
            <LeftPanel
                player={mockPlayer}
                location={mockLocation}
                mode="combat"
                combat={combat}
                onMoveSubmitted={onMoveSubmitted}
                onCombatAction={onCombatAction}
            />
        )
        await screen.findByTestId('combat-input-dialog', {}, { timeout: 3000 })
        fireEvent.click(screen.getByText('Select Target'))
        await waitFor(() => {
            expect(onMoveSubmitted).toHaveBeenCalledTimes(1)
        }, { timeout: 1000 })
        // The selection must actually reach the API as a `target` command with
        // the chosen id — a bare "onMoveSubmitted fired" check passes even when
        // the wrong target, or nothing at all, is sent to the server.
        expect(onCombatAction).toHaveBeenCalledWith('target', { target_id: 'target-1' })
    })

    it('renders nothing when player is not yet loaded', () => {
        const { container } = render(<LeftPanel player={null} location={mockLocation} mode="exploration" />);
        expect(container.firstChild).toBeNull();
    });

    it('opens and closes the feedback dialog', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);
        fireEvent.click(screen.getByText('Feedback'));
        expect(screen.getByTestId('feedback-dialog')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Feedback'));
        expect(screen.queryByTestId('feedback-dialog')).not.toBeInTheDocument();
    });

    it('toggles the interact panel closed when the main interact button is clicked again', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);
        fireEvent.click(screen.getByText('Interact Btn'));
        expect(screen.getByTestId('interact-panel')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Interact Btn'));
        expect(screen.queryByTestId('interact-panel')).not.toBeInTheDocument();
    });

    it('opens the interact panel with a specific target from the room description', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);
        fireEvent.click(screen.getByText('Interact With Lever'));
        expect(screen.getByText('target:a rusty lever')).toBeInTheDocument();
    });

    it('closes inventory when skills is opened and vice versa', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);
        fireEvent.click(screen.getByText('Inventory Btn'));
        expect(screen.getByTestId('inventory-dialog')).toBeInTheDocument();

        fireEvent.click(screen.getByText('Skills Btn'));
        expect(screen.getByTestId('skills-panel')).toBeInTheDocument();
        expect(screen.queryByTestId('inventory-dialog')).not.toBeInTheDocument();
    });

    it('opens the shop dialog via InteractPanel and closes it', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);
        fireEvent.click(screen.getByText('Interact Btn'));
        fireEvent.click(screen.getByText('Open Shop'));

        expect(screen.queryByTestId('interact-panel')).not.toBeInTheDocument();
        expect(screen.getByTestId('shop-dialog')).toBeInTheDocument();
        expect(screen.getByText('Jambo')).toBeInTheDocument();

        fireEvent.click(screen.getByText('Close Shop'));
        expect(screen.queryByTestId('shop-dialog')).not.toBeInTheDocument();
    });

    it('shows the cooldown tray when moves are on cooldown in combat', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [
                makeCombatMove({ id: '1', name: 'Slash', category: 'Offensive', cooldown_remaining: 2 }),
                makeCombatMove({ id: '2', name: 'Guard', category: 'Defensive', cooldown_remaining: 0 }),
            ],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        expect(screen.getByTestId('cooldown-tray')).toHaveTextContent('1 on cooldown');
    });

    it('shows the flee button once enemies are all 20ft or further away', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            enemies: [{ id: enemyId(1), distance: 25 }],
            beat_states: [{ enemies: [] }],
        };
        const onCombatAction = vi.fn();
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByTestId('flee-button'));
        expect(onCombatAction).toHaveBeenCalledWith('flee', {});
    });

    it('does not show the flee button when an enemy is too close', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            enemies: [{ id: enemyId(1), distance: 5 }],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        expect(screen.queryByTestId('flee-button')).not.toBeInTheDocument();
    });

    it('treats an enemy with no distance field as too close to flee (defaults to 0)', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            enemies: [{ id: enemyId(1) }],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        expect(screen.queryByTestId('flee-button')).not.toBeInTheDocument();
    });

    it('merges combat.player onto the base player for the hero panel', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            player: { hp: 42 },
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        expect(screen.getByTestId('hero-player-hp')).toHaveTextContent('42');
    });

    it('opens the move panel for a category and toggles it closed on re-click', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [makeCombatMove({ id: '1', name: 'Slash', category: 'Offensive', available: true })],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);

        fireEvent.click(screen.getByText('Offensive Btn'));
        expect(screen.getByTestId('combat-move-panel')).toBeInTheDocument();

        fireEvent.click(screen.getByText('Offensive Btn'));
        expect(screen.queryByTestId('combat-move-panel')).not.toBeInTheDocument();
    });

    // ---- move-category -> radial-button routing -------------------------------
    // CATEGORY_GROUPS (utils/categories.js) is the SINGLE source of truth for
    // which button a move appears under. It was once duplicated inside
    // LeftPanel and CombatMovePanel and drifted, leaving 8 castable moves with
    // no button at all. These cases are generated FROM the map, so adding a
    // category to it without teaching LeftPanel about it fails here rather than
    // shipping an unreachable move. (utils/categories.consumers.test.jsx guards
    // the other half: that the button and the panel agree.)

    /** Group key -> the token HeroPanel's `hasXMoves` flag renders as. */
    const FLAG_FOR_GROUP = {
        Offensive: 'offensive',
        Defensive: 'defensive',
        Maneuver: 'maneuver',
        Miscellaneous: 'misc',
        Special: 'special',
    };

    const combatWith = (moves) => ({
        log: [],
        awaiting_input: true,
        input_type: 'move_selection',
        available_options: moves,
        beat_states: [{ enemies: [] }],
    });

    /** Every (group, engine category) pair the shared map declares. */
    const GROUP_CATEGORY_PAIRS = Object.entries(CATEGORY_GROUPS).flatMap(
        ([group, categories]) => categories.map((category) => [group, category])
    );

    it('has a hero-panel flag for every group the shared category map declares', () => {
        // Guards the table above against CATEGORY_GROUPS growing a group that
        // no button knows about — which is precisely how the original 8 moves
        // became unreachable.
        expect(Object.keys(FLAG_FOR_GROUP).sort()).toEqual(Object.keys(CATEGORY_GROUPS).sort());
    });

    it.each(GROUP_CATEGORY_PAIRS)(
        'lights ONLY the %s button for a %s move',
        (group, category) => {
            render(
                <LeftPanel
                    player={mockPlayer}
                    location={mockLocation}
                    mode="combat"
                    combat={combatWith([makeCombatMove({ id: '1', name: `A ${category} move`, category })])}
                />
            );
            // Exactly one flag: zero means the move has no button at all, two
            // means it is double-listed.
            const flags = screen.getByTestId('hero-flags').textContent.split(',').filter(Boolean);
            expect(flags).toEqual([FLAG_FOR_GROUP[group]]);
        }
    );

    it('lights every button at once when one move of each mapped category is available', () => {
        const moves = GROUP_CATEGORY_PAIRS.map(([, category], i) =>
            makeCombatMove({ id: String(i), name: `Move ${i}`, category })
        );
        render(
            <LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combatWith(moves)} />
        );
        // HeroPanel renders the flags in a fixed order, so compare as a set.
        const flags = screen.getByTestId('hero-flags').textContent.split(',').filter(Boolean);
        expect(new Set(flags)).toEqual(new Set(Object.values(FLAG_FOR_GROUP)));
    });

    it('shows no category buttons for a category the shared map does not claim', () => {
        // `Passive` moves are never castable, so they must reach no button.
        render(
            <LeftPanel
                player={mockPlayer}
                location={mockLocation}
                mode="combat"
                combat={combatWith([makeCombatMove({ id: '1', name: 'Iron Fist', category: 'Passive' })])}
            />
        );
        expect(screen.getByTestId('hero-flags')).toHaveTextContent('');
    });

    it('tolerates a nameless move while still routing it by category', () => {
        render(
            <LeftPanel
                player={mockPlayer}
                location={mockLocation}
                mode="combat"
                combat={combatWith([makeCombatMove({ id: '1', name: undefined, category: 'Tactical' })])}
            />
        );
        expect(screen.getByTestId('hero-flags')).toHaveTextContent('misc');
    });

    it('shows no category buttons at all outside combat mode', () => {
        // hasGroup() is gated on mode === 'combat'; cached moves must not leak
        // combat buttons into exploration.
        render(
            <LeftPanel
                player={mockPlayer}
                location={mockLocation}
                mode="exploration"
                combat={combatWith([makeCombatMove({ id: '1', name: 'Slash', category: 'Offensive' })])}
            />
        );
        expect(screen.getByTestId('hero-flags')).toHaveTextContent('');
    });

    // useApi's transformCombatData spreads battle_state flat onto the combat
    // object, so a nested battle_state never reaches this component.
    it('reads moves from the flattened combat shape, not a nested battle_state', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            battle_state: {
                available_options: [makeCombatMove({ id: '2', name: 'Reap', category: 'Offensive', available: true })],
            },
            available_options: [makeCombatMove({ id: '1', name: 'Slash', category: 'Offensive', available: true })],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        expect(screen.getByText('Slash')).toBeInTheDocument();
        expect(screen.queryByText('Reap')).not.toBeInTheDocument();
    });

    it('excludes the UseItem and "Use Item" moves from the combat move panel, and tolerates a nameless move', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [
                makeCombatMove({ id: '1', name: 'Slash', category: 'Offensive', available: true }),
                makeCombatMove({ id: '2', name: 'UseItem', category: 'Offensive', available: true }),
                makeCombatMove({ id: '3', name: 'Use Item', category: 'Offensive', available: true }),
                makeCombatMove({ id: '4', name: undefined, category: 'Offensive', available: true }),
            ],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        expect(screen.getByText('Slash')).toBeInTheDocument();
        expect(screen.queryByText('UseItem')).not.toBeInTheDocument();
        expect(screen.queryByText('Use Item')).not.toBeInTheDocument();
    });

    // HeroPanel's base bounding box is 360x310; the wrapper scales by
    // min(width/360, height/310), clamped to [0.4, 2.8].
    const withContainerSize = (width, height, fn) => {
        const originalRect = Element.prototype.getBoundingClientRect;
        Element.prototype.getBoundingClientRect = () => ({
            width, height, top: 0, left: 0, right: 0, bottom: 0, x: 0, y: 0, toJSON() {},
        });
        try {
            fn();
        } finally {
            Element.prototype.getBoundingClientRect = originalRect;
        }
    };
    /** The wrapper <div> that carries the computed transform. */
    const heroScale = () =>
        screen.getByTestId('hero-panel').parentElement.style.transform;

    it.each([
        // [width, height, expected transform]
        // 720/360 = 2 and 620/310 = 2 — both axes agree.
        [720, 620, 'scale(2)'],
        // Fit uses the SMALLER axis: 720/360 = 2 but 465/310 = 1.5.
        [720, 465, 'scale(1.5)'],
        // Clamped to the 2.8 ceiling (raw would be 4).
        [1440, 1240, 'scale(2.8)'],
        // Clamped to the 0.4 floor (raw would be 0.25).
        [90, 77.5, 'scale(0.4)'],
    ])('scales the hero panel to fit a %sx%s container', (w, h, expected) => {
        withContainerSize(w, h, () => {
            render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);
            expect(heroScale()).toBe(expected);
        });
    });

    it('leaves the hero panel unscaled when the container reports zero bounds', () => {
        // A pre-layout measurement must not collapse the panel to the 0.4 floor.
        withContainerSize(0, 0, () => {
            render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);
            expect(heroScale()).toBe('scale(1)');
        });
    });

    it('auto-selects the single viable target for a targeted move without requiring selection', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const onMoveSubmitted = vi.fn();
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [makeCombatMove({
                id: '1', name: 'Slash', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: false,
                viable_targets: [{ id: 'enemy_1' }],
            })],
            beat_states: [{ enemies: [] }],
        };
        render(
            <LeftPanel
                player={mockPlayer} location={mockLocation} mode="combat" combat={combat}
                onCombatAction={onCombatAction} onMoveSubmitted={onMoveSubmitted}
            />
        );
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Slash'));

        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
                move_name: 'Slash', target_id: 'enemy_1',
            });
        });
        // Submitting a move flips the mobile view to the battlefield tab.
        expect(onMoveSubmitted).toHaveBeenCalledTimes(1);
    });

    it('does not notify onMoveSubmitted for instant/non-turn-consuming moves', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const onMoveSubmitted = vi.fn();
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [makeCombatMove({
                id: '1', name: 'Check', category: 'Utility', available: true,
                targeted: true, requires_target_selection: false,
                viable_targets: [{ id: 'enemy_1' }],
            })],
            beat_states: [{ enemies: [] }],
        };
        render(
            <LeftPanel
                player={mockPlayer} location={mockLocation} mode="combat" combat={combat}
                onCombatAction={onCombatAction} onMoveSubmitted={onMoveSubmitted}
            />
        );
        fireEvent.click(screen.getByText('Miscellaneous Btn'));
        fireEvent.click(screen.getByText('Check'));

        await waitFor(() => {
            // The move is dispatched by name against the sole live enemy —
            // asserting the payload catches a wrong move_name or target_id,
            // which a bare toHaveBeenCalled() would wave through.
            expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
                move_name: 'Check', target_id: 'enemy_1',
            });
        });
        // ...and it does NOT flip the mobile view to the battlefield.
        expect(onMoveSubmitted).not.toHaveBeenCalled();
    });

    it('ignores clicks on an unavailable move', () => {
        const onCombatAction = vi.fn();
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [makeCombatMove({ id: '1', name: 'Slash', category: 'Offensive', available: false })],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Slash'));
        expect(onCombatAction).not.toHaveBeenCalled();
    });

    it('opens a local target-selection dialog for moves that require it', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [makeCombatMove({
                id: '1', name: 'Lunge', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: true,
                viable_targets: [{ id: 'enemy_1' }, { id: 'enemy_2' }],
            })],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        expect(screen.getByTestId('combat-input-dialog')).toBeInTheDocument();
    });

    it('sends the local target selection and clears it on success', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [makeCombatMove({
                id: '1', name: 'Lunge', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: true,
                viable_targets: [{ id: 'enemy_1' }],
            })],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        fireEvent.click(screen.getByText('Select Target'));

        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
                move_name: 'Lunge', target_id: 'target-1',
            });
        });
        await waitFor(() => {
            expect(screen.queryByTestId('combat-input-dialog')).not.toBeInTheDocument();
        });
    });

    it('cancels a local target-selection dialog without calling the API', () => {
        const onCombatAction = vi.fn();
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [makeCombatMove({
                id: '1', name: 'Lunge', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: true,
                viable_targets: [{ id: 'enemy_1' }],
            })],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        fireEvent.click(screen.getByText('Cancel Input'));

        expect(screen.queryByTestId('combat-input-dialog')).not.toBeInTheDocument();
        expect(onCombatAction).not.toHaveBeenCalled();
    });

    // The clearing effect used to key on turn_number/combat_id, neither of which
    // exists on the client combat object — so a picker outlived its own turn.
    it('closes a stale local target picker when the beat advances', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            round: 1,
            beat: 1,
            available_options: [makeCombatMove({
                id: '1', name: 'Lunge', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: true,
                viable_targets: [{ id: 'enemy_1' }, { id: 'enemy_2' }],
            })],
            beat_states: [{ enemies: [] }],
        };
        const { rerender } = render(
            <LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />
        );
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        expect(screen.getByTestId('combat-input-dialog')).toBeInTheDocument();

        rerender(
            <LeftPanel
                player={mockPlayer}
                location={mockLocation}
                mode="combat"
                combat={{ ...combat, beat: 2, awaiting_input: false }}
            />
        );
        expect(screen.queryByTestId('combat-input-dialog')).not.toBeInTheDocument();
    });

    it('closes a stale local target picker when the round advances', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            round: 1,
            beat: 3,
            available_options: [makeCombatMove({
                id: '1', name: 'Lunge', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: true,
                viable_targets: [{ id: 'enemy_1' }],
            })],
            beat_states: [{ enemies: [] }],
        };
        const { rerender } = render(
            <LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />
        );
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        expect(screen.getByTestId('combat-input-dialog')).toBeInTheDocument();

        rerender(
            <LeftPanel
                player={mockPlayer}
                location={mockLocation}
                mode="combat"
                combat={{ ...combat, round: 2, awaiting_input: false }}
            />
        );
        expect(screen.queryByTestId('combat-input-dialog')).not.toBeInTheDocument();
    });

    it('opens an empty local target-selection dialog when viable_targets is absent', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [makeCombatMove({
                id: '1', name: 'Lunge', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: true,
            })],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        expect(screen.getByTestId('combat-input-dialog')).toBeInTheDocument();
    });

    it('logs an error and resets pending state when auto-target selection fails', async () => {
        const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        const onCombatAction = vi.fn().mockRejectedValue(new Error('network down'));
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [makeCombatMove({
                id: '1', name: 'Slash', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: false,
                viable_targets: [{ id: 'enemy_1' }],
            })],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Slash'));

        await waitFor(() => {
            expect(errorSpy).toHaveBeenCalledWith('Failed to auto-select target:', expect.any(Error));
        });
        errorSpy.mockRestore();
    });

    it('executes a non-targeted move via the default flow', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [makeCombatMove({ id: '1', name: 'Rest', category: 'Maneuver', available: true, targeted: false })],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Maneuver Btn'));
        fireEvent.click(screen.getByText('Rest'));

        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('move', { move_id: '1' });
        });
    });

    it('logs an error and does not crash when move execution rejects', async () => {
        const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        const onCombatAction = vi.fn().mockRejectedValue(new Error('server error'));
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [makeCombatMove({ id: '1', name: 'Rest', category: 'Maneuver', available: true, targeted: false })],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Maneuver Btn'));
        fireEvent.click(screen.getByText('Rest'));

        await waitFor(() => {
            expect(errorSpy).toHaveBeenCalledWith('Failed to execute move:', expect.any(Error));
        });
        errorSpy.mockRestore();
    });

    it('sends a direction selection through the combat input dialog', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'direction_selection',
            available_options: [],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        await waitFor(() => screen.getByTestId('combat-input-dialog'));
        fireEvent.click(screen.getByText('Select Target'));
        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('direction', { direction: 'target-1' });
        });
    });

    it('sends a number input through the combat input dialog', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'number_input',
            available_options: [],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        await waitFor(() => screen.getByTestId('combat-input-dialog'));
        fireEvent.click(screen.getByText('Select Target'));
        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('number', { value: 'target-1' });
        });
    });

    it('cancels the backend-driven input dialog and notifies the API', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'target_selection',
            available_options: [{ id: 'target-1', name: 'Slime' }],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        await waitFor(() => screen.getByTestId('combat-input-dialog'));
        fireEvent.click(screen.getByText('Cancel Input'));
        expect(onCombatAction).toHaveBeenCalledWith('cancel', {});
    });

    it('logs an error when sending backend input fails', async () => {
        const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        const onCombatAction = vi.fn().mockRejectedValue(new Error('boom'));
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'target_selection',
            available_options: [{ id: 'target-1', name: 'Slime' }],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        await waitFor(() => screen.getByTestId('combat-input-dialog'));
        fireEvent.click(screen.getByText('Select Target'));
        await waitFor(() => {
            expect(errorSpy).toHaveBeenCalledWith('Failed to send input:', expect.any(Error));
        });
        errorSpy.mockRestore();
    });

    it('shows the suggested moves panel and repeats the last move by name', () => {
        const onCombatAction = vi.fn();
        const combat = {
            log: [],
            awaiting_input: true,
            last_move_name: 'Slash',
            last_move_target_id: 'enemy_1',
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Repeat Last'));
        expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
            move_name: 'Slash', target_id: 'enemy_1',
        });
    });

    it('falls back to the first suggested move when repeating with no last move on record', () => {
        const onCombatAction = vi.fn();
        const combat = {
            log: [],
            awaiting_input: true,
            suggested_moves: [{ move_name: 'Guard', target_id: 'enemy_2' }],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Repeat Last'));
        expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
            move_name: 'Guard', target_id: 'enemy_2',
        });
    });

    it('dispatches a directly-suggested move', () => {
        const onCombatAction = vi.fn();
        const combat = { log: [], awaiting_input: true, beat_states: [{ enemies: [] }] };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Suggest Slash'));
        expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
            move_name: 'Slash', target_id: 'enemy_1',
        });
    });

    it('shows the check dialog when the backend sends check_data and closes it', () => {
        const combat = {
            log: [],
            awaiting_input: false,
            check_data: [{ label: 'Perception', value: 12 }],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        expect(screen.getByTestId('combat-check-dialog')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Check'));
        expect(screen.queryByTestId('combat-check-dialog')).not.toBeInTheDocument();
    });

    it('plays SFX cues that correspond to log message keywords', async () => {
        // The very first batch of log lines a mount ever sees is treated as
        // page-reload recovery (displayed instantly, no SFX) — seed one line
        // first, then rerender with the real lines under test so they go
        // through the normal (SFX-playing) path instead.
        const seedEntry = { message: 'Combat begins', round: 0, type: 'info' };
        const combat = { log: [seedEntry], beat_states: [{ enemies: [] }] };
        const { rerender } = render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        await waitFor(() => {
            expect(screen.getByText('Combat begins')).toBeInTheDocument();
        }, { timeout: 3000 });

        const newCombat = {
            log: [
                seedEntry,
                { message: 'Jean attacks Slime', round: 1, type: 'action' },
                { message: 'Jean hit Slime for 10 damage', round: 1, type: 'result' },
                { message: 'Jean missed the strike', round: 1, type: 'result' },
                { message: 'Jean parries the blow', round: 1, type: 'result' },
                { message: 'Slime was defeated', round: 1, type: 'result' },
                { message: 'Jean is poisoned', round: 1, type: 'status' },
                { message: 'Jean uses a Potion', round: 1, type: 'item' },
                { message: 'Jean quest complete', round: 1, type: 'quest' },
            ],
            beat_states: [{ enemies: [] }],
        };
        rerender(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={newCombat} />);

        await waitFor(() => {
            expect(screen.getByText('Jean quest complete')).toBeInTheDocument();
        }, { timeout: 8000 });

        expect(mockPlaySFX).toHaveBeenCalledWith('attack_swipe');
        expect(mockPlaySFX).toHaveBeenCalledWith('attack_hit');
        expect(mockPlaySFX).toHaveBeenCalledWith('attack_miss');
        expect(mockPlaySFX).toHaveBeenCalledWith('attack_parry');
        expect(mockPlaySFX).toHaveBeenCalledWith('enemy_death');
        expect(mockPlaySFX).toHaveBeenCalledWith('status_hit');
        expect(mockPlaySFX).toHaveBeenCalledWith('item_use');
        expect(mockPlaySFX).toHaveBeenCalledWith('quest_complete');
    }, 15000);

    it('plays a heal SFX and notifies onLogProgress/onLogProcessingChange/onDisplayedLogCountChange', async () => {
        const seedEntry = { message: 'Combat begins', round: 0, type: 'info' };
        const combat = { log: [seedEntry], beat_states: [{ enemies: [] }] };
        const onLogProgress = vi.fn();
        const onLogProcessingChange = vi.fn();
        const onDisplayedLogCountChange = vi.fn();
        const { rerender } = render(
            <LeftPanel
                player={mockPlayer} location={mockLocation} mode="combat" combat={combat}
                onLogProgress={onLogProgress}
                onLogProcessingChange={onLogProcessingChange}
                onDisplayedLogCountChange={onDisplayedLogCountChange}
            />
        );
        await waitFor(() => {
            expect(screen.getByText('Combat begins')).toBeInTheDocument();
        }, { timeout: 3000 });

        rerender(
            <LeftPanel
                player={mockPlayer} location={mockLocation} mode="combat"
                combat={{
                    log: [seedEntry, { message: 'Jean restores 20 HP', round: 1, type: 'result', beat_index: 3 }],
                    beat_states: [{ enemies: [] }],
                }}
                onLogProgress={onLogProgress}
                onLogProcessingChange={onLogProcessingChange}
                onDisplayedLogCountChange={onDisplayedLogCountChange}
            />
        );

        await waitFor(() => {
            expect(mockPlaySFX).toHaveBeenCalledWith('heal');
        }, { timeout: 5000 });
        expect(onLogProgress).toHaveBeenCalledWith(3);
        expect(onLogProcessingChange).toHaveBeenCalledWith(true);
        // Both log entries have been displayed by the time the SFX fires.
        expect(onDisplayedLogCountChange).toHaveBeenLastCalledWith(2);
    }, 10000);

    it('does not duplicate a log entry with the same message and round', async () => {
        const seedEntry = { message: 'Combat begins', round: 0, type: 'info' };
        const combat = { log: [seedEntry], beat_states: [{ enemies: [] }] };
        const { rerender } = render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        await waitFor(() => {
            expect(screen.getByText('Combat begins')).toBeInTheDocument();
        }, { timeout: 3000 });

        const dupEntry = { message: 'Jean attacks Slime', round: 1, type: 'action' };
        rerender(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={{
            log: [seedEntry, dupEntry, { ...dupEntry }],
            beat_states: [{ enemies: [] }],
        }} />);

        await waitFor(() => {
            expect(screen.getAllByText('Jean attacks Slime').length).toBe(1);
        }, { timeout: 5000 });
    });

    it('does not play a quest SFX when "quest" appears without a completion keyword', async () => {
        const seedEntry = { message: 'Combat begins', round: 0, type: 'info' };
        const combat = { log: [seedEntry], beat_states: [{ enemies: [] }] };
        const { rerender } = render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        await waitFor(() => {
            expect(screen.getByText('Combat begins')).toBeInTheDocument();
        }, { timeout: 3000 });

        rerender(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={{
            log: [seedEntry, { message: 'A new quest is now available', round: 1, type: 'quest' }],
            beat_states: [{ enemies: [] }],
        }} />);

        await waitFor(() => {
            expect(screen.getByText('A new quest is now available')).toBeInTheDocument();
        }, { timeout: 5000 });
        expect(mockPlaySFX).not.toHaveBeenCalledWith('quest_complete');
    });

    it('plays a low-health warning when Jean is attacked below 30% HP', async () => {
        const lowHpPlayer = { ...mockPlayer, hp: 20, max_hp: 100 };
        const seedEntry = { message: 'Combat begins', round: 0, type: 'info' };
        const combat = { log: [seedEntry], beat_states: [{ enemies: [] }] };
        const { rerender } = render(<LeftPanel player={lowHpPlayer} location={mockLocation} mode="combat" combat={combat} />);
        await waitFor(() => {
            expect(screen.getByText('Combat begins')).toBeInTheDocument();
        }, { timeout: 3000 });

        rerender(<LeftPanel player={lowHpPlayer} location={mockLocation} mode="combat" combat={{
            log: [seedEntry, { message: 'Slime attacks Jean', round: 1, type: 'action' }],
            beat_states: [{ enemies: [] }],
        }} />);

        await waitFor(() => {
            expect(mockPlaySFX).toHaveBeenCalledWith('low_health_warning');
        }, { timeout: 5000 });
    });

    it('skips the keyword SFX and holds the reveal for an animation-carrying log entry', async () => {
        const seedEntry = { message: 'Combat begins', round: 0, type: 'info' };
        const combat = { log: [seedEntry], beat_states: [{ enemies: [] }] };
        const { rerender } = render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        await waitFor(() => {
            expect(screen.getByText('Combat begins')).toBeInTheDocument();
        }, { timeout: 3000 });

        rerender(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={{
            log: [seedEntry, { message: 'Jean attacks Slime', round: 1, type: 'result', animation: { type: 'attack' } }],
            beat_states: [{ enemies: [] }],
        }} />);

        await waitFor(() => {
            expect(screen.getByText('Jean attacks Slime')).toBeInTheDocument();
        }, { timeout: 5000 });
        expect(mockPlaySFX).not.toHaveBeenCalledWith('attack_swipe');
    });

    it('plays the victory sting for a victory log line', async () => {
        const seedEntry = { message: 'Combat begins', round: 0, type: 'info' };
        const combat = { log: [seedEntry], beat_states: [{ enemies: [] }] };
        const { rerender } = render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        await waitFor(() => {
            expect(screen.getByText('Combat begins')).toBeInTheDocument();
        }, { timeout: 3000 });

        rerender(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={{
            log: [seedEntry, { message: 'Victory! The battle is won.', round: 1, type: 'result' }],
            beat_states: [{ enemies: [] }],
        }} />);

        await waitFor(() => {
            expect(mockPlaySting).toHaveBeenCalledWith('fanfare');
        }, { timeout: 5000 });
    }, 10000);

    it('closes the Stats, Skills, Actions, and Interact panels via their onClose handlers', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);

        fireEvent.click(screen.getByText('Attributes Btn'));
        expect(screen.getByTestId('stats-panel')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Stats'));
        expect(screen.queryByTestId('stats-panel')).not.toBeInTheDocument();

        fireEvent.click(screen.getByText('Skills Btn'));
        expect(screen.getByTestId('skills-panel')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Skills'));
        expect(screen.queryByTestId('skills-panel')).not.toBeInTheDocument();

        fireEvent.click(screen.getByText('Actions Btn'));
        expect(screen.getByTestId('actions-panel')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Actions'));
        expect(screen.queryByTestId('actions-panel')).not.toBeInTheDocument();

        fireEvent.click(screen.getByText('Interact Btn'));
        expect(screen.getByTestId('interact-panel')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Interact'));
        expect(screen.queryByTestId('interact-panel')).not.toBeInTheDocument();
    });

    it('opens the Defensive and Special (Mastery) combat move panels', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [
                makeCombatMove({ id: '1', name: 'Dodge', category: 'Defensive', available: true }),
                makeCombatMove({ id: '2', name: 'War Cry', category: 'Mastery', available: true }),
            ],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);

        // LeftPanel's job here is to hand CombatMovePanel the GROUP KEY — the
        // panel itself narrows the list with movesInGroup, so the mock (which
        // cannot filter) legitimately shows every move. The group key must be
        // one CATEGORY_GROUPS actually knows, or the real panel filters against
        // an unknown key and renders nothing at all.
        fireEvent.click(screen.getByText('Defensive Btn'));
        expect(screen.getByTestId('combat-move-panel').firstChild).toHaveTextContent('Defensive');
        expect(CATEGORY_GROUPS).toHaveProperty('Defensive');

        fireEvent.click(screen.getByText('Close Moves'));
        fireEvent.click(screen.getByText('Special Btn'));
        // Mastery moves route to the SPECIAL button — the exact regression that
        // left 7 Mastery moves plus Reaper's Mark with no button at all.
        expect(screen.getByTestId('combat-move-panel').firstChild).toHaveTextContent('Special');
        expect(CATEGORY_GROUPS.Special).toContain('Mastery');
    });

    // The three header buttons each hand-roll the same hover pair. Assert the
    // real theme colors on the way in AND the restore on the way out: the old
    // version entered/left all three but only checked that ONE background was
    // "not empty string", which a handler that set `red` would also satisfy —
    // and it never checked mouseLeave restored anything at all, so a button
    // stuck lit forever passed.
    it.each([
        ['Settings', () => screen.getByTitle('Settings')],
        ['Send Feedback', () => screen.getByTitle('Send Feedback')],
        ['Account', () => screen.getByText('Account')],
    ])('lights the %s header button on hover and restores it on leave', (_label, get) => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);
        const btn = get();
        const rgb = (hex) => {
            const n = parseInt(hex.slice(1), 16);
            return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
        };

        expect(btn.style.backgroundColor).toBe(rgb(colors.primaryDark));

        fireEvent.mouseEnter(btn);
        expect(btn.style.backgroundColor).toBe(rgb(colors.primary));
        expect(btn.style.boxShadow).toContain(colors.primary);

        fireEvent.mouseLeave(btn);
        expect(btn.style.backgroundColor).toBe(rgb(colors.primaryDark));
    });
});
