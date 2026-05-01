import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import RightPanel from './RightPanel';
import React from 'react';

// Mock child components
vi.mock('./Battlefield', () => ({ default: () => <div data-testid="battlefield">Battlefield</div> }));
vi.mock('./WorldMap', () => ({ default: () => <div data-testid="world-map">World Map</div> }));
vi.mock('./CollapsibleRoomDescription', () => ({
  default: ({ location, defaultOpen }) => (
    <div data-testid="collapsible-desc" data-default-open={String(defaultOpen)}>
      {location.name}
    </div>
  )
}));

const loc = { name: 'Dark Grotto', description: 'Damp stone.' }

describe('RightPanel', () => {
    it('renders WorldMap in exploration mode', () => {
        render(<RightPanel mode="exploration" />);
        expect(screen.getAllByText('World Map').length).toBeGreaterThan(0);
        expect(screen.getByTestId('world-map')).toBeDefined();
    });

    it('renders Battlefield in combat mode', () => {
        render(<RightPanel mode="combat" />);
        expect(screen.getByText('Battlefield Map')).toBeDefined();
        expect(screen.getByTestId('battlefield')).toBeDefined();
    });

    it('renders CollapsibleRoomDescription when showDescription=true in exploration', () => {
        render(<RightPanel mode="exploration" showDescription={true} location={loc} />);
        expect(screen.getByTestId('collapsible-desc')).toBeDefined();
        expect(screen.getByText('Dark Grotto')).toBeDefined();
    });

    it('passes defaultOpen=false to CollapsibleRoomDescription', () => {
        render(<RightPanel mode="exploration" showDescription={true} location={loc} />);
        expect(screen.getByTestId('collapsible-desc').getAttribute('data-default-open')).toBe('false');
    });

    it('does not render CollapsibleRoomDescription when showDescription=false', () => {
        render(<RightPanel mode="exploration" showDescription={false} location={loc} />);
        expect(screen.queryByTestId('collapsible-desc')).toBeNull();
    });

    it('does not render CollapsibleRoomDescription in combat mode even with showDescription=true', () => {
        render(<RightPanel mode="combat" showDescription={true} location={loc} />);
        expect(screen.queryByTestId('collapsible-desc')).toBeNull();
    });

    it('does not render CollapsibleRoomDescription when location is undefined', () => {
        render(<RightPanel mode="exploration" showDescription={true} />);
        expect(screen.queryByTestId('collapsible-desc')).toBeNull();
    });
});
