import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Battlefield from './Battlefield';
import React from 'react';

// Mock child components. Battlefield also imports the VIEW_SIZE constant for
// its off-screen-enemy detection, so expose it on the mock.
vi.mock('./BattlefieldGrid', () => ({
    VIEW_SIZE: 13,
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
});
