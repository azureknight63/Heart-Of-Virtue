import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CombatMovePanel from './CombatMovePanel';
import { useAudio } from '../context/AudioContext';
import {
  makeAvailableOption,
  makeTargetOption,
  NOT_ENOUGH_FATIGUE_REASON,
  TOO_FAR_REASON,
} from '../test/payloads';

vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn(),
}));

const onMoveClick = vi.fn();
const onClose = vi.fn();
const playSFX = vi.fn();

// Both describes render the real panel, which reads playSFX from useAudio.
beforeEach(() => {
  vi.clearAllMocks();
  useAudio.mockReturnValue({ playSFX });
});

const renderPanel = (moves) => render(
  <CombatMovePanel moves={moves} category="Offensive" onMoveClick={onMoveClick} onClose={onClose} />
);

const card = (name) => screen.getByText(name).closest('button');

// GlossaryText splits the reason across a span per glossary term, so getByText
// cannot see the whole sentence. The reason element is the one the button's
// aria-describedby points at, and its textContent is the sentence.
const reasonFor = (name) => {
  const id = card(name).getAttribute('aria-describedby');
  return id ? document.getElementById(id) : null;
};

describe('CombatMovePanel — targeted moves with nothing in reach (#554)', () => {
  // The live payload from the reproduction: the engine advertises Attack as
  // available (its viable() only asks whether SOME enemy is in the move's
  // band) while the adapter's range-filtered allow-list is empty. The server
  // then refuses the very move it offered — "No valid targets available for
  // this move" — so the click spends nothing and advances no beat. The name,
  // `targeted` and the empty list are the case under test, so they are
  // spelled out rather than inherited from the builder's defaults. So is the
  // preview list: beside an empty allow-list, every candidate the adapter
  // previews is out of reach — `in_range: false`, a shortfall, no damage
  // preview and no hit chance (_build_target_entry). All four follow from the
  // distance, which the builder derives, so only the distance is stated.
  const enemyOutOfReach = makeTargetOption({ distance: 8 });
  const attackWithNoReachableTarget = makeAvailableOption({
    id: '7',
    name: 'Attack',
    description: 'Swing at an enemy.',
    targeted: true,
    viable_targets: [],
    target_previews: [enemyOutOfReach],
  });

  it('disables a targeted move whose viable-target list is empty', () => {
    renderPanel([attackWithNoReachableTarget]);

    expect(card('Attack')).toBeDisabled();
  });

  it('does not POST a move the server is guaranteed to refuse', () => {
    renderPanel([attackWithNoReachableTarget]);

    fireEvent.click(card('Attack'));
    expect(onMoveClick).not.toHaveBeenCalled();
    expect(playSFX).not.toHaveBeenCalled();
  });

  it('says in the panel why the move is unavailable', () => {
    renderPanel([attackWithNoReachableTarget]);

    expect(reasonFor('Attack')).toHaveTextContent('No valid target in range');
  });

  it('keeps a server-supplied reason rather than replacing it with the derived one', () => {
    renderPanel([{
      ...attackWithNoReachableTarget,
      available: false,
      reason: TOO_FAR_REASON,
    }]);

    const shown = reasonFor('Attack');
    expect(shown).toHaveTextContent(TOO_FAR_REASON);
    expect(shown.textContent).not.toMatch(/No valid target in range/i);
  });

  // Negative control: area moves publish `viable_targets: []` unconditionally
  // (the adapter only fills the list for `targeted` moves), so an empty list
  // must not be read as "nothing to hit" for them.
  it('leaves a non-targeted (area) move enabled with an empty target list', () => {
    renderPanel([makeAvailableOption({
      id: '1',
      name: 'Spin',
      description: 'Sweep everything adjacent.',
      targeted: false,
      viable_targets: [],
    })]);

    expect(card('Spin')).not.toBeDisabled();
    fireEvent.click(card('Spin'));
    expect(onMoveClick).toHaveBeenCalledTimes(1);
  });

  // Negative control: the normal case must keep working.
  it('leaves a targeted move with a reachable target enabled', () => {
    // Two lists, not one array in both fields: _get_available_targets and
    // _get_target_previews build them separately, and payloads.test.js pins
    // the builder to that.
    const rumbler = () => makeTargetOption({ name: 'Rock Rumbler' });
    renderPanel([{
      ...attackWithNoReachableTarget,
      viable_targets: [rumbler()],
      target_previews: [rumbler()],
    }]);

    expect(card('Attack')).not.toBeDisabled();
    fireEvent.click(card('Attack'));
    expect(onMoveClick).toHaveBeenCalledTimes(1);
  });
});

describe('CombatMovePanel — disabled cards read as disabled (#565)', () => {
  const moves = [
    makeAvailableOption({ id: '1', name: 'Slash', description: 'A basic slash' }),
    makeAvailableOption({
      id: '2',
      name: 'Power Strike',
      description: 'Wind up.',
      fatigue_cost: 35,
      available: false,
      reason: NOT_ENOUGH_FATIGUE_REASON,
    }),
  ];

  it('marks the unavailable card with a word, not only a colour', () => {
    renderPanel(moves);
    // One LOCKED marker, on the unavailable card only.
    const markers = screen.getAllByText(/LOCKED/);
    expect(markers).toHaveLength(1);
    expect(markers[0].closest('[data-testid="move-card"]')).toHaveAttribute('data-available', 'false');
  });

  it('gives the unavailable card a dashed border the available one does not have', () => {
    const { container } = renderPanel(moves);
    const cards = container.querySelectorAll('[data-testid="move-card"]');
    const [available, unavailable] = [...cards];
    expect(available.getAttribute('style')).not.toMatch(/dashed/);
    expect(unavailable.getAttribute('style')).toMatch(/dashed/);
  });

  it('associates the reason with the button instead of hiding it in a tooltip', () => {
    renderPanel(moves);
    const button = card('Power Strike');
    const describedBy = button.getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy)).toHaveTextContent(NOT_ENOUGH_FATIGUE_REASON);
  });

  it('leaves an available card undecorated', () => {
    renderPanel(moves);
    const button = card('Slash');
    expect(button).not.toHaveAttribute('aria-describedby');
    expect(button.closest('[data-testid="move-card"]')).toHaveAttribute('data-available', 'true');
  });
});
