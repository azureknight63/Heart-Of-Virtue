"""Security response headers set by ``create_app()``'s ``after_request`` hook.

Three things are pinned here, in rising order of how easy they are to break by
accident:

1. The headers are actually on real responses. Before this suite the app set
   none at all -- no CSP, no ``X-Frame-Options``, no ``nosniff``, no
   ``Referrer-Policy`` -- and nothing would have noticed.
2. The strict :data:`~src.api.app._API_CSP` reaches exactly the responses it is
   safe on (everything that does not render) and the permissive
   :data:`~src.api.app._HTML_CSP` reaches exactly the ones that do. Getting that
   branch backwards is silent in both directions: a strict policy on HTML is a
   blank page, a permissive policy on the API is the hole the strict one exists
   to close.
3. The hook does not fight the CORS layer. ``handle_preflight`` and flask_cors
   negotiate ``Access-Control-*`` on the same responses, and an ``after_request``
   that reassigned rather than defaulted would have been an intermittent
   cross-origin failure rather than an obvious one.
"""

import pathlib
import re
from unittest.mock import MagicMock, patch

import pytest

from src.api.app import _API_CSP, _HTML_CSP, _STATIC_SECURITY_HEADERS


class _FastTestConfig:
    """Bare-minimum config; the universe build is patched out below."""

    TESTING = True
    DEBUG = False
    SECRET_KEY = "test-secret"
    CORS_ORIGINS = ["http://localhost:3000"]


@pytest.fixture(scope="module")
def app():
    """A real ``create_app()`` product, with the slow universe build stubbed.

    Deliberately the real factory rather than a bare ``Flask()`` with the hook
    attached by hand: the thing under test is that ``create_app`` *wires* the
    hook, and a hand-attached one would pass this file forever after someone
    deleted the call.
    """
    session_manager = MagicMock()
    session_manager.get_active_session_count.return_value = 0
    with (
        patch("src.api.app.universe_module"),
        patch("src.api.app.SessionManager", return_value=session_manager),
        patch("src.api.app.GameService", return_value=MagicMock()),
    ):
        from src.api.app import create_app

        built, _socketio = create_app(_FastTestConfig)

    # A stand-in for the SPA document this app does not serve today, so the
    # HTML branch of the policy is exercised rather than merely asserted about.
    @built.route("/__html_probe")
    def _html_probe():
        return "<!doctype html><html><body>probe</body></html>"

    @built.route("/__opinionated")
    def _opinionated():
        from flask import make_response

        response = make_response("{}")
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    return built


class TestHeadersArePresent:
    """The regression this whole file exists for: the app used to set none."""

    @pytest.mark.parametrize(
        "path, expected_status",
        [
            ("/health", 200),
            ("/api/info", 200),
            ("/api/status", 401),  # unauthenticated -> the auth middleware
            ("/definitely-not-a-route", 404),  # -> the JSON error handler
        ],
    )
    def test_every_response_carries_the_static_headers(
        self, app, path, expected_status
    ):
        """Including the error paths -- a 404/401 body is a response an
        attacker can reach without credentials, so it is the *first* thing that
        needs the headers, not an afterthought."""
        response = app.test_client().get(path)
        assert response.status_code == expected_status
        for header, value in _STATIC_SECURITY_HEADERS.items():
            assert response.headers.get(header) == value, header

    def test_the_static_set_is_the_three_agreed_headers(self):
        """Pinned by value: each was a deliberate choice documented in app.py,
        and ``Referrer-Policy`` in particular had a defensible alternative."""
        assert _STATIC_SECURITY_HEADERS == {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }


class TestThePolicyMatchesWhatTheResponseIs:
    """JSON never renders; HTML does. The two get different policies."""

    @pytest.mark.parametrize(
        "path", ["/health", "/api/info", "/definitely-not-a-route"]
    )
    def test_json_responses_get_the_strict_policy(self, app, path):
        response = app.test_client().get(path)
        assert response.mimetype == "application/json"
        assert response.headers["Content-Security-Policy"] == _API_CSP

    def test_html_responses_get_the_permissive_policy(self, app):
        response = app.test_client().get("/__html_probe")
        assert response.mimetype == "text/html"
        assert response.headers["Content-Security-Policy"] == _HTML_CSP

    def test_an_empty_html_response_is_still_treated_as_non_rendering(self, app):
        """``handle_preflight`` answers OPTIONS with a bare ``make_response()``,
        whose Flask default content type is ``text/html`` with a zero-length
        body. It renders nothing, so it must not be handed the permissive
        policy on that technicality -- see ``_renders_as_html``."""
        response = app.test_client().open(
            "/api/info",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.mimetype == "text/html"
        assert not response.content_length
        assert response.headers["Content-Security-Policy"] == _API_CSP

    def test_the_api_policy_forbids_everything(self):
        """``default-src 'none'`` is the whole point: an API response rendered
        as a document must be able to load and run nothing at all."""
        assert "default-src 'none'" in _API_CSP
        assert "sandbox" in _API_CSP
        for directive in (
            "frame-ancestors 'none'",
            "base-uri 'none'",
            "form-action 'none'",
        ):
            assert directive in _API_CSP

    def test_the_html_policy_never_relaxes_script_src(self):
        """The style directives are permissive by necessity (inline
        ``@keyframes``); ``script-src`` is the one that stops XSS and has no
        such excuse -- the frontend has no inline script, no eval and no
        worker. If this ever needs loosening, that is a frontend bug first."""
        script_src = _directive(_HTML_CSP, "script-src")
        assert script_src == ["'self'"]
        assert "'unsafe-eval'" not in _HTML_CSP
        assert "'unsafe-inline'" not in _directive(_HTML_CSP, "default-src")

    def test_neither_policy_permits_framing(self):
        for policy in (_API_CSP, _HTML_CSP):
            assert _directive(policy, "frame-ancestors") == ["'none'"]


class TestTheHookDoesNotFightAnyoneElse:
    """CORS and any explicit per-route choice both survive the hook."""

    def test_cors_headers_survive_on_a_preflight(self, app):
        response = app.test_client().open(
            "/api/info",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        allow_origin = response.headers["Access-Control-Allow-Origin"]
        assert allow_origin == "http://localhost:3000"
        assert "Access-Control-Allow-Methods" in response.headers
        assert "Access-Control-Allow-Headers" in response.headers
        # ...and the security headers are there too, on the same response.
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_cors_headers_survive_on_a_normal_request(self, app):
        response = app.test_client().get(
            "/api/info", headers={"Origin": "http://localhost:3000"}
        )
        allow_origin = response.headers["Access-Control-Allow-Origin"]
        assert allow_origin == "http://localhost:3000"
        assert response.headers["Content-Security-Policy"] == _API_CSP

    def test_a_route_that_sets_its_own_header_keeps_it(self, app):
        """``setdefault``, not assignment: a deliberate per-route or
        reverse-proxy choice must win over the blanket default."""
        response = app.test_client().get("/__opinionated")
        assert response.headers["Content-Security-Policy"] == "default-src 'self'"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        # The headers it did *not* set still get the default.
        assert response.headers["X-Frame-Options"] == "DENY"


class TestTheHtmlPolicyMatchesTheRealFrontend:
    """``_HTML_CSP`` is a specification for whoever serves ``index.html``, so it
    is worth only as much as its agreement with that file. This check turns
    "somebody eyeballed the frontend once" into something that fails the day a
    new CDN is added to the document.
    """

    #: Schemes that are not hosts and so are not the subject of this check.
    _NON_HOSTS = ("http://www.w3.org",)

    def test_every_external_host_in_index_html_is_permitted(self):
        index = (
            pathlib.Path(__file__).resolve().parent.parent / "frontend" / "index.html"
        )
        if not index.exists():  # pragma: no cover - frontend not checked out
            pytest.skip("frontend/index.html not present")
        hosts = {
            match.group(0)
            for match in re.finditer(
                r"https?://[A-Za-z0-9.-]+", index.read_text(encoding="utf-8")
            )
        }
        hosts = {h for h in hosts if not h.startswith(self._NON_HOSTS)}
        assert hosts, "expected index.html to reference at least the font hosts"
        unlisted = sorted(h for h in hosts if h not in _HTML_CSP)
        assert unlisted == [], (
            "frontend/index.html loads from hosts the HTML CSP does not allow, "
            f"so the SPA would break under it: {unlisted}"
        )

    def test_the_font_hosts_are_on_the_directives_that_need_them(self):
        """Both, and each on the right one: the stylesheet comes from
        googleapis and the faces it references come from gstatic, so allowing
        only one of them still yields a page with no typography."""
        assert "https://fonts.googleapis.com" in _directive(_HTML_CSP, "style-src")
        assert "https://fonts.gstatic.com" in _directive(_HTML_CSP, "font-src")

    def test_style_src_admits_inline_because_the_frontend_injects_style_tags(self):
        """Not a rubber stamp on the value -- a check that the justification
        still holds. If no component injects a <style> element any more, the
        concession should be removed rather than inherited."""
        frontend_src = (
            pathlib.Path(__file__).resolve().parent.parent / "frontend" / "src"
        )
        if not frontend_src.exists():  # pragma: no cover - frontend not checked out
            pytest.skip("frontend/src not present")
        injectors = []
        for path in frontend_src.rglob("*.jsx"):
            if path.name.endswith(".test.jsx"):
                continue
            body = path.read_text(encoding="utf-8", errors="replace")
            if "<style>" in body or "createElement('style')" in body:
                injectors.append(path.name)
        assert injectors, (
            "no component injects a <style> element any more -- style-src's "
            "'unsafe-inline' has outlived its justification and should go"
        )
        assert "'unsafe-inline'" in _directive(_HTML_CSP, "style-src")


def _directive(policy: str, name: str):
    """The source list of one directive, as a list of tokens.

    Parsing rather than substring-matching, so a test cannot pass because the
    token it wanted happened to appear under some *other* directive -- which is
    exactly how a ``script-src`` assertion would quietly start reading
    ``style-src``'s ``'unsafe-inline'``.
    """
    for chunk in policy.split(";"):
        parts = chunk.split()
        if parts and parts[0] == name:
            return parts[1:]
    return []


class TestTheDirectiveParserItself:
    """Guard-the-guard for ``_directive``: every assertion above is only as
    good as this parse, and one that quietly returned ``[]`` would make
    ``assert "'unsafe-eval'" not in ...`` pass on a policy that allowed it.
    """

    _SAMPLE = "default-src 'none'; script-src 'self' https://cdn.example; sandbox"

    def test_it_reads_a_directive_it_should_find(self):
        assert _directive(self._SAMPLE, "script-src") == [
            "'self'",
            "https://cdn.example",
        ]

    def test_it_reads_a_valueless_directive_as_present_but_empty(self):
        assert _directive(self._SAMPLE, "sandbox") == []

    def test_it_does_not_confuse_one_directive_for_another(self):
        assert _directive(self._SAMPLE, "default-src") == ["'none'"]
        assert _directive(self._SAMPLE, "style-src") == []

    def test_it_does_not_match_a_directive_name_appearing_as_a_value(self):
        policy = "default-src 'self' script-src"
        assert _directive(policy, "script-src") == []
