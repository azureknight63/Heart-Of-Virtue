import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import useDefeatRecovery, {
  LOAD_SAVE_FAILED,
  START_OVER_FAILED,
} from './useDefeatRecovery';
import apiEndpoints from '../api/endpoints';
import { makeSaveRow } from '../test/payloads';

vi.mock('../api/endpoints', () => ({
  default: {
    saves: {
      list: vi.fn(),
      load: vi.fn(),
      newGame: vi.fn(),
    },
  },
}));

/**
 * Render the hook and wait for its save-list fetch to settle.
 *
 * The flag alone is not enough to wait on: `isLoadingSaves` STARTS false, so
 * a `toBe(false)` would resolve before the effect ran if the hook ever set it
 * after an await. Waiting on the request having been made as well means this
 * helper cannot pass on a fetch that has not happened.
 */
const renderSettled = async (options) => {
  const view = renderHook(() => useDefeatRecovery(options));
  await waitFor(() => {
    expect(apiEndpoints.saves.list).toHaveBeenCalled();
    expect(view.result.current.isLoadingSaves).toBe(false);
  });
  return view;
};

describe('useDefeatRecovery', () => {
  // The one place the failure copy is written out. Every other assertion in
  // this suite and in DefeatDialog.test.jsx reads these by name, which proves
  // the right message reached the player but cannot notice a reword -- the
  // constant would move on both sides at once. This is the reword's tripwire,
  // and the three sentences have to stay distinguishable from each other: the
  // dialog shows exactly one of them, and which one tells the player whether
  // their run changed.
  it('says what actually went wrong, in words the player can act on', () => {
    expect(LOAD_SAVE_FAILED).toBe('Failed to load save.');
    expect(START_OVER_FAILED).toBe('Failed to start over.');
  });

  beforeEach(() => {
    vi.clearAllMocks();
    apiEndpoints.saves.list.mockResolvedValue({ data: { saves: [makeSaveRow()] } });
  });

  it('refuses LOAD with no save selected, without sending a request', async () => {
    // DefeatDialog disables LOAD until a save is selected, so this guard is
    // only reachable by another caller of the hook.
    apiEndpoints.saves.list.mockResolvedValue({ data: { saves: [] } });
    const { result } = await renderSettled();

    await act(async () => {
      await result.current.loadSave();
    });

    expect(result.current.error).toBe('Select a save to load.');
    expect(apiEndpoints.saves.load).not.toHaveBeenCalled();
  });

  it('says the run changed but the screen did not refresh when the parent rejects', async () => {
    // The request succeeded, so the run HAS changed server-side; blaming the
    // request ("Failed to start over.") would tell the player the opposite.
    apiEndpoints.saves.newGame.mockResolvedValue({ data: { success: true } });
    const onRunChanged = vi.fn().mockRejectedValue(new Error('refetch failed'));
    const { result } = await renderSettled({ onRunChanged });

    await act(async () => {
      await result.current.startOver();
    });

    expect(apiEndpoints.saves.newGame).toHaveBeenCalledTimes(1);
    expect(onRunChanged).toHaveBeenCalledTimes(1);
    // Nothing shown, and specifically NOT the request's own failure copy:
    // the run did change, so blaming the request would be a lie, and there is
    // nothing the player could do with the truth either.
    expect(result.current.error).toBe('');
    expect(result.current.isSubmitting).toBe(false);
  });

  it('names WHICH exit is in flight, so START OVER cannot relabel LOAD', async () => {
    // Issue #587 twice over: the fix for it made START OVER a /game/new call,
    // and a single shared `isSubmitting` then had that call render the LOAD
    // button as 'LOADING…'. Both flags are read by DefeatDialog — one
    // disables both buttons, the other labels only LOAD — so they have to be
    // observed mid-flight, which is what the deferred resolvers below buy.
    let finishNewGame;
    apiEndpoints.saves.newGame.mockReturnValue(
      new Promise((resolve) => { finishNewGame = () => resolve({ data: { success: true } }); }),
    );
    let finishLoad;
    apiEndpoints.saves.load.mockReturnValue(
      new Promise((resolve) => { finishLoad = () => resolve({ data: { success: true } }); }),
    );
    const { result } = await renderSettled({ onRunChanged: vi.fn() });

    let startOverCall;
    act(() => { startOverCall = result.current.startOver(); });
    await waitFor(() => expect(result.current.isSubmitting).toBe(true));
    // START OVER disables LOAD without claiming to be it.
    expect(result.current.isRestoringSave).toBe(false);
    await act(async () => { finishNewGame(); await startOverCall; });
    expect(result.current.isSubmitting).toBe(false);

    let loadCall;
    act(() => { loadCall = result.current.loadSave(); });
    await waitFor(() => expect(result.current.isRestoringSave).toBe(true));
    expect(result.current.isSubmitting).toBe(true);
    await act(async () => { finishLoad(); await loadCall; });
    expect(result.current.isRestoringSave).toBe(false);
  });

  it("reports the request's own failure, and never calls the parent, when the request fails", async () => {
    apiEndpoints.saves.newGame.mockRejectedValue(new Error('New game failed'));
    const onRunChanged = vi.fn();
    const { result } = await renderSettled({ onRunChanged });

    await act(async () => {
      await result.current.startOver();
    });

    expect(result.current.error).toBe('New game failed');
    expect(onRunChanged).not.toHaveBeenCalled();
    expect(result.current.isSubmitting).toBe(false);
  });
});
