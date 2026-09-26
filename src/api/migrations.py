import asyncio
import logging
from src.api.db import db
from src.api.services.analytics import SCHEMA_STATEMENTS as ANALYTICS_SCHEMA

logger = logging.getLogger(__name__)


def _warn(message):
    """Report a handled failure through the app logger, without ever raising.

    These call sites all sit inside an ``except`` block, and they used to call
    ``print``. ``print`` is not exception-free -- ``UnicodeEncodeError`` on a
    cp1252 Windows console, ``ValueError`` on a stdout a WSGI server has closed
    -- so a diagnostic could escape the very handler written to swallow the
    fault it was describing.

    The logger, not stdout, for the second half of the same reason: every
    handler this app installs carries ``_RedactSecretsFilter`` (see
    ``src/api/app.py``), and ``print``/``traceback.print_exc`` bypass it
    entirely. ``handlers/error_handler.py`` was moved off ``print_exc`` for
    that reason and these were left behind.
    """
    try:
        logger.warning("%s", message)
    except Exception:  # pragma: no cover - a diagnostic must not have a fault
        pass


# The two core tables, as constants so tests can build the real schema
# (tests/test_analytics_report.py) instead of a drifting copy of it.
USERS_TABLE = """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email_encrypted TEXT NOT NULL,
            is_premium BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            timezone TEXT DEFAULT 'America/New_York'
        );
        """

SAVES_TABLE = """
        CREATE TABLE IF NOT EXISTS saves (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            data BLOB NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_autosave BOOLEAN DEFAULT FALSE,
            level INTEGER,
            map_name TEXT,
            room_title TEXT,
            playtime INTEGER,
            location_x INTEGER,
            location_y INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """


async def init_db():
    statements = [
        USERS_TABLE,
        SAVES_TABLE,
        # Index for faster lookup of user saves
        "CREATE INDEX IF NOT EXISTS idx_saves_user_id ON saves(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);",
        # Player analytics. The recorder also creates these on its first flush,
        # so a deploy that skips this script still records.
        *ANALYTICS_SCHEMA,
    ]

    print("Initializing database...")
    try:
        await db.batch(statements)

        # Add columns for existing databases (will fail harmlessly if already exist)
        backfill = [
            "ALTER TABLE users ADD COLUMN timezone TEXT DEFAULT 'America/New_York'",
            "ALTER TABLE saves ADD COLUMN level INTEGER",
            "ALTER TABLE saves ADD COLUMN map_name TEXT",
            "ALTER TABLE saves ADD COLUMN room_title TEXT",
            "ALTER TABLE saves ADD COLUMN playtime INTEGER",
            # The tile, so reports can tell apart rooms that share a name.
            "ALTER TABLE saves ADD COLUMN location_x INTEGER",
            "ALTER TABLE saves ADD COLUMN location_y INTEGER",
        ]
        for stmt in backfill:
            try:
                await db.execute(stmt)
            except Exception as e:
                # SQLite/libsql reports pre-existing columns as a duplicate-column
                # error; that case is expected on every run after the first and
                # should be swallowed silently. Anything else is a genuine
                # migration failure and must not be hidden, or it will only
                # resurface later as an opaque 500 in the saves routes.
                message = str(e).lower()
                if "duplicate column" in message or "already exists" in message:
                    pass
                else:
                    logger.error(
                        "Backfill migration statement failed: %s | statement=%s",
                        e,
                        stmt,
                    )

        print("Database initialized successfully.")
    except Exception as e:
        _warn(f"Error initializing database: {e}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(init_db())
