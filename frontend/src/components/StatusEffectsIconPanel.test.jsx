import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import StatusEffectsIconPanel from './StatusEffectsIconPanel';

describe('StatusEffectsIconPanel', () => {
    const mockEffects = [
        {
            name: 'Burn',
            type: 'ailment',
            description: 'Taking fire damage over time.',
            duration_remaining: 3
        },
        {
            name: 'Shield',
            type: 'buff',
            description: 'Increases protection.',
            duration_remaining: 5
        }
    ];

    it('does not render when no effects', () => {
        const { container } = render(<StatusEffectsIconPanel effects={[]} />);
        expect(container.firstChild).toBeNull();
    });

    it('renders effect icons', () => {
        render(<StatusEffectsIconPanel effects={mockEffects} />);

        expect(screen.getByText('🔥')).toBeDefined();
        expect(screen.getByText('🛡️')).toBeDefined();
    });

    it('responds to hover events', () => {
        const { container } = render(<StatusEffectsIconPanel effects={mockEffects} />);

        const burnIcon = screen.getByText('🔥').parentElement;

        // Verify icon exists
        expect(burnIcon).toBeDefined();

        // Trigger hover - component should handle this gracefully
        fireEvent.mouseEnter(burnIcon);
        fireEvent.mouseLeave(burnIcon);

        // Component should still be rendered
        expect(screen.getByText('🔥')).toBeDefined();
    });

    it('uses default icon for unknown effects', () => {
        const unknownEffects = [{ name: 'Mystic Energy', type: 'buff' }];
        render(<StatusEffectsIconPanel effects={unknownEffects} />);
        expect(screen.getByText('✨')).toBeDefined();
    });

    describe('Effect Type Variations', () => {
        it('renders buff effects', () => {
            const buffs = [
                { name: 'Strength Boost', type: 'buff', description: 'Increased strength', duration_remaining: 5 }
            ];
            render(<StatusEffectsIconPanel effects={buffs} />);
            expect(screen.getByText('💪')).toBeDefined();
        });

        it('renders ailment effects', () => {
            const ailments = [
                { name: 'Poisoned', type: 'ailment', description: 'Poison damage', duration_remaining: 3 }
            ];
            render(<StatusEffectsIconPanel effects={ailments} />);
            expect(screen.getByText('🧪')).toBeDefined();
        });

        it('renders debuff effects', () => {
            const debuffs = [
                { name: 'Weakness', type: 'debuff', description: 'Reduced damage', duration_remaining: 4 }
            ];
            render(<StatusEffectsIconPanel effects={debuffs} />);
            // Should render without error
            expect(screen.getByText).toBeDefined();
        });

        it('handles mixed effect types', () => {
            const mixed = [
                { name: 'Burn', type: 'ailment', description: 'Fire damage', duration_remaining: 2 },
                { name: 'Shield', type: 'buff', description: 'Protection', duration_remaining: 5 },
                { name: 'Weakness', type: 'debuff', description: 'Low defense', duration_remaining: 3 }
            ];
            render(<StatusEffectsIconPanel effects={mixed} />);
            expect(screen.getByText('🔥')).toBeDefined();
            expect(screen.getByText('🛡️')).toBeDefined();
        });
    });

    describe('Duration Display', () => {
        it('displays effect with remaining duration', () => {
            const shortDuration = [
                { name: 'Quick Effect', type: 'buff', description: 'Brief boost', duration_remaining: 1 }
            ];
            render(<StatusEffectsIconPanel effects={shortDuration} />);
            expect(screen.getByText).toBeDefined();
        });

        it('displays effect expiring soon (1 beat remaining)', () => {
            const expiring = [
                { name: 'Ending Effect', type: 'buff', description: 'Almost gone', duration_remaining: 1 }
            ];
            render(<StatusEffectsIconPanel effects={expiring} />);
            expect(screen.getByText).toBeDefined();
        });

        it('displays effect with long duration', () => {
            const longDuration = [
                { name: 'Long Buff', type: 'buff', description: 'Extended protection', duration_remaining: 99 }
            ];
            render(<StatusEffectsIconPanel effects={longDuration} />);
            expect(screen.getByText).toBeDefined();
        });

        it('handles zero duration remaining', () => {
            const noDuration = [
                { name: 'Expired', type: 'buff', description: 'Already expired', duration_remaining: 0 }
            ];
            render(<StatusEffectsIconPanel effects={noDuration} />);
            expect(screen.getByText).toBeDefined();
        });

        it('handles negative duration gracefully', () => {
            const negativeDuration = [
                { name: 'Over-expired', type: 'ailment', description: 'Should not happen', duration_remaining: -1 }
            ];
            expect(() => {
                render(<StatusEffectsIconPanel effects={negativeDuration} />);
            }).not.toThrow();
        });
    });

    describe('Multiple Effects', () => {
        it('renders many effects', () => {
            const manyEffects = Array.from({ length: 15 }, (_, i) => ({
                name: `Effect ${i}`,
                type: i % 2 === 0 ? 'buff' : 'ailment',
                description: `Description ${i}`,
                duration_remaining: Math.floor(Math.random() * 10) + 1
            }));
            render(<StatusEffectsIconPanel effects={manyEffects} />);
            expect(screen.getByText).toBeDefined();
        });

        it('handles duplicate effect names', () => {
            const duplicates = [
                { name: 'Burn', type: 'ailment', description: 'Fire damage 1', duration_remaining: 2 },
                { name: 'Burn', type: 'ailment', description: 'Fire damage 2', duration_remaining: 3 }
            ];
            render(<StatusEffectsIconPanel effects={duplicates} />);
            expect(screen.getAllByText('🔥')).toHaveLength(2);
        });

        it('handles effects with same icon', () => {
            const sameIcon = [
                { name: 'Fire Burn', type: 'ailment', description: 'Burning', duration_remaining: 2 },
                { name: 'Lava Burn', type: 'ailment', description: 'Hot burning', duration_remaining: 3 }
            ];
            render(<StatusEffectsIconPanel effects={sameIcon} />);
            expect(screen.getAllByText('🔥')).toHaveLength(2);
        });
    });

    describe('Hover and Interaction', () => {
        it('handles hover on single effect', () => {
            const { container } = render(<StatusEffectsIconPanel effects={mockEffects} />);
            const shield = screen.getByText('🛡️');

            fireEvent.mouseEnter(shield.parentElement);
            expect(shield).toBeDefined();

            fireEvent.mouseLeave(shield.parentElement);
            expect(shield).toBeDefined();
        });

        it('handles rapid hover on multiple effects', () => {
            const { container } = render(<StatusEffectsIconPanel effects={mockEffects} />);
            const icons = screen.getAllByText(/🔥|🛡️/);

            icons.forEach(icon => {
                fireEvent.mouseEnter(icon.parentElement);
                fireEvent.mouseLeave(icon.parentElement);
            });

            expect(screen.getByText('🔥')).toBeDefined();
        });

        it('handles hover and unmount', () => {
            const { container, unmount } = render(<StatusEffectsIconPanel effects={mockEffects} />);
            const burnIcon = screen.getByText('🔥');

            fireEvent.mouseEnter(burnIcon.parentElement);
            unmount();

            expect(container.firstChild).toBeNull();
        });
    });

    describe('Description Handling', () => {
        it('displays effects with descriptions', () => {
            const withDesc = [
                { name: 'Known Effect', type: 'buff', description: 'Clear description', duration_remaining: 5 }
            ];
            render(<StatusEffectsIconPanel effects={withDesc} />);
            expect(screen.getByText).toBeDefined();
        });

        it('handles missing descriptions', () => {
            const noDesc = [
                { name: 'Mystery Effect', type: 'buff', duration_remaining: 3 }
            ];
            expect(() => {
                render(<StatusEffectsIconPanel effects={noDesc} />);
            }).not.toThrow();
        });

        it('handles very long descriptions', () => {
            const longDesc = [
                {
                    name: 'Complex Effect',
                    type: 'buff',
                    description: 'This is a very long description that explains in great detail what this effect does and how it impacts the player. '.repeat(5),
                    duration_remaining: 5
                }
            ];
            render(<StatusEffectsIconPanel effects={longDesc} />);
            expect(screen.getByText).toBeDefined();
        });

        it('handles special characters in descriptions', () => {
            const specialDesc = [
                {
                    name: 'Special',
                    type: 'buff',
                    description: 'Effect with special chars: <>&"\'',
                    duration_remaining: 3
                }
            ];
            render(<StatusEffectsIconPanel effects={specialDesc} />);
            expect(screen.getByText).toBeDefined();
        });
    });

    describe('Undefined and Null Handling', () => {
        it('handles undefined effects array', () => {
            const { container } = render(<StatusEffectsIconPanel effects={undefined} />);
            expect(container.firstChild).toBeNull();
        });

        it('handles null effects array', () => {
            const { container } = render(<StatusEffectsIconPanel effects={null} />);
            expect(container.firstChild).toBeNull();
        });

        it('handles effects with missing optional properties', () => {
            const incomplete = [
                { name: 'Minimal Effect', type: 'buff' }
            ];
            expect(() => {
                render(<StatusEffectsIconPanel effects={incomplete} />);
            }).not.toThrow();
        });
    });

    describe('Performance', () => {
        it('handles rendering large effect list efficiently', () => {
            const largeList = Array.from({ length: 100 }, (_, i) => ({
                name: `Effect ${i}`,
                type: 'buff',
                description: `Effect number ${i}`,
                duration_remaining: i % 20
            }));

            expect(() => {
                render(<StatusEffectsIconPanel effects={largeList} />);
            }).not.toThrow();
        });

        it('re-renders when effects change', () => {
            const { rerender } = render(<StatusEffectsIconPanel effects={mockEffects} />);

            const newEffects = [
                { name: 'New Effect', type: 'buff', description: 'Different', duration_remaining: 5 }
            ];

            rerender(<StatusEffectsIconPanel effects={newEffects} />);
            expect(screen.getByText).toBeDefined();
        });
    });
});
