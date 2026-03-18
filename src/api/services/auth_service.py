import os
import uuid
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from typing import Optional, Dict, Any
from src.api.db import db
from datetime import datetime

class AuthService:
    def __init__(self):
        self.ph = PasswordHasher()
        # In a real production app, the encryption key should be in environment variables
        # If not present, we can generate one for now but it won't persist across restarts
        # if you want encrypted data to be readable later.
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        if not self.encryption_key:
            # Generate a consistent key based on SECRET_KEY if available, 
            # or just use a placeholder for now to avoid crashing in this demo.
            # RECOMMENDED: User should set ENCRYPTION_KEY.
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
        INSERT INTO users (id, username, password_hash, email_encrypted, is_premium)
        VALUES (?, ?, ?, ?, ?)
        """
        params = [user_id, username, password_hash, email_encrypted, False]
        
        await db.execute(sql, params)
        
        return {
            "id": user_id,
            "username": username,
            "is_premium": False
        }

    async def authenticate_user(self, username, password) -> Optional[Dict[str, Any]]:
        """Authenticate a user by username and password."""
        sql = "SELECT id, username, password_hash, is_premium FROM users WHERE username = ?"
        result = await db.execute(sql, [username])
        
        if not result.rows:
            return None
        
        user = result.rows[0]
        user_id, uname, p_hash, is_premium = user

        try:
            self.ph.verify(p_hash, password)
            # Rehash if needed
            if self.ph.check_needs_rehash(p_hash):
                new_hash = self.ph.hash(password)
                await db.execute("UPDATE users SET password_hash = ? WHERE id = ?", [new_hash, user_id])
            
            return {
                "id": str(user_id),
                "username": str(uname),
                "is_premium": bool(is_premium)
            }
        except Exception:
            return None

    async def get_user_by_id(self, user_id) -> Optional[Dict[str, Any]]:
        sql = "SELECT id, username, is_premium FROM users WHERE id = ?"
        result = await db.execute(sql, [user_id])
        if not result.rows:
            return None
        user = result.rows[0]
        return {
            "id": str(user[0]),
            "username": str(user[1]),
            "is_premium": bool(user[2])
        }

    def decrypt_email(self, encrypted_email: str) -> str:
        return self.fernet.decrypt(encrypted_email.encode()).decode()

auth_service = AuthService()
