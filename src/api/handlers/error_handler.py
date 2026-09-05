"""Error handling middleware.

Only 404/405 (raised by Flask's own routing), 413 (raised by Werkzeug when a
body exceeds ``MAX_CONTENT_LENGTH``) and 500/generic exceptions (raised by
unhandled errors) are ever reached through Flask's error-handler dispatch.
Every other error status (400/401/403/422/429/503) is produced by routes and
middleware building their own JSON response inline — see
`src/api/middleware/auth.py` for the 401 convention — so no handler is
registered for those; a registered-but-unreachable handler is worse than no
handler, since it invites drift between two response shapes for the same
status code.

The 413 handler is the *second* half of the body bound, not the first: a
declared ``Content-Length`` over the cap is refused by
``src/api/app.py::_register_request_limits`` before the view runs, because a
``RequestEntityTooLarge`` raised inside a view is caught by that view's own
``except Exception`` and reported as a 500. This handler covers what that hook
cannot see — a chunked body, whose size is unknown until it is read — and only
where the reading route lets the exception escape.
"""

import logging

from flask import jsonify

# The 500 and unhandled-exception handlers below are the app's highest-volume
# traceback source. They used to call ``traceback.print_exc()``, which writes
# straight to stderr and never touches the logging pipeline — so
# ``src/api/app.py``'s ``_RedactSecretsFilter``, installed on every handler
# this app owns precisely to keep credentials out of emitted tracebacks, never
# saw a single one of them. ``logger.exception`` routes the same detail
# through that filter, and into LOG_FILE with it.
logger = logging.getLogger(__name__)


def _request_label():
    """``METHOD /path`` for the current request, or ``"<no request>"``.

    ``traceback.print_exc()`` gave the traceback and nothing else, so a 500 in
    the log could not be tied to the call that produced it. Method and path
    only, deliberately: a query string or a request body can carry a token,
    and there is no reason to hand one to the redactor to catch when it need
    never be logged in the first place.
    """
    try:
        from flask import request

        return "%s %s" % (request.method, request.path)
    except Exception:  # pragma: no cover - outside a request context
        return "<no request>"


def register_error_handlers(app):
    """Register global error handlers for the Flask app.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 Not Found errors."""
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Not found",
                    "message": "The requested resource was not found",
                }
            ),
            404,
        )

    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 Method Not Allowed errors."""
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Method not allowed",
                    "message": str(error),
                }
            ),
            405,
        )

    @app.errorhandler(413)
    def payload_too_large(error):
        """Handle 413 Payload Too Large (see this module's docstring)."""
        return (
            jsonify(
                {
                    "success": False,
                    "error": "payload_too_large",
                    "message": "Request body is too large.",
                }
            ),
            413,
        )

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server Error."""
        # Log the detail server-side; never leak str(error) to clients.
        logger.exception("Unhandled 500 error serving %s", _request_label())
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                }
            ),
            500,
        )

    # Handle all other HTTP exceptions
    @app.errorhandler(Exception)
    def generic_error(error):
        """Handle any unhandled exceptions."""
        logger.exception("Unhandled exception serving %s", _request_label())

        return (
            jsonify(
                {
                    "success": False,
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                }
            ),
            500,
        )
