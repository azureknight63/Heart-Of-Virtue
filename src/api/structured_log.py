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
    LOG_FILE       Optional plain-text log file path.
    LOG_JSONL_DIR  Directory for date-stamped .jsonl files. When set, the
                   logger level drops to DEBUG so the JSONL stream captures
                   everything while the console keeps LOG_LEVEL.
"""

import json
import logging
import os
import re
import time
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path

from flask import g, request

# Marker attribute stamped on handlers this module installs, so reconfiguring
# replaces only its own handlers and never a test runner's capture handlers.
_HOV_MARKER = "_hov_structured_handler"

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


def configure_logging(env=None, logger=None):
    """Configure handlers on ``logger`` (root by default) from ``env``.

    Idempotent: previously installed handlers (marked with _HOV_MARKER) are
    replaced; foreign handlers — e.g. pytest's capture handlers — are left
    untouched. The console handler is only added when the logger has no
    foreign handlers, so importing the app under a test runner never
    double-echoes records.
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

    if not logger.handlers:
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(plain)
        setattr(console, _HOV_MARKER, True)
        logger.addHandler(console)

    log_file = env.get("LOG_FILE")
    if log_file:
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(plain)
            setattr(file_handler, _HOV_MARKER, True)
            logger.addHandler(file_handler)
        except OSError:
            pass

    logger.setLevel(level)
    jsonl_dir = env.get("LOG_JSONL_DIR")
    if jsonl_dir:
        # Handler construction can't fail — the file opens lazily in emit(),
        # which already routes errors through handleError.
        jsonl_handler = DateStampedJsonlHandler(jsonl_dir)
        jsonl_handler.setLevel(logging.DEBUG)
        setattr(jsonl_handler, _HOV_MARKER, True)
        logger.addHandler(jsonl_handler)
        # Capture everything in the JSONL file while the console keeps LOG_LEVEL
        logger.setLevel(logging.DEBUG)
        for name in _NOISY_LOGGERS:
            logging.getLogger(name).setLevel(max(level, logging.INFO))


def log_event(event, *, level=logging.INFO, logger="hov", **data):
    """Emit a named structured event.

    ``logger`` accepts a name or a Logger instance. ``data`` becomes the
    envelope's ``data`` object; a ``session`` key is promoted to the top
    level by the formatter.
    """
    if not isinstance(logger, logging.Logger):
        logger = logging.getLogger(logger)
    logger.log(level, event, extra={"event": event, "data": data})


def _session_fingerprint(auth_header):
    """Short, stable, non-reversible id for a Bearer token (never the token)."""
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
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
    session = _session_fingerprint(request.headers.get("Authorization", ""))
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
            log_event("http.request", level=logging.ERROR, logger="hov.http", **data)
        except Exception:
            pass

    return app
