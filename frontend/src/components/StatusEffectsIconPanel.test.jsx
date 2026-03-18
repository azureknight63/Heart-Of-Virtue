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
});
