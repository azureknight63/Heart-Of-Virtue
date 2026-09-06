"""Every URL these tests name must exist in ``app.url_map``.

This is the guard against the failure mode that made a large part of this
directory report green while testing nothing. A test that requests a URL with
no route gets Flask's 404 -- whose JSON body carries ``success: false``, so
even a body assertion passes -- and an assertion written as
``status_code in [200, 404]`` (or ``[401, 404]``, ``[400, 404]``, ``>= 400``)
is satisfied by that 404. Fifty distinct URLs in ``test_routes_critical.py``
and ``test_routes_tier2.py`` had no route; the worst of them were the auth
tests, which got the same 404 for a missing header, an invalid session and a
malformed header alike and would have passed with authentication deleted.

**Where this runs.** ``pytest.ini`` puts ``tests/api`` in ``norecursedirs``,
so a local ``python -m pytest -q`` never executes this file. It runs in the
dedicated ``tests/api`` CI job (``.github/workflows/api-tests.yml``) and for
anyone who names the directory explicitly:
``python -m pytest tests/api/ -q``.

The scan
--------

Static, over every ``tests/api/**/test_*.py`` (``rglob``, so a file added in a
subdirectory is covered) except this module itself -- scanning our own
allow-list keys would make the staleness checks vacuously pass. Two passes,
because the first one alone was already blind:

1. **Verb calls.** ``<anything>.get|post|put|delete|patch|head|options(<url>)``
   with the URL as the first positional argument. This pass also records the
   *verb*, which feeds :func:`test_requests_use_a_verb_the_rule_serves`.
2. **Every ``/api/`` string literal in the file**, whatever syntax surrounds
   it. Five files route their requests through local ``_post_json(client,
   url, ...)`` helpers and two drive lists of endpoints through a ``for``
   loop -- neither form is a verb call, so pass 1 saw none of their URLs, and
   the loop form is exactly what the "these endpoints must 401" auth tests
   use. Pass 2 reads those literals verbatim at their call sites.

An f-string is resolved by replacing each interpolation with ``1`` -- enough
for path converters like ``/api/saves/<save_id>`` -- so a URL whose *prefix*
is interpolated cannot be checked and should be written as a plain literal.
String constants sitting directly under a comparison (``'/api/auth' in
rule``) are skipped: those inspect the url_map, they do not request anything.

What pass 2 still cannot see is a URL that is never written down as a literal
in the file that requests it. :func:`test_dynamic_url_call_sites_stay_visible`
makes that blind spot loud rather than silent: it lists every verb call whose
URL argument the scan could not resolve and requires the file it lives in to
contribute literals of its own. :func:`test_per_file_url_floor` catches the
other direction -- a collapse in what the scan finds, which would otherwise
turn this whole module green by finding nothing.

The hatches
-----------

``ALLOWED_MISSING`` (exact URLs) and ``ALLOWED_MISSING_PREFIXES`` (whole
featureless families) are the escape hatches, and each entry states why.
They are themselves policed, because an unchecked hatch is how this directory
rotted in the first place:

* an allowance for a URL no test requests any more, or for one that has since
  gained a route, fails (:func:`test_no_stale_exact_allowances`,
  :func:`test_no_stale_prefix_allowances`);
* no exact allowance may name an ``/api/`` URL at all
  (:func:`test_exact_allowances_never_cover_an_api_url`) -- the exact-URL
  hatch would otherwise satisfy *both* staleness checks while hiding the very
  defect this module exists to catch, since a routeless API URL is still
  requested and still routeless;
* a prefix-allowed URL may only be requested from a test carrying a strict
  ``xfail`` (:func:`test_prefix_allowed_urls_are_requested_under_strict_xfail`)
  -- the prefix comment always claimed this and nothing enforced it, so a new
  unmarked ``client.get("/api/quests/foo")`` asserting ``in [200, 404]``
  would have passed forever inside the allow-listed hole.
"""

import ast
from pathlib import Path

import pytest
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing.exceptions import RequestRedirect

from ._marks import NO_QUEST_SYSTEM, NO_QUEST_SYSTEM_REASON


TESTS_DIR = Path(__file__).resolve().parent
SELF = Path(__file__).name

#: Verb names whose first positional argument is treated as a URL.
HTTP_METHODS = ("get", "post", "put", "delete", "patch", "head", "options")

#: Methods :func:`_has_route` probes a path with. ``HEAD`` and ``OPTIONS`` are
#: deliberately absent: Werkzeug synthesises ``HEAD`` for every ``GET`` rule
#: and ``OPTIONS`` for every rule, so including them would make the probe
#: answer "route exists" for strictly the same set while hiding which verb the
#: application actually declared -- and would break
#: :func:`test_requests_use_a_verb_the_rule_serves`, which needs a genuine
#: ``MethodNotAllowed`` to mean something.
ROUTABLE_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH")

#: Only literals under this prefix are collected by the second, syntax-blind
#: pass. A bare ``/`` prefix would sweep up every filesystem path, log name
#: and JSON pointer in the directory.
API_PREFIX = "/api/"

#: A placeholder floor, not a quality check: it rejects ``"TODO"`` and ``"n/a"``
#: and nothing more. Nothing here can tell a true reason from a plausible
#: sentence -- the structural bars above are what actually constrain the
#: hatches.
MIN_REASON_WORDS = 8

#: Decorator names that this module accepts as "the test is strictly xfailed".
#: Grounded by :func:`test_the_shared_marker_is_a_strict_xfail`, which asserts
#: the imported object really is ``xfail(strict=True)``; an inline
#: ``pytest.mark.xfail(..., strict=True)`` is recognised directly.
STRICT_XFAIL_MARK_NAMES = ("NO_QUEST_SYSTEM",)

#: Exact URLs that are *deliberately* requested despite having no route.
#: None of these may be an API URL -- see
#: :func:`test_exact_allowances_never_cover_an_api_url`.
ALLOWED_MISSING = {
    "/nonexistent": (
        "test_app.py probes the 404 handler itself; the URL is required to "
        "have no route for the test to mean anything."
    ),
    "/test_404": (
        "test_error_handlers.py registers this route on a throwaway app built "
        "inside the test, so it is absent from the production app map."
    ),
    "/test_500": (
        "test_error_handlers.py registers this route on a throwaway app built "
        "inside the test, so it is absent from the production app map."
    ),
    "/test_500_detail": (
        "test_error_handlers.py registers this route on a throwaway app built "
        "inside the test, so it is absent from the production app map."
    ),
    "/test_exception": (
        "test_error_handlers.py registers this route on a throwaway app built "
        "inside the test, so it is absent from the production app map."
    ),
}

#: Whole URL families with no backing feature. Every test that requests one
#: must carry a strict ``xfail`` -- enforced, not merely asserted in prose, by
#: :func:`test_prefix_allowed_urls_are_requested_under_strict_xfail`.
ALLOWED_MISSING_PREFIXES = {
    "/api/quests/": NO_QUEST_SYSTEM_REASON,
    "/api/quest-chains/": NO_QUEST_SYSTEM_REASON,
    "/api/npc/quests/": NO_QUEST_SYSTEM_REASON,
}

#: ``(url, VERB)`` pairs deliberately sent to a rule that does not serve that
#: verb. A 405 is raised by Werkzeug at *routing* time -- Flask stores it as
#: ``routing_exception`` and re-raises it in ``dispatch_request`` -- so no view
#: body runs and ``get_session_and_player()`` is never reached. An auth test
#: pointed at a real path with the wrong verb therefore answers an identical
#: 405 for a missing header, an invalid session and a malformed one: the exact
#: shape of the 404 defect, one status code over.
ALLOWED_METHOD_MISMATCH = {
    ("/api/saves/load", "POST"): (
        "test_delete_rule_rejects_a_post_to_saves_load pins this 405 on "
        "purpose: /api/saves/load matches /api/saves/<save_id>, which serves "
        "DELETE only, and the test exists to prove a POST is refused while "
        "routing rather than reaching the loader."
    ),
}

#: Lower bounds on the distinct ``/api/`` URLs the scan must still find per
#: file. These are floors, not counts: they sit well under today's numbers so
#: ordinary edits do not trip them, and exist so that a scanner regression --
#: or a file gutted into vacuity -- fails here instead of quietly making every
#: other assertion in this module pass against an empty set.
MIN_URLS_PER_FILE = {
    "test_routes_tier2.py": 45,
    "test_routes_critical.py": 20,
    "test_routes_integration.py": 14,
    "test_inventory_routes.py": 9,
    "test_routes_saves_comprehensive.py": 8,
    "test_routes_tier1.py": 6,
    "test_api_fuzz.py": 5,
}

#: Lower bound on the distinct URLs found across the whole directory.
MIN_URLS_TOTAL = 90


def _literal_url(node):
    """Return the URL a node names, or ``None`` if it is not one.

    Handles plain strings, f-strings (interpolations become ``1``) and
    ``"..." + something`` concatenation.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("1")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_url(node.left)
        if left is None:
            return None
        right = _literal_url(node.right)
        return left + (right if right is not None else "1")
    return None


def _is_strict_xfail(decorator):
    """True when *decorator* is a strict ``xfail`` marker."""
    if isinstance(decorator, ast.Name):
        return decorator.id in STRICT_XFAIL_MARK_NAMES
    if isinstance(decorator, ast.Call):
        if not ast.unparse(decorator.func).endswith("mark.xfail"):
            return False
        for keyword in decorator.keywords:
            if keyword.arg == "strict" and isinstance(keyword.value, ast.Constant):
                return keyword.value.value is True
    return False


class _Scan:
    """What the static scan found, across the whole directory."""

    def __init__(self):
        #: url -> {"file.py:lineno", ...}
        self.sites = {}
        #: url -> {"file.py:lineno", ...} for sites NOT under a strict xfail
        self.unmarked_sites = {}
        #: (url, VERB) -> {"file.py:lineno", ...}
        self.verb_calls = {}
        #: {"file.py:lineno": "receiver source"} for unresolvable URL args
        self.dynamic_calls = {}
        #: file name -> {url, ...}
        self.per_file = {}

    def record(self, filename, lineno, url, strict):
        site = f"{filename}:{lineno}"
        self.sites.setdefault(url, set()).add(site)
        if not strict:
            self.unmarked_sites.setdefault(url, set()).add(site)
        if url.startswith(API_PREFIX):
            self.per_file.setdefault(filename, set()).add(url)


def _comparison_operand_ids(tree):
    """Node ids of literals sitting directly under a comparison.

    ``assert any('/api/auth' in rule for rule in rules)`` inspects the url_map;
    it does not request ``/api/auth`` (which has no rule of its own, only
    children). Collecting such literals would mean either a false failure or
    an ``ALLOWED_MISSING`` entry for an API URL, which is barred.
    """
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for operand in [node.left] + list(node.comparators):
                skip.add(id(operand))
    return skip


def _walk(node, filename, strict, skip, scan):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        strict = strict or any(_is_strict_xfail(d) for d in node.decorator_list)

    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in HTTP_METHODS
        and node.args
    ):
        url = _literal_url(node.args[0])
        receiver = ast.unparse(node.func.value)
        if url is None:
            # Only a test client's verb call is a blind spot worth reporting;
            # `self.tiles.get((x, y))` is a dict lookup, not a request.
            if "client" in receiver.lower():
                scan.dynamic_calls[f"{filename}:{node.lineno}"] = receiver
        elif url.startswith("/"):
            verb = node.func.attr.upper()
            scan.verb_calls.setdefault((url, verb), set()).add(
                f"{filename}:{node.lineno}"
            )
            scan.record(filename, node.lineno, url, strict)

    if id(node) not in skip:
        if isinstance(node, (ast.JoinedStr, ast.BinOp)):
            url = _literal_url(node)
            if url is not None and url.startswith(API_PREFIX):
                scan.record(filename, node.lineno, url, strict)
                return  # its pieces are fragments, not URLs of their own
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, str) and node.value.startswith(API_PREFIX):
                scan.record(filename, node.lineno, url=node.value, strict=strict)

    for child in ast.iter_child_nodes(node):
        _walk(child, filename, strict, skip, scan)


def _scan_directory():
    """Scan every ``tests/api/**/test_*.py`` but this module."""
    scan = _Scan()
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        if path.name == SELF:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        _walk(tree, path.name, False, _comparison_operand_ids(tree), scan)
    return scan


def _has_route(app, url):
    """True when *url*'s path matches a rule on the app, under any method."""
    adapter = app.url_map.bind("localhost")
    path = url.split("?", 1)[0]
    for method in ROUTABLE_METHODS:
        try:
            adapter.match(path, method=method, query_args="")
        except MethodNotAllowed:
            # The rule exists; this verb is simply not one it serves.
            return True
        except RequestRedirect:
            # Differs from a real rule only by a trailing slash. The route
            # exists -- a bare `except Exception: continue` used to swallow
            # this and report it as routeless.
            return True
        except NotFound:
            continue
        # Anything else is a bug in this guard or in the map; let it propagate.
        else:
            return True
    return False


def _method_matches(app, url, verb):
    """True unless *verb* is routed to a rule that does not serve it."""
    adapter = app.url_map.bind("localhost")
    path = url.split("?", 1)[0]
    try:
        adapter.match(path, method=verb, query_args="")
    except MethodNotAllowed:
        return False
    except (NotFound, RequestRedirect):
        # Absent routes are test_every_requested_url_has_a_route's business;
        # a redirect still dispatches to the rule.
        return True
    return True


def _allowed_prefix(url):
    """Return the allow-listed prefix covering *url*, or ``None``."""
    for prefix in ALLOWED_MISSING_PREFIXES:
        if url.startswith(prefix):
            return prefix
    return None


@pytest.fixture(scope="module")
def scan():
    """The static scan of every test module in this directory."""
    result = _scan_directory()
    assert result.sites, "the AST scan found no URLs at all -- it is broken"
    return result


@pytest.fixture(scope="module")
def requested_urls(scan):
    """``url -> sorted ["file:line", ...]`` for every URL the scan found."""
    return {url: sorted(sites) for url, sites in scan.sites.items()}


def test_every_requested_url_has_a_route(app, requested_urls):
    """No test may name a URL that the app does not route."""
    offenders = []
    for url, sites in sorted(requested_urls.items()):
        if url in ALLOWED_MISSING or _allowed_prefix(url):
            continue
        if not _has_route(app, url):
            offenders.append(f"  {url}\n      requested at: {', '.join(sites)}")

    assert not offenders, (
        "These URLs have no rule in app.url_map, so every request to them "
        "returns 404 and any assertion that accepts 404 passes against "
        "nothing:\n"
        + "\n".join(offenders)
        + "\n\nRepoint each to the route that really serves it (see "
        "src/api/routes/ or GET /api/debug/routes), or -- only if the feature "
        "genuinely does not exist -- mark the test "
        "pytest.mark.xfail(reason=..., strict=True) and add the URL to "
        "ALLOWED_MISSING / ALLOWED_MISSING_PREFIXES in "
        "tests/api/test_route_prefix_contract.py with a reason."
    )


def test_requests_use_a_verb_the_rule_serves(app, scan):
    """A request whose verb the rule refuses never reaches the view.

    Werkzeug raises ``MethodNotAllowed`` while matching, so Flask stores it as
    ``routing_exception`` and re-raises it from ``dispatch_request``: no view
    body runs, no ``get_session_and_player()`` is reached, and the 405 is
    identical for every credential. That is the 404 defect wearing a different
    number, and it is invisible to the has-a-route check above because the
    path resolves.
    """
    offenders = []
    for (url, verb), sites in sorted(scan.verb_calls.items()):
        if (url, verb) in ALLOWED_METHOD_MISMATCH:
            continue
        if url in ALLOWED_MISSING or _allowed_prefix(url):
            continue
        if not _has_route(app, url):
            continue  # reported by test_every_requested_url_has_a_route
        if not _method_matches(app, url, verb):
            offenders.append(
                f"  {verb} {url}\n      requested at: {', '.join(sorted(sites))}"
            )

    assert not offenders, (
        "These requests use a verb the matching rule does not serve, so "
        "Werkzeug answers 405 at routing time and the view never runs -- an "
        "auth assertion against one of them passes with authentication "
        "deleted:\n"
        + "\n".join(offenders)
        + "\n\nUse the verb the route declares, or -- if the 405 itself is "
        "the thing under test -- add the (url, VERB) pair to "
        "ALLOWED_METHOD_MISMATCH with a reason."
    )


def test_no_stale_exact_allowances(app, requested_urls):
    """Each allow-listed URL must still be requested and still be routeless."""
    unused = [url for url in ALLOWED_MISSING if url not in requested_urls]
    assert not unused, (
        "ALLOWED_MISSING names URLs no test requests any more; delete them: "
        + ", ".join(sorted(unused))
    )

    now_routed = [url for url in ALLOWED_MISSING if _has_route(app, url)]
    assert not now_routed, (
        "ALLOWED_MISSING names URLs that now have routes, so the allowance is "
        "hiding a real test: " + ", ".join(sorted(now_routed))
    )


def test_exact_allowances_never_cover_an_api_url():
    """The exact-URL hatch may not be used on an API surface.

    Both staleness checks are satisfied by exactly the defect this module
    exists to catch: a routeless ``/api/...`` URL *is* still requested and *is*
    still routeless, so allow-listing one silences the failure permanently and
    ``test_allowances_carry_a_reason`` only counts words. A genuinely missing
    API feature belongs in ALLOWED_MISSING_PREFIXES, where every requesting
    test must additionally carry a strict xfail.
    """
    api_entries = sorted(url for url in ALLOWED_MISSING if url.startswith(API_PREFIX))
    assert not api_entries, (
        "ALLOWED_MISSING must never name an API URL -- that hatch cannot tell "
        "a deliberate probe from the bug it is meant to report: "
        + ", ".join(api_entries)
        + ". If the feature really does not exist, mark the tests "
        "xfail(strict=True) and use ALLOWED_MISSING_PREFIXES instead."
    )


def test_no_stale_prefix_allowances(app, requested_urls):
    """Each allow-listed prefix must still cover at least one routeless URL."""
    for prefix in sorted(ALLOWED_MISSING_PREFIXES):
        covered = [url for url in requested_urls if url.startswith(prefix)]
        assert covered, (
            f"ALLOWED_MISSING_PREFIXES entry {prefix!r} covers no requested "
            "URL any more; delete it."
        )
        routed = [url for url in covered if _has_route(app, url)]
        assert not routed, (
            f"{prefix!r} is allow-listed as having no backing feature, but "
            "these now route: " + ", ".join(sorted(routed)) + ". The feature "
            "has landed: drop the prefix here and the NO_QUEST_SYSTEM marker "
            "from the tests that use it."
        )


def test_prefix_allowed_urls_are_requested_under_strict_xfail(scan):
    """Inside the allow-listed hole, only strictly-xfailed tests may request.

    Without this, a new ``client.get("/api/quests/foo")`` asserting
    ``status_code in [200, 404]`` and carrying no marker at all passes
    forever: ``_allowed_prefix`` exempts the URL before the route check runs.
    The prefix comment has always claimed the marker is present; this makes
    the claim true.
    """
    offenders = []
    for url, sites in sorted(scan.unmarked_sites.items()):
        if not _allowed_prefix(url):
            continue
        offenders.append(f"  {url}\n      named at: {', '.join(sorted(sites))}")

    assert not offenders, (
        "These URLs are covered by ALLOWED_MISSING_PREFIXES -- i.e. they are "
        "known to have no route -- but are named outside any strict xfail, so "
        "the 404 they get satisfies whatever the test asserts:\n"
        + "\n".join(offenders)
        + "\n\nApply NO_QUEST_SYSTEM (tests/api/_marks.py) or an inline "
        "pytest.mark.xfail(..., strict=True) to the test or its class."
    )


def test_dynamic_url_call_sites_stay_visible(scan):
    """A URL the scan cannot resolve must not make its file invisible.

    Five files send every request through a local ``_post_json(client, url,
    ...)`` helper and two drive a list of endpoints through a ``for`` loop, so
    the verb-call pass resolves nothing at those call sites. The literal pass
    reads their URLs at the call sites instead -- this test proves it did,
    rather than leaving a file silently unscanned.
    """
    blind = sorted(
        f"  {site}  ({receiver}.<verb>(...))"
        for site, receiver in scan.dynamic_calls.items()
        if not scan.per_file.get(site.split(":", 1)[0])
    )
    assert not blind, (
        f"{len(scan.dynamic_calls)} test-client calls pass a URL the scan "
        "cannot resolve, and these live in files from which no /api/ literal "
        "was collected at all -- so nothing in them is checked:\n"
        + "\n".join(blind)
        + "\n\nWrite the URL as a literal at the call site."
    )


def test_per_file_url_floor(scan):
    """A collapse in what the scan finds must fail, not pass quietly."""
    shortfalls = [
        f"  {filename}: found {len(scan.per_file.get(filename, ()))}, "
        f"floor is {floor}"
        for filename, floor in sorted(MIN_URLS_PER_FILE.items())
        if len(scan.per_file.get(filename, ())) < floor
    ]
    assert not shortfalls, (
        "The scan found fewer URLs than these files are known to contain. "
        "Either the scanner regressed -- in which case every other assertion "
        "in this module is now passing against a shrunken set -- or the file "
        "genuinely shrank and the floor in MIN_URLS_PER_FILE should move "
        "with it:\n" + "\n".join(shortfalls)
    )

    total = len(scan.sites)
    assert total >= MIN_URLS_TOTAL, (
        f"The scan found {total} distinct URLs across tests/api, below the "
        f"{MIN_URLS_TOTAL} floor. Fix the scanner or lower the floor "
        "deliberately."
    )


def test_the_shared_marker_is_a_strict_xfail():
    """``STRICT_XFAIL_MARK_NAMES`` is only sound while this holds.

    The static check accepts the bare name ``NO_QUEST_SYSTEM`` as proof a test
    is strictly xfailed. That is a claim about an object it never evaluates,
    so evaluate it here.
    """
    assert NO_QUEST_SYSTEM.mark.name == "xfail"
    assert NO_QUEST_SYSTEM.mark.kwargs.get("strict") is True
    assert NO_QUEST_SYSTEM.mark.kwargs.get("reason") == NO_QUEST_SYSTEM_REASON


def test_allowances_carry_a_reason():
    """An allowance without a stated reason is how this directory rotted."""
    for mapping, name in (
        (ALLOWED_MISSING, "ALLOWED_MISSING"),
        (ALLOWED_MISSING_PREFIXES, "ALLOWED_MISSING_PREFIXES"),
        (ALLOWED_METHOD_MISMATCH, "ALLOWED_METHOD_MISMATCH"),
    ):
        for key, reason in mapping.items():
            assert (
                isinstance(reason, str)
                and len(reason.split()) >= MIN_REASON_WORDS
            ), (
                f"{name}[{key!r}] needs a reason that states the fact, not a "
                "placeholder"
            )
