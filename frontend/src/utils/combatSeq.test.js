import { describe, it, expect } from 'vitest';
import { classifySeq } from './combatSeq';

describe('classifySeq', () => {
  it('accepts the first event', () => {
    expect(classifySeq(null, 1)).toBe('next');
  });
  it('flags a duplicate/older seq', () => {
    expect(classifySeq(5, 5)).toBe('duplicate');
    expect(classifySeq(5, 3)).toBe('duplicate');
  });
  it('flags a gap', () => {
    expect(classifySeq(5, 7)).toBe('gap');
  });
  it('accepts the next consecutive seq', () => {
    expect(classifySeq(5, 6)).toBe('next');
  });

  describe('malformed seq', () => {
    // Treating any of these as 'next' would let the consumer store a non-number
    // as lastSeq, permanently breaking gap AND duplicate detection.
    it.each([
      ['undefined', undefined],
      ['null', null],
      ['NaN', NaN],
      ['a numeric string', '6'],
    ])('classifies %s as a gap so the consumer resyncs', (_label, badSeq) => {
      expect(classifySeq(5, badSeq)).toBe('gap');
      expect(classifySeq(null, badSeq)).toBe('gap');
    });
  });
});
