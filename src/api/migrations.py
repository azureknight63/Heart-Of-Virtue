import asyncio
from src.api.db import db


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
            timezone TEXT DEFAULT 'US/Eastern'
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

        # Add timezone column for existing databases (will fail harmlessly if already exists)
        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN timezone TEXT DEFAULT 'US/Eastern'"
            )
        except Exception:
            pass

        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(init_db())
