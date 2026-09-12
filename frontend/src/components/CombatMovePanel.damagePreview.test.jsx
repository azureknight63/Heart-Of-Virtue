import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CombatMovePanel from './CombatMovePanel';
import { useAudio } from '../context/AudioContext';
import { makeAvailableOption, makeTargetOption } from '../test/payloads';

vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn(),
}));

const onMoveClick = vi.fn();
const onClose = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  useAudio.mockReturnValue({ playSFX: vi.fn() });
});

const renderPanel = (moves) => render(
  <CombatMovePanel moves={moves} category="Offensive" onMoveClick={onMoveClick} onClose={onClose} />
);

// #576: the backend has computed and sent `damage_preview` on every target
// card since #555 (ApiCombatAdapter._build_target_entry -- `{min, max,
// lethal}` or null), but `grep -rn "damage_preview" frontend/src` came back
// empty: nothing rendered it. These pin the move card to actually showing it.
describe('CombatMovePanel — damage_preview range on move cards (#576)', () => {
  it('renders the min-max damage range for a targeted move with one viable target', () => {
    const target = makeTargetOption({ damage_preview: { min: 12, max: 18, lethal: false } });
    const move = makeAvailableOption({
      name: 'Attack',
      viable_targets: [target],
      target_previews: [target],
    });

    renderPanel([move]);

    expect(screen.getByText('12-18 dmg')).toBeInTheDocument();
  });

  it('renders fine, with no range shown, when the move has no damage_preview at all', () => {
    const move = makeAvailableOption({
      name: 'Rally Cry',
      description: 'Bolster your resolve.',
      targeted: false,
      viable_targets: [],
      target_previews: [],
      affected_preview: [],
    });

    renderPanel([move]);

    expect(screen.getByText('Rally Cry')).toBeInTheDocument();
    expect(screen.queryByText(/dmg/)).toBeNull();
  });

  it('shows no range when the move can hit more than one target and which one is ambiguous', () => {
    const move = makeAvailableOption({
      name: 'Cleave',
      viable_targets: [
        makeTargetOption({ id: 'enemy_1' }),
        makeTargetOption({ id: 'enemy_2' }),
      ],
      target_previews: [
        makeTargetOption({ id: 'enemy_1' }),
        makeTargetOption({ id: 'enemy_2' }),
      ],
    });

    renderPanel([move]);

    expect(screen.queryByText(/dmg/)).toBeNull();
  });

  it('folds an area move\'s affected_preview into one range', () => {
    const move = makeAvailableOption({
      name: 'Spin Slash',
      targeted: false,
      viable_targets: [],
      target_previews: [],
      affected_preview: [
        makeTargetOption({ id: 'enemy_1', damage_preview: { min: 5, max: 10, lethal: false } }),
        makeTargetOption({ id: 'enemy_2', damage_preview: { min: 8, max: 14, lethal: false } }),
      ],
    });

    renderPanel([move]);

    expect(screen.getByText('5-14 dmg')).toBeInTheDocument();
  });

  it('marks a lethal preview with a text label rather than color alone', () => {
    const lethalTarget = makeTargetOption({
      health: { current: 10, max: 10 },
      damage_preview: { min: 12, max: 18 },
    });
    const move = makeAvailableOption({
      name: 'Finishing Blow',
      viable_targets: [lethalTarget],
      target_previews: [lethalTarget],
    });

    renderPanel([move]);

    // The label carries the word itself -- a screen reader or a colorblind
    // player must not need the (also-present) color cue to see this.
    expect(screen.getByText(/LETHAL/)).toBeInTheDocument();
  });

  it('does not mark a non-lethal preview as lethal', () => {
    const target = makeTargetOption({
      health: { current: 999, max: 999 },
      damage_preview: { min: 12, max: 18 },
    });
    const move = makeAvailableOption({
      name: 'Attack',
      viable_targets: [target],
      target_previews: [target],
    });

    renderPanel([move]);

    expect(screen.getByText('12-18 dmg')).toBeInTheDocument();
    expect(screen.queryByText(/LETHAL/)).toBeNull();
  });
});
