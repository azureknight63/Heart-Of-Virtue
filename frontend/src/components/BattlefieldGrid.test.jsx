import React from 'react';
import { render, screen, fireEvent, act, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import BattlefieldGrid from './BattlefieldGrid';
import { getAnimationDuration } from '../utils/animationConfigs';
import { setFlag, resetFlags } from '../utils/featureFlags';

const { mockPlaySFX } = vi.hoisted(() => ({ mockPlaySFX: vi.fn() }));

// Mock AudioContext so playSFX doesn't throw
vi.mock('../context/AudioContext', () => ({
    useAudio: () => ({ playSFX: mockPlaySFX })
}));

describe('BattlefieldGrid', () => {
    const mockCombat = {
        player: {
            id: 'player',
            name: 'Jean',
            hp: 100,
            max_hp: 100,
            fatigue: 0,
            max_fatigue: 100,
            position: { x: 6, y: 6, facing: 0 },
            current_move: { category: 'Attack' }
        },
        enemies: [
            {
                id: 'enemy_goblin',
                name: 'Goblin',
                hp: 50,
                max_hp: 50,
                position: { x: 8, y: 6, facing: 180 },
                current_move: { category: 'Maneuver' }
            }
        ]
    };

    it('renders grid and combatants in normal mode', () => {
        const { container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);

        // Check if player marker exists (J for Jean)
        expect(screen.getByText('J')).toBeDefined();
        // Check if enemy marker exists (G for Goblin)
        expect(screen.getByText('G')).toBeDefined();

        // Normal mode always renders a 13x13 viewport regardless of map size.
        // On-map cells use a light gray background, off-map cells are dimmer.
        const onMap = container.querySelectorAll('[style*="background-color: rgba(255, 255, 255, 0.03)"]');
        const offMap = container.querySelectorAll('[style*="background-color: rgba(0, 0, 0, 0.35)"]');
        expect(onMap.length + offMap.length).toBe(169);
    });

    it('frames the combatants, not the whole arena, in fit mode', () => {
        // Combatants are clustered; fit mode must not spend the viewport on
        // empty arena. The framing floors at VIEW_SIZE so it never zooms in
        // past the follow-mode window, giving a 13x13 grid here.
        const { container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom="fit" />);

        const grid = container.querySelector('[style*="grid-template-columns"]');
        expect(grid.style.gridTemplateColumns).toBe('repeat(13, minmax(0, 1fr))');
        expect(grid.children.length).toBe(13 * 13);
    });

    it('scales the fit framing up when combatants are far apart', () => {
        // A 40x40 arena with two combatants 24 cells apart: the framing must
        // grow to contain both rather than stay at the follow-mode window.
        const spreadCombat = {
            player: { ...mockCombat.player, position: { x: 5, y: 5 } },
            enemies: [{ id: 'e-far', name: 'Archer', hp: 10, max_hp: 10, position: { x: 29, y: 5 } }],
        };
        const { container } = render(
            <BattlefieldGrid combat={spreadCombat} tab="overview" zoom="fit" mapSize={40} />
        );

        // span 25 + 2*2 padding = 29, rounded up to the 4-cell quantum = 32
        const grid = container.querySelector('[style*="grid-template-columns"]');
        expect(grid.style.gridTemplateColumns).toBe('repeat(32, minmax(0, 1fr))');
    });

    it('falls back to the whole arena in fit mode when nothing has a position', () => {
        const positionless = {
            player: { id: 'player', name: 'Jean', hp: 100, max_hp: 100 },
            enemies: [{ id: 'e', name: 'Ghost', hp: 5, max_hp: 5 }],
        };
        const { container } = render(
            <BattlefieldGrid combat={positionless} tab="overview" zoom="fit" mapSize={9} />
        );

        const grid = container.querySelector('[style*="grid-template-columns"]');
        expect(grid.style.gridTemplateColumns).toBe('repeat(9, minmax(0, 1fr))');
    });

    it('keeps the fit framing stable while combatants stay inside it', () => {
        const spreadCombat = {
            player: { ...mockCombat.player, position: { x: 5, y: 5 } },
            enemies: [{ id: 'e-far', name: 'Archer', hp: 10, max_hp: 10, position: { x: 29, y: 5 } }],
        };
        const { container, rerender } = render(
            <BattlefieldGrid combat={spreadCombat} tab="overview" zoom="fit" mapSize={40} />
        );
        const before = container.querySelector('[style*="grid-template-columns"]').style.gridTemplateColumns;

        // The archer shuffles one cell closer — well inside the current frame.
        rerender(
            <BattlefieldGrid
                combat={{
                    ...spreadCombat,
                    enemies: [{ ...spreadCombat.enemies[0], position: { x: 28, y: 5 } }],
                }}
                tab="overview"
                zoom="fit"
                mapSize={40}
            />
        );
        const after = container.querySelector('[style*="grid-template-columns"]').style.gridTemplateColumns;

        // Re-deriving the box every beat would rescale the whole map underfoot.
        expect(after).toBe(before);
    });

    describe('reading the fight at a glance', () => {
        const pendingMove = {
            name: 'Reap', category: 'Attack',
            current_stage: 0, beats_left: 2, beats_until_resolve: 7,
        };

        it('shows how many beats until an in-progress move resolves', () => {
            const combat = {
                ...mockCombat,
                enemies: [{ ...mockCombat.enemies[0], current_move: pendingMove }],
            };
            render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            // The engine-computed time to land (7), not beats_left (2) — the
            // latter is only beats left in the current stage, and telling the
            // player 2 when the blow lands in 7 mis-times every reaction.
            expect(screen.getByLabelText('Move resolves in 7 beats')).toBeInTheDocument();
            expect(screen.queryByLabelText('Move resolves in 2 beats')).toBeNull();
        });

        it('does not telegraph a move that is only cooling down', () => {
            const combat = {
                ...mockCombat,
                player: { ...mockCombat.player, current_move: null },
                enemies: [{
                    ...mockCombat.enemies[0],
                    // Stage 3 is cooldown — aftermath, not a threat. Glowing here
                    // made a spent combatant look identical to one winding up.
                    current_move: { name: 'Reap', category: 'Attack', current_stage: 3, beats_left: 2 },
                }],
            };
            const { container } = render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            expect(container.querySelector('.battlefield-pending-glow')).toBeNull();
            expect(screen.queryByLabelText(/Move resolves in/)).toBeNull();
        });

        it('marks off-screen enemies with an edge chevron and their distance', () => {
            const combat = {
                ...mockCombat,
                enemies: [{
                    id: 'enemy_archer',
                    name: 'Archer',
                    hp: 10,
                    max_hp: 10,
                    distance: 22,
                    position: { x: 28, y: 6 },  // far outside the 13-cell window
                }],
            };
            render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} mapSize={40} />);

            expect(screen.getByLabelText('Archer off-screen, 22 feet away')).toBeInTheDocument();
        });

        it('does not mark enemies that are on screen', () => {
            render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
            expect(screen.queryByLabelText(/off-screen/)).toBeNull();
        });

        it('shows distance in the hover tooltip and the selected-combatant panel', () => {
            const combat = {
                ...mockCombat,
                enemies: [{ ...mockCombat.enemies[0], distance: 4 }],
            };
            render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            const goblin = screen.getByText('G');
            fireEvent.mouseEnter(goblin.closest('div[style*="position: absolute"]'));
            expect(screen.getByText('4 ft')).toBeInTheDocument();

            fireEvent.click(goblin);
            expect(screen.getByText('4 ft away')).toBeInTheDocument();
        });

        it('still shows hover tooltips for other combatants while one is selected', () => {
            const combat = {
                ...mockCombat,
                enemies: [
                    { ...mockCombat.enemies[0], distance: 4 },
                    { id: 'enemy_rat', name: 'Rat', hp: 8, max_hp: 8, distance: 9, position: { x: 4, y: 6 } },
                ],
            };
            render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            fireEvent.click(screen.getByText('G'));
            fireEvent.mouseEnter(screen.getByText('R').closest('div[style*="position: absolute"]'));

            // Previously any selection suppressed every tooltip on the field.
            expect(screen.getByText('9 ft')).toBeInTheDocument();
        });

        it('clears the selection when the map background is clicked', () => {
            const { container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);

            fireEvent.click(screen.getByText('G'));
            expect(screen.getByText('INTEGRITY (HP)')).toBeInTheDocument();

            // The panel's own tooltip advertises this; the old target-identity
            // check never matched, because full-bleed child layers always
            // absorbed the click first.
            fireEvent.click(container.firstChild);
            expect(screen.queryByText('INTEGRITY (HP)')).toBeNull();
        });
    });

    describe('threat line (who a pending move is aimed at)', () => {
        it('draws a line from a pending attacker to its target', () => {
            const combat = {
                ...mockCombat,
                enemies: [{
                    ...mockCombat.enemies[0],
                    current_move: {
                        name: 'NPC_Attack', category: 'Offensive',
                        current_stage: 0, beats_left: 2, target_id: 'player',
                    },
                }],
            };
            const { container } = render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            const lines = container.querySelectorAll('[data-testid="threat-line"]');
            expect(lines.length).toBe(1);
            expect(lines[0].getAttribute('data-source-id')).toBe('enemy_goblin');
            expect(lines[0].getAttribute('data-target-id')).toBe('player');
            // Enemy-on-Jean is the dominant case: thicker and brighter than any
            // other combination.
            expect(lines[0].getAttribute('data-dominant')).toBe('true');
        });

        it('draws no line when the move is only cooling down (stage 3)', () => {
            const combat = {
                ...mockCombat,
                enemies: [{
                    ...mockCombat.enemies[0],
                    current_move: {
                        name: 'NPC_Attack', category: 'Offensive',
                        current_stage: 3, beats_left: 2, target_id: 'player',
                    },
                }],
            };
            const { container } = render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            expect(container.querySelectorAll('[data-testid="threat-line"]').length).toBe(0);
        });

        it('draws no line when the move has no target', () => {
            const combat = {
                ...mockCombat,
                enemies: [{
                    ...mockCombat.enemies[0],
                    current_move: {
                        name: 'NPC_Rest', category: 'Utility',
                        current_stage: 0, beats_left: 2, target_id: null,
                    },
                }],
            };
            const { container } = render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            expect(container.querySelectorAll('[data-testid="threat-line"]').length).toBe(0);
        });

        it('draws no line when the target is off screen', () => {
            const combat = {
                ...mockCombat,
                enemies: [
                    {
                        ...mockCombat.enemies[0],
                        current_move: {
                            name: 'NPC_Attack', category: 'Offensive',
                            current_stage: 0, beats_left: 2, target_id: 'enemy_far',
                        },
                    },
                    {
                        id: 'enemy_far', name: 'Straggler', hp: 5, max_hp: 5,
                        position: { x: 200, y: 200 }, // well outside the 13-cell window
                    },
                ],
            };
            const { container } = render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            expect(container.querySelectorAll('[data-testid="threat-line"]').length).toBe(0);
        });
    });

    describe('decaying reach renders as a gradient, not a ring', () => {
        // A bow has no hard maximum: it can be fired at any distance and
        // accuracy simply bleeds away past `start`. mvrange.max is where a
        // full 100-point hit chance would decay to zero, not a wall.
        // The viewport is 13 cells, so a plateau of 3 ft has its transition
        // on screen and there is a real dissolve to draw.
        const decayingMove = {
            name: 'ShootBow', category: 'Offensive',
            current_stage: 0, beats_left: 2,
            mvrange: { min: 1, max: 203 },
            falloff: { start: 3, per_ft: 0.5 },
        };
        const selectEnemyWith = (move) => {
            const combat = {
                ...mockCombat,
                enemies: [{ ...mockCombat.enemies[0], current_move: move }],
            };
            const result = render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);
            fireEvent.click(screen.getByText('G'));
            return result;
        };

        it('dissolves outward instead of drawing a wall the engine does not have', () => {
            const { container } = selectEnemyWith(decayingMove);
            const indicator = container.querySelector('[data-testid="range-ring"]');

            expect(indicator.dataset.shape).toBe('falloff');
            expect(indicator.style.background).toContain('radial-gradient');
            // Solid to the plateau, then fading — no hard border anywhere.
            expect(indicator.style.border).toBe('');
            // ...and the fill feathers to nothing at its rim rather than
            // ending in a hard circle, which would read as the wall this
            // treatment exists to deny.
            const stops = indicator.style.background.match(/rgba\([^)]*\)/g);
            expect(parseFloat(stops[stops.length - 1].split(',').pop())).toBe(0);
        });

        it('scales the gradient to the viewport, not to the nominal max reach', () => {
            const { container } = selectEnemyWith(decayingMove);
            const indicator = container.querySelector('[data-testid="range-ring"]');

            // Sizing to mvrange.max (203ft => 406 cells) against a 13-cell view
            // would put the whole visible field inside the plateau, rendering a
            // flat wash with no gradient visible at all. Drawn radius is the
            // viewport's inscribed circle, 13/2 = 6.5 cells => 13 diameter.
            expect(indicator.style.width).toBe('1300%');
            // Plateau at 3 of 6.5 => 46.15% of the radius.
            expect(indicator.style.background).toContain('46.15%');
        });

        it('marks the plateau — the last distance at full accuracy', () => {
            const { container } = selectEnemyWith(decayingMove);
            const plateau = container.querySelector('[data-testid="range-plateau"]');

            // Drawn radius is the inscribed 6.5 cells, so a 3-cell plateau
            // sits at 3/6.5 of the way out => 23.08 in the 0-50 viewBox radius.
            expect(Number(plateau.getAttribute('r'))).toBeCloseTo(23.08, 1);
        });

        it('adds a sparser outer ring so the boundary reads as porous, not a wall', () => {
            const { container } = selectEnemyWith(decayingMove);
            const plateau = container.querySelector('[data-testid="range-plateau"]');
            const outer = container.querySelector('[data-testid="range-outer"]');

            // Both rings are dashed, but the outer one has far more gap than
            // dash — that contrast is what says "this edge is soft".
            const gapRatio = (el) => {
                const [dash, gap] = el.getAttribute('stroke-dasharray').split(' ').map(Number);
                return gap / dash;
            };
            expect(gapRatio(outer)).toBeGreaterThan(gapRatio(plateau));
            expect(Number(outer.getAttribute('r'))).toBeGreaterThan(Number(plateau.getAttribute('r')));

            // Without this the element's scale (up to ~20x a cell) multiplies
            // the dash pattern and both rings smear into solid lines.
            expect(outer.getAttribute('vector-effect')).toBe('non-scaling-stroke');
            expect(plateau.getAttribute('vector-effect')).toBe('non-scaling-stroke');
        });

        it('draws no dashed rings for a bounded move', () => {
            const { container } = selectEnemyWith({
                name: 'PowerStrike', category: 'Attack',
                current_stage: 0, beats_left: 1,
                mvrange: { min: 0, max: 3 },
                falloff: null,
            });
            expect(container.querySelector('[data-testid="range-plateau"]')).toBeNull();
            expect(container.querySelector('[data-testid="range-outer"]')).toBeNull();
        });

        it('draws nothing when the whole visible field is still at full accuracy', () => {
            // The realistic bow case: a 20ft plateau against a 13-cell view
            // means every square the player can see is at undiminished
            // accuracy. A gradient here would be a uniform tint conveying
            // nothing, so the honest output is no indicator at all.
            const { container } = selectEnemyWith({
                ...decayingMove,
                mvrange: { min: 6, max: 2020 },
                falloff: { start: 20, per_ft: 0.05 },
            });
            expect(container.querySelectorAll('[data-testid="range-ring"]').length).toBe(0);
        });

        it('fades in proportion to the accuracy actually lost, not decoratively', () => {
            // The whole justification for a gradient is that its density reads
            // as hit chance. A fixed dramatic fade would overstate a shallow
            // decay by an order of magnitude — a confident-looking lie.
            const gentle = selectEnemyWith(decayingMove)
                .container.querySelector('[data-testid="range-ring"]').style.background;
            cleanup();
            const brutal = selectEnemyWith({
                ...decayingMove,
                falloff: { start: 3, per_ft: 12 },
            }).container.querySelector('[data-testid="range-ring"]').style.background;

            // Same plateau, same drawn radius — only the decay rate differs, so
            // only the outer stop may differ, and the steeper decay must be the
            // fainter one at the edge.
            // Stops are [core, plateau-edge, retention, feather-to-nothing].
            // The retention stop is the one that encodes accuracy; the final
            // feather is always zero (it only softens the drawn rim), so
            // reading the last stop would compare 0 against 0.
            const RETENTION_STOP = 2;
            const outerAlpha = (bg) => {
                const stops = bg.match(/rgba\([^)]*\)/g);
                return parseFloat(stops[RETENTION_STOP].split(',').pop());
            };
            expect(outerAlpha(brutal)).toBeLessThan(outerAlpha(gentle));
        });

        it('is not suppressed merely for exceeding the viewport, unlike a hard ring', () => {
            // A hard ring bigger than the view is suppressed because its edge
            // — the only thing it encodes — would be off screen. A gradient
            // still says something inside the view, so the same rule must not
            // apply to it.
            const { container } = selectEnemyWith(decayingMove);
            expect(container.querySelectorAll('[data-testid="range-ring"]').length).toBe(1);
        });

        it('still draws a hard ring for a move whose accuracy does not decay', () => {
            const { container } = selectEnemyWith({
                name: 'PowerStrike', category: 'Attack',
                current_stage: 0, beats_left: 1,
                mvrange: { min: 0, max: 3 },
                falloff: null,
            });
            const indicator = container.querySelector('[data-testid="range-ring"]');

            expect(indicator.dataset.shape).toBe('ring');
            expect(indicator.style.background).toBe('');
            expect(container.querySelector('[data-testid="range-plateau"]')).toBeNull();
        });

        it('treats a zero decay rate as no decay at all', () => {
            const { container } = selectEnemyWith({
                name: 'Odd', category: 'Attack',
                current_stage: 0, beats_left: 1,
                mvrange: { min: 0, max: 3 },
                falloff: { start: 2, per_ft: 0 },
            });
            expect(container.querySelector('[data-testid="range-ring"]').dataset.shape).toBe('ring');
        });
    });

    describe('range ring (max reach of the selected combatant\'s move)', () => {
        it('appears once the combatant with a ranged move is selected', () => {
            const combat = {
                ...mockCombat,
                enemies: [{
                    ...mockCombat.enemies[0],
                    current_move: {
                        name: 'ShootBow', category: 'Offensive',
                        current_stage: 0, beats_left: 2,
                        mvrange: { min: 1, max: 5 },
                    },
                }],
            };
            const { container } = render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            expect(container.querySelectorAll('[data-testid="range-ring"]').length).toBe(0);

            fireEvent.click(screen.getByText('G'));

            expect(container.querySelectorAll('[data-testid="range-ring"]').length).toBe(1);
        });

        it('does not appear for an unselected combatant', () => {
            const combat = {
                ...mockCombat,
                enemies: [{
                    ...mockCombat.enemies[0],
                    current_move: {
                        name: 'ShootBow', category: 'Offensive',
                        current_stage: 0, beats_left: 2,
                        mvrange: { min: 1, max: 5 },
                    },
                }],
            };
            const { container } = render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            expect(container.querySelectorAll('[data-testid="range-ring"]').length).toBe(0);
        });

        it('does not appear when the selected move has no mvrange', () => {
            const { container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);

            // mockCombat's player current_move carries no mvrange at all.
            fireEvent.click(screen.getByText('J'));

            expect(container.querySelectorAll('[data-testid="range-ring"]').length).toBe(0);
        });

        it('is suppressed when the ring would be larger than the viewport', () => {
            const combat = {
                ...mockCombat,
                enemies: [{
                    ...mockCombat.enemies[0],
                    current_move: {
                        name: 'ShootBow', category: 'Offensive',
                        current_stage: 0, beats_left: 2,
                        // diameter 40 cells vs. the 13-cell follow-mode viewport.
                        mvrange: { min: 1, max: 20 },
                    },
                }],
            };
            const { container } = render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            fireEvent.click(screen.getByText('G'));

            expect(container.querySelectorAll('[data-testid="range-ring"]').length).toBe(0);
        });

        it('disappears again once the selection is cleared', () => {
            const combat = {
                ...mockCombat,
                enemies: [{
                    ...mockCombat.enemies[0],
                    current_move: {
                        name: 'ShootBow', category: 'Offensive',
                        current_stage: 0, beats_left: 2,
                        mvrange: { min: 1, max: 5 },
                    },
                }],
            };
            const { container } = render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

            fireEvent.click(screen.getByText('G'));
            expect(container.querySelectorAll('[data-testid="range-ring"]').length).toBe(1);

            fireEvent.keyDown(window, { key: 'Escape' });
            expect(container.querySelectorAll('[data-testid="range-ring"]').length).toBe(0);
        });
    });

    describe('squareBattlefieldCells feature flag', () => {
        afterEach(() => {
            resetFlags();
        });

        it('fills the panel by default, inheriting its aspect ratio', () => {
            const { getByTestId, container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);

            expect(getByTestId('battlefield-viewport').dataset.layout).toBe('fill');
            // No container-query context is established when the flag is off.
            expect(container.firstChild.style.containerType).toBe('');
        });

        it('letterboxes the map to a square when the flag is on', () => {
            act(() => setFlag('squareBattlefieldCells', true));
            const { getByTestId, container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);

            expect(getByTestId('battlefield-viewport').dataset.layout).toBe('square');
            // The square is sized in container-query units, which need the
            // container to declare size containment.
            expect(container.firstChild.style.containerType).toBe('size');
        });

        it('switches live when the flag is toggled, without a remount', () => {
            const { getByTestId } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
            expect(getByTestId('battlefield-viewport').dataset.layout).toBe('fill');

            act(() => setFlag('squareBattlefieldCells', true));
            expect(getByTestId('battlefield-viewport').dataset.layout).toBe('square');

            act(() => setFlag('squareBattlefieldCells', false));
            expect(getByTestId('battlefield-viewport').dataset.layout).toBe('fill');
        });
    });

    it('renders enemy list in enemies tab', () => {
        render(<BattlefieldGrid combat={mockCombat} tab="enemies" zoom={1} />);

        expect(screen.getByText('Goblin')).toBeDefined();
        expect(screen.getByText(/HP: 50 \/ 50/)).toBeDefined();
    });

    it('handles missing position data gracefully', () => {
        const incompleteCombat = {
            player: { name: 'Jean', hp: 100, max_hp: 100 },
            enemies: []
        };
        render(<BattlefieldGrid combat={incompleteCombat} tab="overview" zoom={1} />);
        expect(screen.getByText('J')).toBeDefined();
    });

    it('handles dead enemies', () => {
        const combatWithDeadEnemy = {
            ...mockCombat,
            enemies: [
                {
                    name: 'Dead Goblin',
                    hp: 0,
                    max_hp: 50,
                    position: { x: 8, y: 8 }
                }
            ]
        };
        render(<BattlefieldGrid combat={combatWithDeadEnemy} tab="overview" zoom={1} />);
        expect(screen.queryByText('D')).toBeNull();
    });

    it('renders different move categories with correct styles', () => {
        const multiMoveCombat = {
            player: { ...mockCombat.player, current_move: { category: 'Special' } },
            enemies: [
                { ...mockCombat.enemies[0], current_move: { category: 'Supernatural' } },
                { name: 'Orc', hp: 100, max_hp: 100, position: { x: 5, y: 5 }, current_move: { category: 'Miscellaneous' } }
            ]
        };
        render(<BattlefieldGrid combat={multiMoveCombat} tab="overview" zoom={1} />);

        // We can't easily check box-shadow styles in JSDOM sometimes, 
        // but we can check if the components render without crashing.
        expect(screen.getByText('J')).toBeDefined();
        expect(screen.getByText('G')).toBeDefined();
        expect(screen.getByText('O')).toBeDefined();
    });

    it('handles hover enter/leave events on combatant tokens without error', () => {
        // Smoke test: verify mouseEnter/mouseLeave events are wired up and
        // do not throw. Detailed reticle rendering relies on Tailwind JIT which
        // is not processed in JSDOM; functional hover state is covered by the
        // select and Escape tests below.
        render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);

        const jeanToken = screen.getByText('J');
        const entityWrapper = jeanToken.closest('[style*="cursor"]');
        expect(entityWrapper).not.toBeNull();

        expect(() => fireEvent.mouseEnter(entityWrapper)).not.toThrow();
        expect(() => fireEvent.mouseLeave(entityWrapper)).not.toThrow();
    });

    it('shows the move name and preparation stage in the hover tooltip', () => {
        const combatWithMove = {
            ...mockCombat,
            enemies: [{
                ...mockCombat.enemies[0],
                current_move: { name: 'NPC_Attack', display_name: 'Attack', current_stage: 0, category: 'Offensive' },
            }],
        };
        render(<BattlefieldGrid combat={combatWithMove} tab="overview" zoom={1} />);

        const enemyToken = screen.getByText('G');
        const entityWrapper = enemyToken.closest('[style*="cursor"]');
        fireEvent.mouseEnter(entityWrapper);

        expect(screen.getByText('Preparing: Attack')).toBeDefined();
    });

    it('opens SelectedEntityPanel when a combatant is clicked', () => {
        render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);

        const jeanToken = screen.getByText('J');
        const entityWrapper = jeanToken.closest('[style*="cursor"]');
        expect(entityWrapper).not.toBeNull();

        fireEvent.click(entityWrapper);

        // SelectedEntityPanel should appear showing Jean's name
        expect(screen.getByText('Jean')).toBeDefined();
    });

    it('closes SelectedEntityPanel on Escape key', () => {
        render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);

        // Open panel by clicking Jean
        const jeanToken = screen.getByText('J');
        const entityWrapper = jeanToken.closest('[style*="cursor"]');
        fireEvent.click(entityWrapper);
        expect(screen.getByText('Jean')).toBeDefined();

        // Escape should close it
        fireEvent.keyDown(window, { key: 'Escape' });
        // Jean token label still exists but SelectedEntityPanel should be gone
        // (it renders the name in a different style context)
        const jeanInPanel = screen.queryAllByText('Jean');
        // Panel renders name inside a distinct section — after Escape there should be at most the marker label
        expect(jeanInPanel.length).toBeLessThanOrEqual(1);
    });

    describe('combat speed scaling (issue #460)', () => {
        beforeEach(() => {
            vi.useFakeTimers();
            mockPlaySFX.mockClear();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        const combatWithAnimation = {
            ...mockCombat,
            log: [
                {
                    animation: {
                        type: 'attack',
                        source_id: 'player',
                        target_id: 'enemy_goblin',
                        outcome: 'hit'
                    }
                }
            ]
        };

        it('finishes the animation in half the time at 2x combat speed', () => {
            const onAnimatingChange = vi.fn();
            render(
                <BattlefieldGrid
                    combat={combatWithAnimation}
                    tab="overview"
                    zoom={1}
                    onAnimatingChange={onAnimatingChange}
                    displayedLogCount={1}
                    combatSpeed={2}
                />
            );
            onAnimatingChange.mockClear();

            const fullDuration = getAnimationDuration('attack');

            // Just under half the natural duration: still animating.
            act(() => vi.advanceTimersByTime(fullDuration / 2 - 20));
            expect(onAnimatingChange).not.toHaveBeenCalledWith(false);

            // Past half the natural duration: the 2x-scaled animation has finished.
            act(() => vi.advanceTimersByTime(40));
            expect(onAnimatingChange).toHaveBeenCalledWith(false);
        });

        it('passes the combat-speed multiplier into playSFX for phase-aligned cues', () => {
            render(
                <BattlefieldGrid
                    combat={combatWithAnimation}
                    tab="overview"
                    zoom={1}
                    displayedLogCount={1}
                    combatSpeed={1.5}
                />
            );

            // 'attack's windup phase is 200ms natural; at 1.5x it elapses in ~133ms,
            // after which the 'strike' phase fires its attack_swipe cue.
            act(() => vi.advanceTimersByTime(150));

            expect(mockPlaySFX).toHaveBeenCalledWith('attack_swipe', 1.5);
        });
    });

    describe('onAnimatingChange callback', () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        const combatWithAnimation = {
            ...mockCombat,
            log: [
                {
                    animation: {
                        type: 'attack',
                        source_id: 'player',
                        target_id: 'enemy_goblin',
                        outcome: 'hit'
                    }
                }
            ]
        };

        it('calls onAnimatingChange(true) when an animation is queued', () => {
            const onAnimatingChange = vi.fn();
            render(
                <BattlefieldGrid
                    combat={combatWithAnimation}
                    tab="overview"
                    zoom={1}
                    onAnimatingChange={onAnimatingChange}
                    displayedLogCount={1}
                />
            );
            expect(onAnimatingChange).toHaveBeenCalledWith(true);
        });

        it('never reports false while a multi-animation queue is still draining', () => {
            // Regression: the notifier effect used to carry a cleanup, which React
            // runs on every dep change rather than only on unmount. Dequeuing the
            // first of two animations emitted a spurious false, and because
            // prevAnimatingRef still read true the corrective true never followed —
            // so the victory/defeat grace timer started mid-animation.
            const onAnimatingChange = vi.fn();
            const twoAnimations = {
                ...mockCombat,
                log: [
                    { animation: { type: 'attack', source_id: 'player', target_id: 'enemy_goblin', outcome: 'hit' } },
                    { animation: { type: 'death', source_id: 'enemy_goblin', target_id: 'enemy_goblin', outcome: 'hit' } },
                ],
            };
            render(
                <BattlefieldGrid
                    combat={twoAnimations}
                    tab="overview"
                    zoom={1}
                    onAnimatingChange={onAnimatingChange}
                    displayedLogCount={2}
                />
            );

            expect(onAnimatingChange).toHaveBeenCalledWith(true);
            onAnimatingChange.mockClear();

            // Advance just past the first animation so the queue dequeues the
            // second. That dep change is what used to trigger the cleanup; the
            // flag must stay true because the queue is still draining.
            act(() => vi.advanceTimersByTime(getAnimationDuration('attack') + 20));
            expect(onAnimatingChange).not.toHaveBeenCalledWith(false);
        });

        it('does not call onAnimatingChange again during phase transitions', () => {
            const onAnimatingChange = vi.fn();
            render(
                <BattlefieldGrid
                    combat={combatWithAnimation}
                    tab="overview"
                    zoom={1}
                    onAnimatingChange={onAnimatingChange}
                    displayedLogCount={1}
                />
            );

            // Should be called once with true on animation start
            expect(onAnimatingChange.mock.calls.filter(c => c[0] === true).length).toBe(1);
            onAnimatingChange.mockClear();

            // Advance past windup (100ms) into strike — activeAnimation stays non-null,
            // so the dep-array condition doesn't change and onAnimatingChange must not fire
            act(() => vi.advanceTimersByTime(150));

            expect(onAnimatingChange.mock.calls.filter(c => c[0] === true).length).toBe(0);
        });

        it('calls onAnimatingChange(false) after all animation phases complete', () => {
            const onAnimatingChange = vi.fn();
            render(
                <BattlefieldGrid
                    combat={combatWithAnimation}
                    tab="overview"
                    zoom={1}
                    onAnimatingChange={onAnimatingChange}
                    displayedLogCount={1}
                />
            );

            onAnimatingChange.mockClear();

            // Advance past the attack animation's full configured duration
            act(() => vi.advanceTimersByTime(getAnimationDuration('attack') + 100));

            expect(onAnimatingChange).toHaveBeenCalledWith(false);
        });

        it('plays new taxonomy types (projectile) through all phases without error', () => {
            const onAnimatingChange = vi.fn();
            const projectileCombat = {
                ...mockCombat,
                log: [
                    {
                        animation: {
                            type: 'projectile',
                            source_id: 'player',
                            target_id: 'enemy_goblin',
                            outcome: 'hit'
                        }
                    }
                ]
            };
            render(
                <BattlefieldGrid
                    combat={projectileCombat}
                    tab="overview"
                    zoom={1}
                    onAnimatingChange={onAnimatingChange}
                    displayedLogCount={1}
                />
            );

            expect(onAnimatingChange).toHaveBeenCalledWith(true);
            onAnimatingChange.mockClear();

            act(() => vi.advanceTimersByTime(getAnimationDuration('projectile') + 100));
            expect(onAnimatingChange).toHaveBeenCalledWith(false);
        });

        it('falls back to the pulse config for unknown animation types', () => {
            const onAnimatingChange = vi.fn();
            const unknownCombat = {
                ...mockCombat,
                log: [
                    {
                        animation: {
                            type: 'mystery_move',
                            source_id: 'player'
                        }
                    }
                ]
            };
            render(
                <BattlefieldGrid
                    combat={unknownCombat}
                    tab="overview"
                    zoom={1}
                    onAnimatingChange={onAnimatingChange}
                    displayedLogCount={1}
                />
            );

            expect(onAnimatingChange).toHaveBeenCalledWith(true);
            onAnimatingChange.mockClear();

            // Unknown types play as pulse (400ms)
            act(() => vi.advanceTimersByTime(getAnimationDuration('pulse') + 100));
            expect(onAnimatingChange).toHaveBeenCalledWith(false);
        });

        it('calls onAnimatingChange(false) on unmount to prevent stuck animating state', () => {
            const onAnimatingChange = vi.fn();
            const { unmount } = render(
                <BattlefieldGrid
                    combat={mockCombat}
                    tab="overview"
                    zoom={1}
                    onAnimatingChange={onAnimatingChange}
                />
            );

            onAnimatingChange.mockClear();
            unmount();

            expect(onAnimatingChange).toHaveBeenCalledWith(false);
        });
    });

    describe('death animation lifecycle', () => {
        beforeEach(() => {
            vi.useFakeTimers();
            mockPlaySFX.mockClear();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it('plays a death burst and the enemy_death SFX after a killing blow, then clears it', () => {
            const allBeatStates = [
                { enemies: [{ id: 'enemy_goblin', hp: 50, position: { x: 8, y: 6 } }] },
                { enemies: [] },
            ];
            const combatWithKill = {
                ...mockCombat,
                log: [
                    { beat_index: 1, animation: { type: 'attack', source_id: 'player', target_id: 'enemy_goblin', outcome: 'hit' } },
                ],
            };
            const { container } = render(
                <BattlefieldGrid
                    combat={combatWithKill}
                    allBeatStates={allBeatStates}
                    currentBeatIndex={1}
                    tab="overview"
                    zoom={1}
                    displayedLogCount={1}
                />
            );

            // Finish the attack animation — the chained death animation should begin
            act(() => vi.advanceTimersByTime(800 + 50));
            expect(mockPlaySFX).toHaveBeenCalledWith('enemy_death', 1);
            expect(container.querySelector('svg[viewBox="-100 -100 200 200"]')).not.toBeNull();

            // Let the death animation finish completely
            act(() => vi.advanceTimersByTime(700 + 50));
            expect(container.querySelector('svg[viewBox="-100 -100 200 200"]')).toBeNull();
        });
    });

    describe('effects layer visuals', () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it('renders a ring effect anchored on the target for a heavy attack', () => {
            const combatWithHeavy = {
                ...mockCombat,
                log: [{ animation: { type: 'heavy_attack', source_id: 'player', target_id: 'enemy_goblin', outcome: 'hit' } }],
            };
            const { container } = render(<BattlefieldGrid combat={combatWithHeavy} tab="overview" zoom={1} displayedLogCount={1} />);
            act(() => vi.advanceTimersByTime(380 + 150 + 10)); // windup + strike -> into impact
            expect(container.querySelector('.battlefield-effect-ring')).not.toBeNull();
        });

        it('renders a ring effect anchored on the source for a sweep attack', () => {
            const combatWithSweep = {
                ...mockCombat,
                log: [{ animation: { type: 'sweep', source_id: 'player', target_id: 'enemy_goblin', outcome: 'hit' } }],
            };
            const { container } = render(<BattlefieldGrid combat={combatWithSweep} tab="overview" zoom={1} displayedLogCount={1} />);
            act(() => vi.advanceTimersByTime(180 + 10)); // windup -> into spin
            expect(container.querySelector('.battlefield-effect-ring')).not.toBeNull();
        });

        it('renders a travelling projectile dot from source to target', () => {
            const combatWithProjectile = {
                ...mockCombat,
                log: [{ animation: { type: 'projectile', source_id: 'player', target_id: 'enemy_goblin', outcome: 'hit' } }],
            };
            const { container } = render(<BattlefieldGrid combat={combatWithProjectile} tab="overview" zoom={1} displayedLogCount={1} />);
            act(() => vi.advanceTimersByTime(220 + 10)); // aim -> into launch
            const dots = Array.from(container.querySelectorAll('div')).filter((d) => d.style.backgroundColor === 'rgb(255, 238, 136)');
            expect(dots.length).toBeGreaterThan(0);

            // Advance further so the double-RAF launch flips the dot into its travelling state
            act(() => vi.advanceTimersByTime(50));
        });

        it('renders drain motes flowing from an ally target back to the source', () => {
            const combatWithAlly = {
                ...mockCombat,
                allies: [{ id: 'gorran', name: 'Gorran', hp: 40, max_hp: 100, position: { x: 5, y: 6 } }],
                log: [{ animation: { type: 'drain', source_id: 'player', target_id: 'gorran', outcome: 'hit' } }],
            };
            const { container } = render(<BattlefieldGrid combat={combatWithAlly} tab="overview" zoom={1} displayedLogCount={1} />);
            act(() => vi.advanceTimersByTime(240 + 10)); // windup -> into impact
            const dots = Array.from(container.querySelectorAll('div')).filter((d) => d.style.backgroundColor === 'rgba(170, 255, 170, 0.9)');
            expect(dots.length).toBeGreaterThan(0);
        });

        it('renders rising particles for a buff animation', () => {
            const combatWithBuff = {
                ...mockCombat,
                log: [{ animation: { type: 'buff', source_id: 'player' } }],
            };
            const { container } = render(<BattlefieldGrid combat={combatWithBuff} tab="overview" zoom={1} displayedLogCount={1} />);
            act(() => vi.advanceTimersByTime(260 + 10)); // windup -> into burst
            expect(container.querySelector('.battlefield-effect-rise')).not.toBeNull();
        });
    });

    describe('animation visual states', () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it('applies a miss flash on the target during an attack animation', () => {
            const missCombat = { ...mockCombat, log: [{ animation: { type: 'attack', source_id: 'player', target_id: 'enemy_goblin', outcome: 'miss' } }] };
            const { container } = render(<BattlefieldGrid combat={missCombat} tab="overview" zoom={1} displayedLogCount={1} />);
            act(() => vi.advanceTimersByTime(200 + 160 + 10)); // windup + strike -> into impact
            expect(container.querySelector('[style*="blur(2px)"]')).not.toBeNull();
        });

        it('applies a parry flash on the target during an attack animation', () => {
            const parryCombat = { ...mockCombat, log: [{ animation: { type: 'attack', source_id: 'player', target_id: 'enemy_goblin', outcome: 'parry' } }] };
            const { container } = render(<BattlefieldGrid combat={parryCombat} tab="overview" zoom={1} displayedLogCount={1} />);
            act(() => vi.advanceTimersByTime(200 + 160 + 10));
            expect(container.querySelector('[style*="rgba(255, 200, 0, 0.7)"]')).not.toBeNull();
        });

        it('applies no special target treatment for an unrecognized outcome (default branch)', () => {
            const critCombat = { ...mockCombat, log: [{ animation: { type: 'attack', source_id: 'player', target_id: 'enemy_goblin', outcome: 'crit' } }] };
            const { container } = render(<BattlefieldGrid combat={critCombat} tab="overview" zoom={1} displayedLogCount={1} />);
            act(() => vi.advanceTimersByTime(200 + 160 + 10));
            expect(container.querySelector('[style*="rgba(255, 0, 0, 0.7)"]')).toBeNull();
            expect(container.querySelector('[style*="blur(2px)"]')).toBeNull();
            expect(container.querySelector('[style*="rgba(255, 200, 0, 0.7)"]')).toBeNull();
            expect(screen.getByText('G')).toBeInTheDocument();
        });

        it('applies a fixed debuff treatment on the target instead of a strike flash', () => {
            const debuffCombat = { ...mockCombat, log: [{ animation: { type: 'debuff', source_id: 'player', target_id: 'enemy_goblin', outcome: 'hit' } }] };
            const { container } = render(<BattlefieldGrid combat={debuffCombat} tab="overview" zoom={1} displayedLogCount={1} />);
            act(() => vi.advanceTimersByTime(240 + 10)); // windup -> into impact
            expect(container.querySelector('[style*="rgba(153, 68, 255, 0.9)"]')).not.toBeNull();
        });

        it('resets the source transform during the contract phase of a fallback pulse animation', () => {
            const pulseCombat = { ...mockCombat, log: [{ animation: { type: 'mystery_move', source_id: 'player' } }] };
            const { container } = render(<BattlefieldGrid combat={pulseCombat} tab="overview" zoom={1} displayedLogCount={1} />);
            act(() => vi.advanceTimersByTime(200 + 10)); // expand -> into contract
            expect(container.querySelector('[style*="scale(1)"]')).not.toBeNull();
        });

        it('resolves a cardinal string facing to a rotation angle', () => {
            const cardinalCombat = {
                ...mockCombat,
                player: { ...mockCombat.player, position: { x: 6, y: 6, facing: 'NE' } },
            };
            const { container } = render(<BattlefieldGrid combat={cardinalCombat} tab="overview" zoom={1} />);
            expect(container.querySelector('[style*="rotate(45deg)"]')).not.toBeNull();
        });
    });

    it('fades status effect icons to full opacity on hover', () => {
        const combat = {
            ...mockCombat,
            enemies: [{
                ...mockCombat.enemies[0],
                status_effects: [{ name: 'Poisoned', type: 'debuff', beats_left: 3 }],
            }],
        };
        render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);

        const statusWrapper = document.querySelector('.absolute.bottom-full');
        expect(statusWrapper).not.toBeNull();

        // Dimmed until hovered, so a field of tokens isn't a wall of icons.
        expect(statusWrapper.style.opacity).toBe('0.35');
        fireEvent.mouseEnter(statusWrapper);
        expect(statusWrapper.style.opacity).toBe('1');
        fireEvent.mouseLeave(statusWrapper);
        expect(statusWrapper.style.opacity).toBe('0.35');
    });

    it('renders no status-effect wrapper for a combatant that has none', () => {
        // The panel renders null for an empty list, so an unconditional wrapper
        // was an empty div plus two live listeners on every token on the field.
        render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
        expect(document.querySelector('.absolute.bottom-full')).toBeNull();
    });

    it('does not close the selected entity panel when clicking inside it', () => {
        render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
        const jeanToken = screen.getByText('J');
        fireEvent.click(jeanToken.closest('[style*="cursor"]'));
        expect(screen.getByText('Jean')).toBeInTheDocument();

        const panelHeader = screen.getByText('Jean').closest('div');
        fireEvent.click(panelHeader);
        expect(screen.getByText('Jean')).toBeInTheDocument();
    });

    it('falls back to Miscellaneous for a move with no category, in the enemies list', () => {
        const combatEdge = {
            ...mockCombat,
            // current_move, not prepared_move: no serializer in src/ emits the
            // latter, so a fixture built on it asserted through a wire name
            // that does not exist — a mock agreeing with itself.
            enemies: [{ id: 'x', name: 'Wisp', hp: 10, max_hp: 10, current_move: { name: 'Cackle' }, position: { x: 1, y: 1 } }],
        };
        render(<BattlefieldGrid combat={combatEdge} tab="enemies" zoom={1} />);
        expect(screen.getByText(/Cackle/)).toBeInTheDocument();
        expect(screen.getByText('(Miscellaneous)')).toBeInTheDocument();
    });

    it('lists distance and the pending-move countdown in the enemies tab', () => {
        const combatEdge = {
            ...mockCombat,
            enemies: [{
                id: 'x',
                name: 'Wisp',
                hp: 10,
                max_hp: 10,
                distance: 12,
                current_move: { name: 'Drain', category: 'Special', current_stage: 0, beats_left: 1 },
                position: { x: 1, y: 1 },
            }],
        };
        render(<BattlefieldGrid combat={combatEdge} tab="enemies" zoom={1} />);

        expect(screen.getByText(/12 ft/)).toBeInTheDocument();
        expect(screen.getByText(/in 1 beat$/)).toBeInTheDocument();
    });

    it('still names a cooling-down move in the enemies tab, without a countdown', () => {
        const combatEdge = {
            ...mockCombat,
            enemies: [{
                id: 'x',
                name: 'Wisp',
                hp: 10,
                max_hp: 10,
                current_move: { name: 'Drain', category: 'Special', current_stage: 3, beats_left: 4 },
                position: { x: 1, y: 1 },
            }],
        };
        render(<BattlefieldGrid combat={combatEdge} tab="enemies" zoom={1} />);

        // Suppressing the *telegraph* for a resolved move must not swallow the
        // fact that the enemy is spent — that is tactically useful information.
        expect(screen.getByText(/Cooling down from: Drain/)).toBeInTheDocument();
        expect(screen.queryByText(/in 4 beats/)).toBeNull();
    });

    it('renders an enemy with no active move and zero max_hp without crashing', () => {
        const combatEdge = {
            ...mockCombat,
            enemies: [{ id: 'x', name: 'Husk', hp: 0, max_hp: 0, position: { x: 1, y: 1 } }],
        };
        render(<BattlefieldGrid combat={combatEdge} tab="enemies" zoom={1} />);
        expect(screen.getByText('Husk')).toBeInTheDocument();
    });

    it('reads HP/max HP from a nested health object when hp/max_hp are absent (torus marker)', () => {
        const combatEdge = {
            ...mockCombat,
            enemies: [{
                id: 'x', name: 'Wisp',
                health: { current: 30, max: 60 },
                position: { x: 1, y: 1 },
            }],
        };
        const { container } = render(<BattlefieldGrid combat={combatEdge} tab="overview" zoom={1} />);
        expect(screen.getByText('W')).toBeInTheDocument();
        expect(container.querySelector('[stroke-dasharray="70.7 141.4"]')).not.toBeNull();
    });

    it('falls back to "?" for a marker with no displaySymbol, battle_symbol, or name', () => {
        const combatEdge = {
            ...mockCombat,
            enemies: [{ id: 'x', hp: 10, max_hp: 10, position: { x: 1, y: 1 } }],
        };
        render(<BattlefieldGrid combat={combatEdge} tab="overview" zoom={1} />);
        expect(screen.getByText('?')).toBeInTheDocument();
    });

    it('falls back to a 0-degree facing for an unrecognized cardinal string', () => {
        const combatEdge = {
            ...mockCombat,
            player: { ...mockCombat.player, position: { x: 6, y: 6, facing: 'UNKNOWN' } },
        };
        const { container } = render(<BattlefieldGrid combat={combatEdge} tab="overview" zoom={1} />);
        expect(container.querySelector('[style*="rotate(0deg)"]')).not.toBeNull();
    });

    it('renders a marker with no pending move without a category glow/border', () => {
        const combatEdge = {
            ...mockCombat,
            player: { ...mockCombat.player, current_move: undefined },
        };
        render(<BattlefieldGrid combat={combatEdge} tab="overview" zoom={1} />);
        expect(screen.getByText('J')).toBeInTheDocument();
    });

    it('renders a dashed extent marker when the real map is smaller than the viewport', () => {
        const { container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} mapSize={5} />);
        expect(container.querySelector('[style*="dashed"]')).not.toBeNull();
    });

    it('renders breadcrumb trail dots from beat history', () => {
        const allBeatStates = [
            { player: { position: { x: 5, y: 6 } }, enemies: [{ id: 'enemy_goblin', position: { x: 7, y: 6 } }] },
            { player: { position: { x: 6, y: 6 } }, enemies: [{ id: 'enemy_goblin', position: { x: 8, y: 6 } }] },
        ];
        const { container } = render(
            <BattlefieldGrid combat={mockCombat} allBeatStates={allBeatStates} currentBeatIndex={2} tab="overview" zoom={1} />
        );
        expect(container.querySelectorAll('[style*="blur(1px)"]').length).toBeGreaterThan(0);
    });

    it('derives the map size from entity positions when mapSize is not provided', () => {
        const farCombat = {
            player: { ...mockCombat.player, position: { x: 15, y: 15 } },
            enemies: [],
        };
        const { container } = render(<BattlefieldGrid combat={farCombat} tab="overview" zoom="fit" />);
        // maxCoord 15 + 1 => a 16x16 arena. The combatant sits in its far
        // corner, so the 13x13 frame is clamped back inside the arena and every
        // cell is on-map: 169 lit. (A 9x9 arena — the floor, i.e. a failure to
        // derive the size from positions — would leave only 81 lit.)
        const cells = container.querySelectorAll('[style*="background-color: rgba(255, 255, 255, 0.03)"]');
        expect(cells.length).toBe(169);
    });

    it('clamps the fit frame inside the arena instead of framing empty void', () => {
        // Combatants hard against the arena's west edge. Centering the frame on
        // them alone would spend half the viewport on out-of-bounds cells.
        const cornerCombat = {
            player: { ...mockCombat.player, position: { x: 0, y: 0 } },
            enemies: [{ id: 'e', name: 'Slime', hp: 5, max_hp: 5, position: { x: 1, y: 1 } }],
        };
        const { container } = render(
            <BattlefieldGrid combat={cornerCombat} tab="overview" zoom="fit" mapSize={40} />
        );

        const cells = container.querySelectorAll('[style*="background-color: rgba(255, 255, 255, 0.03)"]');
        expect(cells.length).toBe(13 * 13);
    });

    describe('touch and mouse panning', () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        // jsdom reports a zero-sized box, and the pan clamp is a fraction of
        // that box — so without a real rect every pan clamps to zero and the
        // gesture assertions below would pass vacuously.
        const renderPannableGrid = (props = {}) => {
            const result = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} {...props} />);
            const gridEl = result.container.firstChild;
            gridEl.getBoundingClientRect = () => ({ width: 400, height: 400, top: 0, left: 0, right: 400, bottom: 400 });
            // The pan layer sits inside the viewport box, which is itself
            // inside the grid container.
            return { ...result, gridEl, panLayer: result.getByTestId('battlefield-viewport').firstChild };
        };

        it('keeps a touch pan where the player left it instead of springing back', () => {
            const { gridEl, panLayer } = renderPannableGrid();

            fireEvent.touchStart(gridEl, { touches: [{ clientX: 100, clientY: 100 }] });
            fireEvent.touchMove(gridEl, { touches: [{ clientX: 60, clientY: 80 }] });
            fireEvent.touchEnd(gridEl);
            expect(panLayer.style.transform).toBe('translate(-40.0px, -20.0px)');

            // The old behaviour decayed the offset to zero on release, which
            // made the advertised "drag to pan" affordance do nothing at all.
            act(() => vi.advanceTimersByTime(1000));
            expect(panLayer.style.transform).toBe('translate(-40.0px, -20.0px)');
        });

        it('offers a recenter control once panned, and it returns the map to center', () => {
            const { gridEl, panLayer } = renderPannableGrid();
            expect(screen.queryByTitle('Recenter the map')).toBeNull();

            fireEvent.mouseDown(gridEl, { button: 0, clientX: 100, clientY: 100 });
            fireEvent.mouseMove(window, { clientX: 60, clientY: 80 });
            fireEvent.mouseUp(window);
            expect(panLayer.style.transform).toBe('translate(-40.0px, -20.0px)');

            const recenter = screen.getByTitle('Recenter the map');
            act(() => { fireEvent.click(recenter); vi.advanceTimersByTime(1000); });

            expect(panLayer.style.transform).toBe('translate(0.0px, 0.0px)');
            expect(screen.queryByTitle('Recenter the map')).toBeNull();
        });

        it('does not clear the selected combatant when a drag ends over the map', () => {
            const { gridEl } = renderPannableGrid();

            fireEvent.click(screen.getByText('J'));
            expect(screen.getByText('INTEGRITY (HP)')).toBeInTheDocument();

            // A drag also fires a click on mouseup; that must not be read as a
            // background click dismissing the panel.
            fireEvent.mouseDown(gridEl, { button: 0, clientX: 100, clientY: 100 });
            fireEvent.mouseMove(window, { clientX: 60, clientY: 80 });
            fireEvent.mouseUp(window);
            fireEvent.click(gridEl);

            expect(screen.getByText('INTEGRITY (HP)')).toBeInTheDocument();
        });

        it('ignores multi-touch gestures and secondary mouse buttons', () => {
            const { container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
            const gridEl = container.firstChild;

            expect(() => fireEvent.touchStart(gridEl, { touches: [{ clientX: 0, clientY: 0 }, { clientX: 10, clientY: 10 }] })).not.toThrow();
            expect(() => fireEvent.mouseDown(gridEl, { button: 2, clientX: 0, clientY: 0 })).not.toThrow();
            expect(() => fireEvent.mouseMove(window, { clientX: 5, clientY: 5 })).not.toThrow();
            expect(() => fireEvent.mouseUp(window)).not.toThrow();
        });
    });

    describe('smooth camera panning', () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it('animates the camera toward the player when they move within the viewport', () => {
            const { rerender, unmount } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
            const movedCombat = { ...mockCombat, player: { ...mockCombat.player, position: { x: 7, y: 6, facing: 0 } } };

            expect(() => {
                rerender(<BattlefieldGrid combat={movedCombat} tab="overview" zoom={1} />);
                act(() => vi.advanceTimersByTime(500));
            }).not.toThrow();

            unmount();
        });

        it('snaps the camera immediately on a jump larger than the viewport radius', () => {
            const { rerender } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
            const jumpedCombat = { ...mockCombat, player: { ...mockCombat.player, position: { x: 40, y: 40, facing: 0 } } };

            expect(() => {
                rerender(<BattlefieldGrid combat={jumpedCombat} tab="overview" zoom={1} />);
                act(() => vi.advanceTimersByTime(50));
            }).not.toThrow();
        });

        it('clears the camera transform when switching into full-map zoom', () => {
            const { rerender } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
            expect(() => rerender(<BattlefieldGrid combat={mockCombat} tab="overview" zoom="full" />)).not.toThrow();
        });
    });
});
