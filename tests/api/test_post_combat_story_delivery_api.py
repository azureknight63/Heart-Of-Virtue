"""Issue #683: a won fight's no-input story scene must reach collect-loot.

``AfterDefeatingKingSlime`` ("The churning stilled...") is a post-combat tile
event that needs no input, so it is never in ``/world/events/pending``. It used
to have exactly one carrier: the ``events_triggered`` of the first
``GET /api/combat/status`` after the kill, which popped it. Any other reader of
that GET (a second tab, devtools, a harness, a lost response) consumed the only
copy, and the browser -- which reads the victory through collect-loot -- never
saw the scene.

The contract these tests pin:

* ``POST /api/combat/collect-loot`` fires the post-combat tile events if no
  status poll has yet, and returns every undelivered one as
  ``events_triggered``. It is the only reader that clears them.
* ``GET /api/combat/status`` may fire them too (the REST harnesses rely on it),
  but it only echoes them; a stray read does not consume them.

Full-app: a real session on the real Grondelith map, so this lives in
``tests/api/`` (one process per file).
"""

import random

import pytest

from tools.harness.scenarios.base import pick_move_body

# The scene's first words (src/story/ch02.py, AfterDefeatingKingSlime).
SCENE = "AfterDefeatingKingSlime"
SCENE_OPENING = "The churning stilled"

# GrondelithApproach, one tile north of the arena where King Slime waits and
# auto-engages. A scratch config rather than config_combat_testing.ini, which
# other agents edit freely.
_CONFIG = """[game]
testmode = True
skipdialog = True
skipintro = True
startmap = grondelith-mineral-pools
startposition = 2, 5
starting_items = Shortsword
"""

_MAX_ROUNDS = 30


@pytest.fixture
def king_slime_session(app, client, tmp_path, monkeypatch):
    """A session standing north of the Grondelith arena. Returns ``(headers, player)``."""
    config = tmp_path / "king_slime_683.ini"
    config.write_text(_CONFIG)
    monkeypatch.setenv("CONFIG_FILE", str(config))
    # SessionManager reads CONFIG_FILE once, at construction; the app fixture
    # is session-scoped, so give this test its own manager.
    from src.api.services.session_manager import SessionManager

    monkeypatch.setattr(
        app, "session_manager", SessionManager(universe=app.session_manager.universe)
    )

    resp = client.post("/api/test/session", json={"username": "issue683"})
    assert resp.status_code == 201, resp.get_data(as_text=True)
    session_id = resp.get_json()["session_id"]
    player = app.session_manager.get_player(session_id)
    assert player.map.get("name") == "grondelith-mineral-pools"
    return {"Authorization": f"Bearer {session_id}"}, player


def _kill_king_slime(client, headers, player):
    """Walk into the arena and win, WITHOUT a status read after the killing move.

    Status is read only while the fight is still on, which never fires the
    post-combat events (they wait for ``in_combat`` to go False).
    """
    random.seed(683)
    resp = client.post("/api/world/move", json={"direction": "south"}, headers=headers)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert player.in_combat, "King Slime should auto-engage on entering the arena"

    # /api/debug/* reaches only the combat-testing arena's rosters, so the
    # slime is softened in-process; Jean is made unkillable through the API.
    for enemy in player.combat_list:
        enemy.hp = 1
    assert client.post(
        "/api/debug/player/hp", json={"hp": 9999, "maxhp": 9999}, headers=headers
    ).status_code == 200
    assert client.post(
        "/api/debug/player/attributes",
        json={"attributes": {"strength": 500, "finesse": 500}},
        headers=headers,
    ).status_code == 200

    for _ in range(_MAX_ROUNDS):
        status = client.get("/api/combat/status", headers=headers).get_json()
        assert status.get("combat_active"), "fight ended outside a move"
        body = pick_move_body(status.get("battle_state") or {})
        assert body is not None, "no usable move"
        resp = client.post("/api/combat/move", json=body, headers=headers)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        if not player.in_combat:
            break
    assert not player.in_combat, f"King Slime still alive after {_MAX_ROUNDS} rounds"
    assert (player.combat_end_summary or {}).get("status") == "victory"


def _scene(events):
    return next((e for e in events or [] if e.get("name") == SCENE), None)


def _collect(client, headers):
    resp = client.post(
        "/api/combat/collect-loot", json={"item_names": []}, headers=headers
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("success") is True, data
    return data


def test_a_stray_status_read_does_not_steal_the_victory_scene(client, king_slime_session):
    headers, player = king_slime_session
    _kill_king_slime(client, headers, player)

    # The stray reader: a second tab, devtools, a harness.
    stray = client.get("/api/combat/status", headers=headers).get_json()
    assert _scene(stray.get("events_triggered")) is not None, (
        "status still fires and reports the post-combat events"
    )
    # ...and it only echoes them: a second read sees them too.
    again = client.get("/api/combat/status", headers=headers).get_json()
    assert _scene(again.get("events_triggered")) is not None

    collected = _collect(client, headers)
    scene = _scene(collected.get("events_triggered"))
    assert scene is not None, (
        f"collect-loot lost {SCENE}: {collected.get('events_triggered')!r}"
    )
    assert scene["needs_input"] is False
    assert scene["output_text"].startswith(SCENE_OPENING)
    assert scene.get("post_combat") is True

    # Delivered once: collect-loot is the reader that clears the buffer.
    after = client.get("/api/combat/status", headers=headers).get_json()
    assert _scene(after.get("events_triggered")) is None


def test_collect_loot_delivers_the_scene_when_nothing_polled_first(client, king_slime_session):
    headers, player = king_slime_session
    _kill_king_slime(client, headers, player)

    collected = _collect(client, headers)
    scene = _scene(collected.get("events_triggered"))
    assert scene is not None, (
        f"collect-loot did not fire {SCENE}: {collected.get('events_triggered')!r}"
    )
    assert scene["output_text"].startswith(SCENE_OPENING)

    # Fired exactly once: neither a later poll nor a second collect repeats it.
    after = client.get("/api/combat/status", headers=headers).get_json()
    assert _scene(after.get("events_triggered")) is None
    assert _scene(_collect(client, headers).get("events_triggered")) is None
