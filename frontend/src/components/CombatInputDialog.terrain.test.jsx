import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CombatInputDialog from './CombatInputDialog';
import { makeTargetOption, makeTargetTerrain } from '../test/payloads';
import { colors } from '../styles/theme';
import { hexToRgb } from '../test/mockHelpers';

vi.mock('../context/AudioContext', () => ({ useAudio: () => ({ playSFX: vi.fn() }) }));

describe('CombatInputDialog terrain labels', () => {

  const renderTargets = (options) => render(
    <CombatInputDialog inputType="target_selection" options={options} onSelect={vi.fn()} onCancel={vi.fn()} />
  );

  it('shows the engine labels for cover and elevation, toned by the net modifier', () => {
    renderTargets([
      makeTargetOption({ id: 'a', name: 'Slime', terrain: makeTargetTerrain() }),
      makeTargetOption({
        id: 'b', name: 'Bat',
        terrain: makeTargetTerrain({ cover: 0, cover_kind: null, elevation: 1, hit_modifier: 10, damage_multiplier: 1.15, labels: ['High ground +10'] }),
      }),
    ]);
    const blocks = screen.getAllByTestId('target-terrain');
    expect(blocks).toHaveLength(2);
    expect(blocks[0].textContent).toBe('Boulder cover -20');
    expect(blocks[0].style.color).toBe(hexToRgb(colors.danger));
    expect(blocks[1].textContent).toBe('High ground +10');
    expect(blocks[1].style.color).toBe(hexToRgb(colors.primary));
  });

  it('renders no terrain row when the block is null or empty', () => {
    renderTargets([
      makeTargetOption({ id: 'a', name: 'Slime', terrain: null }),
      makeTargetOption({ id: 'b', name: 'Bat', terrain: makeTargetTerrain({ labels: [], hit_modifier: 0, cover: 0 }) }),
    ]);
    expect(screen.queryByTestId('target-terrain')).toBeNull();
  });
});
