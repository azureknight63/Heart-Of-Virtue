"""
Feedback API routes
Handles in-game player feedback and creates GitHub issues.
"""
import os
import re
import time
import logging
import requests
from collections import defaultdict
from flask import Blueprint, request, jsonify

def get_session_and_player(request):
    """Extract session and player from request.

    Returns:
        Tuple of (session_manager, session, player, None) on success
        or (None, None, None, (jsonify_response, status_code)) on error
    """
    from flask import current_app

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None, None, (jsonify({"error": "Missing authorization"}), 401)

    session_id = auth_header[7:]
    session_manager = current_app.session_manager

    session = session_manager.get_session(session_id)
    if not session:
        return None, None, None, (jsonify({"error": "Invalid or expired session"}), 401)

    player = session_manager.get_player(session_id)
    if not player:
        return None, None, None, (jsonify({"error": "Player not found"}), 404)

    return session_manager, session, player, None

logger = logging.getLogger(__name__)

feedback_bp = Blueprint("feedback", __name__)

GITHUB_API_URL = "https://api.github.com"
GITHUB_REPO = "azureknight63/heart-of-virtue"

LABEL_MAP = {
    "bug": ["bug", "player-report"],
    "feature": ["enhancement", "player-report"],
    "general": ["feedback", "player-report"],
}

SEVERITY_EMOJI = {
    "low": "🟡",
    "medium": "🟠",
    "high": "🔴",
}

STAR_BLOCK = "⭐"

MAX_TITLE_LENGTH = 256
MAX_FIELD_LENGTH = 2000
_MARKDOWN_UNSAFE = re.compile(r"[*_`\[\]()#\\]")

# Simple in-memory rate limiter: 10 submissions per session per hour.
# Per-worker (not shared across Gunicorn workers) — sufficient for beta.
_RATE_LIMIT = 10
_RATE_WINDOW = 3600  # seconds
_rate_limit_store: dict = defaultdict(list)


def _is_rate_limited(session_id: str) -> bool:
    now = time.time()
    cutoff = now - _RATE_WINDOW
    hits = [t for t in _rate_limit_store[session_id] if t > cutoff]
    _rate_limit_store[session_id] = hits
    if len(hits) >= _RATE_LIMIT:
        return True
    _rate_limit_store[session_id].append(now)
    return False


def _build_bug_body(fields, attribution):
    steps = fields.get("steps", "").strip()
    expected = fields.get("expected", "").strip()
    actual = fields.get("actual", "").strip()
    severity = fields.get("severity", "medium").lower()
    emoji = SEVERITY_EMOJI.get(severity, "🟠")

    return (
        "## Bug Report\n\n"
        f"**Severity:** {emoji} {severity.capitalize()}\n\n"
        "**Steps to Reproduce:**\n"
        f"{steps or '_Not provided_'}\n\n"
        "**Expected Behavior:**\n"
        f"{expected or '_Not provided_'}\n\n"
        "**Actual Behavior:**\n"
        f"{actual or '_Not provided_'}\n\n"
        "---\n"
        f"*{attribution}*"
    )


def _build_feature_body(fields, attribution):
    description = fields.get("description", "").strip()
    use_case = fields.get("use_case", "").strip()

    return (
        "## Feature Request\n\n"
        "**Description:**\n"
        f"{description or '_Not provided_'}\n\n"
        "**Use Case / Why:**\n"
        f"{use_case or '_Not provided_'}\n\n"
        "---\n"
        f"*{attribution}*"
    )


def _build_rating_row(label, value):
    """Render a star rating row as filled/empty stars."""
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    if not 1 <= score <= 5:
        return None
    filled = STAR_BLOCK * score
    empty = "☆" * (5 - score)
    return f"| {label} | {filled}{empty} | {score}/5 |"


def _build_general_body(fields, attribution):
    message = fields.get("message", "").strip()
    ratings = fields.get("ratings", {})

    body = "## General Feedback\n\n"
    body += f"{message or '_No message provided_'}\n\n"

    dimension_labels = {
        "story": "Story & Narrative",
        "combat": "Combat & Gameplay",
        "audio": "Audio & Music",
        "visuals": "Visuals & Aesthetics",
        "difficulty": "Difficulty & Balance",
    }

    rating_rows = []
    for key, label in dimension_labels.items():
        value = ratings.get(key)
        if value is not None:
            row = _build_rating_row(label, value)
            if row:
                rating_rows.append(row)

    if rating_rows:
        body += "### Ratings\n\n"
        body += "| Dimension | Rating | Score |\n"
        body += "|---|---|---|\n"
        body += "\n".join(rating_rows) + "\n\n"

    body += "---\n"
    body += f"*{attribution}*"
    return body


def _create_github_issue(title, body, labels):
    """POST to GitHub Issues API. Returns (issue_url, error_message)."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN not set; cannot create feedback issue")
        return None, "Feedback service is not configured on this server."

    url = f"{GITHUB_API_URL}/repos/{GITHUB_REPO}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"title": title, "body": body, "labels": labels}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
    except requests.exceptions.RequestException as exc:
        logger.error("GitHub API request failed: %s", exc)
        return None, "Could not reach GitHub. Please try again later."

    if resp.status_code == 201:
        return resp.json().get("html_url"), None

    logger.error("GitHub API returned %s", resp.status_code)
    return None, "GitHub rejected the submission. Please try again later."


@feedback_bp.route("/issue", methods=["POST"])
def submit_feedback():
    """
    Create a GitHub issue from in-game player feedback.

    Expected payload:
    {
        "type": "bug" | "feature" | "general",
        "title": "Short descriptive title",
        "anonymous": false,
        "fields": {
            // bug: steps, expected, actual, severity
            // feature: description, use_case
            // general: message, ratings: {story, combat, audio, visuals, difficulty}
        }
    }
    """
    session_manager, session, player, error = get_session_and_player(request)
    if error:
        return error[0], error[1]

    if _is_rate_limited(session.session_id):
        return jsonify({"success": False, "error": "Too many feedback submissions. Please wait before trying again."}), 429

    username = _MARKDOWN_UNSAFE.sub("", getattr(player, "name", "Unknown Player"))

    data = request.get_json(silent=True) or {}
    feedback_type = data.get("type", "").lower()
    title = (data.get("title") or "").strip()
    anonymous = bool(data.get("anonymous", False))
    fields = data.get("fields") or {}
    if not isinstance(fields, dict):
        fields = {}

    if feedback_type not in ("bug", "feature", "general"):
        return jsonify({"success": False, "error": "Invalid feedback type"}), 400

    if not title:
        return jsonify({"success": False, "error": "Title is required"}), 400

    if len(title) > MAX_TITLE_LENGTH:
        return jsonify({"success": False, "error": f"Title must be {MAX_TITLE_LENGTH} characters or fewer"}), 400

    # Truncate oversized text fields to avoid enormous GitHub issues
    fields = {k: (v[:MAX_FIELD_LENGTH] if isinstance(v, str) else v) for k, v in fields.items()}

    attribution = "Submitted anonymously via in-game feedback" if anonymous else f"Submitted in-game by: **{username}**"

    if feedback_type == "bug":
        body = _build_bug_body(fields, attribution)
    elif feedback_type == "feature":
        body = _build_feature_body(fields, attribution)
    else:
        body = _build_general_body(fields, attribution)

    labels = LABEL_MAP[feedback_type]
    issue_url, err = _create_github_issue(title, body, labels)

    if err:
        return jsonify({"success": False, "error": err}), 503

    return jsonify({"success": True, "issue_url": issue_url}), 201
