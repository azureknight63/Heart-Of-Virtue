"""Integration tests for the test-only debug blueprint (TheAdjutant's endpoint).

The debug blueprint is registered only when app.config["TESTING"] is true. These
tests drive it through a Flask test client with a real test session.
"""

import pytest

from src.api.app import create_app
from src.api.config import TestingConfig


@pytest.fixture(scope="module")
def client():
    app, _socketio = create_app(TestingConfig)
    assert app.config.get("TESTING") is True
    return app.test_client()


@pytest.fixture
def auth(client):
    """Create a test session and return an Authorization header dict."""
    resp = client.post("/api/test/session", json={})
    assert resp.status_code == 201
    session_id = resp.get_json()["session_id"]
    return {"Authorization": f"Bearer {session_id}"}


def test_debug_requires_auth(client):
    resp = client.post("/api/debug/player/restore")
    assert resp.status_code == 401


def test_debug_registered_only_in_testing():
    # Production config must NOT expose the debug blueprint.
    from src.api.config import ProductionConfig

    app, _ = create_app(ProductionConfig)
    rules = {r.rule for r in app.url_map.iter_rules()}
    # The debug blueprint's combat-testing routes must be absent in production.
    assert "/api/debug/player/restore" not in rules
    assert "/api/debug/arena/add" not in rules


def test_player_state_endpoint(client, auth):
    resp = client.get("/api/debug/player", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "hp" in data and "attributes" in data


def test_set_hp_endpoint(client, auth):
    resp = client.post("/api/debug/player/hp", json={"hp": 15, "maxhp": 30}, headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["maxhp"] == 30 and data["hp"] == 15


def test_set_hp_missing_field_is_400(client, auth):
    resp = client.post("/api/debug/player/hp", json={"hp": 15}, headers=auth)
    assert resp.status_code == 400


def test_restore_endpoint(client, auth):
    resp = client.post("/api/debug/player/restore", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_arena_rosters_endpoint(client, auth):
    resp = client.get("/api/debug/arena", headers=auth)
    assert resp.status_code == 200
    assert "rosters" in resp.get_json()
