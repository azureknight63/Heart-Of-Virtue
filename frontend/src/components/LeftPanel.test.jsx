import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LeftPanel from './LeftPanel';
import React from 'react';

// Mock child components
vi.mock('./PartyPanel', () => ({ default: ({ onClose }) => <div data-testid="party-panel"><button onClick={onClose}>Close Party</button></div> }));
vi.mock('./InventoryDialog', () => ({ default: ({ onClose }) => <div data-testid="inventory-dialog"><button onClick={onClose}>Close Inv</button></div> }));
vi.mock('./AccountDialog', () => ({ default: ({ onClose }) => <div data-testid="account-dialog"><button onClick={onClose}>Close Acc</button></div> }));
vi.mock('./AudioControlDialog', () => ({ default: ({ onClose }) => <div data-testid="audio-dialog"><button onClick={onClose}>Close Aud</button></div> }));
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

describe('LeftPanel', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders basic info in exploration mode', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);
        expect(screen.getByText(/Heart of Virtue - Exploration/i)).toBeDefined();
        expect(screen.getByTestId('hero-panel')).toBeDefined();
        expect(screen.getByTestId('room-contents')).toBeDefined();
    });

    it('toggles different panels', async () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);

        // Status
        fireEvent.click(screen.getByText('Status Btn'));
        expect(screen.getByTestId('party-panel')).toBeDefined();

        // Inventory
        fireEvent.click(screen.getByText('Inventory Btn'));
        expect(screen.getByTestId('inventory-dialog')).toBeDefined();

        // Skills
        fireEvent.click(screen.getByText('Skills Btn'));
        expect(screen.getByTestId('skills-panel')).toBeDefined();

        // Attributes
        fireEvent.click(screen.getByText('Attributes Btn'));
        expect(screen.getByTestId('stats-panel')).toBeDefined();

        // Actions
        fireEvent.click(screen.getByText('Actions Btn'));
        expect(screen.getByTestId('actions-panel')).toBeDefined();

        // Interact
        fireEvent.click(screen.getByText('Interact Btn'));
        expect(screen.getByTestId('interact-panel')).toBeDefined();
    });

    it('opens audio and account dialogs from header', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);

        fireEvent.click(screen.getByTitle(/Audio Settings/i));
        expect(screen.getByTestId('audio-dialog')).toBeDefined();
        fireEvent.click(screen.getByText('Close Aud'));
        expect(screen.queryByTestId('audio-dialog')).toBeNull();

        fireEvent.click(screen.getByText('Account'));
        expect(screen.getByTestId('account-dialog')).toBeDefined();
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

        expect(screen.getByText(/Heart of Virtue - Combat/i)).toBeDefined();

        await waitFor(() => {
            expect(screen.getByText('Jean attacks Slime')).toBeDefined();
        }, { timeout: 3000 });

        await waitFor(() => {
            expect(screen.getByText('Jean hit Slime for 10 damage')).toBeDefined();
        }, { timeout: 3000 });
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
        await waitFor(() => {
            expect(screen.getByTestId('combat-input-dialog')).toBeDefined()
        }, { timeout: 3000 })
        fireEvent.click(screen.getByText('Select Target'))
        await waitFor(() => {
            expect(onMoveSubmitted).toHaveBeenCalledTimes(1)
        }, { timeout: 1000 })
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
                { id: 1, name: 'Slash', category: 'Offensive', cooldown_remaining: 2 },
                { id: 2, name: 'Guard', category: 'Defensive', cooldown_remaining: 0 },
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
            enemies: [{ id: 1, distance: 25 }],
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
            enemies: [{ id: 1, distance: 5 }],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        expect(screen.queryByTestId('flee-button')).not.toBeInTheDocument();
    });

    it('opens the move panel for a category and toggles it closed on re-click', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [{ id: 1, name: 'Slash', category: 'Offensive', available: true }],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);

        fireEvent.click(screen.getByText('Offensive Btn'));
        expect(screen.getByTestId('combat-move-panel')).toBeInTheDocument();

        fireEvent.click(screen.getByText('Offensive Btn'));
        expect(screen.queryByTestId('combat-move-panel')).not.toBeInTheDocument();
    });

    it('flags the correct hero panel category booleans from available moves', () => {
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [
                { id: 1, name: 'Slash', category: 'Offensive' },
                { id: 2, name: 'Guard', category: 'Defensive' },
                { id: 3, name: 'Dodge', category: 'Maneuver' },
                { id: 4, name: 'Pray', category: 'Supernatural' },
                { id: 5, name: 'Check', category: 'Utility' },
            ],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
        expect(screen.getByTestId('hero-flags')).toHaveTextContent('offensive,defensive,maneuver,misc,special');
    });

    it('auto-selects the single viable target for a targeted move without requiring selection', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const onMoveSubmitted = vi.fn();
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [{
                id: 1, name: 'Slash', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: false,
                viable_targets: [{ id: 'enemy_1' }],
            }],
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
        expect(onMoveSubmitted).toHaveBeenCalled();
    });

    it('does not notify onMoveSubmitted for instant/non-turn-consuming moves', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const onMoveSubmitted = vi.fn();
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [{
                id: 1, name: 'Check', category: 'Utility', available: true,
                targeted: true, requires_target_selection: false,
                viable_targets: [{ id: 'enemy_1' }],
            }],
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
            expect(onCombatAction).toHaveBeenCalled();
        });
        expect(onMoveSubmitted).not.toHaveBeenCalled();
    });

    it('ignores clicks on an unavailable move', () => {
        const onCombatAction = vi.fn();
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [{ id: 1, name: 'Slash', category: 'Offensive', available: false }],
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
            available_options: [{
                id: 1, name: 'Lunge', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: true,
                viable_targets: [{ id: 'enemy_1' }, { id: 'enemy_2' }],
            }],
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
            available_options: [{
                id: 1, name: 'Lunge', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: true,
                viable_targets: [{ id: 'enemy_1' }],
            }],
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
            available_options: [{
                id: 1, name: 'Lunge', category: 'Offensive', available: true,
                targeted: true, requires_target_selection: true,
                viable_targets: [{ id: 'enemy_1' }],
            }],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        fireEvent.click(screen.getByText('Cancel Input'));

        expect(screen.queryByTestId('combat-input-dialog')).not.toBeInTheDocument();
        expect(onCombatAction).not.toHaveBeenCalled();
    });

    it('executes a non-targeted move via the default flow', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [{ id: 1, name: 'Rest', category: 'Maneuver', available: true, targeted: false }],
            beat_states: [{ enemies: [] }],
        };
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Maneuver Btn'));
        fireEvent.click(screen.getByText('Rest'));

        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('move', { move_id: 1 });
        });
    });

    it('logs an error and does not crash when move execution rejects', async () => {
        const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        const onCombatAction = vi.fn().mockRejectedValue(new Error('server error'));
        const combat = {
            log: [],
            awaiting_input: true,
            input_type: 'move_selection',
            available_options: [{ id: 1, name: 'Rest', category: 'Maneuver', available: true, targeted: false }],
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
});
