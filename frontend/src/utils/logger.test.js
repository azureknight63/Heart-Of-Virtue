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
});
