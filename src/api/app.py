"""Flask application factory and initialization."""

import os
import configparser
from pathlib import Path
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from src.api.config import DevelopmentConfig
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

    # Initialize CORS - with explicit support for all methods
    CORS(
        app,
        origins=app.config["CORS_ORIGINS"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["Content-Type", "Authorization"],
        supports_credentials=True,
    )

    # Initialize SocketIO for real-time updates
    socketio = SocketIO(
        app,
        cors_allowed_origins=app.config["CORS_ORIGINS"],
        async_mode="eventlet",
        logger=app.debug,
        engineio_logger=app.debug,
    )
    app.socketio = socketio

    # Load starting position and map from config file
    start_x, start_y = 2, 2  # defaults
    starting_exp = 0
    starting_map_name = "default"
    config_file = os.environ.get("CONFIG_FILE")

    if config_file:
        try:
            # Remove quotes if present (from .env file)
            config_file = config_file.strip("'\"")
            config_path = Path(config_file)

            # If relative path, make it relative to project root
            if not config_path.is_absolute():
                config_path = (
                    Path(__file__).resolve().parent.parent.parent / config_file
                )

            if config_path.exists():
                parser = configparser.ConfigParser()
                parser.read(config_path)

                if parser.has_option("game", "startposition"):
                    pos_str = parser.get("game", "startposition")
                    # Strip parentheses and whitespace
                    pos_str = pos_str.strip("() ")
                    coords = [int(x.strip()) for x in pos_str.split(",")]
                    if len(coords) == 2:
                        start_x, start_y = coords

                if parser.has_option("game", "starting_exp"):
                    starting_exp = parser.getint("game", "starting_exp")

                if parser.has_option("game", "startmap"):
                    starting_map_name = parser.get("game", "startmap")
        except Exception as e:
            print(f"Warning: Could not load config: {e}")

    # Initialize game universe and service first
    # For testing and development, load real game universe
    # Check by class name to avoid import namespace issues
    config_class_name = config_class.__name__
    is_dev_or_test = config_class_name in (
        "DevelopmentConfig",
        "TestingConfig",
    )

    universe = None
    game_service = None

    if is_dev_or_test:
        try:
            # Import Player to create a test player for universe initialization
            from src.player import Player

            # Create a test player
            test_player = Player()
            test_player.name = "Jean"

            # Create universe with test player
            universe = universe_module.Universe(test_player)

            # Build universe with real maps from JSON files
            universe.build(test_player)

            # Set universe reference on player
            test_player.universe = universe

            # Find the starting map by name
            starting_map = next(
                (
                    map_item
                    for map_item in universe.maps
                    if map_item.get("name") == starting_map_name
                ),
                universe.starting_map_default,
            )

            # Set player to starting map and position from config
            test_player.map = starting_map
            test_player.location_x, test_player.location_y = start_x, start_y

            # Apply starting exp
            if starting_exp > 0:
                for category in test_player.skilltree.subtypes.keys():
                    test_player.skill_exp[category] = starting_exp

            # Create a get_tile wrapper for accessing tiles from the player's current map only
            def get_tile_from_maps(x, y):
                """Retrieve a tile from the player's current map by coordinates."""
                if not hasattr(universe, "player") or not universe.player:
                    return None

                player_map = universe.player.map
                if not player_map:
                    return None

                # Only search in the player's current map
                if (x, y) in player_map:
                    return player_map[(x, y)]

                return None

            # Add get_tile method to universe for API layer
            universe.get_tile = get_tile_from_maps

            game_service = GameService()
        except Exception as e:
            # Fallback if universe initialization fails
            import traceback

            print(f"Warning: Universe initialization failed: {e}")
            traceback.print_exc()
            game_service = GameService()
    else:
        # Production mode - load universe from existing game state if available
        universe = None
        game_service = GameService()

    # Initialize session manager (now with universe reference if available)
    session_manager = SessionManager(universe=universe)

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
        npc_bp,
        quest_rewards_bp,
        reputation_bp,
        quest_chains_bp,
        npc_availability_bp,
        dialogue_context_bp,
        logs_bp,
        feedback_bp,
    )

    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(world_bp, url_prefix="/api")
    app.register_blueprint(inventory_bp, url_prefix="/api")
    app.register_blueprint(equipment_bp, url_prefix="/api")
    app.register_blueprint(combat_bp, url_prefix="/api/combat")
    app.register_blueprint(player_bp, url_prefix="/api")
    app.register_blueprint(saves_bp, url_prefix="/api")
    app.register_blueprint(npc_bp, url_prefix="/api/npc")
    app.register_blueprint(quest_rewards_bp, url_prefix="/api/quests")
    app.register_blueprint(reputation_bp, url_prefix="/api/reputation")
    app.register_blueprint(quest_chains_bp, url_prefix="/api/quest-chains")
    app.register_blueprint(npc_availability_bp, url_prefix="/api")
    app.register_blueprint(dialogue_context_bp, url_prefix="/api")
    app.register_blueprint(logs_bp, url_prefix="/api/logs")
    app.register_blueprint(feedback_bp, url_prefix="/api/feedback")

    # Register error handlers from dedicated module
    from src.api.handlers.error_handler import register_error_handlers

    register_error_handlers(app)

    # Register WebSocket handlers
    from src.api.sockets import register_socket_handlers

    register_socket_handlers(socketio)

    # Global before_request handler for CORS preflight
    @app.before_request
    def handle_preflight():
        """Handle CORS preflight OPTIONS requests globally."""
        from flask import make_response, request

        if request.method == "OPTIONS":
            response = make_response()
            response.headers["Access-Control-Allow-Origin"] = (
                request.headers.get("Origin", "http://localhost:3000")
            )
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization"
            )
            response.headers["Access-Control-Max-Age"] = "3600"
            return response, 200

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

    # Test-only session endpoint — bypasses database auth entirely.
    # Only registered when TESTING=True so it is never reachable in production.
    if app.config.get("TESTING"):

        @app.route("/api/test/session", methods=["POST"])
        def test_create_session():
            from flask import jsonify, request as _req

            username = (_req.get_json() or {}).get(
                "username", "inquisitor_test"
            )
            session_id, _ = app.session_manager.create_session(username)
            return (
                jsonify({"session_id": session_id, "username": username}),
                201,
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

    # Debug: List all routes
    @app.route("/api/debug/routes", methods=["GET"])
    def list_routes():
        from flask import jsonify

        routes = []
        for rule in app.url_map.iter_rules():
            routes.append(
                {
                    "endpoint": rule.endpoint,
                    "methods": sorted(
                        list(rule.methods - {"HEAD", "OPTIONS"})
                    ),
                    "rule": str(rule),
                }
            )
        return jsonify({"routes": sorted(routes, key=lambda x: x["rule"])})

    return app, socketio
