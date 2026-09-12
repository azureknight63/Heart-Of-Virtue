import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import HeroPanel from './HeroPanel';
import { CATEGORY_NAV_SELECTOR, CATEGORY_NAV_LABEL } from '../utils/categories';
import { makePlayer } from '../test/payloads';

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

const player = makePlayer();

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

  /**
   * The guard that makes the fixture above load-bearing.
   *
   * Until this existed the file rendered the real HeroPanel and then asserted
   * nothing about what it rendered, so the player fixture could name any field
   * it liked. It did: the literal this replaced carried `maxhp`/`maxfatigue`,
   * which no serializer emits and HeroPanel never reads (it reads `max_hp` and
   * `max_fatigue`). The bars fell through to the `?? 100` / `?? 150` defaults
   * HeroPanel applies when a vital is absent, so the fatigue bar silently
   * rendered 50 / 150 -- a payload the server cannot produce -- while every
   * assertion in this file stayed green.
   *
   * Every value below is deliberately off BOTH defaults, which is the only
   * thing that makes this non-vacuous: assert `max_hp: 100` and the test still
   * passes when the read is broken, because the fallback is also 100. That
   * coincidence is exactly what hid the drift on the HP bar.
   */
  it('reads the vitals off the wire field names, not the fallback defaults', () => {
    const { getByRole } = render(
      <HeroPanel
        player={makePlayer({ hp: 73, max_hp: 91, fatigue: 44, max_fatigue: 88 })}
        mode="combat"
        onCombatMoveClick={vi.fn()}
      />
    );

    expect(getByRole('progressbar', { name: /^HP/ })).toHaveAttribute('aria-label', 'HP: 73 / 91');
    expect(getByRole('progressbar', { name: /^Fatigue/ })).toHaveAttribute('aria-label', 'Fatigue: 44 / 88');
  });
});
