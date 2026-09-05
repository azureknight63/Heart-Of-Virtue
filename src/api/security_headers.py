"""Security response headers: the CSPs, the static header set, and the hook.

Extracted from ``src/api/app.py``, where this reasoning was 230 lines of an
1100-line factory with exactly one edge back into it: ``create_app`` calls
:func:`_register_security_headers`. Nothing else in that module referenced any
name here, and ``tests/test_security_headers.py`` was paying the whole
app-factory import -- universe build included -- to reach three constants.

The header *values* are judgement calls about this app's shape rather than a
hardening checklist, so the reasoning travels with them; it starts below.
"""

# --------------------------------------------------------------------------
# Security response headers
# --------------------------------------------------------------------------
#
# The reasoning is written out here rather than filed in a doc, because every
# value below is a judgement about *this* app's shape, and the shape is unusual
# enough that the obvious policy is the wrong one.
#
# This Flask app serves no HTML. There is no ``templates/`` directory, no
# ``static/`` directory, no ``render_template`` / ``send_file`` /
# ``send_from_directory`` call anywhere under ``src/``, and no catch-all SPA
# route; every registered endpoint returns ``jsonify()``. The React frontend is
# a separate artefact on a separate origin -- Vite serves it from :3000 in
# development (proxying ``/api`` here, which is why ``CORS_ORIGINS`` exists at
# all), and ``deploy.ps1`` unpacks ``frontend/dist`` into a *different*
# container's document root in production while this app runs as its own
# systemd service. Two consequences follow, and they pull in opposite
# directions:
#
#   * These headers can never reach the SPA document, so the CSP that backstops
#     React's escaping of model-authored NPC dialogue is not something this file
#     can ship. It has to be issued by whatever serves ``index.html``.
#     :data:`_HTML_CSP` records the policy that document actually needs, so the
#     requirement is written down in the repo and is applied automatically the
#     day anything here does serve HTML.
#   * Because nothing here renders, the API's own CSP can be the strictest one
#     the grammar allows, with none of the blank-page risk that gets a CSP
#     deleted. :data:`_API_CSP` takes that option.
#
# Nothing below touches the ``Access-Control-*`` headers that flask_cors and
# ``src.api.app._register_preflight`` negotiate, and nothing below contradicts
# that allow-list: CSP constrains what a *document* may load, CORS constrains
# who may read a *response*, and the two never describe the same thing. In
# particular ``default-src 'none'`` does not affect the SPA's cross-origin
# ``fetch``, because a CSP binds the document it was served with and a fetched
# JSON body never becomes a document.

# The policy for every response this app actually produces today.
#
# ``default-src 'none'`` is safe precisely because it only ever binds the case
# it is meant to stop: a browser induced to *navigate* to an API URL and render
# the body (the classic route from a reflected value in an error payload to
# script execution). XHR / fetch / EventSource / WebSocket responses are not
# documents and ignore this header entirely, so the SPA is unaffected.
# ``sandbox`` with no tokens drops such a document into an opaque origin with no
# scripts, no forms and no top-level navigation -- belt to the braces.
_API_CSP = (
    "default-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "sandbox"
)

# The policy for HTML -- unreachable from this app today (nothing calls
# :func:`serves_html_document`), and deliberately kept anyway: it is the
# specification the SPA's host must mirror, and it is what a future
# ``send_from_directory`` of ``frontend/dist`` would need on day one. Derived
# from what the frontend measurably does, not from a hardening checklist:
#
#   script-src 'self'  No inline <script>, no eval, no ``new Function``, no
#       Worker and no blob: URL exists in ``frontend/src`` or ``index.html``
#       (grepped: zero hits) -- index.html loads one module by src. So the
#       directive that actually stops XSS stays strict, with no escape hatch.
#
#   style-src 'unsafe-inline'  A measured cost, not a necessity. Three
#       components render a literal <style> element (GameOverScreen:61,
#       HeroPanel:241, ToastContext:172) plus
#       InteractPanel:768, which builds one via
#       ``document.createElement('style')`` -- all of them for ``@keyframes``.
#       Those four are the whole of what forces the concession today, and the
#       count is falling: TypewriterOutput's ``blink``, NpcChatPanel's
#       spinner keyframes and ItemDetailDialog's ``fadeIn`` have already been
#       lifted into
#       ``frontend/src/styles/index.css``, because keyframe names are
#       document-global and a component-local block silently competes with
#       every other definition of the same name. The same move would work for
#       the remaining four, and if it is made this token should go with them.
#       There is no nonce to offer them meanwhile: a statically hosted, cached
#       index.html has no per-response value to mint. The ~1000 ``style={{}}``
#       props are the weaker argument (React applies those through the CSSOM,
#       which CSP does not police) but they are why a strict style policy would
#       be one refactor away from a blank screen anyway. The concession is
#       bounded: inline *style* cannot execute script, and the one place
#       untrusted model text reaches the DOM as markup (CombatLog's
#       ``dangerouslySetInnerHTML``) is already sanitised by DOMPurify -- CSP is
#       the second line there, not the first. It is still an escape hatch
#       written into a policy this file bills as the spec the SPA's host must
#       mirror, so it is worth removing rather than inheriting.
#
#   fonts.googleapis.com / fonts.gstatic.com  index.html links a Google Fonts
#       stylesheet, which in turn pulls its faces from the gstatic host. Both
#       are needed or the game loses its typography.
#
#   img-src / media-src data:  Vite inlines assets under its 4 KB threshold as
#       data: URIs at build time.
#
#   connect-src 'self'  Correct for the case this constant governs: HTML served
#       *from here* is same-origin with this API, and CSP3's 'self' already
#       covers the ws:/wss: upgrade Socket.IO performs against the same host. A
#       host serving the SPA on a *different* origin from the API (today's
#       production split, and any build setting VITE_API_URL) must append that
#       API origin here.
_HTML_CSP = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "object-src 'none'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "media-src 'self' data:; "
    "connect-src 'self'"
)

# Headers with no policy trade-off to weigh, and so no knob to offer.
#
#   X-Content-Type-Options  The precondition for most "navigate straight at an
#       API endpoint" attacks is a browser deciding a JSON body is really HTML.
#       nosniff removes it, and this app has no legitimate sniffing to lose.
#
#   X-Frame-Options  Nothing here is meant to be framed. This duplicates the
#       CSPs' ``frame-ancestors 'none'`` on purpose: frame-ancestors supersedes
#       it in modern browsers, and X-Frame-Options is what the ones that ignore
#       CSP still honour. DENY rather than SAMEORIGIN because the SPA is a
#       different origin and frames nothing.
#
#   Referrer-Policy  A deliberate pick, not a default. ``no-referrer`` was the
#       alternative and would also have been defensible -- the API never
#       initiates a navigation, so it has nothing to lose by sending nothing.
#       ``strict-origin-when-cross-origin`` wins on two counts: it is the value
#       the SPA's host will also set, so the two halves of the product state one
#       policy rather than two, and it keeps the full URL on same-origin
#       requests, which is what any debugging or log correlation on the API host
#       wants. The residual cross-origin leak is the bare origin, and this API
#       keeps no credential in a URL -- the session id travels in the
#       Authorization header, by the convention in ``src/api/middleware/auth.py``.
_STATIC_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# Strict-Transport-Security, production only.
#
# It is not in the set above because it is the one header here with a
# precondition: a browser ignores HSTS over plaintext, but a host that is *not*
# reachable over TLS and sends it anyway has locked its own clients out of it
# for a year. So it is gated on ``SESSION_COOKIE_SECURE``, which is the flag by
# which this app already says "I believe I am behind TLS" -- pinned True by
# ProductionConfig and by ``runtime_config()`` for a production ``FLASK_ENV``.
#
# It matters more here than the cookie flag it rides on. The session id does
# not travel in a cookie at all: ``src/api/middleware/auth.py`` reads it from
# ``Authorization: Bearer``, which ``SESSION_COOKIE_SECURE`` does nothing to
# protect. One ``http://`` request -- a typed URL, an old bookmark, a redirect
# -- hands that credential to the network in clear text. HSTS is what stops the
# request being made at all.
#
# One year, no ``includeSubDomains``, no ``preload``: the API is one host among
# whatever else the operator runs under the same parent domain, and asserting
# TLS on siblings this app knows nothing about is not its call to make.
_HSTS_HEADER = "Strict-Transport-Security"
_HSTS_VALUE = "max-age=31536000"


# Marks a response as a real SPA document. Opt-in, and deliberately so.
#
# Sniffing ``mimetype == "text/html"`` reads the wrong way round. This app
# authors no HTML, so every ``text/html`` response it emits today is written by
# *Werkzeug*, not by us: routing redirects, and HTTPExceptions that reach the
# WSGI layer with their default HTML bodies. Branching on the content type
# therefore handed the permissive policy to exactly the responses nobody
# designed -- the error paths an attacker reaches without credentials -- while
# the strict one covered the routes we control. ``_register_preflight``'s bare
# ``make_response()`` is a third case: Flask's default content type is
# ``text/html``, so an empty preflight body looked like a document too.
#
# Inverted, the default is :data:`_API_CSP` and a view that genuinely serves
# ``index.html`` asks for :data:`_HTML_CSP` by name. Forgetting to ask yields a
# visibly blank page in development, which is the file's stated safe direction
# to be wrong in; the sniffing version's failure was a policy that silently
# stopped applying.
_HTML_DOCUMENT_FLAG = "_hov_html_document"


def serves_html_document(response):
    """Mark ``response`` as an HTML document, so it gets :data:`_HTML_CSP`.

    For whatever eventually serves ``frontend/dist`` from this app -- a
    ``send_from_directory`` catch-all, or an SPA fallback route. Returns the
    response, so it can wrap a return value in place.
    """
    setattr(response, _HTML_DOCUMENT_FLAG, True)
    return response


def _renders_as_html(response):
    """True when this response has been marked as a document to render."""
    return bool(getattr(response, _HTML_DOCUMENT_FLAG, False))


def _register_security_headers(app):
    """Install the single ``after_request`` hook that sets security headers.

    Every header is written with ``setdefault``, so a reverse proxy or a route
    that has already made a deliberate choice keeps it, and repeated
    registration cannot stack or fight.

    Covers Flask responses only. flask_socketio wraps ``app.wsgi_app``, so the
    ``/socket.io/*`` handshake and polling responses are served beneath this
    hook and carry none of these headers. Harmless -- they are not documents
    and nothing frames them -- but the coverage is not total, and anything
    that needs to be true of *every* response on the port has to be set at the
    reverse proxy instead.
    """

    @app.after_request
    def set_security_headers(response):
        for header, value in _STATIC_SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault(_HSTS_HEADER, _HSTS_VALUE)
        response.headers.setdefault(
            "Content-Security-Policy",
            _HTML_CSP if _renders_as_html(response) else _API_CSP,
        )
        return response
