import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { act } from 'react';
import Battlefield from './Battlefield';
import { setFlag, resetFlags } from '../utils/featureFlags';
import React from 'react';
import { makeBattleState, makeCombatant, makeEnemy, makeTerrain } from '../test/payloads';

// Mock child components. Battlefield also imports the VIEW_SIZE constant for
// its off-screen-enemy detection and the view-mode constants, so expose them on
// the mock.
//
// The mock RECORDS the props it was handed rather than destructuring only the
// three it renders: Battlefield's job for combatId/mapSize is pure forwarding
// from the top-level combat object, and a stub that ignores those props cannot
// tell a correct forward from a deleted one.
const gridProps = [];
vi.mock('./BattlefieldGrid', () => ({
    VIEW_SIZE: 13,
    VIEW_MODE_FOLLOW: 'follow',
    VIEW_MODE_FIT: 'fit',
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
        // The banner must name the enemy count it found, not merely exist:
        // `health.current` is the only HP field this payload carries, so a
        // component reading `hp` alone would see 0 and suppress the hint.
        const banner = await screen.findByRole('status');
        expect(banner).toHaveTextContent(/enemy off-screen/i);
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
        const { rerender } = render(<Battlefield combat={activeCombat} currentLogIndex={1} />);
        expect(lastGridProps().combat.enemies[0].hp).toBe(5);
        expect(lastGridProps().combatActive).toBe(true);

        rerender(
            <Battlefield
                combat={{
                    ...mockCombat,
                    combat_active: false,
                    beat_states: [...mockCombat.beat_states, { combatants: [], enemies: [] }],
                }}
                currentLogIndex={1}
            />
        );
        // combatActive must follow the payload down to the grid — it is half of
        // the grid's camera-reset dependency alongside combatId.
        expect(lastGridProps().combatActive).toBe(false);
        expect(screen.getByTestId('grid')).toBeInTheDocument();
    });

    // The tab/zoom/beat state lives in Battlefield and reaches the player only
    // through the props it hands the grid. The previous versions of these four
    // tests clicked the control and then asserted `getByTestId('grid')` was
    // defined — true before the click, after it, and for every possible state.

    it('opens on the overview tab and labels the enemies tab with the live count', () => {
        render(<Battlefield combat={mockCombat} />);
        expect(lastGridProps().tab).toBe('overview');
        expect(screen.getByText(/Enemies \(1\)/i)).toBeInTheDocument();
    });

    it('switches the tab prop handed to the grid when a tab is clicked', () => {
        render(<Battlefield combat={mockCombat} />);
        expect(lastGridProps().tab).toBe('overview');

        fireEvent.click(screen.getByText(/Enemies \(1\)/i));
        expect(lastGridProps().tab).toBe('enemies');

        fireEvent.click(screen.getByText(/Overview/i));
        expect(lastGridProps().tab).toBe('overview');
    });

    it('switches between the follow and fit view modes', () => {
        render(<Battlefield combat={mockCombat} />);

        const followBtn = screen.getByRole('button', { name: 'Follow' });
        const fitBtn = screen.getByRole('button', { name: 'Fit Fight' });

        // Follow is the default and both options are always offered, so the
        // active mode is legible without clicking anything.
        expect(followBtn.getAttribute('aria-pressed')).toBe('true');
        expect(fitBtn.getAttribute('aria-pressed')).toBe('false');
        expect(screen.getByTestId('grid').textContent).toContain('Zoom: follow');

        fireEvent.click(fitBtn);
        expect(fitBtn.getAttribute('aria-pressed')).toBe('true');
        expect(screen.getByTestId('grid').textContent).toContain('Zoom: fit');

        fireEvent.click(followBtn);
        expect(followBtn.getAttribute('aria-pressed')).toBe('true');
        expect(screen.getByTestId('grid').textContent).toContain('Zoom: follow');
    });

    it('reports the beat number and how many enemies are still standing', () => {
        const combat = {
            ...mockCombat,
            beat: 7,
            beat_states: [{
                player: { name: 'Jean', position: { x: 1, y: 1 } },
                enemies: [
                    { id: 'e1', name: 'Slime', hp: 4, max_hp: 10, position: { x: 2, y: 1 } },
                    { id: 'e2', name: 'Dead Slime', hp: 0, max_hp: 10, position: { x: 3, y: 1 } },
                ],
            }],
        };
        render(<Battlefield combat={combat} currentLogIndex={0} />);

        expect(screen.getByText('Beat 7')).toBeDefined();
        expect(screen.getByText('1 standing')).toBeDefined();
    });

    it('rewinds the grid to the beat state named by currentLogIndex', () => {
        // mockCombat's two beats put Jean at [0,0] then [1,1] and drop the
        // Slime from 10 HP to 5 — so the beat the grid is handed is observable.
        const { rerender } = render(<Battlefield combat={mockCombat} currentLogIndex={0} />);
        expect(lastGridProps().combat.combatants[0].position).toEqual([0, 0]);
        expect(lastGridProps().combat.enemies[0].hp).toBe(10);

        rerender(<Battlefield combat={mockCombat} currentLogIndex={1} />);
        expect(lastGridProps().combat.combatants[0].position).toEqual([1, 1]);
        expect(lastGridProps().combat.enemies[0].hp).toBe(5);
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
        const banner = await screen.findByRole('status');
        expect(banner).toHaveTextContent(/enemy off-screen/i);
        // ...and the zoom control retitles itself to advertise the fix.
        expect(screen.getByTitle(/off-screen/i)).toBeInTheDocument();
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

        it('forwards battle_state.terrain the same way (the beat state never carries it)', () => {
            const terrain = makeTerrain();
            render(<Battlefield combat={fight({ terrain })} currentLogIndex={0} />);
            expect(lastGridProps().terrain).toBe(terrain);
            render(<Battlefield combat={fight({ terrain: null })} currentLogIndex={0} />);
            expect(lastGridProps().terrain).toBeNull();
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

    it('does not show off-screen banner in fit mode', async () => {
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

        // Switch to fit mode — it frames every combatant, so nothing is off-screen
        fireEvent.click(screen.getByRole('button', { name: 'Fit Fight' }));

        // Banner should NOT appear in fit mode
        await waitFor(() => {
            expect(screen.queryByRole('status')).toBeNull();
        });
    });

    describe('beatTimeline feature flag', () => {
        afterEach(() => {
            resetFlags();
        });

        const combatWithPendingMove = {
            ...mockCombat,
            beat: 7,
            beat_states: [{
                player: {
                    id: 'player', name: 'Jean', position: { x: 1, y: 1 },
                    current_move: { name: 'Attack', display_name: 'Attack', category: 'Offensive', current_stage: 0, beats_until_resolve: 3 },
                },
                enemies: [{ id: 'e1', name: 'Slime', hp: 4, max_hp: 10, position: { x: 2, y: 1 } }],
            }],
        };

        // The timeline now ships ON by default, and renders ALONGSIDE the beat
        // counter rather than replacing it: the schedule carries ordering, the
        // counter carries beat number and enemies remaining, and neither
        // substitutes for the other. Turning the flag off drops only the
        // schedule.
        it('shows both the timeline and the beat counter by default', () => {
            render(<Battlefield combat={combatWithPendingMove} currentLogIndex={0} />);
            expect(screen.getByLabelText('Beat timeline')).toBeInTheDocument();
            expect(screen.getByText('Beat 7')).toBeInTheDocument();
            expect(screen.getByText('Jean')).toBeInTheDocument();
        });

        it('keeps the beat counter and drops only the timeline when the flag is off', () => {
            act(() => setFlag('beatTimeline', false));
            render(<Battlefield combat={combatWithPendingMove} currentLogIndex={0} />);
            expect(screen.getByText('Beat 7')).toBeInTheDocument();
            expect(screen.getByText('1 standing')).toBeInTheDocument();
            expect(screen.queryByLabelText('Beat timeline')).not.toBeInTheDocument();
        });
    });
});
