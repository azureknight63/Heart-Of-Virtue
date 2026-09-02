import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import SpriteToken from './SpriteToken';
import { makeSpriteManifest } from '../test/payloads';

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

  it('mirrors the west row for an east facing', () => {
    render(<SpriteToken sprite={sprite} facing="E" />);
    const token = screen.getByTestId('sprite-token');
    expect(token.dataset.mirror).toBe('1');
    expect(token.style.transform).toBe('scaleX(-1)');
  });

  it('advances and loops idle frames on its clock', () => {
    render(<SpriteToken sprite={sprite} clip="idle" />);
    const token = screen.getByTestId('sprite-token');
    expect(token.dataset.frame).toBe('0');
    act(() => vi.advanceTimersByTime(250));
    expect(token.dataset.frame).toBe('1');
    act(() => vi.advanceTimersByTime(250 * 3));
    expect(token.dataset.frame).toBe('0');
    expect(token.style.backgroundPosition).toBe('0% 0%');
  });

  it('holds the last frame of a one-shot clip', () => {
    render(<SpriteToken sprite={sprite} clip="death" facing="S" />);
    const token = screen.getByTestId('sprite-token');
    act(() => vi.advanceTimersByTime(2000));
    expect(token.dataset.frame).toBe('5');
    expect(token.style.backgroundPosition).toBe('100% 0%');
  });

  it('restarts from frame 0 when the clip changes', () => {
    const { rerender } = render(<SpriteToken sprite={sprite} clip="idle" />);
    act(() => vi.advanceTimersByTime(260));
    expect(screen.getByTestId('sprite-token').dataset.frame).toBe('1');
    rerender(<SpriteToken sprite={sprite} clip="attack" />);
    expect(screen.getByTestId('sprite-token').dataset.frame).toBe('0');
  });

  it('falls back to idle for a clip with no sheet, and to nothing without idle', () => {
    const partial = { clips: { idle: sprite.clips.idle } };
    render(<SpriteToken sprite={partial} clip="cast" />);
    expect(screen.getByTestId('sprite-token').dataset.clip).toBe('idle');
    const { container } = render(<SpriteToken sprite={{ clips: {} }} />);
    expect(container.querySelector('[data-testid="sprite-token"]')).toBeNull();
  });

  it('does not tick when paused or single-framed', () => {
    render(<SpriteToken sprite={sprite} clip="idle" running={false} />);
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByTestId('sprite-token').dataset.frame).toBe('0');
    const single = { clips: { idle: { file: 'sprites/x/idle.png', frames: 1, rows: 1 } } };
    render(<SpriteToken sprite={single} />);
    const tokens = screen.getAllByTestId('sprite-token');
    expect(tokens[1].style.backgroundPosition).toBe('0% 0%');
  });
});
