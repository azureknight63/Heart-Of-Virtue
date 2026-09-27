"""Admin-only routes: the player analytics report.

There is no admin role in the database. Admin is an allow-list of account ids
in ``HOV_ADMIN_USER_IDS`` (comma-separated uuids; ``python tools/analytics.py
--whoami NAME`` prints one). Ids rather than usernames because registration is
open: a listed username with no account yet, or one freed later, could be
registered by anyone and would inherit the access. An id exists only once an
account does, and cannot be chosen.

A signed-in non-admin gets 404, not 403, and before any parameter validation,
so the route does not advertise itself to players.
"""

import logging
import os

from flask import Blueprint, jsonify, request

from src.api.db import db
from src.api.middleware.auth import resolve_session
from src.api.services.analytics import recorder
from src.api.services.analytics_report import (
    DEFAULT_WINDOW_DAYS,
    MAX_WINDOW_DAYS,
    build_report,
    executor_for,
)

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)

ADMIN_USER_IDS_ENV = "HOV_ADMIN_USER_IDS"


def is_admin(session):
    """True when ``session``'s account is listed.

    ``recorder.account_id`` reads the account through ``vars``, so the
    ``/api/test/session`` bypass (no account) and test doubles that answer
    every attribute are never admin.
    """
    allowed = {
        entry.strip()
        for entry in os.getenv(ADMIN_USER_IDS_ENV, "").split(",")
        if entry.strip()
    }
    account = recorder.account_id(session)
    return bool(account) and account in allowed


def _reader(session):
    """Who asked, for the audit log: the analytics pid, never the account id."""
    account = recorder.account_id(session)
    if not account:
        return "no-account"
    try:
        return recorder.pid_for(account)
    except Exception:
        return "unkeyed"


def _window_days():
    """``?days=`` as an int in 1..MAX_WINDOW_DAYS, or None when invalid."""
    raw = request.args.get("days")
    if raw is None:
        return DEFAULT_WINDOW_DAYS
    try:
        days = int(raw)
    except ValueError:
        return None
    return days if 1 <= days <= MAX_WINDOW_DAYS else None


@admin_bp.route("/admin/analytics", methods=["GET"])
async def analytics_report():
    """The full analytics report (``analytics_report.build_report``).

    Query: ``days`` (1..MAX_WINDOW_DAYS, default DEFAULT_WINDOW_DAYS), the
    window for the windowed sections.
    """
    _, session, error = resolve_session()
    if error:
        return error
    if not is_admin(session):
        logger.info("Admin analytics report refused (reader=%s)", _reader(session))
        return jsonify({"success": False, "error": "Not found"}), 404

    days = _window_days()
    if days is None:
        return jsonify({"success": False, "error": f"days must be 1-{MAX_WINDOW_DAYS}"}), 400

    try:
        report = await build_report(executor_for(db), days=days)
    except Exception as exc:
        # The type only, as the recorder's flush does: a libsql error can
        # carry the database URL, token included.
        logger.error("Analytics report failed (%s)", type(exc).__name__)
        return jsonify({"success": False, "error": "Report unavailable"}), 500

    # Who read it (pseudonymously), not what: the report is aggregate, the
    # read is privileged.
    logger.info("Admin analytics report served (reader=%s, days=%d)", _reader(session), days)
    response = jsonify({"success": True, "report": report})
    response.headers["Cache-Control"] = "no-store"
    return response
