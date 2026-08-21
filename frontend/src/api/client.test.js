import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import { AUTH_TOKEN_KEY, USERNAME_KEY } from '../utils/session';

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

// Import apiClient AFTER mocking axios
import apiClient from './client';

describe('apiClient', () => {
  // Pulled out of the mock calls once, at module scope, so a missing
  // interceptor is a hard failure instead of the previous `if (responseError)`
  // guard — which made the whole 401 test a silent no-op if client.js ever
  // stopped registering a response handler.
  const requestInterceptor = mockRequestUse.mock.calls[0][0];
  const [responseSuccess, responseError] = mockResponseUse.mock.calls[0];

  beforeEach(() => {
    localStorage.clear();
  });

  it('exports the instance axios.create returned', () => {
    expect(apiClient).toBe(axios.create.mock.results[0].value);
  });

  it('creates the axios instance with the JSON base config', () => {
    // A bare toHaveBeenCalled() here passed regardless of baseURL — the one
    // thing this call decides.
    expect(axios.create).toHaveBeenCalledTimes(1);
    expect(axios.create).toHaveBeenCalledWith({
      baseURL: import.meta.env.VITE_API_URL || '/api',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('registers exactly one request and one response interceptor', () => {
    expect(mockRequestUse).toHaveBeenCalledTimes(1);
    expect(mockResponseUse).toHaveBeenCalledTimes(1);
    expect(typeof requestInterceptor).toBe('function');
    expect(typeof responseError).toBe('function');
  });

  describe('request interceptor', () => {
    it('adds the stored auth token as a Bearer header', () => {
      localStorage.setItem(AUTH_TOKEN_KEY, 'test-token');
      const config = { headers: {} };
      const result = requestInterceptor(config);

      expect(result.headers.Authorization).toBe('Bearer test-token');
      // The config object is mutated and returned, not replaced.
      expect(result).toBe(config);
    });

    it('sends no Authorization header when there is no token', () => {
      const result = requestInterceptor({ headers: {} });
      expect(result.headers).not.toHaveProperty('Authorization');
    });

    it('leaves other headers untouched', () => {
      localStorage.setItem(AUTH_TOKEN_KEY, 'tok');
      const result = requestInterceptor({ headers: { 'X-Trace': 'abc' } });
      expect(result.headers).toEqual({ 'X-Trace': 'abc', Authorization: 'Bearer tok' });
    });
  });

  describe('response interceptor', () => {
    const withLocation = (pathname, fn) => {
      const originalLocation = window.location;
      const mockLocation = { pathname, href: '' };
      Object.defineProperty(window, 'location', { value: mockLocation, writable: true });
      try {
        return fn(mockLocation);
      } finally {
        Object.defineProperty(window, 'location', { value: originalLocation, writable: true });
      }
    };

    it('passes a successful response straight through', () => {
      const response = { status: 200, data: { ok: true } };
      expect(responseSuccess(response)).toBe(response);
    });

    it('clears the whole session and redirects to login on a 401', async () => {
      localStorage.setItem(AUTH_TOKEN_KEY, 'test-token');
      localStorage.setItem(USERNAME_KEY, 'jean');
      const error = { response: { status: 401 } };

      await withLocation('/games/HeartOfVirtue/', async (location) => {
        await expect(responseError(error)).rejects.toBe(error);
        // BOTH session keys go — leaving `username` behind hands the prior
        // account's identifier to the next user on a shared machine.
        expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
        expect(localStorage.getItem(USERNAME_KEY)).toBeNull();
        expect(location.href).toBe(`${import.meta.env.BASE_URL}login`);
      });
    });

    it('does not redirect a 401 raised on the login page itself', async () => {
      // Otherwise a wrong password triggers a redirect back to /login and the
      // page reloads in a loop instead of showing the error.
      localStorage.setItem(AUTH_TOKEN_KEY, 'test-token');
      const error = { response: { status: 401 } };

      await withLocation('/games/HeartOfVirtue/login', async (location) => {
        await expect(responseError(error)).rejects.toBe(error);
        expect(location.href).toBe('');
        expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('test-token');
      });
    });

    it.each([
      ['a 403', { response: { status: 403 } }],
      ['a 500', { response: { status: 500 } }],
      ['a network error with no response', { message: 'Network Error' }],
    ])('rejects %s without touching the session', async (_label, error) => {
      localStorage.setItem(AUTH_TOKEN_KEY, 'test-token');

      await withLocation('/games/HeartOfVirtue/', async (location) => {
        await expect(responseError(error)).rejects.toBe(error);
        expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('test-token');
        expect(location.href).toBe('');
      });
    });
  });
});
