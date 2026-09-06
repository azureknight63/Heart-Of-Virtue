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
// Identical consecutive lines within this window collapse into one entry
// with an `n` repeat count (React StrictMode double-invokes effects in dev,
// duplicating nearly every debug line).
const DEDUPE_WINDOW_MS = 2000;

const REDACTED = '[redacted]';

/**
 * Keys whose VALUE *is* a credential.
 *
 * This is a credential leak, not tidiness. Roughly thirty sites across the app
 * write `console.error('...', err)` with a raw rejected request, and axios's
 * `AxiosError.prototype.toJSON` — which `JSON.stringify` calls for us — emits
 * `config`, whose `headers` carried the `Authorization: Bearer <session id>`
 * a request interceptor in api/client.js attached. So a single failed request
 * used to POST the player's live session token to /api/logs/browser, where it
 * landed in a file on disk.
 *
 * That interceptor is gone -- the credential is an HttpOnly cookie the browser
 * attaches and this code cannot read (issue #493), and `withCredentials: true`
 * is what api/client.js sets instead. The redaction stays, and is keyed on the
 * header NAME rather than on where the header came from: the API still accepts
 * the Bearer form for non-browser callers, an axios error can carry a header
 * this app never set (a proxy, an extension, a hand-built request), and a
 * scrub that only covers the one path that has since been removed is a scrub
 * that covers nothing. This transport has
 * only ever run in development — main.jsx gates `logger.init()` on
 * `import.meta.env.DEV` — so the file was a developer's, not a production
 * server's. A real bearer token in a real file on disk is still worth closing,
 * and the gate is one edit away from being relaxed.
 *
 * It is redacted HERE rather than at the call sites because the call sites are
 * not the hazard: the next `console.error(msg, err)` anyone writes reopens it.
 */
const CREDENTIAL_KEYS = [
    'authorization',
    'cookie',
    'set-cookie',
];

/**
 * Keys whose value merely CARRIES a credential somewhere inside it.
 *
 * `config` and `request` go whole (an XHR/config object is diagnostic noise
 * that happens to carry secrets); `headers` goes by name so a bare header bag
 * passed on its own is covered too. The cost is that a domain object with a
 * `config` field logs as `[redacted]` — an acceptable trade for a class of
 * leak that cannot be closed by remembering to be careful.
 *
 * Split from {@link CREDENTIAL_KEYS} because the two have different reach.
 * Both halves are redacted by key when an argument is an OBJECT; only the
 * credential half is meaningful in free TEXT, where `request: timed out` is a
 * diagnosis and `authorization: Bearer …` is a secret.
 */
const CREDENTIAL_CARRIER_KEYS = [
    'config',
    'request',
    'headers',
];

/** The union, which is what the object path redacts. Derived, not restated. */
const REDACTED_KEYS = new Set([...CREDENTIAL_KEYS, ...CREDENTIAL_CARRIER_KEYS]);

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

const escapeRegExp = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Credential shapes recognised inside a STRING, and what replaces them.
 *
 * The key-based replacer above only sees an object graph. Three things reach
 * the wire as text and never pass through it: a string argument
 * (`console.log('Authorization: ' + header)`), the `String(arg)` fallback for
 * an argument `JSON.stringify` refused, and the URL / User-Agent attached
 * beside the message. A key-based rule cannot help there — there are no keys.
 *
 * BE CLEAR ABOUT WHAT THIS IS: a net, not a proof. It recognises the shapes a
 * credential is written in; a secret written in some other shape (a bare token
 * on its own, with nothing naming it) still goes out. The key-based replacer
 * remains the primary defence and this is the second layer for the paths it
 * structurally cannot reach.
 *
 * The first pattern is BUILT FROM {@link CREDENTIAL_KEYS} rather than
 * restating them, so the object path and the text path cannot drift apart —
 * adding a key there covers both, and logger.test.js asserts that by
 * iterating the exported set rather than a copy of it.
 */
const SECRET_PATTERNS = [
    {
        // `authorization: <value>`, `cookie="<value>"`, `"Set-Cookie": "…"`.
        // The value runs to the next `,`/`;` or the end of the string: a
        // credential with a space in it (`Bearer <id>`) is the normal case, so
        // stopping at whitespace would redact the word `Bearer` and ship the
        // token after it.
        re: new RegExp(
            '\\b(' + CREDENTIAL_KEYS.map(escapeRegExp).join('|') + ')'
            + '("?\\s*[:=]\\s*)'
            + '("[^"]*"|\'[^\']*\'|[^\\s,;][^,;\\n]*)',
            'gi'
        ),
        replace: (_match, key, separator, value) => (
            /^["']/.test(value)
                ? key + separator + value[0] + REDACTED + value[0]
                : key + separator + REDACTED
        ),
    },
    {
        // A bearer token with nothing naming it — the exact thing axios puts
        // in the header, so the exact thing that appears when someone
        // interpolates that header into a message. The scheme word goes with
        // it: `Bearer [redacted]` still says "a token was here", and the
        // suite asserts the wire body contains no `Bearer` at all.
        re: /\bBearer\s+[\w\-.~+/]+=*/gi,
        replace: () => REDACTED,
    },
    {
        // A query or fragment parameter whose NAME looks like a credential.
        // This is the URL half: `?api_key=…` in `window.location.href`.
        // Substring matching, so `?monkey_auth=` is caught and `?auth_ok=` is
        // redacted needlessly — failing toward a useless log line rather than
        // a leaked one.
        re: /([?&#][^?&#=\s]*(?:token|secret|password|passwd|apikey|api[_-]key|auth|session|signature|credential)[^?&#=\s]*=)[^&#\s"']*/gi,
        replace: (_match, name) => name + REDACTED,
    },
];

/**
 * Every recognised credential shape in `text`, blanked.
 *
 * Exported for logger.test.js, which drives it directly as well as through the
 * transport — a pattern that only ever runs behind three layers of queueing is
 * a pattern nobody can tell is broken.
 */
export function scrubSecrets(text) {
    let scrubbed = text;
    for (const { re, replace } of SECRET_PATTERNS) {
        scrubbed = scrubbed.replace(re, replace);
    }
    return scrubbed;
}

/** The key sets, exported so the suite can derive its cases instead of copying them. */
export const REDACTION_KEYS = Object.freeze({
    credential: Object.freeze([...CREDENTIAL_KEYS]),
    carrier: Object.freeze([...CREDENTIAL_CARRIER_KEYS]),
});

/**
 * Scrub every string field of a log entry.
 *
 * Written over `Object.entries(entry)` rather than over a list of field names
 * on purpose. `url` and `userAgent` were attached BESIDE the redacted message
 * and went out untouched; naming those two here would fix those two and leave
 * the next field somebody attaches in exactly the same position. The rule is
 * "every string this module puts on the wire", and the population is read from
 * the entry itself so a new field is covered the day it is added -- which is
 * how `event`/`data` arrived already covered.
 *
 * Recursive for the same reason. The first version walked one level and
 * scrubbed strings, on the stated grounds that no entry field was an object;
 * structured logging then added `data`, whose contents are whatever the caller
 * passed. The flush-time `redactCredentials` replacer still blanks anything
 * under a credential-shaped KEY at any depth, so the gap is narrower than it
 * looks -- but a token under an innocuous key, inside `data`, was scrubbed by
 * nothing at all. Depth is bounded by the JSON the caller could serialise, and
 * `event()` has already rejected cycles by this point.
 */
function scrubEntry(entry) {
    if (typeof entry === 'string') {
        return scrubSecrets(entry);
    }
    if (Array.isArray(entry)) {
        return entry.map(scrubEntry);
    }
    if (entry === null || typeof entry !== 'object') {
        return entry;
    }
    const scrubbed = {};
    for (const [key, value] of Object.entries(entry)) {
        scrubbed[key] = scrubEntry(value);
    }
    return scrubbed;
}

class BrowserLogger {
    constructor() {
        this.logQueue = [];
        this.flushTimer = null;
        this.retryAfter = 0;
        // Last payload per event name, for eventOnChange() suppression
        this._lastEventState = new Map();
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
     * Queue a log entry. `structured` optionally carries {event, data,
     * serialized} from the structured event API. Structured entries ship
     * {event, data} with no message — the composed text exists only for the
     * devtools echo, and shipping both would double every line on the wire
     * and on disk.
     */
    queueLog(level, args, structured = null) {
        const upperLevel = level.toUpperCase();
        const message = structured ? undefined : this.formatArgs(args);
        const sig = structured
            ? `${structured.event} ${structured.serialized || ''}`
            : message;

        // Collapse immediate repeats into the previous entry's counter
        const last = this.logQueue[this.logQueue.length - 1];
        if (
            last &&
            last.level === upperLevel &&
            last._sig === sig &&
            Date.now() - Date.parse(last.timestamp) < DEDUPE_WINDOW_MS
        ) {
            last.n = (last.n || 1) + 1;
            return;
        }

        const raw = {
            timestamp: new Date().toISOString(),
            level: upperLevel,
            url: window.location.href
        };
        if (message !== undefined) {
            raw.message = message;
        }
        if (structured) {
            raw.event = structured.event;
            if (structured.data !== undefined) {
                raw.data = structured.data;
            }
        }
        const entry = scrubEntry(raw);
        // Dedupe key: non-enumerable so JSON.stringify never ships it. Set
        // AFTER scrubEntry, which copies enumerable properties only and would
        // otherwise drop it.
        Object.defineProperty(entry, '_sig', { value: sig, enumerable: false });

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
     * Format console arguments into a condensed single-line string, with
     * credentials stripped.
     *
     * Everything here is shipped to a server-side log file, so no argument may
     * carry an auth header into it. TWO rules are needed, because an argument
     * reaches this in two forms and the key-based replacer only sees one:
     *
     *   an OBJECT      `redactCredentials` blanks it by key, at any depth.
     *   anything else   `String(arg)` -- a string, a number, a function, an
     *                   Error, or an object `JSON.stringify` refused (a cycle,
     *                   a BigInt). There are no keys to match, so the
     *                   `scrubSecrets` below reads the credential shapes out
     *                   of the text instead.
     *
     * The second rule used to be omitted, justified by "an error's
     * `toString()` is its name and message, never its request config". That
     * covers exactly one of the values that reach the fallback, and says
     * nothing at all about the far commoner one: a plain string argument.
     * `console.log('Authorization: ' + header)` went out verbatim.
     *
     * Scrubbing happens once, here, over the joined result -- not inside
     * `formatArg`. `formatArg` is also called directly by `event()` to build
     * the dedupe signature, which is non-enumerable and never shipped; the
     * payload that IS shipped from that path is `entry.data`, and `scrubEntry`
     * covers it.
     */
    formatArgs(args) {
        return scrubSecrets(args.map(arg => this.formatArg(arg)).join(' '));
    }

    formatArg(arg) {
        if (this.isErrorLike(arg)) {
            return this.serializeError(arg);
        }
        if (typeof arg === 'object' && arg !== null) {
            try {
                // Compact: pretty-printed JSON turns one log line into a wall.
                // The replacer is not optional -- it is the only thing that
                // blanks a credential sitting under a credential-shaped KEY,
                // which `scrubSecrets` cannot see.
                return JSON.stringify(arg, redactCredentials);
            } catch (e) {
                return String(arg);
            }
        }
        return String(arg);
    }

    isErrorLike(arg) {
        // instanceof misses cross-realm errors; duck-type on message+stack.
        // Without this, JSON.stringify(new Error(...)) yields "{}" -- the
        // error's name, message, and stack are all non-enumerable.
        return Boolean(
            arg &&
            typeof arg === 'object' &&
            typeof arg.message === 'string' &&
            (arg instanceof Error || typeof arg.stack === 'string')
        );
    }

    serializeError(err) {
        // Axios-style errors: one compact request summary instead of the
        // whole config object (which used to dump ~2KB per failed request).
        const status = err.status ?? err.response?.status;
        if (err.config && (err.isAxiosError || status !== undefined)) {
            const method = (err.config.method || '?').toUpperCase();
            const url = err.config.url || '?';
            return `${method} ${url} -> ${status ?? err.code ?? 'ERR'} (${err.message})`;
        }
        const stackHead = (err.stack || '')
            .split('\n')
            .map(line => line.trim())
            .find(line => line.startsWith('at ') || /\S+@/.test(line)) || '';
        const name = err.name || 'Error';
        return `${name}: ${err.message}${stackHead ? ` [${stackHead}]` : ''}`;
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
            // The last thing that happens before the bytes leave, so the
            // replacer runs here too. `scrubEntry` reads credential SHAPES out
            // of values; this blanks whatever sits under a credential-shaped
            // KEY. Neither subsumes the other, and `session_id` is added here,
            // after scrubEntry has already run over the entries.
            const body = JSON.stringify(payload, redactCredentials);
            if (synchronous) {
                // Use sendBeacon for synchronous sending on page unload
                const blob = new Blob([body], { type: 'application/json' });
                navigator.sendBeacon(LOG_ENDPOINT, blob);
            } else {
                // Use fetch for normal async sending
                const response = await fetch(LOG_ENDPOINT, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body
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
     * Log a named structured event: `logger.event('event.enqueue', {name})`.
     *
     * Always echoes a compact line to the devtools console (through the
     * un-intercepted original, so it is never re-captured). Ships to the
     * backend only once the logger is initialized — component unit tests
     * therefore never trigger network sends.
     *
     * Options: {level: 'debug', onChange: false}. With onChange, the event
     * is suppressed while its payload is unchanged since the last call —
     * use for periodic state checks that only matter when state moves.
     */
    event(name, data = undefined, opts = {}) {
        const { level = 'debug', onChange = false } = opts;
        // A circular/unserializable payload stored verbatim would make every
        // flush()'s JSON.stringify(payload) throw, re-queue, and throw again —
        // poisoning delivery of ALL queued logs until the entry ages out.
        let safeData = data;
        if (data !== undefined) {
            try {
                JSON.stringify(data);
            } catch (e) {
                safeData = { _unserializable: String(data) };
            }
        }
        const serialized = safeData === undefined ? '' : this.formatArg(safeData);
        if (onChange) {
            if (this._lastEventState.get(name) === serialized) {
                return;
            }
            this._lastEventState.set(name, serialized);
        }
        const echo = serialized ? `${name} ${serialized}` : name;
        this.originalConsole.debug(`[hov] ${echo}`);
        if (!this.isInitialized) {
            return;
        }
        this.queueLog(level, [], { event: name, data: safeData, serialized });
    }

    /**
     * Shorthand for event(name, data, {onChange: true}).
     */
    eventOnChange(name, data) {
        this.event(name, data, { onChange: true });
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
