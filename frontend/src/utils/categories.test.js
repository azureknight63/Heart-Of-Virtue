import { describe, it, expect } from 'vitest';
import { colors } from '../styles/theme';
import {
  MOVE_CATEGORY_COLOR,
  MOVE_CATEGORY_GLOW,
  MOVE_CATEGORY_ICON,
  categoryColor,
  categoryGlow,
  categoryIcon,
  CATEGORY_GROUPS,
  movesInGroup,
  groupHasMoves,
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

  describe('CATEGORY_GROUPS', () => {
    it('routes Mastery moves to the SPECIAL button', () => {
      expect(CATEGORY_GROUPS.Special).toEqual(['Mastery']);
    });

    it('makes MISC the catch-all for the low-volume categories', () => {
      expect(CATEGORY_GROUPS.Miscellaneous).toEqual(['Miscellaneous', 'Utility', 'Tactical']);
    });

    it('maps each category to exactly one group', () => {
      const mapped = Object.values(CATEGORY_GROUPS).flat();
      expect(new Set(mapped).size).toBe(mapped.length);
    });

    it('does not filter for categories the engine never emits', () => {
      const mapped = Object.values(CATEGORY_GROUPS).flat();
      expect(mapped).not.toContain('Special');
      expect(mapped).not.toContain('Spiritual');
      expect(mapped).not.toContain('Supernatural');
    });
  });

  describe('movesInGroup', () => {
    const moves = [
      { name: 'Slash', category: 'Offensive' },
      { name: 'Guard', category: 'Defensive' },
      { name: 'Check', category: 'Utility' },
      { name: 'Rest', category: 'Miscellaneous' },
      { name: 'War Cry', category: 'Mastery' },
      { name: "Reaper's Mark", category: 'Tactical' },
    ];

    it('collects every category mapped to the group', () => {
      expect(movesInGroup(moves, 'Miscellaneous').map((m) => m.name)).toEqual([
        'Check',
        'Rest',
        "Reaper's Mark",
      ]);
    });

    it('collects Mastery moves under the Special group', () => {
      expect(movesInGroup(moves, 'Special').map((m) => m.name)).toEqual(['War Cry']);
    });

    it('returns nothing for an unknown group', () => {
      expect(movesInGroup(moves, 'Nonexistent')).toEqual([]);
    });

    it('returns nothing when moves is not an array', () => {
      expect(movesInGroup(undefined, 'Offensive')).toEqual([]);
    });

    it('ignores null entries in the move list', () => {
      expect(movesInGroup([null, { category: 'Offensive' }], 'Offensive')).toHaveLength(1);
    });
  });

  describe('groupHasMoves', () => {
    it('is true when the group has at least one move', () => {
      expect(groupHasMoves([{ category: 'Mastery' }], 'Special')).toBe(true);
    });

    it('is false when no move belongs to the group', () => {
      expect(groupHasMoves([{ category: 'Offensive' }], 'Special')).toBe(false);
    });
  });
});
