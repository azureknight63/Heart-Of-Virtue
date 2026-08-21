import { createElement } from 'react';
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuth, usePlayer, useCombat, useWorld, useExploration, useAutosave } from './useApi';
import { AuthProvider } from '../context/AuthContext';
import apiEndpoints from '../api/endpoints';
import {
  COMBAT_TOP_LEVEL_WHITELIST,
  makeCombatResponse,
  makeEnemy,
  makeRoomResponse,
} from '../test/payloads';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Read once: the whitelist assertion below inspects transformCombatData's own
// source because the helper is module-private and there is no other way to
// prove the copied key set without re-implementing it in the test.
const useApiSource = readFileSync(resolve(process.cwd(), 'src/hooks/useApi.js'), 'utf8');

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

  // `turn` is not a key any serializer emits — the pre-existing versions of the
  // two tests below asserted `combat.turn === 1` against a hand-written
  // `battle_state: { turn: 1 }`, i.e. they proved only that the object spread
  // in transformCombatData works. They would have stayed green if battle_state
  // had been dropped from the response entirely, or renamed. Both now drive a
  // realistic payload (src/test/payloads.js) and assert on the fields the
  // engine actually sends.
  it('spreads every battle_state field the adapter emits onto the combat object', async () => {
    apiEndpoints.combat.getStatus.mockResolvedValue({
      data: makeCombatResponse({ battle_state: { round: 3, beat: 7 } }),
    });

    const { result } = renderHook(() => useCombat());

    await act(async () => {
      await result.current.fetchCombatStatus();
    });

    expect(result.current.inCombat).toBe(true);
    // LeftPanel keys its move-clearing effect on exactly these two.
    expect(result.current.combat.round).toBe(3);
    expect(result.current.combat.beat).toBe(7);
    // Battlefield reads these two off the top-level combat object and passes
    // them to BattlefieldGrid; both live inside battle_state precisely so the
    // spread carries them (see the whitelist test below).
    expect(result.current.combat.combat_id).toBe('fight-0001');
    expect(result.current.combat.map_size).toBe(9);
    expect(result.current.combat.player.hp).toBe(100);
    expect(result.current.combat.enemies[0].id).toBe('enemy_1');
    expect(result.current.combat.awaiting_input).toBe(false);
  });

  it('performs combat action and applies the returned battle_state and log', async () => {
    apiEndpoints.combat.performAction.mockResolvedValue({
      data: makeCombatResponse({
        battle_state: { round: 2, beat: 4, enemies: [makeEnemy({ hp: 6 })] },
        log: ['Attack!'],
      }),
    });

    const { result } = renderHook(() => useCombat());

    await act(async () => {
      await result.current.performAction('attack', { target: 'enemy' });
    });

    expect(apiEndpoints.combat.performAction).toHaveBeenCalledWith('attack', { target: 'enemy' });
    expect(result.current.combat.round).toBe(2);
    expect(result.current.combat.beat).toBe(4);
    expect(result.current.combat.enemies[0].hp).toBe(6);
    expect(result.current.combat.log).toContain('Attack!');
  });

  it('drops top-level combat fields outside transformCombatData\'s whitelist', () => {
    // Documented trap (CLAUDE.md): transformCombatData spreads
    // data.battle_state and then copies a FIXED set of top-level keys.
    // Anything emitted at the top level and absent from that set never reaches
    // the client — this silently caused two of the six wire-drift bugs
    // (combat_id and map_size, both since moved into battle_state).
    //
    // Pinning it here means a future author who adds a top-level field and
    // forgets the whitelist sees a failing test naming the rule, instead of a
    // feature that quietly does nothing.
    const source = useApiSource;
    const transform = source.slice(
      source.indexOf('const transformCombatData'),
      source.indexOf('// Helper to transform location data')
    );
    const whitelisted = [...transform.matchAll(/^\s{2}(\w+):\s*data\./gm)].map((m) => m[1]);
    expect(new Set(whitelisted)).toEqual(new Set(COMBAT_TOP_LEVEL_WHITELIST));
    // battle_state is carried by the spread, not by a whitelist entry.
    expect(transform).toContain('...data.battle_state');
  });

  it('keeps combat_id stable across polls of one fight and changes it for a new fight', async () => {
    // combat_id identifies a FIGHT, not a call: BattlefieldGrid uses it to
    // reset the camera pan once per fight. A per-poll value would reset the
    // camera on every status poll; a missing one never resets it. Both are
    // wrong, so pin the property the client depends on.
    const { result } = renderHook(() => useCombat());

    apiEndpoints.combat.getStatus.mockResolvedValue({
      data: makeCombatResponse({ battle_state: { combat_id: 'fight-A', beat: 1 } }),
    });
    await act(async () => { await result.current.fetchCombatStatus(); });
    const first = result.current.combat.combat_id;
    expect(first).toBe('fight-A');

    // Same fight, next beat (and a reinforcement wave, which reinits the
    // adapter server-side but keeps the id).
    apiEndpoints.combat.getStatus.mockResolvedValue({
      data: makeCombatResponse({
        battle_state: { combat_id: 'fight-A', beat: 2, enemies: [makeEnemy(), makeEnemy({ id: 'enemy_2' })] },
      }),
    });
    await act(async () => { await result.current.fetchCombatStatus(); });
    expect(result.current.combat.combat_id).toBe(first);
    expect(result.current.combat.enemies).toHaveLength(2);

    // A genuinely new combat.
    apiEndpoints.combat.getStatus.mockResolvedValue({
      data: makeCombatResponse({ battle_state: { combat_id: 'fight-B', beat: 1 } }),
    });
    await act(async () => { await result.current.fetchCombatStatus(); });
    expect(result.current.combat.combat_id).toBe('fight-B');
  });

  it('applies a terminal HTTP response even when socket streaming is enabled', async () => {
    apiEndpoints.combat.performAction.mockResolvedValue({
      data: {
        combat_active: false,
        battle_state: { status: 'active', awaiting_input: false },
        end_state: { id: 'victory-1', status: 'victory' },
        log: ['Victory!'],
      },
    });

    const { result } = renderHook(() => useCombat());

    await act(async () => {
      await result.current.performAction('move', { move_id: 'Attack' });
    });

    expect(result.current.inCombat).toBe(false);
    expect(result.current.combat.end_state).toEqual({
      id: 'victory-1',
      status: 'victory',
    });
  });

  it('normalizes a terminal combat:ended payload into end state', () => {
    const { result } = renderHook(() => useCombat());

    act(() => {
      result.current.applyCombatState({
        id: 'victory-2',
        status: 'victory',
        message: 'Victory!',
      });
    });

    expect(result.current.inCombat).toBe(false);
    expect(result.current.combat.end_state).toEqual({
      id: 'victory-2',
      status: 'victory',
      message: 'Victory!',
    });
    expect(result.current.combat.awaiting_input).toBe(false);
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

/**
 * Wait for a hook's initial fetch effect to settle.
 *
 * Replaces `await act(async () => { await new Promise(r => setTimeout(r, 0)) })`,
 * which was repeated nine times in this file. That idiom flushes one macrotask
 * and hopes the effect finished inside it — it asserts nothing, and it silently
 * yields a half-loaded hook the moment a fetch grows a second await. Waiting on
 * `loading` turning false is both the real condition and a proof the effect ran.
 */
const settle = (result) => waitFor(() => expect(result.current.loading).toBe(false))

describe('useWorld', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('normalises the server exits dict into an array of direction names', async () => {
    // The wire shape is a dict (GameService._calculate_exits returns
    // direction -> {x, y}); every component downstream reads `exits` as an
    // array of names (MapGrid does `location.exits.includes(direction)` and
    // `exits.join(', ')`), so this transform is the whole seam. The fixture is
    // the real serializer shape, not `{ north: 'Room 2' }`.
    apiEndpoints.world.getCurrentLocation.mockResolvedValue({
      data: { room: makeRoomResponse({ name: 'Start' }) },
    });

    const { result } = renderHook(() => useWorld());
    await waitFor(() => expect(result.current.location).not.toBeNull());

    expect(result.current.location.name).toBe('Start');
    expect(result.current.location.exits).toEqual(['north', 'east']);
    expect(result.current.location.map_name).toBe('Dark Grotto');
  });

  it('moves to a new location', async () => {
    const initialRoom = { room: { x: 0, y: 0, name: 'Start', exits: { north: 'Room 2' } } };
    const nextRoom = { room: { x: 0, y: -1, name: 'Room 2', exits: { south: 'Start' } } };

    apiEndpoints.world.getCurrentLocation.mockResolvedValue({ data: initialRoom });
    apiEndpoints.world.move.mockResolvedValue({ data: nextRoom });

    const { result } = renderHook(() => useWorld());

    await settle(result);

    await act(async () => {
      await result.current.moveToLocation('north');
    });

    expect(result.current.location.name).toBe('Room 2');
    expect(apiEndpoints.world.move).toHaveBeenCalledWith('north');
  });

  it('sets an error when fetching the current location fails', async () => {
    apiEndpoints.world.getCurrentLocation.mockRejectedValue(new Error('offline'));

    const { result } = renderHook(() => useWorld());
    await settle(result);

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
    await settle(result);

    await act(async () => {
      await result.current.moveToLocation('north');
    });

    // The authoritative server response always wins by the time the promise resolves.
    expect(result.current.location.name).toBe('Authoritative Room');
    // The cache is READ for the optimistic hop and then WRITTEN with the
    // authoritative room keyed by its own coordinates. A bare
    // toHaveBeenCalled() passed even if the hop's stale tile were cached over
    // the real one, or filed under the wrong coordinates.
    expect(TileCache.get).toHaveBeenCalledWith(0, -1);
    // The LAST write must be the authoritative room, filed under its own
    // coordinates — a bare toHaveBeenCalled() passed even if the optimistic
    // stale tile were cached over the real one, or filed at the wrong x/y.
    // (fetchLocation also caches the starting room, hence "last", not "once".)
    expect(TileCache.set).toHaveBeenLastCalledWith(
      0, -1, expect.objectContaining({ name: 'Authoritative Room' })
    );
    expect(TileCache.prefetchAdjacent).toHaveBeenLastCalledWith(0, -1);
    TileCache.get.mockReturnValue(undefined);
  });

  it('sets an error and rethrows when a move request fails', async () => {
    apiEndpoints.world.getCurrentLocation.mockResolvedValue({
      data: { room: { x: 0, y: 0, name: 'Start', exits: {} } },
    });
    apiEndpoints.world.move.mockRejectedValue(new Error('move blocked'));

    const { result } = renderHook(() => useWorld());
    await settle(result);

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
    await settle(result);

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
    await settle(result);

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
    await settle(result);

    expect(result.current.exploredTiles.get('0,0').exits).toEqual(['north']);
    expect(result.current.exploredTiles.get('0,-1').exits).toEqual(['south']);
    expect(result.current.loading).toBe(false);
  });

  it('defaults a tile\'s exits to an empty array when absent', async () => {
    apiEndpoints.world.getExploredTiles.mockResolvedValue({
      data: { explored_tiles: { '1,1': { name: 'Bare Tile' } } },
    });

    const { result } = renderHook(() => useExploration());
    await settle(result);

    expect(result.current.exploredTiles.get('1,1').exits).toEqual([]);
  });

  it('logs an error without throwing when fetching explored tiles fails', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    apiEndpoints.world.getExploredTiles.mockRejectedValue(new Error('offline'));

    const { result } = renderHook(() => useExploration());
    await settle(result);

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

  it('triggers a cloud save every AUTOSAVE_TICK_THRESHOLD ticks and resets the counter', async () => {
    apiEndpoints.saves.save.mockResolvedValue({});
    const { result } = renderHook(() => useAutosave());

    // Threshold is 3: two ticks must not save yet.
    await act(async () => { await result.current.triggerTick(); });
    await act(async () => { await result.current.triggerTick(); });
    expect(apiEndpoints.saves.save).not.toHaveBeenCalled();

    await act(async () => { await result.current.triggerTick(); });

    expect(apiEndpoints.saves.save).toHaveBeenCalledWith('Autosave', true);
    expect(apiEndpoints.saves.save).toHaveBeenCalledTimes(1);
    expect(result.current.tickCount).toBe(0);
  });

  it('logs an error and calls onSaveError without throwing when the cloud save fails', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    apiEndpoints.saves.save.mockRejectedValue(new Error('cloud down'));
    const onSaveError = vi.fn();

    const { result } = renderHook(() => useAutosave({ onSaveError }));
    await act(async () => {
      await result.current.saveToCloud();
    });

    expect(errorSpy).toHaveBeenCalledWith('[Autosave] Cloud sync failed:', expect.any(Error));
    expect(onSaveError).toHaveBeenCalledWith(expect.any(Error));
    errorSpy.mockRestore();
  });

  it('does not fire an overlapping cloud save while one is already in flight', async () => {
    let resolveSave;
    apiEndpoints.saves.save.mockReturnValue(new Promise((resolve) => { resolveSave = resolve; }));
    const { result } = renderHook(() => useAutosave());

    let firstCall;
    let secondCall;
    await act(async () => {
      firstCall = result.current.saveToCloud();
      secondCall = result.current.saveToCloud();
    });

    expect(apiEndpoints.saves.save).toHaveBeenCalledTimes(1);

    resolveSave({});
    await act(async () => {
      await firstCall;
      await secondCall;
    });
  });
});
