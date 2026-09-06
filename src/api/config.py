"""Flask application configuration.

Two rules live here and nowhere else, because both had already drifted between
copies:

* :func:`config_for_env` — the ``FLASK_ENV`` -> config-class mapping. It used
  to be spelled once in ``tools/run_api.py`` and again in ``wsgi.py``, and the
  two disagreed (only run_api.py knew about ``testing``; wsgi.py sent every
  non-production value to ``DevelopmentConfig``). Note which half of that
  disagreement was the safe one: unifying the mapping taught the *production*
  entry point to honour ``FLASK_ENV=testing``, which registers
  ``/api/test/session`` and ``/api/debug/*``. Sharing the mapping is still
  right; the refusal that used to be an accident of the duplication is now
  explicit in ``wsgi.py``, next to the reason.
* :func:`normalized_env` — how ``FLASK_ENV`` is compared. Both entry points
  lowercased it; :meth:`Config.runtime_config` did not, so
  ``FLASK_ENV=Production`` selected ``ProductionConfig`` *and* skipped the
  "SECRET_KEY must be set in production" guard, minting a fresh
  ``os.urandom(24)`` key per worker. A guard that fails open is worse than no
  guard, so the comparison is now shared.
"""

import logging
import os
from datetime import timedelta
from typing import Any, Dict, Optional, Type

_log = logging.getLogger(__name__)

# Environment values that mean "off". The empty string is included: an
# exported-but-blank variable is an operator saying nothing, not "on". This
# tuple exists because there used to be two copies of the list, and they had
# already diverged on precisely that entry — so an empty value was False for
# the COMBAT_SOCKET_STREAMING read and True for the FLASK_DEBUG one. ``"off"``
# is in neither of those copies: it is added here because a single shared list
# should accept the spellings an operator actually writes, rather than the
# union of two accidents.
_FALSEY_ENV_VALUES = ("0", "false", "no", "off", "")


def _env_flag(name: str, default: bool = False) -> bool:
    """Read ``name`` as a boolean. Unset falls back to ``default``."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in _FALSEY_ENV_VALUES


def normalized_env(env: Optional[str] = None) -> str:
    """The comparable form of ``FLASK_ENV`` (stripped, lowercased)."""
    raw = env if env is not None else os.environ.get("FLASK_ENV", "development")
    return (raw or "").strip().lower()


def combat_socket_streaming_enabled() -> bool:
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

    # Largest request body this API accepts, in bytes. Werkzeug refuses to read
    # past it, so an oversized body is never buffered into the (single-worker)
    # process; ``src/api/app.py::_register_request_limits`` turns that refusal
    # into this API's own 413 before any route's ``except Exception`` can
    # relabel it a 500.
    #
    # 1 MiB is set against the largest body a *legitimate* client sends, which
    # is a browser-log batch: ``frontend/src/utils/logger.js`` caps its queue at
    # MAX_QUEUE_SIZE = 100 entries, and ``routes/logs.py`` keeps at most
    # MAX_MESSAGE_LENGTH (4000) + MAX_FIELD_LENGTH (2048) + two short fields of
    # each one — roughly 0.64 MB of content the server would actually retain,
    # so this leaves headroom without accepting a batch whose bulk would be
    # discarded on arrival anyway. Every other endpoint is orders of magnitude
    # smaller: a cloud save posts a *name* (the save document is built
    # server-side), feedback is bounded at MAX_TITLE_LENGTH + a handful of
    # MAX_FIELD_LENGTH fields, and an npc-chat turn is capped at 4000
    # characters.
    #
    # Not environment-backed on purpose: the two endpoints that can be reached
    # with no session at all (``POST /api/logs/browser``,
    # ``POST /api/auth/register``) are the ones this bounds, so it is a floor
    # under the deployment rather than a knob to tune per host — and an
    # operator-typed value is one more thing that can be typed as "unlimited".
    MAX_CONTENT_LENGTH = 1024 * 1024

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
    def _pinned_by_subclass(cls, key: str) -> bool:
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
    def runtime_config(cls) -> Dict[str, Any]:
        """Read the environment-backed settings, at ``create_app()`` time.

        Returns a dict to overlay onto ``app.config``. Keys a subclass pins
        explicitly are omitted, so this fills gaps and never wins — the same
        contract as ``load_dotenv(override=False)`` in the entry points.

        The production guards below fire if EITHER ``FLASK_ENV`` says
        production or ``cls`` is the class that ``FLASK_ENV=production``
        selects, so passing the class directly is as guarded as setting the
        variable.
        """
        # "Is this production" has TWO independent sources -- the ambient
        # ``FLASK_ENV`` and the config class actually in force -- and only one
        # of them was being asked. ``runtime_config`` is a classmethod that
        # ignored ``cls`` for the single decision that matters.
        #
        # Both shipped entry points reach here through :func:`config_for_env`,
        # so for them the two agree by construction. But ``config_class`` is a
        # documented parameter of ``create_app``, and
        # ``create_app(ProductionConfig)`` with ``FLASK_ENV`` unset took the
        # development path through this method: no "SECRET_KEY must be set"
        # guard, and a fresh ``os.urandom(24)`` key minted per worker. The
        # cookie half escaped only by accident -- ``ProductionConfig`` pins
        # ``SESSION_COOKIE_SECURE``, so ``_pinned_by_subclass`` skips it.
        #
        # Derived from the env->class map rather than naming ``ProductionConfig``
        # here, so "which class is production" stays spelled in exactly one
        # place -- the same drift that once split the mapping between the two
        # entry points.
        production = normalized_env() == "production" or issubclass(
            cls, _CONFIG_BY_ENV["production"]
        )
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
# A *misspelled* value is loud about it, though — see config_for_env.
_CONFIG_BY_ENV = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def config_for_env(env: Optional[str] = None) -> Type[Config]:
    """Return the config class for ``env`` (defaults to ``FLASK_ENV``).

    Both process entry points (``tools/run_api.py``, ``wsgi.py``) call this so
    the mapping cannot diverge between them again, and
    :meth:`Config.runtime_config` asks BOTH this mapping and
    :func:`normalized_env`, so "which class" and "is this production" cannot
    disagree however the class was chosen.

    That last clause used to rest on convention rather than on code: the flag
    came from :func:`normalized_env` alone, which made the claim true for these
    two callers and false for ``create_app(ProductionConfig)`` -- a supported
    call that skipped every production guard. See :meth:`Config.runtime_config`.

    Unset and unrecognised are *not* the same thing, exactly as they are not
    for ``LOG_LEVEL`` in ``src/api/app.py::_resolve_log_level``. Unset means
    the operator said nothing and development is the right silent answer.
    ``FLASK_ENV=prod`` means the operator said "production" and got
    ``DEBUG=True``, ``SESSION_COOKIE_SECURE=False``, a fresh ``os.urandom(24)``
    SECRET_KEY per worker, and localhost CORS origins — because *both*
    production guards (``runtime_config``'s SECRET_KEY check and
    ``AuthService``'s ENCRYPTION_KEY check) test ``normalized_env() ==
    "production"``, so a near-miss skips them all with nothing said. Warning
    rather than raising keeps a typo from taking a running deployment down,
    but it does not let it pass in silence.
    """
    name = normalized_env(env)
    config = _CONFIG_BY_ENV.get(name)
    if config is not None:
        return config
    if name:
        _log.warning(
            "Unrecognized FLASK_ENV %r; using DevelopmentConfig "
            "(DEBUG on, insecure cookies, production guards skipped). "
            "Accepted values: %s",
            name,
            ", ".join(_CONFIG_BY_ENV),
        )
    return DevelopmentConfig
