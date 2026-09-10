import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LeftPanel, { HERO_PANEL_STACKING_Z_INDEX } from './LeftPanel';
import { GAME_PANEL_CLASS } from './GamePanel';
import { COMBAT_MOVE_PANEL_Z_INDEX } from './CombatMovePanel';
import { CATEGORY_NAV_SELECTOR } from '../utils/categories';

/**
 * Issue #575 — with a category open, a tall stack of move cards can cover
 * three of the five combat nav tabs (OFFENSIVE/MANEUVER survive because
 * they sit over the panel's header chrome; INVENTORY/MISC/DEFENSIVE sit
 * lower, over the card list, and used to go dead).
 *
 * `useOccludedNavHandoff` used to paper over this by hit-testing coordinates
 * and forwarding a click on the panel's inert chrome to the nav button
 * underneath — but it explicitly declined to do that for a click that landed
 * on one of the panel's OWN controls (a move card), because a real click
 * there is genuinely ambiguous. A tab fully covered by a card stayed dead.
 *
 * The actual fix is a stacking-order change: LeftPanel now renders the WHOLE
 * box that wraps HeroPanel (nav included) at a z-index above CombatMovePanel,
 * so the nav can never be visually underneath the panel in the first place —
 * there is nothing left to occlude, and no coordinate hand-off is needed.
 *
 * jsdom does not hit-test: a `fireEvent.click` on a button reaches its
 * handler regardless of what CSS says is drawn on top of it, so a naive
 * click-based test would pass identically whether the nav is genuinely on
 * top or genuinely buried. These tests instead read the actual rendered
 * stacking relationship and the pointer-events pass-through that makes it
 * safe — the two facts a real browser's hit-test actually depends on.
 */

// Mock every dialog/panel LeftPanel can render EXCEPT HeroPanel and
// CombatMovePanel, which must be the real components for this file's
// assertions to mean anything.
vi.mock('./PartyPanel', () => ({ default: () => <div data-testid="party-panel" /> }));
vi.mock('./InventoryDialog', () => ({ default: () => <div data-testid="inventory-dialog" /> }));
vi.mock('./AccountDialog', () => ({ default: () => <div data-testid="account-dialog" /> }));
vi.mock('./SettingsDialog', () => ({ default: () => <div data-testid="audio-dialog" /> }));
vi.mock('./JournalDialog', () => ({ default: () => <div data-testid="journal-dialog" /> }));
vi.mock('./StatsPanel', () => ({ default: () => <div data-testid="stats-panel" /> }));
vi.mock('./SkillsPanel', () => ({ default: () => <div data-testid="skills-panel" /> }));
vi.mock('./CollapsibleRoomDescription', () => ({ default: () => <div data-testid="room-contents" /> }));
vi.mock('./ActionsPanel', () => ({ default: () => <div data-testid="actions-panel" /> }));
vi.mock('./InteractPanel', () => ({ default: () => <div data-testid="interact-panel" /> }));
vi.mock('./CombatLog', () => ({ default: () => <div data-testid="combat-log" /> }));
vi.mock('./CombatInputDialog', () => ({ default: () => <div data-testid="combat-input-dialog" /> }));
vi.mock('./FeedbackDialog', () => ({ default: () => <div data-testid="feedback-dialog" /> }));
vi.mock('./CooldownTray', () => ({ default: () => <div data-testid="cooldown-tray" /> }));
vi.mock('./HeatMeter', () => ({ default: () => <div data-testid="heat-meter" /> }));
vi.mock('./FleeButton', () => ({ default: () => <button data-testid="flee-button" /> }));
vi.mock('./SuggestedMovesPanel', () => ({ default: () => <div data-testid="suggested-moves-panel" /> }));
vi.mock('./ShopDialog', () => ({ default: () => <div data-testid="shop-dialog" /> }));
vi.mock('./CombatCheckDialog', () => ({ default: () => <div data-testid="combat-check-dialog" /> }));

const mockPlayer = { name: 'Jean', level: 1, hp: 100, max_hp: 100, inventory: [] };
const mockLocation = { name: 'Forest', description: 'Green trees.' };

/** One `available_options` entry, shaped like ApiCombatAdapter emits it. */
const makeCombatMove = (overrides = {}) => ({
  id: '0',
  name: 'Attack',
  display_name: 'Attack',
  description: 'A basic attack.',
  category: 'Offensive',
  fatigue_cost: 5,
  available: true,
  reason: null,
  targeted: false,
  viable_targets: [],
  requires_target_selection: false,
  cooldown_remaining: 0,
  cooldown_max: 0,
  ...overrides,
});

const renderInCombatWithMoveOpen = () => {
  const combat = {
    log: [],
    awaiting_input: true,
    input_type: 'move_selection',
    beat_states: [{ enemies: [] }],
    available_options: [makeCombatMove({ id: '1', name: 'Slash', category: 'Offensive' })],
  };
  const view = render(
    <LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />
  );
  // The real HeroPanel button, not a mock stand-in — CATEGORY_NAV_SELECTOR
  // is the same selector the (now-retired) occlusion hand-off used to
  // hit-test against, so using it here keeps this test honest about which
  // element is actually "the nav".
  const offensiveButton = [...document.querySelectorAll(CATEGORY_NAV_SELECTOR)]
    .find((b) => b.textContent === 'OFFENSIVE');
  fireEvent.click(offensiveButton);
  return { ...view, offensiveButton };
};

/**
 * Same shape, but `awaiting_input: false` — the enemy's turn. `input_type`
 * stays `'move_selection'` so `LeftPanel` still resolves `hasOffensiveMoves`
 * (and renders the OFFENSIVE button) purely from `available_options`,
 * independent of whose turn it is — the ONLY thing this varies is `isMyTurn`.
 */
const renderInCombatOnEnemyTurn = () => {
  const combat = {
    log: [],
    awaiting_input: false,
    input_type: 'move_selection',
    beat_states: [{ enemies: [] }],
    available_options: [makeCombatMove({ id: '1', name: 'Slash', category: 'Offensive' })],
  };
  render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);
  const offensiveButton = [...document.querySelectorAll(CATEGORY_NAV_SELECTOR)]
    .find((b) => b.textContent === 'OFFENSIVE');
  return { offensiveButton };
};

describe('category nav stacking over the move panel (issue #575)', () => {
  it('renders the hero stacking layer above CombatMovePanel, not below it', () => {
    const { container } = renderInCombatWithMoveOpen();

    const panel = container.querySelector(`.${GAME_PANEL_CLASS}`);
    const wrapper = screen.getByTestId('hero-panel-stacking-layer');
    expect(panel).not.toBeNull();

    // This is the assertion that actually distinguishes fixed from broken:
    // before #575 the wrapper was zIndex 50 and the panel was 100, so this
    // failed (50 is not greater than 100) — the panel painted over the nav.
    expect(Number(wrapper.style.zIndex)).toBeGreaterThan(Number(panel.style.zIndex));
    expect(Number(panel.style.zIndex)).toBe(COMBAT_MOVE_PANEL_Z_INDEX);
  });

  it('places the real nav button inside the raised stacking layer', () => {
    // Sanity check on the test itself: if HeroPanel's DOM ever moved outside
    // this wrapper, the z-index assertion above would still "pass" while
    // proving nothing.
    const { offensiveButton } = renderInCombatWithMoveOpen();
    const wrapper = screen.getByTestId('hero-panel-stacking-layer');

    expect(offensiveButton).not.toBeUndefined();
    expect(wrapper.contains(offensiveButton)).toBe(true);
  });

  it('makes the Hero Head Container click-through so a raised HeroPanel cannot swallow clicks meant for the panel below it', () => {
    renderInCombatWithMoveOpen();

    // Raising the whole wrapper (previous assertion) lifts every blank
    // region of HeroPanel above CombatMovePanel too. Without this,
    // elevating the nav would trade three dead tabs for some dead move
    // cards wherever the (now on top) Hero Head Container happens to
    // overlap them — a regression as bad as the bug being fixed.
    const headContainer = screen.getByTestId('hero-head-container');
    expect(headContainer.style.pointerEvents).toBe('none');
  });

  it('opts the real controls inside the Hero Head Container back in to pointer events', () => {
    const { offensiveButton } = renderInCombatWithMoveOpen();

    // The nav button is the one control this issue is actually about.
    expect(offensiveButton.style.pointerEvents).toBe('auto');

    // HP/Fatigue bars live in the same now-click-through container and are
    // independently interactive (hover/click/touch tooltip) — they must not
    // go dead as a side effect of #575's fix.
    expect(screen.getByTestId('hp-bar').style.pointerEvents).toBe('auto');
    expect(screen.getByTestId('fatigue-bar').style.pointerEvents).toBe('auto');
  });

  // A defect found in self-review while building the fix above, not in the
  // original bug report: opting the nav buttons and VitalBar back in to
  // `pointerEvents: 'auto'` unconditionally would have kept them clickable
  // even during the enemy's turn, when LeftPanel's wrapper already goes
  // `pointerEvents: 'none'` to disable and dim the whole hero. A stray click
  // on a category button then would not have opened anything immediately
  // (CombatMovePanel is separately gated on `isMyTurn`) but would have
  // staged `showCombatMoves`/`combatMovesCategory`, popping the panel open
  // unprompted the instant it became the player's turn again.
  it('keeps the nav buttons and vital bars inert during the enemy turn, matching the rest of the dimmed hero', () => {
    const { offensiveButton } = renderInCombatOnEnemyTurn();

    expect(offensiveButton).not.toBeUndefined();
    expect(offensiveButton.style.pointerEvents).toBe('none');
    expect(screen.getByTestId('hp-bar').style.pointerEvents).toBe('none');
    expect(screen.getByTestId('fatigue-bar').style.pointerEvents).toBe('none');
  });
});

describe('the stacking constants themselves (issue #575)', () => {
  it('defines the hero wrapper rank as an offset above the panel, not a second independent literal', () => {
    // Cheap and doesn't need a render: guards against a future edit that
    // changes one constant without the other. The DOM-level test above is
    // what proves the numbers actually reach the rendered style.
    expect(HERO_PANEL_STACKING_Z_INDEX).toBeGreaterThan(COMBAT_MOVE_PANEL_Z_INDEX);
  });
});
