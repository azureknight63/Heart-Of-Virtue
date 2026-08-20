import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Battlefield from './Battlefield';
import React from 'react';
import { makeBattleState, makeCombatant, makeEnemy } from '../test/payloads';

// Mock child components. Battlefield also imports the VIEW_SIZE constant for
// its off-screen-enemy detection, so expose it on the mock.
//
// The mock RECORDS the props it was handed rather than destructuring only the
// three it renders: Battlefield's job for combatId/mapSize is pure forwarding
// from the top-level combat object, and a stub that ignores those props cannot
// tell a correct forward from a deleted one.
const gridProps = [];
vi.mock('./BattlefieldGrid', () => ({
    VIEW_SIZE: 13,
    default: (props) => {
        gridProps.push(props);
        return (
            <div data-testid="grid">
                Grid - Tab: {props.tab} - Zoom: {props.zoom}
                Combatant: {props.combat?.combatants?.[0]?.name}
            </div>
        );
    }
}));

const lastGridProps = () => gridProps[gridProps.length - 1];

const mockCombat = {
    enemies: [{ name: 'Slime', hp: 10, max_hp: 10 }],
    combatants: [{ name: 'Jean', position: [0, 0] }],
    beat_states: [
        {
            combatants: [{ name: 'Jean', position: [0, 0] }],
            enemies: [{ name: 'Slime', hp: 10, max_hp: 10 }]
        },
        {
            combatants: [{ name: 'Jean', position: [1, 1] }],
            enemies: [{ name: 'Slime', hp: 5, max_hp: 10 }]
        }
    ]
};

describe('Battlefield', () => {
    it('shows "No active combat" when there is no combat data', () => {
        render(<Battlefield combat={null} />);
        expect(screen.getByText(/No active combat/i)).toBeInTheDocument();
        expect(screen.queryByTestId('grid')).not.toBeInTheDocument();
    });

    it('detects an off-screen enemy whose HP comes from health.current instead of hp', async () => {
        const offScreenCombat = {
            beat_states: [
                {
                    player: { name: 'Jean', position: { x: 5, y: 5 } },
                    enemies: [
                        { id: 'e1', name: 'Far Goblin', health: { current: 10, max: 10 }, position: { x: 12, y: 5 } }
                    ]
                }
            ],
            enemies: [{ name: 'Far Goblin' }],
            combat_active: true
        };
        render(<Battlefield combat={offScreenCombat} currentLogIndex={0} />);
        await waitFor(() => {
            expect(screen.getByRole('status')).toBeInTheDocument();
        });
    });

    it('does not flag a dead off-screen enemy as needing the zoom hint', async () => {
        const offScreenCombat = {
            beat_states: [
                {
                    player: { name: 'Jean', position: { x: 5, y: 5 } },
                    enemies: [
                        { id: 'e1', name: 'Dead Goblin', hp: 0, max_hp: 10, position: { x: 12, y: 5 } }
                    ]
                }
            ],
            enemies: [{ name: 'Dead Goblin' }],
            combat_active: true
        };
        render(<Battlefield combat={offScreenCombat} currentLogIndex={0} />);
        await waitFor(() => {
            expect(screen.queryByRole('status')).toBeNull();
        });
    });

    it('does not crash or flag an enemy with no position data', () => {
        const noPositionCombat = {
            beat_states: [
                {
                    player: { name: 'Jean', position: { x: 5, y: 5 } },
                    enemies: [{ id: 'e1', name: 'Ghost', hp: 10, max_hp: 10 }]
                }
            ],
            enemies: [{ name: 'Ghost' }],
            combat_active: true
        };
        render(<Battlefield combat={noPositionCombat} currentLogIndex={0} />);
        expect(screen.queryByRole('status')).toBeNull();
    });

    it('resets accumulated beat states when combat ends', () => {
        const activeCombat = { ...mockCombat, combat_active: true };
        const { rerender } = render(<Battlefield combat={activeCombat} />);
        expect(screen.getByTestId('grid')).toBeInTheDocument();

        rerender(<Battlefield combat={{ ...mockCombat, combat_active: false, beat_states: [...mockCombat.beat_states, { combatants: [], enemies: [] }] }} />);
        expect(screen.getByTestId('grid')).toBeInTheDocument();
    });

    it('renders overview by default', () => {
        render(<Battlefield combat={mockCombat} />);
        expect(screen.getByTestId('grid')).toBeDefined();
        expect(screen.getByText(/Enemies \(1\)/i)).toBeDefined();
    });

    it('toggles tabs', () => {
        render(<Battlefield combat={mockCombat} />);

        fireEvent.click(screen.getByText(/Enemies \(1\)/i));
        expect(screen.getByTestId('grid')).toBeDefined();

        fireEvent.click(screen.getByText(/Overview/i));
        expect(screen.getByTestId('grid')).toBeDefined();
    });

    it('toggles zoom', () => {
        render(<Battlefield combat={mockCombat} />);

        const zoomBtn = screen.getByTitle('Toggle View Mode');
        expect(zoomBtn).toBeDefined();
        fireEvent.click(zoomBtn);

        fireEvent.click(zoomBtn);
        expect(screen.getByTestId('grid')).toBeDefined();
    });

    it('updates displayState based on currentLogIndex', () => {
        const { rerender } = render(<Battlefield combat={mockCombat} currentLogIndex={0} />);
        expect(screen.getByTestId('grid')).toBeDefined();

        rerender(<Battlefield combat={mockCombat} currentLogIndex={1} />);
        expect(screen.getByTestId('grid')).toBeDefined();
    });

    it('shows off-screen banner when a living enemy is beyond the zoomed viewport', async () => {
        // HALF_VIEW = floor(13 / 2) = 6. Enemy must be > 6 cells from player.
        const offScreenCombat = {
            beat_states: [
                {
                    player: { name: 'Jean', position: { x: 5, y: 5 } },
                    enemies: [
                        {
                            id: 'e1',
                            name: 'Far Goblin',
                            hp: 10,
                            max_hp: 10,
                            position: { x: 12, y: 5 }  // |12-5| = 7 > HALF_VIEW
                        }
                    ]
                }
            ],
            enemies: [{ name: 'Far Goblin', hp: 10, max_hp: 10 }],
            combat_active: true
        };

        render(<Battlefield combat={offScreenCombat} currentLogIndex={0} />);

        // Banner should appear because enemy is off-screen in normal zoom
        await waitFor(() => {
            expect(screen.getByRole('status')).toBeDefined();
            expect(screen.getByText(/enemy off-screen/i)).toBeDefined();
        });
    });

    // ── combat_id / map_size plumbing ─────────────────────────────────────
    //
    // BattlefieldGrid resets its camera pan on `combatId` changing, and sizes
    // the arena from `mapSize`. Both are read off the TOP-LEVEL combat object
    // here and passed as explicit props, because the grid's own `combat` prop
    // is a per-beat state that serialize_combat_state emits neither field on.
    // Reading them from the grid's prop instead made the pan dep flip
    // uuid <-> undefined as displayState alternated shape, resetting the
    // camera repeatedly mid-fight; dropping them entirely (the original
    // wire-drift bug) meant it never reset and the arena fell back to the
    // bounding box of current positions.
    describe('fight identity and arena size forwarding', () => {
        const fight = (overrides = {}) => ({
            ...makeBattleState(overrides),
            combat_active: true,
            log: [],
            beat_states: [{ player: makeCombatant(), enemies: [makeEnemy()] }],
        });

        it('forwards combat_id and map_size from the top-level combat object', () => {
            render(<Battlefield combat={fight({ combat_id: 'fight-A', map_size: 18 })} currentLogIndex={0} />);
            expect(lastGridProps().combatId).toBe('fight-A');
            expect(lastGridProps().mapSize).toBe(18);
            expect(lastGridProps().combatActive).toBe(true);
        });

        it('does not source them from the per-beat combat prop handed to the grid', () => {
            // The beat state deliberately carries CONTRADICTORY values. If
            // Battlefield ever regressed to reading `displayState.combat_id`,
            // these are the values that would surface.
            const combat = fight({ combat_id: 'fight-A', map_size: 18 });
            combat.beat_states = [{
                player: makeCombatant(),
                enemies: [makeEnemy()],
                combat_id: 'beat-state-id',
                map_size: 13,
            }];
            render(<Battlefield combat={combat} currentLogIndex={0} />);

            expect(lastGridProps().combat.combat_id).toBe('beat-state-id');
            expect(lastGridProps().combatId).toBe('fight-A');
            expect(lastGridProps().mapSize).toBe(18);
        });

        it('holds combat_id still across beats of one fight and moves it for a new fight', () => {
            const { rerender } = render(
                <Battlefield combat={fight({ combat_id: 'fight-A', beat: 1 })} currentLogIndex={0} />
            );
            expect(lastGridProps().combatId).toBe('fight-A');

            // Same fight, later beat + a reinforcement wave (a server-side
            // reinit, which keeps the id).
            rerender(
                <Battlefield
                    combat={fight({ combat_id: 'fight-A', beat: 5, enemies: [makeEnemy(), makeEnemy({ id: 'enemy_2' })] })}
                    currentLogIndex={0}
                />
            );
            expect(lastGridProps().combatId).toBe('fight-A');

            rerender(<Battlefield combat={fight({ combat_id: 'fight-B', beat: 1 })} currentLogIndex={0} />);
            expect(lastGridProps().combatId).toBe('fight-B');
        });
    });

    it('does not show off-screen banner in full-map mode', async () => {
        const offScreenCombat = {
            beat_states: [
                {
                    player: { name: 'Jean', position: { x: 5, y: 5 } },
                    enemies: [
                        { id: 'e1', name: 'Far Goblin', hp: 10, max_hp: 10, position: { x: 12, y: 5 } }
                    ]
                }
            ],
            enemies: [{ name: 'Far Goblin', hp: 10, max_hp: 10 }],
            combat_active: true
        };

        render(<Battlefield combat={offScreenCombat} currentLogIndex={0} />);

        // Switch to full-map mode
        const zoomBtn = screen.getByTitle(/toggle view mode|enemies are off-screen/i);
        fireEvent.click(zoomBtn);

        // Banner should NOT appear in full-map mode
        await waitFor(() => {
            expect(screen.queryByRole('status')).toBeNull();
        });
    });
});
