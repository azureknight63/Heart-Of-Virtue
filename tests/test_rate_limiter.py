"""Tests for the shared bounded rate limiter (src/api/rate_limiter.py).

Covers GitHub issue #284's bounded-growth requirement: a spray attack across
many distinct keys (usernames/IPs, session ids) must not grow the in-memory
store unboundedly for the lifetime of the process.
"""

import time
from contextlib import contextmanager
from unittest.mock import patch

from src.api.rate_limiter import RateLimiter, _SWEEP_INTERVAL


@contextmanager
def fake_clock(start=1_000_000.0):
    """Drive ``rate_limiter``'s notion of *now* from the test.

    Every window-expiry behaviour in this module is a function of
    ``time.time()``. The obvious way to test it -- ``time.sleep()`` -- does
    not work here: tests/conftest.py installs an autouse fixture that no-ops
    ``time.sleep`` suite-wide, so a test that "waits" for a window to expire
    waits for exactly nothing and then asserts against a store where nothing
    expired. (``test_expired_key_that_looks_limited_is_still_evictable``
    below was written that way and consequently proved only that the LRU cap
    holds -- which its sibling tests already prove.)

    Patching the module's clock instead makes expiry deterministic *and*
    instant. Yields a ``tick(seconds)`` callable.
    """
    current = [start]

    def tick(seconds):
        current[0] += seconds

    with patch("src.api.rate_limiter.time.time", lambda: current[0]):
        yield tick


def keys_of(limiter):
    """Snapshot the tracked key set under the limiter's own lock."""
    with limiter._lock:
        return set(limiter._store)


def hits_for(limiter, key):
    """Raw (unpruned) timestamp list recorded for ``key``."""
    with limiter._lock:
        return list(limiter._store.get(key, []))


class TestRateLimiterBasics:
    def test_not_limited_initially(self):
        limiter = RateLimiter(limit=10, window_seconds=900)
        assert limiter.is_limited("fresh_key") is False
        # is_limited must not create the key: an unauthenticated caller can
        # pick the key (username:ip), so a checking read that allocated a
        # store entry would itself be the unbounded-growth vector #284 is
        # about.
        assert limiter.size() == 0

    def test_is_limited_does_not_record(self):
        limiter = RateLimiter(limit=2, window_seconds=900)
        for _ in range(10):
            assert limiter.is_limited("k") is False
        limiter.record("k")
        assert limiter.is_limited("k") is False
        limiter.record("k")
        assert limiter.is_limited("k") is True

    def test_limited_after_hitting_limit(self):
        limiter = RateLimiter(limit=5, window_seconds=900)
        key = "user:1.2.3.4"
        for i in range(5):
            # The Nth call is the first that blocks -- assert the transition,
            # not just the end state. Asserting only the final True passes for
            # an off-by-one that starts blocking at the 4th attempt.
            assert limiter.is_limited(key) is (i >= 5)
            limiter.record(key)
        assert limiter.is_limited(key) is True
        assert len(hits_for(limiter, key)) == 5

    def test_not_limited_below_limit(self):
        limiter = RateLimiter(limit=5, window_seconds=900)
        key = "user:1.2.3.4"
        for _ in range(4):
            limiter.record(key)
        assert limiter.is_limited(key) is False

    def test_clear_resets_key(self):
        limiter = RateLimiter(limit=3, window_seconds=900)
        key = "user:1.2.3.4"
        other = "other:5.6.7.8"
        for _ in range(3):
            limiter.record(key)
            limiter.record(other)
        assert limiter.is_limited(key) is True
        limiter.clear(key)
        assert limiter.is_limited(key) is False
        # Dropped outright, not merely pruned to an empty list -- an empty
        # list left behind would still occupy a slot against max_keys.
        assert keys_of(limiter) == {other}
        # ...and clearing one key must not clear its neighbours (a successful
        # login clears only that user's throttle).
        assert limiter.is_limited(other) is True

    def test_clear_of_unknown_key_is_a_noop(self):
        limiter = RateLimiter(limit=3, window_seconds=900)
        limiter.record("present")
        limiter.clear("never-seen")
        assert keys_of(limiter) == {"present"}

    def test_clear_all_drops_every_key_and_resets_the_sweep_counter(self):
        limiter = RateLimiter(limit=3, window_seconds=900)
        for i in range(5):
            limiter.record(f"k{i}")
        assert limiter._writes_since_sweep == 5
        limiter.clear_all()
        assert limiter.size() == 0
        assert limiter._writes_since_sweep == 0

    def test_expired_hits_dont_count(self):
        limiter = RateLimiter(limit=3, window_seconds=900)
        key = "user:1.2.3.4"
        now = time.time()
        # Manually seed timestamps that are already outside the window.
        with limiter._lock:
            limiter._store[key] = [now - 1000, now - 1000, now - 1000]
        assert limiter.is_limited(key) is False
        # And the read pruned them away rather than leaving dead weight.
        assert keys_of(limiter) == set()

    def test_window_slides_rather_than_resetting_wholesale(self):
        """The three hits must expire independently, one per tick.

        A "reset the whole key once any hit expires" implementation would
        also satisfy a test that only checks limited-then-not-limited, so
        step the clock through the partial-expiry states explicitly.
        """
        limiter = RateLimiter(limit=3, window_seconds=100)
        with fake_clock() as tick:
            limiter.record("k")   # t+0
            tick(40)
            limiter.record("k")   # t+40
            tick(40)
            limiter.record("k")   # t+80
            assert limiter.is_limited("k") is True

            tick(21)              # t+101: the t+0 hit falls out (2 left)
            # Pruning is lazy -- it happens inside a read/write, never on a
            # bare clock tick -- so read through is_limited() before
            # inspecting the store.
            assert limiter.is_limited("k") is False
            assert len(hits_for(limiter, "k")) == 2

            tick(40)              # t+141: the t+40 hit falls out (1 left)
            assert limiter.is_limited("k") is False
            assert len(hits_for(limiter, "k")) == 1

            tick(41)              # t+182: everything is stale
            assert limiter.is_limited("k") is False
            assert keys_of(limiter) == set()

    def test_boundary_timestamp_exactly_one_window_old_is_expired(self):
        """`t > now - window` is a strict comparison, so a hit landing exactly
        `window` seconds ago no longer counts. Pinned because flipping it to
        `>=` would extend every throttle window by a tick."""
        limiter = RateLimiter(limit=1, window_seconds=100)
        with fake_clock() as tick:
            limiter.record("k")
            tick(100)
            assert limiter.is_limited("k") is False

    def test_check_and_record_atomic_semantics(self):
        limiter = RateLimiter(limit=2, window_seconds=900)
        key = "session-abc"
        assert limiter.check_and_record(key) is False  # 1st recorded
        assert limiter.check_and_record(key) is False  # 2nd recorded
        assert hits_for(limiter, key) and len(hits_for(limiter, key)) == 2
        # Now at the limit — should report limited and NOT record a 3rd hit.
        assert limiter.check_and_record(key) is True
        assert limiter.size() == 1
        # The "NOT record" half is the substantive claim: a blocked call that
        # still appended would extend the lockout every time the caller
        # retried, turning a 15-minute throttle into an indefinite one.
        for _ in range(10):
            limiter.check_and_record(key)
        assert len(hits_for(limiter, key)) == 2

    def test_check_and_record_releases_after_the_window(self):
        limiter = RateLimiter(limit=2, window_seconds=100)
        with fake_clock() as tick:
            assert limiter.check_and_record("k") is False
            assert limiter.check_and_record("k") is False
            assert limiter.check_and_record("k") is True
            tick(101)
            # Window elapsed: the call is allowed *and* records afresh.
            assert limiter.check_and_record("k") is False
            assert len(hits_for(limiter, "k")) == 1


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

        # Only the just-written key survives. `size() <= 2` was the previous
        # assertion and would have passed with the sweep deleting nothing but
        # the LRU cap doing the work -- pin the exact surviving key instead.
        assert keys_of(limiter) == {"trigger-sweep-key"}
        # ...and the sweep counter restarted, so the next 199 writes are cheap.
        assert limiter._writes_since_sweep == 0

    def test_hard_cap_bounds_store_regardless_of_sweep_timing(self):
        max_keys = 50
        # Long window so nothing expires — forces the LRU cap to do the work.
        limiter = RateLimiter(limit=10, window_seconds=900, max_keys=max_keys)

        num_keys = 500
        for i in range(num_keys):
            limiter.record(f"spray-user-{i}:203.0.113.{i % 255}")
            # The cap must hold after every single write, not just at the end.
            assert limiter.size() <= max_keys

        # The cap is enforced *down to* max_keys, not merely "below some
        # bound": a `size() <= max_keys` assertion alone also passes for an
        # implementation that evicts everything on every write, which would
        # silently disable the throttle. Assert the store is actually full and
        # holding the most recent arrivals.
        assert limiter.size() == max_keys
        survivors = keys_of(limiter)
        assert f"spray-user-{num_keys - 1}:203.0.113.{(num_keys - 1) % 255}" in survivors
        assert "spray-user-0:203.0.113.0" not in survivors

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

        assert limiter.size() == max_keys

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
        cap enforcement — otherwise stale keys would pin the store above cap.

        Previously this test called ``time.sleep(0.08)`` to age the stale key
        out of its window. tests/conftest.py no-ops ``time.sleep`` suite-wide,
        so no time passed, the "stale" key was never stale, and the only
        surviving assertion (``size() <= 5``) was satisfied by the LRU cap
        alone -- i.e. it exercised none of the branch it names. The fake clock
        makes the expiry real.
        """
        limit = 3
        limiter = RateLimiter(limit=limit, window_seconds=100, max_keys=5)
        with fake_clock() as tick:
            for _ in range(limit):
                limiter.record("stale:9.9.9.9")
            assert limiter.is_limited("stale:9.9.9.9") is True

            tick(101)  # the stale key's whole window falls out
            for i in range(50):
                limiter.record(f"fresh-{i}:198.51.100.{i % 255}")

            assert limiter.size() == 5
            # The substantive claim: `_enforce_cap_locked` re-prunes each
            # eviction candidate, so a key holding `limit` *expired* hits is
            # NOT protected by the issue-#410 keep-limited-keys rule.
            assert "stale:9.9.9.9" not in keys_of(limiter)

    def test_cap_may_be_exceeded_when_every_key_is_genuinely_limited(self):
        """The documented escape hatch in ``_enforce_cap_locked``.

        Real throttled traffic is allowed to push the store past ``max_keys``
        rather than let an attacker LRU-evict a victim's throttle (#410).
        Pinned so the tradeoff cannot be silently reversed into "cap always
        wins", which is exactly the #410 regression.
        """
        max_keys = 3
        # limit=1 so a single write makes a key limited immediately; that is
        # the only way to build a store where *every* key is protected,
        # because a half-recorded key is evicted before it can reach the
        # limit (see test_saturated_store_cannot_admit_new_keys).
        limiter = RateLimiter(limit=1, window_seconds=900, max_keys=max_keys)
        for i in range(10):
            limiter.record(f"limited-{i}")

        assert limiter.size() == 10 > max_keys
        for i in range(10):
            assert limiter.is_limited(f"limited-{i}") is True

    def test_saturated_store_cannot_admit_new_keys(self):
        """Documenting the flip side of the #410 keep-limited-keys rule.

        Once ``max_keys`` throttled keys are resident, a *new* key is evicted
        on the very write that creates it (it holds one hit, below the limit,
        so it is the first eviction candidate) and can therefore never
        accumulate enough hits to become throttled itself. The store stays
        pinned at the cap. This is a real availability tradeoff, not an
        accident -- pinned here so a change to the eviction order has to
        confront it.
        """
        limit = 2
        max_keys = 3
        limiter = RateLimiter(limit=limit, window_seconds=900, max_keys=max_keys)
        for i in range(max_keys):
            for _ in range(limit):
                limiter.record(f"limited-{i}")
        assert limiter.size() == max_keys

        for _ in range(20):
            limiter.record("newcomer")
        assert "newcomer" not in keys_of(limiter)
        assert limiter.is_limited("newcomer") is False
        assert limiter.size() == max_keys

    def test_unlimited_keys_are_evicted_before_limited_ones(self):
        limit = 3
        limiter = RateLimiter(limit=limit, window_seconds=900, max_keys=4)
        for _ in range(limit):
            limiter.record("throttled")
        # Four more distinct keys, each below the limit, added oldest-first.
        for i in range(4):
            limiter.record(f"casual-{i}")

        survivors = keys_of(limiter)
        assert "throttled" in survivors
        # The casual keys compete for the remaining slots by recency.
        assert "casual-0" not in survivors
        assert "casual-3" in survivors
