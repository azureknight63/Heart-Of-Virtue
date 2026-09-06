import { describe, it, expect } from 'vitest';
import { apiErrorMessage, apiErrorDetail } from './apiError';

/**
 * The two shapes this module exists to reconcile, written the way the server
 * writes them.
 *
 * `THROTTLED` is verbatim `rate_limited_response()` (src/api/rate_limiter.py):
 * a machine token in `error`, the human half in `message`. `PROSE` is what
 * nearly every other route emits: prose in `error`, no `message` at all. Every
 * precedence case below is one of these two, so a change to the server's shape
 * has exactly one place to land here.
 */
const THROTTLED = {
  success: false,
  error: 'rate_limited',
  message: 'Slow down — too many messages.',
};
const PROSE = { success: false, error: 'Not enough gold — need 5 more' };

/** A rejected request carrying `body`, as axios delivers it. */
const rejection = (body, transportMessage = 'Request failed with status code 429') =>
  Object.assign(new Error(transportMessage), { response: { status: 429, data: body } });

describe('apiErrorMessage', () => {
  describe('precedence', () => {
    it('shows the prose half of a 429, never the "rate_limited" token', () => {
      expect(apiErrorMessage(rejection(THROTTLED), 'fallback')).toBe(
        'Slow down — too many messages.'
      );
    });

    it('shows `error` when it is the prose and there is no `message`', () => {
      expect(apiErrorMessage(rejection(PROSE), 'fallback')).toBe(
        'Not enough gold — need 5 more'
      );
    });

    it('falls back to the caller copy when the body describes nothing', () => {
      expect(apiErrorMessage(rejection({ success: false }), 'fallback')).toBe('fallback');
    });
  });

  describe('accepted shapes', () => {
    // Many call sites read a 200-with-success:false body rather than a
    // rejection, so the same rule has to apply to a bare body.
    it('reads a response body handed over directly', () => {
      expect(apiErrorMessage(THROTTLED, 'fallback')).toBe('Slow down — too many messages.');
      expect(apiErrorMessage(PROSE, 'fallback')).toBe('Not enough gold — need 5 more');
    });

    it('treats a bare string as the message it already is', () => {
      expect(apiErrorMessage('The statue rejects you.', 'fallback')).toBe(
        'The statue rejects you.'
      );
    });

    it('falls back for a blank string, which describes nothing', () => {
      expect(apiErrorMessage('   ', 'fallback')).toBe('fallback');
    });

    it.each([
      ['a transport failure with no response', new Error('Network Error')],
      ['nothing at all', undefined],
    ])('falls back for %s', (_label, thrown) => {
      expect(apiErrorMessage(thrown, 'fallback')).toBe('fallback');
    });
  });

  // The transport's own wording is a per-site decision, expressed as the
  // fallback, so a site that wants it says so and a site that does not stays
  // on its own copy.
  it('lets a caller opt into the transport wording through the fallback', () => {
    const err = new Error('Network Error');
    expect(apiErrorMessage(err, err.message || 'fallback')).toBe('Network Error');
    expect(apiErrorMessage(rejection(PROSE), 'fallback')).toBe(
      'Not enough gold — need 5 more'
    );
  });
});

describe('apiErrorDetail', () => {
  it('logs the prose half of a 429, never the "rate_limited" token', () => {
    expect(apiErrorDetail(rejection(THROTTLED))).toBe('Slow down — too many messages.');
  });

  it('logs `error` when it is the prose and there is no `message`', () => {
    expect(apiErrorDetail(rejection(PROSE))).toBe('Not enough gold — need 5 more');
  });

  it('logs the transport wording when the body describes nothing', () => {
    expect(apiErrorDetail(rejection({ success: false }, 'timeout of 0ms exceeded'))).toBe(
      'timeout of 0ms exceeded'
    );
  });

  // utils/logger JSON-stringifies any object it is handed and POSTs it to
  // /api/logs/browser; AxiosError.toJSON() carries config.headers.Authorization
  // — the Bearer session id — with it. The last resort is the STRING form, so
  // there is no object for the logger to unpack.
  it('returns a string even for a thrown non-error, so no object reaches the log sink', () => {
    const authorization = 'Bearer session-abc123';
    const axiosLike = {
      toJSON: () => ({ config: { headers: { Authorization: authorization } } }),
      toString: () => 'AxiosError: Network Error',
    };

    const detail = apiErrorDetail(axiosLike);

    expect(typeof detail).toBe('string');
    expect(detail).toBe('AxiosError: Network Error');
    expect(JSON.stringify(detail)).not.toContain(authorization);
  });

  describe('the `@returns {string}` promise, which used to be false', () => {
    // Callers all do `console.error('…:', apiErrorDetail(err))`
    // (hooks/useNpcChat.js), so a non-string return logged `[object Object]`
    // and a throwing one replaced the failure being reported with a different
    // failure. Neither was loud.

    it('renders a non-string `message` readably instead of returning the object', () => {
      const detail = apiErrorDetail(rejection({ message: { field: 'password' } }));

      expect(typeof detail).toBe('string');
      // `String({…})` would be '[object Object]', which is the empty log line
      // this function exists to avoid.
      expect(detail).toContain('password');
    });

    it('renders a non-string `error` readably', () => {
      const detail = apiErrorDetail(rejection({ error: ['too short', 'no digit'] }));

      expect(typeof detail).toBe('string');
      expect(detail).toContain('too short');
    });

    it('does not throw on a value `String()` cannot convert', () => {
      // `String(Object.create(null))` raises TypeError: Cannot convert object
      // to primitive value. The old last resort was exactly that call.
      const bare = Object.create(null);

      expect(() => apiErrorDetail(bare)).not.toThrow();
      expect(typeof apiErrorDetail(bare)).toBe('string');
    });

    it('never returns an empty string', () => {
      // An empty `message` is not a description. Returning it would keep the
      // promise's letter and lose the thing the promise is for.
      const err = Object.assign(new Error(''), {
        response: { data: { message: '', error: '' } },
      });

      expect(apiErrorDetail(err)).not.toBe('');
    });

    it('returns a string for anything at all', () => {
      const circular = {};
      circular.self = circular;
      const odd = [
        undefined, null, '', 0, false, NaN, Symbol('sym'), 10n,
        () => {}, [], circular, new Error('boom'),
        Object.create(null), { message: 0 }, { error: false },
      ];

      for (const value of odd) {
        const detail = apiErrorDetail(value);
        expect(typeof detail, String(detail)).toBe('string');
        expect(detail.length, String(detail)).toBeGreaterThan(0);
      }
    });

    it('still never JSON-stringifies the thrown value itself', () => {
      // The body-field renderer must not be reachable from `err`: doing that
      // would walk an AxiosError through toJSON() and put the Bearer header
      // back in the log line, which is the whole reason the last resort is a
      // string form.
      const authorization = 'Bearer session-abc123';
      const rejected = {
        response: { data: 'a proxy error page, not a body' },
        config: { headers: { Authorization: authorization } },
        toString: () => 'AxiosError: Request failed with status code 502',
      };

      const detail = apiErrorDetail(rejected);

      expect(detail).not.toContain(authorization);
      expect(detail).toBe('AxiosError: Request failed with status code 502');
    });
  });
});
