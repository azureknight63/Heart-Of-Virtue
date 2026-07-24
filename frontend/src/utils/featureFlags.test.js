import { describe, it, expect, afterEach, vi } from 'vitest';
import { combatSocketEnabled } from './featureFlags';

describe('combatSocketEnabled', () => {
  afterEach(() => vi.unstubAllEnvs());

  it('is off by default / when unset', () => {
    vi.stubEnv('VITE_COMBAT_SOCKET', '');
    expect(combatSocketEnabled()).toBe(false);
  });

  it('is on for "1" or "true"', () => {
    vi.stubEnv('VITE_COMBAT_SOCKET', '1');
    expect(combatSocketEnabled()).toBe(true);
    vi.stubEnv('VITE_COMBAT_SOCKET', 'true');
    expect(combatSocketEnabled()).toBe(true);
  });

  it('is off for other values', () => {
    vi.stubEnv('VITE_COMBAT_SOCKET', 'no');
    expect(combatSocketEnabled()).toBe(false);
  });
});
