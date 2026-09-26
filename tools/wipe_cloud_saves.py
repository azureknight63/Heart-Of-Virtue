"""Clear every cloud save before beta 2 opens.

Beta 2 starts after the April-era saves end in the game timeline, and those
saves predate the strict unpickler and ~1,650 commits of engine changes, so the
maintainer chose to start everyone fresh rather than migrate them. Run this on
the server while the maintenance page is up and before players are let back in,
so no beta-2 save is ever caught by it.

    python tools/wipe_cloud_saves.py                     # dry run: counts only
    python tools/wipe_cloud_saves.py --confirm "<phrase>"   # deletes

Without ``--confirm`` it only reports. With anything other than the exact
phrase it refuses. It deletes rows from ``saves`` and nothing else: accounts
are untouched. The database is whatever ``TURSO_DATABASE_URL`` points at (read
from ``.env`` by ``src.api.db``); only its host is printed, never a credential.
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

CONFIRM_PHRASE = "DELETE ALL CLOUD SAVES"

_SUMMARY_SQL = (
    "SELECT COUNT(*), "
    "COALESCE(SUM(CASE WHEN is_autosave THEN 1 ELSE 0 END), 0), "
    "MIN(timestamp), MAX(timestamp) FROM saves"
)
_PER_USER_SQL = "SELECT user_id, COUNT(*) FROM saves GROUP BY user_id"
_DELETE_SQL = "DELETE FROM saves"


def database_host(url):
    """The host[:port] of a database URL, with any user, password or query dropped."""
    if not url:
        return "(unset)"
    parts = urlsplit(url)
    host = parts.hostname or "(unparseable)"
    try:
        port = parts.port
    except ValueError:  # a non-numeric port; the host alone is still useful
        port = None
    return f"{host}:{port}" if port else host


async def _report(db, out):
    total, autosaves, oldest, newest = (await db.execute(_SUMMARY_SQL)).rows[0]
    users = (await db.execute(_PER_USER_SQL)).rows
    print(f"{total} saves ({autosaves} autosaves) across {len(users)} users", file=out)
    if total:
        print(f"  oldest {oldest}, newest {newest}", file=out)
        busiest = max(count for _user, count in users)
        print(f"  most saves held by one user: {busiest}", file=out)
    return total


async def run(db, confirm=None, out=sys.stdout):
    """Report the saves table, and delete it only when ``confirm`` is the exact phrase.

    Returns a process exit code: 0 for a dry run or a completed wipe, 2 for a
    refused confirmation.
    """
    total = await _report(db, out)
    if confirm is None:
        print(f'Dry run. To delete, re-run with --confirm "{CONFIRM_PHRASE}"', file=out)
        return 0
    if confirm != CONFIRM_PHRASE:
        print(f'Saves not deleted: the confirmation did not match "{CONFIRM_PHRASE}".', file=out)
        return 2
    await db.execute(_DELETE_SQL)
    print(f"Deleted {total} saves. Now:", file=out)
    await _report(db, out)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--confirm", help=f'the exact phrase "{CONFIRM_PHRASE}"')
    args = parser.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.api.db import db  # loads .env; must follow the sys.path insert

    print(f"Database: {database_host(os.getenv('TURSO_DATABASE_URL'))}")

    async def _go():
        try:
            return await run(db, confirm=args.confirm)
        finally:
            await db.close()

    return asyncio.run(_go())


if __name__ == "__main__":
    sys.exit(main())
