import asyncio
import logging
from src.api.db import db

logger = logging.getLogger(__name__)


async def init_db():
    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email_encrypted TEXT NOT NULL,
            is_premium BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            timezone TEXT DEFAULT 'America/New_York'
        );
        """,
        """
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
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """,
        # Index for faster lookup of user saves
        "CREATE INDEX IF NOT EXISTS idx_saves_user_id ON saves(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);",
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
        print(f"Error initializing database: {e}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(init_db())
