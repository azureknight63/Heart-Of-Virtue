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
// distance, which the builder derives, so only the distance is stated: 8 ft
// from a move that reaches 5, hence `shortfall_ft: 3`. Shared by both
// describes below.
const outOfReach = (overrides = {}) => makeTargetOption({ distance: 8, ...overrides });
const attackWithNoReachableTarget = makeAvailableOption({
  id: '7',
  name: 'Attack',
  description: 'Swing at an enemy.',
  targeted: true,
  viable_targets: [],
  target_previews: [outOfReach()],
});

describe('CombatMovePanel — targeted moves with nothing in reach (#554)', () => {
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

// #614 gap 1. The card has said WHY since #554 ("No valid target in range"),
// but never HOW FAR: the player is told to close the distance without being
// told what the distance is. The adapter has shipped the number on every
// out-of-reach preview since #555 -- `shortfall_ft`, computed against the
// move's own reach in `_build_target_entry` -- and nothing in frontend/src
// read it. These pin the reading, not the arithmetic: the panel must never
// work a shortfall out from `distance` and `mvrange` itself (that is engine
// logic, and CLAUDE.md puts engine logic in the engine).
describe('CombatMovePanel — how far short a locked move falls (#614)', () => {
  it('says how far away the nearest target is and how far short the move falls', () => {
    renderPanel([attackWithNoReachableTarget]);

    const shown = reasonFor('Attack');
    expect(shown).toHaveTextContent('No valid target in range');
    expect(shown).toHaveTextContent('nearest 8 ft');
    expect(shown).toHaveTextContent('3 ft short');
  });

  it('adds the distance to a server-worded range refusal too', () => {
    renderPanel([{ ...attackWithNoReachableTarget, available: false, reason: TOO_FAR_REASON }]);

    const shown = reasonFor('Attack');
    expect(shown).toHaveTextContent(TOO_FAR_REASON);
    expect(shown).toHaveTextContent('3 ft short');
  });

  it('measures the nearest candidate, not whichever the list happens to start with', () => {
    renderPanel([{
      ...attackWithNoReachableTarget,
      target_previews: [
        outOfReach({ id: 'enemy_9', name: 'Far Rumbler', distance: 14 }),
        outOfReach({ id: 'enemy_2', name: 'Near Rumbler', distance: 7 }),
      ],
    }]);

    const shown = reasonFor('Attack');
    expect(shown).toHaveTextContent('nearest 7 ft');
    expect(shown).toHaveTextContent('2 ft short');
  });

  // Negative control: a fatigue lock is not a range lock. Appending a
  // shortfall to "Not enough fatigue" would name a distance that has nothing
  // to do with why the card is greyed out.
  it('says nothing about range when something IS in reach', () => {
    renderPanel([makeAvailableOption({
      id: '2',
      name: 'Power Strike',
      description: 'Wind up.',
      targeted: true,
      available: false,
      reason: NOT_ENOUGH_FATIGUE_REASON,
      viable_targets: [makeTargetOption()],
      target_previews: [makeTargetOption()],
    })]);

    const shown = reasonFor('Power Strike');
    expect(shown).toHaveTextContent(NOT_ENOUGH_FATIGUE_REASON);
    expect(shown.textContent).not.toMatch(/ft short/i);
  });

  // The lock that holds is the one the reason names. With every target out of
  // reach AND the card locked for fatigue or a cooldown, "3 ft short" appended
  // to that sentence would say walking closer fixes it, which it does not.
  it.each([
    ['fatigue', NOT_ENOUGH_FATIGUE_REASON],
    ['a cooldown', 'Available in 3 beats'],
  ])('says nothing about range when %s is the lock, even out of reach', (_label, why) => {
    renderPanel([{ ...attackWithNoReachableTarget, available: false, reason: why }]);

    const shown = reasonFor('Attack');
    expect(shown).toHaveTextContent(why);
    expect(shown.textContent).not.toMatch(/ft short/i);
  });

  // A card locked with no sentence at all renders no reason line (the panel
  // has rendered it behind `reason &&` since #565), so the suffix has nothing
  // to hang off. It must not become a dangling em-dash in the tooltip either.
  it('adds no dangling suffix to a lock that came with no sentence', () => {
    renderPanel([{ ...attackWithNoReachableTarget, available: false, reason: '' }]);

    expect(card('Attack')).not.toHaveAttribute('aria-describedby');
    expect(card('Attack')).toHaveAttribute('title', '');
  });

  // The reason element IS the accessible description (aria-describedby points
  // at it), so the number has to live in the same node rather than in a
  // sibling a screen reader never reaches.
  it('carries the distance in the accessible description, not beside it', () => {
    renderPanel([attackWithNoReachableTarget]);

    const describedBy = card('Attack').getAttribute('aria-describedby');
    expect(document.getElementById(describedBy).textContent).toMatch(/3 ft short/);
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
