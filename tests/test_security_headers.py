"""Security response headers: policy composition, delivery, and the header set.

Two suites in one file, because both halves of the merge wrote one and they
cover disjoint ground.

MASTER'S HALF (issue #492) pins the *policy*: that it is composed from the one
shared JSON file rather than a hand-copied list, that production never carries
``'unsafe-inline'`` in ``script-src``, that ``report-to`` is never advertised
alongside ``report-uri`` (measured: the pair delivers nothing), and that the
Flask hook and ``frontend/vite.config.js`` agree because they read the same
data.

THIS BRANCH'S HALF pins the *delivery*: that the headers are on real responses
including the error paths an attacker reaches without credentials, that HSTS
appears only where TLS is believed in, that the strict
:data:`~src.api.security_headers._API_CSP` reaches exactly the responses it is
safe on and the document policy reaches exactly the ones that render, that the
hook does not fight the CORS layer, and that the document policy still matches
what ``frontend/index.html`` and the components actually do.

The regression the second half exists for: before it, the app set no security
headers at all -- no CSP, no ``X-Frame-Options``, no ``nosniff``, no
``Referrer-Policy`` -- and nothing would have noticed.

Getting the API/document branch backwards is silent in both directions: a
strict policy on a document is a blank page, a permissive one on the API is the
hole the strict one exists to close. Hence ``/__html_probe`` below, which
exercises the branch rather than asserting about it.
"""

import json
import types

import pytest
from flask import Flask

from src.api import security_headers
from src.api.config import DevelopmentConfig, ProductionConfig, TestingConfig
from src.api.security_headers import (
    ENFORCING_HEADER,
    REPORT_ONLY_HEADER,
    build_csp,
    load_policy,
    register_security_headers,
    serves_html_document,
)


def _directives(policy_string):
    """Parse a policy string back into {directive: [sources]}."""
    parsed = {}
    for part in policy_string.split(";"):
        tokens = part.split()
        if tokens:
            parsed[tokens[0]] = tokens[1:]
    return parsed


def _app(config_class, **overrides):
    """A bare Flask app with the CSP hook installed and one DOCUMENT route.

    ``/ping`` declares itself a document, because these tests are about the
    document policy -- the one composed from the shared JSON and shared with
    the Vite dev server. A response that does not declare itself gets
    ``_API_CSP`` instead, enforced rather than report-only; that branch has its
    own tests further down. Before the two policies existed this distinction
    did not, and ``/ping`` was a bare string.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.update(overrides)
    register_security_headers(app)

    @app.route("/ping")
    def ping():
        from flask import make_response

        return serves_html_document(make_response("pong"))

    @app.route("/ping.json")
    def ping_json():
        return {"pong": True}

    return app


# --------------------------------------------------------------------------
# Policy composition
# --------------------------------------------------------------------------


def test_shared_policy_file_is_readable_and_has_both_sections():
    policy = load_policy()
    assert set(policy) == {"base", "dev_additions"}
    assert policy["base"]["default-src"] == ["'self'"]


def test_load_policy_drops_the_in_file_rationale_comment():
    """The JSON carries a `_comment` array for humans; consumers must not see it."""
    raw = json.loads(security_headers.POLICY_PATH.read_text(encoding="utf-8"))
    assert "_comment" in raw, "the rationale comment is part of the file's contract"
    assert "_comment" not in load_policy()


def test_production_policy_locks_down_script_src():
    directives = _directives(build_csp(dev=False))
    assert directives["script-src"] == ["'self'"]
    assert "'unsafe-eval'" not in directives["script-src"]


def test_production_policy_never_relaxes_scripts_even_via_dev_additions():
    """The whole point of the dev flag: prod must not inherit its relaxations."""
    prod = build_csp(dev=False)
    assert "'unsafe-inline'" not in _directives(prod)["script-src"]
    assert "ws:" not in prod


def test_dev_policy_allows_the_vite_react_refresh_preamble():
    directives = _directives(build_csp(dev=True))
    assert "'unsafe-inline'" in directives["script-src"]
    assert "ws:" in directives["connect-src"]
    # Base sources survive the merge rather than being replaced by it.
    assert "'self'" in directives["connect-src"]


def test_dev_additions_do_not_duplicate_a_source_the_base_already_allows():
    policy = {
        "base": {"connect-src": ["'self'"]},
        "dev_additions": {"connect-src": ["'self'", "ws:"]},
    }
    assert _directives(build_csp(dev=True, policy=policy))["connect-src"] == [
        "'self'",
        "ws:",
    ]


def test_style_src_keeps_unsafe_inline_for_react_inline_style_props():
    """Documented, accepted exception — see docs/development/csp-rollout.md."""
    assert "'unsafe-inline'" in _directives(build_csp())["style-src"]


def test_report_directives_are_emitted_only_when_a_uri_is_configured():
    with_uri = build_csp(report_uri="/api/logs/csp-report")
    assert "report-uri /api/logs/csp-report" in with_uri

    without = build_csp(report_uri=None)
    assert "report-uri" not in without


def test_report_to_is_never_advertised_alongside_report_uri():
    """Advertising both transports delivers nothing in Chromium.

    ``report-to`` takes precedence over ``report-uri`` whenever both are
    present, and Chromium then queues the report through the Reporting API
    instead of POSTing it — a plain-HTTP origin is not even an eligible
    endpoint. Measured over one forced violation: ``report-uri`` alone → 1 POST,
    ``report-to`` alone → 0, both → 0. A report-only rollout that silently
    reports nothing reads as "clean", which is the worst possible outcome, so
    this is pinned rather than left to a future tidy-up. See the module
    docstring in src/api/security_headers.py.
    """
    assert "report-to" not in build_csp(report_uri="/api/logs/csp-report")


def test_a_directive_only_present_in_dev_additions_is_still_emitted():
    policy = {"base": {"default-src": ["'self'"]}, "dev_additions": {"worker-src": ["blob:"]}}
    assert "worker-src blob:" in build_csp(dev=True, policy=policy)


# --------------------------------------------------------------------------
# Delivery
# --------------------------------------------------------------------------


def test_report_only_header_is_set_on_responses():
    app = _app(TestingConfig)
    response = app.test_client().get("/ping")
    assert REPORT_ONLY_HEADER in response.headers
    assert ENFORCING_HEADER not in response.headers


def test_a_non_document_response_gets_the_strict_policy_enforced():
    """Not report-only, and not the document policy.

    The rollout is report-only so a real document cannot break while we learn
    what it needs. A JSON response has nothing to break -- CSP binds documents,
    and a fetched body never becomes one -- so it takes the strictest policy in
    the grammar, enforced. Report-only on ``/api/*`` would have been a header
    that blocks nothing.
    """
    response = _app(TestingConfig).test_client().get("/ping.json")
    assert response.headers[ENFORCING_HEADER] == _API_CSP
    assert REPORT_ONLY_HEADER not in response.headers


def test_no_reporting_endpoints_header_is_sent():
    """The companion of ``report-to``; both are omitted for the same reason."""
    headers = _app(TestingConfig).test_client().get("/ping").headers
    assert "Reporting-Endpoints" not in headers


def test_report_only_false_switches_to_the_enforcing_header():
    app = _app(TestingConfig, CSP_REPORT_ONLY=False)
    response = app.test_client().get("/ping")
    assert ENFORCING_HEADER in response.headers
    assert REPORT_ONLY_HEADER not in response.headers


def test_csp_can_be_disabled_entirely():
    app = _app(TestingConfig, CSP_ENABLED=False)
    response = app.test_client().get("/ping")
    assert REPORT_ONLY_HEADER not in response.headers
    assert ENFORCING_HEADER not in response.headers


def test_register_reports_whether_it_installed_the_hook():
    assert register_security_headers(_app(TestingConfig)) is True
    disabled = Flask(__name__)
    disabled.config["CSP_ENABLED"] = False
    assert register_security_headers(disabled) is False


def test_a_policy_already_set_by_a_nearer_layer_is_not_clobbered():
    app = _app(TestingConfig)

    @app.route("/own-policy")
    def own_policy():
        from flask import make_response

        response = make_response("ok")
        response.headers[ENFORCING_HEADER] = "default-src 'none'"
        return response

    response = app.test_client().get("/own-policy")
    assert response.headers[ENFORCING_HEADER] == "default-src 'none'"
    assert REPORT_ONLY_HEADER not in response.headers


def test_development_config_serves_the_dev_relaxations():
    header = _app(DevelopmentConfig).test_client().get("/ping").headers[
        REPORT_ONLY_HEADER
    ]
    assert "'unsafe-inline'" in _directives(header)["script-src"]


def test_production_config_serves_the_locked_down_policy():
    header = _app(ProductionConfig).test_client().get("/ping").headers[
        REPORT_ONLY_HEADER
    ]
    assert _directives(header)["script-src"] == ["'self'"]


@pytest.mark.parametrize(
    "raw,expected_relaxed",
    [("0", False), ("false", False), ("no", False), ("", False), ("1", True), ("true", True)],
)
def test_string_flags_from_the_environment_are_coerced(raw, expected_relaxed):
    app = _app(TestingConfig, CSP_DEV_RELAXATIONS=raw)
    header = app.test_client().get("/ping").headers[REPORT_ONLY_HEADER]
    assert ("'unsafe-inline'" in _directives(header)["script-src"]) is expected_relaxed


def test_missing_config_key_falls_back_to_the_environment(monkeypatch):
    monkeypatch.setenv("CSP_REPORT_ONLY", "false")
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_security_headers(app)

    @app.route("/ping")
    def ping():
        from flask import make_response

        return serves_html_document(make_response("pong"))

    assert ENFORCING_HEADER in app.test_client().get("/ping").headers


def test_flask_config_wins_over_a_conflicting_environment_variable(monkeypatch):
    monkeypatch.setenv("CSP_REPORT_ONLY", "false")
    app = _app(TestingConfig, CSP_REPORT_ONLY=True)
    assert REPORT_ONLY_HEADER in app.test_client().get("/ping").headers


def test_report_uri_omitted_leaves_the_report_directive_off():
    app = _app(TestingConfig, CSP_REPORT_URI="")
    headers = app.test_client().get("/ping").headers
    assert "report-uri" not in headers[REPORT_ONLY_HEADER]


def test_policy_is_read_once_at_registration_not_per_request(monkeypatch):
    """A per-response file read would put disk I/O on every API call."""
    calls = []
    real = security_headers.load_policy

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(security_headers, "load_policy", counting)
    app = _app(TestingConfig)
    before = len(calls)
    client = app.test_client()
    client.get("/ping")
    client.get("/ping")
    assert len(calls) == before


def test_load_policy_accepts_an_explicit_path(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"base": {"default-src": ["'none'"]}}), encoding="utf-8")
    assert load_policy(path) == {"base": {"default-src": ["'none'"]}}


def test_bool_config_values_pass_through_unchanged():
    """`_flag` must not stringify a real bool into an always-true value."""
    app = types.SimpleNamespace(config={"CSP_ENABLED": False})
    assert security_headers._flag(app, "CSP_ENABLED", True) is False


# --------------------------------------------------------------------------
# Cross-server drift
#
# The Vite dev/preview server composes the same policy in JavaScript. Nothing
# at runtime can catch the two implementations disagreeing — a dev server whose
# policy has quietly diverged from the API's simply reports the wrong
# violations, which is worse than reporting none. These pin the properties that
# keep them in step by construction.
# --------------------------------------------------------------------------

VITE_CONFIG = (
    security_headers.POLICY_PATH.parent.parent.parent
    / "frontend"
    / "vite.config.js"
)


def _vite_config_source(strip_comments=False):
    source = VITE_CONFIG.read_text(encoding="utf-8")
    if strip_comments:
        # Directive names are discussed in the file's comments; only *code*
        # that names one would be an inlined copy.
        source = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith(("//", "*", "/*"))
        )
    return source


def test_vite_config_reads_the_shared_policy_file():
    assert "csp-policy.json" in _vite_config_source()


@pytest.mark.parametrize("directive", sorted(load_policy()["base"]))
def test_vite_config_does_not_inline_a_copy_of_any_directive(directive):
    """A hand-copied directive list is exactly how the two policies drift."""
    assert directive not in _vite_config_source(strip_comments=True)


def test_vite_config_does_not_advertise_report_to_either():
    """Same measured reason as the Flask side — the two must not diverge."""
    source = _vite_config_source(strip_comments=True)
    assert "report-to" not in source
    assert "Reporting-Endpoints" not in source


def test_vite_preview_serves_the_production_policy():
    """`vite preview` serves the built bundle, so it must not relax script-src.

    Step 3 of docs/development/csp-rollout.md leans on this: preview is the only
    local surface that exercises the production ``script-src``.
    """
    source = _vite_config_source()
    assert "cspHeaders({ dev: true })" in source, "dev server keeps its relaxations"
    assert "cspHeaders({ dev: false })" in source, "preview must not"


def test_the_vite_report_uri_matches_the_production_report_uri():
    """Both resolve to the deployed subpath; a mismatch loses reports silently."""
    assert ProductionConfig.CSP_REPORT_URI in _vite_config_source().replace(
        "${BASE}api", "/games/HeartOfVirtue/api"
    )


def test_the_real_app_factory_serves_the_policy(make_api_app):
    """Every other delivery test builds a bare Flask app and registers the hook
    by hand, so deleting ``register_security_headers(app)`` from the factory
    left this whole file green. This is the only test that would catch that.

    ``/health`` is deliberate: it needs no session, so this cannot drag a real
    Universe into the default suite. Being JSON, it takes the enforced
    ``_API_CSP`` rather than the report-only document policy -- either would
    prove the hook is wired, which is the only thing at stake here.
    """
    response = make_api_app().test_client().get("/health")
    assert response.headers[ENFORCING_HEADER] == _API_CSP
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_the_report_uri_resolves_to_a_real_route(make_api_app):
    """A re-prefixed blueprint would send every violation into a 404."""
    app = make_api_app()
    report_path = app.config["CSP_REPORT_URI"]
    assert any(str(rule) == report_path for rule in app.url_map.iter_rules())


# --------------------------------------------------------------------------
# Header delivery: the set, HSTS, the API/document branch, CORS coexistence
# --------------------------------------------------------------------------

import pathlib
import re
from unittest.mock import MagicMock, patch

from src.api.security_headers import (
    _API_CSP,
    _FRAME_OPTIONS_HEADER,
    _FRAME_OPTIONS_VALUE,
    _HSTS_HEADER,
    _HSTS_VALUE,
    _STATIC_SECURITY_HEADERS,
)
from tests._cite import Read, verify

# The document policy as this app actually composes and ships it, not a
# transcription of it. `_DOCUMENT_CSP` -- a second, hand-written copy of the same
# directives -- used to sit in security_headers.py and be the target of every
# assertion below; master replaced it with `src/resources/csp-policy.json`,
# read by BOTH the Flask hook and frontend/vite.config.js, which is the whole
# point (a policy that drifts between the dev server and the API is a policy
# nobody trusts). Reading it back through `build_csp` means the checks below
# are made against what the browser gets.
#
# `dev=False`: the production policy is the one whose promises matter. The dev
# relaxations get their own tests in master's half of this file.
_DOCUMENT_CSP = build_csp(dev=False)

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_FRONTEND = _REPO_ROOT / "frontend"

#: Where the ``style-src`` concession is argued. Derived rather than written:
#: this reference was ``app.py`` until the reasoning was extracted, and a
#: hand-written module name is exactly what went stale. ``describe()`` resolves
#: the file and line when a failure message needs them, and
#: :meth:`TestTheHtmlPolicyMatchesTheRealFrontend
#: .test_the_rationale_this_suite_cites_is_still_there` fails if the anchor
#: moves out from under it.
_STYLE_SRC_RATIONALE = Read(
    "docs/development/csp-rollout.md",
    "Tailwind and Vite inject `<style>` elements at runtime in development.",
)


# ---------------------------------------------------------------------------
# Policy parsing
#
# Defined above every caller on purpose: these read a CSP string, and a reader
# scanning top-down has to know they parse rather than substring-match before
# any assertion using them means anything.
# ---------------------------------------------------------------------------


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


def _permits(policy: str, directive: str, host: str) -> bool:
    """True if ``policy`` allows ``host`` to be loaded under ``directive``.

    Applies CSP's own fallback: a fetch directive that is absent inherits
    ``default-src``. Checking membership in the parsed token list, not
    ``host in policy``, is the point -- a host listed only under ``font-src``
    but pulled in as a stylesheet satisfies the substring test and still gets
    blocked by a real browser.
    """
    tokens = _directive(policy, directive) or _directive(policy, "default-src")
    return host in tokens


def _fetch_hosts(policy: str) -> set:
    """Every host token the policy names under any fetch directive."""
    hosts = set()
    for chunk in policy.split(";"):
        parts = chunk.split()
        if parts and parts[0].endswith("-src"):
            hosts.update(t for t in parts[1:] if "//" in t)
    return hosts


# ---------------------------------------------------------------------------
# Reading frontend/index.html
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(
    r"<(?P<tag>script|link|img|iframe|source)\b(?P<attrs>[^>]*)>", re.I
)
_ATTR_RE = re.compile(
    r"""(?P<name>[A-Za-z-]+)\s*=\s*(?P<q>["'])(?P<value>[^"']*)(?P=q)"""
)
_HOST_RE = re.compile(r"https?://[A-Za-z0-9.-]+")

#: ``rel`` value -> the CSP directive that governs the resulting fetch.
_REL_DIRECTIVE = {
    "stylesheet": "style-src",
    "icon": "img-src",
    "shortcut icon": "img-src",
    "apple-touch-icon": "img-src",
    "modulepreload": "script-src",
    "manifest": "connect-src",
}

#: ``<link rel="preload" as="...">`` -- the ``as`` names the directive.
_AS_DIRECTIVE = {
    "style": "style-src",
    "font": "font-src",
    "script": "script-src",
    "image": "img-src",
    "fetch": "connect-src",
    "track": "media-src",
    "audio": "media-src",
    "video": "media-src",
}

#: ``rel`` values that only warm a connection. The browser fetches no resource,
#: so no fetch directive governs the hint itself -- but a host worth warming is
#: a host something is about to load, so it still has to appear somewhere.
_HINT_RELS = {"preconnect", "dns-prefetch", "prefetch"}

#: Tag -> the attribute that carries the URL it fetches.
_URL_ATTR = {
    "script": "src",
    "img": "src",
    "iframe": "src",
    "source": "src",
    "link": "href",
}

_TAG_DIRECTIVE = {
    "script": "script-src",
    "img": "img-src",
    "iframe": "frame-src",
    "source": "media-src",
}


def _external_references(html: str):
    """Classify every externally-hosted resource ``html`` pulls in.

    Returns ``(fetches, hints, unclassified)``:

    * ``fetches`` -- ``{(host, directive)}`` for resources the browser loads.
    * ``hints`` -- hosts named only by ``preconnect``/``dns-prefetch``.
    * ``unclassified`` -- ``{(tag, rel, host)}`` this mapping cannot place.

    ``unclassified`` is returned rather than ignored so that a new kind of tag
    fails the caller loudly instead of silently escaping the check. Attributes
    that never cause a fetch (``xmlns``, ``content``) are not read at all.
    """
    fetches, hints, unclassified = set(), set(), set()
    for tag_match in _TAG_RE.finditer(html):
        tag = tag_match.group("tag").lower()
        attrs = {
            m.group("name").lower(): m.group("value")
            for m in _ATTR_RE.finditer(tag_match.group("attrs"))
        }
        url = attrs.get(_URL_ATTR[tag], "")
        host_match = _HOST_RE.match(url.strip())
        if not host_match:  # relative URL -- same origin, nothing to permit
            continue
        host = host_match.group(0)

        rel = (attrs.get("rel") or "").strip().lower()
        if tag == "link":
            if rel in _HINT_RELS:
                hints.add(host)
                continue
            if rel == "preload":
                directive = _AS_DIRECTIVE.get((attrs.get("as") or "").lower())
            else:
                directive = _REL_DIRECTIVE.get(rel)
        else:
            directive = _TAG_DIRECTIVE.get(tag)

        if directive is None:
            unclassified.add((tag, rel, host))
        else:
            fetches.add((host, directive))
    return fetches, hints, unclassified


# ---------------------------------------------------------------------------
# Reading frontend/src for inline-style injection
# ---------------------------------------------------------------------------

#: Comments and string literals, so comments can be dropped without a ``//``
#: inside a URL string eating the rest of the line. Strings are matched only to
#: be *kept*: ``insertAdjacentHTML('beforeend', '<style>…')`` puts a real
#: injection inside one.
_JS_COMMENT_OR_STRING = re.compile(
    r"""(?P<comment> // [^\n]* | /\* .*? \*/ )
      | (?P<string> " (?:\\.|[^"\\])* "
                  | ' (?:\\.|[^'\\])* '
                  | ` (?:\\.|[^`\\])* ` )""",
    re.VERBOSE | re.DOTALL,
)

#: Every textual route to an inline stylesheet, matched as a regex rather than
#: by literal substring. The literal-substring version this replaces read
#: ``"<style>" in body or "createElement('style')" in body``, which
#: ``createElement("style")``, ``<style type="text/css">``, ``insertRule`` and
#: ``insertAdjacentHTML`` all walked straight past.
#:
#: The last alternative is knowingly the loose one, and it is loose on purpose.
#: ``insertAdjacentHTML`` is the ordinary way to insert *any* markup, so a bare
#: call proves nothing about stylesheets -- an ``insertAdjacentHTML`` of a
#: ``<div>`` is matched here and is not an injector. The narrower rule would be
#: to require ``<style`` inside the call, and that rule is defeated by one
#: string concatenation: ``'<sty' + 'le>'``, which is
#: ``TestTheInjectorScanItself``'s case I and which no character-level pattern
#: can see through. The over-approximation is the cheaper error of the two,
#: because of what each costs:
#:
#: * a false positive adds a filename to
#:   :data:`TestTheHtmlPolicyMatchesTheRealFrontend._STYLE_INJECTORS`, and the
#:   test that compares the two says so out loud on the next run;
#: * a false negative silently drops a component from that list, which makes
#:   ``style-src 'unsafe-inline'`` look closer to removable than it is -- and
#:   removing it blanks the page.
#:
#: No file in ``frontend/src`` matches this alternative today, so it is a
#: latent cost rather than a live one. If it ever fires on a component that
#: inserts ordinary markup, tighten it *there* with the concatenation case in
#: mind rather than deleting it.
_INJECTS_STYLE = re.compile(
    r"""< style [\s/>]
      | createElement \s* \( \s* ['"`] style ['"`]
      | \. insertRule \s* \(
      | insertAdjacentHTML \s* \(""",
    re.VERBOSE,
)


def _strip_js_comments(source: str) -> str:
    """``source`` with comments removed and string literals left intact.

    Without this the scan punishes explaining itself: a comment that mentions
    the tag by name counted the file as an injector, which is how a component
    that merely *documents* where its keyframes moved to got flagged.
    """
    return _JS_COMMENT_OR_STRING.sub(
        lambda m: "" if m.group("comment") else m.group(0), source
    )


def _style_injectors(root: pathlib.Path) -> set:
    """Filenames under ``root`` that put a stylesheet into the document.

    Both ``*.js`` and ``*.jsx``: the previous version globbed ``*.jsx`` alone,
    so a plain module was free to inject and stay invisible to this check.

    Test scaffolding is excluded -- ``*.test.js``/``*.test.jsx`` and everything
    under ``src/test/`` -- because none of it is in the shipped bundle, and the
    question here is what the *document* does. ``src/test/keyframeAudit.js`` is
    the live example: it is a static auditor that quotes the tag it looks for.
    """
    injectors = set()
    for path in sorted(root.rglob("*.js")) + sorted(root.rglob("*.jsx")):
        if path.name.endswith((".test.js", ".test.jsx")):
            continue
        if "test" in path.relative_to(root).parts[:-1]:
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if _INJECTS_STYLE.search(_strip_js_comments(body)):
            injectors.add(path.name)
    return injectors


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
    # It opts in by name, which is the whole of the branch: the policy follows
    # a deliberate declaration, not a sniffed content type.
    @built.route("/__html_probe")
    def _html_probe():
        from flask import make_response

        return serves_html_document(
            make_response("<!doctype html><html><body>probe</body></html>")
        )

    # The same body with no declaration -- the shape Werkzeug produces on its
    # own for redirects and HTTPExceptions. It must stay strict.
    @built.route("/__unmarked_html")
    def _unmarked_html():
        return "<!doctype html><html><body>not declared</body></html>"

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

    def test_the_static_set_is_the_two_agreed_headers(self):
        """Pinned by value: each was a deliberate choice documented beside
        ``_STATIC_SECURITY_HEADERS`` in ``src/api/security_headers.py``, and
        ``Referrer-Policy`` in particular had a defensible alternative."""
        assert _STATIC_SECURITY_HEADERS == {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

    def test_frame_options_rides_with_the_api_policy_and_not_the_document_one(
        self, app
    ):
        """The two framing controls must not contradict each other.

        ``X-Frame-Options: DENY`` and the document policy's
        ``frame-ancestors 'self'`` disagree, and which one wins depends on
        whether the browser implements CSP framing -- so the blunt header is
        sent only alongside ``_API_CSP``, whose ``frame-ancestors 'none'`` it
        agrees with. If the shared policy ever tightens to ``'none'``, this is
        what should be updated to let the header apply everywhere.
        """
        client = app.test_client()
        assert (
            client.get("/health").headers.get(_FRAME_OPTIONS_HEADER)
            == _FRAME_OPTIONS_VALUE
        )
        assert _FRAME_OPTIONS_HEADER not in client.get("/__html_probe").headers
        assert "frame-ancestors 'none'" in _API_CSP


class TestStrictTransportSecurity:
    """HSTS is the one header here with a precondition, so it has its own gate.

    The session id travels as ``Authorization: Bearer``, which
    ``SESSION_COOKIE_SECURE`` does nothing for -- one plaintext request leaks
    the credential outright. But a host not actually reachable over TLS that
    sends this header has locked its own clients out for a year, so it is tied
    to the flag by which the app already claims to be behind TLS.
    """

    def _build(self, config_class):
        session_manager = MagicMock()
        session_manager.get_active_session_count.return_value = 0
        with (
            patch("src.api.app.universe_module"),
            patch("src.api.app.SessionManager", return_value=session_manager),
            patch("src.api.app.GameService", return_value=MagicMock()),
        ):
            from src.api.app import create_app

            built, _socketio = create_app(config_class)
        return built

    def test_a_non_tls_config_does_not_send_it(self, app):
        """The default posture. Sending it here would be a promise the dev
        server cannot keep, and browsers honour the promise, not the intent."""
        response = app.test_client().get("/health")
        assert _HSTS_HEADER not in response.headers

    def test_a_tls_config_sends_it(self):
        class _SecureConfig:
            TESTING = True
            DEBUG = False
            SECRET_KEY = "test-secret"
            CORS_ORIGINS = ["http://localhost:3000"]
            SESSION_COOKIE_SECURE = True

        response = self._build(_SecureConfig).test_client().get("/health")
        assert response.headers[_HSTS_HEADER] == _HSTS_VALUE

    def test_the_real_production_config_qualifies(self):
        """The gate is only worth anything if the config it keys on is the one
        production actually uses -- a private flag nothing sets would make the
        two tests above agree with each other and with nothing else."""
        from src.api.config import ProductionConfig

        assert ProductionConfig.SESSION_COOKIE_SECURE is True

    def test_it_claims_no_authority_over_sibling_hosts(self):
        """``includeSubDomains`` from an API host asserts TLS on domains this
        app knows nothing about, and ``preload`` makes that irreversible."""
        assert "includeSubDomains" not in _HSTS_VALUE
        assert "preload" not in _HSTS_VALUE
        assert _HSTS_VALUE.startswith("max-age=")
        assert int(_HSTS_VALUE.split("=")[1]) >= 31536000


class TestThePolicyMatchesWhatTheResponseIs:
    """JSON never renders; HTML does. The two get different policies."""

    @pytest.mark.parametrize(
        "path", ["/health", "/api/info", "/definitely-not-a-route"]
    )
    def test_json_responses_get_the_strict_policy(self, app, path):
        response = app.test_client().get(path)
        assert response.mimetype == "application/json"
        assert response.headers["Content-Security-Policy"] == _API_CSP

    def test_a_declared_html_document_gets_the_permissive_policy(self, app):
        response = app.test_client().get("/__html_probe")
        assert response.mimetype == "text/html"
        header = (
            REPORT_ONLY_HEADER
            if REPORT_ONLY_HEADER in response.headers
            else ENFORCING_HEADER
        )
        # Compared against the DEV policy, not the production one: this probe
        # app runs under a TESTING config and `CSP_DEV_RELAXATIONS` defaults to
        # `TESTING`, so what it ships is `build_csp(dev=True)` plus a
        # report-uri. The report-uri is dropped before comparing rather than
        # re-derived, because deriving it here would mean re-implementing
        # `_flag`'s config-then-environment resolution in the test —
        # a second copy of the thing under test. Its presence is asserted
        # separately, which is all this test has an opinion about.
        shipped = _directives(response.headers[header])
        assert shipped.pop("report-uri", None), (
            "the document policy ships no report-uri, so violations go nowhere "
            "and the report-only rollout reads as zero violations"
        )
        assert shipped == _directives(build_csp(dev=True))
        assert shipped != _directives(_DOCUMENT_CSP), (
            "the dev and production document policies are identical, so this "
            "test no longer distinguishes them -- check dev_additions"
        )

    def test_undeclared_html_still_gets_the_strict_policy(self, app):
        """The inversion, stated as a test. Nothing in this app authors HTML,
        so every ``text/html`` body it emits unbidden is Werkzeug's -- a
        routing redirect, or an HTTPException that reached the WSGI layer.
        Sniffing the content type handed the permissive policy to exactly those
        unaudited error paths while the strict one covered the routes we
        control. Opting in reverses that, and forgetting to opt in fails
        visibly (a blank page) rather than silently."""
        response = app.test_client().get("/__unmarked_html")
        assert response.mimetype == "text/html"
        assert response.content_length
        assert response.headers["Content-Security-Policy"] == _API_CSP

    def test_an_empty_html_response_is_still_treated_as_non_rendering(self, app):
        """``handle_preflight`` answers OPTIONS with a bare ``make_response()``,
        whose Flask default content type is ``text/html`` with a zero-length
        body. It declares nothing and renders nothing, so it stays strict."""
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
        script_src = _directive(_DOCUMENT_CSP, "script-src")
        assert script_src == ["'self'"]
        assert "'unsafe-eval'" not in _DOCUMENT_CSP
        assert "'unsafe-inline'" not in _directive(_DOCUMENT_CSP, "default-src")

    def test_the_api_policy_permits_no_framing_at_all(self):
        """``'none'`` here, and paired with ``X-Frame-Options: DENY`` for the
        browsers that ignore CSP framing -- see the frame-options test above
        for why that header rides with this policy and not the other one."""
        assert _directive(_API_CSP, "frame-ancestors") == ["'none'"]

    def test_the_document_policy_permits_framing_only_by_itself(self):
        """Deliberately weaker than the API policy's ``'none'``, and pinned so
        the difference is a decision rather than an oversight.

        The value is the shared one in ``src/resources/csp-policy.json``, which
        ``frontend/vite.config.js`` reads too, so tightening it is a change to
        the SPA's policy and not merely to this app's. Nothing frames the game
        today; ``'self'`` is the conservative default the rollout started from.
        Anything beyond ``'self'`` would be a real regression, which is what
        this catches."""
        assert _directive(_DOCUMENT_CSP, "frame-ancestors") == ["'self'"]


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
    """``_DOCUMENT_CSP`` is a specification for whoever serves ``index.html`` (it
    is never sent by this app -- see the module docstring), so it is worth only
    as much as its agreement with that file. These checks turn "somebody
    eyeballed the frontend once" into something that fails the day a new CDN is
    added to the document.
    """

    def _index_html(self):
        index = _FRONTEND / "index.html"
        if not index.exists():  # pragma: no cover - frontend not checked out
            pytest.skip("frontend/index.html not present")
        return index.read_text(encoding="utf-8")

    def test_every_external_host_in_index_html_is_permitted(self):
        """Per directive, not per policy. The version this replaces asked
        ``host not in _DOCUMENT_CSP`` -- a substring test against the whole policy
        string, which is the very technique ``_directive``'s docstring warns
        about. A host listed only under ``font-src`` and loaded as a stylesheet
        satisfied it while the SPA broke.
        """
        fetches, hints, unclassified = _external_references(self._index_html())
        assert fetches or hints, (
            "expected index.html to reference at least the font hosts"
        )
        assert unclassified == set(), (
            "index.html loads an external resource this check cannot place "
            f"under a CSP directive, so it is going unchecked: {unclassified}"
        )

        unlisted = sorted(
            (host, directive)
            for host, directive in fetches
            if not _permits(_DOCUMENT_CSP, directive, host)
        )
        assert unlisted == [], (
            "frontend/index.html loads from hosts the HTML CSP does not allow "
            f"under the governing directive, so the SPA would break: {unlisted}"
        )

        permitted_anywhere = _fetch_hosts(_DOCUMENT_CSP)
        stray_hints = sorted(h for h in hints if h not in permitted_anywhere)
        assert stray_hints == [], (
            "index.html preconnects to hosts no fetch directive permits -- "
            f"either the policy is missing them or the hint is dead: {stray_hints}"
        )

    def test_the_font_hosts_are_on_the_directives_that_need_them(self):
        """Both, and each on the right one: the stylesheet comes from
        googleapis and the faces it references come from gstatic, so allowing
        only one of them still yields a page with no typography."""
        assert "https://fonts.googleapis.com" in _directive(_DOCUMENT_CSP, "style-src")
        assert "https://fonts.gstatic.com" in _directive(_DOCUMENT_CSP, "font-src")

    #: The components whose inline ``<style>`` blocks are the entire reason
    #: ``style-src`` carries ``'unsafe-inline'``, as named in the rationale
    #: beside that directive -- :data:`_STYLE_SRC_RATIONALE` locates it.
    #:
    #: Pinned as a set, not counted, because the prose version of this list
    #: went stale without anything noticing: it named six components, three of
    #: which (TypewriterOutput's ``blink``, NpcChatPanel's spinner,
    #: ItemDetailDialog's ``fadeIn``) have since had their keyframes lifted
    #: into ``frontend/src/styles/index.css``. ``fadeIn`` was not a tidy-up:
    #: ``ActionsPanel`` was animating with it while the only declaration lived
    #: inside ``ItemDetailDialog``, so it animated only while an item dialog
    #: happened to be mounted. A rationale nothing checks decays into a
    #: rationale nobody can trust, and this is the directive where that costs
    #: the most.
    _STYLE_INJECTORS = {
        "GameOverScreen.jsx",
        "HeroPanel.jsx",
        "ToastContext.jsx",
        "InteractPanel.jsx",  # document.createElement('style')
        "HeatMeter.jsx",  # @keyframes heatChip
    }

    def test_the_rationale_this_suite_cites_is_still_there(self):
        """The citation above is only a citation while its anchor exists.

        A module name in prose survives the module being gutted; an anchor does
        not. This is the half a hand-written ``app.py`` could never give: when
        the reasoning moves again, this fails instead of quietly pointing at a
        file that no longer argues anything.
        """
        broken = verify([_STYLE_SRC_RATIONALE])
        assert not broken, (
            "the style-src rationale this suite cites has moved or been "
            "reworded: " + "; ".join(broken) + ". Repoint "
            "_STYLE_SRC_RATIONALE at the literal the rationale now carries -- "
            "do not widen the anchor to something that happens to match."
        )

    def _injectors(self):
        frontend_src = _FRONTEND / "src"
        if not frontend_src.exists():  # pragma: no cover - not checked out
            pytest.skip("frontend/src not present")
        return _style_injectors(frontend_src)

    def test_style_src_admits_inline_and_the_cited_second_reason_holds(self):
        """Not a rubber stamp on the value -- a check that the cited reasoning
        still describes the codebase.

        The concession is unavoidable on the doc's FIRST reason alone (React
        inline ``style={{}}`` props become element style attributes, which
        ``style-src-attr`` governs and neither a nonce nor a hash reaches), so
        this cannot assert that an empty injector set makes it removable. What
        it can assert is that the doc's second reason -- components injecting a
        ``<style>`` element -- is still true of the tree, rather than prose
        that outlived its subject.
        """
        assert self._injectors(), (
            "no component injects a <style> element any more, so the second "
            f"reason given in {_STYLE_SRC_RATIONALE} is now false -- rewrite "
            "the doc to rest on the inline-style-props argument alone"
        )
        assert "'unsafe-inline'" in _directive(_DOCUMENT_CSP, "style-src")

    def test_the_rationale_names_exactly_the_components_that_still_inject(self):
        """Fails in both directions on purpose. A component dropped from the
        real list means the concession is closer to removable and the comment
        overstates the need; a component added means the comment understates
        it. Either way the prose beside the directive is now wrong, and this is
        the only thing that will say so."""
        assert self._injectors() == self._STYLE_INJECTORS, (
            "the set of components injecting a <style> element has changed, so "
            f"the style-src rationale ({_STYLE_SRC_RATIONALE}) and this list "
            "both need updating"
        )


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


class TestTheHostCheckItself:
    """Guard-the-guard for the index.html check. The property that matters is
    that it can *fail* on a policy the old substring version accepted."""

    _INDEX = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=X" rel="stylesheet">'
        '<link rel="icon" type="image/png" href="/hero-heart.png">'
        '<script type="module" src="/src/main.jsx"></script>'
    )

    def test_it_classifies_each_reference_by_the_directive_that_governs_it(self):
        fetches, hints, unclassified = _external_references(self._INDEX)
        assert fetches == {("https://fonts.googleapis.com", "style-src")}
        assert hints == {
            "https://fonts.googleapis.com",
            "https://fonts.gstatic.com",
        }
        assert unclassified == set()

    def test_it_ignores_same_origin_urls(self):
        """The icon and the module entry point are relative. A check that
        counted them would fail on a policy that is entirely correct."""
        fetches, hints, _ = _external_references(self._INDEX)
        assert all(h.startswith("http") for h, _ in fetches)
        assert not any("hero-heart" in h for h in hints)

    def test_it_reports_a_tag_it_cannot_place(self):
        """A new kind of external reference must fail loudly rather than slip
        past unexamined."""
        _, _, unclassified = _external_references(
            '<link rel="somethingnew" href="https://cdn.example/x.css">'
        )
        assert unclassified == {("link", "somethingnew", "https://cdn.example")}

    def test_a_host_on_the_wrong_directive_is_rejected(self):
        """The exact hole the substring version left open: googleapis present
        in the policy, but only under ``font-src``, while index.html loads it
        as a stylesheet. ``"https://fonts.googleapis.com" in policy`` is True
        here and the browser blocks the request anyway."""
        wrong = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com"
        )
        assert "https://fonts.googleapis.com" in wrong  # the old test's check
        assert not _permits(wrong, "style-src", "https://fonts.googleapis.com")

        fetches, _, _ = _external_references(self._INDEX)
        unlisted = [
            (h, d) for h, d in fetches if not _permits(wrong, d, h)
        ]
        assert unlisted == [("https://fonts.googleapis.com", "style-src")]

    def test_an_absent_directive_falls_back_to_default_src(self):
        """CSP's own rule. A policy with no ``img-src`` is not a policy that
        blocks images, and reporting one would be a false alarm."""
        policy = "default-src 'self' https://cdn.example; script-src 'self'"
        assert _permits(policy, "img-src", "https://cdn.example")
        assert not _permits(policy, "script-src", "https://cdn.example")

    def test_fetch_hosts_reads_only_fetch_directives(self):
        policy = (
            "default-src 'none'; img-src https://a.example; "
            "frame-ancestors https://b.example; report-uri https://c.example"
        )
        assert _fetch_hosts(policy) == {"https://a.example"}


class TestTheInjectorScanItself:
    """Guard-the-guard for ``_style_injectors``. Its previous form matched two
    literal substrings in ``*.jsx`` files, and each case below walked past it.
    """

    def _write(self, tmp_path, name, body):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    @pytest.mark.parametrize(
        "name, body",
        [
            # The two the old literal check did catch.
            ("A.jsx", "export const A = () => <style>{`@keyframes x {}`}</style>"),
            ("B.jsx", "const el = document.createElement('style')"),
            # Everything it did not.
            ("C.js", "const el = document.createElement('style')"),
            ("D.jsx", 'const el = document.createElement("style")'),
            ("E.jsx", "const el = document.createElement(`style`)"),
            ("F.jsx", '<style type="text/css">{css}</style>'),
            ("G.jsx", "<style>{css}</style>"),
            ("H.js", "sheet.insertRule('@keyframes x {}')"),
            ("I.jsx", "node.insertAdjacentHTML('beforeend', '<sty' + 'le>')"),
        ],
    )
    def test_it_catches_every_route_to_an_inline_stylesheet(
        self, tmp_path, name, body
    ):
        self._write(tmp_path, name, body)
        assert _style_injectors(tmp_path) == {name}

    def test_a_file_that_only_mentions_the_tag_in_a_comment_is_not_an_injector(
        self, tmp_path
    ):
        """This one bit for real: a component documented where its keyframes
        had moved to, named the tag in the comment, and was counted as an
        injector -- so the scan punished explaining the thing it measures."""
        self._write(
            tmp_path,
            "Documented.jsx",
            "// keyframes moved to index.css; there is no <style> here now\n"
            "/* nor in this <style> block comment */\n"
            "export const X = () => <div />\n",
        )
        assert _style_injectors(tmp_path) == set()

    def test_a_url_in_a_string_does_not_eat_the_line_after_it(self, tmp_path):
        """``//`` inside a string is not a comment. A stripper that thought it
        was would blank the rest of the line -- and a real injection sitting
        there would vanish with it."""
        self._write(
            tmp_path,
            "Mixed.jsx",
            "const u = 'https://fonts.googleapis.com'; "
            "const el = document.createElement('style')\n",
        )
        assert _style_injectors(tmp_path) == {"Mixed.jsx"}

    def test_it_skips_test_files_and_test_helpers(self, tmp_path):
        """Neither ships in the bundle, and ``src/test/keyframeAudit.js`` is a
        static auditor that quotes the tag it hunts for."""
        self._write(tmp_path, "Thing.test.jsx", "<style>{css}</style>")
        self._write(tmp_path, "Thing.test.js", "<style>{css}</style>")
        self._write(tmp_path, "test/helper.js", "<style>{css}</style>")
        assert _style_injectors(tmp_path) == set()

    def test_a_plain_component_is_not_an_injector(self, tmp_path):
        """Non-vacuity for the cases above: the scan must not simply say yes."""
        self._write(
            tmp_path,
            "Plain.jsx",
            "export const P = () => <div style={{ color: 'red' }}>hi</div>",
        )
        assert _style_injectors(tmp_path) == set()
