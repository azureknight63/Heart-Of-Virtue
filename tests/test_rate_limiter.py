"""Tests for the shared rate-limiting module (src/api/rate_limiter.py).

Covers three things the route blueprints all depend on:

* GitHub issue #284's bounded-growth requirement: a spray attack across many
  distinct keys (usernames/IPs, session ids) must not grow the in-memory store
  unboundedly for the lifetime of the process.
* ``client_ip`` -- the one client-identity rule every IP-keyed limiter shares:
  routable IPv6 collapsed to /64, everything else (IPv4, IPv4-mapped IPv6,
  loopback) kept whole. Getting that order wrong mapped every IPv4 client on a
  dual-stack listener onto a single key and locked the login endpoint out for
  all of them.
* ``limiter_from_env`` -- the one env-var parse, whose whole reason for
  existing is that a malformed value must never take the API down at boot nor
  read as "unlimited".
* The two call-site helpers the parse guard is worthless without:
  ``RateLimiter.check`` (a ``None`` tier never limits) and
  ``rate_limited_response`` (one 429 body for the whole API).
* The contract that body's ``error`` field carries: a machine token there is
  only legible to a *person* if ``message`` comes with it, because
  ``frontend/src/utils/apiError.js`` reads ``message || error || fallback``.
  Guarded twice -- at runtime for a blank message reaching the helper, and by
  an AST scan over ``src/api`` for a route that hand-builds the body and never
  reaches the helper at all.
"""

import ast
import logging
import pathlib
import time
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from flask import Flask

from src.api.rate_limiter import (
    MACHINE_TOKEN_ERROR,
    RATE_LIMITED_ERROR,
    RateLimiter,
    _SWEEP_INTERVAL,
    client_ip,
    limiter_from_env,
    rate_limited_response,
)


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


class TestClientIp:
    """``client_ip`` is the one client-identity rule every IP-keyed limiter in
    the API shares. It used to be copy-pasted into both ``auth.py`` and
    ``npc_chat.py``; these tests moved here with the function.
    """

    def test_outside_request_context_is_unknown(self):
        """Direct helper calls (no request context) must not raise."""
        assert client_ip() == "unknown"

    def test_collapses_ipv6_to_64_prefix(self):
        """IPv6 clients are throttled per /64 so an attacker can't rotate the
        low bits within their allocation to dodge the limit."""
        app = Flask(__name__)
        with app.test_request_context(
            "/", environ_base={"REMOTE_ADDR": "2001:db8:abcd:1234::dead:beef"}
        ):
            assert client_ip() == "2001:db8:abcd:1234::"

    def test_two_addresses_in_one_allocation_share_a_key(self):
        """The point of the collapsing: rotating the low 64 bits buys nothing."""
        app = Flask(__name__)
        keys = set()
        for suffix in ("::1", "::2", ":ffff:ffff:ffff:ffff"):
            with app.test_request_context(
                "/", environ_base={"REMOTE_ADDR": f"2001:db8:abcd:1234{suffix}"}
            ):
                keys.add(client_ip())
        assert keys == {"2001:db8:abcd:1234::"}

    def test_passes_ipv4_through(self):
        app = Flask(__name__)
        with app.test_request_context(
            "/", environ_base={"REMOTE_ADDR": "198.51.100.7"}
        ):
            assert client_ip() == "198.51.100.7"

    def test_unparseable_colon_value_is_used_verbatim(self):
        """A malformed address must still produce a usable (if coarse) key
        rather than raising on the request path."""
        app = Flask(__name__)
        with app.test_request_context(
            "/", environ_base={"REMOTE_ADDR": "not:an:address"}
        ):
            assert client_ip() == "not:an:address"

    def test_missing_remote_addr_is_unknown(self):
        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": None}):
            assert client_ip() == "unknown"

    def test_ipv4_mapped_clients_do_not_share_a_key(self):
        """A dual-stack (``[::]``) listener reports IPv4 peers as
        ``::ffff:a.b.c.d``. Those have all-zero top 64 bits, so collapsing
        before unwrapping them mapped *every* IPv4 client onto the single key
        ``"::"`` -- ten failed logins from anywhere locked one account out for
        everyone, and sixty locked out the login endpoint entirely.
        """
        app = Flask(__name__)
        keys = []
        for mapped in ("::ffff:198.51.100.7", "::ffff:203.0.113.9"):
            with app.test_request_context(
                "/", environ_base={"REMOTE_ADDR": mapped}
            ):
                keys.append(client_ip())
        assert keys == ["198.51.100.7", "203.0.113.9"]
        assert len(set(keys)) == 2

    def test_ipv4_mapped_key_matches_the_bare_ipv4_key(self):
        """The same client must get the same budget whether it arrives on an
        IPv4-only or a dual-stack listener."""
        app = Flask(__name__)
        with app.test_request_context(
            "/", environ_base={"REMOTE_ADDR": "::ffff:198.51.100.7"}
        ):
            mapped_key = client_ip()
        with app.test_request_context(
            "/", environ_base={"REMOTE_ADDR": "198.51.100.7"}
        ):
            bare_key = client_ip()
        assert mapped_key == bare_key == "198.51.100.7"

    def test_ipv6_loopback_is_distinct_from_mapped_ipv4_loopback(self):
        """``::1`` and ``::ffff:127.0.0.1`` are different clients; both used to
        collapse to ``"::"`` alongside every other IPv4-mapped address."""
        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "::1"}):
            v6_loopback = client_ip()
        with app.test_request_context(
            "/", environ_base={"REMOTE_ADDR": "::ffff:127.0.0.1"}
        ):
            mapped_loopback = client_ip()
        assert v6_loopback == "::1"
        assert mapped_loopback == "127.0.0.1"
        assert v6_loopback != mapped_loopback

    def test_real_ipv6_still_collapses_to_its_allocation(self):
        """The fix must not weaken the /64 collapse for genuine IPv6: two
        addresses in one allocation still share a key."""
        app = Flask(__name__)
        keys = set()
        for suffix in ("::1", "::feed:face"):
            with app.test_request_context(
                "/", environ_base={"REMOTE_ADDR": f"2001:db8:dead:beef{suffix}"}
            ):
                keys.add(client_ip())
        assert keys == {"2001:db8:dead:beef::"}

    def test_distinct_ipv6_allocations_do_not_share_a_key(self):
        app = Flask(__name__)
        keys = set()
        for prefix in ("2001:db8:1:1", "2001:db8:1:2"):
            with app.test_request_context(
                "/", environ_base={"REMOTE_ADDR": f"{prefix}::5"}
            ):
                keys.add(client_ip())
        assert keys == {"2001:db8:1:1::", "2001:db8:1:2::"}

    def test_scoped_ipv6_does_not_raise(self):
        """``ip_network(f"{ip}/64")`` rejects a scope id outright; the integer
        mask does not."""
        app = Flask(__name__)
        with app.test_request_context(
            "/", environ_base={"REMOTE_ADDR": "fe80::1%eth0"}
        ):
            assert client_ip() == "fe80::"

    #: Addresses with an all-zero /64 prefix that are neither IPv4-mapped
    #: nor loopback, so the mapped/loopback branches never see them. Each
    #: one used to survive those branches and then be flattened to ``"::"``
    #: by the mask -- the residual half of the login DoS.
    ZERO_PREFIX_ADDRESSES = (
        "::",  # the unspecified address
        "::203.0.113.9",  # IPv4-compatible (deprecated, still parses)
        "::198.51.100.7",  # a second one, to prove they stay distinct
        "::ffff:0:203.0.113.9",  # IPv4-translated (RFC 6145)
        "::2",  # a bare low address that is not loopback
    )

    def test_zero_prefix_addresses_keep_their_own_key(self):
        """Residual of the /64-collapse DoS: unwrapping IPv4-mapped and
        loopback by name left every *other* all-zero-prefix address still
        keying to ``"::"``. Distinct clients sharing one bucket is the same
        lockout, one address family further along.
        """
        app = Flask(__name__)
        keys = []
        for addr in self.ZERO_PREFIX_ADDRESSES:
            with app.test_request_context(
                "/", environ_base={"REMOTE_ADDR": addr}
            ):
                keys.append(client_ip())
        assert "::" not in keys[1:], f"still collapsing to the shared key: {keys}"
        assert len(set(keys)) == len(self.ZERO_PREFIX_ADDRESSES), keys

    def test_the_unspecified_address_is_still_its_own_key(self):
        """``::`` is the one address whose verbatim key *is* ``"::"``. It
        must keep it -- the bug was everyone else joining it, not this."""
        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "::"}):
            assert client_ip() == "::"

    def test_zero_prefix_addresses_do_not_collide_with_loopback(self):
        """The loopback branch used to be the only thing keeping ``::1`` out
        of the shared bucket; the general rule must keep it out too."""
        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "::1"}):
            assert client_ip() == "::1"
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "::2"}):
            assert client_ip() == "::2"


class TestLimiterFromEnv:
    """Every limiter in the API is built by this factory at blueprint *import*
    time. A bare ``int()`` here once turned a typo in an env file into a
    ValueError during import and took the whole API down at boot, so the
    contract is: garbled falls back to the default (limiter stays ON) with a
    warning, and only an exact 0 disables.
    """

    VAR = "TEST_RATE_LIMIT_FROM_ENV"

    def test_unset_uses_the_default(self, monkeypatch):
        monkeypatch.delenv(self.VAR, raising=False)
        limiter = limiter_from_env(self.VAR, 7, 60)
        assert limiter is not None
        assert limiter.limit == 7
        assert limiter.window_seconds == 60

    def test_blank_uses_the_default(self, monkeypatch):
        monkeypatch.setenv(self.VAR, "   ")
        assert limiter_from_env(self.VAR, 7, 60).limit == 7

    def test_explicit_value_wins(self, monkeypatch):
        monkeypatch.setenv(self.VAR, " 3 ")
        assert limiter_from_env(self.VAR, 7, 60).limit == 3

    def test_zero_disables(self, monkeypatch):
        monkeypatch.setenv(self.VAR, "0")
        assert limiter_from_env(self.VAR, 7, 60) is None

    def test_garbled_value_falls_back_to_default_with_a_warning(
        self, monkeypatch, caplog
    ):
        """The boot outage this factory exists to prevent: a one-character
        typo must not raise, and must not silently disable the limiter."""
        monkeypatch.setenv(self.VAR, "twenty")
        with caplog.at_level(logging.WARNING, logger="src.api.rate_limiter"):
            limiter = limiter_from_env(self.VAR, 7, 60)
        assert limiter is not None, "a typo must never read as unlimited"
        assert limiter.limit == 7
        assert self.VAR in caplog.text

    def test_negative_value_falls_back_to_default_with_a_warning(
        self, monkeypatch, caplog
    ):
        """A negative value parses cleanly, so it used to slip past the typo
        guard and through the call site's ``> 0`` test into an unlimited,
        unlogged endpoint. Only an exact 0 is the documented disable.
        """
        monkeypatch.setenv(self.VAR, "-1")
        with caplog.at_level(logging.WARNING, logger="src.api.rate_limiter"):
            limiter = limiter_from_env(self.VAR, 7, 60)
        assert limiter is not None, "a negative value must never read as unlimited"
        assert limiter.limit == 7
        assert self.VAR in caplog.text

    def test_valid_value_logs_nothing(self, monkeypatch, caplog):
        monkeypatch.setenv(self.VAR, "5")
        with caplog.at_level(logging.WARNING, logger="src.api.rate_limiter"):
            limiter_from_env(self.VAR, 7, 60)
        assert caplog.text == ""

    def test_zero_is_refused_when_disabling_is_not_allowed(self, monkeypatch, caplog):
        """``allow_disable=False`` is for throttles whose absence is a security
        hole. A configured 0 must behave like a garbled value -- warn, keep the
        default -- not switch the throttle off.
        """
        monkeypatch.setenv(self.VAR, "0")
        with caplog.at_level(logging.WARNING, logger="src.api.rate_limiter"):
            limiter = limiter_from_env(self.VAR, 7, 60, allow_disable=False)
        assert limiter is not None, "this throttle must not be disableable"
        assert limiter.limit == 7
        assert self.VAR in caplog.text

    def test_positive_value_still_tunes_a_non_disableable_limiter(
        self, monkeypatch, caplog
    ):
        """``allow_disable=False`` blocks only 0; the threshold stays tunable."""
        monkeypatch.setenv(self.VAR, "3")
        with caplog.at_level(logging.WARNING, logger="src.api.rate_limiter"):
            limiter = limiter_from_env(self.VAR, 7, 60, allow_disable=False)
        assert limiter.limit == 3
        assert caplog.text == ""

    def test_garbled_warning_says_a_non_disableable_limiter_cannot_be_disabled(
        self, monkeypatch, caplog
    ):
        """The operator must not be told to use 0 to disable a var where 0 is
        refused."""
        monkeypatch.setenv(self.VAR, "twenty")
        with caplog.at_level(logging.WARNING, logger="src.api.rate_limiter"):
            limiter_from_env(self.VAR, 7, 60, allow_disable=False)
        assert "cannot be disabled" in caplog.text
        assert "0 to disable" not in caplog.text

    def test_a_non_disableable_limiter_refuses_a_zero_default(self, monkeypatch):
        """The ``allow_disable=False`` contract is "this cannot return None",
        and the login helpers dereference their limiters without a None check
        on the strength of it. ``default=0`` walked straight past both guards
        to the final ``if limit == 0: return None`` and broke that promise, so
        it is refused at build time -- a source-code mistake with no operator
        to warn and nothing to fall back to.
        """
        monkeypatch.delenv(self.VAR, raising=False)
        with pytest.raises(ValueError, match="positive default"):
            limiter_from_env(self.VAR, 0, 60, allow_disable=False)

    def test_a_disableable_limiter_may_default_to_off(self, monkeypatch):
        """The refusal above applies only where None is not a legal answer."""
        monkeypatch.delenv(self.VAR, raising=False)
        assert limiter_from_env(self.VAR, 0, 60) is None


def _limiter_constructions(source: str):
    """Line numbers of every ``RateLimiter(...)`` call in ``source``.

    Parsed with ``ast`` rather than searched for as a substring: a guard that a
    line break, an extra space (``RateLimiter (...)``) or a module-qualified
    call (``rate_limiter.RateLimiter(...)``) could walk past would read as
    coverage while providing none. ``ast`` also ignores the name appearing in a
    comment or docstring, so the guard does not fire on prose either.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if _called_name(node) == "RateLimiter":
            found.append(node.lineno)
    return found


def _called_name(node: "ast.Call"):
    """The bare function name of a call, whether or not it is dotted."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _limiter_from_env_calls(source: str):
    """Every ``limiter_from_env(...)`` call in ``source``, as
    ``(lineno, env_var_name, {keyword: value_node})``.

    ``env_var_name`` is the first positional argument when it is a literal, and
    ``None`` otherwise. It is what lets a caller tell one tier from another:
    ``auth.py`` builds three limiters and only the two *login* ones may be
    non-disableable.
    """
    calls = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if _called_name(node) != "limiter_from_env":
            continue
        var = None
        if node.args and isinstance(node.args[0], ast.Constant):
            var = node.args[0].value
        calls.append(
            (node.lineno, var, {kw.arg: kw.value for kw in node.keywords if kw.arg})
        )
    return calls


def _api_dir():
    return pathlib.Path(__file__).resolve().parent.parent / "src/api"


def _routes_dir():
    return _api_dir() / "routes"


#: The one module allowed to say ``RateLimiter(...)``: the factory that
#: owns the malformed-value guard lives there, so it is the definition
#: rather than a copy.
_LIMITER_FACTORY_MODULE = "rate_limiter.py"


def _api_modules():
    """Every module the scan below covers: all of ``src/api`` bar the
    factory itself.

    Scoped to ``routes/`` alone, the guard read as coverage while providing
    none outside it -- a limiter hand-rolled in ``services/``, ``sockets.py``
    or ``middleware/`` would have walked straight past, and the whole point
    of the guard is that the *next* limiter cannot skip the parse guard
    wherever someone puts it. Globbed recursively rather than listed, so a
    new subpackage is covered on the day it is added.
    """
    return sorted(
        path
        for path in _api_dir().rglob("*.py")
        if path.name != _LIMITER_FACTORY_MODULE
    )


class TestEveryLimiterUsesTheSharedFactory:
    """DRY guard: the parse guard above is only worth anything if the *next*
    limiter added gets it too. Each route module must expose limiters built by
    ``limiter_from_env`` (or ``None`` when disabled), not hand-rolled ones.
    """

    def test_route_limiters_are_rate_limiter_instances_or_disabled(self):
        from src.api.routes import auth, feedback, npc_chat

        limiters = {
            "auth._login_limiter": auth._login_limiter,
            "auth._ip_limiter": auth._ip_limiter,
            "auth._register_limiter": auth._register_limiter,
            "feedback._feedback_limiter": feedback._feedback_limiter,
            "npc_chat._chat_limiter": npc_chat._chat_limiter,
            "npc_chat._chat_ip_limiter": npc_chat._chat_ip_limiter,
        }
        for name, limiter in limiters.items():
            assert limiter is None or isinstance(limiter, RateLimiter), name

    def test_no_api_module_hand_rolls_a_limiter(self):
        """``RateLimiter(...)`` must be constructed in exactly one place."""
        api_dir = _api_dir()
        offenders = {
            str(path.relative_to(api_dir)).replace("\\", "/"): lines
            for path, lines in (
                (p, _limiter_constructions(p.read_text(encoding="utf-8")))
                for p in _api_modules()
            )
            if lines
        }
        assert offenders == {}, (
            "every module under src/api must build limiters via "
            "limiter_from_env so the malformed-value guard cannot be "
            f"skipped: {offenders}"
        )

    def test_the_scan_actually_reaches_beyond_routes(self):
        """Guard-the-guard, scope half: the set of scanned files must
        include modules outside ``routes/`` (and must exclude the factory,
        which legitimately constructs one). A glob quietly narrowed back to
        ``routes/*.py`` would still pass the scan above while covering
        nothing new.
        """
        api_dir = _api_dir()
        scanned = {
            str(p.relative_to(api_dir)).replace("\\", "/") for p in _api_modules()
        }
        for expected in (
            "middleware/auth.py",
            "services/session_manager.py",
            "sockets.py",
            "app.py",
            "routes/auth.py",
        ):
            assert expected in scanned, f"{expected} escapes the limiter scan"
        assert _LIMITER_FACTORY_MODULE not in scanned
        # ...and the factory really would trip the scan, so its exclusion is
        # load-bearing rather than decorative.
        assert _limiter_constructions(
            (api_dir / _LIMITER_FACTORY_MODULE).read_text(encoding="utf-8")
        )

    def test_the_guard_itself_sees_through_formatting(self):
        """Guard-the-guard: the check above must not be defeatable by writing
        the same construction differently."""
        evasions = [
            "RateLimiter(limit=1, window_seconds=1)",
            "RateLimiter (limit=1, window_seconds=1)",
            "rate_limiter.RateLimiter(limit=1, window_seconds=1)",
            "RateLimiter(\n    limit=1,\n    window_seconds=1,\n)",
        ]
        for snippet in evasions:
            assert _limiter_constructions(snippet), snippet
        # ...and must not fire on the name merely being mentioned in prose.
        assert _limiter_constructions('x = "RateLimiter("  # a RateLimiter(') == []


class TestLoginThrottlesCannotBeDisabled:
    """The login throttles are the brute-force defence on the credential path.
    An operator typing 0 -- or copying a 0 out of a dev ``.env`` -- must not be
    able to remove them, and the app must say so when they try.
    """

    #: The auth limiters whose absence is an open door rather than an
    #: inconvenience. The registration tier is deliberately NOT here: it
    #: throttles account farming, which is cost and spam, and turning it off
    #: locally is legitimate (see ``limiter_from_env``'s asymmetry note).
    LOGIN_VARS = ("LOGIN_RATE_LIMIT_PER_15_MIN", "LOGIN_IP_RATE_LIMIT_PER_15_MIN")

    def test_auth_builds_both_login_limiters_with_allow_disable_false(self):
        """Pinned structurally so a future edit cannot quietly re-open this:
        every *login* ``limiter_from_env`` call in auth.py must pass
        ``allow_disable=False``.
        """
        source = (_routes_dir() / "auth.py").read_text(encoding="utf-8")
        calls = _limiter_from_env_calls(source)
        login_calls = [c for c in calls if c[1] in self.LOGIN_VARS]
        assert len(login_calls) == 2, f"expected both login tiers, found {calls}"
        for lineno, var, keywords in login_calls:
            node = keywords.get("allow_disable")
            assert node is not None, (
                f"auth.py:{lineno} builds login limiter {var} without "
                "allow_disable=False"
            )
            assert (
                isinstance(node, ast.Constant) and node.value is False
            ), f"auth.py:{lineno} ({var}) must pass allow_disable=False"

    def test_every_auth_limiter_names_its_env_var_as_a_literal(self):
        """The guard above tells the tiers apart by that literal; a computed
        variable name would silently drop a tier out of its scope."""
        source = (_routes_dir() / "auth.py").read_text(encoding="utf-8")
        unnamed = [
            (lineno, kw)
            for lineno, var, kw in _limiter_from_env_calls(source)
            if var is None
        ]
        assert unnamed == [], f"auth.py limiters without a literal env var: {unnamed}"

    def test_the_call_scan_itself_sees_through_formatting(self):
        """Guard-the-guard, matching the one on ``_limiter_constructions``.

        Both structural checks above are only as good as this parse: a scan
        that quietly matched nothing would report every tier compliant. These
        pin that it finds the call however it is written, reads the env var and
        the keyword off it, and does not fire on the name in prose.
        """
        spellings = [
            "x = limiter_from_env('VAR', 1, 2, allow_disable=False)",
            "x = limiter_from_env (\n    'VAR',\n    1,\n    2,\n    allow_disable=False,\n)",
            "x = rate_limiter.limiter_from_env('VAR', 1, 2, allow_disable=False)",
        ]
        for snippet in spellings:
            calls = _limiter_from_env_calls(snippet)
            assert len(calls) == 1, snippet
            _lineno, var, keywords = calls[0]
            assert var == "VAR", snippet
            node = keywords.get("allow_disable")
            assert isinstance(node, ast.Constant) and node.value is False, snippet

        # A computed env var name must read back as None -- that is precisely
        # what test_every_auth_limiter_names_its_env_var_as_a_literal catches.
        (_lineno, var, _kw), = _limiter_from_env_calls(
            "x = limiter_from_env(NAME, 1, 2)"
        )
        assert var is None

        assert _limiter_from_env_calls('x = "limiter_from_env("  # prose') == []

    def test_zero_still_yields_a_live_limiter_at_the_default(self, monkeypatch, caplog):
        """Exercised through the real auth constants, so this breaks if either
        the variable name or the default drifts."""
        from src.api.routes import auth

        for var, default in (
            ("LOGIN_RATE_LIMIT_PER_15_MIN", auth._LOGIN_RATE_LIMIT),
            ("LOGIN_IP_RATE_LIMIT_PER_15_MIN", auth._IP_RATE_LIMIT),
        ):
            monkeypatch.setenv(var, "0")
            caplog.clear()
            with caplog.at_level(logging.WARNING, logger="src.api.rate_limiter"):
                limiter = limiter_from_env(
                    var, default, auth._LOGIN_RATE_WINDOW, allow_disable=False
                )
            assert limiter is not None, f"{var}=0 disabled a login throttle"
            assert limiter.limit == default
            assert var in caplog.text, f"{var}=0 was refused silently"

    def test_the_live_login_limiters_are_not_none(self):
        """Whatever the environment says, the imported blueprint has both --
        which is what lets auth.py dereference them without a None guard."""
        from src.api.routes import auth

        assert auth._login_limiter is not None
        assert auth._ip_limiter is not None


class TestNoneTolerantCheck:
    """``RateLimiter.check`` -- the ``None``-as-disabled rule, in one place.

    ``limiter_from_env`` returns ``None`` for the documented ``<VAR>=0``
    disable, so before this helper every throttled route opened with its own
    ``if _limiter is None: return False``. Four copies of a two-line rule is
    four chances to invert it and read a *disabled* tier as a *tripped* one,
    which turns a convenience switch into an outage.
    """

    def test_a_none_limiter_never_limits(self):
        for _ in range(100):
            assert RateLimiter.check(None, "any-key") is False

    def test_a_real_limiter_still_checks_and_records(self):
        limiter = RateLimiter(limit=2, window_seconds=60)
        assert RateLimiter.check(limiter, "k") is False
        assert RateLimiter.check(limiter, "k") is False
        assert RateLimiter.check(limiter, "k") is True

    def test_it_does_not_record_once_limited(self):
        """Delegates to ``check_and_record``, whose contract is that a rejected
        call is not counted -- otherwise a client hammering a tripped endpoint
        would extend its own lockout indefinitely."""
        limiter = RateLimiter(limit=1, window_seconds=60)
        assert RateLimiter.check(limiter, "k") is False
        for _ in range(5):
            assert RateLimiter.check(limiter, "k") is True
        assert len(hits_for(limiter, "k")) == 1

    def test_keys_stay_independent(self):
        limiter = RateLimiter(limit=1, window_seconds=60)
        assert RateLimiter.check(limiter, "a") is False
        assert RateLimiter.check(limiter, "b") is False
        assert RateLimiter.check(limiter, "a") is True

    def test_calling_it_on_an_instance_fails_loudly(self):
        """It is a static method so it can be called when there is no
        instance. The cost is that ``limiter.check(key)`` binds the key to the
        ``limiter`` parameter -- which must raise rather than silently answer
        the wrong question."""
        limiter = RateLimiter(limit=1, window_seconds=60)
        with pytest.raises(TypeError):
            limiter.check("k")


class TestRateLimitedResponse:
    """One 429 body for the whole API.

    Four routes grew four bodies in two incompatible shapes: ``auth.py``
    paired a machine token in ``error`` with prose in ``message``, while
    ``feedback.py`` and ``npc_chat.py`` put prose straight into ``error`` and
    shipped no ``message`` at all. A client could branch on neither.
    """

    def test_it_returns_the_canonical_shape(self):
        app = Flask(__name__)
        with app.test_request_context("/"):
            response, status = rate_limited_response("Slow down.")
            assert status == 429
            assert response.get_json() == {
                "success": False,
                "error": RATE_LIMITED_ERROR,
                "message": "Slow down.",
            }

    def test_the_error_field_is_a_stable_token(self):
        """Not prose. ``auth.py``'s neighbouring failures are tokens
        (``validation_error``, ``auth_error``, ``service_unavailable``), and a
        client backing off should not have to string-match an English sentence
        that may be reworded."""
        assert RATE_LIMITED_ERROR == "rate_limited"

    def test_the_message_is_the_endpoint_s_own(self):
        """The advice differs per endpoint -- "too many failed logins" is not
        "slow down" -- so the prose stays a parameter rather than being
        flattened into one house string."""
        app = Flask(__name__)
        with app.test_request_context("/"):
            first = rate_limited_response("a")[0].get_json()["message"]
            second = rate_limited_response("b")[0].get_json()["message"]
        assert (first, second) == ("a", "b")

    def test_the_frontend_s_field_is_present(self):
        """``frontend/src/pages/LoginPage.jsx`` renders
        ``err.response.data.message`` for any non-401, non-5xx auth failure. A
        429 body without ``message`` degrades silently to the generic
        "Authentication failed" copy, which is why ``message`` is the field the
        canonical shape had to keep."""
        app = Flask(__name__)
        with app.test_request_context("/"):
            body = rate_limited_response("Too many attempts.")[0].get_json()
        assert body["message"] == "Too many attempts."


def _rate_limit_status_literals(source: str):
    """Line numbers where ``source`` hand-builds a ``(body, 429)`` return.

    Structural, like the ``RateLimiter(...)`` scan: a ``429`` appearing in a
    comment, a docstring or a test id is prose and must not fire. Only a bare
    ``429`` sitting in a returned tuple is a hand-rolled 429 body.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Tuple):
            continue
        for element in node.value.elts:
            if isinstance(element, ast.Constant) and element.value == 429:
                found.append(node.lineno)
    return found


class TestEvery429GoesThroughTheHelper:
    """DRY guard, mirroring ``TestEveryLimiterUsesTheSharedFactory``: the
    shared 429 body is only worth anything if the *next* throttled route uses
    it.

    The four that predated ``rate_limited_response`` disagreed on the body
    in a way no client could work around: ``auth.py`` put a machine token in
    ``error`` and prose in ``message``, ``feedback.py`` and ``npc_chat.py``
    put prose in ``error`` and shipped no ``message``. A fifth would have
    picked one at random.
    """

    #: Modules still permitted to hand-roll a 429, with the reason. Empty is
    #: the goal state, and it is currently empty; anything added here is a
    #: debt, not a policy.
    _429_EXEMPT = ()

    def test_no_api_module_hand_rolls_a_429(self):
        api_dir = _api_dir()
        offenders = {}
        for path in _api_modules():
            name = str(path.relative_to(api_dir)).replace("\\", "/")
            if name in self._429_EXEMPT:
                continue
            lines = _rate_limit_status_literals(path.read_text(encoding="utf-8"))
            if lines:
                offenders[name] = lines
        assert offenders == {}, (
            "throttled routes must return rate_limited_response() so the API "
            f"has one 429 shape: {offenders}"
        )

    def test_the_429_scan_sees_a_hand_rolled_body(self):
        """Guard-the-guard: the scan must fire on the shape it exists to catch,
        however the body is spelled, and stay quiet on prose."""
        offenders = [
            'def v():\n    return jsonify({"error": "x"}), 429\n',
            'def v():\n    return (\n        jsonify({"error": "x"}),\n        429,\n    )\n',
        ]
        for snippet in offenders:
            assert _rate_limit_status_literals(snippet), snippet

        quiet = [
            'def v():\n    """Returns 429 when limited."""\n    return None\n',
            'def v():\n    # a 429 is a rate limit\n    return rate_limited_response("x")\n',
            'def v():\n    status = 429\n    return status\n',
        ]
        for snippet in quiet:
            assert _rate_limit_status_literals(snippet) == [], snippet


def _all_api_modules():
    """Every module under ``src/api``, the factory included.

    Deliberately wider than ``_api_modules()``: that scan excludes
    ``rate_limiter.py`` because the factory is the one place allowed to
    construct a limiter. Here the factory is the opposite -- it holds the one
    canonical token-plus-message body in the tree, so excluding it would drop
    the very row that proves the scan below is looking at something.
    """
    return sorted(_api_dir().rglob("*.py"))


def _module_string_constants(tree: ast.AST):
    """Module-level ``NAME = "literal"`` bindings in ``tree``.

    Without this the scan reads ``{"error": RATE_LIMITED_ERROR}`` as an unknown
    value and says nothing -- which is precisely the spelling the canonical
    body uses, so the scan would have been blind to the one shape it is
    modelled on.
    """
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target]
        else:
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            for target in targets:
                constants[target.id] = value.value
    return constants


def _imported_error_tokens(tree: ast.AST):
    """Token constants a module pulls in from ``rate_limiter`` by name.

    One entry, because there is one: a route doing ``from src.api.rate_limiter
    import RATE_LIMITED_ERROR`` and then building its own body around it is a
    real way to ship a token with no ``message``, and resolving it needs the
    value from the other module rather than this one. Taken from the live
    import at the top of this file rather than re-typed, so a rename cannot
    leave a stale copy here.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(
            "rate_limiter"
        ):
            for alias in node.names:
                if alias.name == "RATE_LIMITED_ERROR":
                    return {alias.asname or alias.name: RATE_LIMITED_ERROR}
    return {}


def _response_dicts(tree):
    """Every dict literal in ``tree`` that leaves the process as a response.

    A dict is a *body* only if it is on its way out: inside a ``return``, or an
    argument to ``jsonify``/``make_response``. Scanning every ``ast.Dict``
    instead matched any mapping that happens to have an ``error`` key, and
    ``src/api/structured_log.py``'s ``BROWSER_LEVEL_MAP`` is one -- it maps the
    browser console's level names onto the envelope vocabulary, so it contains
    the pair ``"error": "error"`` and always will. Reporting a level table as
    an illegible error body is the shape of false positive that gets a scan
    silenced with a ``# noqa``, which is the same failure this guard's own
    docstring warns about one paragraph up.
    """
    out = []
    for node in ast.walk(tree):
        emitting = isinstance(node, ast.Return) or (
            isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id in _RESPONSE_CALLS)
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in _RESPONSE_CALLS
                )
            )
        )
        if not emitting:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Dict):
                out.append(child)
    return out


#: Calls whose argument becomes the response body. ``return`` covers the rest,
#: including a helper that builds a body and hands it back for a caller to
#: jsonify.
_RESPONSE_CALLS = {"jsonify", "make_response"}


def token_error_bodies(source: str):
    """Every failure body in ``source`` whose ``error`` is a machine token.

    Returns ``(lineno, token, has_message)`` triples. Structural rather than
    textual: a token named in a comment or a docstring is prose *about* the
    contract, not an instance of it, and a scan that cried wolf on those would
    be silenced with a ``# noqa`` and stop guarding -- the same reasoning as
    the ``429`` scan above.
    """
    tree = ast.parse(source)
    names = dict(_module_string_constants(tree))
    names.update(_imported_error_tokens(tree))

    found = []
    seen = set()
    for node in _response_dicts(tree):
        if id(node) in seen:
            continue
        seen.add(id(node))
        keys = {}
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys[key.value] = value
        if "error" not in keys:
            continue

        value = keys["error"]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            token = value.value
        elif isinstance(value, ast.Name):
            token = names.get(value.id)
        else:
            token = None
        if token is None or not MACHINE_TOKEN_ERROR.match(token):
            continue

        found.append((node.lineno, token, "message" in keys))
    return sorted(found)


def token_errors_without_message(source: str):
    """Line numbers where ``source`` ships a token in ``error`` and no prose."""
    return [
        line for line, _token, has_message in token_error_bodies(source)
        if not has_message
    ]


class TestATokenInErrorAlwaysCarriesAMessage:
    """The guard that stops the ``rate_limited`` regression recurring.

    ``TestEvery429GoesThroughTheHelper`` above stops a fifth route hand-rolling
    a bare ``..., 429``. It does not stop the other half: a route emitting a
    machine token in ``error`` with no ``message`` beside it, at any status.
    ``frontend/src/utils/apiError.js`` reads ``message || error || fallback``,
    so such a body reaches the player as the token itself -- which is what
    ``FeedbackDialog`` did with the literal string ``rate_limited`` the day
    ``feedback.py`` adopted the shared 429 body.

    A scan rather than only a runtime check, because the failure is an
    *authoring* event: a hand-built body calls nothing ``rate_limiter.py``
    owns, and a rarely-taken error branch may never execute under test at all.
    The runtime half covers the other direction -- reaching the sanctioned
    helper with nothing to say.
    """

    def test_no_api_module_ships_a_token_without_prose(self):
        api_dir = _api_dir()
        offenders = {}
        for path in _all_api_modules():
            lines = token_errors_without_message(path.read_text(encoding="utf-8"))
            if lines:
                offenders[str(path.relative_to(api_dir)).replace("\\", "/")] = lines
        assert offenders == {}, (
            "a machine token in `error` is only legible to a person if "
            "`message` comes with it -- apiError.js reads `message || error` "
            f"and will show the player the token: {offenders}"
        )

    def test_the_scan_actually_sees_the_tokens_that_are_there(self):
        """Guard-the-guard, the half that matters most: the scan above passes
        trivially if the pattern matches nothing at all. The tree does contain
        token-shaped errors -- ``rate_limited`` and auth.py's
        ``validation_error``/``auth_error``/``server_error`` family -- so a
        typo'd pattern, broken constant resolution or a narrowed glob has to
        surface as this test failing rather than as a clean sweep.
        """
        api_dir = _api_dir()
        seen = {}
        for path in _all_api_modules():
            bodies = token_error_bodies(path.read_text(encoding="utf-8"))
            if bodies:
                name = str(path.relative_to(api_dir)).replace("\\", "/")
                seen[name] = {token for _line, token, _msg in bodies}

        assert "rate_limiter.py" in seen, (
            "the canonical body is built from a module-level constant; losing "
            "it means constant resolution broke, and every hand-built body "
            "spelled that way is now invisible to the scan"
        )
        assert RATE_LIMITED_ERROR in seen["rate_limiter.py"]
        assert {"validation_error", "auth_error", "server_error"} <= seen.get(
            "routes/auth.py", set()
        ), seen

    def test_the_scan_reaches_past_routes(self):
        """Scope half. A completeness guard aimed at the package with the
        fewest items reads as coverage without being any: ``middleware/``,
        ``handlers/`` and ``sockets.py`` build response bodies too."""
        api_dir = _api_dir()
        scanned = {
            str(p.relative_to(api_dir)).replace("\\", "/") for p in _all_api_modules()
        }
        for expected in (
            "rate_limiter.py",
            "middleware/auth.py",
            "handlers/error_handler.py",
            "sockets.py",
            "app.py",
            "routes/feedback.py",
        ):
            assert expected in scanned, f"{expected} escapes the token-error scan"

    @pytest.mark.parametrize(
        "snippet",
        [
            # the shape the regression actually took
            'return jsonify({"success": False, "error": "rate_limited"}), 429',
            # any status, not just 429 -- which is why the 429 scan above is
            # not already this guard
            'return jsonify({"success": False, "error": "quota_exceeded"}), 403',
            # a bare dict, no jsonify: combat_adapter returns these
            'def f():\n    return {"error": "not_ready"}',
            # via a module constant -- the spelling the canonical body uses
            '_TOKEN = "rate_limited"\n'
            'def f():\n    return {"success": False, "error": _TOKEN}',
            # via the constant imported from the module that owns it
            "from src.api.rate_limiter import RATE_LIMITED_ERROR\n"
            'def f():\n    return {"error": RATE_LIMITED_ERROR}',
            # one lowercase word: ambiguous between token and prose, and
            # ambiguous is not good enough to put in front of a player
            'def f():\n    return {"error": "unauthorized"}',
            # built by a helper and handed back for a caller to jsonify --
            # still a body, and the reason `return` is scanned as well as the
            # two response calls
            'def body():\n    return {"error": "not_ready"}\n'
            "def route():\n    return jsonify(body()), 503",
        ],
    )
    def test_it_fires_on_a_token_with_no_message(self, snippet):
        assert token_errors_without_message(snippet), snippet

    @pytest.mark.parametrize(
        "snippet",
        [
            # the sanctioned shape
            'x = {"success": False, "error": "rate_limited", "message": "Slow."}',
            # prose in `error` and no `message` -- what nearly every route emits
            'x = {"success": False, "error": "Not enough gold"}',
            'x = {"success": False, "error": "Invalid or expired session"}',
            # a token mentioned in prose, not emitted
            '"""Returns {"error": "rate_limited"} when throttled."""',
            'x = 1  # {"error": "rate_limited"}',
            # an f-string error is interpolated prose, not a stable token
            'x = {"error": f"{name}_error"}',
            # no error key at all
            'x = {"success": True, "message": "done"}',
            # the same key holding something that is not a token
            'x = {"error": handler}',
        ],
    )
    def test_it_stays_quiet_on_prose_and_on_the_sanctioned_shape(self, snippet):
        assert token_errors_without_message(snippet) == [], snippet

    def test_a_blank_message_is_the_runtime_half_s_job_not_the_scan_s(self):
        """The scan can only see that the key is *present*. A body built with
        ``message=""`` satisfies it and still shows the player the token,
        because apiError.js falls through an empty string. That case belongs to
        the runtime guard below -- named here so the seam between the two is
        not mistaken for a hole in either.
        """
        assert token_errors_without_message('x = {"error": "t", "message": ""}') == []


class TestTheSharedBodyRefusesToShipABlankMessage:
    """The runtime half. ``apiErrorMessage`` is ``message || error ||
    fallback``, so an empty ``message`` does not degrade to the caller's
    generic copy -- it falls through to the token. The one helper allowed to
    put a token in ``error`` therefore has to insist on prose to pair with it.
    """

    @pytest.mark.parametrize("blank", ["", "   ", "\n\t", None])
    def test_it_raises_rather_than_shipping_the_token_alone(self, blank):
        app = Flask(__name__)
        with app.test_request_context("/"):
            with pytest.raises(ValueError) as excinfo:
                rate_limited_response(blank)
        assert RATE_LIMITED_ERROR in str(excinfo.value)

    def test_the_real_call_sites_all_pass_prose(self):
        """The precondition is only safe to add because no caller relies on the
        blank case. Read from the source rather than by exercising the routes,
        so this needs no session, no limiter driven to its ceiling, and nothing
        that could reach the network."""
        calls = []
        for path in _all_api_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and _called_name(node) == "rate_limited_response"
                    and node.args
                ):
                    calls.append((path.name, node.args[0]))

        # A floor, not an exact count: a sixth throttled route is a good thing
        # and must not fail this test. The floor is what stops the loop below
        # passing vacuously if the scan stops finding call sites at all.
        assert len(calls) >= 4, calls
        for name, arg in calls:
            assert isinstance(arg, ast.Constant) and arg.value.strip(), name
