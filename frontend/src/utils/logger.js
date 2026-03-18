/**
 * Browser Logger Utility
 * Captures console logs and sends them to the backend for file storage
 */

const LOG_ENDPOINT = '/api/logs/browser';
const BATCH_SIZE = 10;
const FLUSH_INTERVAL = 5000; // 5 seconds

class BrowserLogger {
    constructor() {
        this.logQueue = [];
        this.flushTimer = null;
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

        // Flush if batch size reached
        if (this.logQueue.length >= BATCH_SIZE) {
            this.flush();
        }
    }

    /**
     * Format console arguments into a string
     */
    formatArgs(args) {
        return args.map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg, null, 2);
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
                await fetch(LOG_ENDPOINT, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(payload)
                });
            }
        } catch (error) {
            // Use original console to avoid infinite loop
            this.originalConsole.error('[Logger] Failed to send logs:', error);
            // Re-queue the logs
            this.logQueue.unshift(...logsToSend);
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
