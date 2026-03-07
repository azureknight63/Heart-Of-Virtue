"""Error handling middleware."""

from flask import jsonify


def register_error_handlers(app):
    """Register global error handlers for the Flask app.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(400)
    def bad_request(error):
        """Handle 400 Bad Request errors."""
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Bad request",
                    "message": str(error),
                }
            ),
            400,
        )

    @app.errorhandler(401)
    def unauthorized(error):
        """Handle 401 Unauthorized errors."""
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Unauthorized",
                    "message": "Invalid or missing session",
                }
            ),
            401,
        )

    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 Forbidden errors."""
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Forbidden",
                    "message": "You do not have permission to access this resource",
                }
            ),
            403,
        )

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

    @app.errorhandler(422)
    def unprocessable_entity(error):
        """Handle 422 Unprocessable Entity errors."""
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Unprocessable entity",
                    "message": "The request could not be processed",
                }
            ),
            422,
        )

    @app.errorhandler(429)
    def too_many_requests(error):
        """Handle 429 Too Many Requests errors."""
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Too many requests",
                    "message": "Rate limit exceeded. Please try again later.",
                }
            ),
            429,
        )

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server Error."""
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Internal server error",
                    "message": str(error),
                }
            ),
            500,
        )

    @app.errorhandler(503)
    def service_unavailable(error):
        """Handle 503 Service Unavailable errors."""
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Service unavailable",
                    "message": "The service is temporarily unavailable",
                }
            ),
            503,
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
