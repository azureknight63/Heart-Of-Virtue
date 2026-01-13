import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import RightPanel from './RightPanel';
import React from 'react';

// Mock child components
vi.mock('./Battlefield', () => ({ default: () => <div data-testid="battlefield">Battlefield</div> }));
vi.mock('./WorldMap', () => ({ default: () => <div data-testid="world-map">World Map</div> }));

describe('RightPanel', () => {
    it('renders WorldMap in exploration mode', () => {
        render(<RightPanel mode="exploration" />);
        expect(screen.getByText('World Map')).toBeDefined();
        expect(screen.getByTestId('world-map')).toBeDefined();
    });

    it('renders Battlefield in combat mode', () => {
        render(<RightPanel mode="combat" />);
        expect(screen.getByText('Battlefield Map')).toBeDefined();
        expect(screen.getByTestId('battlefield')).toBeDefined();
    });
});
