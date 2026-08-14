import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// The module reads localStorage and the URL at import time, so each test that
// needs a different starting state re-imports it through vi.resetModules().
const freshImport = async () => {
  vi.resetModules();
  return import('./featureFlags');
};

// Overriding window.location leaks into later tests otherwise — and because
// the module snapshots the URL at import time, a leaked ?flags= would silently
// force flags on in tests that assert the default.
const setSearch = (search) => {
  Object.defineProperty(window, 'location', {
    value: { ...window.location, search },
    writable: true,
    configurable: true,
  });
};

describe('featureFlags', () => {
  beforeEach(() => {
    localStorage.clear();
    setSearch('');
  });

  afterEach(() => {
    localStorage.clear();
    setSearch('');
  });

  it('starts every registered flag at its declared default', async () => {
    const { FEATURE_FLAGS, getFlag } = await freshImport();
    for (const [name, flag] of Object.entries(FEATURE_FLAGS)) {
      expect(getFlag(name)).toBe(flag.default);
    }
  });

  it('persists a flag and reads it back on the next load', async () => {
    const first = await freshImport();
    first.setFlag('squareBattlefieldCells', true);
    expect(first.getFlag('squareBattlefieldCells')).toBe(true);

    const second = await freshImport();
    expect(second.getFlag('squareBattlefieldCells')).toBe(true);
  });

  it('resets flags back to their defaults and clears storage', async () => {
    const { setFlag, resetFlags, getFlag } = await freshImport();
    setFlag('squareBattlefieldCells', true);
    resetFlags();
    expect(getFlag('squareBattlefieldCells')).toBe(false);
    expect(localStorage.getItem('hovFeatureFlags')).toBeNull();
  });

  it('ignores unknown flag names on both read and write', async () => {
    const { setFlag, getFlag } = await freshImport();
    setFlag('notARealFlag', true);
    expect(getFlag('notARealFlag')).toBe(false);
    expect(localStorage.getItem('hovFeatureFlags')).toBeNull();
  });

  describe('untrusted stored blob', () => {
    // Stored flags are attacker-editable input, same as the retired
    // hov_local_autosave blob (issues #487/#489). None of these may reach a
    // component as anything but a boolean.
    it.each([
      ['malformed JSON', '{not json'],
      ['a JSON array', '[1,2,3]'],
      ['a JSON primitive', '"true"'],
      ['null', 'null'],
    ])('falls back to defaults for %s', async (_label, raw) => {
      localStorage.setItem('hovFeatureFlags', raw);
      const { getFlag } = await freshImport();
      expect(getFlag('squareBattlefieldCells')).toBe(false);
    });

    it('coerces a non-boolean value to false rather than passing it through', async () => {
      localStorage.setItem(
        'hovFeatureFlags',
        JSON.stringify({ squareBattlefieldCells: { evil: true } }),
      );
      const { getFlag } = await freshImport();
      expect(getFlag('squareBattlefieldCells')).toBe(false);
    });

    it('does not accept a flag inherited from the prototype chain', async () => {
      localStorage.setItem('hovFeatureFlags', '{"__proto__":{"squareBattlefieldCells":true}}');
      const { getFlag } = await freshImport();
      expect(getFlag('squareBattlefieldCells')).toBe(false);
    });

    it('refuses to parse an oversized blob', async () => {
      // Padded past the 4 KB cap with a key the loader ignores anyway; the
      // point is that the cap is checked before JSON.parse runs.
      localStorage.setItem(
        'hovFeatureFlags',
        JSON.stringify({ squareBattlefieldCells: true, pad: 'x'.repeat(5000) }),
      );
      const { getFlag } = await freshImport();
      expect(getFlag('squareBattlefieldCells')).toBe(false);
    });
  });

  it('forces a flag on from the ?flags= query parameter, overriding storage', async () => {
    localStorage.setItem('hovFeatureFlags', JSON.stringify({ squareBattlefieldCells: false }));
    setSearch('?flags=squareBattlefieldCells');

    const { getFlag } = await freshImport();
    expect(getFlag('squareBattlefieldCells')).toBe(true);
  });

  it('ignores unregistered names in the query parameter', async () => {
    setSearch('?flags=squareBattlefieldCells,bogusFlag');
    const { getFlag } = await freshImport();
    expect(getFlag('squareBattlefieldCells')).toBe(true);
    expect(getFlag('bogusFlag')).toBe(false);
  });

  describe('useFeatureFlag', () => {
    it('re-renders subscribers when the flag changes', async () => {
      const { useFeatureFlag, setFlag } = await freshImport();
      const { result } = renderHook(() => useFeatureFlag('squareBattlefieldCells'));

      expect(result.current).toBe(false);
      act(() => setFlag('squareBattlefieldCells', true));
      expect(result.current).toBe(true);
    });

    it('unsubscribes on unmount so a later write does not touch a dead component', async () => {
      const { useFeatureFlag, setFlag } = await freshImport();
      const { unmount } = renderHook(() => useFeatureFlag('squareBattlefieldCells'));
      unmount();
      expect(() => setFlag('squareBattlefieldCells', true)).not.toThrow();
    });
  });
});
