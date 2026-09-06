import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import GamePage from './GamePage'
import { makeStatusEffect, makeCombatant, makeEnemy } from '../test/payloads';
import { capabilitiesDisabled } from '../test/mockHelpers';
import * as api from '../api/endpoints';
import { usePlayer, useWorld, useCombat, useExploration, useExits, useAutosave } from '../hooks/useApi';
import { useAudio } from '../context/AudioContext';

// `useEventManager` is not stubbed here, so its mount-time
// `/world/events/pending` fetch would go out over the real axios client and
// settle after teardown on a loaded runner — an unhandled
// `ReferenceError: window is not defined` that fails the run with every test
// green. `../api/endpoints` being mocked does not cover this: the hook holds
// the client directly.
vi.mock('../api/client', () => ({
    default: {
        get: vi.fn(() => Promise.resolve({ data: { success: true, events: [] } })),
        post: vi.fn(() => Promise.resolve({ data: { success: true } })),
        delete: vi.fn(() => Promise.resolve({ data: { success: true } })),
    },
}));

// Mock only the hooks we need to stub (useExploration, useExits, useAutosave)
vi.mock('../hooks/useApi', async () => {
    const actual = await vi.importActual('../hooks/useApi');
    return {
        ...actual,
        useExploration: vi.fn(),
        useExits: vi.fn(),
        useAutosave: vi.fn(),
    };
});

vi.mock('../context/CapabilitiesContext', () => ({
    useCapabilities: vi.fn(() => capabilitiesDisabled),
}));

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
    useCombatCoordinator: vi.fn(({ performAction }) => ({
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
        handleSuggestedMoveClick: vi.fn((suggestion) => {
            return performAction('select_move_and_target', {
                move_name: suggestion.move_name,
                target_id: suggestion.target_id
            });
        }),
        handleCombatAction: vi.fn((action, target) => {
            return performAction(action, target);
        }),
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
                status: { name: 'Jean', hp: 100, max_hp: 100, fatigue: 0, max_fatigue: 150 },
                stats: { strength: 10, finesse: 10, speed: 10, endurance: 10 },
                skills: { offensive: [], defensive: [] },
                inventory: { items: [] }
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

        useAudio.mockReturnValue({
            playSFX: vi.fn(),
            playBGM: vi.fn(),
            stopBGM: vi.fn()
        });
    });

    afterEach(() => {
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
                    // Built from src/test/payloads.js: CombatantSerializer marks
                    // sides with `type: 'player' | 'npc'`, NOT the `is_player`
                    // flag these fixtures used to invent (that field exists only
                    // on the thinner start_combat combatants list). A fixture
                    // that names a key the serializer never emits cannot fail.
                    combatants: [
                        makeCombatant({ id: 'player_1', name: 'Jean', hp: 80, max_hp: 100, health: { current: 80, max: 100 }, position: { x: 2, y: 2, facing: 'N' } }),
                        makeEnemy({ id: 'enemy_123', name: 'Rat', hp: 10, max_hp: 10, health: { current: 10, max: 10 }, position: { x: 2, y: 3, facing: 'S' } }),
                    ],
                    player: makeCombatant({ name: 'Jean', hp: 80, max_hp: 100, health: { current: 80, max: 100 } }),
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

        // Wait for combat state to load (via polling or initial effects)
        // We might need to wait for the 2s poll if it doesn't fetch on mount
        // `getStatus` takes no arguments, so there is nothing to assert about
        // the call itself — it is used purely as a "combat has loaded" gate,
        // and the real assertions follow.
        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalledWith();
        }, { timeout: 10000 });

        // The panel HEADER was the only thing asserted here, so the panel
        // could have rendered empty — or dropped every suggestion the API
        // returned — and the test still passed. Assert the suggestions.
        expect(await screen.findByText(/TACTICAL ADVISOR/i, {}, { timeout: 10000 })).toBeInTheDocument();
        expect(screen.getByText('Slash')).toBeInTheDocument();
        expect(screen.getByText('Dodge')).toBeInTheDocument();
        expect(screen.getByText(/High damage potential against low HP enemy\./)).toBeInTheDocument();
    }, 15000);

    it('executes combined move and target from AI suggestion click', async () => {
        api.combat.getStatus.mockResolvedValue({
            data: {
                success: true,
                combat_active: true,
                battle_state: {
                    combatants: [
                        makeCombatant({ id: 'player_1', name: 'Jean' }),
                        makeEnemy({ id: 'enemy_456', name: 'Enemy', hp: 50, max_hp: 50, health: { current: 50, max: 50 } }),
                    ],
                    player: makeCombatant({ name: 'Jean' }),
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
                        makeCombatant({ name: 'Jean' }),
                        makeEnemy({ name: 'Enemy', hp: 40, max_hp: 50, health: { current: 40, max: 50 } }),
                    ],
                },
                log: [{ message: 'Jean attacks Enemy for 10 damage!', type: 'combat' }],
            },
        });

        renderGamePage();

        // The entire body of this test used to sit inside
        // `if (attackSuggestion) { ... }` within a waitFor callback. When the
        // suggestion never rendered — the exact regression the test exists to
        // catch — the callback returned undefined, waitFor resolved, and the
        // test passed having asserted nothing at all. findByText makes the
        // missing suggestion a failure instead.
        const attackSuggestion = await screen.findByText('Attack', {}, { timeout: 8000 });
        fireEvent.click(attackSuggestion.closest('div'));

        await waitFor(() => {
            expect(api.combat.performAction).toHaveBeenCalledWith(
                'select_move_and_target',
                expect.objectContaining({
                    move_name: 'Attack',
                    target_id: 'enemy_456',
                })
            );
        }, { timeout: 8000 });
        // One click, one action: a double dispatch burns two combat beats.
        expect(api.combat.performAction).toHaveBeenCalledTimes(1);
    }, 20000);

    it('displays status effects with icons', async () => {
        api.combat.getStatus.mockResolvedValue({
            data: {
                success: true,
                combat_active: true,
                battle_state: {
                    combatants: [
                        makeCombatant({ id: 'player_1', name: 'Jean', hp: 75, max_hp: 100, health: { current: 75, max: 100 } }),
                    ],
                    player: {
                        name: 'Jean',
                        hp: 75,
                        max_hp: 100,
                        // `beats_left`, not `duration_remaining`:
                        // StateEffectSerializer.serialize_state (the live path
                        // that actually feeds this component) emits the former;
                        // the latter comes from serialize_state_with_duration,
                        // which has no callers. Encoding the dead name here was
                        // wire-drift bug #4 reproduced inside the fixture.
                        status_effects: [
                            makeStatusEffect({
                                name: 'Burn',
                                type: 'ailment',
                                description: 'Taking fire damage',
                                beats_left: 3,
                            }),
                            makeStatusEffect({
                                name: 'Shield',
                                type: 'buff',
                                description: 'Increased protection',
                                beats_left: 5,
                            }),
                        ]
                    },
                    input_type: 'move_selection',
                    awaiting_input: true,
                },
                log: [],
            },
        });

        renderGamePage();

        // Both effects must reach the panel. The previous assertion was
        // `burnIcons.length + shieldIcons.length > 0`, which passes when one of
        // the two is dropped — and would still pass if the list were truncated
        // to a single entry.
        await waitFor(() => {
            expect(screen.queryAllByText('🔥').length).toBeGreaterThan(0);
        }, { timeout: 8000 });
        expect(screen.queryAllByText('🛡️').length).toBeGreaterThan(0);

        // And the tooltip reads the effect's own beats_left, so a fixture using
        // the dead `duration_remaining` name would show nothing here.
        fireEvent.mouseEnter(screen.queryAllByText('🔥')[0]);
        expect(screen.getByText('3 beats remaining').textContent).toBe('3 beats remaining');
    }, 15000);

    it('shows previous move analysis in suggestions panel', async () => {
        api.combat.getStatus.mockResolvedValue({
            data: {
                success: true,
                combat_active: true,
                battle_state: {
                    combatants: [
                        makeCombatant({ id: 'player_1', name: 'Jean', hp: 90, max_hp: 100, health: { current: 90, max: 100 } }),
                        makeEnemy({ id: 'enemy_789', name: 'Enemy', hp: 30, max_hp: 50, health: { current: 30, max: 50 } }),
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

        // Zero-argument poll; a load gate, not an assertion (see above).
        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalledWith();
        }, { timeout: 10000 });

        // `expect(analysisText || outcomeText).toBeTruthy()` let the test pass
        // on the analysis LABEL alone — i.e. with last_move_outcome dropped
        // entirely, which is the one field this test is named for. Assert the
        // outcome copy itself.
        expect(await screen.findByText(/TACTICAL ADVISOR/i, {}, { timeout: 10000 })).toBeInTheDocument();
        expect(screen.getByText(/ANALYSIS OF PREVIOUS CYCLE/i)).toBeInTheDocument();
        expect(screen.getByText(/previous attack dealt 20 damage/i)).toBeInTheDocument();
    }, 15000);

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
                        suggestions_loading: true, // Trigger poll
                        battle_state: {
                            combatants: [makeCombatant({ name: 'Jean' })],
                            player: makeCombatant({ name: 'Jean', status_effects: [] }),
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
                        suggestions_loading: false, // End poll
                        battle_state: {
                            combatants: [makeCombatant({ name: 'Jean', hp: 95, health: { current: 95, max: 100 } })],
                            player: makeCombatant({
                                name: 'Jean',
                                hp: 95,
                                health: { current: 95, max: 100 },
                                status_effects: [
                                    makeStatusEffect({
                                        name: 'Poison',
                                        type: 'ailment',
                                        description: 'Losing HP over time',
                                        beats_left: 4,
                                    }),
                                ],
                            }),
                            input_type: 'move_selection',
                            awaiting_input: true,
                        },
                        log: [],
                    },
                });
            }
        });

        renderGamePage();

        // Zero-argument poll; a load gate, not an assertion (see above).
        await waitFor(() => {
            expect(api.combat.getStatus).toHaveBeenCalledWith();
        }, { timeout: 10000 });

        // Initially no poison icon
        expect(screen.queryAllByText('🧪')).toHaveLength(0);

        // After the poll delivers the second state, the poison effect shows —
        // picked up without a remount.
        //
        // queryAllByText, not findByText/queryByText: the effect legitimately
        // renders on more than one surface at once (the battlefield token's
        // StatusEffectsIconPanel and the panels beside it), and the
        // single-match queries THROW on multiple matches rather than returning
        // the first. That turned a passing render into a retry loop that ran out
        // the waitFor budget, so the failure surfaced as a ~10s "timeout" and
        // read as load flakiness — it was an over-specific query all along.
        await waitFor(() => {
            expect(screen.queryAllByText('🧪').length).toBeGreaterThan(0);
        }, { timeout: 10000 });

        // Visibility is only half of it: the effect must also carry its name and
        // remaining duration, which is what the player actually reads.
        fireEvent.mouseEnter(screen.queryAllByText('🧪')[0]);
        expect(screen.getAllByText('POISON').length).toBeGreaterThan(0);
        expect(screen.getAllByText('4 beats remaining').length).toBeGreaterThan(0);
        // The test budget must exceed the sum of the waitFor budgets above.
        // At 10000 it equalled a single wait, so under parallel full-suite load
        // the test timed out before its own waits could resolve — a flake that
        // only ever reproduced in a full run, never in isolation.
    }, 25000);
});
