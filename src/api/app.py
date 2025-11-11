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

    # Initialize game universe and service first
    # For testing and development, load real game universe
    # Check by class name to avoid import namespace issues
    config_class_name = config_class.__name__
    is_dev_or_test = config_class_name in ('DevelopmentConfig', 'TestingConfig')
    
    universe = None
    game_service = None
    
    if is_dev_or_test:
        try:
            # Import Player to create a test player for universe initialization
            from src.player import Player
            
            # Create a test player
            test_player = Player()
            test_player.name = "TestPlayer"
            
            # Create universe with test player
            universe = universe_module.Universe(test_player)
            
            # Build universe with real maps from JSON files
            universe.build(test_player)
            
            # Set player to starting position (first tile of first map)
            if universe.maps and len(universe.maps) > 0:
                map_data = universe.maps[0]
                tiles = [k for k in map_data if isinstance(k, tuple)]
                if tiles:
                    start_pos = tiles[0]
                    test_player.x, test_player.y = start_pos
            
            # Create a get_tile wrapper for accessing tiles from the universe.maps structure
            def get_tile_from_maps(x, y):
                """Retrieve a tile from the loaded maps by coordinates."""
                if not hasattr(universe, 'maps') or not universe.maps:
                    return None
                
                # Maps is a list of dictionaries, each dict has 'name' and tile coordinate keys
                for map_dict in universe.maps:
                    if (x, y) in map_dict:
                        return map_dict[(x, y)]
                
                return None
            
            # Add get_tile method to universe for API layer
            universe.get_tile = get_tile_from_maps
            
            game_service = GameService(universe)
        except Exception as e:
            # Fallback if universe initialization fails
            import traceback
            print(f"Warning: Universe initialization failed: {e}")
            traceback.print_exc()
            game_service = None
    else:
        # Production mode - load universe from existing game state if available
        universe = None
        game_service = GameService(universe) if universe else None

    # Initialize session manager (now with universe reference if available)
    session_manager = SessionManager(universe=universe)

    # Store in app context
    app.session_manager = session_manager
    app.game_service = game_service
    app.socketio = socketio
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
        npc_bp,
        quest_rewards_bp,
        reputation_bp,
        quest_chains_bp,
        npc_availability_bp,
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(world_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(combat_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(saves_bp)
    app.register_blueprint(npc_bp)
    app.register_blueprint(quest_rewards_bp)
    app.register_blueprint(reputation_bp)
    app.register_blueprint(quest_chains_bp)
    app.register_blueprint(npc_availability_bp)

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
