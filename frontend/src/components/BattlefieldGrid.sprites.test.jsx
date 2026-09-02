import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BattlefieldGrid from './BattlefieldGrid';
import { makeBattleState, makeCombatant, makeEnemy, makeSpriteManifest, makeTerrain } from '../test/payloads';
import { useSpriteManifest } from '../hooks/useSpriteManifest';

vi.mock('../context/AudioContext', () => ({ useAudio: () => ({ playSFX: vi.fn() }) }));
vi.mock('../hooks/useSpriteManifest', () => ({ useSpriteManifest: vi.fn() }));

const combat = makeBattleState({
  player: makeCombatant({ position: { x: 4, y: 4, facing: 'E' }, current_move: { name: 'Advance', current_stage: 1, category: 'Maneuver' } }),
  enemies: [
    makeEnemy({ id: 'enemy_1', name: 'Slime', sprite_key: 'slime', position: { x: 7, y: 4, facing: 'W' } }),
    makeEnemy({ id: 'enemy_2', name: 'King Slime', sprite_key: 'kingslime', position: { x: 2, y: 2, facing: 'S' } }),
  ],
});

describe('BattlefieldGrid sprites', () => {
  beforeEach(() => useSpriteManifest.mockReturnValue(null));

  it('draws glyph tokens when no manifest has loaded', () => {
    render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);
    expect(screen.queryAllByTestId('sprite-token')).toHaveLength(0);
    expect(screen.getByText('J')).toBeDefined();
  });

  it('draws a sprite for every combatant with a sheet set and a glyph for the rest', () => {
    useSpriteManifest.mockReturnValue(makeSpriteManifest());
    render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} />);
    const tokens = screen.getAllByTestId('sprite-token');
    expect(tokens).toHaveLength(2);
    // Jean is advancing and facing east: walk clip, west row mirrored.
    const jean = tokens.find((t) => t.style.backgroundImage.includes('sprites/jean/'));
    expect(jean.dataset.clip).toBe('walk');
    expect(jean.dataset.mirror).toBe('1');
    expect(screen.queryByText('J')).toBeNull();
    // The King Slime has no sheets: still an initial.
    expect(screen.getByText('K')).toBeDefined();
  });

  it('paints delivered terrain tiles, floor included, instead of procedural fills', () => {
    useSpriteManifest.mockReturnValue(makeSpriteManifest());
    render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} terrain={makeTerrain()} mapSize={9} />);
    const layer = screen.getByTestId('terrain-layer');
    const floor = layer.querySelectorAll('[data-terrain="open"]');
    expect(floor.length).toBe(81 - 16);
    const wall = layer.querySelector('[data-terrain="wall"]');
    expect(wall.dataset.tiled).toBe('1');
    expect(wall.style.backgroundImage).toContain('terrain/verdette_caverns/crystal_wall.png');
    expect(wall.textContent).toBe('');
  });

  it('keeps procedural terrain when the manifest has no tileset for the region', () => {
    useSpriteManifest.mockReturnValue(makeSpriteManifest({ terrain: {} }));
    render(<BattlefieldGrid combat={combat} tab="overview" zoom={1} terrain={makeTerrain()} mapSize={9} />);
    const layer = screen.getByTestId('terrain-layer');
    expect(layer.querySelectorAll('[data-terrain="open"]').length).toBe(0);
    expect(layer.querySelector('[data-terrain="boulder"]').dataset.tiled).toBeUndefined();
  });
});
