import { render, screen, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CombatInputDialog from './CombatInputDialog';
import { enemyId, makeTargetOption } from '../test/payloads';
import { useAudio } from '../context/AudioContext';

vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn(),
}));

/**
 * Issue #688: with the Shortsword drawn, Attack's `viable_targets` carried
 * `damage_preview {min: 0, max: 0}` for the Stone Creature and a lethal 52-78
 * for the Slime beside it, and the SELECT TARGET card showed neither -- only
 * HP, accuracy and STRIKE. The numbers come from the engine's
 * `Move.preview_damage` via `ApiCombatAdapter._build_target_entry`; the card
 * only has to render them, and never by colour alone.
 */
describe('CombatInputDialog — damage preview on the target card (#688)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAudio.mockReturnValue({ playSFX: vi.fn() });
  });

  const renderCards = (options) =>
    render(
      <CombatInputDialog
        inputType="target_selection"
        options={options}
        onSelect={vi.fn()}
        onCancel={vi.fn()}
      />
    );

  const cardFor = (name) =>
    screen.getAllByTestId('target-card').find((c) => within(c).queryByText(name));

  it('renders the range, "no damage" for a zero preview, and a lethal marker', () => {
    renderCards([
      makeTargetOption({
        id: enemyId(1), name: 'Stone Creature', distance: 3,
        health: { current: 96, max: 96 },
        damage_preview: { min: 0, max: 0, lethal: false },
      }),
      makeTargetOption({
        id: enemyId(2), name: 'Slime', distance: 3,
        health: { current: 40, max: 40 },
        damage_preview: { min: 52, max: 78, lethal: true },
      }),
    ]);

    const stone = cardFor('Stone Creature');
    expect(within(stone).getByText(/no damage/i)).toBeDefined();
    expect(within(stone).queryByText(/lethal/i)).toBeNull();

    const slime = cardFor('Slime');
    expect(within(slime).getByText(/52–78 dmg/)).toBeDefined();
    // A word, not a colour: pillar 5.
    expect(within(slime).getByText(/lethal/i)).toBeDefined();
    expect(within(slime).queryByText(/no damage/i)).toBeNull();
  });

  it('renders nothing for a target with no preview (out of reach, or a support move)', () => {
    renderCards([
      makeTargetOption({ id: enemyId(1), name: 'Far Bat', distance: 40 }),
    ]);
    const card = cardFor('Far Bat');
    expect(within(card).queryByText(/dmg|no damage/i)).toBeNull();
  });
});
