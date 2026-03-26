"""
Browser logging API routes
Handles receiving and storing browser console logs
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import os
from pathlib import Path
from src.api.utils.log_cleanup import LogCleanupManager

logs_bp = Blueprint("logs", __name__)

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
        data = request.get_json()

        if not data or "logs" not in data:
            return jsonify({"error": "No logs provided"}), 400

        logs = data.get("logs", [])
        session_id = data.get("session_id", "unknown")

        if not logs:
            return jsonify({"message": "No logs to write"}), 200

        # Create a log file for today with session ID
        today = datetime.now().strftime("%Y-%m-%d")
        log_filename = f"{today}_{session_id}.log"
        log_filepath = LOGS_DIR / log_filename

        # Append logs to the file
        with open(log_filepath, "a", encoding="utf-8") as f:
            for log_entry in logs:
                timestamp = log_entry.get("timestamp", datetime.now().isoformat())
                level = log_entry.get("level", "LOG")
                message = log_entry.get("message", "")
                url = log_entry.get("url", "")

                # Format: [TIMESTAMP] [LEVEL] [URL] MESSAGE
                log_line = f"[{timestamp}] [{level}] [{url}] {message}\n"
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


@logs_bp.route("/browser/files/<filename>", methods=["GET"])
def get_browser_log_file(filename):
    """
    Retrieve the contents of a specific browser log file
    """
    try:
        # Sanitize filename to prevent directory traversal
        safe_filename = os.path.basename(filename)
        log_filepath = LOGS_DIR / safe_filename

        if not log_filepath.exists():
            return jsonify({"error": "Log file not found"}), 404

        with open(log_filepath, "r", encoding="utf-8") as f:
            content = f.read()

        return jsonify({"filename": safe_filename, "content": content}), 200

    except Exception as e:
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
    try:
        data = request.get_json() if request.is_json else {}

        # Create cleanup manager with custom settings if provided
        retention_days = data.get("retention_days", cleanup_manager.retention_days)
        max_size_mb = data.get(
            "max_size_mb", cleanup_manager.max_size_bytes / (1024 * 1024)
        )

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
    try:
        # Sanitize filename to prevent directory traversal
        safe_filename = os.path.basename(filename)
        log_filepath = LOGS_DIR / safe_filename

        if not log_filepath.exists():
            return jsonify({"error": "Log file not found"}), 404

        file_size = log_filepath.stat().st_size
        log_filepath.unlink()

        return (
            jsonify(
                {
                    "message": f"Successfully deleted {safe_filename}",
                    "deleted_size": file_size,
                }
            ),
            200,
        )

    except Exception as e:
        print(f"Error deleting browser log file: {str(e)}")
        return jsonify({"error": "Failed to delete log file"}), 500
