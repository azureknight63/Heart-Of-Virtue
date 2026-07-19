import os
import uuid
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from typing import Optional, Dict, Any
from src.api.db import db

# Static dummy Argon2 hash used to equalize timing when a username lookup
# misses. Verifying against this constant hash costs roughly the same as
# verifying a real one, so an attacker can't distinguish "unknown username"
# from "wrong password" by measuring response time (username-enumeration
# side-channel). The password behind this hash is never used for anything.
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$dn4DipiMg0kHqj/17Tq8lA$"
    "7KbniMDtZdj7bd8jcqYNPc4AUaZL3Wb7k3WpG2rg18g"
)


class AuthService:
    def __init__(self):
        self.ph = PasswordHasher()
        # Mirrors the SECRET_KEY handling in src/api/config.py: production must
        # set ENCRYPTION_KEY explicitly (an ephemeral key would silently orphan
        # already-encrypted data — e.g. user emails — on every restart). Testing
        # and development fall back to a generated key so the suite/dev server
        # don't need one configured.
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        if not self.encryption_key:
            if os.environ.get("FLASK_ENV") == "production":
                raise RuntimeError("ENCRYPTION_KEY must be set in production")
            self.encryption_key = Fernet.generate_key()
        self.fernet = Fernet(self.encryption_key)

    async def create_user(self, username, password, email) -> Dict[str, Any]:
        """Create a new user in the database."""
        # Validation
        if len(username) < 4:
            raise ValueError("Username must be at least 4 characters")
        if len(password) < 16:
            raise ValueError("Password must be at least 16 characters")

        user_id = str(uuid.uuid4())
        password_hash = self.ph.hash(password)
        email_encrypted = self.fernet.encrypt(email.encode()).decode()

        sql = """
        INSERT INTO users (id, username, password_hash, email_encrypted, is_premium, timezone)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params = [
            user_id,
            username,
            password_hash,
            email_encrypted,
            False,
            "America/New_York",
        ]

        await db.execute(sql, params)

        return {
            "id": user_id,
            "username": username,
            "is_premium": False,
            "timezone": "America/New_York",
        }

    async def authenticate_user(self, username, password) -> Optional[Dict[str, Any]]:
        """Authenticate a user by username and password."""
        sql = "SELECT id, username, password_hash, is_premium, timezone FROM users WHERE username = ?"
        result = await db.execute(sql, [username])

        if not result.rows:
            # Username not found: still run a full Argon2 verify against a
            # static dummy hash so this path takes comparable time to the
            # "username exists" path below. Without this, response timing
            # alone would let an attacker enumerate valid usernames.
            try:
                self.ph.verify(_DUMMY_PASSWORD_HASH, password)
            except Exception:
                pass
            return None

        user = result.rows[0]
        user_id, uname, p_hash, is_premium, timezone = user

        try:
            self.ph.verify(p_hash, password)
            # Rehash if needed
            if self.ph.check_needs_rehash(p_hash):
                new_hash = self.ph.hash(password)
                await db.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    [new_hash, user_id],
                )

            return {
                "id": str(user_id),
                "username": str(uname),
                "is_premium": bool(is_premium),
                "timezone": str(timezone) if timezone else "America/New_York",
            }
        except Exception:
            return None

    async def get_user_by_id(self, user_id) -> Optional[Dict[str, Any]]:
        sql = "SELECT id, username, is_premium, timezone FROM users WHERE id = ?"
        result = await db.execute(sql, [user_id])
        if not result.rows:
            return None
        user = result.rows[0]
        return {
            "id": str(user[0]),
            "username": str(user[1]),
            "is_premium": bool(user[2]),
            "timezone": str(user[3]) if len(user) > 3 and user[3] else "America/New_York",
        }

    async def update_user_timezone(self, user_id: str, timezone: str) -> bool:
        """Update a user's timezone."""
        sql = "UPDATE users SET timezone = ? WHERE id = ?"
        result = await db.execute(sql, [timezone, user_id])
        return result.rows_affected > 0

    def decrypt_email(self, encrypted_email: str) -> str:
        return self.fernet.decrypt(encrypted_email.encode()).decode()


auth_service = AuthService()
