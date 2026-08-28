"""Shared in-memory sliding-window rate limiter.

Used by ``src/api/routes/auth.py`` (login username+IP, login per-IP, and
registration per-IP throttles), ``src/api/routes/feedback.py`` (feedback
submission throttle) and ``src/api/routes/npc_chat.py`` (per-identity + per-IP
LLM chat throttles).

Everything a throttled route needs lives here, so no call site has to
re-derive it: the store itself (:class:`RateLimiter`), the rule for turning a
request into a client identity (:func:`client_ip`), the rule for reading a
limit out of the environment without taking the process down
(:func:`limiter_from_env`), the ``None``-tolerant way to spend a tier's budget
(:meth:`RateLimiter.check`), and the 429 body every throttled route returns
(:func:`rate_limited_response`).

**Known limitation (tracked in GitHub issue #284):** this store is
per-process. Under multiple Gunicorn workers, the *effective* limit for a
given key is ``limit * worker_count`` because each worker keeps its own
independent store. Moving to a shared store (e.g. Redis) is a larger
infrastructure decision than any of these call sites warrants today, and this
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

import ipaddress
import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Optional, Tuple

from flask import Response, jsonify, request

from src.env_bootstrap import load_project_env

logger = logging.getLogger(__name__)

# Every limiter in this API is built by :func:`limiter_from_env` at *blueprint
# import* time — ``auth.py``, ``feedback.py``, ``npc_chat.py`` all call it in
# their module bodies, long before ``create_app()`` runs. So ``.env`` has to be
# in ``os.environ`` by then, and until this line it was only by accident:
# ``auth.py`` imports ``auth_service``, which happens to pull in
# ``src/api/db.py``, which loads it. Reordering an unrelated import would have
# silently pinned every throttle to its default, with nothing logged.
#
# Loading it here — in the module that owns the read — makes the order
# irrelevant, because this body necessarily runs before any call to the
# function below. ``load_project_env`` is idempotent and defaults to
# ``override=False``, so it never overwrites a deliberately-set variable.
load_project_env()

# How many writes to allow between full sweeps of expired keys. Keeps the
# amortized cost of sweeping low while still reclaiming idle keys promptly.
_SWEEP_INTERVAL = 200

# Hard cap on distinct keys tracked at once. Chosen generously above expected
# legitimate traffic; it exists purely as a backstop against unbounded growth,
# not as a tuned production limit.
_DEFAULT_MAX_KEYS = 5000

# Prefix length an IPv6 address is collapsed to before it is used as a limiter
# key. A typical end-site allocation is a /64, so this throttles the whole
# allocation rather than a single address out of it.
_IPV6_KEY_PREFIX = 64

# The /64 collapse as an integer mask. Masking ``int(addr)`` rather than
# round-tripping through ``ip_network(f"{ip}/64")`` also tolerates a scoped
# address (``fe80::1%eth0``), which ``ip_network`` rejects outright.
_IPV6_KEY_MASK = ((1 << _IPV6_KEY_PREFIX) - 1) << (128 - _IPV6_KEY_PREFIX)


def _collapse_ip(ip: str) -> str:
    """Turn one address string into the limiter key that stands for it.

    The order of the branches below is load-bearing, and getting it wrong is
    an availability bug rather than a security one. ``::ffff:203.0.113.9``
    (an IPv4 client on a dual-stack ``[::]`` listener — the default on many
    PaaS hosts) and ``::1`` both have all-zero top 64 bits, so collapsing
    *before* unwrapping them mapped **every** such client onto the single key
    ``"::"``: ten failed logins from anywhere would lock one account out for
    everyone, and sixty would lock out the login endpoint entirely.

    So: IPv4 and IPv4-mapped IPv6 keep their full address, anything whose /64
    prefix is empty keeps its own identity, and only a genuine routable IPv6
    address is collapsed — which is the only case the collapse was ever aimed
    at, since /128s are cheap for an attacker to rotate within one allocation
    but IPv4 addresses are not.

    Unparseable values (including ``"unknown"``) are used verbatim: a coarse
    key beats raising on the request path.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip

    if addr.version == 4:
        return str(addr)

    mapped = addr.ipv4_mapped
    if mapped is not None:
        return str(mapped)

    # The general form of the bug described above: *any* address whose /64
    # prefix is all zeros collapses onto the single key ``"::"``, not just the
    # two shapes named by name. ``::1`` (one host, not an allocation), the
    # unspecified address ``::``, IPv4-compatible ``::a.b.c.d`` and
    # IPv4-translated ``::ffff:0:a.b.c.d`` all land here. None of them is an
    # allocation worth throttling as one, and lumping them together is the
    # same shared-bucket lockout, so they keep their own identity. Testing the
    # mask rather than a fixed shift keeps this true if _IPV6_KEY_PREFIX moves.
    prefix = int(addr) & _IPV6_KEY_MASK
    if prefix == 0:
        return str(addr)

    return str(ipaddress.IPv6Address(prefix))


def client_ip() -> str:
    """The client's IP, collapsed to a /64 prefix for routable IPv6.

    See :func:`_collapse_ip` for the exact rule. Returns ``"unknown"`` when
    called outside a request context (e.g. direct helper calls in tests).

    This is the single client-identity rule for every IP-keyed limiter in the
    API. It lives here rather than in a blueprint because two blueprints
    (``auth`` and ``npc_chat``) each grew their own copy, and a client-identity
    rule that disagrees between endpoints is a limiter one of them can be
    walked past.

    It reads ``request.remote_addr``, which is the direct client IP by default
    (no proxy/load balancer in this deployment) and automatically becomes the
    real client IP if the opt-in ProxyFix is ever configured (see
    ``src/api/app.py::_apply_proxy_fix`` / ``TRUSTED_PROXY_COUNT`` and
    ``tests/test_proxy_fix.py``).
    """
    try:
        ip = request.remote_addr or "unknown"
    except RuntimeError:  # working outside of request context
        return "unknown"
    return _collapse_ip(ip)


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

    @staticmethod
    def check(limiter: "Optional[RateLimiter]", key: str) -> bool:
        """:meth:`check_and_record` for a tier that may not exist.

        ``limiter_from_env`` returns ``None`` for the documented
        ``<VAR>=0`` disable, so every call site had to open with the same
        ``if _limiter is None: return False`` before it could spend a budget —
        four copies of it, and each one a place to get the polarity backwards
        and read a *disabled* tier as a *tripped* one. A ``None`` limiter never
        limits; that rule belongs to the module that invented ``None``.

        Deliberately a static method rather than an instance one: the whole
        point is to be callable when there is no instance. Call it on the
        class (``RateLimiter.check(limiter, key)``); calling it on an instance
        would pass the key as ``limiter`` and fail loudly on the missing second
        argument.

        Returns:
            True if ``key`` is over ``limiter``'s budget (and this call was
            *not* recorded), False otherwise (and this call was recorded).
        """
        if limiter is None:
            return False
        return limiter.check_and_record(key)

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


#: Machine-readable value of the 429 body's ``error`` field. A stable token,
#: not prose: ``auth.py``'s neighbouring failures (``validation_error``,
#: ``auth_error``, ``service_unavailable``) are tokens too, and a client that
#: wants to back off should not have to string-match an English sentence that
#: may be reworded.
RATE_LIMITED_ERROR = "rate_limited"


def rate_limited_response(message: str) -> Tuple[Response, int]:
    """The 429 a throttled route returns, in the API's one 429 shape.

    Four routes grew four 429 bodies in two incompatible shapes: ``auth.py``
    paired the ``rate_limited`` token with human prose in ``message``, while
    ``feedback.py`` and ``npc_chat.py`` put the prose straight into ``error``
    and shipped no ``message`` at all. A client could therefore neither
    branch on ``error`` nor read ``message`` without knowing which endpoint it
    had called — and this module's own docstring already promised no call site
    would have to re-derive any of this.

    The ``error`` + ``message`` pairing wins because it is the one the
    frontend reads: ``frontend/src/pages/LoginPage.jsx`` surfaces
    ``response.data.message`` and would show nothing at all for a body that
    omits it.

    Args:
        message: Player-facing prose. Endpoint-specific on purpose — "too many
            failed login attempts" and "slow down" are different advice — so it
            stays a parameter rather than being flattened into one house
            string.

    Returns:
        The ``(response, 429)`` tuple, ready to ``return`` from a view.
    """
    return (
        jsonify({"success": False, "error": RATE_LIMITED_ERROR, "message": message}),
        429,
    )


def limiter_from_env(
    var: str,
    default: int,
    window_seconds: float,
    allow_disable: bool = True,
) -> Optional[RateLimiter]:
    """Build a limiter whose threshold comes from env var ``var``, surviving a
    malformed value.

    Every limiter in this API is built at *blueprint import* time, so a bare
    ``int()`` here turned a typo in an env file
    (``NPC_CHAT_RATE_LIMIT_PER_MINUTE=twenty``) into a ValueError during import
    and took the whole API down at boot. Falling back to the default keeps the
    limiter *on*, which is the safe direction to fail: a garbled value must
    never be read as "unlimited".

    A *negative* value is garbled too, and used to parse cleanly and then fall
    through the ``> 0`` test at the call site into an unlimited, unlogged
    endpoint — the exact outcome the paragraph above promises cannot happen.
    Only an exact 0 is the documented disable.

    Every limiter goes through this function rather than hand-rolling the parse,
    because the guard is only worth anything if the *next* limiter added gets it
    too. The three that predated it did not.

    **Why ``allow_disable`` is not uniform.** The two login throttles pass
    ``allow_disable=False``; the register, npc-chat and feedback throttles do
    not. That asymmetry is a decision, not an oversight. Those three throttle
    *cost and spam* — LLM quota, GitHub issue noise, account farming — and
    turning one off in local development is legitimate and self-correcting. The
    login throttles are a brute-force defence on the *credential-guessing*
    path: a ``0`` typed there, or copied out of a dev ``.env`` into production,
    silently removes the only thing standing between an attacker and unlimited
    password guesses, and nothing in the running app would report the loss.
    That is the same failure the paragraphs above exist to prevent, one
    variable further along, so ``0`` on those vars is treated exactly like a
    garbled value: warn, and keep the default.

    Args:
        var: Name of the environment variable holding the limit, as an integer
            count of permitted requests per window. Unset or blank means
            "use ``default``".
        default: Limit applied when ``var`` is unset, blank, or unusable. Must
            be positive when ``allow_disable`` is False — see Raises.
        window_seconds: Width of the sliding window the limit applies over.
        allow_disable: Whether ``0`` may switch this throttle off. Pass ``False``
            for any limiter whose absence is a security hole rather than an
            inconvenience; ``0`` then warns and falls back to ``default``, and
            this function cannot return ``None``.

    Returns:
        A configured :class:`RateLimiter`, or ``None`` when ``var`` is exactly
        ``0`` *and* ``allow_disable`` is true — the one documented way to
        disable a throttle. Callers must treat ``None`` as "this tier never
        limits".

    Raises:
        ValueError: if ``allow_disable`` is False and ``default`` is not
            positive. That combination is a *source-code* mistake, not a
            deployment one — and it would quietly defeat the "cannot return
            ``None``" guarantee the callers of the login tiers rely on to
            dereference their limiters without a ``None`` check. Unlike a
            garbled env value there is nothing to fall back to and no operator
            to warn, so it fails at import, on every run, including the tests.
    """
    if not allow_disable and default <= 0:
        raise ValueError(
            "%s: a throttle built with allow_disable=False needs a positive "
            "default (got %r); 0 would disable the very limiter that is not "
            "permitted to be disabled." % (var, default)
        )

    limit = _parse_env_limit(var, default, window_seconds, allow_disable)
    if limit == 0:
        return None
    return RateLimiter(limit=limit, window_seconds=window_seconds)


def _parse_env_limit(
    var: str, default: int, window_seconds: float, allow_disable: bool
) -> int:
    """The limit ``var`` asks for, or ``default`` if it does not ask usably.

    Split out so the parse failure is handled where it happens: the previous
    shape reused ``limit`` as both the parsed integer and a ``None``
    parse-failure sentinel, which meant every later comparison had to keep
    remembering that ``limit`` might not be a number.
    """
    raw = os.environ.get(var, "")
    if not raw.strip():
        return default

    try:
        limit = int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "%s=%r is not a usable limit (%s); falling back to %d per "
            "%g seconds.",
            var,
            raw,
            (
                "expected 0 to disable, or a positive integer"
                if allow_disable
                else "expected a positive integer; this throttle cannot be "
                "disabled"
            ),
            default,
            window_seconds,
        )
        return default

    if limit < 0:
        logger.warning(
            "%s=%r is not a usable limit (a negative limit used to parse "
            "cleanly and then read as 'unlimited' at the call site); falling "
            "back to %d per %g seconds.",
            var,
            raw,
            default,
            window_seconds,
        )
        return default

    if limit == 0 and not allow_disable:
        logger.warning(
            "%s=0 would switch off a throttle that is not permitted to be "
            "disabled (it guards the credential path); falling back to %d "
            "per %g seconds.",
            var,
            default,
            window_seconds,
        )
        return default

    return limit
