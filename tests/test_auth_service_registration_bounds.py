"""Registration validates its fields from **both** ends.

``AuthService.create_user`` checked minimums only (``len(username) < 4``,
``len(password) < 16``) and nothing above them, on the one write path an
unauthenticated caller can reach. The password went straight into
``PasswordHasher.hash`` — Argon2, whose cost is deliberately high — and the
username and email straight into the ``INSERT``.

The maximums are asserted here at the service, which is where they live and
where the hash is called, plus one route-level test that the refusal keeps the
shape the minimum checks already had (``400 validation_error`` + prose), since
that is what the client renders.

No database is reached: ``src.api.services.auth_service.db`` is replaced with
an ``AsyncMock`` in every test below. This suite has form here — writing real
rows to the production database is one of the three incidents this repo has
had — so the "nothing was executed" assertions are load-bearing rather than
decorative.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.auth_service import (
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH,
    MAX_USERNAME_LENGTH,
    AuthService,
)

_VALID = {
    "username": "jean_claire",
    "password": "a-sufficiently-long-passphrase",
    "email": "jean@example.com",
}


@pytest.fixture
def service():
    """A fresh ``AuthService`` whose Argon2 hasher and database are spies.

    A fresh instance rather than the module singleton so a test cannot leave a
    patched hasher behind on the object every route shares.
    """
    svc = AuthService()
    svc.ph = MagicMock(wraps=svc.ph)
    return svc


@pytest.fixture
def db_spy():
    with patch(
        "src.api.services.auth_service.db", new=MagicMock()
    ) as fake_db:
        fake_db.execute = AsyncMock()
        yield fake_db


def _payload(**overrides):
    body = dict(_VALID)
    body.update(overrides)
    return body


class TestTheMaximumsAreEnforced:
    pytestmark = pytest.mark.asyncio

    @pytest.mark.parametrize(
        "field, value, expected",
        [
            ("username", "u" * (MAX_USERNAME_LENGTH + 1), "Username"),
            ("password", "p" * (MAX_PASSWORD_LENGTH + 1), "Password"),
            ("email", "e" * (MAX_EMAIL_LENGTH + 1), "Email"),
        ],
    )
    async def test_one_character_over_is_refused(
        self, service, db_spy, field, value, expected
    ):
        with pytest.raises(ValueError) as excinfo:
            await service.create_user(**_payload(**{field: value}))
        message = str(excinfo.value)
        assert expected in message
        # The same shape the minimum checks produce: which field, and the
        # number. `routes/auth.py` puts this string in `message` verbatim.
        assert "at most" in message

    async def test_the_refusal_precedes_the_argon2_hash(self, service, db_spy):
        """The whole point of the password bound. Argon2 is expensive by
        design; hashing first and validating afterwards would spend that cost
        on exactly the input the bound exists to reject."""
        with pytest.raises(ValueError):
            await service.create_user(
                **_payload(password="p" * (MAX_PASSWORD_LENGTH + 1))
            )
        service.ph.hash.assert_not_called()

    @pytest.mark.parametrize("field", ["username", "password", "email"])
    async def test_nothing_is_written(self, service, db_spy, field):
        limits = {
            "username": MAX_USERNAME_LENGTH,
            "password": MAX_PASSWORD_LENGTH,
            "email": MAX_EMAIL_LENGTH,
        }
        with pytest.raises(ValueError):
            await service.create_user(
                **_payload(**{field: "x" * (limits[field] + 1)})
            )
        db_spy.execute.assert_not_called()


class TestTheBoundsAdmitRealCredentials:
    """The control: a guard that refused everything would satisfy every
    assertion above."""

    pytestmark = pytest.mark.asyncio

    async def test_a_normal_registration_still_succeeds(self, service, db_spy):
        result = await service.create_user(**_payload())
        assert result["username"] == _VALID["username"]
        service.ph.hash.assert_called_once()
        db_spy.execute.assert_awaited_once()

    @pytest.mark.parametrize(
        "field, length",
        [
            ("username", MAX_USERNAME_LENGTH),
            ("password", MAX_PASSWORD_LENGTH),
            ("email", MAX_EMAIL_LENGTH),
        ],
    )
    async def test_exactly_at_the_limit_is_accepted(
        self, service, db_spy, field, length
    ):
        """The bound is inclusive, and off-by-one in the other direction is a
        registration a real password manager can produce being refused."""
        await service.create_user(**_payload(**{field: "x" * length}))
        db_spy.execute.assert_awaited_once()

    async def test_the_minimums_are_untouched(self, service, db_spy):
        with pytest.raises(ValueError, match="at least 4"):
            await service.create_user(**_payload(username="abc"))
        with pytest.raises(ValueError, match="at least 16"):
            await service.create_user(**_payload(password="short"))


class TestTheRouteReportsItLikeAnyOtherValidationFailure:
    @pytest.fixture
    def app(self, make_route_app, make_stub_session, make_stub_session_manager):
        from src.api.routes.auth import _register_limiter, auth_bp

        # Shared, process-wide, and spent by every registration test in this
        # process — a 429 here would read as a validation failure.
        if _register_limiter is not None:
            _register_limiter.clear_all()
        session = make_stub_session(session_id="sid_bounds", db_user_id="db_1")
        sm = make_stub_session_manager(session, MagicMock())
        return make_route_app(auth_bp, session=session, session_manager=sm)

    def test_an_overlong_username_is_a_400_validation_error(self, app, db_spy):
        with app.test_client() as c:
            rv = c.post(
                "/auth/register",
                json=_payload(username="u" * (MAX_USERNAME_LENGTH + 1)),
            )
        assert rv.status_code == 400
        body = rv.get_json()
        assert body["success"] is False
        assert body["error"] == "validation_error"
        assert "at most" in body["message"]
        db_spy.execute.assert_not_called()
