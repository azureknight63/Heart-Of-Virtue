"""
Browser logging API routes
Handles receiving and storing browser console logs
"""

from flask import Blueprint, current_app, request, jsonify, abort
from datetime import datetime
import os
import re
import threading
import time
import zlib
from pathlib import Path
from src.api.rate_limiter import (
    RateLimiter,
    client_ip,
    limiter_from_env,
    rate_limited_response,
)
from src.api.utils.log_cleanup import LogCleanupManager

logs_bp = Blueprint("logs", __name__)

# Resource-exhaustion guards for the unauthenticated POST /browser route.
# The frontend logger posts here without auth (incl. via sendBeacon), so the
# route cannot be gated — instead we bound what a single request can write and
# how many distinct files a hostile client can create (issue #429).
MAX_LOGS_PER_REQUEST = 500       # max log entries accepted per request
MAX_MESSAGE_LENGTH = 4000        # per-message truncation (matches npc_chat)
MAX_FIELD_LENGTH = 2048          # cap on url and other free-text fields
MAX_SHORT_FIELD_LENGTH = 64      # cap on timestamp/level
SESSION_ID_BUCKETS = 64          # bound distinct session log files per day

# Control chars (incl. CR/LF) are stripped from every client-supplied field
# before it is written into a log line, so a hostile payload can't inject a
# newline to forge fake entries or embed terminal escape sequences (CWE-117).
_LOG_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_log_field(value):
    """Collapse control characters in a log field to single spaces."""
    return _LOG_CONTROL_CHARS.sub(" ", value)


def _require_testing():
    """Gate log-management routes behind TESTING mode.

    Listing/reading/deleting/cleaning server log files is a debug/QA
    capability only — never reachable in production. Mirrors the
    `/api/debug/routes` self-check pattern in src/api/app.py. The POST
    `/browser` (receive) route is intentionally NOT gated by this: the
    frontend logger posts to it unauthenticated (incl. via sendBeacon).
    """
    if not current_app.config.get("TESTING"):
        abort(404)


# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent.parent.parent.parent / "logs" / "browser"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize log cleanup manager
# Default: 7 days retention, 100MB max size
cleanup_manager = LogCleanupManager(LOGS_DIR, retention_days=7, max_size_mb=100)

# Requests per source IP per minute on the unauthenticated POST /browser route.
# The IP is the only tier available: the frontend logger posts without a
# session (and via sendBeacon on unload, which carries no headers of ours), so
# there is no account or session to key on — see `client_ip` for how a source
# is identified. Per-worker like every other limiter here (issue #284).
#
# 60/minute is set against what the logger can legitimately emit:
# `frontend/src/utils/logger.js` flushes on a 5s timer (12/min) and whenever
# its queue reaches BATCH_SIZE, so a burst of console output can exceed the
# timer rate — but a request per second, per address, is far above a real
# client and far below a flood. A tripped client is not broken by it: the
# logger treats a non-2xx as a failure and stands down for FAILURE_BACKOFF_MS
# (30s), re-queueing (and trimming) its backlog.
#
# Disableable via BROWSER_LOG_RATE_LIMIT_PER_MINUTE=0: what its absence costs
# is log noise and disk churn on a debug facility, not an open credential path
# — the same reasoning that lets FEEDBACK_RATE_LIMIT_PER_HOUR be switched off
# and keeps the two LOGIN_* tiers from being.
_BROWSER_LOG_RATE_LIMIT = 60
_BROWSER_LOG_RATE_WINDOW = 60  # seconds
_browser_log_limiter = limiter_from_env(
    "BROWSER_LOG_RATE_LIMIT_PER_MINUTE",
    _BROWSER_LOG_RATE_LIMIT,
    _BROWSER_LOG_RATE_WINDOW,
)

# Minimum seconds between retention sweeps triggered by an inbound log post.
# The sweep is a full listing + stat of every file in LOGS_DIR, and it ran once
# per request on a route no credential guards — so a flood paid for a directory
# scan per request *and* drove the 100 MB size-based eviction, which discards
# the oldest files first: genuine logs. Running it on a floor instead keeps the
# retention policy enforced under real traffic while decoupling its cost, and
# its eviction, from the request rate. The TESTING-only POST /browser/cleanup
# route is the on-demand path and is deliberately not throttled by this.
CLEANUP_MIN_INTERVAL_SECONDS = 300

_cleanup_lock = threading.Lock()
# monotonic() so a clock adjustment cannot push the next sweep hours away; the
# 0.0 start means the first post after boot sweeps, as before.
_last_cleanup_at = 0.0


def _warn(message):
    """Report a handled failure to stderr, without ever raising.

    Every error path in this module reports with ``print`` rather than through
    the app logger, and the reason written beside them -- "to avoid circular
    logging" -- is not the true one. Nothing in the Python logging path
    re-enters ``POST /api/logs/browser``; the app logger writes to a file
    handler and no ``HTTPHandler`` is installed anywhere. The reason that DOES
    hold is narrower and worth keeping: the faults reported here are faults of
    the log directory itself (a failed sweep, an unwritable file), which is
    where the app logger's own handler writes, so reporting through it is
    reporting through the thing that is broken.

    What ``print`` is not, however, is exception-free, and every call site sits
    inside an ``except`` block whose entire job is to swallow. ``print`` raises
    ``UnicodeEncodeError`` on a cp1252 Windows console -- this repo has been
    bitten by exactly that from the terminal engine's ``cprint`` -- and
    ``ValueError: I/O operation on closed file`` when a WSGI server has closed
    stdout. Either one escaped the handler and turned a swallowed housekeeping
    failure into a 500 on the request that triggered it.
    """
    try:
        print(message)
    except Exception:  # pragma: no cover - a diagnostic must not have a fault
        pass


def _maybe_cleanup():
    """Run the retention sweep if the interval floor has elapsed.

    Returns True when a sweep was ATTEMPTED -- the floor had elapsed and
    ``cleanup_manager.cleanup()`` was called -- and NOT when it succeeded. A
    sweep that raises is swallowed and still returns True, deliberately: the
    return value paces the floor, and a sweep failing for a persistent reason
    (an unwritable directory, say) must not then be retried on every single
    request. The old wording, "returns True when a sweep ran", described a
    value this function has never returned.

    Never raises, and now means it -- see :func:`_warn`, which exists because
    the ``print`` in the handler below could.
    """
    global _last_cleanup_at
    now = time.monotonic()
    with _cleanup_lock:
        if now - _last_cleanup_at < CLEANUP_MIN_INTERVAL_SECONDS:
            return False
        _last_cleanup_at = now
    try:
        cleanup_manager.cleanup()
    except Exception as cleanup_error:
        # Reported through _warn, not the app logger: see _warn's docstring
        # for why (the fault is usually in the log directory the logger writes
        # to) and for why a bare print here was not safe.
        _warn(f"Warning: Log cleanup failed: {str(cleanup_error)}")
    return True


@logs_bp.route("/browser", methods=["POST"])
def receive_browser_logs():
    """
    Receive browser logs from the frontend and write them to a file

    Expected payload:
    {
        "logs": [
            {
                "timestamp": "2025-11-27T18:41:11.123Z",
                "level": "LOG|ERROR|WARN|INFO|DEBUG",
                "message": "log message",
                "url": "http://localhost:3000/",
                "userAgent": "Mozilla/5.0..."
            }
        ],
        "session_id": "session_1234567890_abc123"
    }
    """
    # Spent before the body is parsed and before anything is written: this is
    # the only route in the API with neither authentication nor a session, so
    # the throttle is the whole of its admission control. Checked outside the
    # try below so the 429 cannot be relabelled a 500 by the catch-all.
    if RateLimiter.check(_browser_log_limiter, client_ip()):
        return rate_limited_response(
            "Too many log submissions. Please slow down."
        )

    try:
        data = request.get_json(silent=True)

        # A non-object body (string/number/list/null/bool) has no "logs"; treat
        # it as a bad request rather than letting ``in``/``.get`` raise a 500.
        if not isinstance(data, dict) or "logs" not in data:
            return jsonify({"error": "No logs provided"}), 400

        logs = data.get("logs", [])
        # A non-list "logs" (string/number/dict) is malformed input, not a
        # payload to iterate — treat it as a bad request rather than a 500.
        if not isinstance(logs, list):
            return jsonify({"error": "No logs provided"}), 400

        # Bounded HERE, before anything else touches it, because this is the
        # one client-supplied field that is re-emitted on EVERY written line
        # (see the log_line below) rather than once per request.
        #
        # It was unbounded, and nothing downstream shortened it: `str()`,
        # `os.path.basename` and the charset `re.sub` are all
        # length-preserving. With MAX_LOGS_PER_REQUEST entries in one body, a
        # ~1 MiB session_id wrote ~500 MB -- on a route with no auth, at 60
        # requests per minute per IP, with the retention sweep floored at
        # CLEANUP_MIN_INTERVAL_SECONDS so growth between sweeps is unbounded.
        # `cleanup_by_size` then evicts oldest-first, destroying genuine logs.
        #
        # The bounds comment at the top of this module claimed to cap "what a
        # single request can write" -- and it does, for every field of an
        # ENTRY. session_id is a sibling of `logs`, not a member of an entry,
        # so it fell outside an enumeration derived from the entry schema.
        session_id = str(data.get("session_id", "unknown"))[:MAX_SHORT_FIELD_LENGTH]

        if not logs:
            return jsonify({"message": "No logs to write"}), 200

        # Cap the number of entries accepted per request so a single
        # unauthenticated POST cannot write an unbounded amount to disk.
        logs = logs[:MAX_LOGS_PER_REQUEST]

        # Sanitize the client-supplied session id before it becomes part of a
        # filesystem path — strip directory components and restrict to a safe
        # charset so it cannot be used to escape LOGS_DIR (matches the
        # basename() guard used by the read/delete routes below).
        session_id = re.sub(r"[^A-Za-z0-9_-]", "_", os.path.basename(session_id))
        if not session_id:
            session_id = "unknown"

        # Bound the number of distinct log files a hostile client can create by
        # mapping the client-controlled session id into a fixed bucket set.
        # Without this, varying session_id yields unbounded per-day files that
        # size-based cleanup cannot reclaim until they age out. The full session
        # id is preserved on each log line below so traceability is retained.
        bucket = zlib.crc32(session_id.encode("utf-8")) % SESSION_ID_BUCKETS

        # Create a bucketed log file for today.
        today = datetime.now().strftime("%Y-%m-%d")
        log_filename = f"{today}_bucket{bucket:02d}.log"
        log_filepath = LOGS_DIR / log_filename

        # Append logs to the file, bounding every free-text field so no single
        # oversized entry can blow up disk usage.
        # Counts lines actually written, not entries submitted: malformed entries
        # are skipped below, so len(logs) would over-report on a mixed batch.
        written = 0
        with open(log_filepath, "a", encoding="utf-8") as f:
            for log_entry in logs:
                # Hostile payloads may include non-dict entries (e.g. bare
                # strings); skip them instead of raising.
                if not isinstance(log_entry, dict):
                    continue
                timestamp = _sanitize_log_field(
                    str(log_entry.get("timestamp", datetime.now().isoformat()))[
                        :MAX_SHORT_FIELD_LENGTH
                    ]
                )
                level = _sanitize_log_field(
                    str(log_entry.get("level", "LOG"))[:MAX_SHORT_FIELD_LENGTH]
                )
                message = _sanitize_log_field(
                    str(log_entry.get("message", ""))[:MAX_MESSAGE_LENGTH]
                )
                url = _sanitize_log_field(
                    str(log_entry.get("url", ""))[:MAX_FIELD_LENGTH]
                )

                # Format: [TIMESTAMP] [LEVEL] [SESSION] [URL] MESSAGE
                log_line = (
                    f"[{timestamp}] [{level}] [{session_id}] [{url}] {message}\n"
                )
                f.write(log_line)
                written += 1

        # Automatic retention sweep, rate-floored rather than per-request —
        # see CLEANUP_MIN_INTERVAL_SECONDS.
        _maybe_cleanup()

        return (
            jsonify(
                {
                    "message": f"Successfully wrote {written} log entries",
                    "file": str(log_filename),
                }
            ),
            200,
        )

    except Exception as e:
        # Reported through _warn, not the app logger -- see _warn.
        _warn(f"Error writing browser logs: {str(e)}")
        return jsonify({"error": "Failed to write logs"}), 500


@logs_bp.route("/browser/files", methods=["GET"])
def list_browser_log_files():
    """
    List all available browser log files
    """
    _require_testing()
    try:
        log_files = []

        if LOGS_DIR.exists():
            for log_file in sorted(LOGS_DIR.glob("*.log"), reverse=True):
                stat = log_file.stat()
                log_files.append(
                    {
                        "filename": log_file.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                )

        return jsonify({"files": log_files}), 200

    except Exception as e:
        _warn(f"Error listing browser log files: {str(e)}")
        return jsonify({"error": "Failed to list log files"}), 500


def _resolve_log_file(filename):
    """Resolve an attacker-supplied log filename to a path inside LOGS_DIR.

    Returns ``(path, None)`` for a real, in-directory log file, or
    ``(None, (response, status))`` describing a structured 4xx for a hostile
    name: directory-traversal segments (``.``/``..``), an over-long name (a
    filesystem ``ENAMETOOLONG`` would otherwise surface as a 500), or a name
    that does not resolve to a regular file. Never raises.
    """
    safe_filename = os.path.basename(filename or "")
    if not safe_filename or safe_filename in (".", "..") or len(safe_filename) > 255:
        return None, (jsonify({"error": "Invalid log filename"}), 400)
    log_filepath = LOGS_DIR / safe_filename
    try:
        is_file = log_filepath.is_file()
    except OSError:
        return None, (jsonify({"error": "Invalid log filename"}), 400)
    if not is_file:
        return None, (jsonify({"error": "Log file not found"}), 404)
    return log_filepath, None


@logs_bp.route("/browser/files/<filename>", methods=["GET"])
def get_browser_log_file(filename):
    """
    Retrieve the contents of a specific browser log file
    """
    _require_testing()
    log_filepath, error = _resolve_log_file(filename)
    if error:
        return error
    try:
        with open(log_filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"filename": log_filepath.name, "content": content}), 200
    except OSError as e:
        _warn(f"Error reading browser log file: {str(e)}")
        return jsonify({"error": "Failed to read log file"}), 500


@logs_bp.route("/browser/cleanup", methods=["POST"])
def cleanup_logs():
    """
    Manually trigger log cleanup

    Optional JSON payload:
    {
        "retention_days": 7,  // Override default retention
        "max_size_mb": 100    // Override default max size
    }
    """
    _require_testing()
    try:
        raw = request.get_json(silent=True)
        # A JSON body can parse to any type (string, number, list, null); coerce
        # a non-object to {} so the .get() calls below never crash with a 500.
        data = raw if isinstance(raw, dict) else {}

        # Create cleanup manager with custom settings if provided. Hostile
        # non-numeric overrides fall back to the manager's defaults rather than
        # propagating a TypeError into LogCleanupManager.
        try:
            retention_days = int(
                data.get("retention_days", cleanup_manager.retention_days)
            )
        except (TypeError, ValueError):
            retention_days = cleanup_manager.retention_days
        try:
            max_size_mb = float(
                data.get(
                    "max_size_mb", cleanup_manager.max_size_bytes / (1024 * 1024)
                )
            )
        except (TypeError, ValueError):
            max_size_mb = cleanup_manager.max_size_bytes / (1024 * 1024)

        temp_manager = LogCleanupManager(
            LOGS_DIR, retention_days=retention_days, max_size_mb=max_size_mb
        )
        result = temp_manager.cleanup()

        return jsonify({"message": "Cleanup completed", "result": result}), 200

    except Exception as e:
        _warn(f"Error during manual cleanup: {str(e)}")
        return jsonify({"error": "Failed to cleanup logs"}), 500


@logs_bp.route("/browser/stats", methods=["GET"])
def get_log_stats():
    """
    Get statistics about browser log files
    """
    _require_testing()
    try:
        stats = cleanup_manager.get_stats()

        return (
            jsonify(
                {
                    "stats": stats,
                    "cleanup_config": {
                        "retention_days": cleanup_manager.retention_days,
                        "max_size_mb": cleanup_manager.max_size_bytes / (1024 * 1024),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        _warn(f"Error getting log stats: {str(e)}")
        return jsonify({"error": "Failed to get log stats"}), 500


@logs_bp.route("/browser/files/<filename>", methods=["DELETE"])
def delete_browser_log_file(filename):
    """
    Delete a specific browser log file
    """
    _require_testing()
    log_filepath, error = _resolve_log_file(filename)
    if error:
        return error
    try:
        file_size = log_filepath.stat().st_size
        log_filepath.unlink()
        return (
            jsonify(
                {
                    "message": f"Successfully deleted {log_filepath.name}",
                    "deleted_size": file_size,
                }
            ),
            200,
        )
    except OSError as e:
        _warn(f"Error deleting browser log file: {str(e)}")
        return jsonify({"error": "Failed to delete log file"}), 500
