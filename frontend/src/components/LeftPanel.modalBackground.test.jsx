import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LeftPanel from './LeftPanel';
import { MODAL_BACKGROUND_ATTR } from './BaseDialog';
import { CATEGORY_NAV_LABEL } from '../utils/categories'
import { makePlayer, makeLocation, makeBattleState, makeEnemy, makeTargetOption } from '../test/payloads';

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

const baseProps = {
  player: makePlayer(),
  location: makeLocation({ name: 'High Ledge', description: 'A ledge.' }),
};

// `combat` is a battle_state, not a response body: transformCombatData
// (useApi.js) SPREADS battle_state flat onto the object components receive, so
// makeBattleState is the shape this prop actually takes.
//
// The dialog opens off an effect, not a prop: the effect that sets
// showInputDialog wants input_type present and not 'move_selection',
// awaiting_input true, and no end_state. Everything else is the factory
// default -- stated here only where this test depends on it.
const combat = makeBattleState({
  input_type: 'target_selection',
  awaiting_input: true,
  available_options: [
    // `is_ally` is hand-supplied rather than a factory default because
    // makeTargetOption does not carry it yet, even though
    // _build_target_entry (src/api/combat_adapter.py) emits it on every card.
    // Promoting it to the factory is not free: hostilityTokenFor treats
    // `false` and absent differently (HOSTILE badge vs no badge), so a
    // default would change the 13 existing makeTargetOption fixtures in
    // CombatInputDialog.test.jsx. Left for its own change.
    makeTargetOption({ id: 'enemy_1', name: 'Rock Rumbler', is_ally: false }),
  ],
  // `distance` is the only field of an enemy row LeftPanel itself reads (the
  // flee gate, against FLEE_BREAK_AWAY_DISTANCE_FT). Kept under the 20 ft
  // threshold, as it was before the migration, so this refactor does not move
  // which affordances render.
  enemies: [makeEnemy({ name: 'Rock Rumbler', distance: 3 })],
});

describe('LeftPanel — no modal may live inside a modal-background region', () => {
  it('renders no role=dialog inside a marked region during combat target selection', () => {
    const { container } = render(
      <LeftPanel
        {...baseProps}
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
