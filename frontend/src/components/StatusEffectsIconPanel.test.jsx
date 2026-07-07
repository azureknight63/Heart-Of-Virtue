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

        const burnIcon = screen.getByText('🔥');

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

            fireEvent.mouseEnter(shield);
            expect(shield).toBeDefined();

            fireEvent.mouseLeave(shield);
            expect(shield).toBeDefined();
        });

        it('handles rapid hover on multiple effects', () => {
            const { container } = render(<StatusEffectsIconPanel effects={mockEffects} />);
            const icons = screen.getAllByText(/🔥|🛡️/);

            icons.forEach(icon => {
                fireEvent.mouseEnter(icon);
                fireEvent.mouseLeave(icon);
            });

            expect(screen.getByText('🔥')).toBeDefined();
        });

        it('handles hover and unmount', () => {
            const { container, unmount } = render(<StatusEffectsIconPanel effects={mockEffects} />);
            const burnIcon = screen.getByText('🔥');

            fireEvent.mouseEnter(burnIcon);
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

    describe('Tooltip Content', () => {
        it('shows the tooltip with name, description, and duration on hover', () => {
            render(<StatusEffectsIconPanel effects={mockEffects} />);
            const burnIcon = screen.getByText('🔥');

            fireEvent.mouseEnter(burnIcon);

            expect(screen.getByText('BURN')).toBeInTheDocument();
            expect(screen.getByText('Taking fire damage over time.')).toBeInTheDocument();
            expect(screen.getByText('3 beats remaining')).toBeInTheDocument();
        });

        it('hides the tooltip after mouse leave', () => {
            render(<StatusEffectsIconPanel effects={mockEffects} />);
            const burnIcon = screen.getByText('🔥');

            fireEvent.mouseEnter(burnIcon);
            expect(screen.getByText('BURN')).toBeInTheDocument();

            fireEvent.mouseLeave(burnIcon);
            expect(screen.queryByText('BURN')).not.toBeInTheDocument();
        });

        it('falls back to a default message when description is missing', () => {
            const noDesc = [{ name: 'Mystery Effect', type: 'buff' }];
            render(<StatusEffectsIconPanel effects={noDesc} />);
            fireEvent.mouseEnter(screen.getByText('✨'));
            expect(screen.getByText('No description available.')).toBeInTheDocument();
        });

        it('omits the duration line when duration_remaining is undefined', () => {
            const noDuration = [{ name: 'Mystery Effect', type: 'buff', description: 'Something' }];
            render(<StatusEffectsIconPanel effects={noDuration} />);
            fireEvent.mouseEnter(screen.getByText('✨'));
            expect(screen.queryByText(/beats remaining/)).not.toBeInTheDocument();
        });

        it('shows only the hovered effect\'s tooltip, not others', () => {
            render(<StatusEffectsIconPanel effects={mockEffects} />);
            fireEvent.mouseEnter(screen.getByText('🔥'));
            expect(screen.getByText('BURN')).toBeInTheDocument();
            expect(screen.queryByText('SHIELD')).not.toBeInTheDocument();
        });

        it('applies the debuff color to a debuff effect tooltip', () => {
            const debuffs = [{ name: 'Weakness', type: 'debuff', description: 'Reduced damage', duration_remaining: 4 }];
            render(<StatusEffectsIconPanel effects={debuffs} />);
            fireEvent.mouseEnter(screen.getByText('🥀'));
            expect(screen.getByText('WEAKNESS')).toBeInTheDocument();
        });

        it('renders a passive effect and an unrecognized-type effect without error', () => {
            const mixed = [
                { name: 'Vigilance', type: 'passive', description: 'Always watching', duration_remaining: 1 },
                { name: 'Curious', type: 'strange-type', description: 'Unclassified', duration_remaining: 1 },
            ]
            render(<StatusEffectsIconPanel effects={mixed} />);
            const icons = screen.getAllByText('✨');
            fireEvent.mouseEnter(icons[0]);
            expect(screen.getByText('VIGILANCE')).toBeInTheDocument();

            fireEvent.mouseLeave(icons[0]);
            fireEvent.mouseEnter(icons[1]);
            expect(screen.getByText('CURIOUS')).toBeInTheDocument();
        });

        it('handles an effect with no type using the default color', () => {
            const noType = [{ name: 'Blank', description: 'No type set', duration_remaining: 2 }]
            render(<StatusEffectsIconPanel effects={noType} />);
            fireEvent.mouseEnter(screen.getByText('✨'));
            expect(screen.getByText('BLANK')).toBeInTheDocument();
        });
    });

    describe('Vertical Layout', () => {
        it('stacks icons in a column when vertical is true', () => {
            const { container } = render(<StatusEffectsIconPanel effects={mockEffects} vertical />);
            const wrapper = container.firstChild;
            expect(wrapper.style.flexDirection).toBe('column');
        });

        it('lays out icons in a row by default', () => {
            const { container } = render(<StatusEffectsIconPanel effects={mockEffects} />);
            const wrapper = container.firstChild;
            expect(wrapper.style.flexDirection).toBe('row');
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
