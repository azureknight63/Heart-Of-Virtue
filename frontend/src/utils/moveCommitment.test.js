import { describe, it, expect } from 'vitest';
import {
  STAGE_KEYS,
  getStageBeats,
  totalStageBeats,
  formatBeats,
  maxTotalStageBeats,
} from './moveCommitment';

describe('moveCommitment', () => {
  describe('STAGE_KEYS', () => {
    it('lists the four engine stages in prep/execute/recoil/cooldown order', () => {
      expect(STAGE_KEYS).toEqual(['prep', 'execute', 'recoil', 'cooldown']);
    });
  });

  describe('getStageBeats', () => {
    it('reads the named wire fields off move.stage_beats', () => {
      const move = { stage_beats: { prep: 40, execute: 1, recoil: 5, cooldown: 55 } };
      expect(getStageBeats(move)).toEqual({ prep: 40, execute: 1, recoil: 5, cooldown: 55 });
    });

    it('preserves float beat values', () => {
      const move = { stage_beats: { prep: 0, execute: 3.5, recoil: 0, cooldown: 12 } };
      expect(getStageBeats(move)).toEqual({ prep: 0, execute: 3.5, recoil: 0, cooldown: 12 });
    });

    it('preserves zero beat values (not treated as missing)', () => {
      const move = { stage_beats: { prep: 0, execute: 0, recoil: 0, cooldown: 0 } };
      expect(getStageBeats(move)).toEqual({ prep: 0, execute: 0, recoil: 0, cooldown: 0 });
    });

    it('defaults every stage to 0 when stage_beats is missing entirely', () => {
      expect(getStageBeats({})).toEqual({ prep: 0, execute: 0, recoil: 0, cooldown: 0 });
      expect(getStageBeats(undefined)).toEqual({ prep: 0, execute: 0, recoil: 0, cooldown: 0 });
    });

    it('defaults non-numeric or negative fields to 0 rather than propagating garbage', () => {
      const move = { stage_beats: { prep: 'lots', execute: -5, recoil: null, cooldown: 10 } };
      expect(getStageBeats(move)).toEqual({ prep: 0, execute: 0, recoil: 0, cooldown: 10 });
    });
  });

  describe('totalStageBeats', () => {
    it('sums all four stages', () => {
      expect(totalStageBeats({ prep: 40, execute: 1, recoil: 5, cooldown: 55 })).toBe(101);
    });

    it('handles float sums', () => {
      expect(totalStageBeats({ prep: 0, execute: 3.5, recoil: 0, cooldown: 12 })).toBe(15.5);
    });

    it('is 0 when every stage is 0', () => {
      expect(totalStageBeats({ prep: 0, execute: 0, recoil: 0, cooldown: 0 })).toBe(0);
    });
  });

  describe('formatBeats', () => {
    it('renders whole numbers without a decimal', () => {
      expect(formatBeats(101)).toBe('101');
      expect(formatBeats(0)).toBe('0');
    });

    it('renders fractional beats to one decimal place', () => {
      expect(formatBeats(15.5)).toBe('15.5');
      expect(formatBeats(15.449)).toBe('15.4');
    });
  });

  describe('maxTotalStageBeats', () => {
    it('returns the largest total across the list — the shared scale', () => {
      const moves = [
        { name: 'Attack', stage_beats: { prep: 4, execute: 1, recoil: 1, cooldown: 4 } }, // 10
        { name: 'AimedShot', stage_beats: { prep: 25, execute: 1, recoil: 2, cooldown: 8 } }, // 36
        { name: 'BloodOfMartyrs', stage_beats: { prep: 40, execute: 1, recoil: 5, cooldown: 55 } }, // 101
      ];
      expect(maxTotalStageBeats(moves)).toBe(101);
    });

    it('is 0 for an empty or non-array input', () => {
      expect(maxTotalStageBeats([])).toBe(0);
      expect(maxTotalStageBeats(undefined)).toBe(0);
      expect(maxTotalStageBeats(null)).toBe(0);
    });

    it('is 0 when no move in the list declares stage_beats', () => {
      expect(maxTotalStageBeats([{ name: 'Legacy' }, { name: 'AlsoLegacy' }])).toBe(0);
    });
  });
});
