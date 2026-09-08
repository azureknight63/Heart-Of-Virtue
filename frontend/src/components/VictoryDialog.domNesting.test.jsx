import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import VictoryDialog from './VictoryDialog';

/**
 * #565: the level-up banner nested one GameText inside another, and GameText
 * defaults to `as="p"`, so React logged
 *
 *   validateDOMNesting(...): <p> cannot appear as a descendant of <p>.
 *
 * on every victory that granted a level. Nothing looked broken — which is why
 * it survived — so the only honest assertion is on the warning itself.
 *
 * This lives in its OWN file on purpose. React records each nesting violation
 * once per process and never repeats it, so a console spy set up partway
 * through VictoryDialog.test.jsx sees nothing: an earlier render in that file
 * has already spent the warning. A dedicated file gets a fresh module graph,
 * and the render below is the first one in it.
 */
describe('VictoryDialog DOM nesting', () => {
  const endState = {
    message: 'Victory!',
    exp_gained: { Combat: 100 },
    items_dropped: [],
    level_ups: [{ old_level: 1, new_level: 2, points_awarded: 5 }],
    attribute_points_available: 5,
    attributes: {
      strength_base: 10,
      finesse_base: 10,
      speed_base: 10,
      endurance_base: 10,
      charisma_base: 10,
      intelligence_base: 10,
    },
  };

  it('logs no DOM-nesting warning when a level-up banner renders', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    try {
      render(
        <VictoryDialog
          endState={endState}
          onClose={vi.fn()}
          onAllocatePoints={vi.fn()}
        />
      );

      const nestingWarnings = consoleError.mock.calls
        .map((args) => args.map(String).join(' '))
        .filter((line) => /validateDOMNesting|cannot (?:appear|be a descendant)/i.test(line));

      expect(nestingWarnings, nestingWarnings.join('\n')).toEqual([]);
    } finally {
      consoleError.mockRestore();
    }
  });
});
