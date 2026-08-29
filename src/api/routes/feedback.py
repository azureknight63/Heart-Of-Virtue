"""
Feedback API routes
Handles in-game player feedback and creates GitHub issues.
"""

import os
import re
import logging
import requests
from flask import Blueprint, request, jsonify
from src.api.middleware.auth import get_session_and_player
from src.api.rate_limiter import (
    RateLimiter,
    client_ip,
    limiter_from_env,
    rate_limited_response,
)


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

# Zero-width space. Inserted after a sigil so GitHub stops treating it as a
# cross-reference while a human still reads the text unchanged.
_ZWSP = "​"

# The constructs that make GitHub *act* on player-supplied text rather than
# merely display it: "@name" notifies a real account, an issue reference
# cross-links (and back-links) a real issue, and a link whose visible label can
# disagree with its destination is a phishing primitive. Everything else about
# the player's prose is left alone deliberately — see
# _neutralise_github_markup.
#
# The issue-reference spellings below are the ones GitHub's "Autolinked
# references and URLs" doc lists as producing the *same* autolink: "#26",
# "GH-26", "jlord/sheetsee.js#26", and the full
# "https://github.com/jlord/sheetsee.js/issues/26" URL. A word-boundary rule
# on "#" alone caught only the first of the four — "owner/repo#26" has an
# alphanumeric immediately before the "#" and sailed through the lookbehind.
# The raw-HTML rule covers the subset GitHub renders rather than escapes:
# "<a href>" is the same label-vs-destination hazard as "](", and "<details>"
# is documented under "Organizing information with collapsed sections".
#
# Deliberately NOT defused, so the next reader knows it was weighed rather
# than missed: bare 40-character commit SHAs and the "user@sha" /
# "owner/repo@sha" forms. Those autolink too, but a 40-hex run is exactly what
# a pasted stack trace or save hash looks like, and a commit link does not
# write into the issue tracker the way an issue cross-reference does.
#
# Every alternative is written so the character to defuse is the LAST one
# consumed, because the substitution appends the zero-width space to the whole
# match; context that must survive intact is expressed as a lookaround.
_GITHUB_ACTIVATORS = re.compile(
    r"""
      (?<![0-9A-Za-z_])[@#](?=[0-9A-Za-z])            # @mention, #123
    | (?<![0-9A-Za-z_])(?i:gh)(?=-[0-9])              # GH-123
    | (?<![0-9A-Za-z_./-])
      [0-9A-Za-z_.-]+/[0-9A-Za-z_.-]+\#(?=[0-9])      # owner/repo#123
    | (?<![0-9A-Za-z_])(?i:github)                    # .../issues/123 URLs
      (?=\.com/[0-9A-Za-z_.-]+/[0-9A-Za-z_.-]+/(?:issues|pull|commit)/)
    | \](?=[(\[:])                                    # ](url)  [a][b]  [b]: url
    | <(?=[A-Za-z/!])                                 # <a href=...>, <details>
    """,
    re.VERBOSE,
)

# Control characters that have no business in an issue body. Newline, tab and
# carriage return are kept; ESC (which would otherwise reach any terminal that
# cats the issue) and the rest are not.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _neutralise_github_markup(text: str) -> str:
    """Defuse the GitHub markup that *acts*, leaving prose readable.

    Player-supplied field values are interpolated verbatim into an issue body
    on a repo the player does not own, so ``@maintainer`` notified a real
    person and ``#123`` posted a back-reference onto a real issue — a write
    into the project's tracker from an authenticated game client.

    The title is scrubbed with :data:`_MARKDOWN_UNSAFE` and
    :data:`_CONTROL_CHARS` instead, because it is a short label and losing its
    punctuation costs nothing — and because GitHub renders a title as plain
    text, so it has no activation to defuse. Doing the same to a bug report's
    *body* would be a bad trade: it strips parentheses,
    underscores and backticks out of the reproduction steps the report exists
    to convey. So the bodies get this narrower rule, which removes the
    activation and keeps the text.

    The username gets *both*: :data:`_MARKDOWN_UNSAFE` first, then this. That
    regex contains no ``@``, and ``AuthService.create_user`` validates a
    username on length alone, so ``@azureknight63`` is a registrable account
    name and every non-anonymous submission from it mentioned a real person.
    """
    text = _CONTROL_CHARS.sub("", text)
    # The zero-width space goes *after* the whole match: every alternative in
    # _GITHUB_ACTIVATORS ends on the character being defused.
    return _GITHUB_ACTIVATORS.sub(lambda m: m.group(0) + _ZWSP, text)


# Simple in-memory rate limiter: 10 submissions per client per hour.
# Per-worker (not shared across Gunicorn workers) — see GitHub issue #284 and
# `src.api.rate_limiter` for the bounded-store rationale, the `None`-tolerant
# `RateLimiter.check` and the shared 429 body, all of which auth.py's login
# throttles and npc_chat.py's chat throttles use too.
# Override with FEEDBACK_RATE_LIMIT_PER_HOUR; 0 disables the limiter — which is
# why `_is_rate_limited` spends this budget through `RateLimiter.check` rather
# than dereferencing the limiter directly.
_RATE_LIMIT = 10
_RATE_WINDOW = 3600  # seconds
_feedback_limiter = limiter_from_env(
    "FEEDBACK_RATE_LIMIT_PER_HOUR", _RATE_LIMIT, _RATE_WINDOW
)


def _throttle_keys(session) -> list:
    """The identities a feedback submission is counted against.

    **Not the session id.** This throttle guards *real GitHub issue creation*,
    and a session id is minted by the client at will: every ``/auth/login``
    returns a fresh one, so the cap was bypassed simply by re-authenticating
    between submissions. ``client_ip()`` is not client-selectable (see
    ``src/api/app.py::_apply_proxy_fix`` for the one case where a header can
    influence it, which is off by default), so it is the tier that actually
    holds.

    The account tier is added on top when the session is linked to a DB user:
    it survives an IP change, which the IP tier does not.
    """
    keys = ["ip:%s" % client_ip()]
    db_user_id = getattr(session, "db_user_id", None)
    if db_user_id is not None:
        keys.append("user:%s" % db_user_id)
    return keys


def _is_rate_limited(session) -> bool:
    """True if this client has spent its submission budget.

    Counts the call against every tier unless that tier is already limited.

    ``FEEDBACK_RATE_LIMIT_PER_HOUR=0`` is a documented disable, and
    ``limiter_from_env`` expresses it by returning ``None``, so the ``None``
    case here is load-bearing rather than defensive. It is spelled
    ``RateLimiter.check`` rather than an ``is None`` test of this module's own
    because that polarity is easy to invert — a disabled tier read as a tripped
    one would 429 every submission — and the module that invented ``None``
    owns the rule for reading it. auth.py and npc_chat.py spend their budgets
    the same way.
    """
    # List, not a generator: `any` short-circuits, and a short-circuit here
    # would leave the second tier uncounted whenever the first one tripped.
    return any(
        [
            RateLimiter.check(_feedback_limiter, key)
            for key in _throttle_keys(session)
        ]
    )


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


_STRING_FIELD_KEYS_BY_TYPE = {
    "bug": ("steps", "expected", "actual", "severity"),
    "feature": ("description", "use_case"),
    "general": ("message",),
}


def _validate_fields_for_type(feedback_type, fields):
    """Validate the types of values inside the ``fields`` payload.

    ``submit_feedback`` only checks that ``fields`` itself is a dict. The
    ``_build_*_body`` helpers then call ``.strip()``/``.lower()``/``.get()``
    on specific entries assuming they are strings (or, for ``ratings``, a
    dict) — a wrong-typed value (e.g. ``{"steps": 123}`` or
    ``{"ratings": "nope"}``) would raise ``AttributeError`` deep in the
    builder and surface as a 500. Reject it here as a 400 instead.

    Args:
        feedback_type: One of "bug", "feature", "general".
        fields: The ``fields`` dict from the request body.

    Returns:
        An error message string, or ``None`` if all present values type-check.
    """
    for key in _STRING_FIELD_KEYS_BY_TYPE.get(feedback_type, ()):
        value = fields.get(key)
        if value is not None and not isinstance(value, str):
            return f"fields.{key} must be a string"

    if feedback_type == "general":
        ratings = fields.get("ratings")
        if ratings is not None and not isinstance(ratings, dict):
            return "fields.ratings must be an object"

    return None


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
    session_manager, session, player, error = get_session_and_player()
    if error:
        return error

    if _is_rate_limited(session):
        return rate_limited_response(
            "Too many feedback submissions. Please wait before trying again."
        )

    try:
        # Both scrubs, in this order. `_MARKDOWN_UNSAFE` is the blunt one a
        # short label can afford; `_neutralise_github_markup` then handles the
        # activators that regex has no character for — chiefly `@`, which
        # matters because `AuthService.create_user` validates a username on
        # length alone, so `@azureknight63` is registrable and reached the
        # attribution line of every non-anonymous issue as a live mention.
        # It strips control characters from the label as well.
        username = _neutralise_github_markup(
            _MARKDOWN_UNSAFE.sub("", getattr(session, "username", "Unknown Player"))
        )

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            data = {}
        raw_type = data.get("type", "")
        feedback_type = raw_type.lower() if isinstance(raw_type, str) else ""
        raw_title = data.get("title") or ""
        # GitHub renders an issue *title* as plain text — no markdown, no
        # autolinks — so the `_MARKDOWN_UNSAFE` scrub here is tidiness and
        # defence in depth, NOT the thing standing between a title and a live
        # mention. (The comment that used to sit here claimed otherwise. A
        # title cannot carry a mention or a cross-reference in the first
        # place, which is why no `_neutralise_github_markup` pass is added.)
        #
        # `_CONTROL_CHARS` is a different matter, and its absence here was a
        # real asymmetry: field *bodies* have had ESC and friends stripped
        # since `_neutralise_github_markup` existed, while a title carried
        # them straight into the tracker — and into every terminal that
        # later cats the issue.
        title = (
            _CONTROL_CHARS.sub("", _MARKDOWN_UNSAFE.sub("", raw_title)).strip()
            if isinstance(raw_title, str)
            else ""
        )
        anonymous = bool(data.get("anonymous", False))
        fields = data.get("fields") or {}
        if not isinstance(fields, dict):
            fields = {}

        if feedback_type not in ("bug", "feature", "general"):
            return jsonify({"success": False, "error": "Invalid feedback type"}), 400

        if not title:
            return jsonify({"success": False, "error": "Title is required"}), 400

        if len(title) > MAX_TITLE_LENGTH:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Title must be {MAX_TITLE_LENGTH} characters or fewer",
                    }
                ),
                400,
            )

        # Truncate oversized text fields to avoid enormous GitHub issues, then
        # defuse the markup GitHub would act on. Truncation runs first so the
        # bound applies to what the player actually wrote; the neutralising
        # pass adds at most one zero-width character per activator.
        fields = {
            k: (
                _neutralise_github_markup(v[:MAX_FIELD_LENGTH])
                if isinstance(v, str)
                else v
            )
            for k, v in fields.items()
        }

        field_type_error = _validate_fields_for_type(feedback_type, fields)
        if field_type_error:
            return jsonify({"success": False, "error": field_type_error}), 400

        attribution = (
            "Submitted anonymously via in-game feedback"
            if anonymous
            else f"Submitted in-game by: **{username}**"
        )

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

    except Exception:
        logger.exception("Unhandled error in submit_feedback")
        return (
            jsonify({"success": False, "error": "An internal error occurred"}),
            500,
        )
