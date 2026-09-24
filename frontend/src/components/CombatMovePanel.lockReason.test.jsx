import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CombatMovePanel from './CombatMovePanel';
import { useAudio } from '../context/AudioContext';
import { makeAvailableOption } from '../test/payloads';

vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  useAudio.mockReturnValue({ playSFX: vi.fn() });
});

const renderPanel = (moves) => render(
  <CombatMovePanel moves={moves} category="Maneuver" onMoveClick={vi.fn()} onClose={vi.fn()} />
);

const cardFor = (name) => screen.getByText(name).closest('[data-testid="move-card"]');
const buttonFor = (name) => screen.getByText(name).closest('button');

// #627: every untargeted move viable() refused used to read "Cannot use this
// move". The adapter now ships the engine's reason code and its sentence.
const rest = makeAvailableOption({
  id: '3',
  name: 'Rest',
  targeted: false,
  category: 'Maneuver',
  available: false,
  reason_code: 'fully_rested',
  reason: 'Already fully rested',
});

describe('CombatMovePanel — a locked card says why (#627)', () => {
  it('shows the engine sentence for the lock', () => {
    renderPanel([rest]);

    const describedBy = buttonFor('Rest').getAttribute('aria-describedby');
    expect(document.getElementById(describedBy)).toHaveTextContent('Already fully rested');
  });

  // The code rides on the card so QA tooling can group locked cards by cause
  // without parsing the prose -- which is exactly what the prose may not be
  // relied on for, since its wording is free to change.
  it('carries the reason code on a locked card', () => {
    renderPanel([rest]);

    expect(cardFor('Rest')).toHaveAttribute('data-reason-code', 'fully_rested');
  });

  it('carries no reason code on an available card', () => {
    renderPanel([makeAvailableOption({ name: 'Wait', targeted: false, category: 'Maneuver' })]);

    expect(cardFor('Wait')).not.toHaveAttribute('data-reason-code');
  });
});
