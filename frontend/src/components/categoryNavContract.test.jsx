import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import HeroPanel from './HeroPanel';
import { CATEGORY_NAV_SELECTOR, CATEGORY_NAV_LABEL } from '../utils/categories';

/**
 * The one guard that can actually fail on a HeroPanel rename.
 *
 * CombatMovePanel hands back clicks its flyout occludes by hit-testing
 * `CATEGORY_NAV_SELECTOR` against the live DOM (#557). Every other test of that
 * behaviour renders its OWN <nav> with the same label, so all of them would
 * stay green while the real nav drifted out from under the selector — a mock
 * agreeing with a mock, which CLAUDE.md names as this codebase's dominant bug
 * class. This one renders the REAL HeroPanel and asserts the real selector
 * finds real buttons.
 */
vi.mock('../hooks/useMobile', () => ({ default: () => false, useMobile: () => false }));

const player = { name: 'Jean', hp: 100, maxhp: 100, fatigue: 50, maxfatigue: 50, level: 1 };

describe('the combat category nav contract', () => {
  it('is found in the real HeroPanel by the selector CombatMovePanel uses', () => {
    render(<HeroPanel player={player} mode="combat" onCombatMoveClick={vi.fn()} />);

    const buttons = document.querySelectorAll(CATEGORY_NAV_SELECTOR);
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('derives both halves from one exported constant', () => {
    // Not a restatement of the literal: this asserts the selector is BUILT
    // from the label, so the two cannot drift even if the label is retuned.
    expect(CATEGORY_NAV_SELECTOR).toContain(CATEGORY_NAV_LABEL);
  });
});
