"""Error handling middleware.

Only 404/405 (raised by Flask's own routing) and 500/generic exceptions
(raised by unhandled errors) are ever reached through Flask's error-handler
dispatch. Every other error status (400/401/403/422/429/503) is produced by
routes and middleware building their own JSON response inline — see
`src/api/middleware/auth.py` for the 401 convention — so no handler is
registered for those; a registered-but-unreachable handler is worse than no
handler, since it invites drift between two response shapes for the same
status code.
"""

from flask import jsonify


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

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server Error."""
        # Log the detail server-side; never leak str(error) to clients.
        import traceback

        traceback.print_exc()
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
        import traceback

        traceback.print_exc()

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
