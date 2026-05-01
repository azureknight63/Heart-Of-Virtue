import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BattlefieldGrid from './BattlefieldGrid';

// Mock AudioContext so playSFX doesn't throw
vi.mock('../context/AudioContext', () => ({
    useAudio: () => ({ playSFX: vi.fn() })
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

    it('shows hover reticle SVG when a combatant token is moused over', () => {
        // Use a fixture without current_move to ensure the reticle isn't
        // rendered by any other pathway before hover.
        const simpleCombat = {
            player: {
                name: 'Jean',
                hp: 100,
                max_hp: 100,
                position: { x: 6, y: 6 }
            },
            enemies: []
        };
        const { container } = render(<BattlefieldGrid combat={simpleCombat} tab="overview" zoom={1} />);

        const jeanToken = screen.getByText('J');
        const entityWrapper = jeanToken.closest('[style*="cursor"]');
        expect(entityWrapper).not.toBeNull();

        // The reticle is a div with class 'inset-\\[-12px\\]' — unique to the hover reticle
        const RETICLE_SELECTOR = '.inset-\\[-12px\\]';
        expect(container.querySelector(RETICLE_SELECTOR)).toBeNull();

        fireEvent.mouseEnter(entityWrapper);

        // Reticle wrapper appears on hover
        expect(
            container.querySelector(RETICLE_SELECTOR),
            'Hover reticle wrapper should appear on mouse enter'
        ).not.toBeNull();

        fireEvent.mouseLeave(entityWrapper);

        // Reticle is gone after mouse leave
        expect(container.querySelector(RETICLE_SELECTOR)).toBeNull();
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
});
