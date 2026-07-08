import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import GamePage from './GamePage';
import { usePlayer, useWorld, useCombat, useExploration, useAutosave } from '../hooks/useApi';
import { useEventManager } from '../hooks/useEventManager';
import { useCombatCoordinator } from '../hooks/useCombatCoordinator';
import { useAudio } from '../context/AudioContext';
import { useToast } from '../context/ToastContext';
import { combat as combatApi } from '../api/endpoints';

// This file mocks every hook and heavy child component so it can drive
// GamePage's *own* local handler functions (handleMove, handleEventInputWrapper,
// handleVictoryClose, handleCollectLoot, handleSkipLoot, handleDefeatClose,
// handleAllocatePoints, handleAdvisorPause/RequestSuggestions) directly via
// simple button clicks, rather than through the real EventManager/CombatManager
// UI. GamePage.test.jsx / GamePage.integration.test.jsx already exercise real
// hook + dialog behavior; this file targets the wiring code those don't reach.

vi.mock('../hooks/useApi', () => ({
    usePlayer: vi.fn(),
    useWorld: vi.fn(),
    useCombat: vi.fn(),
    useExploration: vi.fn(),
    useAutosave: vi.fn(),
    useAuth: vi.fn(),
}));

vi.mock('../hooks/useEventManager', () => ({
    useEventManager: vi.fn(),
}));

vi.mock('../hooks/useCombatCoordinator', () => ({
    useCombatCoordinator: vi.fn(),
}));

vi.mock('../hooks/useMobile', () => ({
    useMobile: vi.fn(() => false),
}));

vi.mock('../context/AudioContext', () => ({
    useAudio: vi.fn(),
}));

vi.mock('../context/ToastContext', () => ({
    useToast: vi.fn(),
}));

vi.mock('../api/endpoints', () => ({
    combat: {
        pauseSuggestions: vi.fn(),
        collectLoot: vi.fn(),
    },
    default: {
        player: {
            allocateLevelUpPoints: vi.fn(),
        },
    },
}));

vi.mock('../components/LeftPanel', () => ({
    default: ({ onMove, onCombatAction, onAdvisorPause, onAdvisorRequestSuggestions, onInteractionTypingChange, onInteractionClose }) => (
        <div data-testid="left-panel">
            <button onClick={() => onMove('north').catch(() => {})}>Move North</button>
            <button onClick={() => onCombatAction('attack', { target: 'enemy_1' })}>Combat Action</button>
            <button onClick={() => onAdvisorPause(true)}>Pause Advisor</button>
            <button onClick={() => onAdvisorRequestSuggestions()}>Request Suggestions</button>
            <button onClick={() => onInteractionTypingChange(true)}>Start Typing</button>
            <button onClick={() => onInteractionClose()}>Close Interaction</button>
        </div>
    )
}));

vi.mock('../components/RightPanel', () => ({
    default: () => <div data-testid="right-panel" />
}));

vi.mock('../components/EventManager', () => ({
    default: ({ currentEvent, onClose, onSubmitInput }) => (
        <div data-testid="event-manager">
            {currentEvent && <span>{currentEvent.name}</span>}
            <button onClick={onClose}>Close Event</button>
            <button onClick={() => onSubmitInput('event-1', 'some-input')}>Submit Event Input</button>
            <button onClick={() => onSubmitInput('combat_init', 'combat_start')}>Confirm Combat Start</button>
        </div>
    )
}));

vi.mock('../components/CombatManager', () => ({
    default: ({
        showVictoryDialog, showDefeatDialog, showLootDialog,
        onVictoryClose, onDefeatClose, onContinueToLoot, onCollectLoot, onSkipLoot, onAllocatePoints,
    }) => (
        <div data-testid="combat-manager">
            {showVictoryDialog && <button onClick={onVictoryClose}>Close Victory</button>}
            {showVictoryDialog && <button onClick={onContinueToLoot}>Continue To Loot</button>}
            {showVictoryDialog && <button onClick={() => onAllocatePoints('strength_base', 1)}>Allocate From Victory</button>}
            {showLootDialog && <button onClick={() => onCollectLoot(['Sword'])}>Collect Loot</button>}
            {showLootDialog && <button onClick={onSkipLoot}>Skip Loot</button>}
            {showDefeatDialog && <button onClick={onDefeatClose}>Close Defeat</button>}
        </div>
    )
}));

vi.mock('../components/LevelUpModal', () => ({
    default: ({ onAllocatePoints }) => (
        <div data-testid="level-up-modal">
            <button onClick={() => onAllocatePoints('faith_base', 1)}>Allocate From LevelUp</button>
        </div>
    )
}));

vi.mock('../components/GameOverScreen', () => ({
    default: ({ message }) => <div data-testid="game-over-screen">{message}</div>
}));

vi.mock('../components/BetaEndDialog', () => ({
    default: ({ onSendFeedback, onContinue }) => (
        <div data-testid="beta-end-dialog">
            <button onClick={onSendFeedback}>Send Feedback</button>
            <button onClick={onContinue}>Continue</button>
        </div>
    )
}));

vi.mock('../components/FeedbackDialog', () => ({
    default: ({ onClose }) => <div data-testid="feedback-dialog"><button onClick={onClose}>Close Feedback</button></div>
}));

vi.mock('../components/MobileTabBar', () => ({
    default: () => <div data-testid="mobile-tab-bar" />,
    MOBILE_TAB_BAR_HEIGHT: 50,
}));

function makeEventManagerReturn(overrides = {}) {
    return {
        currentEvent: null,
        eventsChecked: true,
        eventHistory: [],
        eventQueue: [],
        isEventDialogActive: false,
        isInteractionDelayActive: false,
        setEventQueue: vi.fn(),
        setCurrentEvent: vi.fn(),
        setIsInteractionDelayActive: vi.fn(),
        handleEventsTriggered: vi.fn(),
        handleEventClose: vi.fn(),
        handleEventInput: vi.fn().mockResolvedValue({ success: true }),
        checkPendingEvents: vi.fn().mockResolvedValue(),
        ...overrides,
    };
}

function makeCombatCoordinatorReturn(overrides = {}) {
    return {
        combatDialogShown: false,
        showVictoryDialog: false,
        showDefeatDialog: false,
        showLootDialog: false,
        endState: null,
        lastEndStateId: null,
        endStatePendingRef: { current: false },
        isCombatLogProcessing: false,
        currentLogIndex: 0,
        hoveredTargetId: null,
        setCombatDialogShown: vi.fn(),
        setShowVictoryDialog: vi.fn(),
        setShowDefeatDialog: vi.fn(),
        setShowLootDialog: vi.fn(),
        setEndState: vi.fn(),
        setIsCombatLogProcessing: vi.fn(),
        setCurrentLogIndex: vi.fn(),
        setHoveredTargetId: vi.fn(),
        handleSuggestedMoveClick: vi.fn(),
        handleCombatAction: vi.fn().mockResolvedValue({}),
        handleInteractionComplete: vi.fn(),
        ...overrides,
    };
}

describe('GamePage handler wiring', () => {
    const mockPlayer = { name: 'Jean', hp: 100, max_hp: 100, weight_current: 10, carrying_capacity: 100, pending_attribute_points: 0 };
    const mockLocation = { name: 'Forest', description: 'Trees.', x: 0, y: 0, exits: [] };
    let refetchPlayer, refetchWorld, refetchExploration, fetchCombatStatus, moveToLocation, performAction, triggerTick;

    beforeEach(() => {
        vi.clearAllMocks();

        refetchPlayer = vi.fn().mockResolvedValue();
        refetchWorld = vi.fn().mockResolvedValue();
        refetchExploration = vi.fn().mockResolvedValue();
        fetchCombatStatus = vi.fn().mockResolvedValue();
        moveToLocation = vi.fn().mockResolvedValue({ combat_started: false, events_triggered: [] });
        performAction = vi.fn().mockResolvedValue({});
        triggerTick = vi.fn();

        usePlayer.mockReturnValue({ player: mockPlayer, loading: false, refetch: refetchPlayer });
        useWorld.mockReturnValue({ location: mockLocation, loading: false, moveToLocation, refetch: refetchWorld });
        useExploration.mockReturnValue({ exploredTiles: new Map(), setExploredTiles: vi.fn(), refetch: refetchExploration });
        useCombat.mockReturnValue({ combat: null, inCombat: false, fetchCombatStatus, performAction });
        useAutosave.mockReturnValue({ triggerTick });
        useAudio.mockReturnValue({ playBGM: vi.fn(), playSFX: vi.fn(), playSting: vi.fn() });
        useToast.mockReturnValue({ error: vi.fn() });
        useEventManager.mockReturnValue(makeEventManagerReturn());
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn());

        combatApi.pauseSuggestions.mockResolvedValue();
        combatApi.collectLoot.mockResolvedValue();
    });

    const renderGamePage = () => render(<MemoryRouter><GamePage /></MemoryRouter>);

    it('moves, refetches player, and triggers an autosave tick', async () => {
        renderGamePage();
        fireEvent.click(screen.getByText('Move North'));

        await waitFor(() => {
            expect(moveToLocation).toHaveBeenCalledWith('north');
        });
        expect(refetchPlayer).toHaveBeenCalled();
        expect(triggerTick).toHaveBeenCalled();
    });

    it('queues displayable events triggered by movement, filtering out silent ones', async () => {
        const setEventQueue = vi.fn();
        useEventManager.mockReturnValue(makeEventManagerReturn({ setEventQueue }));
        moveToLocation.mockResolvedValue({
            combat_started: false,
            events_triggered: [
                { event_id: 'a', output_text: 'You found a trap!', needs_input: false },
                { event_id: 'b', output_text: '', needs_input: false },
                { event_id: 'c', output_text: '   ', needs_input: false },
            ],
        });
        renderGamePage();
        fireEvent.click(screen.getByText('Move North'));

        await waitFor(() => {
            expect(setEventQueue).toHaveBeenCalledWith([
                { event_id: 'a', output_text: 'You found a trap!', needs_input: false },
            ]);
        });
    });

    it('fetches combat status when movement triggers combat', async () => {
        moveToLocation.mockResolvedValue({ combat_started: true, events_triggered: [] });
        renderGamePage();
        fireEvent.click(screen.getByText('Move North'));

        await waitFor(() => {
            expect(fetchCombatStatus).toHaveBeenCalled();
        });
    });

    it('propagates a rejected move without running post-move side effects', async () => {
        moveToLocation.mockRejectedValue(new Error('blocked path'));
        renderGamePage();

        await act(async () => {
            fireEvent.click(screen.getByText('Move North'));
        });

        // handleMove's catch block just rethrows — refetch/triggerTick only run on success.
        expect(refetchPlayer).not.toHaveBeenCalled();
        expect(triggerTick).not.toHaveBeenCalled();
    });

    it('starts combat mode when the combat_init event is confirmed', async () => {
        const setMode_setCurrentEvent = vi.fn();
        const setCombatDialogShown = vi.fn();
        useEventManager.mockReturnValue(makeEventManagerReturn({ setCurrentEvent: setMode_setCurrentEvent }));
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({ setCombatDialogShown }));

        renderGamePage();
        fireEvent.click(screen.getByText('Confirm Combat Start'));

        expect(setMode_setCurrentEvent).toHaveBeenCalledWith(null);
        expect(setCombatDialogShown).toHaveBeenCalledWith(true);
        await waitFor(() => expect(fetchCombatStatus).toHaveBeenCalled());
    });

    it('shows the game over screen when a submitted event input reports game over', async () => {
        const handleEventInput = vi.fn().mockResolvedValue({
            success: true, is_game_over: true, output_text: 'Jean has died.',
        });
        const handleEventClose = vi.fn();
        useEventManager.mockReturnValue(makeEventManagerReturn({ handleEventInput, handleEventClose }));

        renderGamePage();
        fireEvent.click(screen.getByText('Submit Event Input'));
        await waitFor(() => expect(handleEventInput).toHaveBeenCalledWith('event-1', 'some-input', expect.any(Function)));

        // Death text stays in the EventDialog until the user closes it.
        expect(screen.queryByTestId('game-over-screen')).not.toBeInTheDocument();

        fireEvent.click(screen.getByText('Close Event'));
        await waitFor(() => {
            expect(screen.getByTestId('game-over-screen')).toHaveTextContent('Jean has died.');
        });
    });

    it('fetches combat status and shows the encounter dialog flag when an event triggers combat', async () => {
        const handleEventInput = vi.fn().mockResolvedValue({ success: true, combat_started: true });
        const setCombatDialogShown = vi.fn();
        useEventManager.mockReturnValue(makeEventManagerReturn({ handleEventInput }));
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({ setCombatDialogShown }));

        renderGamePage();
        fireEvent.click(screen.getByText('Submit Event Input'));

        await waitFor(() => {
            expect(setCombatDialogShown).toHaveBeenCalledWith(true);
        });
        expect(refetchPlayer).toHaveBeenCalled();
        expect(refetchWorld).toHaveBeenCalled();
    });

    it('does nothing extra when the event handler reports failure', async () => {
        const handleEventInput = vi.fn().mockResolvedValue({ success: false });
        useEventManager.mockReturnValue(makeEventManagerReturn({ handleEventInput }));

        renderGamePage();
        fireEvent.click(screen.getByText('Submit Event Input'));

        await waitFor(() => expect(handleEventInput).toHaveBeenCalled());
        expect(refetchPlayer).not.toHaveBeenCalled();
    });

    it('closes the victory dialog, refetches state, and shows the beta-end dialog', async () => {
        const setShowVictoryDialog = vi.fn();
        const setEndState = vi.fn();
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({
            showVictoryDialog: true,
            endState: { status: 'victory', beta_end: true },
            setShowVictoryDialog,
            setEndState,
        }));

        renderGamePage();
        await act(async () => {
            fireEvent.click(screen.getByText('Close Victory'));
        });

        expect(setShowVictoryDialog).toHaveBeenCalledWith(false);
        expect(setEndState).toHaveBeenCalledWith(null);
        expect(refetchPlayer).toHaveBeenCalled();
        await waitFor(() => {
            expect(screen.getByTestId('beta-end-dialog')).toBeInTheDocument();
        });
    });

    it('transitions from the victory dialog to the loot dialog', () => {
        const setShowVictoryDialog = vi.fn();
        const setShowLootDialog = vi.fn();
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({
            showVictoryDialog: true,
            endState: { status: 'victory' },
            setShowVictoryDialog,
            setShowLootDialog,
        }));

        renderGamePage();
        fireEvent.click(screen.getByText('Continue To Loot'));

        expect(setShowVictoryDialog).toHaveBeenCalledWith(false);
        expect(setShowLootDialog).toHaveBeenCalledWith(true);
    });

    it('collects loot, calls the API, and shows the beta-end dialog on a beta-end kill', async () => {
        const setShowLootDialog = vi.fn();
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({
            showLootDialog: true,
            endState: { status: 'victory', beta_end: true },
            setShowLootDialog,
        }));

        renderGamePage();
        await act(async () => {
            fireEvent.click(screen.getByText('Collect Loot'));
        });

        expect(combatApi.collectLoot).toHaveBeenCalledWith(['Sword']);
        expect(setShowLootDialog).toHaveBeenCalledWith(false);
        await waitFor(() => expect(screen.getByTestId('beta-end-dialog')).toBeInTheDocument());
    });

    it('still closes the loot dialog and refetches when collectLoot fails', async () => {
        const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        combatApi.collectLoot.mockRejectedValue(new Error('server down'));
        const setShowLootDialog = vi.fn();
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({
            showLootDialog: true,
            endState: { status: 'victory' },
            setShowLootDialog,
        }));

        renderGamePage();
        await act(async () => {
            fireEvent.click(screen.getByText('Collect Loot'));
        });

        expect(errorSpy).toHaveBeenCalledWith('collect-loot failed:', expect.any(Error));
        expect(setShowLootDialog).toHaveBeenCalledWith(false);
        expect(refetchPlayer).toHaveBeenCalled();
        errorSpy.mockRestore();
    });

    it('skips loot with an empty collection call', async () => {
        const setShowLootDialog = vi.fn();
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({
            showLootDialog: true,
            endState: { status: 'victory' },
            setShowLootDialog,
        }));

        renderGamePage();
        await act(async () => {
            fireEvent.click(screen.getByText('Skip Loot'));
        });

        expect(combatApi.collectLoot).toHaveBeenCalledWith([]);
        expect(setShowLootDialog).toHaveBeenCalledWith(false);
    });

    it('closes the defeat dialog and refetches game state', async () => {
        const setShowDefeatDialog = vi.fn();
        const setEndState = vi.fn();
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({
            showDefeatDialog: true,
            endState: { status: 'defeat' },
            setShowDefeatDialog,
            setEndState,
        }));

        renderGamePage();
        await act(async () => {
            fireEvent.click(screen.getByText('Close Defeat'));
        });

        expect(setShowDefeatDialog).toHaveBeenCalledWith(false);
        expect(setEndState).toHaveBeenCalledWith(null);
        expect(refetchPlayer).toHaveBeenCalled();
    });

    it('allocates points from the victory dialog via the dynamically-imported endpoint', async () => {
        const { default: apiEndpoints } = await import('../api/endpoints');
        apiEndpoints.player.allocateLevelUpPoints.mockResolvedValue({ data: { success: true } });
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({
            showVictoryDialog: true,
            endState: { status: 'victory' },
        }));

        renderGamePage();
        await act(async () => {
            fireEvent.click(screen.getByText('Allocate From Victory'));
        });

        expect(apiEndpoints.player.allocateLevelUpPoints).toHaveBeenCalledWith('strength_base', 1);
        expect(refetchPlayer).toHaveBeenCalled();
        expect(fetchCombatStatus).toHaveBeenCalled();
    });

    it('shows the level-up modal outside of combat dialogs when points are pending', async () => {
        usePlayer.mockReturnValue({
            player: { ...mockPlayer, pending_attribute_points: 3 },
            loading: false,
            refetch: refetchPlayer,
        });
        const { default: apiEndpoints } = await import('../api/endpoints');
        apiEndpoints.player.allocateLevelUpPoints.mockResolvedValue({ data: { success: true } });

        renderGamePage();
        expect(screen.getByTestId('level-up-modal')).toBeInTheDocument();

        await act(async () => {
            fireEvent.click(screen.getByText('Allocate From LevelUp'));
        });
        expect(apiEndpoints.player.allocateLevelUpPoints).toHaveBeenCalledWith('faith_base', 1);
    });

    it('does not show the level-up modal while an event dialog is active', () => {
        usePlayer.mockReturnValue({
            player: { ...mockPlayer, pending_attribute_points: 3 },
            loading: false,
            refetch: refetchPlayer,
        });
        useEventManager.mockReturnValue(makeEventManagerReturn({ currentEvent: { name: 'Some Event' } }));

        renderGamePage();
        expect(screen.queryByTestId('level-up-modal')).not.toBeInTheDocument();
    });

    it('pauses and resumes the tactical advisor via the combat API', async () => {
        renderGamePage();
        fireEvent.click(screen.getByText('Pause Advisor'));

        await waitFor(() => {
            expect(combatApi.pauseSuggestions).toHaveBeenCalledWith(true);
        });
    });

    it('swallows a rejected pauseSuggestions call without crashing', async () => {
        combatApi.pauseSuggestions.mockRejectedValue(new Error('offline'));
        renderGamePage();
        expect(() => fireEvent.click(screen.getByText('Pause Advisor'))).not.toThrow();
        await waitFor(() => expect(combatApi.pauseSuggestions).toHaveBeenCalled());
    });

    it('requests fresh suggestions by refetching combat status', () => {
        renderGamePage();
        fireEvent.click(screen.getByText('Request Suggestions'));
        expect(fetchCombatStatus).toHaveBeenCalled();
    });

    it('shows a loading screen while player and world data are both unavailable', () => {
        usePlayer.mockReturnValue({ player: null, loading: true, refetch: refetchPlayer });
        useWorld.mockReturnValue({ location: null, loading: true, moveToLocation, refetch: refetchWorld });

        renderGamePage();
        expect(screen.getByText(/Loading your adventure/i)).toBeInTheDocument();
        expect(screen.queryByTestId('left-panel')).not.toBeInTheDocument();
    });

    it('opens and closes the beta feedback dialog from the beta-end screen', async () => {
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({
            showVictoryDialog: true,
            endState: { status: 'victory', beta_end: true },
        }));

        renderGamePage();
        await act(async () => { fireEvent.click(screen.getByText('Close Victory')); });
        await waitFor(() => expect(screen.getByTestId('beta-end-dialog')).toBeInTheDocument());

        fireEvent.click(screen.getByText('Send Feedback'));
        expect(screen.queryByTestId('beta-end-dialog')).not.toBeInTheDocument();
        expect(screen.getByTestId('feedback-dialog')).toBeInTheDocument();

        fireEvent.click(screen.getByText('Close Feedback'));
        expect(screen.queryByTestId('feedback-dialog')).not.toBeInTheDocument();
    });

    it('dismisses the beta-end dialog via Continue without opening feedback', async () => {
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({
            showVictoryDialog: true,
            endState: { status: 'victory', beta_end: true },
        }));

        renderGamePage();
        await act(async () => { fireEvent.click(screen.getByText('Close Victory')); });
        await waitFor(() => expect(screen.getByTestId('beta-end-dialog')).toBeInTheDocument());

        fireEvent.click(screen.getByText('Continue'));
        expect(screen.queryByTestId('beta-end-dialog')).not.toBeInTheDocument();
        expect(screen.queryByTestId('feedback-dialog')).not.toBeInTheDocument();
    });

    it('notifies interaction typing state changes to the event manager', () => {
        const setIsInteractionDelayActive = vi.fn();
        useEventManager.mockReturnValue(makeEventManagerReturn({ setIsInteractionDelayActive }));

        renderGamePage();
        fireEvent.click(screen.getByText('Start Typing'));
        expect(setIsInteractionDelayActive).toHaveBeenCalledWith(true);

        fireEvent.click(screen.getByText('Close Interaction'));
        expect(setIsInteractionDelayActive).toHaveBeenCalledWith(false);
    });

    it('dispatches a combat action through the coordinator wrapper', async () => {
        const handleCombatAction = vi.fn().mockResolvedValue({});
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({ handleCombatAction }));

        renderGamePage();
        fireEvent.click(screen.getByText('Combat Action'));

        await waitFor(() => {
            expect(handleCombatAction).toHaveBeenCalledWith(
                'attack', { target: 'enemy_1' }, expect.any(Function), expect.any(Function)
            );
        });
    });
});
