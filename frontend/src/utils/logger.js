/**
 * Browser Logger Utility
 * Captures console logs and sends them to the backend for file storage
 */

const LOG_ENDPOINT = `${import.meta.env.BASE_URL}api/logs/browser`;
const BATCH_SIZE = 10;
const FLUSH_INTERVAL = 5000; // 5 seconds
// With the log API down, every console call used to re-queue its failed batch
// and immediately retry, so the queue grew without bound and each console call
// issued another doomed request. Cap the backlog and stand down briefly after
// a failure. Oldest entries are dropped first — recent logs matter most.
const MAX_QUEUE_SIZE = 100;
const FAILURE_BACKOFF_MS = 30000;

const REDACTED = '[redacted]';

/**
 * Keys whose VALUE never leaves the browser, at any depth, in any argument.
 *
 * This is a credential leak, not tidiness. Roughly thirty sites across the app
 * write `console.error('...', err)` with a raw rejected request, and axios's
 * `AxiosError.prototype.toJSON` — which `JSON.stringify` calls for us — emits
 * `config`, whose `headers` carry the `Authorization: Bearer <session id>`
 * that api/client.js's request interceptor attached. So a single failed
 * request used to POST the player's live session token to
 * /api/logs/browser, where it landed in a file on disk.
 *
 * It is redacted HERE rather than at the call sites because the call sites are
 * not the hazard: the next `console.error(msg, err)` anyone writes reopens it.
 * `config` and `request` go whole (an XHR/config object is diagnostic noise
 * that happens to carry secrets); `headers`, `authorization`, `cookie` and
 * `set-cookie` go by name so a bare header bag passed on its own is covered
 * too. The cost is that a domain object with a `config` field logs as
 * `[redacted]` — an acceptable trade for a class of leak that cannot be
 * closed by remembering to be careful.
 */
const REDACTED_KEYS = new Set([
    'config',
    'request',
    'headers',
    'authorization',
    'cookie',
    'set-cookie',
]);

/**
 * `JSON.stringify` replacer that blanks the values above.
 *
 * Runs AFTER `toJSON()` on each value (that is the serialization order the
 * spec defines), so it sees the object graph `AxiosError.toJSON()` actually
 * produces rather than the error's own enumerable properties.
 */
function redactCredentials(key, value) {
    if (typeof key === 'string' && REDACTED_KEYS.has(key.toLowerCase())) {
        return REDACTED;
    }
    return value;
}

class BrowserLogger {
    constructor() {
        this.logQueue = [];
        this.flushTimer = null;
        this.retryAfter = 0;
        this.originalConsole = {
            log: console.log,
            error: console.error,
            warn: console.warn,
            info: console.info,
            debug: console.debug
        };

        this.isInitialized = false;
    }

    /**
     * Initialize the logger and intercept console methods
     */
    init() {
        if (this.isInitialized) {
            return;
        }

        // Intercept console methods
        this.interceptConsole('log');
        this.interceptConsole('error');
        this.interceptConsole('warn');
        this.interceptConsole('info');
        this.interceptConsole('debug');

        // Set up periodic flushing
        this.flushTimer = setInterval(() => this.flush(), FLUSH_INTERVAL);

        // Flush on page unload
        window.addEventListener('beforeunload', () => this.flush(true));

        this.isInitialized = true;
        this.originalConsole.log('[Logger] Browser logging initialized');
    }

    /**
     * Intercept a console method
     */
    interceptConsole(method) {
        const original = this.originalConsole[method];

        console[method] = (...args) => {
            // Call original console method
            original.apply(console, args);

            // Queue the log entry
            this.queueLog(method, args);
        };
    }

    /**
     * Queue a log entry
     */
    queueLog(level, args) {
        const entry = {
            timestamp: new Date().toISOString(),
            level: level.toUpperCase(),
            message: this.formatArgs(args),
            url: window.location.href,
            userAgent: navigator.userAgent
        };

        this.logQueue.push(entry);
        this.trimQueue();

        // Flush if batch size reached
        if (this.logQueue.length >= BATCH_SIZE) {
            this.flush();
        }
    }

    /**
     * Drop the oldest entries once the backlog exceeds MAX_QUEUE_SIZE.
     */
    trimQueue() {
        if (this.logQueue.length > MAX_QUEUE_SIZE) {
            this.logQueue = this.logQueue.slice(-MAX_QUEUE_SIZE);
        }
    }

    /**
     * Format console arguments into a string, with credentials stripped.
     *
     * See `REDACTED_KEYS`: everything here is shipped to a server-side log
     * file, so no argument may carry an auth header into it. The `String(arg)`
     * fallback for an unserializable value is safe on the same grounds — an
     * error's `toString()` is its name and message, never its request config.
     */
    formatArgs(args) {
        return args.map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg, redactCredentials, 2);
                } catch (e) {
                    return String(arg);
                }
            }
            return String(arg);
        }).join(' ');
    }

    /**
     * Flush queued logs to the backend
     */
    async flush(synchronous = false) {
        if (this.logQueue.length === 0) {
            return;
        }

        // Stand down after a failure so a dead endpoint isn't hammered once per
        // console call. The unload flush (sendBeacon) always goes out.
        if (!synchronous && Date.now() < this.retryAfter) {
            return;
        }

        const logsToSend = [...this.logQueue];
        this.logQueue = [];

        const payload = {
            logs: logsToSend,
            session_id: this.getSessionId()
        };

        try {
            if (synchronous) {
                // Use sendBeacon for synchronous sending on page unload
                const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
                navigator.sendBeacon(LOG_ENDPOINT, blob);
            } else {
                // Use fetch for normal async sending
                const response = await fetch(LOG_ENDPOINT, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(payload)
                });
                // fetch only rejects on network-level failure — a 500, a 404,
                // or a proxy returning an error body all resolve normally.
                // Without this the backoff below covered only the unreachable
                // case, and a backend that is *up but erroring* still got a
                // doomed request per console call: exactly what the stand-down
                // exists to prevent.
                if (!response.ok) {
                    throw new Error(`log endpoint returned ${response.status}`);
                }
            }
            this.retryAfter = 0;
        } catch (error) {
            // Use original console to avoid infinite loop
            this.originalConsole.error('[Logger] Failed to send logs:', error);
            this.retryAfter = Date.now() + FAILURE_BACKOFF_MS;
            // Re-queue the logs, then trim so the backlog stays bounded
            this.logQueue.unshift(...logsToSend);
            this.trimQueue();
        }
    }

    /**
     * Get or create a session ID
     */
    getSessionId() {
        let sessionId = sessionStorage.getItem('browser_log_session_id');
        if (!sessionId) {
            sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            sessionStorage.setItem('browser_log_session_id', sessionId);
        }
        return sessionId;
    }

    /**
     * Manually log a message
     */
    log(level, ...args) {
        this.queueLog(level, args);
    }

    /**
     * Restore original console methods
     */
    destroy() {
        if (!this.isInitialized) {
            return;
        }

        // Restore original console methods
        Object.keys(this.originalConsole).forEach(method => {
            console[method] = this.originalConsole[method];
        });

        // Clear flush timer
        if (this.flushTimer) {
            clearInterval(this.flushTimer);
            this.flushTimer = null;
        }

        // Flush remaining logs
        this.flush(true);

        this.isInitialized = false;
        this.originalConsole.log('[Logger] Browser logging destroyed');
    }
}

// Create singleton instance
const logger = new BrowserLogger();

export default logger;
