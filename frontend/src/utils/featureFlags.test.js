import { describe, it, expect } from 'vitest';
import { combatSocketEnabled } from './featureFlags';

describe('combatSocketEnabled', () => {
  it('follows the backend capability when enabled', () => {
    expect(combatSocketEnabled({ combat_socket_streaming: true })).toBe(true);
  });

  it('stays off when the backend capability is disabled or unavailable', () => {
    expect(combatSocketEnabled({ combat_socket_streaming: false })).toBe(false);
    expect(combatSocketEnabled(null)).toBe(false);
    expect(combatSocketEnabled({})).toBe(false);
  });
});
