import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import CombatMovePanel from './CombatMovePanel';
import { useAudio } from '../context/AudioContext';

vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn(),
}));

const card = (name) => screen.getByText(name).closest('button');

// GlossaryText splits the reason across a span per glossary term, so getByText
// cannot see the whole sentence. The reason element is the one the button's
// aria-describedby points at, and its textContent is the sentence.
const reasonFor = (name) => {
  const id = card(name).getAttribute('aria-describedby');
  return id ? document.getElementById(id) : null;
};

describe('CombatMovePanel — targeted moves with nothing in reach (#554)', () => {
  const onMoveClick = vi.fn();
  const onClose = vi.fn();
  const playSFX = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useAudio.mockReturnValue({ playSFX });
  });

  // The live payload from the reproduction: the engine advertises Attack as
  // available (its viable() only asks whether SOME enemy is in the move's
  // band) while the adapter's range-filtered allow-list is empty. The server
  // then refuses the very move it offered — "No valid targets available for
  // this move" — so the click spends nothing and advances no beat.
  const attackWithNoReachableTarget = {
    id: '7',
    name: 'Attack',
    category: 'Offensive',
    description: 'Swing at an enemy.',
    fatigue_cost: 4,
    available: true,
    reason: null,
    targeted: true,
    requires_target_selection: false,
    viable_targets: [],
  };

  it('disables a targeted move whose viable-target list is empty', () => {
    render(
      <CombatMovePanel
        moves={[attackWithNoReachableTarget]}
        category="Offensive"
        onMoveClick={onMoveClick}
        onClose={onClose}
      />
    );

    expect(card('Attack')).toBeDisabled();
  });

  it('does not POST a move the server is guaranteed to refuse', () => {
    render(
      <CombatMovePanel
        moves={[attackWithNoReachableTarget]}
        category="Offensive"
        onMoveClick={onMoveClick}
        onClose={onClose}
      />
    );

    fireEvent.click(card('Attack'));
    expect(onMoveClick).not.toHaveBeenCalled();
    expect(playSFX).not.toHaveBeenCalled();
  });

  it('says in the panel why the move is unavailable', () => {
    render(
      <CombatMovePanel
        moves={[attackWithNoReachableTarget]}
        category="Offensive"
        onMoveClick={onMoveClick}
        onClose={onClose}
      />
    );

    expect(reasonFor('Attack')).toHaveTextContent('No valid target in range');
  });

  it('keeps a server-supplied reason rather than replacing it with the derived one', () => {
    render(
      <CombatMovePanel
        moves={[{
          ...attackWithNoReachableTarget,
          available: false,
          reason: 'Enemy out of range (too far)',
        }]}
        category="Offensive"
        onMoveClick={onMoveClick}
        onClose={onClose}
      />
    );

    const shown = reasonFor('Attack');
    expect(shown).toHaveTextContent('Enemy out of range (too far)');
    expect(shown.textContent).not.toMatch(/No valid target in range/i);
  });

  // Negative control: area moves publish `viable_targets: []` unconditionally
  // (the adapter only fills the list for `targeted` moves), so an empty list
  // must not be read as "nothing to hit" for them.
  it('leaves a non-targeted (area) move enabled with an empty target list', () => {
    render(
      <CombatMovePanel
        moves={[{
          name: 'Spin',
          category: 'Offensive',
          description: 'Sweep everything adjacent.',
          available: true,
          targeted: false,
          viable_targets: [],
        }]}
        category="Offensive"
        onMoveClick={onMoveClick}
        onClose={onClose}
      />
    );

    expect(card('Spin')).not.toBeDisabled();
    fireEvent.click(card('Spin'));
    expect(onMoveClick).toHaveBeenCalledTimes(1);
  });

  // Negative control: the normal case must keep working.
  it('leaves a targeted move with a reachable target enabled', () => {
    render(
      <CombatMovePanel
        moves={[{
          ...attackWithNoReachableTarget,
          viable_targets: [{ id: 'enemy_1', name: 'Rock Rumbler' }],
        }]}
        category="Offensive"
        onMoveClick={onMoveClick}
        onClose={onClose}
      />
    );

    expect(card('Attack')).not.toBeDisabled();
    fireEvent.click(card('Attack'));
    expect(onMoveClick).toHaveBeenCalledTimes(1);
  });
});

describe('CombatMovePanel — disabled cards read as disabled (#565)', () => {
  const onMoveClick = vi.fn();
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useAudio.mockReturnValue({ playSFX: vi.fn() });
  });

  const moves = [
    { name: 'Slash', category: 'Offensive', description: 'A basic slash', fatigue_cost: 5, available: true },
    {
      name: 'Power Strike',
      category: 'Offensive',
      description: 'Wind up.',
      fatigue_cost: 35,
      available: false,
      reason: 'Not enough fatigue',
    },
  ];

  const renderPanel = () => render(
    <CombatMovePanel moves={moves} category="Offensive" onMoveClick={onMoveClick} onClose={onClose} />
  );

  it('marks the unavailable card with a word, not only a colour', () => {
    renderPanel();
    // One LOCKED marker, on the unavailable card only.
    const markers = screen.getAllByText(/LOCKED/);
    expect(markers).toHaveLength(1);
    expect(markers[0].closest('[data-testid="move-card"]')).toHaveAttribute('data-available', 'false');
  });

  it('gives the unavailable card a dashed border the available one does not have', () => {
    const { container } = renderPanel();
    const cards = container.querySelectorAll('[data-testid="move-card"]');
    const [available, unavailable] = [...cards];
    expect(available.getAttribute('style')).not.toMatch(/dashed/);
    expect(unavailable.getAttribute('style')).toMatch(/dashed/);
  });

  it('associates the reason with the button instead of hiding it in a tooltip', () => {
    renderPanel();
    const button = screen.getByText('Power Strike').closest('button');
    const describedBy = button.getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy)).toHaveTextContent('Not enough fatigue');
  });

  it('leaves an available card undecorated', () => {
    renderPanel();
    const button = screen.getByText('Slash').closest('button');
    expect(button).not.toHaveAttribute('aria-describedby');
    expect(button.closest('[data-testid="move-card"]')).toHaveAttribute('data-available', 'true');
  });
});

describe('CombatMovePanel — clicks over the occluded category nav (#557)', () => {
  const onMoveClick = vi.fn();
  const onClose = vi.fn();
  let navClick;

  // The nav bar HeroPanel renders under this flyout. Its buttons are
  // zIndex 5 against the panel's 100, so a press at these coordinates lands
  // on the panel; the rect is what lets the panel notice.
  const NAV_RECT = { left: 100, top: 40, right: 170, bottom: 84, width: 70, height: 44 };

  const OccludedNav = () => (
    <nav aria-label="Game actions" style={{ display: 'contents' }}>
      <button onClick={navClick}>OFFENSIVE</button>
    </nav>
  );

  beforeEach(() => {
    vi.clearAllMocks();
    navClick = vi.fn();
    useAudio.mockReturnValue({ playSFX: vi.fn() });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderWithNav = (moves) => {
    const view = render(
      <>
        <OccludedNav />
        <CombatMovePanel
          moves={moves}
          category="Miscellaneous"
          onMoveClick={onMoveClick}
          onClose={onClose}
        />
      </>
    );
    const navButton = screen.getByRole('button', { name: 'OFFENSIVE' });
    vi.spyOn(navButton, 'getBoundingClientRect').mockReturnValue(NAV_RECT);
    return view;
  };

  const inNavRect = { clientX: 135, clientY: 62 };

  it('hands a press on the panel chrome to the category button underneath', () => {
    const { container } = renderWithNav([
      { name: 'Meditate', category: 'Miscellaneous', description: 'Rest.', available: true },
    ]);

    const panel = container.querySelector('.game-panel');
    fireEvent.pointerDown(panel, inNavRect);

    expect(navClick).toHaveBeenCalledTimes(1);
  });

  it('leaves a press on one of its own move cards alone', () => {
    renderWithNav([
      { name: 'Meditate', category: 'Miscellaneous', description: 'Rest.', available: true },
    ]);

    const moveButton = screen.getByText('Meditate').closest('button');
    fireEvent.pointerDown(moveButton, inNavRect);
    fireEvent.click(moveButton);

    expect(navClick).not.toHaveBeenCalled();
    expect(onMoveClick).toHaveBeenCalledTimes(1);
  });

  it('ignores a press on the panel chrome that is over nothing', () => {
    const { container } = renderWithNav([
      { name: 'Meditate', category: 'Miscellaneous', description: 'Rest.', available: true },
    ]);

    const panel = container.querySelector('.game-panel');
    fireEvent.pointerDown(panel, { clientX: 999, clientY: 999 });

    expect(navClick).not.toHaveBeenCalled();
  });
});
