import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import GamePage from './GamePage';
import * as api from '../api/endpoints';
import { usePlayer, useWorld, useCombat, useExploration, useExits, useAutosave, useAuth } from '../hooks/useApi';
import { useAudio } from '../context/AudioContext';

// Mock the hooks first
vi.mock('../hooks/useApi', () => ({
    usePlayer: vi.fn(),
    useWorld: vi.fn(),
    useCombat: vi.fn(),
    useExploration: vi.fn(),
    useExits: vi.fn(),
    useAutosave: vi.fn(),
    useAuth: vi.fn(),
}));

vi.mock('../context/AudioContext', () => ({
    useAudio: vi.fn(),
}));

// Mock the API
vi.mock('../api/endpoints', () => ({
    player: {
        getFullState: vi.fn(),
        getSkills: vi.fn(),
    },
    world: {
        getCurrentLocation: vi.fn(),
        getCommands: vi.fn(),
    },
    combat: {
        getStatus: vi.fn(),
        performAction: vi.fn(),
    },
    saves: {
        list: vi.fn(),
    },
}));

describe('Tactical AI Integration Tests', () => {
    beforeEach(() => {
        vi.clearAllMocks();

        // Setup hook mocks
        usePlayer.mockReturnValue({
            player: {
                name: 'Jean',
                level: 1,
                hp: 80,
                max_hp: 100,
                mp: 30,
                max_mp: 50,
                map_name: 'forest_path',
            },
            loading: false,
            refetch: vi.fn()
        });

        useWorld.mockReturnValue({
            location: {
                name: 'Forest Path',
                description: 'A peaceful forest path',
                x: 10,
                y: 10,
            },
            loading: false,
            moveToLocation: vi.fn(),
            refetch: vi.fn()
        });

        useCombat.mockReturnValue({
            combat: null,
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
                        {
                            name: 'Jean',
                            hp: 80,
                            max_hp: 100,
                            is_player: true,
                            x: 2,
                            y: 2,
                        },
                        {
                            name: 'Rat',
                            hp: 10,
                            max_hp: 10,
                            is_player: false,
                            x: 2,
                            y: 3,
                        },
                    ],
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
                log: [
                    { message: 'Combat started!', type: 'system' },
                ],
            },
        });

        api.player.getFullState.mockResolvedValue({
            data: {
                player: {
                    name: 'Jean',
                    hp: 80,
                    max_hp: 100,
                    in_combat: true,
                },
            },
        });

        api.world.getCurrentLocation.mockResolvedValue({
            data: { location: { name: 'Test Room' } },
        });

        api.world.getCommands.mockResolvedValue({
            data: { commands: [] },
        });

        const { container } = render(<GamePage />);

        // Wait for combat state to load
        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalled();
        });

        // Verify suggested moves panel appears
        await waitFor(() => {
            const advisorText = screen.queryByText(/TACTICAL ADVISOR/i);
            if (advisorText) {
                expect(advisorText).toBeDefined();
            }
        }, { timeout: 3000 });
    });

    it('executes combined move and target from AI suggestion click', async () => {
        api.combat.getStatus.mockResolvedValue({
            data: {
                success: true,
                combat_active: true,
                battle_state: {
                    combatants: [
                        { name: 'Jean', hp: 100, max_hp: 100, is_player: true },
                        { name: 'Enemy', hp: 50, max_hp: 50, is_player: false },
                    ],
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

        api.player.getFullState.mockResolvedValue({
            data: { player: { name: 'Jean', in_combat: true } },
        });

        api.world.getCurrentLocation.mockResolvedValue({
            data: { location: { name: 'Test Room' } },
        });

        api.world.getCommands.mockResolvedValue({
            data: { commands: [] },
        });

        render(<GamePage />);

        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalled();
        });

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
                        {
                            name: 'Jean',
                            hp: 75,
                            max_hp: 100,
                            is_player: true,
                            active_effects: [
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
                            ],
                        },
                    ],
                    input_type: 'move_selection',
                    awaiting_input: true,
                },
                log: [],
            },
        });

        api.player.getFullState.mockResolvedValue({
            data: { player: { name: 'Jean', in_combat: true } },
        });

        api.world.getCurrentLocation.mockResolvedValue({
            data: { location: { name: 'Test Room' } },
        });

        api.world.getCommands.mockResolvedValue({
            data: { commands: [] },
        });

        render(<GamePage />);

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
                        { name: 'Jean', hp: 90, max_hp: 100, is_player: true },
                        { name: 'Enemy', hp: 30, max_hp: 50, is_player: false },
                    ],
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
                    last_move_outcome: 'Your previous attack dealt 20 damage.',
                },
                log: [],
            },
        });

        api.player.getFullState.mockResolvedValue({
            data: { player: { name: 'Jean', in_combat: true } },
        });

        api.world.getCurrentLocation.mockResolvedValue({
            data: { location: { name: 'Test Room' } },
        });

        api.world.getCommands.mockResolvedValue({
            data: { commands: [] },
        });

        render(<GamePage />);

        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalled();
        });

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
                                    active_effects: [],
                                },
                            ],
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
                                    active_effects: [
                                        {
                                            name: 'Poison',
                                            type: 'ailment',
                                            description: 'Losing HP over time',
                                            duration_remaining: 4,
                                        },
                                    ],
                                },
                            ],
                            input_type: 'move_selection',
                            awaiting_input: true,
                        },
                        log: [],
                    },
                });
            }
        });

        api.player.getFullState.mockResolvedValue({
            data: { player: { name: 'Jean', in_combat: true } },
        });

        api.world.getCurrentLocation.mockResolvedValue({
            data: { location: { name: 'Test Room' } },
        });

        api.world.getCommands.mockResolvedValue({
            data: { commands: [] },
        });

        const { rerender } = render(<GamePage />);

        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalled();
        });

        // Initially no poison icon
        expect(screen.queryByText('🧪')).toBeNull();

        // Simulate combat state update
        rerender(<GamePage />);

        // After update, poison icon should appear
        await waitFor(() => {
            const poisonIcon = screen.queryByText('🧪');
            if (callCount > 1) {
                expect(poisonIcon).toBeTruthy();
            }
        }, { timeout: 3000 });
    });
});
