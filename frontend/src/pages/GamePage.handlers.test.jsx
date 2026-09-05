import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import GamePage from './GamePage';
import { capabilitiesDisabled } from '../test/mockHelpers';
import { usePlayer, useWorld, useCombat, useExploration, useAutosave } from '../hooks/useApi';
import { useEventManager } from '../hooks/useEventManager';
import { useCombatCoordinator } from '../hooks/useCombatCoordinator';
import { useMobile } from '../hooks/useMobile';
import { useAudio } from '../context/AudioContext';
import { useToast } from '../context/ToastContext';
import { combat as combatApi } from '../api/endpoints';
import { makePlayer, makeLocation } from '../test/payloads';
import { TAB_KEYS } from '../utils/mobileTabs';
import { COMBAT_INIT_EVENT_ID } from '../utils/eventIds';

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
}));

vi.mock('../context/CapabilitiesContext', () => ({
    useCapabilities: vi.fn(() => capabilitiesDisabled),
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
    default: ({ onMove, onCombatAction, onAdvisorPause, onAdvisorRequestSuggestions, onInteractionTypingChange, onInteractionClose, onMoveSubmitted }) => (
        <div data-testid="left-panel">
            <button onClick={() => onMove('north').catch(() => {})}>Move North</button>
            <button onClick={() => onCombatAction('attack', { target: 'enemy_1' })}>Combat Action</button>
            <button onClick={() => onAdvisorPause(true)}>Pause Advisor</button>
            <button onClick={() => onAdvisorRequestSuggestions()}>Request Suggestions</button>
            <button onClick={() => onInteractionTypingChange(true)}>Start Typing</button>
            <button onClick={() => onInteractionClose()}>Close Interaction</button>
            {onMoveSubmitted && <button onClick={onMoveSubmitted}>Move Submitted</button>}
        </div>
    )
}));

vi.mock('../components/RightPanel', () => ({
    default: ({ onDescriptionInteract }) => (
        <div data-testid="right-panel">
            {onDescriptionInteract && <button onClick={onDescriptionInteract}>Description Interact</button>}
        </div>
    )
}));

vi.mock('../components/EventManager', () => ({
    default: ({ currentEvent, onClose, onSubmitInput }) => (
        <div data-testid="event-manager">
            {currentEvent && <span>{currentEvent.name}</span>}
            <button onClick={onClose}>Close Event</button>
            <button onClick={() => onSubmitInput('event-1', 'some-input')}>Submit Event Input</button>
            <button onClick={() => onSubmitInput(COMBAT_INIT_EVENT_ID, 'combat_start')}>Confirm Combat Start</button>
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

// Renders `activeTab` so the tab-switch handlers are actually observable. A
// bare <div /> mock made "switches to the map tab" unassertable, and the three
// mobile tests degenerated into `expect(...).not.toThrow()`.
vi.mock('../components/MobileTabBar', () => ({
    default: ({ activeTab, mode }) => (
        <div data-testid="mobile-tab-bar" data-active-tab={activeTab} data-mode={mode} />
    ),
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
    // Derived from src/test/payloads.js so these carry the field names the
    // Python serializers actually emit (weight_current/carrying_capacity, not
    // the engine-side `weight_tolerance`), rather than whatever GamePage reads.
    const mockPlayer = makePlayer({ pending_attribute_points: 0 });
    const mockLocation = makeLocation({ name: 'Empty Cave', exits: ['north', 'east'] });
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
        useMobile.mockReturnValue(false);
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
        // GamePage polls combat status once on mount; discount that baseline so
        // the assertions below are about the move handler only.
        fetchCombatStatus.mockClear();
        fireEvent.click(screen.getByText('Move North'));

        await waitFor(() => {
            expect(moveToLocation).toHaveBeenCalledWith('north');
        });
        // Exactly one refetch and one autosave tick per successful move —
        // a duplicated tick would burn through AUTOSAVE_TICK_THRESHOLD twice
        // as fast, and a duplicated refetch doubles the request load.
        expect(refetchPlayer).toHaveBeenCalledTimes(1);
        expect(triggerTick).toHaveBeenCalledTimes(1);
        // No combat was started, so combat status must not be polled.
        expect(fetchCombatStatus).not.toHaveBeenCalled();
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
        fetchCombatStatus.mockClear();
        fireEvent.click(screen.getByText('Move North'));

        await waitFor(() => expect(fetchCombatStatus).toHaveBeenCalledTimes(1));
        // Combat polling happens *before* the player refetch, and the autosave
        // tick still runs — a combat start must not skip the post-move work.
        expect(refetchPlayer).toHaveBeenCalledTimes(1);
        expect(triggerTick).toHaveBeenCalledTimes(1);
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
        fetchCombatStatus.mockClear();
        fireEvent.click(screen.getByText('Confirm Combat Start'));

        expect(setMode_setCurrentEvent).toHaveBeenCalledWith(null);
        expect(setCombatDialogShown).toHaveBeenCalledWith(true);
        await waitFor(() => expect(fetchCombatStatus).toHaveBeenCalledTimes(1));
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
        expect(refetchPlayer).toHaveBeenCalledTimes(1);
        expect(refetchWorld).toHaveBeenCalledTimes(1);
    });

    it('does nothing extra when the event handler reports failure', async () => {
        const handleEventInput = vi.fn().mockResolvedValue({ success: false });
        useEventManager.mockReturnValue(makeEventManagerReturn({ handleEventInput }));

        renderGamePage();
        fireEvent.click(screen.getByText('Submit Event Input'));

        await waitFor(() =>
            expect(handleEventInput).toHaveBeenCalledWith('event-1', 'some-input', expect.any(Function))
        );
        expect(refetchPlayer).not.toHaveBeenCalled();
        expect(refetchWorld).not.toHaveBeenCalled();
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
        expect(refetchPlayer).toHaveBeenCalledTimes(1);
        expect(refetchWorld).toHaveBeenCalledTimes(1);
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
        // The failure is logged, not surfaced: the dialog still closes and the
        // player is still refetched, so a dropped loot call cannot soft-lock.
        expect(refetchPlayer).toHaveBeenCalledTimes(1);
        expect(screen.queryByTestId('beta-end-dialog')).not.toBeInTheDocument();
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
        expect(refetchPlayer).toHaveBeenCalledTimes(1);
        expect(refetchWorld).toHaveBeenCalledTimes(1);
    });

    it('allocates points from the victory dialog via the dynamically-imported endpoint', async () => {
        const { default: apiEndpoints } = await import('../api/endpoints');
        apiEndpoints.player.allocateLevelUpPoints.mockResolvedValue({ data: { success: true } });
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({
            showVictoryDialog: true,
            endState: { status: 'victory' },
        }));

        renderGamePage();
        fetchCombatStatus.mockClear();
        await act(async () => {
            fireEvent.click(screen.getByText('Allocate From Victory'));
        });

        expect(apiEndpoints.player.allocateLevelUpPoints).toHaveBeenCalledWith('strength_base', 1);
        expect(refetchPlayer).toHaveBeenCalledTimes(1);
        expect(fetchCombatStatus).toHaveBeenCalledTimes(1);
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
        fireEvent.click(screen.getByText('Pause Advisor'));

        await waitFor(() => expect(combatApi.pauseSuggestions).toHaveBeenCalledWith(true));
        // The rejection is swallowed: the page stays mounted and playable
        // rather than unmounting behind an error boundary.
        expect(screen.getByTestId('left-panel')).toBeInTheDocument();
    });

    it('requests fresh suggestions by refetching combat status', () => {
        renderGamePage();
        fetchCombatStatus.mockClear();
        fireEvent.click(screen.getByText('Request Suggestions'));
        expect(fetchCombatStatus).toHaveBeenCalledTimes(1);
        // Refreshing suggestions must not re-issue an advisor pause toggle.
        expect(combatApi.pauseSuggestions).not.toHaveBeenCalled();
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

    it('refreshes combat status when an event is processed while in combat', () => {
        useCombat.mockReturnValue({ combat: { log: [] }, inCombat: true, fetchCombatStatus, performAction });
        renderGamePage();

        const onEventProcessed = useEventManager.mock.calls[useEventManager.mock.calls.length - 1][0].onEventProcessed;
        fetchCombatStatus.mockClear();
        onEventProcessed();

        expect(fetchCombatStatus).toHaveBeenCalledTimes(1);
    });

    it('does not refresh combat status when an event is processed outside combat', () => {
        renderGamePage();

        const onEventProcessed = useEventManager.mock.calls[useEventManager.mock.calls.length - 1][0].onEventProcessed;
        fetchCombatStatus.mockClear();
        onEventProcessed();

        expect(fetchCombatStatus).not.toHaveBeenCalled();
    });

    it('logs and still closes the dialog when skip-loot collectLoot fails', async () => {
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
            fireEvent.click(screen.getByText('Skip Loot'));
        });

        expect(errorSpy).toHaveBeenCalledWith('collect-loot (skip) failed:', expect.any(Error));
        expect(combatApi.collectLoot).toHaveBeenCalledWith([]);
        expect(setShowLootDialog).toHaveBeenCalledWith(false);
        errorSpy.mockRestore();
    });

    it('shows the beta-end dialog after skipping loot on a beta-end victory', async () => {
        useCombatCoordinator.mockReturnValue(makeCombatCoordinatorReturn({
            showLootDialog: true,
            endState: { status: 'victory', beta_end: true },
        }));

        renderGamePage();
        await act(async () => {
            fireEvent.click(screen.getByText('Skip Loot'));
        });

        await waitFor(() => expect(screen.getByTestId('beta-end-dialog')).toBeInTheDocument());
    });

    it('forwards combat-triggered events to the event manager', () => {
        const handleEventsTriggered = vi.fn();
        useEventManager.mockReturnValue(makeEventManagerReturn({ handleEventsTriggered }));
        useCombat.mockReturnValue({
            combat: { log: [], events_triggered: [{ event_id: 'x', output_text: 'Ambush!' }] },
            inCombat: true,
            fetchCombatStatus,
            performAction,
        });

        renderGamePage();

        expect(handleEventsTriggered).toHaveBeenCalledWith([{ event_id: 'x', output_text: 'Ambush!' }]);
    });

    describe('mobile layout wiring', () => {
        beforeEach(() => {
            useMobile.mockReturnValue(true);
        });

        // On mobile exactly one panel slot is visible at a time; panelWrap()
        // sets display:none on the other. That is the user-visible consequence
        // of a tab switch, so assert it alongside the tab bar's own state.
        const visiblePanel = () => {
            const left = screen.getByTestId('left-panel').parentElement.style.display;
            const right = screen.getByTestId('right-panel').parentElement.style.display;
            return { left, right };
        };
        const activeTab = () => screen.getByTestId('mobile-tab-bar').dataset.activeTab;

        it('starts on the character tab with only the left panel visible', () => {
            renderGamePage();

            expect(activeTab()).toBe(TAB_KEYS.left);
            expect(visiblePanel()).toEqual({ left: 'flex', right: 'none' });
        });

        it('switches to the map tab when a move is submitted', () => {
            renderGamePage();

            fireEvent.click(screen.getByText('Move Submitted'));

            expect(activeTab()).toBe(TAB_KEYS.right);
            // The battlefield/map slot takes over the screen.
            expect(visiblePanel()).toEqual({ left: 'none', right: 'flex' });
        });

        it('switches back to the character tab when the room description is interacted with', () => {
            renderGamePage();
            fireEvent.click(screen.getByText('Move Submitted'));
            expect(activeTab()).toBe(TAB_KEYS.right);

            fireEvent.click(screen.getByText('Description Interact'));

            expect(activeTab()).toBe(TAB_KEYS.left);
            expect(visiblePanel()).toEqual({ left: 'flex', right: 'none' });
        });

        it('renders the tab bar in exploration mode and hides it on desktop', () => {
            const { unmount } = renderGamePage();
            // `mode` drives only the tab LABELS; the keys must not vary by it.
            expect(screen.getByTestId('mobile-tab-bar').dataset.mode).toBe('exploration');
            unmount();

            useMobile.mockReturnValue(false);
            renderGamePage();
            expect(screen.queryByTestId('mobile-tab-bar')).not.toBeInTheDocument();
            // Desktop shows both panels side by side (display: contents).
            expect(screen.getByTestId('left-panel').parentElement.style.display).toBe('contents');
            expect(screen.getByTestId('right-panel').parentElement.style.display).toBe('contents');
        });
    });
});
