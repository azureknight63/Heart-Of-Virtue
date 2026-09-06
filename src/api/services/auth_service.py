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

# Upper bounds on the three registration fields. ``create_user`` used to check
# minimums only, which left every one of them unbounded above:
#
# * ``password`` is fed to Argon2, which is *deliberately* expensive — its cost
#   is the defence. An unauthenticated caller supplying a multi-megabyte
#   password turns that defence into the attack: the hash is computed over the
#   whole string, on the request thread, in a single-worker deployment.
# * ``username`` and ``email`` are written to the database on a path that
#   is reachable without credentials, and the username is later interpolated
#   into a GitHub issue by ``routes/feedback.py``.
#
# The values: 64 is far above any name a person types and is what
# ``routes/feedback.py`` bounds its attribution label to; 128 accommodates a
# generated passphrase from any password manager while keeping the Argon2 input
# trivial; 254 is the maximum length of an email address in RFC 5321 §4.5.3.1.4.
#
# These are checked *before* the hash and the insert, and the request-body cap
# (``Config.MAX_CONTENT_LENGTH``) sits above them as the coarse bound on the
# payload that carries them.
MAX_USERNAME_LENGTH = 64
MAX_PASSWORD_LENGTH = 128
MAX_EMAIL_LENGTH = 254


class RegistrationValidationError(ValueError):
    """A registration input the caller supplied and can fix.

    The point of the type is that its *message is safe to echo* to an
    unauthenticated caller. ``routes/auth.py`` used to decide that by scanning
    the message for five substrings -- ``_URL``, ``_KEY``, ``_TOKEN``, "not
    set", "os.environ" -- and echoing anything that matched none of them. A
    deny-list over free-form exception text cannot be complete, and this one
    was not: a ``ValueError`` reading ``could not connect to
    postgres://svc:<password>@db.internal:5432/hov`` contains none of the five
    markers, so it was returned verbatim, credential included, in a 400 body
    to an anonymous POST /api/auth/register.

    Subclasses ``ValueError`` so existing callers and their
    ``pytest.raises(ValueError)`` assertions are unaffected; the route is what
    changed, and it now allow-lists this type instead of deny-listing text.
    Anything else out of :meth:`AuthService.create_user` is treated as
    infrastructure and masked, which is the safe default a deny-list can never
    give.
    """


class AuthService:
    def __init__(self):
        self.ph = PasswordHasher()
        # Mirrors the SECRET_KEY *rule* in src/api/config.py: production must
        # set ENCRYPTION_KEY explicitly (an ephemeral key would silently orphan
        # already-encrypted data — e.g. user emails — on every restart). Testing
        # and development fall back to a generated key so the suite/dev server
        # don't need one configured.
        #
        # It does NOT mirror the timing, and that difference is the fragile
        # part. config.py deliberately moved its guard off import time into
        # runtime_config(), which create_app() calls — the entire premise of
        # that module's docstring. This one still runs at *import* time,
        # because the `auth_service = AuthService()` singleton at the bottom of
        # this file is built in the module body. It reads the right value only
        # because `from src.api.db import db` at the top of this file happens
        # to load .env first: the same incidental-import dependency that
        # src/api/rate_limiter.py's module-level load_project_env() exists to
        # remove. Reordering that import would silently move this read ahead of
        # the .env load. Deferring the check into a lazily-built singleton is
        # the real fix; until then, do not reorder the imports above.
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        if not self.encryption_key:
            # normalized_env(), not a bare == "production": this guard is
            # fail-open, so a case difference silently costs data. FLASK_ENV is
            # operator-typed and both entry points that select the config class
            # lowercase it, so "Production" reaches here and, compared raw,
            # skips this raise and mints an ephemeral Fernet key — orphaning
            # every already-encrypted email on the next restart, with nothing
            # reporting the loss. src/api/config.py's SECRET_KEY guard, which
            # the comment above says this mirrors, had the identical defect and
            # was normalised; sharing the helper is what stops them drifting
            # apart a third time.
            from src.api.config import normalized_env

            if normalized_env() == "production":
                raise RuntimeError("ENCRYPTION_KEY must be set in production")
            self.encryption_key = Fernet.generate_key()
        self.fernet = Fernet(self.encryption_key)

    async def create_user(self, username, password, email) -> Dict[str, Any]:
        """Create a new user in the database."""
        # Validation. Every bound is enforced here, before the Argon2 hash and
        # before the insert — see the MAX_* constants for why the maximums are
        # not optional.
        if len(username) < 4:
            raise RegistrationValidationError("Username must be at least 4 characters")
        if len(username) > MAX_USERNAME_LENGTH:
            raise RegistrationValidationError(
                "Username must be at most %d characters" % MAX_USERNAME_LENGTH
            )
        if len(password) < 16:
            raise RegistrationValidationError("Password must be at least 16 characters")
        if len(password) > MAX_PASSWORD_LENGTH:
            raise RegistrationValidationError(
                "Password must be at most %d characters" % MAX_PASSWORD_LENGTH
            )
        if len(email) > MAX_EMAIL_LENGTH:
            raise RegistrationValidationError(
                "Email must be at most %d characters" % MAX_EMAIL_LENGTH
            )

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
