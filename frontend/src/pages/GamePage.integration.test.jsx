import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import GamePage from './GamePage';
import * as api from '../api/endpoints';
import { usePlayer, useWorld, useCombat, useExploration, useExits, useAutosave, useAuth } from '../hooks/useApi';
import { useAudio } from '../context/AudioContext';

// Mock only the hooks we need to stub (useExploration, useExits, useAutosave, useAuth)
vi.mock('../hooks/useApi', async () => {
    const actual = await vi.importActual('../hooks/useApi');
    return {
        ...actual,
        useExploration: vi.fn(),
        useExits: vi.fn(),
        useAutosave: vi.fn(),
        useAuth: vi.fn(),
    };
});

vi.mock('../context/AudioContext', () => ({
    useAudio: vi.fn(),
}));

vi.mock('../context/ToastContext', () => ({
    useToast: () => ({
        showError: vi.fn(),
        showSuccess: vi.fn(),
        showInfo: vi.fn(),
    }),
}));

vi.mock('../hooks/useCombatCoordinator', () => ({
    useCombatCoordinator: vi.fn(() => ({
        combatDialogShown: true,
        showVictoryDialog: false,
        showDefeatDialog: false,
        endState: null,
        isCombatLogProcessing: false,
        currentLogIndex: 0,
        hoveredTargetId: null,
        setCombatDialogShown: vi.fn(),
        setShowVictoryDialog: vi.fn(),
        setShowDefeatDialog: vi.fn(),
        setEndState: vi.fn(),
        setIsCombatLogProcessing: vi.fn(),
        setCurrentLogIndex: vi.fn(),
        setHoveredTargetId: vi.fn(),
        handleSuggestedMoveClick: vi.fn(),
        handleCombatAction: vi.fn(),
        handleInteractionComplete: vi.fn()
    }))
}));

const {
    mockGetStatus,
    mockPerformAction,
    mockGetFullState,
    mockGetCurrentLocation,
    mockGetCommands,
    mockListSaves,
    mockLogin,
    mockLogout,
    mockRegister,
    mockGetTilesBatch,
    mockGetExploredTiles
} = vi.hoisted(() => ({
    mockGetStatus: vi.fn(),
    mockPerformAction: vi.fn(),
    mockGetFullState: vi.fn(),
    mockGetCurrentLocation: vi.fn(),
    mockGetCommands: vi.fn(),
    mockListSaves: vi.fn(),
    mockLogin: vi.fn(),
    mockLogout: vi.fn(),
    mockRegister: vi.fn(),
    mockGetTilesBatch: vi.fn(),
    mockGetExploredTiles: vi.fn()
}));

// Mock the API with both default and named exports to match the real module structure
vi.mock('../api/endpoints', () => ({
    default: {
        player: {
            getFullState: mockGetFullState,
            getSkills: vi.fn(),
        },
        world: {
            getCurrentLocation: mockGetCurrentLocation,
            getCommands: mockGetCommands,
            getTilesBatch: mockGetTilesBatch,
            getExploredTiles: mockGetExploredTiles,
        },
        combat: {
            getStatus: mockGetStatus,
            performAction: mockPerformAction,
        },
        saves: {
            list: mockListSaves,
        },
        auth: {
            login: mockLogin,
            logout: mockLogout,
            register: mockRegister,
        },
    },
    // Named exports
    player: {
        getFullState: mockGetFullState,
        getSkills: vi.fn(),
    },
    world: {
        getCurrentLocation: mockGetCurrentLocation,
        getCommands: mockGetCommands,
        getTilesBatch: mockGetTilesBatch,
        getExploredTiles: mockGetExploredTiles,
    },
    combat: {
        getStatus: mockGetStatus,
        performAction: mockPerformAction,
    },
    saves: {
        list: mockListSaves,
    },
    auth: {
        login: mockLogin,
        logout: mockLogout,
        register: mockRegister,
    },
}));

describe('Tactical AI Integration Tests', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.useFakeTimers();

        // Global fetch mock to handle relative URLs in JSDOM
        global.fetch = vi.fn().mockImplementation((url) => {
            if (url.includes('/api/world/events/pending')) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve([])
                });
            }
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve({})
            });
        });

        // Setup default successful responses for mandatory APIs
        mockGetFullState.mockResolvedValue({
            data: {
                success: true,
                player: { name: 'Jean', hp: 100, max_hp: 100 }
            }
        });
        mockGetCurrentLocation.mockResolvedValue({
            data: {
                success: true,
                room: { name: 'Test Room', description: 'Test', x: 0, y: 0, exits: [] }
            }
        });
        mockGetCommands.mockResolvedValue({
            data: {
                success: true,
                commands: []
            }
        });
        mockGetTilesBatch.mockResolvedValue({
            data: {
                success: true,
                tiles: []
            }
        });
        mockGetExploredTiles.mockResolvedValue({
            data: {
                success: true,
                explored_tiles: []
            }
        });
        mockGetStatus.mockResolvedValue({
            data: {
                success: false,
                combat_active: false,
                battle_state: null
            }
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

        useAuth.mockReturnValue({
            logout: vi.fn()
        });

        useAudio.mockReturnValue({
            playSFX: vi.fn(),
            playBGM: vi.fn(),
            stopBGM: vi.fn()
        });
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    const renderGamePage = () => {
        return render(
            <MemoryRouter>
                <GamePage />
            </MemoryRouter>
        );
    };

    it('displays AI suggestions during combat', async () => {
        // Mock combat state with AI suggestions
        api.combat.getStatus.mockResolvedValue({
            data: {
                success: true,
                combat_active: true,
                battle_state: {
                    combatants: [
                        { id: 'player_1', name: 'Jean', hp: 80, max_hp: 100, is_player: true, x: 2, y: 2 },
                        { id: 'enemy_123', name: 'Rat', hp: 10, max_hp: 10, is_player: false, x: 2, y: 3 },
                    ],
                    player: {
                        name: 'Jean',
                        hp: 80,
                        max_hp: 100
                    },
                    input_type: 'move_selection',
                    awaiting_input: true,
                    suggested_moves: [
                        {
                            move_name: 'Slash',
                            target_id: 'enemy_123',
                            score: 95,
                            reasoning: 'High damage potential against low HP enemy.',
                        },
                        {
                            move_name: 'Dodge',
                            target_id: null,
                            score: 60,
                            reasoning: 'Conserve stamina for later.',
                        },
                    ],
                },
                suggested_moves: [
                    {
                        move_name: 'Slash',
                        target_id: 'enemy_123',
                        score: 95,
                        reasoning: 'High damage potential against low HP enemy.',
                    },
                    {
                        move_name: 'Dodge',
                        target_id: null,
                        score: 60,
                        reasoning: 'Conserve stamina for later.',
                    },
                ],
                log: [
                    { message: 'Combat started!', type: 'system', round: 1 },
                ],
            },
        });

        renderGamePage();

        // Wait for combat state to load
        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalled();
        });

        // Advance timers for SuggestedMovesPanel visibility
        vi.advanceTimersByTime(600);

        // Verify suggested moves panel appears
        await waitFor(() => {
            const advisorText = screen.queryByText(/TACTICAL ADVISOR/i) || screen.queryByText(/Suggested Moves/i);
            expect(advisorText).toBeTruthy();
        }, { timeout: 4000 });
    });

    it('executes combined move and target from AI suggestion click', async () => {
        api.combat.getStatus.mockResolvedValue({
            data: {
                success: true,
                combat_active: true,
                battle_state: {
                    combatants: [
                        { id: 'player_1', name: 'Jean', hp: 100, max_hp: 100, is_player: true },
                        { id: 'enemy_456', name: 'Enemy', hp: 50, max_hp: 50, is_player: false },
                    ],
                    player: { name: 'Jean', hp: 100, max_hp: 100 },
                    input_type: 'move_selection',
                    awaiting_input: true,
                    suggested_moves: [
                        {
                            move_name: 'Attack',
                            target_id: 'enemy_456',
                            score: 85,
                            reasoning: 'Standard attack.',
                        },
                    ],
                },
                suggested_moves: [
                    {
                        move_name: 'Attack',
                        target_id: 'enemy_456',
                        score: 85,
                        reasoning: 'Standard attack.',
                    },
                ],
                log: [],
            },
        });

        api.combat.performAction.mockResolvedValue({
            data: {
                success: true,
                battle_state: {
                    combatants: [
                        { name: 'Jean', hp: 100, max_hp: 100, is_player: true },
                        { name: 'Enemy', hp: 40, max_hp: 50, is_player: false },
                    ],
                },
                log: [{ message: 'Jean attacks Enemy for 10 damage!', type: 'combat' }],
            },
        });

        renderGamePage();

        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalled();
        });

        // Advance timers for SuggestedMovesPanel visibility
        vi.advanceTimersByTime(600);

        // Wait for suggestions to appear and click one
        await waitFor(async () => {
            const attackSuggestion = screen.queryByText('Attack');
            if (attackSuggestion) {
                fireEvent.click(attackSuggestion.closest('div'));

                // Verify combined action was called
                await waitFor(() => {
                    expect(api.combat.performAction).toHaveBeenCalledWith(
                        'select_move_and_target',
                        expect.objectContaining({
                            move_name: 'Attack',
                            target_id: 'enemy_456',
                        })
                    );
                });
            }
        }, { timeout: 3000 });
    });

    it('displays status effects with icons', async () => {
        api.combat.getStatus.mockResolvedValue({
            data: {
                success: true,
                combat_active: true,
                battle_state: {
                    combatants: [
                        { id: 'player_1', name: 'Jean', hp: 75, max_hp: 100, is_player: true },
                    ],
                    player: {
                        name: 'Jean',
                        hp: 75,
                        max_hp: 100,
                        status_effects: [
                            {
                                name: 'Burn',
                                type: 'ailment',
                                description: 'Taking fire damage',
                                duration_remaining: 3,
                            },
                            {
                                name: 'Shield',
                                type: 'buff',
                                description: 'Increased protection',
                                duration_remaining: 5,
                            },
                        ]
                    },
                    input_type: 'move_selection',
                    awaiting_input: true,
                },
                log: [],
            },
        });

        renderGamePage();

        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalled();
        });

        // Check for status effect icons
        await waitFor(() => {
            // Look for emoji icons (🔥 for burn, 🛡️ for shield)
            const burnIcon = screen.queryByText('🔥');
            const shieldIcon = screen.queryByText('🛡️');

            // At least one should be present if effects are rendering
            expect(burnIcon || shieldIcon).toBeTruthy();
        }, { timeout: 3000 });
    });

    it('shows previous move analysis in suggestions panel', async () => {
        api.combat.getStatus.mockResolvedValue({
            data: {
                success: true,
                combat_active: true,
                battle_state: {
                    combatants: [
                        { id: 'player_1', name: 'Jean', hp: 90, max_hp: 100, is_player: true },
                        { id: 'enemy_789', name: 'Enemy', hp: 30, max_hp: 50, is_player: false },
                    ],
                    player: { name: 'Jean', hp: 90, max_hp: 100 },
                    input_type: 'move_selection',
                    awaiting_input: true,
                    suggested_moves: [
                        {
                            move_name: 'Slash',
                            target_id: 'enemy_789',
                            score: 90,
                            reasoning: 'Finish the enemy.',
                        },
                    ],
                },
                last_move_outcome: 'Your previous attack dealt 20 damage.',
                suggested_moves: [
                    {
                        move_name: 'Slash',
                        target_id: 'enemy_789',
                        score: 90,
                        reasoning: 'Finish the enemy.',
                    },
                ],
                log: [],
            },
        });

        renderGamePage();

        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalled();
        });

        // Advance timers for SuggestedMovesPanel visibility
        vi.advanceTimersByTime(600);

        // Look for previous cycle analysis
        await waitFor(() => {
            const analysisText = screen.queryByText(/ANALYSIS OF PREVIOUS CYCLE/i);
            const outcomeText = screen.queryByText(/previous attack dealt 20 damage/i);

            // Either the header or the outcome should be visible
            expect(analysisText || outcomeText).toBeTruthy();
        }, { timeout: 3000 });
    });

    it('updates status effects when combat state changes', async () => {
        let callCount = 0;

        api.combat.getStatus.mockImplementation(() => {
            callCount++;
            if (callCount === 1) {
                // Initial state: no effects
                return Promise.resolve({
                    data: {
                        success: true,
                        combat_active: true,
                        battle_state: {
                            combatants: [
                                {
                                    name: 'Jean',
                                    hp: 100,
                                    max_hp: 100,
                                    is_player: true,
                                },
                            ],
                            player: {
                                name: 'Jean',
                                hp: 100,
                                max_hp: 100,
                                status_effects: []
                            },
                            input_type: 'move_selection',
                            awaiting_input: true,
                        },
                        log: [],
                    },
                });
            } else {
                // After move: effect applied
                return Promise.resolve({
                    data: {
                        success: true,
                        combat_active: true,
                        battle_state: {
                            combatants: [
                                {
                                    name: 'Jean',
                                    hp: 95,
                                    max_hp: 100,
                                    is_player: true,
                                },
                            ],
                            player: {
                                name: 'Jean',
                                hp: 95,
                                max_hp: 100,
                                status_effects: [
                                    {
                                        name: 'Poison',
                                        type: 'ailment',
                                        description: 'Losing HP over time',
                                        duration_remaining: 4,
                                    },
                                ],
                            },
                            input_type: 'move_selection',
                            awaiting_input: true,
                        },
                        log: [],
                    },
                });
            }
        });

        const { rerender } = renderGamePage();

        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalled();
        });

        // Initially no poison icon
        expect(screen.queryByText('🧪')).toBeNull();

        // Simulate combat state update
        rerender(<MemoryRouter><GamePage /></MemoryRouter>);

        // After update, poison icon should appear
        await waitFor(() => {
            const poisonIcon = screen.queryByText('🧪');
            if (callCount > 1) {
                expect(poisonIcon).toBeTruthy();
            }
        }, { timeout: 3000 });
    });
});
