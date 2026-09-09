"""``GET /api/journal`` through the real app (issue #538).

The wire-field contract in ``tests/test_wire_field_contract.py`` pins what
``GameService.get_journal`` returns. It cannot see the envelope the ROUTE wraps
that in — and ``JournalDialog.jsx`` reads ``response?.data?.journal`` behind a
``?.``, so renaming the route's key would render an empty journal forever with
nothing failing. This file closes that last hop.

Lives under ``tests/api/`` because it builds a real session and universe, which
mutates module-level item and merchant registries — see ``.claude/rules/testing.md``.
"""

import pytest

from src.api.app import create_app
from src.api.config import TestingConfig


@pytest.fixture
def client():
    app, _socketio = create_app(TestingConfig)
    return app.test_client()


@pytest.fixture
def auth(client):
    """A real session via the TESTING-only bypass; returns its auth header."""
    response = client.post("/api/test/session", json={"username": "journal_tester"})
    assert response.status_code == 201, response.get_data(as_text=True)
    session_id = response.get_json()["session_id"]
    return {"Authorization": f"Bearer {session_id}"}


class TestJournalRoute:
    def test_returns_the_envelope_the_client_reads(self, client, auth):
        response = client.get("/api/journal", headers=auth)

        assert response.status_code == 200
        body = response.get_json()
        # `success` + `journal` is the shape JournalDialog unwraps as
        # `response?.data?.journal`.
        assert body["success"] is True
        assert set(body["journal"]) == {"objectives", "completed", "log"}

    def test_a_fresh_player_gets_an_empty_journal_rather_than_an_error(self, client, auth):
        body = client.get("/api/journal", headers=auth).get_json()

        assert body["journal"] == {"objectives": [], "completed": [], "log": []}

    def test_reading_the_journal_reports_what_the_story_recorded(self, client, auth):
        """End to end: a story write shows up through the route.

        Without this, every assertion above would still pass against a route
        that always returned the empty shape.
        """
        from src.journal import set_objective

        session_manager = client.application.session_manager
        session_id = auth["Authorization"].split()[1]
        player = session_manager.get_player(session_id)

        set_objective(player, "route_probe", "Cross the river.", chapter=3)

        body = client.get("/api/journal", headers=auth).get_json()

        assert [o["text"] for o in body["journal"]["objectives"]] == ["Cross the river."]

    def test_requires_a_session(self, client):
        assert client.get("/api/journal").status_code == 401
