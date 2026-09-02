import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import BattlefieldGrid from './BattlefieldGrid';
import { makeBattleState, makeCombatant, makeEnemy, makeTerrain } from '../test/payloads';

vi.mock('../context/AudioContext', () => ({
  useAudio: () => ({ playSFX: vi.fn() }),
}));

// Jean at (4,4) so the 13-cell follow viewport (leftX = -2 .. 10) covers the
// whole 9x9 fixture grid.
const combat = makeBattleState({
  player: makeCombatant({ position: { x: 4, y: 4, facing: 'N' } }),
  enemies: [makeEnemy({ position: { x: 7, y: 4, facing: 'W' } })],
});

describe('BattlefieldGrid terrain layer', () => {
  it('renders nothing terrain-related in a flat fight', () => {
    render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} terrain={null} />);
    expect(screen.queryByTestId('terrain-layer')).toBeNull();
    expect(screen.queryByTestId('terrain-legend')).toBeNull();
  });

  it('paints one cell per feature in the viewport, decoded from the wire rows', () => {
    const terrain = makeTerrain();
    render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} terrain={terrain} mapSize={9} />);
    const layer = screen.getByTestId('terrain-layer');
    // Fixture: 2 boulders, 4 walls, 4 shelf, 3 rough, 3 hazard = 16 features.
    expect(layer.querySelectorAll('[data-terrain]').length).toBe(16);
    expect(layer.querySelectorAll('[data-terrain="boulder"]').length).toBe(2);
    expect(layer.querySelectorAll('[data-terrain="wall"]').length).toBe(4);
    expect(layer.querySelectorAll('[data-terrain="shelf"]').length).toBe(4);
    // The lattice still has its 13x13 placeholders underneath.
    expect(layer.children.length).toBe(169);
  });

  it('names feature cells with the server legend and carries the region variant', () => {
    const terrain = makeTerrain();
    render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} terrain={terrain} mapSize={9} />);
    const boulder = screen.getByTestId('terrain-layer').querySelector('[data-terrain="boulder"]');
    expect(boulder.getAttribute('title')).toBe('Boulder');
    expect(boulder.getAttribute('data-variant')).toBe('crystal_cluster');
    const shelf = screen.getByTestId('terrain-layer').querySelector('[data-terrain="shelf"]');
    expect(shelf.getAttribute('title')).toBe('High ground (+1)');
  });

  it('shows a legend with the region and only the kinds present', () => {
    render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} terrain={makeTerrain()} mapSize={9} />);
    const legend = screen.getByTestId('terrain-legend');
    expect(legend.textContent).toContain('Verdette Caverns');
    expect(legend.textContent).toContain('Boulder (blocks, cover -20)');
    expect(legend.textContent).toContain('High ground (high +10)');
    expect(legend.textContent).toContain('Hazard (slow)');
    expect(legend.textContent).not.toContain('Drop');
  });

  it('tolerates a malformed payload by drawing no terrain', () => {
    render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} terrain={{ rows: 'nope' }} />);
    expect(screen.queryByTestId('terrain-layer')).toBeNull();
  });

  it('tells the hover card what the token stands on', () => {
    const standing = makeBattleState({
      player: makeCombatant({
        position: { x: 4, y: 4, facing: 'N' },
        terrain: { kind: 'shelf', variant: 'rock_shelf', elevation: 1, label: 'High ground' },
      }),
      enemies: [makeEnemy({
        position: { x: 7, y: 4, facing: 'W' },
        terrain: { kind: 'open', variant: 'cavern_floor', elevation: 0, label: 'Open ground' },
      })],
    });
    render(<BattlefieldGrid combat={standing} tab="overview" zoom={1} terrain={makeTerrain()} mapSize={9} />);
    fireEvent.mouseEnter(screen.getByText('J'));
    expect(screen.getByTestId('tooltip-terrain').textContent).toBe('on High ground (+1 high)');
    fireEvent.mouseLeave(screen.getByText('J'));
    fireEvent.mouseEnter(screen.getByText('S'));
    // Open ground says nothing.
    expect(screen.queryByTestId('tooltip-terrain')).toBeNull();
  });
});
