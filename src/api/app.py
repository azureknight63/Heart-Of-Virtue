"""Flask application factory and initialization."""

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from src.api.config import Config, DevelopmentConfig, TestingConfig, ProductionConfig
from src.api.services import SessionManager, GameService
import src.universe as universe_module


def create_app(config_class=None):
    """Create and configure Flask application.

    Args:
        config_class: Configuration class to use (defaults to DevelopmentConfig)

    Returns:
        Configured Flask app instance
    """
    if config_class is None:
        config_class = DevelopmentConfig

    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize CORS
    CORS(app, origins=app.config["CORS_ORIGINS"])

    # Initialize SocketIO for real-time updates
    socketio = SocketIO(
        app,
        cors_allowed_origins=app.config["SOCKETIO_CORS_ALLOWED_ORIGINS"],
        async_mode="threading",
    )

    # Initialize session manager
    session_manager = SessionManager()

    # Initialize game universe and service
    # TODO: Load universe from existing game
    universe = None  # Will be initialized when loading game state
    game_service = GameService(universe) if universe else None

    # Store in app context
    app.session_manager = session_manager
    app.game_service = game_service
    app.socketio = socketio

    # Register blueprints (will be created in routes/)
    # from src.api.routes import auth_bp, world_bp, inventory_bp, combat_bp, player_bp, saves_bp
    # app.register_blueprint(auth_bp)
    # app.register_blueprint(world_bp)
    # app.register_blueprint(inventory_bp)
    # app.register_blueprint(combat_bp)
    # app.register_blueprint(player_bp)
    # app.register_blueprint(saves_bp)

    # Register error handlers
    register_error_handlers(app)

    # Health check endpoint
    @app.route("/health", methods=["GET"])
    def health():
        return {
            "status": "healthy",
            "sessions": app.session_manager.get_active_session_count(),
        }

    # API info endpoint
    @app.route("/api/info", methods=["GET"])
    def api_info():
        return {
            "version": "1.0.0",
            "name": "Heart of Virtue API",
            "phase": "Phase 1",
            "description": "Flask-based REST API for Heart of Virtue game engine",
        }

    return app, socketio


def register_error_handlers(app):
    """Register global error handlers.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(400)
    def bad_request(error):
        return {"error": "Bad request", "message": str(error)}, 400

    @app.errorhandler(401)
    def unauthorized(error):
        return {"error": "Unauthorized", "message": "Invalid session"}, 401

    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Not found", "message": "Endpoint not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        return {"error": "Internal server error", "message": str(error)}, 500
