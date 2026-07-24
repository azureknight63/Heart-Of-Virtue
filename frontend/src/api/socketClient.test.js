import { vi, describe, it, expect, beforeEach } from 'vitest';

vi.mock('socket.io-client', () => ({ io: vi.fn(() => ({ id: 'sock' })) }));

import { io } from 'socket.io-client';
import { createCombatSocket } from './socketClient';

describe('createCombatSocket', () => {
  beforeEach(() => io.mockClear());

  it('connects to the given url with websocket+polling transports', () => {
    createCombatSocket({ url: 'http://api.example' });
    expect(io).toHaveBeenCalledTimes(1);
    const [url, opts] = io.mock.calls[0];
    expect(url).toBe('http://api.example');
    expect(opts).toMatchObject({
      autoConnect: true,
      transports: ['websocket', 'polling'],
    });
  });

  it('returns the socket instance', () => {
    const sock = createCombatSocket({ url: 'http://api.example' });
    expect(sock).toEqual({ id: 'sock' });
  });
});
