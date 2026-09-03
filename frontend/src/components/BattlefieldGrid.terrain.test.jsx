import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import BattlefieldGrid from './BattlefieldGrid';
import { makeBattleState, makeCombatant, makeEnemy, makeTerrain, makeNineByNineFight, TERRAIN_FIXTURE_FEATURES } from '../test/payloads';

vi.mock('../context/AudioContext', () => ({
  useAudio: () => ({ playSFX: vi.fn() }),
}));

const combat = makeNineByNineFight();
const renderGrid = (props = {}) => render(
  <BattlefieldGrid combat={combat} tab="overview" zoom={1} mapSize={9} {...props} />
);
const cells = (kind) => [
  ...screen.getByTestId('terrain-layer').querySelectorAll(kind ? `[data-terrain="${kind}"]` : '[data-terrain]'),
];

describe('BattlefieldGrid terrain layer', () => {
  it('renders nothing terrain-related in a flat fight', () => {
    renderGrid({ terrain: null, mapSize: undefined });
    expect(screen.queryByTestId('terrain-layer')).toBeNull();
    expect(screen.queryByTestId('terrain-legend')).toBeNull();
  });

  it('paints one cell per feature in the viewport, decoded from the wire rows', () => {
    renderGrid({ terrain: makeTerrain() });
    const layer = screen.getByTestId('terrain-layer');
    // Only feature cells emit a node: open ground and off-map cells do not.
    expect(cells().length).toBe(TERRAIN_FIXTURE_FEATURES);
    expect(cells('boulder').length).toBe(2);
    expect(cells('wall').length).toBe(4);
    expect(cells('shelf').length).toBe(4);
    expect(layer.children.length).toBe(TERRAIN_FIXTURE_FEATURES);
    // World y grows north; screen row 0 is the top of the 13-cell viewport
    // (topY = 4 + 6 = 10, leftX = -2). rows[0][4] (a boulder at world 4,0)
    // lands on 0-based lattice row 10, column 6; CSS grid lines are 1-based.
    const at = (row, col) => [String(row + 1), String(col + 1)];
    const placements = cells('boulder').map((el) => [el.style.gridRowStart, el.style.gridColumnStart]);
    expect(placements).toContainEqual(at(10, 6));   // world (4,0)
    expect(placements).toContainEqual(at(4, 10));   // world (8,6)
  });

  it('names feature cells with the server legend and carries the region variant', () => {
    renderGrid({ terrain: makeTerrain() });
    const [boulder] = cells('boulder');
    expect(boulder.getAttribute('title')).toBe('Boulder');
    expect(boulder.getAttribute('data-variant')).toBe('crystal_cluster');
    const [shelf] = cells('shelf');
    expect(shelf.getAttribute('title')).toBe('High ground');
    expect(shelf.style.boxShadow).not.toBe('none');
  });

  it('shows a legend with the region and only the kinds present', () => {
    renderGrid({ terrain: makeTerrain() });
    const legend = screen.getByTestId('terrain-legend');
    expect(legend.textContent).toContain('Verdette Caverns');
    expect(legend.textContent).toContain('Boulder (blocks, cover -20)');
    expect(legend.textContent).toContain('Wall (blocks, no line of sight)');
    expect(legend.textContent).toContain('High ground (+10 to hit)');
    expect(legend.textContent).toContain('Hazard (slow, hurts)');
    expect(legend.textContent).not.toContain('Drop');
  });

  it('tolerates a malformed payload by drawing no terrain', () => {
    renderGrid({ terrain: { rows: 'nope' } });
    expect(screen.queryByTestId('terrain-layer')).toBeNull();
    expect(screen.queryByTestId('terrain-legend')).toBeNull();
  });

  it('mounts an empty layer and no legend for an all-open grid', () => {
    renderGrid({ terrain: makeTerrain({ rows: Array(9).fill('ooooooooo'), elevation: Array(9).fill('000000000') }) });
    expect(screen.getByTestId('terrain-layer').children.length).toBe(0);
    expect(screen.queryByTestId('terrain-legend')).toBeNull();
  });

  it('ignores codes and kinds the engine never emits', () => {
    const odd = makeTerrain({
      rows: ['xzooooooo', ...Array(8).fill('ooooooooo')],
      codes: { o: 'open', z: 'lava' },
    });
    renderGrid({ terrain: odd });
    expect(cells().length).toBe(0);
    expect(screen.queryByTestId('terrain-legend')).toBeNull();
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
    renderGrid({ combat: standing, terrain: makeTerrain() });
    fireEvent.mouseEnter(screen.getByText('J'));
    expect(screen.getByTestId('tooltip-terrain').textContent).toBe('on High ground');
    fireEvent.mouseLeave(screen.getByText('J'));
    fireEvent.mouseEnter(screen.getByText('S'));
    // The enemy's hover card is open, and open ground says nothing on it.
    expect(screen.getByText('Idle')).toBeDefined();
    expect(screen.queryByTestId('tooltip-terrain')).toBeNull();
  });
});
