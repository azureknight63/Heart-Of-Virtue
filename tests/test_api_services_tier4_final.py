"""API service coverage for the corners nothing else reaches.

History: this file used to be 26 blanket-skipped tests whose bodies were
``try: ... except Exception: pass`` or ``assert isinstance(result, tuple)``.
Every one of them was simultaneously vacuous *and* redundant:

* ``TestAuthService``      -> superseded by ``tests/test_auth_service_and_npc_availability.py``,
  which covers create_user validation, the dummy-hash timing guard,
  rehash-on-verify, and the encrypt/decrypt round trip.
* ``TestSessionManager``   -> superseded by ``tests/test_session_manager_coverage.py``.
  Half its cases called methods that do not exist at all
  (``validate_session``, ``delete_session``, ``get_player_from_session``,
  ``update_session_data``, ``cleanup_expired_sessions``) behind ``hasattr``
  guards or ``except Exception: pass``, so they ran zero production statements.
* ``TestValidators`` / ``TestValidatorsEdgeCases`` / ``TestServiceIntegration``
  -> superseded by ``tests/test_validators_and_sanitizer.py``.

What is kept here is only what *nothing* in the suite covered:
``ensure_dict``, ``validate_string_field`` and ``coerce_optional_index`` (0%
direct coverage), the production ``ENCRYPTION_KEY`` guard, and
``SessionManager._reap_expired_if_due``'s throttle and swallow-failures paths.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.api.services.auth_service import AuthService
from src.api.services.session_manager import Session, SessionManager
from src.api.services.validators import (
    coerce_optional_index,
    ensure_dict,
    has_visible_characters,
    validate_string_field,
)


class TestEnsureDict:
    """``ensure_dict`` funnels a non-object JSON body into the missing-field path.

    Without it a body of ``[1, 2]`` or ``"hi"`` reaches ``.get()`` in a route
    handler and surfaces as an HTTP 500 instead of a structured 4xx.
    """

    def test_dict_passes_through_by_identity(self):
        body = {"direction": "north"}
        assert ensure_dict(body) is body

    @pytest.mark.parametrize("value", [None, [1, 2], "hi", 7, 3.5, True, set()])
    def test_non_object_bodies_become_an_empty_dict(self, value):
        assert ensure_dict(value) == {}

    def test_result_is_always_safe_to_call_get_on(self):
        # The whole reason the helper exists.
        assert ensure_dict([1, 2]).get("direction") is None


class TestValidateStringField:
    """``validate_string_field`` guards route handlers that call ``.strip()``."""

    @pytest.mark.parametrize("value", [5, None, ["north"], {"a": 1}, 2.5])
    def test_non_strings_are_rejected_by_type(self, value):
        ok, error = validate_string_field(value, "Direction")
        assert ok is False
        assert error == "Direction must be a string"

    def test_blank_string_is_rejected_and_names_the_field(self):
        ok, error = validate_string_field("   ", "Username")
        assert ok is False
        assert error == "Username is required"

    @pytest.mark.parametrize(
        "value, reason",
        [
            ("\x00", "NUL"),
            ("\u200b", "ZERO WIDTH SPACE"),
            ("\ufeff", "BYTE ORDER MARK"),
            ("\u2060", "WORD JOINER"),
            ("  \x00\u200b  ", "padding around invisible codepoints"),
        ],
    )
    def test_invisible_but_non_whitespace_values_are_blank(self, value, reason):
        """A value that survives ``.strip()`` but renders as nothing is blank.

        ``str.strip()`` removes only whitespace, so these reached routes as
        "non-empty" text and then displayed as nothing -- the empty save-list
        row of issue #523. The rule is visibility-based instead.
        """
        ok, error = validate_string_field(value, "Username")
        assert ok is False, reason
        assert error == "Username is required"

    @pytest.mark.parametrize(
        "value, reason",
        [
            ("\u3164", "HANGUL FILLER -- category Lo, the classic blank name"),
            ("\u115f", "HANGUL CHOSEONG FILLER -- category Lo"),
            ("\uffa0", "HALFWIDTH HANGUL FILLER -- category Lo"),
            ("\u2800", "BRAILLE PATTERN BLANK -- category So"),
            ("\u0301", "COMBINING ACUTE -- category Mn, no base to attach to"),
        ],
    )
    def test_blank_glyphs_outside_the_invisible_categories_are_blank(
        self, value, reason
    ):
        """Rendering blank is not the same as having an invisible category.

        These sit in Lo/So/Mn -- "letter", "symbol", "mark" -- so a rule that
        only screens the C* and Z* categories waves them through, and a save
        named with one renders as exactly the empty row issue #523 was filed
        for. The category test is necessary but not sufficient.
        """
        ok, error = validate_string_field(value, "Username")
        assert ok is False, reason
        assert error == "Username is required"

    def test_blank_string_allowed_when_opted_in(self):
        assert validate_string_field("   ", "Note", allow_empty=True) == (True, None)

    def test_invisible_value_allowed_when_opted_in(self):
        """``allow_empty`` short-circuits the visibility rule as well."""
        assert validate_string_field("\x00", "Note", allow_empty=True) == (True, None)

    def test_max_length_is_inclusive(self):
        assert validate_string_field("abc", "Name", max_length=3) == (True, None)
        ok, error = validate_string_field("abcd", "Name", max_length=3)
        assert ok is False
        assert error == "Name must be 3 characters or less"

    def test_length_is_measured_before_stripping(self):
        """Trailing whitespace still counts against ``max_length``."""
        ok, _ = validate_string_field("ab  ", "Name", max_length=3)
        assert ok is False

    def test_valid_string_returns_no_error(self):
        assert validate_string_field("north", "Direction") == (True, None)


class TestHasVisibleCharacters:
    """``has_visible_characters`` is the project's definition of "not blank"."""

    @pytest.mark.parametrize(
        "value", ["a", " a ", "north", "Save_2026-01-01", "\x00a", "\u4e2d"]
    )
    def test_true_when_anything_renders(self, value):
        assert has_visible_characters(value) is True

    @pytest.mark.parametrize(
        "value",
        ["", " ", "\t\n\r", "\u00a0", "\x00", "\u200b", "\ufeff", "\x00\u200b "],
    )
    def test_false_for_values_that_render_as_nothing(self, value):
        assert has_visible_characters(value) is False

    @pytest.mark.parametrize("value", ["\u3164", "\u115f", "\uffa0", "\u2800", "\u0301"])
    def test_false_for_blank_glyphs_with_a_visible_looking_category(self, value):
        """Lo/So/Mn codepoints that still render as nothing."""
        assert has_visible_characters(value) is False

    @pytest.mark.parametrize(
        "value", ["\u2801", "caf\u00e9", "cafe\u0301", "\U0001f5e1", "\u5192\u967a"]
    )
    def test_true_for_real_text_in_those_same_categories(self, value):
        """The blank-glyph screen must not swallow legitimate text.

        A non-blank braille pattern, an emoji, CJK, and both the precomposed
        and decomposed spellings of an accented word all render.
        """
        assert has_visible_characters(value) is True

    def test_it_is_stricter_than_strip(self):
        """The whole reason it exists: ``.strip()`` alone lets NUL through."""
        assert "\x00".strip() != ""
        assert has_visible_characters("\x00") is False


class TestCoerceOptionalIndex:
    """``coerce_optional_index`` distinguishes "omitted" from "garbage"."""

    def test_none_means_omitted_not_invalid(self):
        assert coerce_optional_index(None) == (None, None)

    def test_numeric_string_is_coerced(self):
        assert coerce_optional_index("3") == (3, None)

    def test_float_truncates_toward_zero(self):
        assert coerce_optional_index(2.9) == (2, None)

    @pytest.mark.parametrize("value", [True, False])
    def test_booleans_are_rejected_despite_being_ints(self, value):
        """``True == 1`` but a boolean is never a meaningful inventory index."""
        index, error = coerce_optional_index(value)
        assert index is None
        assert error == "item_index must be an integer"

    @pytest.mark.parametrize("value", ["abc", [1], {"a": 1}, object()])
    def test_uncoercible_values_report_an_error_instead_of_raising(self, value):
        index, error = coerce_optional_index(value)
        assert index is None
        assert error == "item_index must be an integer"

    def test_field_name_appears_in_the_error(self):
        assert coerce_optional_index("x", "slot")[1] == "slot must be an integer"


class TestAuthServiceEncryptionKey:
    """The ENCRYPTION_KEY fallback must never silently apply in production.

    An ephemeral Fernet key orphans every already-encrypted user email on
    restart, so ``AuthService.__init__`` raises rather than generating one when
    ``FLASK_ENV == "production"``.
    """

    def test_production_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("FLASK_ENV", "production")
        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY must be set in production"):
            AuthService()

    def test_production_with_key_is_usable(self, monkeypatch):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", key)
        monkeypatch.setenv("FLASK_ENV", "production")
        service = AuthService()
        assert service.encryption_key == key
        token = service.fernet.encrypt(b"jean@example.com").decode()
        assert service.decrypt_email(token) == "jean@example.com"

    @pytest.mark.parametrize(
        "flask_env", ["Production", "PRODUCTION", " production ", "pRoDuCtIoN"]
    )
    def test_the_guard_is_not_case_sensitive(self, monkeypatch, flask_env):
        """A case difference must not turn a fail-closed guard into a fail-open one.

        ``FLASK_ENV`` is operator-typed, and both entry points that select the
        config class lowercase it — so ``Production`` really does select
        ``ProductionConfig``. Compared raw here, it skipped this raise and minted
        an ephemeral Fernet key instead, orphaning every already-encrypted email
        on the next restart with nothing reporting the loss.

        The identical defect existed in ``src/api/config.py``'s SECRET_KEY guard
        — which this one's own comment says it mirrors — and both now share
        ``normalized_env()``. This test exists so they cannot drift a third time.
        """
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("FLASK_ENV", flask_env)
        with pytest.raises(
            RuntimeError, match="ENCRYPTION_KEY must be set in production"
        ):
            AuthService()

    def test_non_production_falls_back_to_a_generated_key(self, monkeypatch):
        """The normalisation must not over-reach and break dev/test startup."""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("FLASK_ENV", "development")
        service = AuthService()
        assert service.encryption_key  # generated, not inherited
        token = service.fernet.encrypt(b"a@b.c").decode()
        assert service.decrypt_email(token) == "a@b.c"

    def test_two_generated_keys_do_not_interoperate(self, monkeypatch):
        """Demonstrates precisely the data loss the production guard prevents."""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("FLASK_ENV", "development")
        from cryptography.fernet import InvalidToken

        first, second = AuthService(), AuthService()
        token = first.fernet.encrypt(b"jean@example.com").decode()
        with pytest.raises(InvalidToken):
            second.decrypt_email(token)


class TestSessionReaping:
    """``_reap_expired_if_due`` is on the per-request path; it must be cheap and safe."""

    @staticmethod
    def _manager():
        with patch.object(SessionManager, "_load_game_config", return_value=None):
            return SessionManager()

    @staticmethod
    def _expired_session(manager, session_id="stale"):
        session = Session(session_id, f"player_{session_id}", "jean", datetime.now())
        session.expires_at = datetime.now() - timedelta(hours=1)
        manager.sessions[session_id] = session
        manager.session_to_player[session_id] = session.player_id
        manager.players[session.player_id] = object()
        return session

    def test_throttled_within_the_interval(self):
        manager = self._manager()
        manager._last_reap = datetime.now()
        self._expired_session(manager)

        manager._reap_expired_if_due()

        assert "stale" in manager.sessions, "sweep should have been throttled"

    def test_force_bypasses_the_throttle(self):
        manager = self._manager()
        manager._last_reap = datetime.now()
        self._expired_session(manager)

        manager._reap_expired_if_due(force=True)

        assert manager.sessions == {}
        assert manager.players == {}
        assert manager.session_to_player == {}

    def test_stale_last_reap_triggers_the_sweep(self):
        manager = self._manager()
        manager._last_reap = datetime.now() - timedelta(days=1)
        self._expired_session(manager)
        live = Session("live", "player_live", "jean", datetime.now())
        manager.sessions["live"] = live

        manager._reap_expired_if_due()

        assert list(manager.sessions) == ["live"], "only the expired session is reaped"

    def test_cleanup_failure_never_breaks_the_caller(self):
        manager = self._manager()
        manager._last_reap = datetime.now() - timedelta(days=1)
        with patch.object(
            manager, "cleanup_expired", side_effect=RuntimeError("boom")
        ) as cleanup:
            manager._reap_expired_if_due()  # must not raise
        cleanup.assert_called_once_with()

    def test_last_reap_advances_even_when_cleanup_raises(self):
        """Otherwise a persistently failing sweep would retry on every request."""
        manager = self._manager()
        manager._last_reap = datetime.now() - timedelta(days=1)
        before = manager._last_reap
        with patch.object(manager, "cleanup_expired", side_effect=RuntimeError("boom")):
            manager._reap_expired_if_due()
        assert manager._last_reap > before
