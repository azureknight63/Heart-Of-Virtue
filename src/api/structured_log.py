"""Unified structured (JSONL) debug logging for the API and engine.

Every log line — backend and frontend alike — shares one envelope schema so
tools/logcat.py, the bug-hunt harness, and AI agents can consume a single
stream without format sniffing:

    {"ts": "2026-08-22T16:13:23.901Z",   ISO-8601 UTC, Z suffix
     "src": "be" | "fe",                 backend / frontend origin
     "lvl": "debug|info|warning|error",  normalized level vocabulary
     "event": "http.request",            dot-separated event name; "log" for
                                          plain logger.info(...) calls
     "logger": "src.api...",             backend only: emitting logger
     "session": "ab12",                  short session fingerprint (optional)
     "msg": "...",                       human-readable text (optional)
     "data": {...},                      structured payload (optional)
     "n": 3}                             repeat count when collapsed (optional)

The pretty rendering lives in tools/logcat.py; this module only produces the
stream. Console output stays plain text so `tools/run_api.py` remains readable.

Environment variables (read by configure_logging):
    LOG_LEVEL      Console/plain-file level name. Defaults to WARNING.
    LOG_FILE       Optional plain-text log file path, confined to
                   ``<repo>/logs/`` and rotated (see _resolve_log_file_setting).
    LOG_JSONL_DIR  Directory for date-stamped .jsonl files. When set, the
                   logger level drops to DEBUG so the JSONL stream captures
                   everything while the console keeps LOG_LEVEL.

This module is the **only** installer of root-logger handlers (issue #698).
``src/api/app.py`` used to install a second console + LOG_FILE set from
``create_app()``; both sets survived each other's idempotence checks, so every
line printed twice and only one copy was redacted. ``create_app()`` now sets
namespace levels only. Every handler installed here carries
:class:`_RedactSecretsFilter`.
"""

import json
import logging
import logging.handlers
import os
import re
import time
import traceback
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path

from flask import g, request

from src.api.middleware.auth import session_token
from src.api.utils.log_cleanup import LogCleanupManager
from src.env_bootstrap import PROJECT_ROOT

_log = logging.getLogger(__name__)

# Marker attribute stamped on handlers this module installs, so reconfiguring
# replaces only its own handlers and never a test runner's capture handlers.
_HOV_MARKER = "_hov_structured_handler"

# LOG_FILE is confined to this directory. See _resolve_log_file_setting.
_LOG_DIR = PROJECT_ROOT / "logs"

# LOG_FILE rotation budget: a DEBUG run must not be able to fill the disk.
_LOG_FILE_MAX_BYTES = 5 * 1024 * 1024
_LOG_FILE_BACKUP_COUNT = 3

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

    Installed on **every** handler :func:`configure_logging` owns — console,
    LOG_FILE and JSONL alike. Filters run per handler, in handler order, so a
    filter missing from any one handler emits the unredacted record through
    it before the redacting one ever runs. That is not hypothetical: it is
    issue #698, where a second, unfiltered handler set installed at import
    time printed every line raw ahead of the redacted copy.

    Two payloads are scrubbed, because they travel by different routes:

    * ``record.msg`` (with ``record.args`` dropped, as they have already been
      merged in by ``getMessage()``).
    * ``record.exc_text`` — the formatted traceback. This is the one that
      matters most. Every ``logger.exception`` / ``exc_info=True`` call under
      ``src/`` and ``ai/`` feeds it — dozens of sites across the tree, so no
      list of them written here would stay true — and the largest single
      contributor is not any route module but
      ``src/api/handlers/error_handler.py``, the app-wide 500 handler that
      every unhandled exception passes through. Any of them can surface a
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
    caplog's, and :class:`JsonlFormatter`.

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


def _resolve_log_file_setting(log_file, log_dir=None):
    """Return the confined absolute path the LOG_FILE *setting* may write to.

    Not to be confused with ``src.api.routes.logs._resolve_log_file``, which
    answers a different question with an incompatible contract: that one takes
    a client-supplied filename to *read*, returns ``(path, error)`` and never
    raises. This one takes an operator-supplied setting to *write*, returns a
    ``Path`` and raises.

    Raises ValueError when it escapes ``log_dir`` (default ``<repo>/logs/``).
    Unconfined, this path reaches ``mkdir(parents=True)`` — which silently
    creates a directory tree anywhere the process can write — and a rotating
    handler, which *renames* ``X`` -> ``X.1`` -> ``X.2`` and so clobbers up to
    three neighbouring names beside whatever it was pointed at. A relative
    value is interpreted inside the log directory rather than against the
    working directory.
    """
    base = Path(_LOG_DIR if log_dir is None else log_dir)
    candidate = Path(log_file).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = candidate.resolve()
    base = base.resolve()
    if resolved == base or base not in resolved.parents:
        raise ValueError("LOG_FILE must resolve to a path under %s" % base)
    return resolved


_PLAIN_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

# Requests that would only log the act of logging (or monitor polling).
_REQUEST_LOG_SKIP_PREFIXES = ("/api/logs/browser",)
_REQUEST_LOG_SKIP_PATHS = frozenset({"/health"})

# Control characters stripped from attacker-influenced fields (request paths)
# before they enter the stream — logcat renders envelope content to a terminal.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# Libraries whose DEBUG output would drown the JSONL stream once the logger
# level drops to DEBUG for capture.
_NOISY_LOGGERS = ("engineio", "socketio", "werkzeug", "urllib3")

# Browser console levels normalize into the envelope vocabulary
# (debug/info/warning/error). Single source of truth — routes/logs.py imports
# this; tools/logcat.py mirrors it (standalone tool, kept dependency-free).
BROWSER_LEVEL_MAP = {
    "log": "info",
    "info": "info",
    "warn": "warning",
    "warning": "warning",
    "error": "error",
    "debug": "debug",
}


def utc_iso_z(dt=None):
    """ISO-8601 UTC with millisecond precision and a Z suffix.

    The one timestamp format every envelope uses — fe and be lines must
    match or logcat's chronological merge mis-orders the stream.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    return (
        dt.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def to_compact_json(obj):
    """Serialize one envelope (or payload) as a single compact JSON line."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


class JsonlFormatter(logging.Formatter):
    """Render a LogRecord as one single-line JSON envelope."""

    def format(self, record):
        env = {
            "ts": utc_iso_z(datetime.fromtimestamp(record.created, tz=timezone.utc)),
            "src": "be",
            "lvl": record.levelname.lower(),
            "event": getattr(record, "event", "log"),
            "logger": record.name,
        }
        data = dict(getattr(record, "data", None) or {})
        session = data.pop("session", None)
        if session:
            env["session"] = session
        msg = record.getMessage()
        if msg and msg != env["event"]:
            env["msg"] = msg
        if record.exc_info:
            exc_type, exc_value = record.exc_info[0], record.exc_info[1]
            data["error"] = f"{getattr(exc_type, '__name__', exc_type)}: {exc_value}"
            data["trace"] = self.formatException(record.exc_info)
        if data:
            env["data"] = data
        return to_compact_json(env)


class DateStampedJsonlHandler(logging.Handler):
    """Append JSONL lines to ``<dir>/<YYYY-MM-DD>.jsonl``, rolling at midnight.

    The date is recomputed per emit so a long-running dev server rolls to a
    new file naturally. Not stdlib TimedRotatingFileHandler by choice: the
    *active* file carries its date-stamped name (logcat tails it under that
    name), whereas TRFH keeps a fixed base name and renames on rotation.
    ``clock`` is injectable for tests; the default is UTC so the filename's
    date always agrees with the UTC ``ts`` fields inside the file.
    """

    def __init__(self, directory, clock=None):
        super().__init__()
        self.directory = Path(directory)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._stream = None
        self._current_path = None
        self.setFormatter(JsonlFormatter())

    def _open_stream(self, path):
        self.directory.mkdir(parents=True, exist_ok=True)
        return open(path, "a", encoding="utf-8")

    def emit(self, record):
        try:
            path = self.directory / f"{self._clock():%Y-%m-%d}.jsonl"
            if path != self._current_path:
                if self._stream is not None:
                    self._stream.close()
                self._stream = self._open_stream(path)
                self._current_path = path
            self._stream.write(self.format(record) + "\n")
            # Per-record flush is deliberate: logcat --tail depends on lines
            # appearing immediately, and this handler only runs on the dev
            # server (LOG_JSONL_DIR). Buffer/queue it if that ever changes.
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        try:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        finally:
            super().close()


def configure_logging(env=None, logger=None, log_dir=None):
    """Configure handlers on ``logger`` (root by default) from ``env``.

    The one owner of root-logger handlers in this process (issue #698). Every
    handler it installs carries :class:`_RedactSecretsFilter`.

    Idempotent: previously installed handlers (marked with _HOV_MARKER) are
    replaced; foreign handlers — e.g. pytest's capture handlers — are left
    untouched. The console handler is only added when the logger has no
    foreign handlers, so importing the app under a test runner never
    double-echoes records.

    ``log_dir`` overrides the directory LOG_FILE is confined to (tests only).
    A LOG_FILE outside it is refused with a warning, never a crash.
    """
    env = os.environ if env is None else env
    logger = logging.getLogger() if logger is None else logger

    level = getattr(
        logging, str(env.get("LOG_LEVEL", "WARNING")).upper(), logging.WARNING
    )
    if not isinstance(level, int):
        level = logging.WARNING

    for handler in list(logger.handlers):
        if getattr(handler, _HOV_MARKER, False):
            logger.removeHandler(handler)
            handler.close()

    plain = logging.Formatter(_PLAIN_FORMAT)
    redactor = _RedactSecretsFilter()

    def _install(handler, handler_level, formatter=None):
        handler.setLevel(handler_level)
        if formatter is not None:
            handler.setFormatter(formatter)
        handler.addFilter(redactor)
        setattr(handler, _HOV_MARKER, True)
        logger.addHandler(handler)

    if not logger.handlers:
        _install(logging.StreamHandler(), level, plain)

    log_file = env.get("LOG_FILE")
    if log_file:
        try:
            path = _resolve_log_file_setting(log_file, log_dir)
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                path,
                encoding="utf-8",
                maxBytes=_LOG_FILE_MAX_BYTES,
                backupCount=_LOG_FILE_BACKUP_COUNT,
            )
            _install(file_handler, level, plain)
        except (OSError, ValueError) as exc:
            # Degrade to the remaining handlers rather than refuse to boot
            # over a logging destination.
            _log.warning("Could not attach LOG_FILE handler %s: %s", log_file, exc)

    logger.setLevel(level)
    jsonl_dir = env.get("LOG_JSONL_DIR")
    if jsonl_dir:
        # Handler construction can't fail — the file opens lazily in emit(),
        # which already routes errors through handleError.
        _install(DateStampedJsonlHandler(jsonl_dir), logging.DEBUG)
        # Capture everything in the JSONL file while the console keeps LOG_LEVEL
        logger.setLevel(logging.DEBUG)
        for name in _NOISY_LOGGERS:
            logging.getLogger(name).setLevel(max(level, logging.INFO))
        # Prune old/oversized backend logs on every (re)configure — mirrors
        # the browser log directory's retention (7 days / 100MB). Without
        # this, logs/backend/*.jsonl grows forever: nothing else ever
        # touches this directory. Best-effort — a prune failure must never
        # block server startup.
        try:
            LogCleanupManager(jsonl_dir, retention_days=7, max_size_mb=100).cleanup()
        except OSError:
            pass


def log_event(event, *, level=logging.INFO, logger="hov", **data):
    """Emit a named structured event.

    ``logger`` accepts a name or a Logger instance. ``data`` becomes the
    envelope's ``data`` object; a ``session`` key is promoted to the top
    level by the formatter.
    """
    if not isinstance(logger, logging.Logger):
        logger = logging.getLogger(logger)
    logger.log(level, event, extra={"event": event, "data": data})


def _session_fingerprint(token):
    """Short, stable, non-reversible id for a session id (never the id).

    Takes the bare session id, not an ``Authorization`` header: since #493 the
    browser authenticates with an HttpOnly cookie and sends no header at all,
    so the caller resolves the credential via ``session_token()`` first. The
    hash is unchanged — it was always computed over the bare token — so
    fingerprints stay comparable with previously written log lines.
    """
    if not token:
        return None
    return f"{zlib.crc32(token.encode('utf-8')) & 0xFFFF:04x}"


def _should_skip_request_log():
    return (
        request.method == "OPTIONS"
        or request.path in _REQUEST_LOG_SKIP_PATHS
        or request.path.startswith(_REQUEST_LOG_SKIP_PREFIXES)
    )


def _request_data(status):
    """The canonical http.request payload for the current request.

    ``request.path`` is attacker-chosen (any URL can be requested) — strip
    control characters so a crafted path can't smuggle terminal escape
    sequences into the JSONL stream that logcat renders.
    """
    start = getattr(g, "hov_req_start", None)
    data = {
        "method": request.method,
        "path": _CONTROL_CHARS.sub(" ", request.path)[:512],
        "status": status,
        "dur_ms": (
            round((time.perf_counter() - start) * 1000, 1)
            if start is not None
            else None
        ),
        "request_id": getattr(g, "hov_request_id", None),
    }
    # Resolve through session_token(), not the raw header: since #493 the
    # browser sends an HttpOnly cookie and no Authorization header at all, so
    # reading the header directly silently drops the session field from every
    # real player's request line and breaks `logcat --session`.
    session = _session_fingerprint(session_token() or "")
    if session:
        data["session"] = session
    return data


def init_request_logging(app):
    """Attach one canonical ``http.request`` log line per request.

    The wide-event pattern: method, path, status, duration, and session
    fingerprint in a single structured record, replacing scattered per-route
    debug logging. 5xx responses log at ERROR; everything else at INFO
    (expected 4xx like the combat-status 401 poll would otherwise drown the
    console). Unhandled exceptions in debug mode re-raise before
    after_request runs, so a teardown hook backstops those — a crash is
    exactly what a debug log must not lose.
    """

    @app.before_request
    def _hov_request_start():
        g.hov_req_start = time.perf_counter()
        g.hov_request_id = uuid.uuid4().hex[:8]
        g.hov_request_logged = False

    @app.after_request
    def _hov_request_line(response):
        try:
            if _should_skip_request_log():
                return response
            data = _request_data(response.status_code)
            level = logging.ERROR if response.status_code >= 500 else logging.INFO
            log_event("http.request", level=level, logger="hov.http", **data)
            g.hov_request_logged = True
        except Exception:
            # A logging failure must never break the request itself.
            pass
        return response

    @app.teardown_request
    def _hov_request_crash(exc):
        try:
            if (
                exc is None
                or getattr(g, "hov_request_logged", False)
                or _should_skip_request_log()
            ):
                return
            data = _request_data(500)
            data["error"] = f"{type(exc).__name__}: {exc}"
            data["trace"] = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )
            log_event("http.request", level=logging.ERROR, logger="hov.http", **data)
        except Exception:
            pass

    return app
