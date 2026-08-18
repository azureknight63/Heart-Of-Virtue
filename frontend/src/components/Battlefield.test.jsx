import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { act } from 'react';
import Battlefield from './Battlefield';
import { setFlag, resetFlags } from '../utils/featureFlags';
import React from 'react';

// Mock child components. Battlefield also imports VIEW_SIZE (off-screen-enemy
// detection) and the view-mode constants, so expose them on the mock.
vi.mock('./BattlefieldGrid', () => ({
    VIEW_SIZE: 13,
    VIEW_MODE_FOLLOW: 'follow',
    VIEW_MODE_FIT: 'fit',
    default: ({ combat, tab, zoom }) => (
        <div data-testid="grid">
            Grid - Tab: {tab} - Zoom: {zoom}
            Combatant: {combat?.combatants?.[0]?.name}
        </div>
    )
}));

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

        it('shows the old beat counter, not the timeline, by default', () => {
            render(<Battlefield combat={combatWithPendingMove} currentLogIndex={0} />);
            expect(screen.getByText('Beat 7')).toBeInTheDocument();
            expect(screen.queryByLabelText('Beat timeline')).not.toBeInTheDocument();
        });

        it('shows the timeline instead of the counter once the flag is on', () => {
            act(() => setFlag('beatTimeline', true));
            render(<Battlefield combat={combatWithPendingMove} currentLogIndex={0} />);
            expect(screen.getByLabelText('Beat timeline')).toBeInTheDocument();
            expect(screen.queryByText('Beat 7')).not.toBeInTheDocument();
            expect(screen.getByText('Jean')).toBeInTheDocument();
        });
    });
});
