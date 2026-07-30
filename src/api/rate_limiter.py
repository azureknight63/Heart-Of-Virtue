"""Shared in-memory sliding-window rate limiter.

Used by ``src/api/routes/auth.py`` (login throttle) and
``src/api/routes/feedback.py`` (feedback submission throttle).

**Known limitation (tracked in GitHub issue #284):** this store is
per-process. Under multiple Gunicorn workers, the *effective* limit for a
given key is ``limit * worker_count`` because each worker keeps its own
independent store. Moving to a shared store (e.g. Redis) is a larger
infrastructure decision than either call site warrants today, and this
project does not currently depend on Redis or flask-limiter — see CLAUDE.md's
dependency policy. This module only fixes the *unbounded growth* half of the
issue: a spray attack across many distinct keys (usernames/IPs, session ids)
must not grow the store for the lifetime of the process.

Bounding strategy:
    - Every write prunes the target key's own expired timestamps (cheap,
      same as the original implementation).
    - Every ``_SWEEP_INTERVAL`` writes, a full sweep drops every key whose
      timestamps have all expired, so idle keys don't linger.
    - After every write, a hard cap (``max_keys``) is enforced via LRU
      eviction (oldest-touched key first) so the store size is bounded even
      between sweeps or under a sustained flood of distinct keys.
"""

import threading
import time
from collections import OrderedDict

# How many writes to allow between full sweeps of expired keys. Keeps the
# amortized cost of sweeping low while still reclaiming idle keys promptly.
_SWEEP_INTERVAL = 200

# Hard cap on distinct keys tracked at once. Chosen generously above expected
# legitimate traffic; it exists purely as a backstop against unbounded growth,
# not as a tuned production limit.
_DEFAULT_MAX_KEYS = 5000


class RateLimiter:
    """A bounded, thread-safe sliding-window rate limiter.

    Not shared across processes/workers — see module docstring.
    """

    def __init__(self, limit: int, window_seconds: float, max_keys: int = _DEFAULT_MAX_KEYS):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        # OrderedDict used as an LRU: `move_to_end` on every touch, evict from
        # the front when over `max_keys`.
        self._store: "OrderedDict[str, list]" = OrderedDict()
        self._lock = threading.Lock()
        self._writes_since_sweep = 0

    def _prune_locked(self, key: str, now: float) -> list:
        """Drop expired timestamps for `key` and return the surviving list."""
        hits = [t for t in self._store.get(key, ()) if t > now - self.window_seconds]
        if hits:
            self._store[key] = hits
        else:
            self._store.pop(key, None)
        return hits

    def _sweep_locked(self, now: float) -> None:
        """Drop every key whose timestamps have fully expired."""
        cutoff = now - self.window_seconds
        stale = []
        for key, hits in self._store.items():
            fresh = [t for t in hits if t > cutoff]
            if fresh:
                self._store[key] = fresh
            else:
                stale.append(key)
        for key in stale:
            del self._store[key]

    def _enforce_cap_locked(self, now: float) -> None:
        """Evict least-recently-touched keys down to ``max_keys``.

        Never evicts a key that is *currently at/over the limit*: doing so
        would silently reset a throttled key's window, which an attacker
        could weaponize by flooding the store with ``max_keys`` distinct
        throwaway keys to LRU-evict a targeted victim and re-enable brute
        force against it (issue #410). Expired timestamps are pruned per
        candidate so a key that only *looks* limited (stale hits) is still
        eligible for eviction. If every remaining key is genuinely limited
        the store may briefly exceed the cap — that population is bounded by
        real throttled traffic, not by attacker-controlled key spray.
        """
        if len(self._store) <= self.max_keys:
            return
        cutoff = now - self.window_seconds
        for key in list(self._store):  # least-recently-touched first
            if len(self._store) <= self.max_keys:
                break
            fresh = [t for t in self._store[key] if t > cutoff]
            if len(fresh) >= self.limit:
                # Currently limited — keep it, and refresh its pruned list.
                self._store[key] = fresh
                continue
            del self._store[key]

    def _maybe_sweep_locked(self, now: float) -> None:
        self._writes_since_sweep += 1
        if self._writes_since_sweep >= _SWEEP_INTERVAL:
            self._sweep_locked(now)
            self._writes_since_sweep = 0
        self._enforce_cap_locked(now)

    def is_limited(self, key: str) -> bool:
        """Return True if `key` is currently at/over the limit.

        Does not record a new attempt; pair with `record()` when the caller
        needs to check-then-conditionally-act (e.g. auth.py checks before
        calling out to `authenticate_user`, and only records on failure).
        """
        with self._lock:
            now = time.time()
            hits = self._prune_locked(key, now)
            if hits:
                self._store.move_to_end(key)
            return len(hits) >= self.limit

    def record(self, key: str) -> None:
        """Record an attempt for `key` at the current time."""
        with self._lock:
            now = time.time()
            hits = self._prune_locked(key, now)
            hits.append(now)
            self._store[key] = hits
            self._store.move_to_end(key)
            self._maybe_sweep_locked(now)

    def check_and_record(self, key: str) -> bool:
        """Atomically check-then-record: if `key` is already at/over the
        limit, return True without recording. Otherwise record this attempt
        and return False.

        Matches feedback.py's original "check, and count this call unless
        already limited" semantics in a single locked operation.
        """
        with self._lock:
            now = time.time()
            hits = self._prune_locked(key, now)
            if len(hits) >= self.limit:
                self._store.move_to_end(key)
                return True
            hits.append(now)
            self._store[key] = hits
            self._store.move_to_end(key)
            self._maybe_sweep_locked(now)
            return False

    def clear(self, key: str) -> None:
        """Forget all recorded attempts for `key` (e.g. on successful login)."""
        with self._lock:
            self._store.pop(key, None)

    def clear_all(self) -> None:
        """Drop all tracked keys. Intended for test isolation."""
        with self._lock:
            self._store.clear()
            self._writes_since_sweep = 0

    def size(self) -> int:
        """Number of distinct keys currently tracked (for tests/monitoring)."""
        with self._lock:
            return len(self._store)
