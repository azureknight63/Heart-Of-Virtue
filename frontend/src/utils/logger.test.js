import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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

  it('formats object arguments as compact single-line JSON', () => {
    logger.init();
    console.log('payload:', { a: 1, b: 2 });
    expect(logger.logQueue[0].message).toBe('payload: {"a":1,"b":2}');
  });

  it('falls back to String() when an argument cannot be JSON-serialized', () => {
    logger.init();
    const circular = {};
    circular.self = circular;
    console.log(circular);
    expect(logger.logQueue[0].message).toBe(String(circular));
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

  describe('error serialization', () => {
    it('serializes Error objects with name, message, and stack head', () => {
      logger.init();
      console.error('failed:', new Error('boom'));
      const msg = logger.logQueue[0].message;
      expect(msg).toContain('failed:');
      expect(msg).toContain('Error: boom');
      expect(msg).not.toContain('{}');
    });

    it('summarizes axios-style errors as METHOD url -> status', () => {
      logger.init();
      const err = new Error('Request failed with status code 401');
      err.isAxiosError = true;
      err.config = { method: 'get', url: '/combat/status' };
      err.status = 401;
      console.error('Combat status error:', err);
      const msg = logger.logQueue[0].message;
      expect(msg).toContain('GET /combat/status');
      expect(msg).toContain('401');
      // The old behavior dumped the entire axios config object into the log
      expect(msg).not.toContain('transitional');
    });
  });

  describe('repeat collapsing', () => {
    it('collapses immediately repeated identical lines into one entry with n', () => {
      logger.init();
      console.log('Adding new event to queue: X');
      console.log('Adding new event to queue: X');
      expect(logger.logQueue).toHaveLength(1);
      expect(logger.logQueue[0].n).toBe(2);
    });

    it('does not collapse different messages or levels', () => {
      logger.init();
      console.log('one');
      console.log('two');
      console.warn('two');
      expect(logger.logQueue).toHaveLength(3);
      expect(logger.logQueue.every((e) => e.n === undefined)).toBe(true);
    });
  });

  describe('structured events', () => {
    afterEach(() => {
      logger._lastEventState.clear();
    });

    it('queues a structured entry with event and data when initialized', () => {
      logger.init();
      logger.event('event.enqueue', { name: 'Passage', needsInput: true });
      const entry = logger.logQueue[0];
      expect(entry.event).toBe('event.enqueue');
      expect(entry.data).toEqual({ name: 'Passage', needsInput: true });
      expect(entry.level).toBe('DEBUG');
      // No message: data carries the payload; shipping both doubled the wire
      expect(entry.message).toBeUndefined();
    });

    it('collapses identical repeated structured events into one entry', () => {
      logger.init();
      vi.spyOn(logger.originalConsole, 'debug').mockImplementation(() => {});
      logger.event('event.enqueue', { name: 'X' });
      logger.event('event.enqueue', { name: 'X' });
      logger.event('event.enqueue', { name: 'Y' });
      expect(logger.logQueue).toHaveLength(2);
      expect(logger.logQueue[0].n).toBe(2);
    });

    it('echoes to the devtools console without re-entering the interceptor', () => {
      logger.init();
      const debugSpy = vi
        .spyOn(logger.originalConsole, 'debug')
        .mockImplementation(() => {});
      logger.event('combat.start', { enemy: 'Slime' });
      expect(debugSpy).toHaveBeenCalledTimes(1);
      // Exactly one queue entry — the echo must not be captured again
      expect(logger.logQueue).toHaveLength(1);
    });

    it('does not queue (console-echo only) before init', () => {
      const debugSpy = vi
        .spyOn(logger.originalConsole, 'debug')
        .mockImplementation(() => {});
      logger.event('event.queue', { queueLength: 0 });
      expect(logger.logQueue).toHaveLength(0);
      expect(debugSpy).toHaveBeenCalled();
    });

    it('eventOnChange suppresses unchanged payloads and passes changed ones', () => {
      logger.init();
      vi.spyOn(logger.originalConsole, 'debug').mockImplementation(() => {});
      logger.eventOnChange('event.queue', { queueLength: 0, hasCurrentEvent: false });
      logger.eventOnChange('event.queue', { queueLength: 0, hasCurrentEvent: false });
      logger.eventOnChange('event.queue', { queueLength: 1, hasCurrentEvent: false });
      expect(logger.logQueue).toHaveLength(2);
    });

    it('a circular event payload does not block subsequent log delivery', async () => {
      logger.init();
      vi.spyOn(logger.originalConsole, 'debug').mockImplementation(() => {});
      const circular = {};
      circular.self = circular;
      logger.event('weird.event', circular);
      await logger.flush();
      logger.log('info', 'unrelated log');
      await logger.flush();
      // Without the serializability guard, JSON.stringify(payload) throws on
      // every flush and the poisoned entry re-queues forever.
      const bodies = global.fetch.mock.calls.map(([, init]) => JSON.parse(init.body));
      expect(bodies.some((b) => b.logs.some((l) => l.message === 'unrelated log'))).toBe(true);
      expect(
        bodies.some((b) => b.logs.some((l) => l.data && l.data._unserializable))
      ).toBe(true);
    });

    it('ships event, data, and n fields to the backend', async () => {
      logger.init();
      logger.event('event.dedupe', { name: 'X' });
      console.log('dup');
      console.log('dup');
      await logger.flush();
      const body = JSON.parse(global.fetch.mock.calls[0][1].body);
      expect(body.logs[0].event).toBe('event.dedupe');
      expect(body.logs[0].data).toEqual({ name: 'X' });
      expect(body.logs[1].n).toBe(2);
      // Neither the internal dedupe key nor dead fields ship over the wire
      expect(body.logs[0]._sig).toBeUndefined();
      expect(body.logs[0].message).toBeUndefined();
      expect(body.logs[0].userAgent).toBeUndefined();
      expect(body.logs[1].message).toBe('dup');
    });
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
