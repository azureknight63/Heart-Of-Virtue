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
        with open(log_filepath, "a", encoding="utf-8") as f:
            for log_entry in logs:
                # Hostile payloads may include non-dict entries (e.g. bare
                # strings); skip them instead of raising.
                if not isinstance(log_entry, dict):
                    continue
                timestamp = str(
                    log_entry.get("timestamp", datetime.now().isoformat())
                )[:MAX_SHORT_FIELD_LENGTH]
                level = str(log_entry.get("level", "LOG"))[:MAX_SHORT_FIELD_LENGTH]
                message = str(log_entry.get("message", ""))[:MAX_MESSAGE_LENGTH]
                url = str(log_entry.get("url", ""))[:MAX_FIELD_LENGTH]

                # Format: [TIMESTAMP] [LEVEL] [SESSION] [URL] MESSAGE
                log_line = (
                    f"[{timestamp}] [{level}] [{session_id}] [{url}] {message}\n"
                )
                f.write(log_line)

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
