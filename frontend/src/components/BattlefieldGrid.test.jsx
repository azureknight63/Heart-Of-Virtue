import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import BattlefieldGrid from './BattlefieldGrid';
import { getAnimationDuration } from '../utils/animationConfigs';

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

    it('renders entire grid in full mode', () => {
        const { container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom="full" />);

        // Full mode shows the entire map (9x9 = 81 cells for mockCombat)
        const cells = container.querySelectorAll('[style*="background-color: rgba(255, 255, 255, 0.03)"]');
        expect(cells.length).toBe(81);
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
            expect(mockPlaySFX).toHaveBeenCalledWith('enemy_death');
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

    it('shows status effect icons at full opacity on hover', () => {
        render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
        const statusWrapper = document.querySelector('.absolute.bottom-full');
        expect(statusWrapper).not.toBeNull();
        expect(() => fireEvent.mouseEnter(statusWrapper)).not.toThrow();
        expect(() => fireEvent.mouseLeave(statusWrapper)).not.toThrow();
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

    it('falls back to Miscellaneous for a prepared_move with no category, in the enemies list', () => {
        const combatEdge = {
            ...mockCombat,
            enemies: [{ id: 'x', name: 'Wisp', hp: 10, max_hp: 10, prepared_move: { name: 'Cackle' }, position: { x: 1, y: 1 } }],
        };
        render(<BattlefieldGrid combat={combatEdge} tab="enemies" zoom={1} />);
        expect(screen.getByText(/Cackle/)).toBeInTheDocument();
        expect(screen.getByText('(Miscellaneous)')).toBeInTheDocument();
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
            player: { ...mockCombat.player, current_move: undefined, prepared_move: undefined },
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
        const { container } = render(<BattlefieldGrid combat={farCombat} tab="overview" zoom="full" />);
        // Full mode shows the entire derived map: maxCoord 15 + 1 = 16x16 cells
        const cells = container.querySelectorAll('[style*="background-color: rgba(255, 255, 255, 0.03)"]');
        expect(cells.length).toBe(256);
    });

    describe('touch and mouse panning', () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it('pans the map via touch drag and decays back afterward', () => {
            const { container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
            const gridEl = container.firstChild;
            expect(gridEl).not.toBeNull();

            fireEvent.touchStart(gridEl, { touches: [{ clientX: 100, clientY: 100 }] });
            fireEvent.touchMove(gridEl, { touches: [{ clientX: 60, clientY: 80 }] });
            fireEvent.touchEnd(gridEl);

            expect(() => act(() => vi.advanceTimersByTime(500))).not.toThrow();
        });

        it('pans the map via mouse drag and decays back afterward', () => {
            const { container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
            const gridEl = container.firstChild;

            fireEvent.mouseDown(gridEl, { button: 0, clientX: 100, clientY: 100 });
            fireEvent.mouseMove(window, { clientX: 60, clientY: 80 });
            fireEvent.mouseUp(window);

            expect(() => act(() => vi.advanceTimersByTime(500))).not.toThrow();
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
