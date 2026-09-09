import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import useJournal, { JOURNAL_LOAD_FAILED } from './useJournal';
import { player as playerApi } from '../api/endpoints';

vi.mock('../api/endpoints', () => ({
    player: { getJournal: vi.fn() },
}));

const JOURNAL = { objectives: [{ key: 'k', text: 'Cross the river.' }], completed: [], log: [] };

beforeEach(() => {
    vi.clearAllMocks();
    playerApi.getJournal.mockResolvedValue({ data: { success: true, journal: JOURNAL } });
});

describe('useJournal', () => {
    it('fetches once on mount and exposes the payload', async () => {
        const { result } = renderHook(() => useJournal());

        expect(result.current.isLoading).toBe(true);
        await waitFor(() => expect(result.current.isLoading).toBe(false));

        expect(result.current.journal).toEqual(JOURNAL);
        expect(result.current.error).toBe('');
        expect(playerApi.getJournal).toHaveBeenCalledTimes(1);
    });

    it('surfaces a transport failure as prose', async () => {
        playerApi.getJournal.mockRejectedValueOnce(new Error('server down'));
        const { result } = renderHook(() => useJournal());

        await waitFor(() => expect(result.current.error).toBe(JOURNAL_LOAD_FAILED));
        expect(result.current.journal).toBeNull();
    });

    it('prefers the API error prose over the generic fallback', async () => {
        playerApi.getJournal.mockRejectedValueOnce({
            response: { data: { error: 'Session expired.' } },
        });
        const { result } = renderHook(() => useJournal());

        await waitFor(() => expect(result.current.error).toBe('Session expired.'));
    });

    it('clears a previous error when a reload succeeds', async () => {
        playerApi.getJournal.mockRejectedValueOnce(new Error('server down'));
        const { result } = renderHook(() => useJournal());
        await waitFor(() => expect(result.current.error).toBe(JOURNAL_LOAD_FAILED));

        await act(async () => { await result.current.reload(); });

        expect(result.current.error).toBe('');
        expect(result.current.journal).toEqual(JOURNAL);
    });

    it('stops loading even when the request fails', async () => {
        // A stuck `isLoading` hides both the error and the retry button.
        playerApi.getJournal.mockRejectedValueOnce(new Error('server down'));
        const { result } = renderHook(() => useJournal());

        await waitFor(() => expect(result.current.isLoading).toBe(false));
    });

    it('treats a payload with no journal key as empty rather than crashing', async () => {
        playerApi.getJournal.mockResolvedValue({ data: {} });
        const { result } = renderHook(() => useJournal());

        await waitFor(() => expect(result.current.isLoading).toBe(false));
        expect(result.current.journal).toBeNull();
        expect(result.current.error).toBe('');
    });

    it('keeps a stable reload identity so a consumer effect cannot loop', async () => {
        // `reload` is the effect's own dependency; a fresh identity per render
        // would refetch forever.
        const { result, rerender } = renderHook(() => useJournal());
        await waitFor(() => expect(result.current.isLoading).toBe(false));
        const first = result.current.reload;

        rerender();

        expect(result.current.reload).toBe(first);
        expect(playerApi.getJournal).toHaveBeenCalledTimes(1);
    });
});
