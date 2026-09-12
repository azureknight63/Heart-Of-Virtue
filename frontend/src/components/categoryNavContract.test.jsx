import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import HeroPanel from './HeroPanel';
import { CATEGORY_NAV_SELECTOR, CATEGORY_NAV_LABEL } from '../utils/categories';
import { makePlayer } from '../test/payloads';

/**
 * The direct guard on HeroPanel's nav identity.
 *
 * LeftPanel.modalBackground.test.jsx mocks HeroPanel with a stand-in nav
 * carrying this label, so it would stay green while the real nav drifted out
 * from under the selector — a mock agreeing with a mock, which CLAUDE.md
 * names as this codebase's dominant bug class. This one renders the REAL
 * HeroPanel in combat and asserts the real selector finds the real category
 * buttons; the stacking-order tests
 * (`LeftPanel.categoryNavStacking.test.jsx`) are the selector's other
 * consumer.
 *
 * It lives in its own file rather than inside HeroPanel.test.jsx because the
 * claim is about a contract BETWEEN modules — the selector in
 * utils/categories.js and the markup in HeroPanel.jsx — and a reader chasing
 * the selector should find its guard by name, not by reading a component
 * suite that covers thirty other things.
 */
describe('the combat category nav contract', () => {
  it('is found in the real HeroPanel by the exported selector', () => {
    render(<HeroPanel player={makePlayer()} inCombat hasOffensiveMoves onOffensiveClick={vi.fn()} />);

    const labels = [...document.querySelectorAll(CATEGORY_NAV_SELECTOR)].map((b) => b.textContent);
    expect(labels).toContain('OFFENSIVE');
  });

  it('derives both halves from one exported constant', () => {
    // Not a restatement of the literal: this asserts the selector is BUILT
    // from the label, so the two cannot drift even if the label is retuned.
    expect(CATEGORY_NAV_SELECTOR).toContain(CATEGORY_NAV_LABEL);
  });
});
