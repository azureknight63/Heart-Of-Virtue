import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CombatInputDialog from './CombatInputDialog';
import { makeTargetOption } from '../test/payloads';
import { useAudio } from '../context/AudioContext';

// Mock useAudio
vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn(),
}));

describe('CombatInputDialog', () => {
  const mockPlaySFX = vi.fn();
  const mockOnSelect = vi.fn();
  const mockOnCancel = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useAudio.mockReturnValue({ playSFX: mockPlaySFX });
  });

  it('renders target selection correctly', () => {
    // From src/test/payloads.js (ApiCombatAdapter._get_available_targets), so a
    // rename on the server side breaks this test instead of passing against a
    // fixture that agrees with whatever the component happens to read.
    // `hit_chance` is an INTEGER PERCENTAGE in [2, 100], never a 0-1 fraction —
    // rescaling it client-side collapsed every real value to 0%-1% (drift #5).
    const options = [
      makeTargetOption({ id: 'target1', name: 'Goblin', distance: 10, health: { current: 50, max: 100 }, hit_chance: 85 }),
      makeTargetOption({ id: 'target2', name: 'Orc', distance: 20, health: { current: 120, max: 150 }, hit_chance: 60 }),
    ];

    render(
      <CombatInputDialog
        inputType="target_selection"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText((content) => content.includes('SELECT TARGET'))).toBeDefined();
    expect(screen.getByText('Goblin')).toBeDefined();
    expect(screen.getAllByText(/10 ft/i)).toBeDefined();
    expect(screen.getByText(/50\/100/)).toBeDefined();
    expect(screen.getAllByText(/Accuracy:/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/85%/)).toBeDefined();

    expect(screen.getByText('Orc')).toBeDefined();
    expect(screen.getAllByText(/20 ft/i)).toBeDefined();
    expect(screen.getByText(/120\/150/)).toBeDefined();
    expect(screen.getByText(/60%/)).toBeDefined();

    // Click a target (the card containing 'Goblin')
    fireEvent.click(screen.getByText('Goblin').closest('div').parentElement);
    expect(mockOnSelect).toHaveBeenCalledWith('target1');
    expect(mockPlaySFX).toHaveBeenCalledWith('attack');
  });

  it('renders direction selection correctly', () => {
    const options = ['North', 'South', 'East', 'West'];

    render(
      <CombatInputDialog
        inputType="direction_selection"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText((content) => content.includes('SELECT DIRECTION'))).toBeDefined();
    options.forEach(dir => {
      expect(screen.getByText(dir.toUpperCase())).toBeDefined();
    });

    fireEvent.click(screen.getByText('NORTH'));
    expect(mockOnSelect).toHaveBeenCalledWith('North');
  });

  it('renders number input correctly and handles increment/decrement', () => {
    const options = { prompt: 'How many points?', min: 1, max: 10, default: 5 };

    render(
      <CombatInputDialog
        inputType="number_input"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText((content) => content.includes('ENTER VALUE'))).toBeDefined();
    expect(screen.getByText('How many points?')).toBeDefined();
    expect(screen.getByText(/Range: 1 - 10/i)).toBeDefined();

    expect(screen.getByText('5')).toBeDefined();

    // Increment
    fireEvent.click(screen.getByText('+'));
    expect(screen.getByText('6')).toBeDefined();

    // Decrement
    fireEvent.click(screen.getByText('−'));
    expect(screen.getByText('5')).toBeDefined();

    // Validation - min
    fireEvent.click(screen.getByText('−'));
    fireEvent.click(screen.getByText('−'));
    fireEvent.click(screen.getByText('−'));
    fireEvent.click(screen.getByText('−'));
    fireEvent.click(screen.getByText('−'));
    expect(screen.getByText('1')).toBeDefined();

    // Confirm
    fireEvent.click(screen.getByText('CONFIRM'));
    expect(mockOnSelect).toHaveBeenCalledWith(1);
  });

  it('renders item selection (default case) correctly', () => {
    const options = [
      { id: 'item1', name: 'Health Potion' },
      { id: 'item2', name: 'Mana Potion' }
    ];

    render(
      <CombatInputDialog
        inputType="item_selection"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText((content) => content.includes('SELECT ITEM'))).toBeDefined();
    expect(screen.getByText('Health Potion')).toBeDefined();
    expect(screen.getByText('Mana Potion')).toBeDefined();

    fireEvent.click(screen.getByText('Health Potion'));
    expect(mockOnSelect).toHaveBeenCalledWith('item1');
  });

  it('renders generic options correctly', () => {
    const options = ['Option A', 'Option B'];

    render(
      <CombatInputDialog
        inputType="unknown"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText((content) => content.includes('SELECT OPTION'))).toBeDefined();
    expect(screen.getByText('Option A')).toBeDefined();
    expect(screen.getByText('Option B')).toBeDefined();

    fireEvent.click(screen.getByText('Option A'));
    expect(mockOnSelect).toHaveBeenCalledWith('Option A');
  });

  it('renders empty state when no options provided', () => {
    render(
      <CombatInputDialog
        inputType="target_selection"
        options={[]}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText(/No valid targets or options available/i)).toBeDefined();
  });

  it('calls onCancel when cancel button is clicked', () => {
    render(
      <CombatInputDialog
        inputType="target_selection"
        options={[{ id: 1, name: 'Test' }]}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    const cancelButton = screen.getByText('CANCEL ACTION');
    fireEvent.click(cancelButton);
    // Exactly once, and cancelling must never also submit a selection — the
    // adapter would consume the beat on a move the player backed out of.
    expect(mockOnCancel).toHaveBeenCalledTimes(1);
    expect(mockOnSelect).not.toHaveBeenCalled();
  });

  it('highlights a direction button on hover and clears it on leave', () => {
    // The old comment here ("jsdom doesn't support :hover styles") was wrong:
    // GameButton tracks hover in React state and recomputes backgroundColor, so
    // it IS observable. Under the old version both handlers could be deleted and
    // the test still passed.
    render(
      <CombatInputDialog
        inputType="direction_selection"
        options={['North']}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    const button = screen.getByText('NORTH');
    // secondary variant: transparent at rest, text.highlight @ 0x22 alpha on hover.
    expect(button.style.backgroundColor).toBe('transparent');

    fireEvent.mouseEnter(button);
    expect(button.style.backgroundColor).toBe('rgba(255, 238, 170, 0.133)');

    fireEvent.mouseLeave(button);
    expect(button.style.backgroundColor).toBe('transparent');

    fireEvent.click(button);
    expect(mockOnSelect).toHaveBeenCalledExactlyOnceWith('North');
  });

  it('handles hover effects on target selection buttons', () => {
    const options = [{ id: 't1', name: 'Target' }];
    render(
      <CombatInputDialog
        inputType="target_selection"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    const card = screen.getByText('Target').closest('div').parentElement;

    fireEvent.mouseEnter(card);
    fireEvent.mouseLeave(card);

    fireEvent.click(card);
    // Selecting a target must send the target's ID, never its display name —
    // the adapter resolves the combatant by id.
    expect(mockOnSelect).toHaveBeenCalledExactlyOnceWith('t1');
  });

  it('highlights the confirm button on hover and submits the value on the face of the dial', () => {
    render(
      <CombatInputDialog
        inputType="number_input"
        options={{ min: 1, max: 10 }}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    const button = screen.getByText('CONFIRM');
    // primary variant: #00ff88 at rest, #00ffaa on hover.
    expect(button.style.backgroundColor).toBe('rgb(0, 255, 136)');
    fireEvent.mouseEnter(button);
    expect(button.style.backgroundColor).toBe('rgb(0, 255, 170)');
    fireEvent.mouseLeave(button);
    expect(button.style.backgroundColor).toBe('rgb(0, 255, 136)');

    // With no `default`, the dial starts at `min` — and confirming must submit
    // exactly what the player can see, as a NUMBER. `toHaveBeenCalled()` passed
    // even when the handler sent undefined, which the adapter reads as 0 beats.
    fireEvent.click(screen.getByText('+'));
    fireEvent.click(button);
    expect(mockOnSelect).toHaveBeenCalledExactlyOnceWith(2);
  });

  it('notifies onTargetHover on hover and clears it on select', () => {
    const mockOnTargetHover = vi.fn();
    const options = [{ id: 't1', name: 'Target' }];
    render(
      <CombatInputDialog
        inputType="target_selection"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
        onTargetHover={mockOnTargetHover}
      />
    );

    const card = screen.getByText('Target').closest('div').parentElement;
    fireEvent.mouseEnter(card);
    expect(mockOnTargetHover).toHaveBeenCalledWith('t1');
    fireEvent.mouseLeave(card);
    expect(mockOnTargetHover).toHaveBeenCalledWith(null);

    fireEvent.click(card);
    expect(mockOnTargetHover).toHaveBeenLastCalledWith(null);
  });

  it('falls back to name/label/id and renders plain strings for default-case options', () => {
    const options = ['Plain String', { label: 'Label Only' }, { name: 'Named Item' }];
    render(
      <CombatInputDialog
        inputType="unknown"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText('Plain String')).toBeDefined();
    expect(screen.getByText('Label Only')).toBeDefined();
    expect(screen.getByText('Named Item')).toBeDefined();

    fireEvent.click(screen.getByText('Plain String'));
    expect(mockOnSelect).toHaveBeenCalledWith('Plain String');
  });

  it('defaults min/max/default when NumberInput options omit them', () => {
    render(
      <CombatInputDialog
        inputType="number_input"
        options={{}}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText('5')).toBeDefined();
    expect(screen.getByText(/Range: 1 - 100/i)).toBeDefined();
  });

  it('handles hover effects on generic option buttons', () => {
    render(
      <CombatInputDialog
        inputType="generic"
        options={['Option']}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    const button = screen.getByText('Option');

    // jsdom doesn't support :hover styles, so just verify button responds to hover events
    fireEvent.mouseEnter(button);
    fireEvent.mouseLeave(button);

    // Button should still be clickable
    fireEvent.click(button);
    expect(mockOnSelect).toHaveBeenCalledWith('Option');
  });
  // --- Issue #535: confirm-verb, HP color, and hit-testability -------------
  describe('target selection — confirm verb (issue #535 sub-item 2)', () => {
    it('labels the confirm control STRIKE for a genuine attack (Offensive) move', () => {
      const options = [makeTargetOption({ id: 'target1', name: 'Goblin' })];
      render(
        <CombatInputDialog
          inputType="target_selection"
          options={options}
          onSelect={mockOnSelect}
          onCancel={mockOnCancel}
          moveName="Slash"
          moveCategory="Offensive"
        />
      );
      expect(screen.getByRole('button', { name: /strike/i })).toBeDefined();
    });

    it('labels the confirm control with the move\'s own verb for a non-attack move (e.g. Advance)', () => {
      // Regression: MANEUVER -> Advance used to show "STRIKE" on both the
      // enemy AND an allied target, which reads as "attack your own ally".
      const options = [
        makeTargetOption({ id: 'enemy_1', name: 'Rock Rumbler' }),
        makeTargetOption({ id: 'ally_1', name: 'Gorran' }),
      ];
      render(
        <CombatInputDialog
          inputType="target_selection"
          options={options}
          onSelect={mockOnSelect}
          onCancel={mockOnCancel}
          moveName="Advance"
          moveCategory="Maneuver"
        />
      );
      // Two targets means two confirm buttons; a stray "STRIKE" on either
      // one is the bug, so scan all matches rather than assume uniqueness.
      expect(screen.queryAllByText(/strike/i).length).toBe(0);
      // GameButton uppercases via CSS textTransform, so the button's own text
      // content is the move's actual name, not a fixed "STRIKE".
      expect(screen.getAllByRole('button', { name: /advance/i }).length).toBeGreaterThan(0);
    });

    it('falls back to a neutral "Select" when no move name/category is known', () => {
      const options = [makeTargetOption({ id: 'target1', name: 'Goblin' })];
      render(
        <CombatInputDialog
          inputType="target_selection"
          options={options}
          onSelect={mockOnSelect}
          onCancel={mockOnCancel}
        />
      );
      expect(screen.queryAllByText(/strike/i).length).toBe(0);
      expect(screen.getByRole('button', { name: /select/i })).toBeDefined();
    });
  });

  describe('target selection — HP bar color reflects real percentage (issue #535 sub-item 3)', () => {
    // colors.success/warning/danger, as rgb() — jsdom normalizes any hex
    // color set via inline style to this form.
    const HEALTHY = 'rgb(0, 255, 136)';
    const WARNING = 'rgb(255, 170, 0)';
    const DANGER = 'rgb(255, 68, 68)';

    it('renders a full-health target in a healthy color, not danger red', () => {
      const options = [makeTargetOption({ id: 'ally_1', name: 'Gorran', health: { current: 48, max: 48 } })];
      render(
        <CombatInputDialog
          inputType="target_selection"
          options={options}
          onSelect={mockOnSelect}
          onCancel={mockOnCancel}
        />
      );
      const hpLine = screen.getByText('48/48');
      expect(hpLine.style.color).toBe(HEALTHY);
    });

    it('renders a critically low-health target in danger red', () => {
      const options = [makeTargetOption({ id: 'enemy_1', name: 'Rumbler', health: { current: 10, max: 100 } })];
      render(
        <CombatInputDialog
          inputType="target_selection"
          options={options}
          onSelect={mockOnSelect}
          onCancel={mockOnCancel}
        />
      );
      const hpLine = screen.getByText('10/100');
      expect(hpLine.style.color).toBe(DANGER);
    });

    it('renders a mid-health target in a distinct warning color', () => {
      const options = [makeTargetOption({ id: 'enemy_1', name: 'Rumbler', health: { current: 35, max: 100 } })];
      render(
        <CombatInputDialog
          inputType="target_selection"
          options={options}
          onSelect={mockOnSelect}
          onCancel={mockOnCancel}
        />
      );
      const hpLine = screen.getByText('35/100');
      expect(hpLine.style.color).toBe(WARNING);
    });

    it('also colors the fill bar itself by percentage, not a fixed hue', () => {
      const options = [makeTargetOption({ id: 'ally_1', name: 'Gorran', health: { current: 48, max: 48 } })];
      const { container } = render(
        <CombatInputDialog
          inputType="target_selection"
          options={options}
          onSelect={mockOnSelect}
          onCancel={mockOnCancel}
        />
      );
      const fill = container.querySelector('div[style*="width: 100%"][style*="border-radius: 2px"]');
      expect(fill).not.toBeNull();
      expect(fill.style.backgroundColor).toBe(HEALTHY);
    });
  });

  describe('target selection — STRIKE/confirm button is genuinely hit-testable (issue #535 sub-item 5)', () => {
    it('the confirm button itself does not carry pointerEvents: none', () => {
      // Confirmed root cause: a deliberate `pointerEvents: 'none'` on the
      // button made it invisible to real DOM hit-testing (elementFromPoint /
      // Playwright's actionability check), even though the card's onClick
      // still made the CARD clickable. The button itself must be real.
      const options = [makeTargetOption({ id: 'target1', name: 'Goblin' })];
      render(
        <CombatInputDialog
          inputType="target_selection"
          options={options}
          onSelect={mockOnSelect}
          onCancel={mockOnCancel}
        />
      );
      const button = screen.getByRole('button', { name: /select|strike/i });
      expect(button.style.pointerEvents).not.toBe('none');
    });

    it('clicking the confirm button directly selects the target exactly once', () => {
      const options = [makeTargetOption({ id: 'target1', name: 'Goblin' })];
      render(
        <CombatInputDialog
          inputType="target_selection"
          options={options}
          onSelect={mockOnSelect}
          onCancel={mockOnCancel}
        />
      );
      const button = screen.getByRole('button', { name: /select|strike/i });
      fireEvent.click(button);
      // Not called twice: the card itself keeps its own onClick for the same
      // target, and a naive fix that lets both fire would submit the move twice.
      expect(mockOnSelect).toHaveBeenCalledExactlyOnceWith('target1');
    });
  });

  it('sizes itself against the battlefield panel it sits in, not the viewport', () => {
    // This dialog is `containerCentered` — it is positioned inside the
    // battlefield panel, not the viewport. It also passes maxWidth="600px", so
    // BaseDialog's viewport-relative `min(94vw, 600px)` default resolves to a
    // width wider than its own container on any panel narrower than 600px and
    // overflows it. Container-relative is the only correct default here.
    const { container } = render(
      <CombatInputDialog
        inputType="generic"
        options={['Option']}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    const overlay = container.querySelector('.modal-overlay');
    expect(overlay).toHaveStyle({ position: 'absolute' });
    expect(container.querySelector('.modal-content')).toHaveStyle({
      width: '90%',
      maxWidth: '600px',
    });
  });
});
