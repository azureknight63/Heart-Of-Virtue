"""
Browser logging API routes
Handles receiving and storing browser console logs
"""

from flask import Blueprint, current_app, request, jsonify, abort
from datetime import datetime
import os
import re
import zlib
from pathlib import Path
from src.api.structured_log import BROWSER_LEVEL_MAP, to_compact_json, utc_iso_z
from src.api.utils.log_cleanup import LOG_FILE_PATTERNS, LogCleanupManager

logs_bp = Blueprint("logs", __name__)

# Resource-exhaustion guards for the unauthenticated POST /browser route.
# The frontend logger posts here without auth (incl. via sendBeacon), so the
# route cannot be gated — instead we bound what a single request can write and
# how many distinct files a hostile client can create (issue #429).
MAX_LOGS_PER_REQUEST = 500  # max log entries accepted per request
MAX_MESSAGE_LENGTH = 4000  # per-message truncation (matches npc_chat)
MAX_FIELD_LENGTH = 2048  # cap on url and other free-text fields
MAX_SHORT_FIELD_LENGTH = 64  # cap on timestamp and data keys
MAX_EVENT_LENGTH = 64  # cap on structured event names
MAX_REPEAT_COUNT = 100000  # clamp on the client-side collapse counter
SESSION_ID_BUCKETS = 64  # bound distinct session log files per day

# Structured event names are dot-separated lowercase slugs; anything else
# collapses to underscores so a hostile name can't smuggle odd characters.
_EVENT_CHARS = re.compile(r"[^a-z0-9._-]")

# Control chars (incl. CR/LF) are stripped from every client-supplied field
# before it is written into a log line, so a hostile payload can't inject a
# newline to forge fake entries or embed terminal escape sequences (CWE-117).
_LOG_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_log_field(value):
    """Collapse control characters in a log field to single spaces."""
    return _LOG_CONTROL_CHARS.sub(" ", value)


# Bound recursion on adversarially nested (_MAX_DATA_DEPTH) or wide
# (_MAX_DATA_NODES) data payloads. The serialized-size check in
# _entry_to_envelope runs AFTER sanitization and only bounds the stored
# output — it does nothing to cap the walk's own cost, so a single dict
# with one key holding thousands of short strings previously did unbounded
# work (up to 500x per request, once per MAX_LOGS_PER_REQUEST entry) before
# that check ever ran. The node budget bounds total work regardless of
# whether the adversarial shape is deep or wide.
_MAX_DATA_DEPTH = 8
_MAX_DATA_NODES = 500


def _sanitize_data(value, depth=0, budget=None):
    """Strip control characters from every string inside a data payload.

    The JSON file encoding escapes control bytes, but consumers that parse
    and re-render the payload (tools/logcat.py's terminal view) would
    otherwise receive live ESC sequences from an unauthenticated client —
    sanitize keys and values at the source too, not just at the sink.
    """
    if budget is None:
        budget = [_MAX_DATA_NODES]
    if depth >= _MAX_DATA_DEPTH or budget[0] <= 0:
        return "..."
    budget[0] -= 1
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            if budget[0] <= 0:
                result["..."] = "(truncated)"
                break
            result[_sanitize_log_field(str(k))[:MAX_SHORT_FIELD_LENGTH]] = (
                _sanitize_data(v, depth + 1, budget)
            )
        return result
    if isinstance(value, list):
        result = []
        for v in value:
            if budget[0] <= 0:
                result.append("...(truncated)")
                break
            result.append(_sanitize_data(v, depth + 1, budget))
        return result
    if isinstance(value, str):
        return _sanitize_log_field(value)
    return value


def _entry_to_envelope(log_entry, session_id):
    """Convert one client log entry into the shared JSONL envelope.

    Every field is client-supplied and hostile until proven otherwise:
    strings are control-stripped and capped, the event name is slugged, the
    data payload is size-bounded, and the repeat counter is clamped. The
    envelope is serialized with json.dumps, so a payload can never forge
    additional log lines (CWE-117) — newlines are escaped by encoding.
    """
    # Fallback matches the client's toISOString() (UTC, Z suffix) so logcat's
    # chronological merge never mixes naive local time into the feed. Built
    # only when the client omitted the timestamp — the closed BROWSER_LEVEL_MAP
    # likewise makes any sanitize/cap ceremony on the level a no-op: hostile
    # input simply isn't a key and collapses to "info".
    raw_ts = log_entry.get("timestamp")
    envelope = {
        "ts": (
            _sanitize_log_field(str(raw_ts)[:MAX_SHORT_FIELD_LENGTH])
            if raw_ts is not None
            else utc_iso_z()
        ),
        "src": "fe",
        "lvl": BROWSER_LEVEL_MAP.get(
            str(log_entry.get("level", "LOG")).strip().lower(), "info"
        ),
        "event": _EVENT_CHARS.sub("_", str(log_entry.get("event", "console")).lower())[
            :MAX_EVENT_LENGTH
        ]
        or "console",
        "session": session_id,
    }

    url = _sanitize_log_field(str(log_entry.get("url", ""))[:MAX_FIELD_LENGTH])
    if url:
        envelope["url"] = url

    message = _sanitize_log_field(
        str(log_entry.get("message", ""))[:MAX_MESSAGE_LENGTH]
    )
    if message:
        envelope["msg"] = message

    data = log_entry.get("data")
    if isinstance(data, dict) and data:
        data = _sanitize_data(data)
        serialized = to_compact_json(data)
        if len(serialized) > MAX_MESSAGE_LENGTH:
            data = {"_truncated": True, "size": len(serialized)}
        envelope["data"] = data

    try:
        repeat = int(log_entry.get("n", 1))
    except (TypeError, ValueError):
        repeat = 1
    if repeat > 1:
        envelope["n"] = min(repeat, MAX_REPEAT_COUNT)

    return envelope


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


def _write_log_entries(entries, session_id):
    """Append client log entries to today's bucketed JSONL file.

    Shared by the console-log and CSP-violation sinks: both are unauthenticated
    POST routes writing attacker-influenced content into the same stream, so the
    path sanitization, bucketing and per-line encoding must be identical for
    both rather than reimplemented per route.

    Returns the name of the file written.
    """
    # Sanitize the client-supplied session id before it becomes part of a
    # filesystem path — strip directory components and restrict to a safe
    # charset so it cannot be used to escape LOGS_DIR (matches the basename()
    # guard used by the read/delete routes below).
    session_id = re.sub(r"[^A-Za-z0-9_-]", "_", os.path.basename(str(session_id)))
    if not session_id:
        session_id = "unknown"

    # Bound the number of distinct log files a hostile client can create by
    # mapping the client-controlled session id into a fixed bucket set. Without
    # this, varying session_id yields unbounded per-day files that size-based
    # cleanup cannot reclaim until they age out. The full session id is
    # preserved on each log line so traceability is retained.
    bucket = zlib.crc32(session_id.encode("utf-8")) % SESSION_ID_BUCKETS

    today = datetime.now().strftime("%Y-%m-%d")
    log_filename = f"{today}_bucket{bucket:02d}.jsonl"

    # Append one envelope per line, bounding every field so no single oversized
    # entry can blow up disk usage.
    with open(LOGS_DIR / log_filename, "a", encoding="utf-8") as handle:
        for entry in entries:
            # Hostile payloads may include non-dict entries (e.g. bare
            # strings); skip them instead of raising.
            if not isinstance(entry, dict):
                continue
            handle.write(to_compact_json(_entry_to_envelope(entry, session_id)) + "\n")

    return log_filename


@logs_bp.route("/browser", methods=["POST"])
def receive_browser_logs():
    """
    Receive browser logs from the frontend and write them as JSONL

    Expected payload:
    {
        "logs": [
            {
                "timestamp": "2025-11-27T18:41:11.123Z",
                "level": "LOG|ERROR|WARN|INFO|DEBUG",
                "message": "log message",
                "url": "http://localhost:3000/",
                "event": "event.enqueue",       // optional structured name
                "data": {"name": "..."},        // optional structured payload
                "n": 2                           // optional repeat count
            }
        ],
        "session_id": "session_1234567890_abc123"
    }

    Each entry becomes one line of the shared JSONL envelope schema (see
    src/api/structured_log.py) in logs/browser/<date>_bucket<NN>.jsonl.
    """
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

        session_id = str(data.get("session_id", "unknown"))

        if not logs:
            return jsonify({"message": "No logs to write"}), 200

        # Cap the number of entries accepted per request so a single
        # unauthenticated POST cannot write an unbounded amount to disk.
        logs = logs[:MAX_LOGS_PER_REQUEST]

        log_filename = _write_log_entries(logs, session_id)

        # Perform automatic cleanup after writing logs
        # This runs silently in the background
        try:
            cleanup_manager.cleanup()
        except Exception as cleanup_error:
            # Don't fail the request if cleanup fails
            print(f"Warning: Log cleanup failed: {str(cleanup_error)}")

        return (
            jsonify(
                {
                    "message": f"Successfully wrote {len(logs)} log entries",
                    "file": str(log_filename),
                }
            ),
            200,
        )

    except Exception as e:
        # Don't use app logger here to avoid circular logging
        print(f"Error writing browser logs: {str(e)}")
        return jsonify({"error": "Failed to write logs"}), 500


# Violation sink for the Content-Security-Policy rollout (issue #492). Both
# report transports are accepted: the legacy `report-uri` directive POSTs a
# single {"csp-report": {...}} object as application/csp-report, while the
# Reporting API's `report-to` POSTs a list of {"type", "body"} entries as
# application/reports+json. The policy currently advertises `report-uri` only
# (pairing the two delivers nothing in Chromium — see the module docstring in
# src/api/security_headers.py), so the reports+json shape is unreachable today;
# accepting it anyway means the follow-up that re-adds `report-to` over HTTPS
# needs no server-side change.
MAX_CSP_REPORTS_PER_REQUEST = 20

# The bucket these violations land in. A CSP report carries no session id (it is
# sent by the browser, not the app), so they share one predictable file rather
# than diluting the per-session buckets.
CSP_LOG_SESSION = "csp"

# Fields worth keeping off a violation report. The rest of the payload is
# browser-version-specific noise, and an allowlist keeps a hostile POST from
# using this route as arbitrary log storage.
_CSP_REPORT_FIELDS = (
    "document-uri",
    "referrer",
    "violated-directive",
    "effective-directive",
    "original-policy",
    "disposition",
    "blocked-uri",
    "line-number",
    "column-number",
    "source-file",
    "status-code",
    "script-sample",
)


def _csp_reports_from_body(body):
    """Normalize either CSP report transport into a list of report dicts."""
    if isinstance(body, dict):
        report = body.get("csp-report")
        if isinstance(report, dict):
            return [report]
        # A Reporting-API body can also arrive as a single object.
        if isinstance(body.get("body"), dict):
            return [body["body"]]
        return []
    if isinstance(body, list):
        return [
            item["body"]
            for item in body
            if isinstance(item, dict) and isinstance(item.get("body"), dict)
        ]
    return []


@logs_bp.route("/csp-report", methods=["POST"])
def receive_csp_report():
    """Record a Content-Security-Policy violation report.

    Unauthenticated by necessity — the browser, not the app, sends these, and it
    attaches no credentials. Reports are written into the same bounded JSONL
    stream as browser console logs (``event: csp.violation``), so logcat shows a
    violation alongside the console output from the same page load.

    Always answers 204: a report endpoint that argues with the browser only
    produces console noise, and there is no client left to act on an error.
    """
    try:
        # Reports arrive as application/csp-report or application/reports+json,
        # neither of which Flask treats as JSON — force the parse.
        body = request.get_json(silent=True, force=True)
        reports = _csp_reports_from_body(body)[:MAX_CSP_REPORTS_PER_REQUEST]
        if not reports:
            return "", 204

        entries = []
        for report in reports:
            data = {key: report[key] for key in _CSP_REPORT_FIELDS if key in report}
            entries.append(
                {
                    "level": "WARN",
                    "event": "csp.violation",
                    "url": report.get("document-uri", ""),
                    "data": data or {"_empty": True},
                }
            )

        _write_log_entries(entries, CSP_LOG_SESSION)
        return "", 204

    except Exception as e:
        # Don't use the app logger here to avoid circular logging.
        print(f"Error writing CSP report: {str(e)}")
        return "", 204


@logs_bp.route("/browser/files", methods=["GET"])
def list_browser_log_files():
    """
    List all available browser log files
    """
    _require_testing()
    try:
        log_files = []

        if LOGS_DIR.exists():
            # Both current .jsonl files and pre-migration .log files
            found = [p for pattern in LOG_FILE_PATTERNS for p in LOGS_DIR.glob(pattern)]
            for log_file in sorted(found, key=lambda p: p.name, reverse=True):
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
        print(f"Error listing browser log files: {str(e)}")
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
        print(f"Error reading browser log file: {str(e)}")
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
                data.get("max_size_mb", cleanup_manager.max_size_bytes / (1024 * 1024))
            )
        except (TypeError, ValueError):
            max_size_mb = cleanup_manager.max_size_bytes / (1024 * 1024)

        temp_manager = LogCleanupManager(
            LOGS_DIR, retention_days=retention_days, max_size_mb=max_size_mb
        )
        result = temp_manager.cleanup()

        return jsonify({"message": "Cleanup completed", "result": result}), 200

    except Exception as e:
        print(f"Error during manual cleanup: {str(e)}")
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
        print(f"Error getting log stats: {str(e)}")
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
        print(f"Error deleting browser log file: {str(e)}")
        return jsonify({"error": "Failed to delete log file"}), 500
