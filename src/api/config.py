"""Flask application configuration."""

import os
from datetime import timedelta


def combat_socket_streaming_enabled():
    """Read the server-owned combat streaming switch at app creation time."""
    value = os.environ.get("COMBAT_SOCKET_STREAMING", "false")
    return value.lower() not in ("0", "false", "no", "")


class Config:
    """Base configuration."""

    # Flask settings
    _secret_env = os.environ.get("SECRET_KEY")
    if not _secret_env and os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("SECRET_KEY must be set in production")
    SECRET_KEY = _secret_env or os.urandom(24).hex()
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() not in (
        "0",
        "false",
        "no",
    )
    TESTING = False

    # Session settings
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    # CORS settings
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    # API settings
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = True

    # SocketIO settings
    SOCKETIO_CORS_ALLOWED_ORIGINS = CORS_ORIGINS
    SOCKETIO_MESSAGE_QUEUE = None  # Use simple in-memory queue for now

    # Engine-driven combat streaming over SocketIO (issue #436). Off by default:
    # while off, combat resolves via the existing lump-response replay path. When
    # on, the engine streams per-beat events the frontend animates/sounds in
    # lockstep. Feature-flag for the phased rollout (see
    # docs/development/combat-streaming-plan.md).
    COMBAT_SOCKET_STREAMING = False


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""

    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    SESSION_COOKIE_SECURE = True
    CORS_ORIGINS = ["https://nexusfidei.dev"]
    # Keep SocketIO CORS in lockstep with the HTTP CORS origins. The base class
    # binds SOCKETIO_CORS_ALLOWED_ORIGINS to the (localhost) CORS_ORIGINS at
    # class-definition time, so overriding CORS_ORIGINS alone would leave prod
    # sockets stuck on localhost origins and reject the real origin.
    SOCKETIO_CORS_ALLOWED_ORIGINS = CORS_ORIGINS
