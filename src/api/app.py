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
    # For testing and development, create a minimal universe
    # Check by class name to avoid import namespace issues
    config_class_name = config_class.__name__
    is_dev_or_test = config_class_name in ('DevelopmentConfig', 'TestingConfig')
    
    if is_dev_or_test:
        try:
            # Import Player to create a test player for universe initialization
            from src.player import Player
            
            # Create a minimal test player
            test_player = Player()
            test_player.name = "TestPlayer"
            test_player.x = 0  # Set starting position
            test_player.y = 0
            
            # Create universe with test player
            universe = universe_module.Universe(test_player)
            # Build minimal map structure for testing
            if not hasattr(universe, 'maps') or not universe.maps:
                # Create a simple test map with basic tiles
                test_tiles = {
                    (0, 0): type('MockTile', (), {
                        'name': 'Test Starting Room',
                        'description': 'A test room',
                        'x': 0, 'y': 0,
                        'exits': {'north': (0, 1), 'south': (0, -1), 'east': (1, 0), 'west': (-1, 0)},
                        'items_here': [],
                        'npcs_here': [],
                        'objects_here': [],
                        'events_here': []
                    })(),
                    (0, 1): type('MockTile', (), {
                        'name': 'Test Northern Room',
                        'description': 'A room to the north',
                        'x': 0, 'y': 1,
                        'exits': {'north': (0, 2), 'south': (0, 0), 'east': (1, 1), 'west': (-1, 1)},
                        'items_here': [],
                        'npcs_here': [],
                        'objects_here': [],
                        'events_here': []
                    })(),
                    (1, 0): type('MockTile', (), {
                        'name': 'Test Eastern Room',
                        'description': 'A room to the east',
                        'x': 1, 'y': 0,
                        'exits': {'north': (1, 1), 'south': (1, -1), 'east': (2, 0), 'west': (0, 0)},
                        'items_here': [],
                        'npcs_here': [],
                        'objects_here': [],
                        'events_here': []
                    })(),
                    (0, -1): type('MockTile', (), {
                        'name': 'Test Southern Room',
                        'description': 'A room to the south',
                        'x': 0, 'y': -1,
                        'exits': {'north': (0, 0), 'south': (0, -2), 'east': (1, -1), 'west': (-1, -1)},
                        'items_here': [],
                        'npcs_here': [],
                        'objects_here': [],
                        'events_here': []
                    })(),
                    (-1, 0): type('MockTile', (), {
                        'name': 'Test Western Room',
                        'description': 'A room to the west',
                        'x': -1, 'y': 0,
                        'exits': {'north': (-1, 1), 'south': (-1, -1), 'east': (0, 0), 'west': (-2, 0)},
                        'items_here': [],
                        'npcs_here': [],
                        'objects_here': [],
                        'events_here': []
                    })(),
                }
                # Create a simple get_tile method
                def get_tile_method(x, y):
                    return test_tiles.get((x, y))
                
                universe.get_tile = get_tile_method
            
            game_service = GameService(universe)
        except Exception as e:
            # Fallback if test initialization fails
            game_service = None
    else:
        # Production mode - load universe from existing game state if available
        universe = None
        game_service = GameService(universe) if universe else None

    # Store in app context
    app.session_manager = session_manager
    app.game_service = game_service
    app.socketio = socketio

    # Register blueprints
    from src.api.routes import (
        auth_bp,
        world_bp,
        inventory_bp,
        equipment_bp,
        combat_bp,
        player_bp,
        saves_bp,
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(world_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(combat_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(saves_bp)

    # Register error handlers from dedicated module
    from src.api.handlers.error_handler import register_error_handlers

    register_error_handlers(app)

    # Health check endpoint
    @app.route("/health", methods=["GET"])
    def health():
        from flask import jsonify

        return jsonify(
            {
                "status": "healthy",
                "sessions": app.session_manager.get_active_session_count(),
            }
        )

    # API info endpoint
    @app.route("/api/info", methods=["GET"])
    def api_info():
        from flask import jsonify

        return jsonify(
            {
                "version": "1.0.0",
                "name": "Heart of Virtue API",
                "phase": "Phase 1",
                "description": "Flask-based REST API for Heart of Virtue game engine",
            }
        )

    # OpenAPI schema endpoint
    @app.route("/api/openapi.json", methods=["GET"])
    def openapi_schema():
        from flask import jsonify
        from src.api.schemas.openapi import generate_openapi_schema

        return jsonify(generate_openapi_schema())

    # Swagger UI endpoint
    @app.route("/api/docs", methods=["GET"])
    def swagger_ui():
        from src.api.schemas.openapi import generate_swagger_ui_html

        return generate_swagger_ui_html()

    return app, socketio
