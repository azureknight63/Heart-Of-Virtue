import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LeftPanel from './LeftPanel';
import { MODAL_BACKGROUND_ATTR } from './BaseDialog';
import { CATEGORY_NAV_LABEL } from '../utils/categories'

/**
 * Structural guard for #563 item 5's aria-hidden mechanism.
 *
 * The marker hides a region from assistive tech while any modal is open. That
 * is only correct if no modal is rendered INSIDE a marked region -- otherwise
 * the dialog hides itself, and because the focus trap still holds keyboard
 * focus inside it, a screen-reader user is parked at a blocking prompt that
 * announces nothing and offers no reachable exit. Worse than the state the
 * marker was added to fix.
 *
 * CombatInputDialog was exactly that: rendered inside the marked content well
 * rather than in the Modal Overlays block where every other dialog lives.
 *
 * Asserted as a general property over whatever the component renders, not as
 * a check for that one dialog -- the next dialog dropped into the wrong block
 * has to fail this too. Deliberately does NOT mock BaseDialog: the whole
 * point is the real marker plumbing.
 */
vi.mock('./HeroPanel', () => ({
  default: () => (
    <nav aria-label={CATEGORY_NAV_LABEL}>
      <button>OFFENSIVE</button>
    </nav>
  ),
}));
vi.mock('./CombatLog', () => ({ default: () => <div /> }));
vi.mock('./CooldownTray', () => ({ default: () => <div /> }));
vi.mock('./HeatMeter', () => ({ default: () => <div /> }));
vi.mock('./SuggestedMovesPanel', () => ({ default: () => <div /> }));
vi.mock('./CollapsibleRoomDescription', () => ({ default: () => <div /> }));

const player = { name: 'Jean', hp: 100, maxhp: 100, fatigue: 50, maxfatigue: 50, level: 1 };
const location = { name: 'High Ledge', description: 'A ledge.', objects: [], npcs: [], items: [] };

// The dialog opens off an effect, not a prop: input_type must be present and
// not move_selection, awaiting_input true, and no end_state (LeftPanel.jsx:193).
const combat = {
  combat_id: 'c1',
  input_type: 'target_selection',
  awaiting_input: true,
  available_options: [{ id: '1', name: 'Rock Rumbler', is_ally: false }],
  enemies: [{ name: 'Rock Rumbler', hp: 48, maxhp: 48, distance: 3 }],
  beat: 1,
};

describe('LeftPanel — no modal may live inside a modal-background region', () => {
  it('renders no role=dialog inside a marked region during combat target selection', () => {
    const { container } = render(
      <LeftPanel
        player={player}
        location={location}
        mode="combat"
        combat={combat}
        onCombatAction={vi.fn()}
      />
    );

    const marked = [...container.querySelectorAll(`[${MODAL_BACKGROUND_ATTR}]`)];
    expect(marked.length).toBeGreaterThan(0); // the mechanism is actually present

    const dialogs = [...container.querySelectorAll('[role="dialog"]')];
    expect(dialogs.length).toBeGreaterThan(0); // and a dialog really is open

    const trapped = dialogs.filter((d) => marked.some((m) => m !== d && m.contains(d)));
    expect(trapped.map((d) => d.getAttribute('aria-label') || d.textContent?.slice(0, 60))).toEqual([]);
  });
});
