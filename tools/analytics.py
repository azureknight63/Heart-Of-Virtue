"""Print the player analytics report: players, retention, progress, combat, chat.

The same report as the admin page (GET /api/admin/analytics) and the Discord
digest's Players section; definitions of every number are in
src/api/services/analytics_report.py.

Usage:
    python tools/analytics.py              # last 30 days, as text
    python tools/analytics.py --days 7
    python tools/analytics.py --json       # the raw report, for scripts and agents
    python tools/analytics.py --whoami NAME
                                           # the account id to put in HOV_ADMIN_USER_IDS

Reads TURSO_DATABASE_URL / TURSO_AUTH_TOKEN from the project .env. Point them
at production to read production; everything here only runs SELECTs.
"""

import argparse
import json
import sys
from pathlib import Path


def _load_report_api():
    """``analytics_report`` with the project importable and .env loaded."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.env_bootstrap import load_project_env
    from src.api.services import analytics_report

    load_project_env()
    return analytics_report


def _account_id(report_api, username):
    """The account id for an exact ``username``, or None."""
    rows = report_api.run_query("SELECT id FROM users WHERE username = ?", [username])
    return rows[0][0] if rows else None


def main(argv=None, out=None, err=None):
    report_api = _load_report_api()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--days", type=int, default=report_api.DEFAULT_WINDOW_DAYS,
        help="window in days, 1-%d (default %d)"
        % (report_api.MAX_WINDOW_DAYS, report_api.DEFAULT_WINDOW_DAYS),
    )
    parser.add_argument("--json", action="store_true", help="print the raw report as JSON")
    parser.add_argument("--whoami", metavar="USERNAME", help="print that account's id and exit")
    args = parser.parse_args(argv)
    if not 1 <= args.days <= report_api.MAX_WINDOW_DAYS:
        parser.error("--days must be 1-%d" % report_api.MAX_WINDOW_DAYS)

    out, err = out or sys.stdout, err or sys.stderr
    from src.api.db import DatabaseNotConfigured  # importable once _load_report_api has run

    try:
        if args.whoami:
            account = _account_id(report_api, args.whoami)
            if not account:
                print("No account named %r." % args.whoami, file=err)
                return 1
            print(account, file=out)
            return 0
        report = report_api.fetch_report(days=args.days)
    except DatabaseNotConfigured as exc:
        # Its text names the missing setting and carries no secret.
        print("Analytics report failed: %s" % exc, file=err)
        return 1
    except Exception as exc:
        # The type only: a libsql connection error can echo the database URL,
        # which may carry an auth token.
        print("Analytics report failed: %s" % type(exc).__name__, file=err)
        return 1

    if args.json:
        print(json.dumps(report, indent=2), file=out)
    else:
        print(report_api.format_text(report), file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
