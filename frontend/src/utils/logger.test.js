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
    expect(global.fetch).toHaveBeenCalled();
    expect(logger.logQueue.length).toBe(0);
  });

  it('flushes logs on interval', () => {
    logger.init();
    console.log('test log');
    expect(global.fetch).not.toHaveBeenCalled();

    vi.advanceTimersByTime(5000);
    expect(global.fetch).toHaveBeenCalled();
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

    expect(logger.logQueue).toHaveLength(1);
    expect(errorSpy).toHaveBeenCalled();
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
    logger.isInitialized = false;
    expect(() => logger.destroy()).not.toThrow();
  });
});
