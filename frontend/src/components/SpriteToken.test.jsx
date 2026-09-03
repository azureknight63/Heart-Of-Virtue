import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import SpriteToken from './SpriteToken';
import { makeSpriteManifest } from '../test/payloads';
import { CLIP_FPS } from '../utils/sprites';

const IDLE_MS = 1000 / CLIP_FPS.idle;

describe('SpriteToken', () => {
  const sprite = makeSpriteManifest().sprites.jean;

  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('draws the requested clip and facing from the strip', () => {
    render(<SpriteToken sprite={sprite} clip="walk" facing="W" />);
    const token = screen.getByTestId('sprite-token');
    expect(token.dataset.clip).toBe('walk');
    expect(token.dataset.row).toBe('1');
    expect(token.dataset.mirror).toBe('0');
    expect(token.style.backgroundImage).toContain('sprites/jean/walk.png');
    expect(token.style.backgroundSize).toBe('600% 300%');
    expect(token.style.backgroundPosition).toBe('0% 50%');
  });

  it('mirrors the west row for an east facing, degrees included', () => {
    render(<SpriteToken sprite={sprite} facing={90} />);
    const token = screen.getByTestId('sprite-token');
    expect(token.dataset.mirror).toBe('1');
    expect(token.style.transform).toBe('scaleX(-1)');
  });

  it('advances and loops idle frames on its clock', () => {
    render(<SpriteToken sprite={sprite} clip="idle" />);
    const token = screen.getByTestId('sprite-token');
    expect(token.dataset.frame).toBe('0');
    act(() => vi.advanceTimersByTime(IDLE_MS));
    expect(token.dataset.frame).toBe('1');
    act(() => vi.advanceTimersByTime(IDLE_MS * 3));
    expect(token.dataset.frame).toBe('0');
    expect(token.style.backgroundPosition).toBe('0% 0%');
  });

  it('runs faster at a higher combat speed', () => {
    render(<SpriteToken sprite={sprite} clip="idle" speed={2} />);
    act(() => vi.advanceTimersByTime(IDLE_MS / 2 + 5));
    expect(screen.getByTestId('sprite-token').dataset.frame).toBe('1');
  });

  it('holds the last frame of a one-shot clip and stops ticking', () => {
    const clear = vi.spyOn(globalThis, 'clearInterval');
    render(<SpriteToken sprite={sprite} clip="death" facing="S" />);
    const token = screen.getByTestId('sprite-token');
    act(() => vi.advanceTimersByTime(2000));
    expect(token.dataset.frame).toBe('5');
    expect(token.style.backgroundPosition).toBe('100% 0%');
    expect(clear).toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    clear.mockRestore();
  });

  it('keeps a looping clip ticking', () => {
    render(<SpriteToken sprite={sprite} clip="walk" />);
    act(() => vi.advanceTimersByTime(2000));
    expect(vi.getTimerCount()).toBe(1);
  });

  it('restarts from frame 0 when the clip changes', () => {
    const { rerender } = render(<SpriteToken sprite={sprite} clip="idle" />);
    act(() => vi.advanceTimersByTime(IDLE_MS + 10));
    expect(screen.getByTestId('sprite-token').dataset.frame).toBe('1');
    rerender(<SpriteToken sprite={sprite} clip="attack" />);
    expect(screen.getByTestId('sprite-token').dataset.frame).toBe('0');
  });

  it('falls back to idle for a missing clip', () => {
    const partial = { clips: { idle: sprite.clips.idle } };
    render(<SpriteToken sprite={partial} clip="cast" />);
    expect(screen.getByTestId('sprite-token').dataset.clip).toBe('idle');
  });

  it('draws nothing without an idle strip', () => {
    const { container } = render(<SpriteToken sprite={{ clips: {} }} />);
    expect(container.querySelector('[data-testid="sprite-token"]')).toBeNull();
  });

  it('draws nothing when the only strip has an unsafe path', () => {
    const unsafe = { clips: { idle: { file: '../x.png', frames: 2, rows: 3 } } };
    const { container } = render(<SpriteToken sprite={unsafe} clip="dance" />);
    expect(container.querySelector('[data-testid="sprite-token"]')).toBeNull();
  });

  it('does not tick when paused', () => {
    render(<SpriteToken sprite={sprite} clip="idle" running={false} />);
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByTestId('sprite-token').dataset.frame).toBe('0');
  });

  it('clamps absurd frame and row counts', () => {
    const odd = { clips: { idle: { file: 'sprites/x/idle.png', frames: 'Infinity', rows: 0 } } };
    const { container } = render(<SpriteToken sprite={odd} rows={['south', 'west', 'north']} />);
    const token = container.querySelector('[data-testid="sprite-token"]');
    expect(token.style.backgroundPosition).toBe('0% 0%');
    expect(token.style.backgroundSize).toBe('100% 300%');
    const many = { clips: { idle: { file: 'sprites/x/idle.png', frames: 1000, rows: 3 } } };
    const big = render(<SpriteToken sprite={many} />).container.querySelector('[data-testid="sprite-token"]');
    expect(big.style.backgroundSize).toBe('6400% 300%');
  });
});
