import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LeftPanel from './LeftPanel';
import { GAME_PANEL_CLASS } from './GamePanel';
import { CATEGORY_NAV_SELECTOR } from '../utils/categories';
import { zIndex } from '../styles/theme';
import {
  makeAvailableOption,
  makeCombat,
  makeCombatant,
  makeLocation,
  makePassive,
  makePlayer,
  makeStatusEffect,
} from '../test/payloads';

/**
 * Issue #575 — with a category open, a tall stack of move cards could cover
 * three of the visible combat nav tabs (INVENTORY, MISC and DEFENSIVE, the
 * tabs that share screen space with the card list). The fix is a
 * stacking-order change; the reasoning lives on `zIndex` in styles/theme.js
 * and on the stacking layer in LeftPanel.jsx.
 *
 * jsdom does not hit-test: a `fireEvent.click` on a button reaches its
 * handler regardless of what CSS says is drawn on top of it, so a naive
 * click-based test would pass identically whether the nav is genuinely on
 * top or genuinely buried. These tests instead read the two rendered facts a
 * real browser's hit-test depends on — the stacking relationship, and the
 * pointer-events pass-through that keeps the raised layer from swallowing
 * clicks meant for the panel beneath it.
 */

// Every component LeftPanel renders directly, EXCEPT HeroPanel and
// CombatMovePanel, which must be the real components for this file's
// assertions to mean anything. (BaseDialog is imported only for
// MODAL_BACKGROUND_PROPS and stays real.) Add a line when LeftPanel renders
// another.
vi.mock('./AbortMoveControl', () => ({ default: () => null }));
vi.mock('./PartyPanel', () => ({ default: () => null }));
vi.mock('./InventoryDialog', () => ({ default: () => null }));
vi.mock('./AccountDialog', () => ({ default: () => null }));
vi.mock('./SettingsDialog', () => ({ default: () => null }));
vi.mock('./JournalDialog', () => ({ default: () => null }));
vi.mock('./StatsPanel', () => ({ default: () => null }));
vi.mock('./SkillsPanel', () => ({ default: () => null }));
vi.mock('./CollapsibleRoomDescription', () => ({ default: () => null }));
vi.mock('./ActionsPanel', () => ({ default: () => null }));
vi.mock('./InteractPanel', () => ({ default: () => null }));
vi.mock('./CombatLog', () => ({ default: () => null }));
vi.mock('./CombatInputDialog', () => ({ default: () => null }));
vi.mock('./FeedbackDialog', () => ({ default: () => null }));
vi.mock('./CooldownTray', () => ({ default: () => null }));
vi.mock('./HeatMeter', () => ({ default: () => null }));
vi.mock('./FleeButton', () => ({ default: () => null }));
vi.mock('./SuggestedMovesPanel', () => ({ default: () => null }));
vi.mock('./ShopDialog', () => ({ default: () => null }));
vi.mock('./CombatCheckDialog', () => ({ default: () => null }));

const basePlayer = makePlayer();
const baseLocation = makeLocation();

/**
 * The tabs to probe: INVENTORY went dead under a tall flyout; OFFENSIVE, over
 * the panel's header chrome, survived. Both must behave the same now.
 *
 * OFFENSIVE is also the category this file opens a panel from, so it is named
 * once -- it appears in the probe list, in the render helper and in an
 * individual assertion, the same reason the test ids above are named once.
 */
const OPENED_CATEGORY_LABEL = 'OFFENSIVE';
const COMBAT_PROBE_LABELS = [OPENED_CATEGORY_LABEL, 'INVENTORY'];
const EXPLORATION_PROBE_LABELS = ['ATTRIBUTES', 'INVENTORY'];

// The test ids this file probes, each named once: they appear both inside
// the two arrays below and on their own in individual assertions, so an id
// renamed in HeroPanel had two places here to miss.
const HP_BAR_ID = 'hp-bar';
const FATIGUE_BAR_ID = 'fatigue-bar';
const PASSIVES_COLUMN_ID = 'passives-column';
const STATUS_COLUMN_ID = 'status-effects-column';
const MOBILE_EFFECT_ROW_ID = 'mobile-effect-row';

/** HeroPanel's two VitalBars, which are controls in their own right. */
const VITAL_BAR_TEST_IDS = [HP_BAR_ID, FATIGUE_BAR_ID];

/** The combatant payload that makes both icon surfaces render. */
const combatantWithEffects = () => makeCombatant({
  passives: [makePassive()],
  status_effects: [makeStatusEffect()],
});

/**
 * HeroPanel's hover-only icon surfaces, which carry no click handler: the two
 * desktop columns, and the single row the mobile layout renders instead.
 */
const HOVER_ONLY_TEST_IDS = [PASSIVES_COLUMN_ID, STATUS_COLUMN_ID, MOBILE_EFFECT_ROW_ID];

/**
 * The inline values that keep the pass-through: unset (inherits the layer's
 * `none`) or `none` itself. Anything else — `auto`, `all`, `visiblePainted` —
 * re-arms hit-testing on that element.
 */
const CLICK_THROUGH = ['', 'none'];

/**
 * The REAL nav button with this label, through the exported selector, so a
 * renamed nav fails loudly here rather than matching a stand-in.
 */
const findNavButton = (label) => {
  const button = [...document.querySelectorAll(CATEGORY_NAV_SELECTOR)]
    .find((el) => el.textContent === label);
  if (!button) throw new Error(`no category nav button labelled ${label}`);
  return button;
};

const stackingLayer = () => screen.getByTestId('hero-panel-stacking-layer');

/**
 * Renders LeftPanel mid-combat. On the player's turn it also opens the
 * OFFENSIVE category so CombatMovePanel is mounted (LeftPanel mounts it only
 * on the player's turn). `combatPlayer` is the CombatantSerializer payload
 * LeftPanel merges over the `player` prop in combat — the only wire that
 * carries `passives` and `status_effects`. `isMobile` picks the layout: the
 * icon surfaces differ between the two (two columns vs one row), and both
 * sit inside the raised layer.
 */
const renderInCombat = ({ awaitingInput = true, combatPlayer, isMobile = false } = {}) => {
  const combat = makeCombat({
    awaiting_input: awaitingInput,
    // Stays 'move_selection' in both turns so LeftPanel resolves
    // `hasOffensiveMoves` purely from `available_options`; `awaiting_input`
    // is the only thing that varies between the player's and enemy's turn.
    input_type: 'move_selection',
    available_options: [makeAvailableOption({ id: '1', name: 'Slash', category: 'Offensive' })],
    ...(combatPlayer ? { player: combatPlayer } : {}),
  });
  const view = render(
    <LeftPanel player={basePlayer} location={baseLocation} mode="combat" combat={combat} isMobile={isMobile} />
  );
  if (awaitingInput) fireEvent.click(findNavButton(OPENED_CATEGORY_LABEL));
  return view;
};

/**
 * Whether `el` is a surface allowed to opt back in to pointer events inside
 * the layer: a real nav button, a vital bar, or anything inside a hover-only
 * icon surface.
 */
const mayOptBackIn = (el) =>
  el.matches(CATEGORY_NAV_SELECTOR)
  || VITAL_BAR_TEST_IDS.includes(el.dataset.testid)
  || HOVER_ONLY_TEST_IDS.some((id) => el.closest(`[data-testid="${id}"]`) !== null);

/** Every element inside the stacking layer whose inline value re-arms hit-testing. */
const optedInElements = () => [...stackingLayer().querySelectorAll('*')]
  .filter((el) => !CLICK_THROUGH.includes(el.style.pointerEvents));

/** The nav buttons under `labels` and both vital bars, live or inert. */
const expectControls = (labels, { live }) => {
  const expectedPointerEvents = live ? 'auto' : 'none';
  for (const label of labels) {
    const button = findNavButton(label);
    expect(button.style.pointerEvents).toBe(expectedPointerEvents);
    if (live) expect(button).not.toBeDisabled();
    else expect(button).toBeDisabled();
  }
  for (const id of VITAL_BAR_TEST_IDS) {
    expect(screen.getByTestId(id).style.pointerEvents).toBe(expectedPointerEvents);
  }
};

describe('category nav stacking over the move panel (issue #575)', () => {
  it('ranks the hero stacking layer above CombatMovePanel', () => {
    const { container } = renderInCombat();

    // The one GamePanel here is CombatMovePanel: every other consumer
    // (StatsPanel, SkillsPanel, InteractPanel) is mocked to null above.
    const panels = container.querySelectorAll(`.${GAME_PANEL_CLASS}`);
    expect(panels).toHaveLength(1);
    const [movePanel] = panels;
    const layer = stackingLayer();

    // Before #575 the layer was 50 and the panel 100 — the panel painted
    // over the nav. Each element is pinned to its theme token, and the scale
    // test below pins the tokens' order, so a number hard-coded on either
    // element fails here as soon as it drifts from its token.
    expect(Number(movePanel.style.zIndex)).toBe(zIndex.combatMovePanel);
    expect(Number(layer.style.zIndex)).toBe(zIndex.heroStackingLayer);
  });

  it('places the real nav buttons inside the raised stacking layer', () => {
    // If HeroPanel's DOM ever moved outside this layer, the z-index
    // assertion above would still pass while proving nothing.
    renderInCombat();
    for (const label of COMBAT_PROBE_LABELS) {
      expect(stackingLayer().contains(findNavButton(label))).toBe(true);
    }
  });

  it.each([
    ['desktop', false],
    ['mobile', true],
  ])('makes every raised surface click-through in the %s layout, except the controls and the hover-only icon surfaces', (_layout, isMobile) => {
    // With effects on the wire in both layouts, so the icon surfaces, the
    // exception that is not a gated control, are actually in the sweep.
    renderInCombat({
      isMobile,
      combatPlayer: combatantWithEffects(),
    });

    // Raising the layer lifts ALL of HeroPanel's blank chrome above the
    // panel — the layer's own box, HeroPanel's padding ring, the head
    // container, the portrait — and a click on any of it would target that
    // element and never reach a move card underneath. jsdom cannot hit-test,
    // so this pins the pass-through the way CSS resolves it: the layer and
    // HeroPanel's root set 'none' explicitly (pointer-events inherits), and
    // every element inside the layer either keeps that or is one of the
    // surfaces allowed to opt back in.
    expect(stackingLayer().style.pointerEvents).toBe('none');
    expect(screen.getByTestId('hero-panel-root').style.pointerEvents).toBe('none');

    const optedIn = optedInElements();
    for (const el of optedIn) {
      expect(mayOptBackIn(el), `${el.tagName}[${el.dataset.testid ?? ''}] opts back in`).toBe(true);
    }
    // The live controls are among them, so the sweep is known to have
    // reached the surfaces it is filtering.
    expect(optedIn).toContain(findNavButton(OPENED_CATEGORY_LABEL));
    expect(optedIn).toContain(screen.getByTestId(HP_BAR_ID));
    // And the surface only THIS layout renders, so the mobile case cannot
    // quietly become a second copy of the desktop one if `isMobile` stops
    // reaching HeroPanel.
    expect(optedIn).toContain(
      screen.getByTestId(isMobile ? MOBILE_EFFECT_ROW_ID : PASSIVES_COLUMN_ID)
    );
  });

  it("opts the real controls back in on the player's turn", () => {
    renderInCombat();
    // HP/Fatigue bars are independently interactive (hover/click/touch
    // tooltip) — they must not go dead as a side effect of #575's fix.
    expectControls(COMBAT_PROBE_LABELS, { live: true });
  });

  it('keeps the exploration nav live — the pass-through is unconditional, only the opt-in is gated', () => {
    render(<LeftPanel player={basePlayer} location={baseLocation} mode="exploration" />);

    expect(stackingLayer().style.pointerEvents).toBe('none');
    expectControls(EXPLORATION_PROBE_LABELS, { live: true });
  });

  // Opting the nav buttons and VitalBar back in unconditionally would keep
  // them live during the enemy's turn, when LeftPanel dims the whole hero. A
  // stray click on a category button would stage `showCombatMoves`, popping
  // the panel open unprompted the instant it became the player's turn again
  // — and pointer-events alone leaves the buttons keyboard-reachable.
  it('makes the nav buttons and vital bars inert during the enemy turn', () => {
    renderInCombat({ awaitingInput: false });

    expect(stackingLayer().style.pointerEvents).toBe('none');
    expectControls(COMBAT_PROBE_LABELS, { live: false });
  });

  it('leaves the passive and status icon columns hoverable during the enemy turn, as before #575', () => {
    renderInCombat({
      awaitingInput: false,
      combatPlayer: combatantWithEffects(),
    });

    // Hover tooltips with no click handler: deliberately not gated on
    // `interactive` (see HOVER_ONLY_POINTER_EVENTS in HeroPanel.jsx). The
    // headings render only over a non-empty list, so they show the fixture's
    // effects reached the columns.
    const passives = screen.getByTestId(PASSIVES_COLUMN_ID);
    const statuses = screen.getByTestId(STATUS_COLUMN_ID);
    expect(within(passives).getByText('PASSIVES')).toBeInTheDocument();
    expect(within(statuses).getByText('STATUS')).toBeInTheDocument();
    expect(passives.style.pointerEvents).toBe('auto');
    expect(statuses.style.pointerEvents).toBe('auto');
  });
});

describe('the stacking scale (issue #575)', () => {
  it('orders the hero layer above the panel and below the dialog layer', () => {
    expect(zIndex.heroStackingLayer).toBeGreaterThan(zIndex.combatMovePanel);
    // Live HUD controls must never paint over a blocking modal; BaseDialog's
    // default rank reads the same token.
    expect(zIndex.heroStackingLayer).toBeLessThan(zIndex.dialog);
    // theme.js says the 1500 and 2000 literal tiers sit between these two;
    // that only means anything while the two are in this order.
    expect(zIndex.dialog).toBeLessThan(zIndex.raisedDialog);
  });
});
