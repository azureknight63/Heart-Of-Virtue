"""Tests for the shared bounded rate limiter (src/api/rate_limiter.py).

Covers GitHub issue #284's bounded-growth requirement: a spray attack across
many distinct keys (usernames/IPs, session ids) must not grow the in-memory
store unboundedly for the lifetime of the process.
"""

import time

from src.api.rate_limiter import RateLimiter, _SWEEP_INTERVAL


class TestRateLimiterBasics:
    def test_not_limited_initially(self):
        limiter = RateLimiter(limit=10, window_seconds=900)
        assert limiter.is_limited("fresh_key") is False

    def test_limited_after_hitting_limit(self):
        limiter = RateLimiter(limit=5, window_seconds=900)
        key = "user:1.2.3.4"
        for _ in range(5):
            limiter.record(key)
        assert limiter.is_limited(key) is True

    def test_not_limited_below_limit(self):
        limiter = RateLimiter(limit=5, window_seconds=900)
        key = "user:1.2.3.4"
        for _ in range(4):
            limiter.record(key)
        assert limiter.is_limited(key) is False

    def test_clear_resets_key(self):
        limiter = RateLimiter(limit=3, window_seconds=900)
        key = "user:1.2.3.4"
        for _ in range(3):
            limiter.record(key)
        assert limiter.is_limited(key) is True
        limiter.clear(key)
        assert limiter.is_limited(key) is False

    def test_expired_hits_dont_count(self):
        limiter = RateLimiter(limit=3, window_seconds=900)
        key = "user:1.2.3.4"
        now = time.time()
        # Manually seed timestamps that are already outside the window.
        with limiter._lock:
            limiter._store[key] = [now - 1000, now - 1000, now - 1000]
        assert limiter.is_limited(key) is False

    def test_check_and_record_atomic_semantics(self):
        limiter = RateLimiter(limit=2, window_seconds=900)
        key = "session-abc"
        assert limiter.check_and_record(key) is False  # 1st recorded
        assert limiter.check_and_record(key) is False  # 2nd recorded
        # Now at the limit — should report limited and NOT record a 3rd hit.
        assert limiter.check_and_record(key) is True
        assert limiter.size() == 1


class TestRateLimiterBoundedGrowth:
    """The core issue #284 regression coverage: unbounded key growth."""

    def test_expired_keys_are_swept_after_sweep_interval(self):
        limiter = RateLimiter(limit=10, window_seconds=0.01, max_keys=100000)

        num_keys = 300
        for i in range(num_keys):
            limiter.record(f"user{i}:10.0.0.{i % 255}")

        # Backdate every recorded timestamp so it's outside the window. This
        # suite globally no-ops `time.sleep` (see tests/conftest.py), so we
        # simulate elapsed time directly rather than sleeping for real.
        with limiter._lock:
            very_old = time.time() - 1000
            for key in list(limiter._store.keys()):
                limiter._store[key] = [very_old]
            # Force the write counter right up against the sweep boundary so
            # the next write deterministically triggers `_sweep_locked`,
            # regardless of exactly where the loop above left the counter.
            limiter._writes_since_sweep = _SWEEP_INTERVAL

        # This write triggers `_maybe_sweep_locked`, which sweeps every key
        # with no fresh timestamps left (i.e. all `num_keys` of them).
        limiter.record("trigger-sweep-key")

        # Only the just-written key should survive.
        assert limiter.size() <= 2
        assert limiter.size() < num_keys

    def test_hard_cap_bounds_store_regardless_of_sweep_timing(self):
        max_keys = 50
        # Long window so nothing expires — forces the LRU cap to do the work.
        limiter = RateLimiter(limit=10, window_seconds=900, max_keys=max_keys)

        num_keys = 500
        for i in range(num_keys):
            limiter.record(f"spray-user-{i}:203.0.113.{i % 255}")
            # The cap must hold after every single write, not just at the end.
            assert limiter.size() <= max_keys

        assert limiter.size() <= max_keys

    def test_many_distinct_failed_login_style_keys_stay_bounded(self):
        """Simulates a spray attack: many distinct username:ip pairs each
        recording a handful of failed attempts (as auth.py's login throttle
        does), and asserts the store never exceeds the configured cap."""
        max_keys = 200
        limiter = RateLimiter(limit=10, window_seconds=900, max_keys=max_keys)

        for i in range(2000):
            key = f"attacker{i}:198.51.100.{i % 255}"
            # A couple of failed attempts per distinct identity, like
            # auth.py's `_record_failed_login` would produce.
            limiter.record(key)
            limiter.record(key)
            assert limiter.size() <= max_keys

        assert limiter.size() <= max_keys

    def test_lru_eviction_keeps_recently_touched_keys(self):
        limiter = RateLimiter(limit=10, window_seconds=900, max_keys=3)
        limiter.record("a")
        limiter.record("b")
        limiter.record("c")
        # Touch "a" again so it's most-recently-used.
        limiter.record("a")
        # Adding a 4th distinct key must evict the least-recently-touched
        # key, which is "b" (touched only once, before "a" was re-touched).
        limiter.record("d")

        assert limiter.size() == 3
        with limiter._lock:
            remaining = set(limiter._store.keys())
        assert "b" not in remaining
        assert {"a", "c", "d"}.issubset(remaining)

    def test_limited_key_is_not_evicted_by_key_spray(self):
        """Issue #410: LRU eviction must not reset a throttled key.

        A victim key that is currently at/over the limit must survive a flood
        of distinct throwaway keys, otherwise an attacker could LRU-evict the
        victim's throttle and re-enable brute force against it.
        """
        limit = 5
        max_keys = 10
        limiter = RateLimiter(limit=limit, window_seconds=900, max_keys=max_keys)

        victim = "victim:1.2.3.4"
        for _ in range(limit):
            limiter.record(victim)
        assert limiter.is_limited(victim) is True

        # Flood with many distinct (non-limited) keys — far more than the cap.
        for i in range(max_keys * 20):
            limiter.record(f"spray-{i}:203.0.113.{i % 255}")

        # The victim must still be tracked and still limited.
        with limiter._lock:
            assert victim in limiter._store
        assert limiter.is_limited(victim) is True

    def test_expired_key_that_looks_limited_is_still_evictable(self):
        """A key whose hits have all expired must not count as limited during
        cap enforcement — otherwise stale keys would pin the store above cap."""
        limit = 3
        limiter = RateLimiter(limit=limit, window_seconds=0.05, max_keys=5)
        for _ in range(limit):
            limiter.record("stale:9.9.9.9")
        time.sleep(0.08)  # let the stale key's window fully expire
        for i in range(50):
            limiter.record(f"fresh-{i}:198.51.100.{i % 255}")
        assert limiter.size() <= 5
