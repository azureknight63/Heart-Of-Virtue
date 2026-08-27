"""Flask application factory and initialization."""

import configparser
import logging
import logging.handlers
import os
import re
from pathlib import Path
from typing import NamedTuple, Tuple
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from src.api.config import DevelopmentConfig
from src.api.services import SessionManager, GameService
from src.env_bootstrap import PROJECT_ROOT as _REPO_ROOT
import src.universe as universe_module


_log = logging.getLogger(__name__)

# LOG_FILE is confined to this directory. See _resolve_log_file.
_LOG_DIR = _REPO_ROOT / "logs"

# LOG_FILE rotation budget: a DEBUG run must not be able to fill the disk.
_LOG_FILE_MAX_BYTES = 5 * 1024 * 1024
_LOG_FILE_BACKUP_COUNT = 3

# Marker stamped on the handlers this module installs. It is written twice
# (the read in the removal loop, the write in the install loop), so a bare
# literal in both places would silently stack a handler per create_app() the
# day one of them is mistyped.
_HOV_HANDLER_ATTR = "_hov_handler"

# Level names only — getattr(logging, name) would happily resolve any module
# attribute (LOG_LEVEL=BASIC_FORMAT raised at import; NOTSET meant "log
# everything").
_LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

# LOG_LEVEL is applied to these namespaces, never to the root logger. Root at
# DEBUG also turns on urllib3/httpx/openai/werkzeug/engineio wire logging, which
# LOG_FILE then persists at the default umask. Every logger in the project is
# named for its module, so these two prefixes cover all of ours and none of
# anyone else's.
#
# What this scoping does NOT do — stated plainly, because an earlier version of
# this comment read as though it did: ``ai`` is *inside* the selected set, and
# ``ai.llm_client`` logs raw model output at DEBUG (``raw=%r``, several hundred
# characters). So ``LOG_LEVEL=DEBUG`` plus ``LOG_FILE`` still writes player
# conversation text to disk. That is a deliberate developer opt-in (it is the
# only way to debug a dialogue turn), not something this tuple prevents;
# bounding the payload belongs in the LLM client, next to the log call.
_APP_LOG_NAMESPACES = ("src", "ai")

# Blunt scrub for credential-shaped substrings on their way into any handler
# this module installs. Nothing in the tree is known to log a secret in a
# message (checked deliberately: the LLM client logs bool(api_key), never the
# value) — but provider-SDK tracebacks are not written by this tree, and this
# repo has shipped a live GITHUB_TOKEN in ``.env``, so the scrub covers the
# credential families actually present here rather than only the OpenAI shape:
#   sk-…            OpenAI / OpenRouter / Anthropic-style API keys
#   gsk_…           Groq
#   ghp_/gho_/…     GitHub OAuth + classic PATs
#   github_pat_…    GitHub fine-grained PATs
#   discord webhook the provider digest's Discord sink URL (the path IS the
#                   credential)
#   eyJ….….         JWTs, which is how the Turso/libSQL auth token is shaped
#   Bearer …        anything already framed as a bearer credential
_SECRET_RE = re.compile(
    r"""
      sk-[A-Za-z0-9_\-]{8,}
    | gsk_[A-Za-z0-9_\-]{8,}
    | gh[pousr]_[A-Za-z0-9_\-]{8,}
    | github_pat_[A-Za-z0-9_\-]{8,}
    | https://(?:\w+\.)*discord(?:app)?\.com/api/webhooks/\S+
    | eyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]*
    | Bearer\s+[A-Za-z0-9._\-]{8,}
    """,
    re.VERBOSE,
)

# Used to render ``record.exc_info`` for scrubbing before any handler formats
# it. A bare Formatter's ``formatException`` is exactly what the real handlers
# would call, so the text this filter rewrites is the text they will emit.
_EXC_FORMATTER = logging.Formatter()


class _RedactSecretsFilter(logging.Filter):
    """Replace anything credential-shaped with ``[REDACTED]``.

    Installed on **every** handler this module owns, not just the LOG_FILE
    one. Filters run per handler, and the StreamHandler is appended first, so a
    file-handler-only filter emitted the unredacted record to stderr before it
    ever ran.

    Two payloads are scrubbed, because they travel by different routes:

    * ``record.msg`` (with ``record.args`` dropped, as they have already been
      merged in by ``getMessage()``).
    * ``record.exc_text`` — the formatted traceback. This is the one that
      matters most: ``logger.exception`` / ``exc_info=True`` at
      ``auth.py``, ``game_service.py`` and ``world.py`` can surface a
      provider-SDK traceback whose frame locals or request repr carry the API
      key, and that text is rendered by ``Formatter.format`` *after* every
      filter has run. Rendering it here and caching the redacted result in
      ``exc_text`` (which ``Formatter.format`` reuses verbatim when set) is
      what puts it inside the scrub. ``stack_info`` gets the same treatment
      for the same reason.

    Mutating the record makes it scrubbed for every handler that formats it
    afterwards as well — the safe direction to be wrong in.
    """

    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - defensive; bad %-format args
            message = None
        if message is not None and _SECRET_RE.search(message):
            record.msg = _SECRET_RE.sub("[REDACTED]", message)
            record.args = ()
        self._redact_traceback(record)
        return True

    @staticmethod
    def _redact_traceback(record):
        """Scrub (and, if needed, materialise) the record's traceback text."""
        text = getattr(record, "exc_text", None)
        if not text and record.exc_info:
            try:
                text = _EXC_FORMATTER.formatException(record.exc_info)
            except Exception:  # pragma: no cover - defensive
                text = None
        if text:
            record.exc_text = _SECRET_RE.sub("[REDACTED]", text)

        stack = getattr(record, "stack_info", None)
        if stack:
            record.stack_info = _SECRET_RE.sub("[REDACTED]", stack)


def _resolve_log_level(level_name=None):
    """Return the level to apply, or ``None`` for "leave levels alone".

    Distinguishes *unset* from *unrecognized*: an unset LOG_LEVEL means the
    caller's levels are none of this module's business (see the root-level
    note in :func:`_configure_logging`), while ``LOG_LEVEL=TRACE`` is a typo
    in a variable whose entire purpose is "set this to see more" and used to
    produce a silent WARNING-level run with no explanation at all.
    """
    raw = level_name if level_name is not None else os.environ.get("LOG_LEVEL")
    if raw is None:
        return None
    name = str(raw).strip().upper()
    if name in _LOG_LEVELS:
        return _LOG_LEVELS[name]
    # ASCII only: this can be emitted to a cp1252 Windows console before any
    # handler with a safer encoding is attached.
    _log.warning(
        "Unrecognized LOG_LEVEL %r; using WARNING. Accepted values: %s",
        raw,
        ", ".join(_LOG_LEVELS),
    )
    return logging.WARNING


def _resolve_log_file(log_file):
    """Return the confined absolute path LOG_FILE is allowed to write to.

    Raises ValueError when it escapes ``<repo>/logs/``. Unconfined, this path
    reaches ``mkdir(parents=True)`` — which silently creates a directory tree
    anywhere the process can write — and a rotating handler, which *renames*
    ``X`` -> ``X.1`` -> ``X.2`` and so clobbers up to three neighbouring names
    beside whatever it was pointed at. A relative value is interpreted inside
    the log directory rather than against the working directory.
    """
    candidate = Path(log_file).expanduser()
    if not candidate.is_absolute():
        candidate = _LOG_DIR / candidate
    resolved = candidate.resolve()
    log_dir = _LOG_DIR.resolve()
    if resolved == log_dir or log_dir not in resolved.parents:
        raise ValueError("LOG_FILE must resolve to a path under %s" % log_dir)
    return resolved


def _configure_logging(level_name=None):
    """Configure application logging from environment variables.

    Called from create_app() rather than at import time: installing handlers
    on the root logger is not something importing this module should do to
    the host process.

    Args:
        level_name: an explicit level that overrides LOG_LEVEL. ``create_app``
            passes ``"WARNING"`` for a TESTING config *when LOG_LEVEL is
            actually set*, because ``.env`` reaches pytest through
            ``src/api/db.py``'s import-time ``load_project_env()`` — so a
            developer's ``LOG_LEVEL=DEBUG`` used to put the *whole test suite*
            at DEBUG from the second create_app() call onward, paying
            formatting and stderr writes for every ``logger.debug`` in the
            engine. ``None`` means "restore the namespaces to inheriting",
            which is what makes that pin reversible (see the level block at
            the end of this function).

    Supported env vars:
      LOG_LEVEL   - Python log level name, e.g. DEBUG, INFO, WARNING. Applied
                    to the ``src`` and ``ai`` logger namespaces only. Unset
                    means "leave the levels inherited", which leaves Python's
                    WARNING root default in place.
      LOG_FILE    - Optional file path under ``<repo>/logs/`` to also write
                    logs to (rotated per ``_LOG_FILE_MAX_BYTES`` /
                    ``_LOG_FILE_BACKUP_COUNT``, so DEBUG runs cannot grow
                    without bound).
    """
    level = _resolve_log_level(level_name)

    handlers = [logging.StreamHandler()]
    log_file = os.environ.get("LOG_FILE")
    if log_file:
        try:
            path = _resolve_log_file(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(
                logging.handlers.RotatingFileHandler(
                    path,
                    encoding="utf-8",
                    maxBytes=_LOG_FILE_MAX_BYTES,
                    backupCount=_LOG_FILE_BACKUP_COUNT,
                )
            )
        except Exception as exc:
            # Fail safe to stream-only rather than refuse to boot over a
            # logging destination.
            _log.warning("Could not attach LOG_FILE handler %s: %s", log_file, exc)

    # Replace only the handlers a previous call installed. basicConfig(
    # force=True) did the idempotence job but removes *and closes* every root
    # handler, including ones this process does not own: under pytest that is
    # caplog's, so any test building an app lost its log capture from that
    # point on and every later "nothing was logged" assertion passed
    # vacuously. Tagging our own handlers keeps repeated create_app() calls
    # from stacking duplicates without touching anyone else's.
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    redactor = _RedactSecretsFilter()
    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, _HOV_HANDLER_ATTR, False):
            root.removeHandler(existing)
            existing.close()
    for handler in handlers:
        setattr(handler, _HOV_HANDLER_ATTR, True)
        handler.setFormatter(formatter)
        handler.addFilter(redactor)
        root.addHandler(handler)

    # The ROOT logger's level is deliberately never touched. Setting it was
    # the same trespass the handler tagging above exists to avoid, one field
    # over: `caplog.at_level(INFO)` around a create_app() had every INFO
    # record dropped, which is the vacuous-pass failure again. Python's root
    # default is already WARNING, so scoping the level to our own namespaces
    # gives verbose app logs without dragging in third-party wire logging.
    #
    # NOTSET (not "skip the write") is what `level is None` means here, and
    # that matters twice over. It restores inheritance, so a bare
    # `caplog.set_level(INFO)` — which raises the *root* level only — actually
    # reaches app records instead of being silently outranked by an explicit
    # namespace level: the same vacuous-pass shape as above, one field over
    # again. And it makes the TESTING pin reversible: without it, one
    # `create_app(TestingConfig)` left `src`/`ai` at WARNING for the rest of
    # the process, and a later non-TESTING create_app() took the
    # "change nothing" path and never gave them back.
    resolved = logging.NOTSET if level is None else level
    for namespace in _APP_LOG_NAMESPACES:
        logging.getLogger(namespace).setLevel(resolved)


def _apply_proxy_fix(app):
    """Wrap the WSGI app with Werkzeug's ProxyFix when trusted proxies exist.

    Issue #409. **Off by default** (0 trusted hops): with no trusting,
    ``request.remote_addr`` keeps reflecting the direct peer, so an untrusted
    client cannot spoof ``X-Forwarded-For`` to forge the per-IP login
    rate-limit key. Set ``TRUSTED_PROXY_COUNT`` (Flask config or environment)
    to the number of trusted reverse-proxy hops in front of the app — e.g. 1
    for a single platform proxy — so ProxyFix rewrites ``remote_addr`` from the
    corresponding ``X-Forwarded-For`` entry and the rate limiter buckets by the
    real client again.

    Returns True if ProxyFix was installed, False otherwise.
    """
    raw = app.config.get(
        "TRUSTED_PROXY_COUNT", os.environ.get("TRUSTED_PROXY_COUNT", 0)
    )
    try:
        count = int(raw)
    except (TypeError, ValueError):
        count = 0

    if count <= 0:
        return False

    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=count, x_proto=count, x_host=count, x_port=count
    )
    return True


def _apply_runtime_config(app, config_class):
    """Overlay the environment-backed settings Config reads at runtime.

    ``config_class`` is not required to be a :class:`~src.api.config.Config`
    subclass — several tests pass a bare stand-in class — so this is a
    duck-typed call, not an assumption.
    """
    runtime_config = getattr(config_class, "runtime_config", None)
    if callable(runtime_config):
        app.config.update(runtime_config())


def _init_socketio(app):
    """Build the SocketIO server and bind it to the app.

    Honors the dedicated SocketIO config keys (issue #436):
    SOCKETIO_CORS_ALLOWED_ORIGINS falls back to the HTTP CORS origins, and
    SOCKETIO_MESSAGE_QUEUE (e.g. a Redis URL) fans emits out across workers
    when set — None keeps the single-process in-memory queue.
    """
    socketio = SocketIO(
        app,
        cors_allowed_origins=app.config.get(
            "SOCKETIO_CORS_ALLOWED_ORIGINS", app.config["CORS_ORIGINS"]
        ),
        message_queue=app.config.get("SOCKETIO_MESSAGE_QUEUE"),
        async_mode="threading",
        logger=app.debug,
        engineio_logger=app.debug,
    )
    app.socketio = socketio
    return socketio


class StartConfig(NamedTuple):
    """The starting state ``CONFIG_FILE`` can override, as a typed record.

    This used to be a bare 6-key dict indexed by string literal in
    :func:`_build_dev_universe`, with neither function naming the keys — so a
    typo was a ``KeyError`` raised deep inside universe construction and
    swallowed whole by :func:`_init_universe`'s ``except``, leaving a
    universe-less service and one log line about "initialization failed".
    """

    start_x: int = 2
    start_y: int = 2
    starting_exp: int = 0
    starting_map_name: str = "default"
    starting_gold: int = 0
    starting_equipment: Tuple[str, ...] = ()


def _load_start_config() -> StartConfig:
    """Read starting position/map/exp/gold/equipment from CONFIG_FILE.

    Returns a :class:`StartConfig`; the defaults come back unchanged when
    CONFIG_FILE is unset, missing, or unreadable.
    """
    start = {}
    config_file = os.environ.get("CONFIG_FILE")
    if not config_file:
        return StartConfig()

    try:
        # Remove quotes if present (from .env file)
        config_file = config_file.strip("'\"")
        config_path = Path(config_file)

        # If relative path, make it relative to project root
        if not config_path.is_absolute():
            config_path = _REPO_ROOT / config_file

        if config_path.exists():
            parser = configparser.ConfigParser()
            parser.read(config_path)

            if parser.has_option("game", "startposition"):
                pos_str = parser.get("game", "startposition")
                # Strip parentheses and whitespace
                pos_str = pos_str.strip("() ")
                coords = [int(x.strip()) for x in pos_str.split(",")]
                if len(coords) == 2:
                    start["start_x"], start["start_y"] = coords

            if parser.has_option("game", "starting_exp"):
                start["starting_exp"] = parser.getint("game", "starting_exp")

            if parser.has_option("game", "startmap"):
                start["starting_map_name"] = parser.get("game", "startmap")

            if parser.has_option("game", "starting_gold"):
                start["starting_gold"] = parser.getint("game", "starting_gold")

            if parser.has_option("game", "starting_equipment"):
                eq_str = parser.get("game", "starting_equipment")
                start["starting_equipment"] = tuple(
                    item.strip() for item in eq_str.split(",") if item.strip()
                )
    except Exception as exc:
        # Whatever was parsed before the failure is kept; the rest falls back
        # to the StartConfig defaults. Unchanged from the dict version.
        _log.warning("Could not load config: %s", exc)

    return StartConfig(**start)


def _apply_starting_equipment(test_player, starting_equipment):
    """Create, add and auto-equip each ``Item[:enchantment]`` spec."""
    import src.items as items

    for eq_spec in starting_equipment:
        item_class_name, enchantment_level_str = (
            eq_spec.split(":") if ":" in eq_spec else (eq_spec, "0")
        )
        item_class_name = item_class_name.strip()
        try:
            enchantment_level = int(enchantment_level_str.strip())
        except ValueError:
            enchantment_level = 0

        # Get the item class from the items module
        if not hasattr(items, item_class_name):
            continue
        item_class = getattr(items, item_class_name)
        # Create item with enchantment_level
        item = item_class(enchantment_level=enchantment_level)
        test_player.inventory.append(item)
        # Auto-equip armor/weapons for convenience
        if hasattr(item, "isequipped"):
            item.isequipped = True
            if "unequip" not in item.interactions:
                item.interactions.append("unequip")
            if "equip" in item.interactions:
                item.interactions.remove("equip")
            # Special handling for weapons
            if hasattr(item, "maintype") and item.maintype == "Weapon":
                test_player.eq_weapon = item

    # Refresh stat bonuses after equipping all items
    import src.functions as functions

    functions.refresh_stat_bonuses(test_player)


def _make_get_tile(universe):
    """Build the ``get_tile(x, y)`` accessor the API layer expects.

    Named factory rather than a closure defined inline in
    :func:`_build_dev_universe`, because the only thing that ever calls the
    result reaches it as ``universe.get_tile`` — an attribute the Universe
    class does not declare — and a closure assigned onto an instance from
    inside a builder is not greppable from the call site.

    Lookups are confined to the player's *current* map: coordinates repeat
    across maps, so searching all of them would silently return a tile from
    somewhere the player is not.
    """

    def get_tile_from_maps(x, y):
        """Retrieve a tile from the player's current map by coordinates."""
        if not hasattr(universe, "player") or not universe.player:
            return None

        player_map = universe.player.map
        if not player_map:
            return None

        if (x, y) in player_map:
            return player_map[(x, y)]

        return None

    return get_tile_from_maps


def _build_dev_universe(start: StartConfig):
    """Build the real game universe around a throwaway "Jean" player.

    Dev/test only — production loads its universe from saved game state. The
    ``start`` record comes from :func:`_load_start_config`.
    """
    # Import Player to create a test player for universe initialization
    from src.player import Player
    import src.items as items

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
            if map_item.get("name") == start.starting_map_name
        ),
        universe.starting_map_default,
    )

    # Set player to starting map and position from config
    test_player.map = starting_map
    test_player.location_x = start.start_x
    test_player.location_y = start.start_y

    # Apply starting exp (for both leveling and skill learning)
    if start.starting_exp > 0:
        # Set experience for leveling system
        test_player.exp = start.starting_exp
        # Trigger level-ups if needed (without prompts since we're in API mode)
        while test_player.exp >= test_player.exp_to_level:
            test_player._level_up_api()
        # Set experience for skill tree learning
        for category in test_player.skilltree.subtypes.keys():
            test_player.skill_exp[category] = start.starting_exp

    # Apply starting gold
    if start.starting_gold > 0:
        test_player.inventory.append(items.Gold(start.starting_gold))

    if start.starting_equipment:
        _apply_starting_equipment(test_player, start.starting_equipment)

    # Add get_tile method to universe for API layer
    universe.get_tile = _make_get_tile(universe)
    return universe


def _init_universe(config_class, start: StartConfig):
    """Return ``(universe, game_service)`` for this config class.

    The dev/test branch is selected by class *name* rather than identity, to
    avoid import-namespace issues where two copies of the config module would
    make an ``is`` comparison fail.
    """
    is_dev_or_test = config_class.__name__ in ("DevelopmentConfig", "TestingConfig")
    if not is_dev_or_test:
        # Production mode - load universe from existing game state if available
        return None, GameService()

    try:
        return _build_dev_universe(start), GameService()
    except Exception:
        # Fall back to a universe-less service if initialization fails.
        # Logged with a traceback rather than printed: this is one of the two
        # most consequential startup failures in the file, and print() +
        # traceback.print_exc() bypass the LOG_FILE handler entirely.
        _log.exception("Universe initialization failed")
        return None, GameService()


def _register_blueprints(app):
    """Register every API blueprint under its URL prefix, plus error handlers."""
    from src.api.routes import (
        auth_bp,
        world_bp,
        inventory_bp,
        combat_bp,
        player_bp,
        saves_bp,
        logs_bp,
        feedback_bp,
        shop_bp,
    )
    from src.api.routes.npc_chat import npc_chat_bp

    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(world_bp, url_prefix="/api")
    app.register_blueprint(inventory_bp, url_prefix="/api")
    app.register_blueprint(combat_bp, url_prefix="/api/combat")
    app.register_blueprint(player_bp, url_prefix="/api")
    app.register_blueprint(saves_bp, url_prefix="/api")
    app.register_blueprint(npc_chat_bp, url_prefix="/api/npc/chat")
    app.register_blueprint(logs_bp, url_prefix="/api/logs")
    app.register_blueprint(feedback_bp, url_prefix="/api/feedback")
    app.register_blueprint(shop_bp, url_prefix="/api/shop")

    # Register error handlers from dedicated module
    from src.api.handlers.error_handler import register_error_handlers

    register_error_handlers(app)


def _register_preflight(app):
    """Install the global before_request CORS-preflight handler."""

    @app.before_request
    def handle_preflight():
        """Handle CORS preflight OPTIONS requests globally."""
        from flask import make_response, request

        if request.method == "OPTIONS":
            response = make_response()
            # Only echo the Origin if it's in the configured allowlist —
            # otherwise the preflight would undermine the CORS restriction
            # (esp. ProductionConfig, which locks origins to nexusfidei.dev).
            allowed = app.config.get("CORS_ORIGINS", [])
            origin = request.headers.get("Origin")
            if origin and origin in allowed:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = (
                    "GET, POST, PUT, DELETE, OPTIONS, PATCH"
                )
                response.headers["Access-Control-Allow-Headers"] = (
                    "Content-Type, Authorization"
                )
                response.headers["Access-Control-Max-Age"] = "3600"
            return response, 200


def _register_meta_routes(app):
    """Health and API info — the two unauthenticated public endpoints."""

    @app.route("/health", methods=["GET"])
    def health():
        from flask import jsonify

        payload = {"status": "healthy"}
        # The live session gauge is operational telemetry, and this route has
        # no auth at all: on a public deployment it is an occupancy oracle for
        # a single-player game — anyone can poll "is the developer online?" and
        # watch the count move. It is genuinely useful locally, so it is kept
        # for the non-production configs (which is every config the tests and
        # the bug-hunt harness build) and dropped for production. A monitor
        # that needs the number in production should read it from an
        # authenticated route rather than reopening this one.
        if app.config.get("TESTING") or app.config.get("DEBUG"):
            payload["sessions"] = app.session_manager.get_active_session_count()
        return jsonify(payload)

    # API info endpoint.
    #
    # This is also the runtime capability-discovery endpoint (#436/#496): the
    # frontend's CapabilitiesProvider fetches it once at startup and reads
    # `features.combat_socket_streaming` to decide whether combat animation
    # is driven by the Socket.IO beat stream or by the HTTP-only fallback.
    # A dedicated `/api/capabilities` route was considered and rejected for
    # now — it would grow the public API surface for a single boolean, with
    # no other capability planned. Revisit if `features` grows past a couple
    # of keys, or gains metadata/versioning needs that shouldn't share a
    # payload with the general info fields above it.
    @app.route("/api/info", methods=["GET"])
    def api_info():
        from flask import jsonify

        return jsonify(
            {
                "version": "1.0.0",
                "name": "Heart of Virtue API",
                "phase": "Phase 1",
                "description": "Flask-based REST API for Heart of Virtue game engine",
                "features": {
                    "combat_socket_streaming": bool(
                        app.config.get("COMBAT_SOCKET_STREAMING", False)
                    )
                },
            }
        )


def _register_test_routes(app):
    """Test-only endpoints — these bypass database auth entirely.

    Only called when TESTING=True, so they are never reachable in production.
    """
    # Combat-testing / debug endpoints (replaces TheAdjutant's terminal menu).
    from src.api.routes.debug import debug_bp

    app.register_blueprint(debug_bp, url_prefix="/api/debug")

    @app.route("/api/debug/routes", methods=["GET"])
    def list_routes():
        """Dump the URL map. Registered here rather than always-on with an
        in-body 404, so that "test-only endpoint" has exactly one mechanism in
        this file instead of two. Unregistered, it 404s through the normal
        error handler with the same ``success: False`` shape.
        """
        from flask import jsonify

        routes = []
        for rule in app.url_map.iter_rules():
            routes.append(
                {
                    "endpoint": rule.endpoint,
                    "methods": sorted(list(rule.methods - {"HEAD", "OPTIONS"})),
                    "rule": str(rule),
                }
            )
        return jsonify({"routes": sorted(routes, key=lambda x: x["rule"])})

    @app.route("/api/test/session", methods=["POST"])
    def test_create_session():
        from flask import jsonify, request as _req

        username = (_req.get_json() or {}).get("username", "inquisitor_test")
        session_id, _ = app.session_manager.create_session(username)
        return (
            jsonify({"session_id": session_id, "username": username}),
            201,
        )

    @app.route("/api/test/heal", methods=["POST"])
    def test_heal_player():
        """Restore player to full HP and fatigue. Test mode only — never active in production."""
        from flask import jsonify
        from src.api.middleware.auth import get_session_and_player

        session_manager, session, player, error = get_session_and_player()
        if error:
            return error
        try:
            player.hp = player.maxhp
            player.fatigue = player.maxfatigue
            return (
                jsonify({"success": True, "hp": player.hp, "maxhp": player.maxhp}),
                200,
            )
        except Exception as exc:
            return jsonify({"success": False, "error": str(exc)}), 500


def _testing_log_level(config_class):
    """The level a TESTING config should pin, or ``None`` to leave levels alone.

    The pin exists for exactly one scenario: ``.env`` reaches pytest (through
    ``src/api/db.py``'s import-time ``load_project_env()``), so a developer's
    ``LOG_LEVEL=DEBUG`` used to put the whole suite at DEBUG. When LOG_LEVEL is
    *not* set there is nothing to neutralise, and pinning anyway would set an
    explicit level on ``src``/``ai`` that outranks a plain
    ``caplog.set_level(INFO)`` — which raises only the root level — and make
    every app record invisible to it.
    """
    if not getattr(config_class, "TESTING", False):
        return None
    if os.environ.get("LOG_LEVEL") is None:
        return None
    return "WARNING"


def create_app(config_class=None):
    """Create and configure Flask application.

    Args:
        config_class: Configuration class to use (defaults to DevelopmentConfig)

    Returns:
        ``(app, socketio)`` — every caller unpacks both.
    """
    if config_class is None:
        config_class = DevelopmentConfig

    # Logging is configured *after* the config class is known so a TESTING
    # config can pin the level — see _configure_logging's docstring.
    _configure_logging(_testing_log_level(config_class))

    app = Flask(__name__)
    app.config.from_object(config_class)
    # Every env-backed *app.config value* is read here and only here, because
    # runtime_config() is the one place that knows which of them a subclass has
    # already pinned. (_apply_proxy_fix below reads TRUSTED_PROXY_COUNT itself:
    # it wires WSGI middleware rather than setting a config value, and it
    # consults app.config first so a config class can still override it.)
    _apply_runtime_config(app, config_class)

    # Honor a reverse proxy's X-Forwarded-* headers so request.remote_addr (and
    # thus the login rate-limit key) reflects the real client. Off by default —
    # see _apply_proxy_fix (issue #409).
    _apply_proxy_fix(app)

    # Initialize CORS - with explicit support for all methods
    CORS(
        app,
        origins=app.config["CORS_ORIGINS"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["Content-Type", "Authorization"],
        supports_credentials=True,
    )

    socketio = _init_socketio(app)

    # Read unconditionally, as before: only the dev/test universe consumes the
    # values, but a malformed CONFIG_FILE must be reported whatever config is
    # in use.
    universe, game_service = _init_universe(config_class, _load_start_config())

    # Store in app context (`app.socketio` is set by _init_socketio).
    app.session_manager = SessionManager(universe=universe)
    app.game_service = game_service

    _register_blueprints(app)

    # Register WebSocket handlers
    from src.api.sockets import register_socket_handlers

    register_socket_handlers(socketio)

    _register_preflight(app)
    _register_meta_routes(app)
    if app.config.get("TESTING"):
        _register_test_routes(app)

    return app, socketio
