"""Every URL these tests request must exist in ``app.url_map``.

This is the guard against the failure mode that made a large part of this
directory report green while testing nothing. A test that requests a URL with
no route gets Flask's 404 -- whose JSON body carries ``success: false``, so
even a body assertion passes -- and an assertion written as
``status_code in [200, 404]`` (or ``[401, 404]``, ``[400, 404]``, ``>= 400``)
is satisfied by that 404. Fifty distinct URLs in ``test_routes_critical.py``
and ``test_routes_tier2.py`` had no route; the worst of them were the auth
tests, which got the same 404 for a missing header, an invalid session and a
malformed header alike and would have passed with authentication deleted.

The scan is static: it walks every ``tests/api/test_*.py`` for calls of the
form ``<anything>.get|post|put|delete|patch(<string literal>, ...)`` where the
literal starts with ``/``. An f-string is resolved by replacing each
interpolation with ``1`` -- enough for path converters like
``/api/saves/<save_id>`` -- so a URL whose *prefix* is interpolated cannot be
checked and should be written as a plain literal instead.

``ALLOWED_MISSING`` is the escape hatch, and every entry has to say why. Stale
entries are an error too: an allowance that no test uses any more, or one for
a URL that has since gained a route, fails this test so the list cannot rot
into the same silence it exists to prevent.
"""

import ast
from pathlib import Path

import pytest
from werkzeug.exceptions import MethodNotAllowed


TESTS_DIR = Path(__file__).resolve().parent

HTTP_METHODS = ("get", "post", "put", "delete", "patch", "head", "options")

#: Exact URLs that are *deliberately* requested despite having no route.
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
#: carries ``NO_QUEST_SYSTEM`` -- ``pytest.mark.xfail(strict=True)`` -- so the
#: day a quest blueprint lands, those tests fail as unexpected passes and
#: these prefixes go stale, which this test also reports.
ALLOWED_MISSING_PREFIXES = {
    "/api/quests/": (
        "No quest system exists in this tree: no quest blueprint is "
        "registered in src/api/routes/, GameService carries no quest method "
        "and src/ defines no Quest class. Every test requesting this prefix "
        "is marked NO_QUEST_SYSTEM (xfail strict=True)."
    ),
    "/api/quest-chains/": (
        "Same missing feature as /api/quests/ -- no quest-chain blueprint "
        "exists. Requesting tests are marked NO_QUEST_SYSTEM (xfail strict)."
    ),
    "/api/npc/quests/": (
        "Same missing feature as /api/quests/ -- no npc-quest blueprint "
        "exists. Requesting tests are marked NO_QUEST_SYSTEM (xfail strict)."
    ),
}


def _literal_url(node):
    """Return the URL a call argument names, or ``None`` if it is not one.

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


def _requested_urls():
    """Collect every ``/``-rooted URL literal handed to an HTTP verb call.

    Returns a dict of ``url -> sorted list of "file:line"`` sites.
    """
    found = {}
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in HTTP_METHODS:
                continue
            if not node.args:
                continue
            url = _literal_url(node.args[0])
            if url is None or not url.startswith("/"):
                continue
            found.setdefault(url, set()).add(f"{path.name}:{node.lineno}")
    return {url: sorted(sites) for url, sites in found.items()}


def _has_route(app, url):
    """True when *url*'s path matches a rule on the app, under any method."""
    adapter = app.url_map.bind("localhost")
    path = url.split("?", 1)[0]
    for method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        try:
            adapter.match(path, method=method, query_args="")
        except MethodNotAllowed:
            # The rule exists; this verb is simply not one it serves.
            return True
        except Exception:
            continue
        else:
            return True
    return False


def _allowed_prefix(url):
    """Return the allow-listed prefix covering *url*, or ``None``."""
    for prefix in ALLOWED_MISSING_PREFIXES:
        if url.startswith(prefix):
            return prefix
    return None


@pytest.fixture(scope="module")
def requested_urls():
    """The URL literals every test in this directory requests."""
    urls = _requested_urls()
    assert urls, "the AST scan found no request URLs at all -- it is broken"
    return urls


def test_every_requested_url_has_a_route(app, requested_urls):
    """No test may request a URL that the app does not route."""
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


def test_allowances_carry_a_reason():
    """An allowance without a stated reason is how this directory rotted."""
    for mapping, name in (
        (ALLOWED_MISSING, "ALLOWED_MISSING"),
        (ALLOWED_MISSING_PREFIXES, "ALLOWED_MISSING_PREFIXES"),
    ):
        for key, reason in mapping.items():
            assert isinstance(reason, str) and len(reason.split()) >= 8, (
                f"{name}[{key!r}] needs a reason that states the fact, not a "
                "placeholder"
            )
