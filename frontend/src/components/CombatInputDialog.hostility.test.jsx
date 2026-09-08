import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CombatInputDialog from './CombatInputDialog';
import { useAudio } from '../context/AudioContext';
import { colors } from '../styles/theme';
import { hexToRgb } from '../test/hexToRgb';

vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn(),
}));

/**
 * Issue #558: measured in the live SELECT TARGET dialog, Gorran (the player's
 * own ally, offered by Advance because it declares `accepts_ally_target`) and
 * a Rock Rumbler were identical on every axis — row background, row border,
 * name colour and name weight. A scripted pick landed on Gorran.
 *
 * The hostility is on the wire as `is_ally`, set for every card by
 * `ApiCombatAdapter._build_target_entry` (src/api/combat_adapter.py) — the
 * ally branch of `_candidate_targets` sets it true, and everything else on the
 * list came out of `player.combat_list`.
 */
describe('CombatInputDialog — friend and foe in the target picker (#558)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAudio.mockReturnValue({ playSFX: vi.fn() });
  });

  const options = [
    { id: 'enemy_1', name: 'Rock Rumbler', distance: 5, is_ally: false, health: { current: 40, max: 40 } },
    { id: 'ally_1', name: 'Gorran', distance: 3, is_ally: true, health: { current: 30, max: 30 } },
  ];

  const renderPicker = (opts = options) => render(
    <CombatInputDialog
      inputType="target_selection"
      options={opts}
      onSelect={vi.fn()}
      moveName="Advance"
      moveCategory="Maneuver"
    />
  );

  const cardFor = (name) => screen.getByText(name).closest('[data-testid="target-card"]');

  it('labels each card with a word, not only a colour', () => {
    renderPicker();
    expect(cardFor('Rock Rumbler')).toHaveTextContent('HOSTILE');
    expect(cardFor('Gorran')).toHaveTextContent('ALLY');
    expect(cardFor('Gorran')).not.toHaveTextContent('HOSTILE');
  });

  it('gives the two cards different borders', () => {
    renderPicker();
    const hostileBorder = cardFor('Rock Rumbler').style.border;
    const allyBorder = cardFor('Gorran').style.border;
    expect(hostileBorder).toContain(hexToRgb(colors.danger));
    expect(allyBorder).toContain(hexToRgb(colors.primary));
    expect(hostileBorder).not.toBe(allyBorder);
  });

  it('marks nothing when the payload says nothing about hostility', () => {
    renderPicker([{ id: 'thing_1', name: 'Something', distance: 5 }]);
    expect(screen.queryByText(/HOSTILE/)).toBeNull();
    expect(screen.queryByText(/\bALLY\b/)).toBeNull();
  });
});
