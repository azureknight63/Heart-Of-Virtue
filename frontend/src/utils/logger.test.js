import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AxiosError } from 'axios';
import logger from './logger';

describe('BrowserLogger', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Mock fetch
    global.fetch = vi.fn().mockImplementation(() => 
      Promise.resolve({ ok: true })
    );
    // Mock window.location and navigator
    global.window = { 
      location: { href: 'http://localhost/' },
      addEventListener: vi.fn()
    };
    global.navigator = { userAgent: 'test-agent' };
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
    logger.logQueue = [];
    logger.isInitialized = false;
    // Singleton: a failing flush in one test would otherwise backoff the next.
    logger.retryAfter = 0;
  });

  it('initializes correctly', () => {
    const spy = vi.spyOn(console, 'log');
    logger.init();
    expect(logger.isInitialized).toBe(true);
    expect(global.window.addEventListener).toHaveBeenCalledWith('beforeunload', expect.any(Function));
  });

  it('queues logs when console methods are called', () => {
    logger.init();
    console.log('test log');
    expect(logger.logQueue.length).toBe(1);
    expect(logger.logQueue[0].message).toBe('test log');
    expect(logger.logQueue[0].level).toBe('LOG');
  });

  it('flushes logs when batch size is reached', async () => {
    logger.init();
    for (let i = 0; i < 10; i++) {
      console.log(`log ${i}`);
    }
    // One POST carrying all ten queued entries, keyed by the session id —
    // a bare toHaveBeenCalled() would pass even if the body were empty.
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toContain('api/logs/browser');
    expect(init.method).toBe('POST');
    const body = JSON.parse(init.body);
    expect(body.logs.map((l) => l.message)).toEqual(
      Array.from({ length: 10 }, (_, i) => `log ${i}`)
    );
    expect(body.session_id).toBe(logger.getSessionId());
    expect(logger.logQueue.length).toBe(0);
  });

  it('flushes logs on interval', () => {
    logger.init();
    console.log('test log');
    expect(global.fetch).not.toHaveBeenCalled();

    vi.advanceTimersByTime(5000);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).logs.map((l) => l.message))
      .toEqual(['test log']);
  });

  it('does not re-initialize if already initialized', () => {
    logger.init();
    const addEventListenerCallCount = global.window.addEventListener.mock.calls.length;
    logger.init();
    expect(global.window.addEventListener.mock.calls.length).toBe(addEventListenerCallCount);
  });

  it('queues logs for error, warn, info, and debug levels', () => {
    logger.init();
    console.error('an error');
    console.warn('a warning');
    console.info('some info');
    console.debug('debug details');

    const levels = logger.logQueue.map((e) => e.level);
    expect(levels).toEqual(['ERROR', 'WARN', 'INFO', 'DEBUG']);
  });

  it('formats object arguments as JSON', () => {
    logger.init();
    console.log('payload:', { a: 1, b: 2 });
    expect(logger.logQueue[0].message).toContain('"a": 1');
  });

  it('falls back to String() when an argument cannot be JSON-serialized', () => {
    logger.init();
    const circular = {};
    circular.self = circular;
    console.log(circular);
    expect(logger.logQueue[0].message).toBe(String(circular));
  });

  describe('credential redaction', () => {
    // The leak this closes: ~30 sites across the app write
    // `console.error('...', err)` with a raw rejected request. Axios defines
    // `AxiosError.prototype.toJSON`, which `JSON.stringify` calls, and it emits
    // `config` — carrying the `Authorization: Bearer <session id>` that
    // api/client.js attaches to every request. Every failed call therefore
    // wrote the player's live session token into a server-side log file.
    //
    // A REAL AxiosError is constructed rather than an error-shaped literal:
    // the whole hazard is what axios's own `toJSON` chooses to serialize, so an
    // invented shape would only be testing this file's guess about it.
    const TOKEN = 'eyJhbGciOiJIUzI1NiJ9.super-secret-session-token';

    const shippedBody = async (...args) => {
      logger.log('error', ...args);
      await logger.flush();
      return global.fetch.mock.calls[0][1].body;
    };

    const unauthorizedError = () =>
      new AxiosError(
        'Request failed with status code 401',
        'ERR_BAD_REQUEST',
        {
          url: '/npc/chat/open',
          method: 'post',
          headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' },
        },
        {},
        { status: 401, data: { error: 'unauthorized' } }
      );

    it('proves axios really does serialize the auth header', () => {
      // Guard-the-guard. If a future axios stops emitting `config` from
      // `toJSON`, the assertions below would pass for the wrong reason — they
      // would be redacting something that was never there.
      expect(JSON.stringify(unauthorizedError())).toContain(TOKEN);
    });

    it('never ships an AxiosError’s Authorization header to the log endpoint', async () => {
      const body = await shippedBody('[npcChat] open failed:', unauthorizedError());

      expect(body).not.toContain(TOKEN);
      expect(body).not.toContain('Bearer');
      // Still a useful log line: the redaction takes the credentials, not the
      // diagnosis.
      expect(body).toContain('Request failed with status code 401');
      expect(body).toContain('[npcChat] open failed:');
    });

    it('redacts a header bag nested at any depth, under any casing', async () => {
      const body = await shippedBody({
        outer: {
          deeper: {
            response: { CONFIG: { HEADERS: { authorization: `Bearer ${TOKEN}` } } },
            cookie: `session=${TOKEN}`,
            'Set-Cookie': `session=${TOKEN}`,
          },
        },
      });

      expect(body).not.toContain(TOKEN);
      expect(body).toContain('[redacted]');
    });

    it('leaves ordinary object arguments alone', async () => {
      const body = await shippedBody('payload:', { npcId: 'Mynx', loquacity: 3 });

      const message = JSON.parse(body).logs[0].message;
      expect(message).toContain('"npcId": "Mynx"');
      expect(message).toContain('"loquacity": 3');
      expect(message).not.toContain('[redacted]');
    });
  });

  it('manually logs a message via log()', () => {
    logger.log('info', 'manual entry');
    expect(logger.logQueue).toHaveLength(1);
    expect(logger.logQueue[0].message).toBe('manual entry');
    expect(logger.logQueue[0].level).toBe('INFO');
  });

  it('does nothing when flush is called with an empty queue', async () => {
    logger.logQueue = [];
    await logger.flush();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('re-queues logs when the async flush request fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network down'));
    const errorSpy = vi.spyOn(logger.originalConsole, 'error').mockImplementation(() => {});

    logger.log('log', 'will fail to send');
    await logger.flush();

    expect(logger.logQueue).toHaveLength(1);
    expect(logger.logQueue[0].message).toBe('will fail to send');
    expect(errorSpy).toHaveBeenCalledWith('[Logger] Failed to send logs:', expect.any(Error));
  });

  it('does not grow the queue past the cap while the endpoint is down', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network down'));
    vi.spyOn(logger.originalConsole, 'error').mockImplementation(() => {});
    // Silence the pass-through to the real console — interceptConsole captures
    // originalConsole.log at init(), so the spy must be installed first.
    vi.spyOn(logger.originalConsole, 'log').mockImplementation(() => {});

    logger.init();
    // Far more entries than the cap, each console call also attempting a flush.
    for (let i = 0; i < 500; i++) {
      console.log(`spam ${i}`);
      await Promise.resolve();
    }

    expect(logger.logQueue.length).toBeLessThanOrEqual(100);
    // The most recent entry survives; the oldest are the ones dropped.
    expect(logger.logQueue[logger.logQueue.length - 1].message).toBe('spam 499');
  });

  it('treats an HTTP error status as a failure, not a success', async () => {
    // fetch only rejects on a network-level failure — a 500, a 404, or a proxy
    // returning an error body all RESOLVE. Without the response.ok check the
    // stand-down covered only the unreachable case, so a backend that is up
    // but erroring still got a doomed request per console call, which is the
    // exact scenario the backoff exists to prevent.
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const errorSpy = vi.spyOn(logger.originalConsole, 'error').mockImplementation(() => {});

    logger.log('log', 'server is unhappy');
    await logger.flush();

    expect(logger.logQueue).toHaveLength(1);
    expect(logger.retryAfter).toBeGreaterThan(Date.now());
    expect(errorSpy).toHaveBeenCalledWith('[Logger] Failed to send logs:', expect.any(Error));
  });

  it('clears the backoff after a genuinely successful send', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 204 });

    logger.log('log', 'fine');
    await logger.flush();

    expect(logger.logQueue).toHaveLength(0);
    expect(logger.retryAfter).toBe(0);
  });

  it('backs off further async flushes after a failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network down'));
    vi.spyOn(logger.originalConsole, 'error').mockImplementation(() => {});

    logger.log('log', 'first');
    await logger.flush();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    logger.log('log', 'second');
    await logger.flush();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Once the backoff window elapses the logger tries again.
    vi.advanceTimersByTime(30000);
    await logger.flush();
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('uses sendBeacon for a synchronous flush', async () => {
    global.navigator.sendBeacon = vi.fn();
    logger.log('log', 'unload log');
    await logger.flush(true);

    expect(global.navigator.sendBeacon).toHaveBeenCalledWith(
      expect.stringContaining('api/logs/browser'),
      expect.any(Blob)
    );
    expect(logger.logQueue).toHaveLength(0);
  });

  it('re-queues logs when the synchronous sendBeacon flush throws', async () => {
    global.navigator.sendBeacon = vi.fn(() => { throw new Error('beacon blocked') });
    const errorSpy = vi.spyOn(logger.originalConsole, 'error').mockImplementation(() => {});

    logger.log('log', 'beacon log');
    await logger.flush(true);

    // The entry is put back so the next flush can retry it, and the failure is
    // reported through the ORIGINAL console (routing it through the patched one
    // would recurse straight back into the logger).
    expect(logger.logQueue).toHaveLength(1);
    expect(logger.logQueue[0].message).toBe('beacon log');
    expect(errorSpy).toHaveBeenCalledTimes(1);
  });

  it('creates a session id once and reuses it thereafter', () => {
    global.sessionStorage = (() => {
      let store = {};
      return {
        getItem: (key) => store[key] || null,
        setItem: (key, value) => { store[key] = value; },
      };
    })();

    const first = logger.getSessionId();
    const second = logger.getSessionId();
    expect(first).toBe(second);
    expect(first).toMatch(/^session_/);
  });

  it('restores original console methods and stops the flush timer on destroy', () => {
    logger.init();
    const originalLog = console.log;
    logger.destroy();

    expect(console.log).toBe(logger.originalConsole.log);
    expect(logger.isInitialized).toBe(false);

    // Logging after destroy should no longer be intercepted into the queue.
    logger.logQueue = [];
    console.log('post-destroy log');
    expect(logger.logQueue).toHaveLength(0);
  });

  it('does nothing when destroy is called without having initialized', () => {
    // `.not.toThrow()` alone would also pass for a destroy() that tore down a
    // LIVE interceptor belonging to someone else. Prove it is a genuine no-op:
    // the console stays intercepted and the flush timer stays armed.
    logger.isInitialized = false;
    const interceptedLog = console.log;
    const timerBefore = logger.flushInterval;

    logger.destroy();

    expect(console.log).toBe(interceptedLog);
    expect(logger.flushInterval).toBe(timerBefore);
    expect(logger.isInitialized).toBe(false);
  });
});
