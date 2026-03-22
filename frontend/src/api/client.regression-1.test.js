// Regression: ISSUE-001 — API client base URL resolves to wrong path under Vite base
// Found by /qa on 2026-03-22
// Report: .gstack/qa-reports/qa-report-localhost-3000-2026-03-22.md
//
// When VITE_API_URL is unset, the fallback used `${BASE_URL}api` which evaluated
// to /games/HeartOfVirtue/api. The Vite dev proxy only intercepts /api/* paths,
// so all API calls returned 404. Fixed to use '/api' as the hardcoded fallback.

import { describe, it, expect, vi } from 'vitest';
import axios from 'axios';

const { mockRequestUse, mockResponseUse } = vi.hoisted(() => ({
  mockRequestUse: vi.fn(),
  mockResponseUse: vi.fn(),
}));

vi.mock('axios', () => {
  const mockAxiosInstance = {
    interceptors: {
      request: { use: mockRequestUse },
      response: { use: mockResponseUse }
    },
    defaults: { headers: { common: {} } }
  };
  return {
    default: {
      create: vi.fn().mockReturnValue(mockAxiosInstance)
    }
  };
});

import apiClient from './client';

describe('ISSUE-001 regression: API base URL', () => {
  it('uses /api as base URL when VITE_API_URL is not set', () => {
    // The create call must use baseURL '/api', not '/games/HeartOfVirtue/api'
    const createCall = axios.create.mock.calls[0][0];
    expect(createCall.baseURL).toBe('/api');
    expect(createCall.baseURL).not.toContain('/games/');
    expect(createCall.baseURL).not.toContain('HeartOfVirtue');
  });
});
