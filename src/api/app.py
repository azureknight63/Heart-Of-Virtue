"""Flask application factory and initialization."""

import configparser
import logging
import logging.handlers
import os
import re
from pathlib import Path
from typing import NamedTuple, Tuple
from flask import Flask, jsonify
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

# Read for two different questions ~700 lines apart — "what level?" in
# _resolve_log_level and "is there anything to neutralise?" in
# _testing_log_level — so both go through _log_level_setting() below rather
# than through two literals that can drift apart.
_LOG_LEVEL_ENV = "LOG_LEVEL"

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
# What this scoping does NOT do: ``ai`` is *inside* the selected set, and
# ``ai.llm_client`` logs raw model output at DEBUG. So ``LOG_LEVEL=DEBUG`` plus
# ``LOG_FILE`` does write player conversation text to disk, and no choice of
# namespaces here would stop it.
#
# What bounds that payload lives in the LLM client, next to the log call, which
# is the only place that knows what the string is: ``_RAW_LOG_HEAD_CHARS`` in
# ``ai/llm_client.py`` caps the logged excerpt at an 80-character head by
# default, and the full body is behind ``LLM_LOG_RAW_BODIES`` — a separate
# switch on purpose, so that raising the log level to chase an unrelated bug
# cannot start transcribing dialogue as a side effect. Provider *error* bodies
# follow the same rule: bounded by ``_ERROR_BODY_LOG_CHARS`` and released in
# full by the same ``LLM_LOG_RAW_BODIES`` switch, because a provider that
# echoes the rejected request back is echoing the player's dialogue back.
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

    The ``exc_text`` cache is written only when the scrub actually changed
    something. That reuse cuts both ways: a non-empty ``exc_text`` freezes the
    traceback for *every* handler on root, so writing it unconditionally would
    take ``formatException`` away from handlers that render it differently —
    caplog's today, and the JSON formatter in ``src/api/structured_log.py``
    once this branch catches up with master.

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
            redacted = _SECRET_RE.sub("[REDACTED]", text)
            if redacted != text:
                record.exc_text = redacted

        # ``stack_info`` is appended verbatim by every formatter rather than
        # cached, so an unconditional write costs nothing and hides nothing.
        stack = getattr(record, "stack_info", None)
        if stack:
            record.stack_info = _SECRET_RE.sub("[REDACTED]", stack)


def _log_level_setting():
    """The configured LOG_LEVEL, or ``None`` when it is not configured.

    Blank counts as unconfigured. ``LOG_LEVEL=`` in a ``.env`` reads as "no
    opinion", and the test suite relies on that: ``.env`` ships
    ``LOG_LEVEL=DEBUG``, and every ``load_project_env()`` in the tree
    (``db.py``, ``rate_limiter.py``, ``ai/llm_client.py``) runs with
    ``override=False``, which refills a *deleted* key but leaves an assigned
    empty one alone. Blanking is therefore the only way ``tests/conftest.py``
    can say "unset" and have it stick.
    """
    raw = os.environ.get(_LOG_LEVEL_ENV)
    if raw is None or not str(raw).strip():
        return None
    return raw


def _resolve_log_level(level_name=None):
    """Return the level to apply, or ``None`` for "leave levels alone".

    Distinguishes *unset* from *unrecognized*: an unset LOG_LEVEL means the
    caller's levels are none of this module's business (see the root-level
    note in :func:`_configure_logging`), while ``LOG_LEVEL=TRACE`` is a typo
    in a variable whose entire purpose is "set this to see more" and used to
    produce a silent WARNING-level run with no explanation at all.
    """
    raw = level_name if level_name is not None else _log_level_setting()
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
    # `caplog.set_level(INFO)` — which raises the *root* level only — reaches
    # app records instead of being silently outranked by an explicit namespace
    # level: the same vacuous-pass shape as above, one field over again. And it
    # makes the TESTING pin reversible: without it, one
    # `create_app(TestingConfig)` left `src`/`ai` at WARNING for the rest of
    # the process, and a later non-TESTING create_app() took the
    # "change nothing" path and never gave them back.
    #
    # The caplog half only holds while the suite actually reaches this branch,
    # which is why `tests/conftest.py` blanks LOG_LEVEL rather than pinning it
    # to WARNING: a pinned value sends every pytest run down the explicit-level
    # path instead, and the claim above becomes untestable by the suite that
    # depends on it.
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

    A record rather than a dict because the consumer is
    :func:`_build_dev_universe`, whose own failures are swallowed by
    :func:`_init_universe`'s ``except``: a missing key there surfaces only as a
    universe-less service and one log line about "initialization failed". Field
    access fails at the name instead.
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
    defaults = StartConfig()
    config_file = os.environ.get("CONFIG_FILE")
    if not config_file:
        return defaults

    # Accumulated in locals rather than a dict keyed by string literals that
    # have to match StartConfig's field names. Those literals were the last of
    # the untyped indirection the NamedTuple was introduced to remove: a
    # mistyped key built a StartConfig with a silent default and no error.
    start_x, start_y = defaults.start_x, defaults.start_y
    starting_exp = defaults.starting_exp
    starting_map_name = defaults.starting_map_name
    starting_gold = defaults.starting_gold
    starting_equipment = defaults.starting_equipment

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
                    start_x, start_y = coords

            if parser.has_option("game", "starting_exp"):
                starting_exp = parser.getint("game", "starting_exp")

            if parser.has_option("game", "startmap"):
                starting_map_name = parser.get("game", "startmap")

            if parser.has_option("game", "starting_gold"):
                starting_gold = parser.getint("game", "starting_gold")

            if parser.has_option("game", "starting_equipment"):
                eq_str = parser.get("game", "starting_equipment")
                starting_equipment = tuple(
                    item.strip() for item in eq_str.split(",") if item.strip()
                )
    except Exception as exc:
        # Whatever was parsed before the failure is kept; the rest falls back
        # to the StartConfig defaults.
        _log.warning("Could not load config: %s", exc)

    return StartConfig(
        start_x=start_x,
        start_y=start_y,
        starting_exp=starting_exp,
        starting_map_name=starting_map_name,
        starting_gold=starting_gold,
        starting_equipment=starting_equipment,
    )


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


# --------------------------------------------------------------------------
# Security response headers
# --------------------------------------------------------------------------
#
# The reasoning is written out here rather than filed in a doc, because every
# value below is a judgement about *this* app's shape, and the shape is unusual
# enough that the obvious policy is the wrong one.
#
# This Flask app serves no HTML. There is no ``templates/`` directory, no
# ``static/`` directory, no ``render_template`` / ``send_file`` /
# ``send_from_directory`` call anywhere under ``src/``, and no catch-all SPA
# route; every registered endpoint returns ``jsonify()``. The React frontend is
# a separate artefact on a separate origin -- Vite serves it from :3000 in
# development (proxying ``/api`` here, which is why ``CORS_ORIGINS`` exists at
# all), and ``deploy.ps1`` unpacks ``frontend/dist`` into a *different*
# container's document root in production while this app runs as its own
# systemd service. Two consequences follow, and they pull in opposite
# directions:
#
#   * These headers can never reach the SPA document, so the CSP that backstops
#     React's escaping of model-authored NPC dialogue is not something this file
#     can ship. It has to be issued by whatever serves ``index.html``.
#     :data:`_HTML_CSP` records the policy that document actually needs, so the
#     requirement is written down in the repo and is applied automatically the
#     day anything here does serve HTML.
#   * Because nothing here renders, the API's own CSP can be the strictest one
#     the grammar allows, with none of the blank-page risk that gets a CSP
#     deleted. :data:`_API_CSP` takes that option.
#
# Nothing below touches the ``Access-Control-*`` headers that flask_cors and
# :func:`_register_preflight` negotiate, and nothing below contradicts that
# allow-list: CSP constrains what a *document* may load, CORS constrains who may
# read a *response*, and the two never describe the same thing. In particular
# ``default-src 'none'`` does not affect the SPA's cross-origin ``fetch``,
# because a CSP binds the document it was served with and a fetched JSON body
# never becomes a document.

# The policy for every response this app actually produces today.
#
# ``default-src 'none'`` is safe precisely because it only ever binds the case
# it is meant to stop: a browser induced to *navigate* to an API URL and render
# the body (the classic route from a reflected value in an error payload to
# script execution). XHR / fetch / EventSource / WebSocket responses are not
# documents and ignore this header entirely, so the SPA is unaffected.
# ``sandbox`` with no tokens drops such a document into an opaque origin with no
# scripts, no forms and no top-level navigation -- belt to the braces.
_API_CSP = (
    "default-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "sandbox"
)

# The policy for HTML -- unreachable from this app today (nothing calls
# :func:`serves_html_document`), and deliberately kept anyway: it is the
# specification the SPA's host must mirror, and it is what a future
# ``send_from_directory`` of ``frontend/dist`` would need on day one. Derived
# from what the frontend measurably does, not from a hardening checklist:
#
#   script-src 'self'  No inline <script>, no eval, no ``new Function``, no
#       Worker and no blob: URL exists in ``frontend/src`` or ``index.html``
#       (grepped: zero hits) -- index.html loads one module by src. So the
#       directive that actually stops XSS stays strict, with no escape hatch.
#
#   style-src 'unsafe-inline'  A measured cost, not a necessity. Four
#       components render a literal <style> element (GameOverScreen:61,
#       HeroPanel:241, ItemDetailDialog:778, ToastContext:172) plus
#       InteractPanel:703, which builds one via
#       ``document.createElement('style')`` -- all of them for ``@keyframes``.
#       Those five are the whole of what forces the concession today, and the
#       count is falling: TypewriterOutput's ``blink`` and NpcChatPanel's
#       spinner keyframes have already been lifted into
#       ``frontend/src/styles/index.css``, because keyframe names are
#       document-global and a component-local block silently competes with
#       every other definition of the same name. The same move would work for
#       the remaining five, and if it is made this token should go with them.
#       There is no nonce to offer them meanwhile: a statically hosted, cached
#       index.html has no per-response value to mint. The ~1000 ``style={{}}``
#       props are the weaker argument (React applies those through the CSSOM,
#       which CSP does not police) but they are why a strict style policy would
#       be one refactor away from a blank screen anyway. The concession is
#       bounded: inline *style* cannot execute script, and the one place
#       untrusted model text reaches the DOM as markup (CombatLog's
#       ``dangerouslySetInnerHTML``) is already sanitised by DOMPurify -- CSP is
#       the second line there, not the first. It is still an escape hatch
#       written into a policy this file bills as the spec the SPA's host must
#       mirror, so it is worth removing rather than inheriting.
#
#   fonts.googleapis.com / fonts.gstatic.com  index.html links a Google Fonts
#       stylesheet, which in turn pulls its faces from the gstatic host. Both
#       are needed or the game loses its typography.
#
#   img-src / media-src data:  Vite inlines assets under its 4 KB threshold as
#       data: URIs at build time.
#
#   connect-src 'self'  Correct for the case this constant governs: HTML served
#       *from here* is same-origin with this API, and CSP3's 'self' already
#       covers the ws:/wss: upgrade Socket.IO performs against the same host. A
#       host serving the SPA on a *different* origin from the API (today's
#       production split, and any build setting VITE_API_URL) must append that
#       API origin here.
_HTML_CSP = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "object-src 'none'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "media-src 'self' data:; "
    "connect-src 'self'"
)

# Headers with no policy trade-off to weigh, and so no knob to offer.
#
#   X-Content-Type-Options  The precondition for most "navigate straight at an
#       API endpoint" attacks is a browser deciding a JSON body is really HTML.
#       nosniff removes it, and this app has no legitimate sniffing to lose.
#
#   X-Frame-Options  Nothing here is meant to be framed. This duplicates the
#       CSPs' ``frame-ancestors 'none'`` on purpose: frame-ancestors supersedes
#       it in modern browsers, and X-Frame-Options is what the ones that ignore
#       CSP still honour. DENY rather than SAMEORIGIN because the SPA is a
#       different origin and frames nothing.
#
#   Referrer-Policy  A deliberate pick, not a default. ``no-referrer`` was the
#       alternative and would also have been defensible -- the API never
#       initiates a navigation, so it has nothing to lose by sending nothing.
#       ``strict-origin-when-cross-origin`` wins on two counts: it is the value
#       the SPA's host will also set, so the two halves of the product state one
#       policy rather than two, and it keeps the full URL on same-origin
#       requests, which is what any debugging or log correlation on the API host
#       wants. The residual cross-origin leak is the bare origin, and this API
#       keeps no credential in a URL -- the session id travels in the
#       Authorization header, by the convention in ``src/api/middleware/auth.py``.
_STATIC_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# Strict-Transport-Security, production only.
#
# It is not in the set above because it is the one header here with a
# precondition: a browser ignores HSTS over plaintext, but a host that is *not*
# reachable over TLS and sends it anyway has locked its own clients out of it
# for a year. So it is gated on ``SESSION_COOKIE_SECURE``, which is the flag by
# which this app already says "I believe I am behind TLS" -- pinned True by
# ProductionConfig and by ``runtime_config()`` for a production ``FLASK_ENV``.
#
# It matters more here than the cookie flag it rides on. The session id does
# not travel in a cookie at all: ``src/api/middleware/auth.py`` reads it from
# ``Authorization: Bearer``, which ``SESSION_COOKIE_SECURE`` does nothing to
# protect. One ``http://`` request -- a typed URL, an old bookmark, a redirect
# -- hands that credential to the network in clear text. HSTS is what stops the
# request being made at all.
#
# One year, no ``includeSubDomains``, no ``preload``: the API is one host among
# whatever else the operator runs under the same parent domain, and asserting
# TLS on siblings this app knows nothing about is not its call to make.
_HSTS_HEADER = "Strict-Transport-Security"
_HSTS_VALUE = "max-age=31536000"


# Marks a response as a real SPA document. Opt-in, and deliberately so.
#
# Sniffing ``mimetype == "text/html"`` reads the wrong way round. This app
# authors no HTML, so every ``text/html`` response it emits today is written by
# *Werkzeug*, not by us: routing redirects, and HTTPExceptions that reach the
# WSGI layer with their default HTML bodies. Branching on the content type
# therefore handed the permissive policy to exactly the responses nobody
# designed -- the error paths an attacker reaches without credentials -- while
# the strict one covered the routes we control. ``_register_preflight``'s bare
# ``make_response()`` is a third case: Flask's default content type is
# ``text/html``, so an empty preflight body looked like a document too.
#
# Inverted, the default is :data:`_API_CSP` and a view that genuinely serves
# ``index.html`` asks for :data:`_HTML_CSP` by name. Forgetting to ask yields a
# visibly blank page in development, which is the file's stated safe direction
# to be wrong in; the sniffing version's failure was a policy that silently
# stopped applying.
_HTML_DOCUMENT_FLAG = "_hov_html_document"


def serves_html_document(response):
    """Mark ``response`` as an HTML document, so it gets :data:`_HTML_CSP`.

    For whatever eventually serves ``frontend/dist`` from this app -- a
    ``send_from_directory`` catch-all, or an SPA fallback route. Returns the
    response, so it can wrap a return value in place.
    """
    setattr(response, _HTML_DOCUMENT_FLAG, True)
    return response


def _renders_as_html(response):
    """True when this response has been marked as a document to render."""
    return bool(getattr(response, _HTML_DOCUMENT_FLAG, False))


def _register_security_headers(app):
    """Install the single ``after_request`` hook that sets security headers.

    Every header is written with ``setdefault``, so a reverse proxy or a route
    that has already made a deliberate choice keeps it, and repeated
    registration cannot stack or fight.

    Covers Flask responses only. flask_socketio wraps ``app.wsgi_app``, so the
    ``/socket.io/*`` handshake and polling responses are served beneath this
    hook and carry none of these headers. Harmless -- they are not documents
    and nothing frames them -- but the coverage is not total, and anything
    that needs to be true of *every* response on the port has to be set at the
    reverse proxy instead.
    """

    @app.after_request
    def set_security_headers(response):
        for header, value in _STATIC_SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault(_HSTS_HEADER, _HSTS_VALUE)
        response.headers.setdefault(
            "Content-Security-Policy",
            _HTML_CSP if _renders_as_html(response) else _API_CSP,
        )
        return response


def _register_meta_routes(app):
    """Health and API info — the two unauthenticated public endpoints."""

    @app.route("/health", methods=["GET"])
    def health():
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
        from flask import request as _req

        username = (_req.get_json() or {}).get("username", "inquisitor_test")
        session_id, _ = app.session_manager.create_session(username)
        return (
            jsonify({"session_id": session_id, "username": username}),
            201,
        )

    @app.route("/api/test/heal", methods=["POST"])
    def test_heal_player():
        """Restore player to full HP and fatigue. Test mode only — never active in production."""
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
    if _log_level_setting() is None:
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
    _register_security_headers(app)
    _register_meta_routes(app)
    if app.config.get("TESTING"):
        _register_test_routes(app)

    return app, socketio
