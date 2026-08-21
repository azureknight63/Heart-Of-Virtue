"""
Tests for:
- src/api/services/auth_service.py (validation logic and encrypt/decrypt, no DB)
"""

import os
import uuid
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

# ===========================================================================
# AuthService — tested in isolation (no DB calls)
# ===========================================================================


class TestAuthServiceInit:
    """Test that AuthService can be constructed with/without env key."""

    def test_init_generates_ephemeral_key_when_env_absent(self):
        """Without ENCRYPTION_KEY, each instance generates its own throwaway key.

        ``fernet is not None`` -- the previous assertion -- is true of every
        possible implementation, including one that ignored the env var
        entirely. What actually matters is that the fallback key is *ephemeral*
        (so nobody mistakes dev behaviour for a persistent key) and that it is
        a usable Fernet key.
        """
        from src.api.services.auth_service import AuthService

        with patch.dict(os.environ, {}, clear=True):
            first = AuthService()
            second = AuthService()

        assert first.encryption_key != second.encryption_key
        token = first.fernet.encrypt(b"jean@virtue.com")
        # Different ephemeral keys => the second instance cannot read the
        # first's ciphertext. This is precisely the "restart orphans every
        # encrypted email" hazard the production guard below exists to stop.
        with pytest.raises(InvalidToken):
            second.fernet.decrypt(token)

    def test_init_uses_env_key_when_present(self):
        """ENCRYPTION_KEY must actually be the key in use, not merely present.

        Proven by decrypting -- with an independently constructed Fernet
        holding the same key -- a token the service produced. An
        implementation that read the env var and then generated a fresh key
        anyway would pass ``svc.fernet is not None`` and fail here, and that
        implementation would silently lose every stored email on restart.
        """
        from src.api.services.auth_service import AuthService

        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"ENCRYPTION_KEY": key}):
            svc = AuthService()

        assert svc.encryption_key == key
        token = svc.fernet.encrypt(b"jean@virtue.com")
        assert Fernet(key.encode()).decrypt(token) == b"jean@virtue.com"

    def test_init_refuses_to_generate_a_key_in_production(self):
        """The whole point of the fallback branch's guard, and it had no test.

        Silently generating an ephemeral key under FLASK_ENV=production would
        make every already-encrypted email undecryptable after a deploy, with
        no error anywhere -- the failure would surface later as unreadable
        user data.
        """
        from src.api.services.auth_service import AuthService

        with patch.dict(os.environ, {"FLASK_ENV": "production"}, clear=True):
            with pytest.raises(RuntimeError, match="ENCRYPTION_KEY must be set"):
                AuthService()

    def test_production_with_an_explicit_key_is_allowed(self):
        from src.api.services.auth_service import AuthService

        key = Fernet.generate_key().decode()
        with patch.dict(
            os.environ, {"FLASK_ENV": "production", "ENCRYPTION_KEY": key}, clear=True
        ):
            svc = AuthService()
        assert svc.encryption_key == key

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypted email should decrypt back to original plaintext."""
        from src.api.services.auth_service import AuthService

        svc = AuthService()
        email = "test@example.com"
        encrypted = svc.fernet.encrypt(email.encode()).decode()
        decrypted = svc.decrypt_email(encrypted)
        assert decrypted == email

    def test_decrypt_email_method(self):
        from src.api.services.auth_service import AuthService

        svc = AuthService()
        plaintext = "jean@virtue.medieval"
        token = svc.fernet.encrypt(plaintext.encode()).decode()
        assert svc.decrypt_email(token) == plaintext

    def test_decrypt_email_rejects_a_foreign_token(self):
        """Fernet is authenticated encryption: a token minted under a different
        key must raise, not return garbage. Pinned because ``decrypt_email``
        has no try/except -- callers rely on the exception."""
        from src.api.services.auth_service import AuthService

        svc = AuthService()
        foreign = Fernet(Fernet.generate_key()).encrypt(b"attacker@evil.com").decode()
        with pytest.raises(InvalidToken):
            svc.decrypt_email(foreign)

    def test_ciphertext_does_not_contain_the_plaintext(self):
        from src.api.services.auth_service import AuthService

        svc = AuthService()
        token = svc.fernet.encrypt(b"jean@virtue.medieval").decode()
        assert "jean@virtue.medieval" not in token
        assert "virtue" not in token


class TestAuthServiceValidation:
    """Test validation rules without any DB interaction."""

    @pytest.fixture
    def svc(self):
        from src.api.services.auth_service import AuthService

        return AuthService()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("username", ["", "a", "abc"])
    async def test_create_user_short_username_raises(self, svc, username):
        mock_db = AsyncMock()
        with patch("src.api.services.auth_service.db", mock_db):
            with pytest.raises(ValueError, match="Username must be at least 4"):
                await svc.create_user(username, "validpassword12345", "x@y.com")
        # Validation must reject *before* touching the database, or a rejected
        # signup still costs a round trip (and, with a partial write, could
        # leave a row behind).
        mock_db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_user_accepts_exactly_four_character_username(self, svc):
        """The boundary: `< 4` rejects, so 4 is valid. An off-by-one to `<= 4`
        would lock out every legitimate four-letter name."""
        mock_db = AsyncMock()
        svc.ph = MagicMock(hash=MagicMock(return_value="$argon2id$stub"))
        with patch("src.api.services.auth_service.db", mock_db):
            user = await svc.create_user("jean", "a" * 16, "x@y.com")
        assert user["username"] == "jean"
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("password", ["", "short", "a" * 15])
    async def test_create_user_short_password_raises(self, svc, password):
        mock_db = AsyncMock()
        with patch("src.api.services.auth_service.db", mock_db):
            with pytest.raises(ValueError, match="Password must be at least 16"):
                await svc.create_user("validuser", password, "x@y.com")
        mock_db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_user_valid_calls_db(self, svc):
        """Valid inputs invoke db.execute and return the new user dict.

        ``assert_awaited_once()`` on its own -- the previous assertion -- says
        nothing about *what* was written. The row is where the two secrets in
        this system live, so assert the actual params: the password must reach
        the database as an Argon2 hash and the email as Fernet ciphertext,
        never as plaintext.
        """
        password = "a_very_long_password_123"
        email = "jean@virtue.com"
        mock_db = AsyncMock()
        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.create_user("jeanclaire", password, email)

        assert result == {
            "id": result["id"],
            "username": "jeanclaire",
            "is_premium": False,
            "timezone": "America/New_York",
        }
        uuid.UUID(result["id"])  # raises if it is not a real UUID

        mock_db.execute.assert_awaited_once()
        sql, params = mock_db.execute.await_args.args
        # Parameterized INSERT, not string interpolation.
        assert sql.count("?") == 6
        assert "jeanclaire" not in sql

        user_id, username, password_hash, email_encrypted, is_premium, timezone = params
        assert user_id == result["id"]
        assert username == "jeanclaire"
        assert is_premium is False
        assert timezone == "America/New_York"

        # The password is hashed, and the hash verifies against the original.
        assert password_hash != password
        assert password not in password_hash
        assert password_hash.startswith("$argon2")
        svc.ph.verify(password_hash, password)

        # The email is encrypted, and round-trips through the service.
        assert email not in email_encrypted
        assert svc.decrypt_email(email_encrypted) == email

    @pytest.mark.asyncio
    async def test_create_user_hashes_are_salted(self, svc):
        """Two accounts with the same password must not share a hash."""
        mock_db = AsyncMock()
        with patch("src.api.services.auth_service.db", mock_db):
            await svc.create_user("userone", "identical_password_x", "a@b.com")
            await svc.create_user("usertwo", "identical_password_x", "c@d.com")

        first, second = [c.args[1][2] for c in mock_db.execute.await_args_list]
        assert first != second

    @pytest.mark.asyncio
    async def test_authenticate_user_no_rows_returns_none(self, svc):
        mock_result = MagicMock()
        mock_result.rows = []
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.authenticate_user("nobody", "password")

        assert result is None
        # The lookup is a parameterized SELECT: the username never reaches the
        # SQL text, so a username of `x'; DROP TABLE users; --` is inert.
        sql, params = mock_db.execute.await_args.args
        assert params == ["nobody"]
        assert "nobody" not in sql
        assert sql.count("?") == 1

    @pytest.mark.asyncio
    async def test_authenticate_user_no_rows_still_verifies_dummy_hash(self, svc):
        """Issue #365: unknown username must still run a full Argon2 verify
        (against a static dummy hash) so the response time is comparable to
        the 'username exists, wrong password' path — otherwise an attacker
        could enumerate valid usernames by timing.
        """
        from src.api.services.auth_service import _DUMMY_PASSWORD_HASH

        mock_result = MagicMock()
        mock_result.rows = []
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mock_ph = MagicMock()
        mock_ph.verify.side_effect = Exception("mismatch")
        svc.ph = mock_ph

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.authenticate_user("nobody", "password")

        assert result is None
        mock_ph.verify.assert_called_once_with(_DUMMY_PASSWORD_HASH, "password")

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password_returns_none(self, svc):
        """ph.verify raises on bad password — method should catch and return None.

        argon2-cffi PasswordHasher.verify is a C-extension method and cannot be
        patched directly on an instance.  We replace svc.ph entirely with a mock.
        """
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", "$argon2...", False, "UTC")]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mock_ph = MagicMock()
        mock_ph.verify.side_effect = Exception("bad password")
        svc.ph = mock_ph

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.authenticate_user("jeanclaire", "wrong_password")

        assert result is None
        # Verified against the *stored* hash for that row, not the dummy hash
        # (which would accept anybody) and not some other row's.
        mock_ph.verify.assert_called_once_with("$argon2...", "wrong_password")
        # A failed verify must not trigger the rehash UPDATE.
        assert mock_db.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_authenticate_user_never_verifies_against_the_dummy_hash_for_a_real_row(
        self, svc
    ):
        """The timing-equalization dummy hash must stay confined to the
        not-found branch. If it leaked into the found branch, any password
        would authenticate any user."""
        from src.api.services.auth_service import _DUMMY_PASSWORD_HASH

        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", "$argon2real", False, "UTC")]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        svc.ph = MagicMock()
        svc.ph.verify.side_effect = Exception("bad password")

        with patch("src.api.services.auth_service.db", mock_db):
            assert await svc.authenticate_user("jeanclaire", "anything") is None

        used_hashes = [c.args[0] for c in svc.ph.verify.call_args_list]
        assert _DUMMY_PASSWORD_HASH not in used_hashes

    @pytest.mark.asyncio
    async def test_authenticate_user_correct_password_returns_dict(self, svc):
        """When verify succeeds, method should return user dict."""
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", "hash_placeholder", False, "UTC")]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mock_ph = MagicMock()
        mock_ph.verify.return_value = None
        mock_ph.check_needs_rehash.return_value = False
        svc.ph = mock_ph

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.authenticate_user("jeanclaire", "correct_password")

        # Full dict, not three spot-checks: the caller (auth.py's login route)
        # forwards these fields straight into the session, so a dropped or
        # renamed key is a wire-contract break.
        assert result == {
            "id": "uid1",
            "username": "jeanclaire",
            "is_premium": False,
            "timezone": "UTC",
        }
        # The password hash itself must never be part of the returned record.
        assert "password_hash" not in result
        assert "hash_placeholder" not in result.values()
        # No rehash was needed, so no second write.
        assert mock_db.execute.await_count == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "raw_premium, raw_timezone, expected_premium, expected_timezone",
        [
            (1, "Asia/Tokyo", True, "Asia/Tokyo"),      # SQLite stores bools as ints
            (0, None, False, "America/New_York"),        # NULL timezone -> default
            (None, "", False, "America/New_York"),       # empty string is falsy too
        ],
    )
    async def test_authenticate_user_coerces_db_column_types(
        self, svc, raw_premium, raw_timezone, expected_premium, expected_timezone
    ):
        """libsql hands back raw SQLite values; the service normalizes them.

        `is_premium` gates paid content and `timezone` drives save-list
        ordering, so an integer 1 leaking through as an int (falsy-safe but
        not `is True`) or a NULL timezone reaching the client would both be
        real bugs.
        """
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", "h", raw_premium, raw_timezone)]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        svc.ph = MagicMock(check_needs_rehash=MagicMock(return_value=False))

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.authenticate_user("jeanclaire", "pw")

        assert result["is_premium"] is expected_premium
        assert result["timezone"] == expected_timezone

    @pytest.mark.asyncio
    async def test_authenticate_user_rehashes_when_needed(self, svc):
        """If check_needs_rehash returns True, db.execute is called a second time."""
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", "old_hash", False, "UTC")]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mock_ph = MagicMock()
        mock_ph.verify.return_value = None
        mock_ph.check_needs_rehash.return_value = True
        mock_ph.hash.return_value = "new_hash"
        svc.ph = mock_ph

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.authenticate_user("jeanclaire", "good_password")

        # First call = SELECT, second call = UPDATE for rehash
        assert mock_db.execute.await_count == 2
        update_sql, update_params = mock_db.execute.await_args_list[1].args
        # The count alone would pass for an UPDATE that wrote the *old* hash,
        # or wrote it to the wrong row -- assert both.
        assert "UPDATE users SET password_hash" in update_sql
        assert update_params == ["new_hash", "uid1"]
        mock_ph.hash.assert_called_once_with("good_password")
        # Rehashing is transparent: the login still succeeds.
        assert result["id"] == "uid1"

    @pytest.mark.asyncio
    async def test_rehash_failure_fails_the_login_closed(self, svc):
        """The rehash UPDATE runs inside the same try/except that guards
        verify(), so a DB error during rehash returns None rather than
        propagating. Pinned as the current (fail-closed) contract -- it is a
        surprising one, since the password was already verified correctly.
        """
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", "old_hash", False, "UTC")]
        mock_db = AsyncMock()
        mock_db.execute.side_effect = [mock_result, RuntimeError("db down")]

        svc.ph = MagicMock()
        svc.ph.verify.return_value = None
        svc.ph.check_needs_rehash.return_value = True
        svc.ph.hash.return_value = "new_hash"

        with patch("src.api.services.auth_service.db", mock_db):
            assert await svc.authenticate_user("jeanclaire", "good_password") is None

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found_returns_none(self, svc):
        mock_result = MagicMock()
        mock_result.rows = []
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.get_user_by_id("no-such-id")

        assert result is None
        sql, params = mock_db.execute.await_args.args
        assert params == ["no-such-id"]
        assert "no-such-id" not in sql
        # The password hash is not even selected, so it cannot be leaked by a
        # caller that serializes the whole row.
        assert "password_hash" not in sql

    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self, svc):
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", False, "Europe/London")]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.get_user_by_id("uid1")

        assert result == {
            "id": "uid1",
            "username": "jeanclaire",
            "is_premium": False,
            "timezone": "Europe/London",
        }

    @pytest.mark.asyncio
    async def test_get_user_by_id_null_timezone_defaults(self, svc):
        """Null timezone in DB should default to America/New_York."""
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", True, None)]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.get_user_by_id("uid1")

        assert result["timezone"] == "America/New_York"
        assert result["is_premium"] is True

    @pytest.mark.asyncio
    async def test_get_user_by_id_short_row_defaults_timezone(self, svc):
        """`len(user) > 3` guards a row returned without the timezone column
        (e.g. an older schema). Without the guard this would IndexError and
        surface as a 500 on every authenticated request."""
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", 0)]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.get_user_by_id("uid1")

        assert result == {
            "id": "uid1",
            "username": "jeanclaire",
            "is_premium": False,
            "timezone": "America/New_York",
        }

    @pytest.mark.asyncio
    async def test_update_user_timezone_returns_bool(self, svc):
        mock_result = MagicMock()
        mock_result.rows_affected = 1
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            ok = await svc.update_user_timezone("uid1", "Asia/Tokyo")

        assert ok is True
        sql, params = mock_db.execute.await_args.args
        # Param order is (timezone, user_id) — swapping them would write the
        # id into the timezone column for a nonexistent user and still return
        # a plausible-looking bool.
        assert params == ["Asia/Tokyo", "uid1"]
        assert "WHERE id = ?" in sql

    @pytest.mark.asyncio
    async def test_update_user_timezone_no_rows_affected_returns_false(self, svc):
        mock_result = MagicMock()
        mock_result.rows_affected = 0
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            ok = await svc.update_user_timezone("no-such-id", "UTC")

        assert ok is False
