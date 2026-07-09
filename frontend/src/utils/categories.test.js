import { describe, it, expect } from 'vitest';
import { colors } from '../styles/theme';
import {
  MOVE_CATEGORY_COLOR,
  MOVE_CATEGORY_GLOW,
  MOVE_CATEGORY_ICON,
  categoryColor,
  categoryGlow,
  categoryIcon,
} from './categories';

describe('categories', () => {
  describe('categoryColor', () => {
    it('returns the mapped color for a known category', () => {
      expect(categoryColor('Offensive')).toBe(MOVE_CATEGORY_COLOR.Offensive);
    });

    it('falls back to the muted text color for an unknown category', () => {
      expect(categoryColor('Nonexistent')).toBe(colors.text.muted);
    });
  });

  describe('categoryGlow', () => {
    it('returns the mapped glow for a known category', () => {
      expect(categoryGlow('Special')).toBe(MOVE_CATEGORY_GLOW.Special);
    });

    it('falls back to transparent for an unknown category', () => {
      expect(categoryGlow('Nonexistent')).toBe('transparent');
    });
  });

  describe('categoryIcon', () => {
    it('returns the mapped icon for a known category', () => {
      expect(categoryIcon('Maneuver')).toBe(MOVE_CATEGORY_ICON.Maneuver);
    });

    it('falls back to the default icon for an unknown category', () => {
      expect(categoryIcon('Nonexistent')).toBe('◈');
    });
  });
});
