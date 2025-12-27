import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuth, usePlayer, useCombat, useWorld } from './useApi';
import apiEndpoints from '../api/endpoints';

vi.mock('../api/endpoints', () => ({
  default: {
    auth: {
      login: vi.fn(),
      logout: vi.fn(),
      register: vi.fn(),
    },
    player: {
      getStatus: vi.fn(),
      getInventory: vi.fn(),
      getStats: vi.fn(),
      getSkills: vi.fn(),
    },
    combat: {
      getStatus: vi.fn(),
      performAction: vi.fn(),
    },
    world: {
      getCurrentLocation: vi.fn(),
      move: vi.fn(),
    }
  }
}));

vi.mock('../utils/TileCache', () => ({
  default: {
    set: vi.fn(),
    get: vi.fn(),
    prefetchAdjacent: vi.fn(),
  }
}));

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('initializes with token from localStorage', () => {
    localStorage.setItem('authToken', 'test-token');
    const { result } = renderHook(() => useAuth());
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.loading).toBe(false);
  });

  it('logs in successfully', async () => {
    const mockResponse = { data: { data: { session_id: 'new-token' } } };
    apiEndpoints.auth.login.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useAuth());
    
    await act(async () => {
      await result.current.login('user', 'pass');
    });

    expect(localStorage.getItem('authToken')).toBe('new-token');
    expect(result.current.isAuthenticated).toBe(true);
  });

  it('logs out successfully', async () => {
    localStorage.setItem('authToken', 'test-token');
    const { result } = renderHook(() => useAuth());

    // Mock window.location
    const originalLocation = window.location;
    delete window.location;
    window.location = { href: '' };

    await act(async () => {
      await result.current.logout();
    });

    expect(localStorage.getItem('authToken')).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(window.location.href).toBe('/login');

    window.location = originalLocation;
  });
});

describe('usePlayer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches player data successfully', async () => {
    apiEndpoints.player.getStatus.mockResolvedValue({ data: { status: { name: 'Hero', level: 5 } } });
    apiEndpoints.player.getInventory.mockResolvedValue({ data: { inventory: { items: [] } } });
    apiEndpoints.player.getStats.mockResolvedValue({ data: { stats: { strength: 15 } } });
    apiEndpoints.player.getSkills.mockResolvedValue({ data: { skills: { fireball: 1 } } });

    const { result } = renderHook(() => usePlayer());

    await act(async () => {
      await result.current.refetch();
    });

    expect(result.current.player.name).toBe('Hero');
    expect(result.current.player.strength).toBe(15);
    expect(result.current.loading).toBe(false);
  });

  it('handles fetch error', async () => {
    apiEndpoints.player.getStatus.mockRejectedValue(new Error('Fetch failed'));

    const { result } = renderHook(() => usePlayer());

    await act(async () => {
      await result.current.refetch();
    });

    expect(result.current.error).toBe('Fetch failed');
    expect(result.current.player.name).toBe('Unknown');
  });
});

describe('useCombat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches combat status', async () => {
    const mockCombat = { battle_state: { turn: 1 }, combat_active: true };
    apiEndpoints.combat.getStatus.mockResolvedValue({ data: mockCombat });

    const { result } = renderHook(() => useCombat());

    await act(async () => {
      await result.current.fetchCombatStatus();
    });

    expect(result.current.inCombat).toBe(true);
    expect(result.current.combat.turn).toBe(1);
  });

  it('performs combat action', async () => {
    const mockResponse = { data: { battle_state: { turn: 2 }, combat_active: true, log: ['Attack!'] } };
    apiEndpoints.combat.performAction.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useCombat());

    await act(async () => {
      await result.current.performAction('attack', { target: 'enemy' });
    });

    expect(result.current.combat.turn).toBe(2);
    expect(result.current.combat.log).toContain('Attack!');
  });
});

describe('useWorld', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches current location', async () => {
    const mockRoom = { room: { x: 0, y: 0, name: 'Start', exits: { north: 'Room 2' } } };
    apiEndpoints.world.getCurrentLocation.mockResolvedValue({ data: mockRoom });

    const { result } = renderHook(() => useWorld());

    // Wait for initial useEffect
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result.current.location.name).toBe('Start');
    expect(result.current.location.exits).toContain('north');
  });

  it('moves to a new location', async () => {
    const initialRoom = { room: { x: 0, y: 0, name: 'Start', exits: { north: 'Room 2' } } };
    const nextRoom = { room: { x: 0, y: -1, name: 'Room 2', exits: { south: 'Start' } } };
    
    apiEndpoints.world.getCurrentLocation.mockResolvedValue({ data: initialRoom });
    apiEndpoints.world.move.mockResolvedValue({ data: nextRoom });

    const { result } = renderHook(() => useWorld());

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    await act(async () => {
      await result.current.moveToLocation('north');
    });

    expect(result.current.location.name).toBe('Room 2');
    expect(apiEndpoints.world.move).toHaveBeenCalledWith('north');
  });
});
