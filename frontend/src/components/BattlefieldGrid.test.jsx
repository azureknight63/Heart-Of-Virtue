import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import BattlefieldGrid from './BattlefieldGrid';
import { getAnimationDuration } from '../utils/animationConfigs';
import { CATEGORY_GROUPS, MOVE_CATEGORY_COLOR, MOVE_CATEGORY_GLOW } from '../utils/categories';

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
            // CombatantSerializer._serialize_position emits `pos.facing.name`
            // — a cardinal string, never degrees. The fixture used to send
            // 0/180, which meant every test here exercised the numeric branch
            // production never reaches, leaving the live FACING_MAP lookup
            // covered by two edge-case tests only.
            position: { x: 6, y: 6, facing: 'N' },
            current_move: { category: 'Attack' }
        },
        enemies: [
            {
                id: 'enemy_goblin',
                name: 'Goblin',
                hp: 50,
                max_hp: 50,
                position: { x: 8, y: 6, facing: 'S' },
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

    // The token that carries a combatant's pending-move border/glow.
    const tokenFor = (letter) => screen.getByText(letter).closest('[style*="border-color"]');
    const rgb = (hex) => {
        const n = parseInt(hex.slice(1), 16);
        return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
    };

    // Every category the engine can put in `current_move` — taken from
    // CATEGORY_GROUPS so a new engine category cannot slip past unstyled.
    const ENGINE_CATEGORIES = Object.values(CATEGORY_GROUPS).flat();

    it.each(ENGINE_CATEGORIES.map((c) => [c]))(
        'borders a token telegraphing a %s move in that category\'s colour',
        (category) => {
            // The old test used 'Attack', 'Special' and 'Supernatural' —
            // NONE of which the engine emits — and then asserted only that the
            // three markers were `toBeDefined()`, with a comment conceding it
            // could not check the styles it was named for. So the mapping it
            // claimed to prove went entirely unexercised, exactly as the
            // CooldownTray fixtures did.
            render(
                <BattlefieldGrid
                    combat={{
                        ...mockCombat,
                        player: { ...mockCombat.player, current_move: { category } },
                    }}
                    tab="overview"
                    zoom={1}
                />
            );
            const token = tokenFor('J');
            expect(token.style.borderColor).toBe(rgb(MOVE_CATEGORY_COLOR[category]));
            expect(token.style.getPropertyValue('--pending-glow')).toBe(MOVE_CATEGORY_GLOW[category]);
            expect(token.className).toContain('battlefield-pending-glow');
        }
    );

    it('renders several combatants telegraphing different categories at once', () => {
        const multiMoveCombat = {
            player: { ...mockCombat.player, current_move: { category: 'Mastery' } },
            enemies: [
                { ...mockCombat.enemies[0], current_move: { category: 'Defensive' } },
                {
                    name: 'Orc', hp: 100, max_hp: 100, position: { x: 5, y: 5, facing: 'S' },
                    current_move: { category: 'Miscellaneous' },
                },
            ],
        };
        render(<BattlefieldGrid combat={multiMoveCombat} tab="overview" zoom={1} />);

        // Each token takes its OWN category's colour — a shared/leaked style
        // would have gone unnoticed under the old presence-only assertions.
        expect(tokenFor('J').style.borderColor).toBe(rgb(MOVE_CATEGORY_COLOR.Mastery));
        expect(tokenFor('G').style.borderColor).toBe(rgb(MOVE_CATEGORY_COLOR.Defensive));
        expect(tokenFor('O').style.borderColor).toBe(rgb(MOVE_CATEGORY_COLOR.Miscellaneous));
    });

    /** The rotating hover reticle mounts only while a token is hovered. */
    const reticles = (container) => container.querySelectorAll('.absolute.inset-\\[-12px\\]');

    it('mounts the hover reticle on the hovered token only, and removes it on leave', () => {
        // The old version fired mouseEnter/mouseLeave and asserted only
        // `.not.toThrow()`, excusing itself with "reticle rendering relies on
        // Tailwind JIT". It does not: `isHovered && <div>` mounts a real SVG
        // node that jsdom renders, so the whole hover contract was assertable
        // and simply unasserted — every hover handler could have been deleted.
        const { container } = render(<BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />);
        const entityWrapper = screen.getByText('J').closest('[style*="cursor"]');
        const enemyWrapper = screen.getByText('G').closest('[style*="cursor"]');

        expect(reticles(container)).toHaveLength(0);

        fireEvent.mouseEnter(entityWrapper);
        expect(reticles(container)).toHaveLength(1);
        expect(entityWrapper.contains(reticles(container)[0])).toBe(true);
        expect(enemyWrapper.contains(reticles(container)[0])).toBe(false);

        // Moving to another token moves the reticle rather than adding one.
        fireEvent.mouseEnter(enemyWrapper);
        expect(reticles(container)).toHaveLength(1);
        expect(enemyWrapper.contains(reticles(container)[0])).toBe(true);

        fireEvent.mouseLeave(enemyWrapper);
        expect(reticles(container)).toHaveLength(0);
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

        it('passes a numeric facing straight through as degrees', () => {
            // The legacy branch: no serializer sends this today, but the
            // component still accepts it, so it needs its own case now that the
            // shared fixture uses the real cardinal-string shape.
            const degreesCombat = {
                ...mockCombat,
                player: { ...mockCombat.player, position: { x: 6, y: 6, facing: 135 } },
            };
            const { container } = render(<BattlefieldGrid combat={degreesCombat} tab="overview" zoom={1} />);
            expect(container.querySelector('[style*="rotate(135deg)"]')).not.toBeNull();
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

        // The whole point of the handler is the opacity swap: icons sit at 0.35
        // so they do not fight the token for attention, and rise to 1 when the
        // player reaches for them. `.not.toThrow()` proved neither value.
        expect(statusWrapper.style.opacity).toBe('0.35');
        fireEvent.mouseEnter(statusWrapper);
        expect(statusWrapper.style.opacity).toBe('1');
        fireEvent.mouseLeave(statusWrapper);
        expect(statusWrapper.style.opacity).toBe('0.35');
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

        // applyDelta clamps the pan to 40% of the grid's measured size. jsdom
        // reports 0x0, so an un-stubbed grid clamps EVERY drag to zero — which
        // is why these tests could previously only assert `.not.toThrow()`:
        // there was no pan to observe. Give the element a real box so the drag
        // actually moves the layer.
        const GRID_W = 500;
        const GRID_H = 400;
        const sizeGrid = (el) => {
            el.getBoundingClientRect = () => ({
                width: GRID_W, height: GRID_H,
                top: 0, left: 0, right: GRID_W, bottom: GRID_H, x: 0, y: 0, toJSON() {},
            });
        };
        /** The panLayerRef div — the only node carrying a `translate(...px...)`. */
        const panTransform = (container) =>
            [...container.querySelectorAll('div')]
                .map((d) => d.style.transform)
                .find((t) => t.startsWith('translate(') && t.includes('px'));

        const renderPannableGrid = (props = {}) => {
            const utils = render(
                <BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} {...props} />
            );
            const gridEl = utils.container.firstChild;
            sizeGrid(gridEl);
            return { ...utils, gridEl };
        };

        it('pans the map via touch drag and decays back afterward', () => {
            const { container, gridEl } = renderPannableGrid();

            fireEvent.touchStart(gridEl, { touches: [{ clientX: 100, clientY: 100 }] });
            fireEvent.touchMove(gridEl, { touches: [{ clientX: 60, clientY: 80 }] });
            // The layer follows the finger by exactly the drag delta.
            expect(panTransform(container)).toBe('translate(-40.0px, -20.0px)');

            fireEvent.touchEnd(gridEl);
            act(() => vi.advanceTimersByTime(500));
            // ...then springs back to centre once the finger lifts.
            expect(panTransform(container)).toBe('translate(0.0px, 0.0px)');
        });

        it('pans the map via mouse drag and decays back afterward', () => {
            const { container, gridEl } = renderPannableGrid();

            fireEvent.mouseDown(gridEl, { button: 0, clientX: 100, clientY: 100 });
            fireEvent.mouseMove(window, { clientX: 60, clientY: 80 });
            expect(panTransform(container)).toBe('translate(-40.0px, -20.0px)');
            // A drag in progress swaps the cursor.
            expect(gridEl.style.cursor).toBe('grabbing');

            fireEvent.mouseUp(window);
            expect(gridEl.style.cursor).toBe('');
            act(() => vi.advanceTimersByTime(500));
            expect(panTransform(container)).toBe('translate(0.0px, 0.0px)');
        });

        it('clamps the pan to 40% of the grid in each axis', () => {
            const { container, gridEl } = renderPannableGrid();

            fireEvent.mouseDown(gridEl, { button: 0, clientX: 0, clientY: 0 });
            fireEvent.mouseMove(window, { clientX: 9999, clientY: 9999 });
            // 500 * 0.4 = 200, 400 * 0.4 = 160 — not the raw 9999.
            expect(panTransform(container)).toBe('translate(200.0px, 160.0px)');
        });

        it('ignores multi-touch gestures and secondary mouse buttons', () => {
            const { container, gridEl } = renderPannableGrid();
            const atRest = 'translate(0.0px, 0.0px)';

            // A two-finger gesture (pinch/zoom) must not be treated as a pan.
            fireEvent.touchStart(gridEl, {
                touches: [{ clientX: 0, clientY: 0 }, { clientX: 10, clientY: 10 }],
            });
            fireEvent.touchMove(gridEl, {
                touches: [{ clientX: 50, clientY: 50 }, { clientX: 60, clientY: 60 }],
            });
            expect(panTransform(container)).toBe(atRest);

            // Right-click drag must not pan either (it opens a context menu).
            fireEvent.mouseDown(gridEl, { button: 2, clientX: 0, clientY: 0 });
            fireEvent.mouseMove(window, { clientX: 50, clientY: 50 });
            expect(panTransform(container)).toBe(atRest);
            fireEvent.mouseUp(window);
        });

        // `combat_id` identifies a FIGHT, not a call: it survives a reinit
        // (wave transition / reinforcement spawn — still the same fight) and
        // changes only when a genuinely new combat starts. The camera reset is
        // keyed on it, so both halves have to hold.
        describe('pan reset keyed on combat_id', () => {
            const panTo = (container, gridEl) => {
                fireEvent.mouseDown(gridEl, { button: 0, clientX: 100, clientY: 100 });
                fireEvent.mouseMove(window, { clientX: 60, clientY: 80 });
                fireEvent.mouseUp(window);
                expect(panTransform(container)).toBe('translate(-40.0px, -20.0px)');
            };

            it('keeps the pan across a reinit that reuses the same combat_id', () => {
                const { container, gridEl, rerender } = renderPannableGrid({
                    combatId: 'fight-0001',
                    combatActive: true,
                });
                panTo(container, gridEl);

                // A wave transition: new enemies, SAME fight, same combat_id.
                rerender(
                    <BattlefieldGrid
                        combat={{ ...mockCombat, enemies: [...mockCombat.enemies] }}
                        tab="overview"
                        zoom={1}
                        combatId="fight-0001"
                        combatActive
                    />
                );
                expect(panTransform(container)).toBe('translate(-40.0px, -20.0px)');
            });

            it('recentres the camera when a genuinely new fight starts', () => {
                const { container, gridEl, rerender } = renderPannableGrid({
                    combatId: 'fight-0001',
                    combatActive: true,
                });
                panTo(container, gridEl);

                rerender(
                    <BattlefieldGrid
                        combat={mockCombat}
                        tab="overview"
                        zoom={1}
                        combatId="fight-0002"
                        combatActive
                    />
                );
                expect(panTransform(container)).toBe('translate(0.0px, 0.0px)');
            });

            it('recentres the camera when combat ends', () => {
                const { container, gridEl, rerender } = renderPannableGrid({
                    combatId: 'fight-0001',
                    combatActive: true,
                });
                panTo(container, gridEl);

                rerender(
                    <BattlefieldGrid
                        combat={mockCombat}
                        tab="overview"
                        zoom={1}
                        combatId="fight-0001"
                        combatActive={false}
                    />
                );
                expect(panTransform(container)).toBe('translate(0.0px, 0.0px)');
            });
        });
    });

    describe('smooth camera panning', () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        // contentDivRef — the one div marked `will-change: transform` — receives
        // the per-frame sub-cell camera offset as a percent translate. Selecting
        // it by that marker rather than by "any percent translate" matters:
        // every combatant token is positioned with a percent translate too.
        // A cleared camera leaves the empty string, not a missing node.
        const cameraTransform = (container) => {
            const el = [...container.querySelectorAll('div')].find(
                (d) => d.style.willChange === 'transform'
            );
            expect(el).toBeDefined();
            return el.style.transform;
        };

        const movePlayerTo = (x, y) => ({
            ...mockCombat,
            player: { ...mockCombat.player, position: { x, y, facing: 'N' } },
        });

        it('animates the camera toward the player when they move within the viewport', () => {
            const { container, rerender, unmount } = render(
                <BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />
            );
            // At rest the camera sits on its snap cell, so there is no sub-cell offset.
            expect(cameraTransform(container)).toBe('');

            rerender(<BattlefieldGrid combat={movePlayerTo(7, 6)} tab="overview" zoom={1} />);
            // One frame in, the camera is mid-lerp: a real fractional offset,
            // not the cleared/absent transform a snap would leave.
            act(() => vi.advanceTimersByTime(20));
            const midFlight = cameraTransform(container);
            expect(midFlight).toMatch(/^translate\(-?\d+\.\d+%, -?\d+\.\d+%\)$/);
            expect(midFlight).not.toBe('translate(0.000%, 0.000%)');

            // Still animating a few frames later — a one-frame blip that then
            // stalled would satisfy the mid-flight check alone.
            act(() => vi.advanceTimersByTime(200));
            expect(cameraTransform(container)).not.toBe('');
            // (The residual is measured against the camera's CURRENT snap cell,
            // so it is not monotonic — it flips as the camera crosses a cell
            // boundary. Only the convergence below is a safe invariant.)

            // The offset is cleared outright once the lerp converges.
            act(() => vi.advanceTimersByTime(3000));
            expect(cameraTransform(container)).toBe('');
            unmount();
        });

        it('snaps the camera immediately on a jump larger than the viewport radius', () => {
            const { container, rerender } = render(
                <BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />
            );
            rerender(<BattlefieldGrid combat={movePlayerTo(40, 40)} tab="overview" zoom={1} />);

            // No frames advanced: a teleport must land on the new cell in the
            // same commit rather than lerping across 34 cells of empty grid.
            expect(cameraTransform(container)).toBe('');
            act(() => vi.advanceTimersByTime(50));
            expect(cameraTransform(container)).toBe('');
        });

        it('clears the camera transform when switching into full-map zoom', () => {
            const { container, rerender } = render(
                <BattlefieldGrid combat={mockCombat} tab="overview" zoom={1} />
            );
            // Get a real sub-cell offset on screen first, so "cleared" is a
            // state change rather than the value it already had.
            rerender(<BattlefieldGrid combat={movePlayerTo(7, 6)} tab="overview" zoom={1} />);
            act(() => vi.advanceTimersByTime(20));
            expect(cameraTransform(container)).not.toBe('');

            rerender(<BattlefieldGrid combat={movePlayerTo(7, 6)} tab="overview" zoom="full" />);
            expect(cameraTransform(container)).toBe('');
        });
    });
});
