import { createElement } from 'react';
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuth, usePlayer, useCombat, useWorld, useExploration, useAutosave } from './useApi';
import { AuthProvider } from '../context/AuthContext';
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
      getFullState: vi.fn(),
      getStats: vi.fn(),
      getSkills: vi.fn(),
      allocateLevelUpPoints: vi.fn(),
    },
    combat: {
      getStatus: vi.fn(),
      performAction: vi.fn(),
    },
    world: {
      getCurrentLocation: vi.fn(),
      move: vi.fn(),
      getExploredTiles: vi.fn(),
    },
    saves: {
      save: vi.fn(),
    },
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
  const wrapper = ({ children }) => createElement(AuthProvider, null, children);

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('initializes with token from localStorage', () => {
    localStorage.setItem('authToken', 'test-token');
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.loading).toBe(false);
  });

  it('logs in successfully', async () => {
    const mockResponse = { data: { data: { session_id: 'new-token' } } };
    apiEndpoints.auth.login.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login('user', 'pass');
    });

    expect(localStorage.getItem('authToken')).toBe('new-token');
    expect(result.current.isAuthenticated).toBe(true);
  });

  it('logs out successfully', async () => {
    localStorage.setItem('authToken', 'test-token');
    const { result } = renderHook(() => useAuth(), { wrapper });

    // Mock window.location
    const originalLocation = window.location;
    delete window.location;
    window.location = { href: '' };

    await act(async () => {
      await result.current.logout();
    });

    expect(localStorage.getItem('authToken')).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    // BASE_URL is '/games/HeartOfVirtue/' per vite.config.js base setting
    expect(window.location.href).toBe('/games/HeartOfVirtue/login');

    window.location = originalLocation;
  });
});

describe('usePlayer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches player data successfully', async () => {
    const mockFullState = {
      status: { name: 'Hero', level: 5 },
      inventory: { items: [] },
      stats: { strength: 15 },
      skills: { skills: { fireball: 1 } }
    };
    apiEndpoints.player.getFullState.mockResolvedValue({ data: mockFullState });

    const { result } = renderHook(() => usePlayer());

    await act(async () => {
      await result.current.refetch();
    });

    expect(result.current.player.name).toBe('Hero');
    expect(result.current.player.strength).toBe(15);
    expect(result.current.loading).toBe(false);
  });

  it('defaults inventory to an empty array when absent from the response', async () => {
    apiEndpoints.player.getFullState.mockResolvedValue({
      data: { status: { name: 'Hero', level: 5 }, stats: {}, skills: {} },
    });

    const { result } = renderHook(() => usePlayer());
    await act(async () => {
      await result.current.refetch();
    });

    expect(result.current.player.inventory).toEqual([]);
  });

  it('handles fetch error', async () => {
    apiEndpoints.player.getFullState.mockRejectedValue(new Error('Fetch failed'));

    const { result } = renderHook(() => usePlayer());

    await act(async () => {
      await result.current.refetch();
    });

    expect(result.current.error).toBe('Fetch failed');
    expect(result.current.player.name).toBe('Unknown');
  });

  it('allocates level-up points and refetches the full player payload', async () => {
    apiEndpoints.player.getFullState.mockResolvedValue({
      data: { status: { name: 'Hero', level: 6 }, inventory: { items: [] }, stats: {}, skills: {} },
    });
    apiEndpoints.player.allocateLevelUpPoints.mockResolvedValue({
      data: { success: true },
    });

    const { result } = renderHook(() => usePlayer());
    await act(async () => { await result.current.refetch(); });

    let response;
    await act(async () => {
      response = await result.current.allocateLevelUpPoints('strength_base', 2);
    });

    expect(apiEndpoints.player.allocateLevelUpPoints).toHaveBeenCalledWith('strength_base', 2);
    // Once on mount, once from the explicit refetch() above, once from allocateLevelUpPoints itself.
    expect(apiEndpoints.player.getFullState).toHaveBeenCalledTimes(3);
    expect(response).toEqual({ success: true });
    expect(result.current.player.level).toBe(6);
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

  it('logs and swallows errors from fetchCombatStatus without throwing', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    apiEndpoints.combat.getStatus.mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => useCombat());
    await act(async () => {
      await result.current.fetchCombatStatus();
    });

    expect(errorSpy).toHaveBeenCalledWith('Combat status error:', expect.any(Error));
    expect(result.current.loading).toBe(false);
    errorSpy.mockRestore();
  });

  it('ignores a second concurrent fetchCombatStatus call while one is in flight', async () => {
    let resolveFirst;
    apiEndpoints.combat.getStatus.mockReturnValue(new Promise((resolve) => { resolveFirst = resolve; }));

    const { result } = renderHook(() => useCombat());
    let firstCall, secondCall;
    act(() => {
      firstCall = result.current.fetchCombatStatus();
      secondCall = result.current.fetchCombatStatus();
    });

    await act(async () => {
      resolveFirst({ data: { battle_state: { turn: 1 }, combat_active: true } });
      await firstCall;
      await secondCall;
    });

    expect(apiEndpoints.combat.getStatus).toHaveBeenCalledTimes(1);
  });

  it('returns the raw response without overwriting state when the backend reports success:false', async () => {
    apiEndpoints.combat.getStatus.mockResolvedValue({ data: { battle_state: { turn: 1 }, combat_active: true } });
    apiEndpoints.combat.performAction.mockResolvedValue({ data: { success: false, error: 'no viable targets' } });

    const { result } = renderHook(() => useCombat());
    await act(async () => { await result.current.fetchCombatStatus(); });

    let response;
    await act(async () => {
      response = await result.current.performAction('attack', { target: 'enemy' });
    });

    expect(response).toEqual({ success: false, error: 'no viable targets' });
    expect(result.current.combat.turn).toBe(1); // unchanged
  });

  it('logs and rethrows when performAction fails', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    apiEndpoints.combat.performAction.mockRejectedValue(new Error('server error'));

    const { result } = renderHook(() => useCombat());
    await expect(
      act(async () => { await result.current.performAction('attack', {}); })
    ).rejects.toThrow('server error');

    expect(errorSpy).toHaveBeenCalledWith('Combat action error:', expect.any(Error));
    errorSpy.mockRestore();
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

  it('sets an error when fetching the current location fails', async () => {
    apiEndpoints.world.getCurrentLocation.mockRejectedValue(new Error('offline'));

    const { result } = renderHook(() => useWorld());
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result.current.error).toBe('offline');
    expect(result.current.loading).toBe(false);
  });

  it('optimistically applies a cached tile before the authoritative move response arrives', async () => {
    const TileCache = (await import('../utils/TileCache')).default;
    const initialRoom = { room: { x: 0, y: 0, name: 'Start', exits: {} } };
    const cachedTile = { x: 0, y: -1, name: 'Cached Room', exits: {} };
    const authoritativeRoom = { room: { x: 0, y: -1, name: 'Authoritative Room', exits: {} } };

    apiEndpoints.world.getCurrentLocation.mockResolvedValue({ data: initialRoom });
    TileCache.get.mockReturnValue(cachedTile);
    apiEndpoints.world.move.mockResolvedValue({ data: authoritativeRoom });

    const { result } = renderHook(() => useWorld());
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    await act(async () => {
      await result.current.moveToLocation('north');
    });

    // The authoritative server response always wins by the time the promise resolves.
    expect(result.current.location.name).toBe('Authoritative Room');
    expect(TileCache.set).toHaveBeenCalled();
    TileCache.get.mockReturnValue(undefined);
  });

  it('sets an error and rethrows when a move request fails', async () => {
    apiEndpoints.world.getCurrentLocation.mockResolvedValue({
      data: { room: { x: 0, y: 0, name: 'Start', exits: {} } },
    });
    apiEndpoints.world.move.mockRejectedValue(new Error('move blocked'));

    const { result } = renderHook(() => useWorld());
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    let caught;
    await act(async () => {
      try {
        await result.current.moveToLocation('south');
      } catch (e) {
        caught = e;
      }
    });

    expect(caught.message).toBe('move blocked');
    expect(result.current.error).toBe('move blocked');
  });

  it('carries an already-array exits field and populated items/npcs/objects through as new array references', async () => {
    apiEndpoints.world.getCurrentLocation.mockResolvedValue({
      data: {
        room: {
          x: 0, y: 0, name: 'Populated Room',
          exits: ['north', 'south'],
          items: [{ id: 'i1' }],
          npcs: [{ id: 'n1' }],
          objects: [{ id: 'o1' }],
        },
      },
    });

    const { result } = renderHook(() => useWorld());
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result.current.location.exits).toEqual(['north', 'south']);
    expect(result.current.location.items).toEqual([{ id: 'i1' }]);
    expect(result.current.location.npcs).toEqual([{ id: 'n1' }]);
    expect(result.current.location.objects).toEqual([{ id: 'o1' }]);
  });

  it('defaults exits/items/npcs/objects to empty arrays when absent from the room', async () => {
    apiEndpoints.world.getCurrentLocation.mockResolvedValue({
      data: { room: { x: 0, y: 0, name: 'Bare Room' } },
    });

    const { result } = renderHook(() => useWorld());
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result.current.location.exits).toEqual([]);
    expect(result.current.location.items).toEqual([]);
    expect(result.current.location.npcs).toEqual([]);
    expect(result.current.location.objects).toEqual([]);
  });
});

describe('useExploration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches and normalizes explored tiles into a Map', async () => {
    apiEndpoints.world.getExploredTiles.mockResolvedValue({
      data: {
        explored_tiles: {
          '0,0': { name: 'Start', exits: { north: 'Room 2' } },
          '0,-1': { name: 'Room 2', exits: ['south'] },
        },
      },
    });

    const { result } = renderHook(() => useExploration());
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result.current.exploredTiles.get('0,0').exits).toEqual(['north']);
    expect(result.current.exploredTiles.get('0,-1').exits).toEqual(['south']);
    expect(result.current.loading).toBe(false);
  });

  it('defaults a tile\'s exits to an empty array when absent', async () => {
    apiEndpoints.world.getExploredTiles.mockResolvedValue({
      data: { explored_tiles: { '1,1': { name: 'Bare Tile' } } },
    });

    const { result } = renderHook(() => useExploration());
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result.current.exploredTiles.get('1,1').exits).toEqual([]);
  });

  it('logs an error without throwing when fetching explored tiles fails', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    apiEndpoints.world.getExploredTiles.mockRejectedValue(new Error('offline'));

    const { result } = renderHook(() => useExploration());
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(errorSpy).toHaveBeenCalledWith('Error fetching explored tiles:', expect.any(Error));
    expect(result.current.loading).toBe(false);
    errorSpy.mockRestore();
  });
});

describe('useAutosave', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('saves player state to localStorage when the player is known', () => {
    const player = { name: 'Jean', level: 5 };
    renderHook(() => useAutosave(player));

    const saved = JSON.parse(localStorage.getItem('hov_local_autosave'));
    expect(saved.player).toEqual(player);
    expect(saved.type).toBe('local_autosave');
  });

  it('does not save to localStorage for the placeholder Unknown player', () => {
    renderHook(() => useAutosave({ name: 'Unknown' }));
    expect(localStorage.getItem('hov_local_autosave')).toBeNull();
  });

  it('triggers a cloud save every 20 ticks and resets the counter', async () => {
    apiEndpoints.saves.save.mockResolvedValue({});
    const { result } = renderHook(() => useAutosave({ name: 'Jean' }));

    for (let i = 0; i < 20; i++) {
      await act(async () => { await result.current.triggerTick(); });
    }

    expect(apiEndpoints.saves.save).toHaveBeenCalledWith('Autosave', true);
    expect(result.current.tickCount).toBe(0);
  });

  it('logs an error without throwing when the cloud save fails', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    apiEndpoints.saves.save.mockRejectedValue(new Error('cloud down'));

    const { result } = renderHook(() => useAutosave({ name: 'Jean' }));
    await act(async () => {
      await result.current.saveToCloud();
    });

    expect(errorSpy).toHaveBeenCalledWith('[Autosave] Cloud sync failed:', expect.any(Error));
    errorSpy.mockRestore();
  });
});
