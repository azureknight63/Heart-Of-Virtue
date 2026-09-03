import { renderHook } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useStableTerrain } from './useStableTerrain';
import { makeTerrain } from '../test/payloads';

const renderStable = (terrain, id) => renderHook(
  (p) => useStableTerrain(p.terrain, p.id),
  { initialProps: { terrain, id } }
);

describe('useStableTerrain', () => {
  it('keeps the first reference while the fight and shape are unchanged', () => {
    const first = makeTerrain();
    const { result, rerender } = renderStable(first, 'fight-1');
    expect(result.current).toBe(first);
    rerender({ terrain: makeTerrain(), id: 'fight-1' });
    expect(result.current).toBe(first);
  });

  it('adopts a new payload when the fight or the grid shape changes', () => {
    const first = makeTerrain();
    const { result, rerender } = renderStable(first, 'fight-1');
    const wider = makeTerrain({ width: 13 });
    rerender({ terrain: wider, id: 'fight-1' });
    expect(result.current).toBe(wider);
    const next = makeTerrain();
    rerender({ terrain: next, id: 'fight-2' });
    expect(result.current).toBe(next);
  });

  it('treats a region change as a new grid and holds through a missing id', () => {
    const first = makeTerrain();
    const { result, rerender } = renderStable(first, 'fight-1');
    const elsewhere = makeTerrain({ region: 'grondia', region_label: 'Grondia' });
    rerender({ terrain: elsewhere, id: 'fight-1' });
    expect(result.current).toBe(elsewhere);
    rerender({ terrain: makeTerrain({ region: 'grondia', region_label: 'Grondia' }), id: undefined });
    expect(result.current).not.toBe(elsewhere);
    const held = result.current;
    rerender({ terrain: makeTerrain({ region: 'grondia', region_label: 'Grondia' }), id: undefined });
    expect(result.current).toBe(held);
  });

  it('passes null through and recovers afterwards', () => {
    const { result, rerender } = renderStable(null, 'fight-1');
    expect(result.current).toBeNull();
    const t = makeTerrain();
    rerender({ terrain: t, id: 'fight-1' });
    expect(result.current).toBe(t);
    rerender({ terrain: null, id: 'fight-1' });
    expect(result.current).toBeNull();
  });
});
