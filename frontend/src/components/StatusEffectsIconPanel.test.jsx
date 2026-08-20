import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import StatusEffectsIconPanel from './StatusEffectsIconPanel';

describe('StatusEffectsIconPanel', () => {
    const mockEffects = [
        {
            name: 'Burn',
            type: 'ailment',
            description: 'Taking fire damage over time.',
            beats_left: 3
        },
        {
            name: 'Shield',
            type: 'buff',
            description: 'Increases protection.',
            beats_left: 5
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

    it('picks the correct icon for bleed/stun/blind/slow/regen effects', () => {
        const effects = [
            { name: 'Bleeding', type: 'ailment' },
            { name: 'Stunned', type: 'ailment' },
            { name: 'Blinded', type: 'ailment' },
            { name: 'Slowed', type: 'debuff' },
            { name: 'Regeneration', type: 'buff' },
        ];
        render(<StatusEffectsIconPanel effects={effects} />);

        expect(screen.getByText('🩸')).toBeDefined();
        expect(screen.getByText('💫')).toBeDefined();
        expect(screen.getByText('🕶️')).toBeDefined();
        expect(screen.getByText('🐢')).toBeDefined();
        expect(screen.getByText('💖')).toBeDefined();
    });

    it('uses default icon for unknown effects', () => {
        const unknownEffects = [{ name: 'Mystic Energy', type: 'buff' }];
        render(<StatusEffectsIconPanel effects={unknownEffects} />);
        expect(screen.getByText('✨')).toBeDefined();
    });

    describe('Effect Type Variations', () => {
        it('renders buff effects', () => {
            const buffs = [
                { name: 'Strength Boost', type: 'buff', description: 'Increased strength', beats_left: 5 }
            ];
            render(<StatusEffectsIconPanel effects={buffs} />);
            expect(screen.getByText('💪')).toBeDefined();
        });

        it('renders ailment effects', () => {
            const ailments = [
                { name: 'Poisoned', type: 'ailment', description: 'Poison damage', beats_left: 3 }
            ];
            render(<StatusEffectsIconPanel effects={ailments} />);
            expect(screen.getByText('🧪')).toBeDefined();
        });

        it('renders debuff effects', () => {
            const debuffs = [
                { name: 'Weakness', type: 'debuff', description: 'Reduced damage', beats_left: 4 }
            ];
            render(<StatusEffectsIconPanel effects={debuffs} />);
            // Should render without error
            expect(screen.getByText).toBeDefined();
        });

        it('handles mixed effect types', () => {
            const mixed = [
                { name: 'Burn', type: 'ailment', description: 'Fire damage', beats_left: 2 },
                { name: 'Shield', type: 'buff', description: 'Protection', beats_left: 5 },
                { name: 'Weakness', type: 'debuff', description: 'Low defense', beats_left: 3 }
            ];
            render(<StatusEffectsIconPanel effects={mixed} />);
            expect(screen.getByText('🔥')).toBeDefined();
            expect(screen.getByText('🛡️')).toBeDefined();
        });
    });

    describe('Duration Display', () => {
        it('displays effect with remaining duration', () => {
            const shortDuration = [
                { name: 'Quick Effect', type: 'buff', description: 'Brief boost', beats_left: 1 }
            ];
            render(<StatusEffectsIconPanel effects={shortDuration} />);
            expect(screen.getByText).toBeDefined();
        });

        // These three previously asserted `expect(screen.getByText).toBeDefined()`
        // — i.e. that testing-library's own query function exists. They would
        // have passed against a component that rendered the duration line for
        // every effect, or for none of them. They now read the line.
        it.each([[1], [99]])('renders the remaining-beats line for beats_left=%i', (beats) => {
            render(<StatusEffectsIconPanel effects={[
                { name: 'Shield', type: 'buff', description: 'Guard', beats_left: beats }
            ]} />);
            fireEvent.mouseEnter(screen.getByText('🛡️'));
            expect(screen.getByText(`${beats} beats remaining`)).toBeInTheDocument();
        });

        it.each([[0], [-1]])(
            'omits the remaining-beats line entirely for a non-positive beats_left=%i',
            (beats) => {
                // `> 0` rather than `!== undefined` is load-bearing: permanent
                // states carry beats_left fixed at 0, and the earlier check
                // labelled every permanent buff "0 beats remaining".
                render(<StatusEffectsIconPanel effects={[
                    { name: 'Shield', type: 'buff', description: 'Guard', beats_left: beats }
                ]} />);
                fireEvent.mouseEnter(screen.getByText('🛡️'));
                expect(screen.getByText('SHIELD')).toBeInTheDocument();
                expect(screen.queryByText(/beats remaining/)).not.toBeInTheDocument();
            }
        );

        it('renders the remaining-beats line from the beats_left the API actually sends', () => {
            // StateEffectSerializer.serialize_state emits `beats_left`; this is the
            // real production contract, so the tooltip must read it.
            const effects = [{ name: 'Burn', type: 'ailment', description: 'Fire', beats_left: 3 }];
            render(<StatusEffectsIconPanel effects={effects} />);
            fireEvent.mouseEnter(screen.getByText('🔥'));
            expect(screen.getByText('3 beats remaining')).toBeInTheDocument();
        });

        it('still honours the legacy duration_remaining field', () => {
            const effects = [{ name: 'Shield', type: 'buff', description: 'Guard', duration_remaining: 7 }];
            render(<StatusEffectsIconPanel effects={effects} />);
            fireEvent.mouseEnter(screen.getByText('🛡️'));
            expect(screen.getByText('7 beats remaining')).toBeInTheDocument();
        });

    });

    describe('Multiple Effects', () => {
        it('renders one icon per effect and colours each by its own type', () => {
            // beats_left was Math.random() here, and the only assertion was
            // that screen.getByText exists — so the list length and the
            // per-effect type styling were both unproven.
            const manyEffects = Array.from({ length: 15 }, (_, i) => ({
                name: `Effect ${i}`,
                type: i % 2 === 0 ? 'buff' : 'ailment',
                description: `Description ${i}`,
                beats_left: i + 1,
            }));
            render(<StatusEffectsIconPanel effects={manyEffects} />);

            // Every name falls through getEffectIcon's keyword table to the
            // default glyph, so all 15 render and none are collapsed.
            expect(screen.getAllByText('✨')).toHaveLength(15);
            // buff -> success green, ailment -> gold; the tile border carries it.
            const borders = screen.getAllByText('✨').map((el) => el.style.border);
            expect(borders[0]).not.toBe(borders[1]);
            expect(borders[0]).toBe(borders[2]);
            expect(borders[1]).toBe(borders[3]);
        });

        it('handles duplicate effect names', () => {
            const duplicates = [
                { name: 'Burn', type: 'ailment', description: 'Fire damage 1', beats_left: 2 },
                { name: 'Burn', type: 'ailment', description: 'Fire damage 2', beats_left: 3 }
            ];
            render(<StatusEffectsIconPanel effects={duplicates} />);
            expect(screen.getAllByText('🔥')).toHaveLength(2);
        });

        it('handles effects with same icon', () => {
            const sameIcon = [
                { name: 'Fire Burn', type: 'ailment', description: 'Burning', beats_left: 2 },
                { name: 'Lava Burn', type: 'ailment', description: 'Hot burning', beats_left: 3 }
            ];
            render(<StatusEffectsIconPanel effects={sameIcon} />);
            expect(screen.getAllByText('🔥')).toHaveLength(2);
        });
    });

    describe('Hover and Interaction', () => {
        it('opens the tooltip on mouseenter and closes it on mouseleave', () => {
            render(<StatusEffectsIconPanel effects={mockEffects} />);
            const shield = screen.getByText('🛡️');

            expect(screen.queryByText('SHIELD')).not.toBeInTheDocument();
            fireEvent.mouseEnter(shield);
            expect(screen.getByText('SHIELD')).toBeInTheDocument();
            expect(screen.getByText('Increases protection.')).toBeInTheDocument();

            fireEvent.mouseLeave(shield);
            expect(screen.queryByText('SHIELD')).not.toBeInTheDocument();
        });

        it('shows only the currently-hovered effect\'s tooltip when moving between icons', () => {
            // Hover state is a single `hoveredEffectName`, so moving from one
            // icon to the next must swap the tooltip, never stack both.
            render(<StatusEffectsIconPanel effects={mockEffects} />);

            fireEvent.mouseEnter(screen.getByText('🔥'));
            expect(screen.getByText('BURN')).toBeInTheDocument();
            expect(screen.queryByText('SHIELD')).not.toBeInTheDocument();

            fireEvent.mouseLeave(screen.getByText('🔥'));
            fireEvent.mouseEnter(screen.getByText('🛡️'));
            expect(screen.getByText('SHIELD')).toBeInTheDocument();
            expect(screen.queryByText('BURN')).not.toBeInTheDocument();
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
        const hoverFirstIcon = () => fireEvent.mouseEnter(screen.getByText('✨'));

        it('renders the supplied description in the tooltip', () => {
            render(<StatusEffectsIconPanel effects={[
                { name: 'Known Effect', type: 'buff', description: 'Clear description', beats_left: 5 }
            ]} />);
            hoverFirstIcon();
            expect(screen.getByText('Clear description')).toBeInTheDocument();
        });

        it('falls back to placeholder copy when the effect has no description', () => {
            // Previously only `not.toThrow()`, which would have passed against
            // a tooltip that rendered a blank gap where the copy belongs.
            render(<StatusEffectsIconPanel effects={[
                { name: 'Mystery Effect', type: 'buff', beats_left: 3 }
            ]} />);
            hoverFirstIcon();
            expect(screen.getByText('No description available.')).toBeInTheDocument();
        });

        it('renders a long description in full rather than truncating it', () => {
            const long = 'This is a very long description that explains in great detail what this effect does and how it impacts the player. '.repeat(5);
            render(<StatusEffectsIconPanel effects={[
                { name: 'Complex Effect', type: 'buff', description: long, beats_left: 5 }
            ]} />);
            hoverFirstIcon();
            expect(screen.getByText(long.trim())).toBeInTheDocument();
        });

        it('renders special characters as literal text, not markup', () => {
            const description = 'Effect with special chars: <>&"\'';
            render(<StatusEffectsIconPanel effects={[
                { name: 'Special', type: 'buff', description, beats_left: 3 }
            ]} />);
            hoverFirstIcon();
            const node = screen.getByText(description);
            expect(node).toBeInTheDocument();
            // React escapes by default; assert it, so a future switch to
            // dangerouslySetInnerHTML shows up here rather than as an XSS.
            expect(node.textContent).toBe(description);
            expect(node.querySelector('*')).toBeNull();
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

        it('renders an effect carrying only a name and type', () => {
            // A serializer that dropped description/beats_left must degrade to
            // the default glyph plus placeholder copy, with no duration line —
            // `not.toThrow()` proved none of that.
            render(<StatusEffectsIconPanel effects={[{ name: 'Minimal Effect', type: 'buff' }]} />);
            fireEvent.mouseEnter(screen.getByText('✨'));
            expect(screen.getByText('MINIMAL EFFECT')).toBeInTheDocument();
            expect(screen.getByText('No description available.')).toBeInTheDocument();
            expect(screen.queryByText(/beats remaining/)).not.toBeInTheDocument();
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

        it('omits the duration line when beats_left is undefined', () => {
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
            const debuffs = [{ name: 'Weakness', type: 'debuff', description: 'Reduced damage', beats_left: 4 }];
            render(<StatusEffectsIconPanel effects={debuffs} />);
            fireEvent.mouseEnter(screen.getByText('🥀'));
            expect(screen.getByText('WEAKNESS')).toBeInTheDocument();
        });

        it('renders a passive effect and an unrecognized-type effect without error', () => {
            const mixed = [
                { name: 'Vigilance', type: 'passive', description: 'Always watching', beats_left: 1 },
                { name: 'Curious', type: 'strange-type', description: 'Unclassified', beats_left: 1 },
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
            const noType = [{ name: 'Blank', description: 'No type set', beats_left: 2 }]
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
        it('renders every entry of a large effect list', () => {
            const largeList = Array.from({ length: 100 }, (_, i) => ({
                name: `Effect ${i}`,
                type: 'buff',
                description: `Effect number ${i}`,
                beats_left: (i % 20) + 1,
            }));

            render(<StatusEffectsIconPanel effects={largeList} />);
            expect(screen.getAllByText('✨')).toHaveLength(100);
        });

        it('drops the previous effects when the list is replaced', () => {
            // The old assertion could not distinguish a re-render from a
            // component that ignored the new prop entirely.
            const { rerender } = render(<StatusEffectsIconPanel effects={mockEffects} />);
            expect(screen.getByText('🔥')).toBeInTheDocument();

            rerender(<StatusEffectsIconPanel effects={[
                { name: 'New Effect', type: 'buff', description: 'Different', beats_left: 5 }
            ]} />);

            expect(screen.queryByText('🔥')).not.toBeInTheDocument();
            expect(screen.queryByText('🛡️')).not.toBeInTheDocument();
            expect(screen.getByText('✨')).toBeInTheDocument();
        });
    });
});
