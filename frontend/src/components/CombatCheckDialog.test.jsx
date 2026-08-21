import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CombatCheckDialog from './CombatCheckDialog';

describe('CombatCheckDialog', () => {
  const mockCheckData = [
    {
      name: 'Hero',
      is_ally: true,
      distance: 0,
      direction_from_player: 'Self',
      facing: 'North',
      current_move: 'Rest',
      current_move_display_name: 'Rest',
      current_move_stage: 0
    },
    {
      name: 'Goblin',
      is_ally: false,
      distance: 5,
      direction_from_player: 'North',
      facing: 'South',
      current_move: 'NPC_Attack',
      current_move_display_name: 'Attack',
      current_move_stage: 1
    }
  ];

  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing if checkData is empty', () => {
    const { container } = render(<CombatCheckDialog checkData={[]} onClose={mockOnClose} />);
    expect(container.firstChild).toBeNull();
  });

  /** The card wrapping a named combatant. */
  const cardFor = (name) => screen.getByText(name).closest('div[style*="border-radius: 6px"]');

  it('renders one card per combatant, in the order the server sent them', () => {
    render(<CombatCheckDialog checkData={mockCheckData} onClose={mockOnClose} />);

    expect(screen.getByText('Battlefield Status').textContent).toBe('Battlefield Status');
    expect(screen.getByText(/combatants? detected/).textContent)
      .toBe('2 combatants detected (sorted by distance)');

    // The header claims "sorted by distance", but the sorting happens server
    // side — the dialog must render the array as given, not re-sort it.
    const heroCard = cardFor('Hero');
    const goblinCard = cardFor('Goblin');
    expect(Array.from(heroCard.parentElement.children)).toEqual([heroCard, goblinCard]);
  });

  it('labels allies and enemies distinctly and shows each combatant\'s stats', () => {
    render(<CombatCheckDialog checkData={mockCheckData} onClose={mockOnClose} />);
    const heroCard = cardFor('Hero');
    const goblinCard = cardFor('Goblin');

    expect(heroCard.textContent).toBe('HeroALLYDistance: 0 ftDirection: SelfFacing: NorthPreparing: Rest');
    expect(goblinCard.textContent).toBe('GoblinENEMYDistance: 5 ftDirection: NorthFacing: SouthUsing: Attack');
  });

  it('prefers current_move_display_name over the raw engine move id', () => {
    // The Goblin's move is `NPC_Attack` on the wire; the player must never see
    // that identifier.
    render(<CombatCheckDialog checkData={mockCheckData} onClose={mockOnClose} />);
    expect(screen.getByText('Using: Attack').textContent).toBe('Using: Attack');
    expect(screen.queryByText(/NPC_Attack/)).toBeNull();
  });

  it.each([
    [0, 'Preparing: Rest'],
    [1, 'Using: Rest'],
    [2, 'Just used: Rest'],
    [3, 'Cooling down from: Rest'],
    [undefined, 'Rest'],
  ])('renders move stage %s as "%s"', (stage, expected) => {
    render(<CombatCheckDialog
      checkData={[{ ...mockCheckData[0], current_move_stage: stage }]}
      onClose={mockOnClose}
    />);
    expect(screen.getByText(expected).textContent).toBe(expected);
  });

  it('omits the optional rows a combatant payload does not carry', () => {
    render(<CombatCheckDialog
      checkData={[{ name: 'Wisp', is_ally: false, distance: 12 }]}
      onClose={mockOnClose}
    />);
    expect(cardFor('Wisp').textContent).toBe('WispENEMYDistance: 12 ft');
  });

  it('renders singular "combatant" when there is only one', () => {
    render(<CombatCheckDialog checkData={[mockCheckData[0]]} onClose={mockOnClose} />);
    expect(screen.getByText(/combatants? detected/).textContent)
      .toBe('1 combatant detected (sorted by distance)');
  });

  it('renders nothing when checkData is null', () => {
    const { container } = render(<CombatCheckDialog checkData={null} onClose={mockOnClose} />);
    expect(container.firstChild).toBeNull();
  });

  it('closes from either the ✕ or the bottom Close button', () => {
    render(<CombatCheckDialog checkData={mockCheckData} onClose={mockOnClose} />);

    fireEvent.click(screen.getByText('✕'));
    expect(mockOnClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText('Close'));
    expect(mockOnClose).toHaveBeenCalledTimes(2);
  });

  it('does not close on hover alone', () => {
    // Was "handles hover effects on close button", which hovered and then
    // clicked — so it re-proved the click test and said nothing about hover.
    // jsdom applies no :hover CSS, so the only checkable claim is that hover is
    // not itself an activation.
    render(<CombatCheckDialog checkData={mockCheckData} onClose={mockOnClose} />);
    const closeBtn = screen.getByText('Close');

    fireEvent.mouseEnter(closeBtn);
    fireEvent.mouseLeave(closeBtn);
    expect(mockOnClose).not.toHaveBeenCalled();

    fireEvent.click(closeBtn);
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });
});
