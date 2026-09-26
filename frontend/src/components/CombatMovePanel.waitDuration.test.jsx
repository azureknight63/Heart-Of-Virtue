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

// #718 item 2: Wait's card said "0 beats" — the engine reports a placeholder
// stage_beats of [0,0,0,0] until a duration is actually chosen
// (src/moves/_utility.py Wait.__init__), and the real 3-10 beat range that
// the player picks from lives only in WAIT_DURATION_PROMPT
// (src/api/combat_adapter.py), a payload the client never sees until AFTER
// Wait is clicked and the server switches to the number_input prompt. The
// moves-list payload itself carries no range at all, so the card must not
// invent one — it says "you choose" instead of a beat count.
const wait = makeAvailableOption({
  id: '7',
  name: 'Wait',
  display_name: 'Wait',
  targeted: false,
  category: 'Utility',
  stage_beats: { prep: 0, execute: 0, recoil: 0, cooldown: 0 },
});

describe('CombatMovePanel — Wait duration label (#718)', () => {
  // Utility rides in the Miscellaneous button group (CATEGORY_GROUPS,
  // utils/categories.js), not its own "Utility" panel.
  it('does not claim a "0 beats" commitment for a move whose duration is chosen later', () => {
    render(
      <CombatMovePanel moves={[wait]} category="Miscellaneous" onMoveClick={vi.fn()} onClose={vi.fn()} />
    );

    expect(screen.queryByText(/0 beats/i)).not.toBeInTheDocument();
  });

  it('tells the player they choose the duration instead', () => {
    render(
      <CombatMovePanel moves={[wait]} category="Miscellaneous" onMoveClick={vi.fn()} onClose={vi.fn()} />
    );

    expect(screen.getByText(/you choose/i)).toBeInTheDocument();
  });
});
