import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { classifySeq, BeatQueueController } from './beatQueue';

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
});

describe('BeatQueueController', () => {
  let played;
  let sfx;
  let drained;
  let controller;

  const beat = (seq, animation = 'attack') => ({
    seq,
    web_animation: animation,
    sfx: [{ index: 0, kind: 'impact', outcome: 'hit' }],
  });

  beforeEach(() => {
    vi.useFakeTimers();
    played = [];
    sfx = [];
    drained = 0;
    controller = new BeatQueueController({
      playBeat: (b) => played.push(b.seq),
      playSfx: (cue) => sfx.push({ cue, at: Date.now() }),
      beatSfxFor: () => ['attack_hit'],
      durationForBeat: () => 800,
      durationForCue: () => 200,
      onDrain: () => {
        drained += 1;
      },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('plays a single beat and drains after its hold', () => {
    controller.push(beat(1));
    expect(played).toEqual([1]); // plays immediately
    expect(controller.isAnimating).toBe(true);
    expect(drained).toBe(0);

    vi.advanceTimersByTime(800);
    expect(drained).toBe(1);
    expect(controller.isAnimating).toBe(false);
  });

  it('paces multiple beats one hold apart (no overrun)', () => {
    controller.push(beat(1));
    controller.push(beat(2));
    controller.push(beat(3));
    // Only the first plays right away; the rest are queued.
    expect(played).toEqual([1]);

    vi.advanceTimersByTime(800);
    expect(played).toEqual([1, 2]);
    vi.advanceTimersByTime(800);
    expect(played).toEqual([1, 2, 3]);
    expect(drained).toBe(0);

    vi.advanceTimersByTime(800);
    expect(drained).toBe(1);
  });

  it('fires SFX for the played beat', () => {
    controller.push(beat(1));
    // impact SFX scheduled at offset 0
    vi.advanceTimersByTime(0);
    expect(sfx.map((s) => s.cue)).toEqual(['attack_hit']);
  });

  it('clear() drops the queue and cancels pending SFX (reconnect suppression)', () => {
    controller.push(beat(1));
    controller.push(beat(2));
    controller.clear();
    expect(controller.isAnimating).toBe(false);

    // Advancing time must not play queued beats nor their SFX.
    const playedBefore = played.length;
    const sfxBefore = sfx.length;
    vi.advanceTimersByTime(5000);
    expect(played.length).toBe(playedBefore);
    expect(sfx.length).toBe(sfxBefore);
    expect(drained).toBe(0);
  });

  it('resumes playing when new beats arrive after a drain', () => {
    controller.push(beat(1));
    vi.advanceTimersByTime(800);
    expect(drained).toBe(1);

    controller.push(beat(2));
    expect(played).toEqual([1, 2]);
    vi.advanceTimersByTime(800);
    expect(drained).toBe(2);
  });
});
