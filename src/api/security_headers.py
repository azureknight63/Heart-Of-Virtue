"""Security response headers for the Flask app: the CSPs, the static set, HSTS.

This module owns every security response header this app sets, and has exactly
one edge into the app factory: ``create_app`` calls
:func:`register_security_headers`. Nothing here imports from ``src.api.app``,
so ``tests/test_security_headers.py`` reaches these constants without building
a universe.

Two policies, because there are two kinds of response
-----------------------------------------------------
The CSP rollout below (issue #492) is a policy for a *document*: it governs
what the SPA may load, it is shared with the Vite dev server and the
production static host, and it starts report-only so nothing breaks while we
learn what it needs.

This Flask app serves no documents. There is no ``templates/``, no ``static/``,
no ``render_template`` / ``send_file`` / ``send_from_directory`` call anywhere
under ``src/``, and no catch-all SPA route; every registered endpoint returns
``jsonify()``. The only HTML it can emit is Werkzeug's -- routing redirects and
HTTPException bodies. So a JSON response gets :data:`_API_CSP` instead: the
strictest policy the grammar allows, enforcing rather than report-only,
because with nothing to render there is none of the blank-page risk that gets a
CSP deleted. ``default-src 'none'`` only ever binds the case it is meant to
stop -- a browser induced to *navigate* at an API URL and render the body --
and fetch/XHR/EventSource/WebSocket responses are not documents and ignore the
header entirely, so the SPA is unaffected.

A response opts into the document policy by name, through
:func:`serves_html_document`, rather than by being sniffed for
``mimetype == "text/html"``. Sniffing reads the wrong way round here: since
this app authors no HTML, every ``text/html`` response it emits today is
Werkzeug's, so branching on content type handed the permissive policy to
exactly the responses nobody designed -- the error paths an attacker reaches
without credentials -- while the strict one covered the routes we control.
``_register_preflight``'s bare ``make_response()`` was a third such case:
Flask's default content type is ``text/html``, so an empty preflight body
looked like a document too. Inverted, forgetting to declare a real document
yields a visibly blank page in development; the sniffing version's failure was
a policy that silently stopped applying.

Nothing below touches the ``Access-Control-*`` headers that flask_cors and
``src.api.app._register_preflight`` negotiate, and nothing below contradicts
that allow-list: CSP constrains what a *document* may load, CORS constrains who
may read a *response*, and the two never describe the same thing.

Why a response header and not a ``<meta>`` tag
----------------------------------------------
A ``<meta http-equiv="Content-Security-Policy-Report-Only">`` element is
**ignored by browsers** — the CSP spec allows only the enforcing header name in
markup, and Chrome/Firefox additionally log a console error when a report-only
policy arrives that way. Since the rollout starts in report-only mode (no
player-visible breakage while we learn what the real policy needs), a meta tag
is not an option today; the policy has to be a response header.

Where the header actually lands
-------------------------------
Three surfaces serve bytes to a browser, and each needs the header from its own
server:

* **The Flask API** — this module. Covers every ``/api/*`` response and any HTML
  Werkzeug renders (error pages), and is the home the policy moves to wholesale
  if Flask ever serves the SPA itself.
* **The Vite dev server** — ``frontend/vite.config.js`` (``server.headers`` /
  ``preview.headers``). This is what carries the policy on the *document* during
  development and QA runs, which is where violations are actually observed.
* **Production static hosting** — the built SPA is untarred into the web
  server's document root by ``deploy.ps1``; that server is not configured from
  this repo. ``docs/development/csp-rollout.md`` carries the snippet to add
  there.

All three read the same directive data from ``src/resources/csp-policy.json`` so
the dev and production policies cannot silently diverge.

Why only ``report-uri``, and not the newer ``report-to``
-------------------------------------------------------
The obvious move is to advertise both transports, since ``report-uri`` is
deprecated and browser support is split. Measured in headless Chromium against
this app, that combination delivers **nothing**: ``report-to`` takes precedence
over ``report-uri`` whenever both are present, and Chromium's Reporting API then
queues the report rather than POSTing it (delivery is batched, and a plain-HTTP
origin is not an eligible endpoint at all). A three-way A/B over one forced
violation — ``report-uri`` alone, ``report-to`` alone, both — produced 1, 0 and 0
report POSTs respectively.

A report-only rollout whose reports never arrive is worse than no rollout: it
reads as "zero violations" and nothing is learned. So the policy ships
``report-uri`` alone, which is also the only transport Firefox and Safari
implement. Re-adding ``report-to`` is a follow-up in
docs/development/csp-rollout.md, gated on re-running that A/B over HTTPS.
"""

import json
import os
from pathlib import Path

# Directive data shared with frontend/vite.config.js. Loaded once at import.
POLICY_PATH = (
    Path(__file__).resolve().parent.parent / "resources" / "csp-policy.json"
)

ENFORCING_HEADER = "Content-Security-Policy"
REPORT_ONLY_HEADER = "Content-Security-Policy-Report-Only"

# The policy for every response this app actually produces today. Enforced, not
# report-only: see the module docstring for why a non-document can carry the
# strictest policy in the grammar at no risk. ``sandbox`` with no tokens drops
# such a response, if a browser is ever induced to render one, into an opaque
# origin with no scripts, no forms and no top-level navigation.
_API_CSP = (
    "default-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "sandbox"
)

# Headers with no policy trade-off to weigh, and so no knob to offer.
#
#   X-Content-Type-Options  The precondition for most "navigate straight at an
#       API endpoint" attacks is a browser deciding a JSON body is really HTML.
#       nosniff removes it, and this app has no legitimate sniffing to lose.
#
#   Referrer-Policy  A deliberate pick, not a default. ``no-referrer`` was the
#       alternative and would also have been defensible -- the API never
#       initiates a navigation, so it has nothing to lose by sending nothing.
#       ``strict-origin-when-cross-origin`` wins on two counts: it is the value
#       the SPA's host will also set, so the two halves of the product state one
#       policy rather than two, and it keeps the full URL on same-origin
#       requests, which is what any debugging or log correlation on the API host
#       wants. The residual cross-origin leak is the bare origin, and this API
#       keeps no credential in a URL.
#
# Both enforce immediately, unlike the report-only document CSP, so for the
# whole rollout window they are the only active protection on a document.
_STATIC_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# X-Frame-Options travels with :data:`_API_CSP` and only with it, so the two
# cannot disagree. It duplicates that policy's ``frame-ancestors 'none'`` on
# purpose: frame-ancestors supersedes it in modern browsers, and this is what
# the ones that ignore CSP still honour. DENY rather than SAMEORIGIN because the
# SPA is a different origin and frames nothing.
#
# Deliberately NOT set on a declared document. The shared policy in
# ``csp-policy.json`` says ``frame-ancestors 'self'``; pairing that with a blunt
# DENY would ship a header pair that contradicts itself, with which one wins
# depending on the browser. If the document policy ever tightens to 'none', move
# this into the static set above.
_FRAME_OPTIONS_HEADER = "X-Frame-Options"
_FRAME_OPTIONS_VALUE = "DENY"

# Strict-Transport-Security, production only.
#
# It is not in the static set because it is the one header here with a
# precondition: a browser ignores HSTS over plaintext, but a host that is *not*
# reachable over TLS and sends it anyway has locked its own clients out of it
# for a year. So it is gated on ``SESSION_COOKIE_SECURE``, which is the flag by
# which this app already says "I believe I am behind TLS" -- pinned True by
# ProductionConfig and by ``runtime_config()`` for a production ``FLASK_ENV``.
#
# One year, no ``includeSubDomains``, no ``preload``: the API is one host among
# whatever else the operator runs under the same parent domain, and asserting
# TLS on siblings this app knows nothing about is not its call to make.
_HSTS_HEADER = "Strict-Transport-Security"
_HSTS_VALUE = "max-age=31536000"

# Marks a response as a real SPA document, so it gets the shared document policy
# instead of :data:`_API_CSP`. Opt-in -- see the module docstring.
_HTML_DOCUMENT_FLAG = "_hov_html_document"


def serves_html_document(response):
    """Mark ``response`` as an HTML document, so it gets the document policy.

    For whatever eventually serves ``frontend/dist`` from this app -- a
    ``send_from_directory`` catch-all, or an SPA fallback route. Returns the
    response, so it can wrap a return value in place.
    """
    setattr(response, _HTML_DOCUMENT_FLAG, True)
    return response


def _renders_as_html(response):
    """True when this response has been marked as a document to render."""
    return bool(getattr(response, _HTML_DOCUMENT_FLAG, False))


def load_policy(path=None):
    """Read the shared directive data.

    Returns a ``{"base": {...}, "dev_additions": {...}}`` mapping. Keys starting
    with an underscore (the in-file rationale comment) are dropped.
    """
    with open(path or POLICY_PATH, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def build_csp(dev=False, report_uri=None, policy=None):
    """Compose the policy string.

    Args:
        dev: Apply the development relaxations (the Vite dev server injects an
            inline React-Refresh preamble that no build step can hash). Never
            true for the production policy.
        report_uri: Where violations are POSTed, as a ``report-uri`` directive.
            Deliberately not paired with ``report-to`` — see the module
            docstring for the measurement that ruled that out.
        policy: Pre-loaded directive data, for tests. Defaults to the shared
            JSON file.

    Returns:
        The policy as a single ``;``-joined header value.
    """
    data = policy if policy is not None else load_policy()
    directives = {name: list(values) for name, values in data["base"].items()}

    if dev:
        for name, extra in data.get("dev_additions", {}).items():
            merged = directives.setdefault(name, [])
            # Preserve source order and skip anything the base already allows;
            # a duplicated source is legal CSP but noise in a header humans read.
            merged.extend(value for value in extra if value not in merged)

    parts = [f"{name} {' '.join(values)}" for name, values in directives.items()]

    if report_uri:
        parts.append(f"report-uri {report_uri}")

    return "; ".join(parts)


def _flag(app, key, default):
    """Read a boolean switch from Flask config, then environment, then default."""
    value = app.config.get(key, os.environ.get(key))
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("0", "false", "no", "")


def register_security_headers(app):
    """Install the single ``after_request`` hook that sets security headers.

    The document CSP is report-only by default: ``CSP_REPORT_ONLY=false``
    (config or environment) flips it to enforcing. See
    docs/development/csp-rollout.md for the checklist that gates that flip.
    :data:`_API_CSP` is not part of that rollout and is always enforced -- it
    governs responses that are not documents, where there is nothing to break.

    Every header is written with ``setdefault``, so a reverse proxy or a route
    that has already made a deliberate choice keeps it, and repeated
    registration cannot stack or fight.

    Covers Flask responses only. flask_socketio wraps ``app.wsgi_app``, so the
    ``/socket.io/*`` handshake and polling responses are served beneath this
    hook and carry none of these headers. Harmless -- they are not documents
    and nothing frames them -- but the coverage is not total, and anything that
    needs to be true of *every* response on the port has to be set at the
    reverse proxy instead.

    Returns True when the hook was installed, False when ``CSP_ENABLED`` is off.
    """
    if not _flag(app, "CSP_ENABLED", True):
        return False

    report_only = _flag(app, "CSP_REPORT_ONLY", True)
    dev = _flag(app, "CSP_DEV_RELAXATIONS", bool(app.config.get("TESTING")))
    report_uri = app.config.get(
        "CSP_REPORT_URI", os.environ.get("CSP_REPORT_URI", "/api/logs/csp-report")
    )
    # Composed once at registration, not per request: load_policy() opens a file.
    document_header = REPORT_ONLY_HEADER if report_only else ENFORCING_HEADER
    document_policy = build_csp(dev=dev, report_uri=report_uri)

    @app.after_request
    def set_security_headers(response):
        for header, value in _STATIC_SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault(_HSTS_HEADER, _HSTS_VALUE)

        # Don't clobber a policy a nearer layer already chose (e.g. a route that
        # deliberately relaxes it) — set only when absent. Checked against BOTH
        # header names: a route that set the enforcing one must not then also
        # receive the report-only one, and vice versa.
        already_set = (
            ENFORCING_HEADER in response.headers
            or REPORT_ONLY_HEADER in response.headers
        )
        if _renders_as_html(response):
            if not already_set:
                response.headers[document_header] = document_policy
        else:
            response.headers.setdefault(_FRAME_OPTIONS_HEADER, _FRAME_OPTIONS_VALUE)
            if not already_set:
                response.headers[ENFORCING_HEADER] = _API_CSP
        return response

    return True
