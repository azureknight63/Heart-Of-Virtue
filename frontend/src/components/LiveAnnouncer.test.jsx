import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import LiveAnnouncer from './LiveAnnouncer';

describe('LiveAnnouncer', () => {
  it('replaces the node when an identical string is announced again', () => {
    // The whole reason `seq` exists. A polite region announces a DOM change,
    // not a value: without a changing key, re-rendering the same text reuses
    // the same text node, React mutates nothing, and a screen reader stays
    // silent. "Jean misses" twice running has to be heard twice.
    const { container, rerender } = render(<LiveAnnouncer text="Jean misses!" seq={1} testId="a" />);
    const first = container.querySelector('[data-seq]');

    rerender(<LiveAnnouncer text="Jean misses!" seq={2} testId="a" />);
    const second = container.querySelector('[data-seq]');

    expect(second).not.toBe(first);
    expect(second).toHaveTextContent('Jean misses!');
  });

  it('is a polite atomic region that is not visible', () => {
    const { container } = render(<LiveAnnouncer text="hi" seq={1} testId="a" />);
    const region = container.querySelector('[data-testid="a"]');
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveAttribute('aria-atomic', 'true');
    expect(region.style.clipPath).toBe('inset(50%)');
  });

  it('renders no child for empty text, so nothing is announced on mount', () => {
    const { container } = render(<LiveAnnouncer text="" seq={0} testId="a" />);
    expect(container.querySelector('[data-seq]')).toBeNull();
  });
});
