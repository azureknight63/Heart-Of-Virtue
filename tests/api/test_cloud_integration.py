"""Registration, login and cloud-save persistence against a REAL database.

This file writes real rows. ``auth_service.create_user`` has no TESTING
guard, and ``src/api/db.py`` reads ``TURSO_DATABASE_URL`` straight from the
environment rather than from Flask config, so a process with a configured
``.env`` INSERTs into whatever database that URL names.

Two things stop that, and only together:

* ``tests/conftest.py`` blanks ``TURSO_DATABASE_URL``/``TURSO_AUTH_TOKEN``
  unconditionally, so under pytest there is no database to reach.
* the ``xfail(strict=True)`` below turns that into an EXPECTED failure --
  and, crucially, into a loud one the day the blanking stops working. An
  XPASS here means a test just talked to a real database.

That second half is why this is an xfail and not the opt-in skip it was
briefly rewritten as. A skip reports the same "nothing ran" whether the
guard is holding or has quietly come off; only the strict xfail can tell
those apart. An opt-in variable would not have helped either: the blanking
in ``tests/conftest.py`` is unconditional, so ``HOV_LIVE_DB=1`` alone would
not have made this run. Running it for real means restoring the credentials
the way ``tests/integration/conftest.py`` does for the live LLM suite.

The exposure was hidden for months by ``pytest.ini``'s ``norecursedirs``,
and surfaced when the directory was briefly un-excluded: the coverage
measurement that justified that rescue never asked whether a rescued module
had external side effects.
"""

import logging
import os

import pytest
import uuid
import asyncio
from src.api.db import db

_log = logging.getLogger(__name__)

# Both credentials are required. Keying only on the URL made the marker
# deactivate the moment a developer exported it, at which point the test
# hard-failed on the first request instead of being skipped -- which is the
# opposite of what the reason text told them to expect.
TURSO_CONFIGURED = bool(
    os.getenv("TURSO_DATABASE_URL") and os.getenv("TURSO_AUTH_TOKEN")
)

# Kept as an `xfail`, not converted to a `skipif`. Without a database this
# test really does fail (503 from the register route), so "expected to fail"
# is the accurate report, it still exercises the config-leak guard on the way
# through, and it keeps this directory's zero-skip property (CLAUDE.md is
# explicit that skips in this suite have a long history of hiding defects).
#
# `strict=True` is the house setting and matters here: an XPASS with no Turso
# configured would mean the test is no longer verifying cloud persistence at
# all -- exactly the silent hollowing-out that should fail loudly.
requires_turso = pytest.mark.xfail(
    condition=not TURSO_CONFIGURED,
    strict=True,
    reason=(
        "Needs a reachable Turso database. src/api/db.py raises "
        "'TURSO_DATABASE_URL is not set' on first execute(), and the register "
        "route's config-leak guard turns that into HTTP 503, so the very first "
        "assertion (201 from /api/auth/register) fails. This test verifies real "
        "cloud persistence — registration, the manual-save row, the single-row "
        "autosave UPSERT, and load-after-relogin — so a fake db would verify "
        "nothing it exists to verify. Set both TURSO_DATABASE_URL and "
        "TURSO_AUTH_TOKEN and it runs for real."
    ),
)


class TestCloudIntegration:
    """Integration tests for Cloud Authentication and Save System."""

    def setup_method(self, method):
        """Initialize test variables."""
        self.test_user_prefix = "test_cloud_user_"
        self.test_username = f"{self.test_user_prefix}{uuid.uuid4().hex[:8]}"
        self.test_password = "SecurePassword123!@#" # > 16 chars
        self.test_email = "test@example.com"
        self.created_user = False

    async def _do_cleanup(self):
        """Actual cleanup logic."""
        try:
            sql_get_user = "SELECT id FROM users WHERE username = ?"
            res = await db.execute(sql_get_user, [self.test_username])
            if res.rows:
                user_id = res.rows[0][0]
                await db.execute("DELETE FROM saves WHERE user_id = ?", [user_id])
                await db.execute("DELETE FROM users WHERE id = ?", [user_id])
        except Exception:
            # Through `logging`, never `print`: tests/api/conftest.py replaces
            # builtins.print with a no-op for every test in this directory, so
            # a printed teardown failure is invisible.
            _log.exception("Cloud teardown failed for %s", self.test_username)

    def teardown_method(self, method):
        """Delete the row this test created, if it created one.

        Gated twice: without Turso configured there is no database to talk to,
        and the validation test never registers anybody. Running the cleanup
        unconditionally meant every test in the class opened an event loop and
        issued a doomed query.
        """
        if not (TURSO_CONFIGURED and self.created_user):
            return
        asyncio.run(self._do_cleanup())

    @requires_turso
    def test_user_lifecycle_and_saves(self, client, app):
        """Test registration, login, and cloud save persistence."""

        # 1. Test Registration
        reg_payload = {
            "username": self.test_username,
            "password": self.test_password,
            "email": self.test_email
        }
        # Correct URL with /api prefix
        response = client.post("/api/auth/register", json=reg_payload)
        assert response.status_code == 201
        self.created_user = True
        data = response.get_json()
        assert data["success"] is True
        session_id = data["data"]["session_id"]
        assert session_id is not None

        # 2. Verify User ID in session
        session = app.session_manager.get_session(session_id)
        assert session is not None
        assert hasattr(session, "db_user_id")
        # Asserted, not merely bound: a registered player always carries a
        # db_user_id, and the saves routes 403 every cloud operation without
        # one (CLAUDE.md, "There is no guest mode").
        assert session.db_user_id

        # 3. Test Manual Save
        save_name = "Cloud Test Save"
        headers = {"Authorization": f"Bearer {session_id}"}
        save_resp = client.post("/api/saves", json={"name": save_name}, headers=headers)
        assert save_resp.status_code == 201
        save_data = save_resp.get_json()
        save_id = save_data["save_id"]

        # 4. Test List Saves
        list_resp = client.get("/api/saves", headers=headers)
        assert list_resp.status_code == 200
        saves_data = list_resp.get_json()
        assert len(saves_data["saves"]) >= 1
        # Find our manual save
        manual_saves = [s for s in saves_data["saves"] if s["name"] == save_name]
        assert len(manual_saves) == 1
        assert manual_saves[0]["is_autosave"] is False

        # 5. Test Autosave
        auto_resp1 = client.post("/api/saves", json={"is_autosave": True}, headers=headers)
        assert auto_resp1.status_code == 201

        # Perform second autosave (should UPSERT)
        auto_resp2 = client.post("/api/saves", json={"is_autosave": True}, headers=headers)
        assert auto_resp2.status_code == 201

        # List again
        list_resp2 = client.get("/api/saves", headers=headers)
        saves_data2 = list_resp2.get_json()
        autosave_recs = [s for s in saves_data2["saves"] if s["is_autosave"]]
        assert len(autosave_recs) == 1

        # 6. Test Login (Persistence check)
        login_payload = {
            "username": self.test_username,
            "password": self.test_password
        }
        login_resp = client.post("/api/auth/login", json=login_payload)
        assert login_resp.status_code == 200
        new_session_id = login_resp.get_json()["data"]["session_id"]

        # Verify new session access
        new_headers = {"Authorization": f"Bearer {new_session_id}"}
        list_resp3 = client.get("/api/saves", headers=new_headers)
        assert list_resp3.status_code == 200
        assert len(list_resp3.get_json()["saves"]) >= 2

        # 7. Test Load Game
        load_resp = client.post(f"/api/saves/{save_id}/load", headers=new_headers)
        assert load_resp.status_code == 200
        assert load_resp.get_json()["success"] is True

    def test_register_rejects_a_short_password(self, client):
        """Registration enforces the 16-character password floor.

        The username floor is covered once, by
        `test_routes_integration.py::test_register_short_username`, which
        asserts the status, the `success` flag, the `validation_error` code and
        the message. This test used to repeat that case verbatim.
        """
        # Short Password
        short_pass = {
            "username": f"valid_{uuid.uuid4().hex[:4]}",
            "password": "short", # < 16
            "email": "test@test.com"
        }
        resp2 = client.post("/api/auth/register", json=short_pass)
        assert resp2.status_code == 400
        assert "at least 16 characters" in resp2.get_json()["message"]
