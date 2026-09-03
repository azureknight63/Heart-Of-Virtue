import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import GamePage from './GamePage';
import { capabilitiesDisabled } from '../test/mockHelpers';
import { usePlayer, useWorld, useCombat, useExploration, useExits, useAutosave } from '../hooks/useApi';
import { useAudio } from '../context/AudioContext';
import { useToast } from '../context/ToastContext';
import { MemoryRouter } from 'react-router-dom';

// Mock the hooks
vi.mock('../hooks/useApi', () => ({
    usePlayer: vi.fn(),
    useWorld: vi.fn(),
    useCombat: vi.fn(),
    useExploration: vi.fn(),
    useExits: vi.fn(),
    useAutosave: vi.fn(),
}));

vi.mock('../context/CapabilitiesContext', () => ({
    useCapabilities: vi.fn(() => capabilitiesDisabled),
}));

vi.mock('../context/AudioContext', () => ({
    useAudio: vi.fn(),
}));

vi.mock('../context/ToastContext', () => ({
    useToast: vi.fn(),
}));

vi.mock('../components/RightPanel', () => ({
    default: ({ mode, location }) => (
        <div data-testid="right-panel">
            Mode: {mode}
            Location: {location?.name}
        </div>
    )
}));

vi.mock('../components/LeftPanel', () => ({
    default: ({ location, player, onMove }) => (
        <div data-testid="left-panel">
            <h1>{location?.name}</h1>
            <p>{location?.description}</p>
            <div>Player: {player?.name}</div>
            <button onClick={() => onMove('north')}>Move North</button>
        </div>
    )
}));



vi.mock('../components/EventDialog', () => ({
    default: ({ event, onSubmitInput }) => (
        <div data-testid="event-dialog">
            <h1>{event.name}</h1>
            <p>{event.output_text}</p>
            {event.input_options?.map((opt, i) => (
                <button key={i} onClick={() => onSubmitInput(event.event_id, opt.value)}>
                    {opt.label}
                </button>
            ))}
        </div>
    )
}));



describe('GamePage', () => {
    const mockPlayer = {
        name: 'Jean',
        hp: 100,
        max_hp: 100,
        fatigue: 0,
        max_fatigue: 100,
        level: 1,
        exp: 0,
        inventory: []
    };

    const mockLocation = {
        name: 'Forest Path',
        description: 'A quiet path through the woods.',
        exits: ['north', 'south'],
        x: 0,
        y: 0
    };

    const mockCombat = {
        combat_active: false,
        player: mockPlayer,
        enemies: [],
        log: []
    };

    beforeEach(() => {
        vi.clearAllMocks();

        usePlayer.mockReturnValue({
            player: mockPlayer,
            loading: false,
            refetch: vi.fn()
        });

        useWorld.mockReturnValue({
            location: mockLocation,
            loading: false,
            moveToLocation: vi.fn(),
            refetch: vi.fn()
        });

        useCombat.mockReturnValue({
            combat: mockCombat,
            inCombat: false,
            loading: false,
            fetchCombatStatus: vi.fn(),
            performAction: vi.fn()
        });

        useExploration.mockReturnValue({
            exploredTiles: new Map(),
            setExploredTiles: vi.fn(),
            loading: false,
            refetch: vi.fn()
        });

        useExits.mockReturnValue({
            exits: [],
            loading: false,
            refetch: vi.fn()
        });

        useAutosave.mockReturnValue({
            triggerTick: vi.fn()
        });

        useAudio.mockReturnValue({
            playSFX: vi.fn(),
            playBGM: vi.fn(),
            stopBGM: vi.fn()
        });

        useToast.mockReturnValue({
            error: vi.fn(),
            success: vi.fn(),
            info: vi.fn()
        });
    });

    const renderGamePage = () => {
        return render(
            <MemoryRouter>
                <GamePage />
            </MemoryRouter>
        );
    };

    it('renders exploration mode by default', () => {
        renderGamePage();
        expect(screen.getByText('Forest Path')).toBeDefined();
        expect(screen.getByText('A quiet path through the woods.')).toBeDefined();
    });

    it('renders combat mode when inCombat is true', async () => {
        useCombat.mockReturnValue({
            combat: { ...mockCombat, combat_active: true },
            inCombat: true,
            loading: false,
            fetchCombatStatus: vi.fn(),
            performAction: vi.fn()
        });

        renderGamePage();

        // Should show the encounter dialog first
        expect(screen.getByText(/Enemies draw near/i)).toBeDefined();

        // Click the "FIGHT FOR YOUR LIFE" button
        const fightBtn = screen.getByRole('button', { name: /FIGHT FOR YOUR LIFE/i });
        fireEvent.click(fightBtn);

        // Now it should be in combat mode
        await waitFor(() => {
            expect(screen.getByText(/Mode: combat/i)).toBeDefined();
        });
    });

    it('handles movement and triggers events', async () => {
        const mockMoveToLocation = vi.fn().mockResolvedValue({
            combat_started: false,
            events_triggered: [
                {
                    event_id: 'trap-1',
                    name: 'Spike Trap',
                    output_text: 'You stepped on a trap!',
                    needs_input: false
                }
            ],
            room: { ...mockLocation, x: 1, y: 0 }
        });

        const mockRefetchPlayer = vi.fn();
        usePlayer.mockReturnValue({
            player: mockPlayer,
            loading: false,
            refetch: mockRefetchPlayer
        });

        useWorld.mockReturnValue({
            location: mockLocation,
            loading: false,
            moveToLocation: mockMoveToLocation,
            refetch: vi.fn()
        });

        renderGamePage();

        fireEvent.click(screen.getByText('Move North'));

        await waitFor(() => {
            expect(mockMoveToLocation).toHaveBeenCalledWith('north');
            // Mocked EventDialog should show the trap text
            expect(screen.getByText(/You stepped on a trap!/i)).toBeDefined();
        });
    });


    it('shows victory dialog after combat win', () => {
        vi.useFakeTimers();
        try {
            useCombat.mockReturnValue({
                combat: {
                    combat_active: false,
                    end_state: { id: 'win-1', status: 'victory', message: 'You won!' }
                },
                inCombat: false,
                loading: false,
                fetchCombatStatus: vi.fn(),
                performAction: vi.fn()
            });

            renderGamePage();

            act(() => vi.advanceTimersByTime(5000));

            expect(screen.getByText(/You won!/i)).toBeDefined();
        } finally {
            vi.useRealTimers();
        }
    });

    it('shows BetaEndDialog after closing victory dialog with beta_end=true', async () => {
        vi.useFakeTimers();
        try {
            const mockFetchCombatStatus = vi.fn().mockResolvedValue(undefined);

            useCombat.mockReturnValue({
                combat: {
                    combat_active: false,
                    end_state: {
                        id: 'lurker-win-1',
                        status: 'victory',
                        message: 'Victory!',
                        beta_end: true,
                        exp_gained: {},
                        items_dropped: [],
                        level_ups: [],
                        attribute_points_available: 0,
                        attributes: {
                            strength_base: 10, finesse_base: 10, speed_base: 10,
                            endurance_base: 10, charisma_base: 10, intelligence_base: 10,
                        },
                    }
                },
                inCombat: false,
                loading: false,
                fetchCombatStatus: mockFetchCombatStatus,
                performAction: vi.fn()
            });

            renderGamePage();

            // Advance time to trigger the delayed victory dialog
            act(() => vi.advanceTimersByTime(5000));

            expect(screen.getByText(/Victory!/i)).toBeDefined();

            // Close button is enabled (no points to spend)
            const closeBtn = screen.getByText('CLOSE');
            expect(closeBtn.disabled).toBe(false);
            fireEvent.click(closeBtn);

            // Switch back to real timers so waitFor can retry for the BetaEndDialog
            vi.useRealTimers();

            // BetaEndDialog should appear after closing the victory dialog
            await waitFor(() => {
                expect(screen.getByText('END OF BETA')).toBeDefined();
            });
        } finally {
            vi.useRealTimers();
        }
    });

    describe('stuck-combat recovery (issues #505 / #508)', () => {
        // A page that only learns the combat state when it pushes an action has no
        // way back from a desync. These three pin the ways out of it.

        it('re-syncs combat status on a slow tick even when no suggestions are loading', async () => {
            // The poll used to be gated on suggestions_loading, which left
            // GameService.get_combat_status's own self-heal (in_combat with no
            // awaiting_input resets to move_selection) unreachable in normal play.
            const mockFetchCombatStatus = vi.fn();
            useCombat.mockReturnValue({
                combat: { ...mockCombat, combat_active: true, suggestions_loading: false, log: [] },
                inCombat: true,
                loading: false,
                fetchCombatStatus: mockFetchCombatStatus,
                performAction: vi.fn()
            });

            vi.useFakeTimers();
            try {
                renderGamePage();
                mockFetchCombatStatus.mockClear();
                act(() => vi.advanceTimersByTime(1000));
                expect(mockFetchCombatStatus).toHaveBeenCalled();
            } finally {
                vi.useRealTimers();
            }
        });

        it('does not poll once the fight is over', () => {
            const mockFetchCombatStatus = vi.fn();
            useCombat.mockReturnValue({
                combat: mockCombat,
                inCombat: false,
                loading: false,
                fetchCombatStatus: mockFetchCombatStatus,
                performAction: vi.fn()
            });

            vi.useFakeTimers();
            try {
                renderGamePage();
                mockFetchCombatStatus.mockClear();
                act(() => vi.advanceTimersByTime(5000));
                expect(mockFetchCombatStatus).not.toHaveBeenCalled();
            } finally {
                vi.useRealTimers();
            }
        });

        it('surfaces a server refusal to the player instead of swallowing it', () => {
            const showError = vi.fn();
            useToast.mockReturnValue({ error: showError, success: vi.fn(), info: vi.fn() });
            useCombat.mockReturnValue({
                combat: { ...mockCombat, combat_active: true, log: [] },
                inCombat: true,
                loading: false,
                fetchCombatStatus: vi.fn(),
                performAction: vi.fn()
            });

            renderGamePage();

            // The handler GamePage hands useCombat is the whole point of the fix:
            // an HTTP-200 `success:false` has to reach the player somehow.
            const options = useCombat.mock.calls.at(-1)[1];
            act(() => {
                options.onActionRefused({ success: false, error: 'Not enough fatigue' });
            });
            expect(showError).toHaveBeenCalledWith('Not enough fatigue');

            // A refusal carrying prose prefers it over the machine-readable code.
            act(() => {
                options.onActionRefused({
                    success: false,
                    error: 'Event pending',
                    message: 'Please resolve the current event before taking combat actions.'
                });
            });
            expect(showError).toHaveBeenLastCalledWith(
                'Please resolve the current event before taking combat actions.'
            );
        });

    });
});
