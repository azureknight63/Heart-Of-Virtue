import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import useAdminAnalytics, { ANALYTICS_LOAD_FAILED, ANALYTICS_WINDOWS, DEFAULT_DAYS } from './useAdminAnalytics';
import { admin as adminApi } from '../api/endpoints';

vi.mock('../api/endpoints', () => ({
    admin: { getAnalytics: vi.fn() },
}));

const REPORT = { window_days: 30, players: { total_accounts: 4 } };

beforeEach(() => {
    vi.clearAllMocks();
    adminApi.getAnalytics.mockResolvedValue({ data: { success: true, report: REPORT } });
});

describe('useAdminAnalytics', () => {
    it('defaults to a window the page offers', () => {
        // Otherwise no window button shows as selected on first load.
        expect(ANALYTICS_WINDOWS).toContain(DEFAULT_DAYS);
    });

    it('fetches the default window on mount', async () => {
        const { result } = renderHook(() => useAdminAnalytics());
        expect(result.current.isLoading).toBe(true);
        await waitFor(() => expect(result.current.isLoading).toBe(false));
        expect(adminApi.getAnalytics).toHaveBeenCalledWith(DEFAULT_DAYS);
        expect(result.current.report).toEqual(REPORT);
        expect(result.current.notFound).toBe(false);
        expect(result.current.isAdmin).toBe(true);
        expect(result.current.error).toBe('');
    });

    it('treats a successful response with no report as a failure', async () => {
        adminApi.getAnalytics.mockResolvedValueOnce({ data: { success: true } });
        const { result } = renderHook(() => useAdminAnalytics());
        await waitFor(() => expect(result.current.error).toBe(ANALYTICS_LOAD_FAILED));
        expect(result.current.isAdmin).toBe(false);
    });

    it('refetches when the window changes', async () => {
        const { result } = renderHook(() => useAdminAnalytics());
        await waitFor(() => expect(result.current.isLoading).toBe(false));
        act(() => result.current.selectDays(7));
        await waitFor(() => expect(adminApi.getAnalytics).toHaveBeenCalledWith(7));
        expect(result.current.days).toBe(7);
    });

    it('clears the old report as soon as the window changes', async () => {
        let resolveNext;
        const { result } = renderHook(() => useAdminAnalytics());
        await waitFor(() => expect(result.current.report).toEqual(REPORT));
        adminApi.getAnalytics.mockImplementationOnce(() => new Promise((r) => { resolveNext = r; }));
        act(() => result.current.selectDays(7));
        // Still loading the 7-day window: the 30-day numbers must be gone.
        expect(result.current.report).toBeNull();
        await act(async () => { resolveNext({ data: { report: { window_days: 7 } } }); });
        expect(result.current.report).toEqual({ window_days: 7 });
    });

    it('selecting the current window does nothing', async () => {
        const { result } = renderHook(() => useAdminAnalytics());
        await waitFor(() => expect(result.current.isLoading).toBe(false));
        act(() => result.current.selectDays(DEFAULT_DAYS));
        expect(result.current.report).toEqual(REPORT);
        expect(adminApi.getAnalytics).toHaveBeenCalledTimes(1);
    });

    it('treats a 404 as "not an admin", not as an error', async () => {
        adminApi.getAnalytics.mockRejectedValueOnce({ response: { status: 404, data: { error: 'Not found' } } });
        const { result } = renderHook(() => useAdminAnalytics());
        await waitFor(() => expect(result.current.isLoading).toBe(false));
        expect(result.current.notFound).toBe(true);
        expect(result.current.isAdmin).toBe(false);
        expect(result.current.error).toBe('');
        expect(result.current.report).toBeNull();
    });

    it('surfaces other failures as prose', async () => {
        adminApi.getAnalytics.mockRejectedValueOnce(new Error('network down'));
        const { result } = renderHook(() => useAdminAnalytics());
        await waitFor(() => expect(result.current.error).toBe(ANALYTICS_LOAD_FAILED));
        expect(result.current.isLoading).toBe(false);
    });

    it('prefers the server message', async () => {
        adminApi.getAnalytics.mockRejectedValueOnce({ response: { status: 500, data: { error: 'Report unavailable' } } });
        const { result } = renderHook(() => useAdminAnalytics());
        await waitFor(() => expect(result.current.error).toBe('Report unavailable'));
    });

    it('clears an error on a successful reload', async () => {
        adminApi.getAnalytics.mockRejectedValueOnce(new Error('network down'));
        const { result } = renderHook(() => useAdminAnalytics());
        await waitFor(() => expect(result.current.error).toBe(ANALYTICS_LOAD_FAILED));
        await act(async () => { await result.current.reload(); });
        expect(result.current.error).toBe('');
        expect(result.current.report).toEqual(REPORT);
    });

    it('ignores a response that lands after the window changed', async () => {
        let resolveFirst;
        adminApi.getAnalytics
            .mockImplementationOnce(() => new Promise((r) => { resolveFirst = r; }))
            .mockResolvedValueOnce({ data: { report: { window_days: 7 } } });
        const { result } = renderHook(() => useAdminAnalytics());
        act(() => result.current.selectDays(7));
        await waitFor(() => expect(result.current.report).toEqual({ window_days: 7 }));
        await act(async () => { resolveFirst({ data: { report: { window_days: 30 } } }); });
        expect(result.current.report).toEqual({ window_days: 7 });
    });
});
