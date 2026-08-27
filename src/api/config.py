"""Flask application configuration.

Two rules live here and nowhere else, because both had already drifted between
copies:

* :func:`config_for_env` — the ``FLASK_ENV`` -> config-class mapping. It used
  to be spelled once in ``tools/run_api.py`` and again in ``wsgi.py``, and the
  two disagreed (only run_api.py knew about ``testing``).
* :func:`normalized_env` — how ``FLASK_ENV`` is compared. Both entry points
  lowercased it; :meth:`Config.runtime_config` did not, so
  ``FLASK_ENV=Production`` selected ``ProductionConfig`` *and* skipped the
  "SECRET_KEY must be set in production" guard, minting a fresh
  ``os.urandom(24)`` key per worker. A guard that fails open is worse than no
  guard, so the comparison is now shared.
"""

import os
from datetime import timedelta

# Environment values that mean "off". The empty string is included: an
# exported-but-blank variable is an operator saying nothing, not "on". This
# tuple exists because two copies of it, 87 lines apart, had already diverged
# on precisely that entry — so an empty value was False for one flag and True
# for another.
_FALSEY_ENV_VALUES = ("0", "false", "no", "off", "")


def _env_flag(name, default=False):
    """Read ``name`` as a boolean. Unset falls back to ``default``."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in _FALSEY_ENV_VALUES


def normalized_env(env=None):
    """The comparable form of ``FLASK_ENV`` (stripped, lowercased)."""
    raw = env if env is not None else os.environ.get("FLASK_ENV", "development")
    return (raw or "").strip().lower()


def combat_socket_streaming_enabled():
    """Read the server-owned combat streaming switch.

    Kept as a module-level function (rather than folded into
    :meth:`Config.runtime_config`, its only caller) because it is the
    server-side half of the ``/api/info`` capability contract and reads better
    named at import scope than as one line of an overlay dict.
    """
    return _env_flag("COMBAT_SOCKET_STREAMING", default=False)


class Config:
    """Base configuration.

    The environment-backed settings below are *defaults only*. They are read
    for real by :meth:`runtime_config`, which ``create_app()`` calls — not in
    this class body. A class body runs at **import** time, which for this
    module is before ``tools/run_api.py`` and ``wsgi.py`` have loaded ``.env``,
    so ``SECRET_KEY`` and ``FLASK_ENV`` used to sit in a different, invisible
    tier from ``LOG_LEVEL``, ``CONFIG_FILE`` and the LLM vars: the latter were
    rescued by the later load, the former silently were not.
    """

    # Flask settings
    SECRET_KEY = None  # populated by runtime_config()
    DEBUG = False
    TESTING = False

    # Session settings
    SESSION_COOKIE_SECURE = False  # populated by runtime_config()
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

    @classmethod
    def _pinned_by_subclass(cls, key):
        """True when a subclass (not ``Config`` itself) hard-codes ``key``.

        ``DevelopmentConfig.DEBUG = True`` and ``ProductionConfig.
        SESSION_COOKIE_SECURE = True`` are deliberate choices, not defaults
        waiting to be filled in from the environment — so the runtime read
        below must not overwrite them. Walking the MRO up to (but not
        including) ``Config`` is what "a subclass said so" means here.
        """
        for klass in cls.__mro__:
            if klass is Config:
                return False
            if key in klass.__dict__:
                return True
        return False

    @classmethod
    def runtime_config(cls):
        """Read the environment-backed settings, at ``create_app()`` time.

        Returns a dict to overlay onto ``app.config``. Keys a subclass pins
        explicitly are omitted, so this fills gaps and never wins — the same
        contract as ``load_dotenv(override=False)`` in the entry points.
        """
        production = normalized_env() == "production"
        values = {}

        if not cls._pinned_by_subclass("SECRET_KEY"):
            secret = os.environ.get("SECRET_KEY")
            if not secret and production:
                raise RuntimeError("SECRET_KEY must be set in production")
            # An ephemeral key is fine for dev (it only invalidates cookies on
            # restart) and is refused above for production.
            values["SECRET_KEY"] = secret or os.urandom(24).hex()

        if not cls._pinned_by_subclass("SESSION_COOKIE_SECURE"):
            values["SESSION_COOKIE_SECURE"] = production

        if not cls._pinned_by_subclass("COMBAT_SOCKET_STREAMING"):
            values["COMBAT_SOCKET_STREAMING"] = combat_socket_streaming_enabled()

        # There is deliberately no FLASK_DEBUG branch. Every shipped config
        # class pins DEBUG, so `_pinned_by_subclass` always skipped it and the
        # branch was dead code advertising a knob that did nothing. DEBUG
        # follows the config class, which follows FLASK_ENV.

        return values


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


# FLASK_ENV -> config class. The default is deliberately the *development*
# config: an unset or misspelled value must not silently select production
# behaviour (locked CORS origins, secure-only cookies) on a developer's box.
_CONFIG_BY_ENV = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def config_for_env(env=None):
    """Return the config class for ``env`` (defaults to ``FLASK_ENV``).

    Both process entry points (``tools/run_api.py``, ``wsgi.py``) call this so
    the mapping cannot diverge between them again, and
    :meth:`Config.runtime_config` derives its ``production`` flag from the same
    :func:`normalized_env`, so "which class" and "is this production" can never
    disagree.
    """
    return _CONFIG_BY_ENV.get(normalized_env(env), DevelopmentConfig)
