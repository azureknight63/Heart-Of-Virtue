import { describe, it, expect, vi, beforeEach } from 'vitest';
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

// Import apiClient AFTER mocking axios
import apiClient from './client';

describe('apiClient', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('creates an axios instance with correct base URL', () => {
    expect(axios.create).toHaveBeenCalled();
  });

  it('adds auth token from localStorage to request headers', () => {
    // Get the request interceptor function from the mock call
    const requestInterceptor = mockRequestUse.mock.calls[0][0];
    
    localStorage.setItem('authToken', 'test-token');
    const config = { headers: {} };
    const result = requestInterceptor(config);
    
    expect(result.headers.Authorization).toBe('Bearer test-token');
  });

  it('handles 401 errors by clearing token and redirecting', () => {
    const mockError = {
      response: { status: 401 }
    };
    localStorage.setItem('authToken', 'test-token');
    
    // Mock window.location.pathname
    const originalLocation = window.location;
    const mockLocation = {
      pathname: '/',
      href: ''
    };
    Object.defineProperty(window, 'location', {
      value: mockLocation,
      writable: true
    });
    
    try {
      // Get the response interceptor error handler
      const responseError = mockResponseUse.mock.calls[0]?.[1];
      if (responseError) {
        responseError(mockError).catch(() => {});
        expect(localStorage.getItem('authToken')).toBeNull();
        expect(mockLocation.href).toBe('/login');
      }
    } finally {
      Object.defineProperty(window, 'location', {
        value: originalLocation,
        writable: true
      });
    }
  });
});
