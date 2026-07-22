"""
Tests for:
- src/api/services/auth_service.py (validation logic and encrypt/decrypt, no DB)
"""

import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch
from cryptography.fernet import Fernet

# ===========================================================================
# AuthService — tested in isolation (no DB calls)
# ===========================================================================


class TestAuthServiceInit:
    """Test that AuthService can be constructed with/without env key."""

    def test_init_generates_key_when_env_absent(self):
        """Without ENCRYPTION_KEY env var, a key should be generated and stored."""
        from src.api.services.auth_service import AuthService

        with patch.dict(os.environ, {}, clear=True):
            # Remove key if set
            os.environ.pop("ENCRYPTION_KEY", None)
            svc = AuthService()
            assert svc.fernet is not None

    def test_init_uses_env_key_when_present(self):
        """If ENCRYPTION_KEY is set, AuthService must use it for the Fernet instance."""
        from src.api.services.auth_service import AuthService

        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"ENCRYPTION_KEY": key}):
            svc = AuthService()
            assert svc.fernet is not None

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


class TestAuthServiceValidation:
    """Test validation rules without any DB interaction."""

    @pytest.fixture
    def svc(self):
        from src.api.services.auth_service import AuthService

        return AuthService()

    @pytest.mark.asyncio
    async def test_create_user_short_username_raises(self, svc):
        with pytest.raises(ValueError, match="at least 4"):
            await svc.create_user("abc", "validpassword12345", "x@y.com")

    @pytest.mark.asyncio
    async def test_create_user_short_password_raises(self, svc):
        with pytest.raises(ValueError, match="at least 16"):
            await svc.create_user("validuser", "short", "x@y.com")

    @pytest.mark.asyncio
    async def test_create_user_valid_calls_db(self, svc):
        """Valid inputs should invoke db.execute (mocked) and return user dict."""
        mock_db = AsyncMock()
        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.create_user(
                "jeanclaire", "a_very_long_password_123", "jean@virtue.com"
            )
        assert result["username"] == "jeanclaire"
        assert "id" in result
        assert result["is_premium"] is False
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_no_rows_returns_none(self, svc):
        mock_result = MagicMock()
        mock_result.rows = []
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.authenticate_user("nobody", "password")

        assert result is None

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

        assert result is not None
        assert result["username"] == "jeanclaire"
        assert result["id"] == "uid1"

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
            await svc.authenticate_user("jeanclaire", "good_password")

        # First call = SELECT, second call = UPDATE for rehash
        assert mock_db.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found_returns_none(self, svc):
        mock_result = MagicMock()
        mock_result.rows = []
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.get_user_by_id("no-such-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self, svc):
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", False, "Europe/London")]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.get_user_by_id("uid1")

        assert result["id"] == "uid1"
        assert result["username"] == "jeanclaire"
        assert result["timezone"] == "Europe/London"

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

    @pytest.mark.asyncio
    async def test_update_user_timezone_returns_bool(self, svc):
        mock_result = MagicMock()
        mock_result.rows_affected = 1
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            ok = await svc.update_user_timezone("uid1", "Asia/Tokyo")

        assert ok is True

    @pytest.mark.asyncio
    async def test_update_user_timezone_no_rows_affected_returns_false(self, svc):
        mock_result = MagicMock()
        mock_result.rows_affected = 0
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            ok = await svc.update_user_timezone("no-such-id", "UTC")

        assert ok is False
