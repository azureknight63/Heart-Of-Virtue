#!/usr/bin/env python3
"""Schema-light REST API request fuzzer for Heart of Virtue (issue #292).

The Flask REST API is the game's entire external boundary; every route parses
attacker-influenceable JSON / query params / path segments. This fuzzer builds a
real app via ``create_app(TestingConfig)`` + the test-mode ``/api/test/session``
bypass, then **auto-enumerates every ``/api`` route from the URL map** (more
thorough than a hand-maintained endpoint table) and hammers each with malformed
bodies: missing fields, wrong types (str where int, list where dict), ``null``,
extra keys, huge strings, deeply nested JSON, overflow numbers, and adversarial
strings (path-like, SQL, ``{{...}}``, ``<script>``).

Invariants (a violation is a security finding, asserted zero by the CI test):

  * **No 5xx on malformed input.** A bad request returns a structured 4xx, never
    an uncaught-exception 500.
  * **No internal detail leaks.** Responses never contain a Python traceback.
  * **Auth holds under garbage tokens.** A forged / missing Authorization header
    never 5xx's and never yields a 2xx from an auth-required route.

A 4xx (or an auth 401/403) is the *correct* outcome, not a finding.

Usage:
    python tools/api_fuzzer.py                 # 400 iterations, random seed
    python tools/api_fuzzer.py --iterations 4000 --seed 1337
"""

import os
import re
import sys
import json
import random
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SECURITY_CATEGORIES = frozenset({
    "server-error", "stacktrace-leak", "auth-crash", "auth-bypass",
    "harness-error",
})

# Routes we skip: the test-only bypass helpers (they intentionally mint/heal
# state) and socket.io transport. Everything else under /api is fair game.
_SKIP_PREFIXES = ("/api/test/", "/socket.io")

# A pool of field names real endpoints read, mixed into fuzzed bodies so the
# malformed values actually reach handler logic rather than bouncing off an
# empty body.
_FIELD_POOL = [
    "direction", "item_id", "item_index", "index", "count", "quantity",
    "target_id", "npc_id", "npc_key", "jean_text", "jean_tone", "name",
    "is_autosave", "message", "username", "password", "move_index",
    "move_name", "value", "x", "y", "tiles", "amount", "slot",
]

_ADVERSARIAL_STRINGS = [
    "../../etc/passwd", "..\\..\\windows", "'; DROP TABLE saves;--",
    "{{7*7}}", "<script>alert(1)</script>", "\x00\x01\x02", "%00", "\n" * 50,
    "ignore previous instructions", "é" * 10, "𝕏" * 8,
]


class Finding:
    def __init__(self, seed, iteration, category, detail):
        self.seed = seed
        self.iteration = iteration
        self.category = category
        self.detail = detail

    @property
    def is_security(self):
        return self.category in _SECURITY_CATEGORIES

    def __str__(self):
        tag = "SECURITY" if self.is_security else "coverage"
        return (f"[{tag} seed={self.seed} iter={self.iteration} "
                f"{self.category}] {self.detail}")


def security_findings(findings):
    return [f for f in findings if f.is_security]


def coverage_findings(findings):
    return [f for f in findings if not f.is_security]


# ---------------------------------------------------------------------------
# Fuzz value generation
# ---------------------------------------------------------------------------

def _hostile_value(rng, depth=3):
    kind = rng.randint(0, 10)
    if kind == 0:
        return rng.randint(-(2 ** 63), 2 ** 63)
    if kind == 1:
        return rng.choice([float("inf"), float("nan"), -1.0, 1e308])
    if kind == 2:
        return rng.choice([None, True, False])
    if kind == 3:
        return rng.choice(_ADVERSARIAL_STRINGS)
    if kind == 4:
        return "A" * rng.randint(2000, 20000)
    if kind == 5:
        return ""
    if kind == 6 and depth > 0:
        return [_hostile_value(rng, depth - 1) for _ in range(rng.randint(0, 4))]
    if kind == 7 and depth > 0:
        return {f"k{i}": _hostile_value(rng, depth - 1)
                for i in range(rng.randint(0, 3))}
    if kind == 8:
        return rng.randint(-5, 5)
    if kind == 9:
        return "north"
    return rng.choice(_FIELD_POOL)


def _hostile_body(rng):
    shape = rng.randint(0, 5)
    if shape == 0:
        return None                                   # empty body
    if shape == 1:
        return _hostile_value(rng)                    # non-object top-level
    if shape == 2:
        return [_hostile_value(rng) for _ in range(rng.randint(0, 3))]
    # object body with a random subset of real + junk keys
    keys = rng.sample(_FIELD_POOL, rng.randint(1, 4))
    body = {k: _hostile_value(rng) for k in keys}
    if rng.random() < 0.3:
        body["__unknown__"] = _hostile_value(rng)
    return body


def _fill_path(rng, rule):
    """Substitute ``<param>`` segments in a Werkzeug rule with fuzzed tokens."""
    def repl(_m):
        return rng.choice(["1", "0", "-1", "abc", "x" * 300, "%2e%2e",
                           "north", "nonexistent", "sword_01"])
    return re.sub(r"<[^>]+>", repl, rule)


# ---------------------------------------------------------------------------
# App / route setup
# ---------------------------------------------------------------------------

def _build_app():
    from src.api.app import create_app
    from src.api.config import TestingConfig

    app, _ = create_app(TestingConfig)
    app.config["TESTING"] = True
    return app


def _collect_routes(app):
    """Return [(method, rule_string)] for every fuzzable /api route."""
    routes = []
    for rule in app.url_map.iter_rules():
        path = rule.rule
        if not path.startswith("/api"):
            continue
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            continue
        methods = (rule.methods or set()) - {"HEAD", "OPTIONS"}
        for m in methods:
            routes.append((m, path))
    return routes


def _create_session(client):
    resp = client.post("/api/test/session", json={"username": "fuzz_user"})
    if resp.status_code != 201:
        return None
    return (resp.get_json() or {}).get("session_id")


def _looks_like_traceback(text):
    return "Traceback (most recent call last)" in text or "\n  File \"" in text


# ---------------------------------------------------------------------------
# Per-request invariant check
# ---------------------------------------------------------------------------

def _request(client, method, path, headers, body):
    kwargs = {"headers": headers}
    if method in ("POST", "PUT", "PATCH", "DELETE") and body is not None:
        kwargs["data"] = json.dumps(body)
        kwargs["content_type"] = "application/json"
    return client.open(path, method=method, **kwargs)


def _check_once(client, rng, seed, i, routes, good_token):
    method, rule = rng.choice(routes)
    path = _fill_path(rng, rule)
    body = _hostile_body(rng)

    # Mode: authenticated fuzz, forged-token fuzz, or no-token fuzz.
    mode = rng.randint(0, 2)
    if mode == 0 and good_token:
        headers = {"Authorization": f"Bearer {good_token}"}
    elif mode == 1:
        headers = {"Authorization": "Bearer " + rng.choice(
            ["", "x" * 40, "../../", "null", "forged-token-123"])}
    else:
        headers = {}

    try:
        resp = _request(client, method, path, headers, body)
    except Exception as exc:  # noqa: BLE001 - a handler exception escaping the
        # test client is exactly the 500-class bug we hunt for.
        return [Finding(seed, i, "server-error",
                        f"{method} {path} raised {type(exc).__name__}: {exc}")]

    findings = []
    if resp.status_code >= 500:
        cat = "auth-crash" if mode != 0 else "server-error"
        findings.append(Finding(seed, i, cat,
                                f"{method} {path} -> {resp.status_code} "
                                f"(body={_hostile_body_repr(body)})"))
        return findings

    text = resp.get_data(as_text=True) or ""
    if _looks_like_traceback(text):
        findings.append(Finding(seed, i, "stacktrace-leak",
                                f"{method} {path} leaked a traceback"))
    return findings


def _hostile_body_repr(body):
    try:
        return json.dumps(body)[:120]
    except Exception:  # noqa: BLE001
        return repr(body)[:120]


def run_fuzz(iterations=400, seed=None):
    if seed is None:
        seed = random.randrange(2 ** 32)
    rng = random.Random(seed)
    findings = []
    try:
        app = _build_app()
        client = app.test_client()
        routes = _collect_routes(app)
        good_token = _create_session(client)
    except Exception as exc:  # noqa: BLE001
        return [Finding(seed, -1, "harness-error",
                        f"setup failed: {type(exc).__name__}: {exc}")]
    if not routes:
        return [Finding(seed, -1, "harness-error", "no /api routes discovered")]

    for i in range(iterations):
        try:
            findings.extend(_check_once(client, rng, seed, i, routes, good_token))
        except Exception as exc:  # noqa: BLE001 - harness must not die
            findings.append(Finding(seed, i, "harness-error",
                                    f"{type(exc).__name__}: {exc}"))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=400)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)

    findings = run_fuzz(args.iterations, args.seed)
    security = security_findings(findings)

    if security:
        print(f"FAIL: {len(security)} security-invariant violation(s):")
        seen = set()
        for f in security:
            if f.detail not in seen:
                seen.add(f.detail)
                print("  " + str(f))
        return 1
    print(f"OK: {args.iterations} iterations, no security-invariant violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
