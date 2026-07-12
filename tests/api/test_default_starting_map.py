"""Regression test for GitHub issue #56 — "Need config fallback".

Bug: when no CONFIG_FILE env var is set (the default for a fresh dev setup
or CI run), SessionManager.starting_map_name used to default to "default" —
a map name that doesn't exist in the universe — and Universe.starting_map_default
was also None (it only gets set when a map's name contains the substring
"start", and none of the real maps do). The session manager silently set
player.map = None, so every world endpoint 404'd/400'd for a brand new player.

Fix: SessionManager now defaults starting_map_name to "dark-grotto" (the
game's actual starting map — see config_dev.ini / story ch01 references),
and _create_player_for_session also has a belt-and-suspenders fallback to
the first map with real tile data if even that name is somehow missing.

This test exercises the real app + real SessionManager (no CONFIG_FILE set)
end-to-end through the Flask test client, per the "full-app integration
tests belong in tests/api/" rule in CLAUDE.md.
"""

import json


class TestDefaultStartingMapFallback:
    def test_fresh_session_lands_on_valid_map(self, app, monkeypatch):
        """With no CONFIG_FILE set, a fresh player must get a real, non-None map."""
        monkeypatch.delenv("CONFIG_FILE", raising=False)

        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("issue56_tester")
        player = session_manager.get_player(session_id)

        assert player.map is not None, "player.map must not be None for a fresh session"
        map_name = player.map.get("name")
        assert map_name, "starting map must have a name"

        # The chosen map must actually exist in the universe's map list.
        universe_map_names = {m.get("name") for m in player.universe.maps}
        assert map_name in universe_map_names

        # The map must contain real tile data (at least one coordinate key),
        # otherwise the player would still be stranded with no room to view.
        assert any(isinstance(k, tuple) for k in player.map), (
            f"starting map '{map_name}' has no tile data"
        )

    def test_get_world_succeeds_for_fresh_session(self, client, app, monkeypatch):
        """GET /api/world must succeed (200) for a session created with no CONFIG_FILE."""
        monkeypatch.delenv("CONFIG_FILE", raising=False)

        resp = client.post(
            "/api/test/session",
            data=json.dumps({"username": "issue56_tester2"}),
            content_type="application/json",
        )
        assert resp.status_code == 201
        session_id = resp.get_json()["session_id"]

        world_resp = client.get(
            "/api/world",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        assert world_resp.status_code == 200, (
            f"Expected 200 from GET /api/world, got {world_resp.status_code}: "
            f"{world_resp.get_data(as_text=True)}"
        )
        data = world_resp.get_json()
        assert data.get("success") is not False
