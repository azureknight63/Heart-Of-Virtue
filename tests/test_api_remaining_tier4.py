"""API service edge paths that nothing else in the suite exercises.

Rewritten from scratch. The 73 tests that used to live here were blanket
skipped with "Test framework isolation issues - 27+ failures when run with full
suite ... tests pass in isolation". That reason was false in both halves: run
alone the file produced **24 failures and 5 errors**, and the causes were not
isolation at all --

* **Stale signatures.** ``execute_move``, ``interact_with_target``,
  ``trigger_tile_events``, ``store_tile_modification``, ``save_game``,
  ``load_game`` and ``process_event_input`` were all called with the wrong
  arity, against an engine that had moved on.
* **Attributes that do not exist.** ``player.x`` / ``player.y`` (the real names
  are ``location_x`` / ``location_y``) and ``Universe.get_current_tile``.
* **``create_app()`` returns ``(app, socketio)``**, so ``app.config`` was a
  tuple attribute lookup.

Whole classes were deleted rather than repaired, each superseded by real
coverage that already exists:

* ``TestVerifyCombatEvent`` claimed to cover ``src/verify_combat_event.py``, a
  module deleted in the terminal teardown. Its ``test_imports`` imported four
  *unrelated* modules and asserted they were not ``None``; its
  ``test_verify_combat_event_module_execution`` was a triple no-op (guarded by
  ``if verify_path.exists():`` -- false -- around a ``try/except Exception:
  pass``). ``tests/test_verify_combat_event_unit.py`` covers CombatEvent
  deserialization for real, with a module-scoped universe.
* Roughly twenty ``if hasattr(game_service, 'get_quests'): ...`` bodies, for
  ``get_quests``, ``complete_quest``, ``get_reputation``, ``modify_reputation``,
  ``talk_to_npc``, ``get_dialogue_options``, ``buy_item``, ``sell_item``,
  ``apply_status_effect`` and ``remove_status_effect``. **None of those methods
  exist on GameService**, so every one of those tests ran zero production
  statements. ``test_game_service_public_surface_is_stable`` below replaces the
  lot with a single check that actually fails when the surface changes.
* The per-test ``Universe.build()`` fixture (73 calls, ~45 ms each, mutating
  module-level item/merchant registries -- CLAUDE.md, "Running Tests"). Every
  test here now uses ``live_world()``, which assembles the same graph by hand.
"""

import copy

import pytest

from src.api.services.game_service import GameService
from src.player import Player
from tests._gs_fixtures import GRID_3X3, live_world

import src.objects as objects


@pytest.fixture
def gs():
    return GameService()


@pytest.fixture
def world():
    return live_world(GRID_3X3)


@pytest.fixture
def player(world):
    return world[0]


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


#: Every public method ``GameService`` exposes. Pinned so a rename shows up as a
#: failing assertion here instead of as a silently-skipped ``hasattr`` guard in
#: a caller's test (which is exactly how ~20 tests in this file came to run no
#: production code at all).
GAME_SERVICE_PUBLIC_API = {
    # Added with the combat abort control (master).
    "abort_move",
    "allocate_level_up_points", "apply_tile_modifications",
    "capture_tile_object_baseline", "collect_combat_loot", "delete_save",
    "drop_item", "equip_item", "execute_move", "flee_combat",
    "get_available_commands", "get_available_moves", "get_combat_state",
    "get_combat_status", "get_current_room", "get_current_tile",
    "get_current_tile_object", "get_equipment", "get_explored_tiles",
    "get_inventory", "get_player_skills", "get_player_stats",
    "get_player_status", "get_shop_state", "get_tile", "get_world_info",
    "interact_with_target", "interact_with_tile", "is_player_dead",
    "learn_skill", "list_saves", "load_game", "move_player", "npc_chat_end",
    "npc_chat_history", "npc_chat_open", "npc_chat_respond",
    "persist_tile_state", "process_event_input", "save_game", "search",
    "set_suggestions_paused", "shop_buy", "shop_buyback", "shop_sell",
    "start_combat", "store_tile_modification", "trigger_combat_events",
    "trigger_tile_events", "unequip_item", "use_item",
}


class TestGameServiceSurface:
    def test_game_service_public_surface_is_stable(self):
        actual = {name for name in vars(GameService) if not name.startswith("_")}
        assert actual == GAME_SERVICE_PUBLIC_API

    @pytest.mark.parametrize(
        "absent",
        [
            "get_quests", "complete_quest", "get_reputation", "modify_reputation",
            "talk_to_npc", "get_dialogue_options", "buy_item", "sell_item",
            "apply_status_effect", "remove_status_effect",
        ],
    )
    def test_methods_the_old_tests_guarded_on_really_do_not_exist(self, absent):
        """Documents why those ~20 tests were no-ops, not flaky."""
        assert not hasattr(GameService, absent)


# ---------------------------------------------------------------------------
# get_tile / move_player edge inputs
# ---------------------------------------------------------------------------


class TestTileLookupEdges:
    def test_get_tile_off_the_map_reports_not_found(self, gs, player):
        assert gs.get_tile(player, 999, 999) == {"error": "Tile not found"}

    def test_get_tile_accepts_negative_coordinates_that_exist(self, gs, player):
        tile = gs.get_tile(player, -1, -1)
        assert (tile["x"], tile["y"]) == (-1, -1)
        assert tile["description"] == "Test room at (-1, -1)."

    def test_get_tile_reads_position_from_location_x_not_x(self, gs, player):
        """``player.x`` does not exist -- ``location_x``/``location_y`` do.

        The old tests here all did ``x, y = player.x, player.y``; that
        ``AttributeError`` was five of the file's failures.
        """
        assert not hasattr(player, "x") and not hasattr(player, "y")
        here = gs.get_tile(player, player.location_x, player.location_y)
        assert here["description"] == "Test room at (0, 0)."

    @pytest.mark.parametrize("direction", ["", "sideways", "up", "NORTHWARD"])
    def test_move_player_rejects_junk_directions_verbatim(self, gs, player,
                                                          direction):
        before = (player.location_x, player.location_y)

        result = gs.move_player(player, direction)

        assert result == {"error": f"Invalid direction: {direction}"}
        assert (player.location_x, player.location_y) == before

    def test_move_player_accepts_diagonals(self, gs, player):
        """Diagonal movement is supported; only the eight names are valid."""
        result = gs.move_player(player, "northeast")
        assert result["success"] is True
        assert (player.location_x, player.location_y) == (1, -1)

    def test_move_player_direction_is_case_insensitive(self, gs, player):
        assert gs.move_player(player, "NORTH")["success"] is True
        assert (player.location_x, player.location_y) == (0, -1)


# ---------------------------------------------------------------------------
# Search / interact
# ---------------------------------------------------------------------------


class TestSearchAndInteract:
    def test_search_reveals_a_hidden_object_and_reports_it(self, gs, player):
        chest = objects.Object(
            "Chest", "A chest.", tile=player.current_room, player=player,
            hidden=True, hide_factor=0,
        )
        player.current_room.objects_here.append(chest)

        result = gs.search(player)

        assert result["success"] is True
        assert chest.hidden is False, "a found object must stop being hidden"
        assert [f["name"] for f in result["found"]] == ["Chest"]
        assert result["found"][0]["type"] == "object"
        assert "found something interesting" in result["messages"][-1]

    def test_search_leaves_a_well_hidden_object_alone(self, gs, player):
        chest = objects.Object(
            "Chest", "A chest.", tile=player.current_room, player=player,
            hidden=True, hide_factor=1000,
        )
        player.current_room.objects_here.append(chest)

        result = gs.search(player)

        assert chest.hidden is True
        assert result["found"] == []

    @pytest.mark.parametrize(
        "target_id", ["npc:test", "object:chest", "invalid:target", "", "item_999"]
    )
    def test_interact_with_target_reports_every_bad_reference_the_same_way(
        self, gs, player, target_id
    ):
        assert gs.interact_with_target(player, target_id, "talk") == {
            "success": False,
            "message": "Target not found.",
        }

    def test_interact_with_target_resolves_a_real_object_by_its_wire_id(
        self, gs, player, caplog
    ):
        """A found target with an unsupported verb fails *differently* from a
        missing one -- proving the id actually resolved."""
        chest = objects.Object(
            "Chest", "A chest.", tile=player.current_room, player=player
        )
        player.current_room.objects_here.append(chest)

        room = gs.get_current_room(player)
        (entry,) = room["objects"]
        assert entry["name"] == "Chest"

        with caplog.at_level("CRITICAL"):
            result = gs.interact_with_target(player, entry["id"], "look")

        assert result["success"] is False
        assert result["message"] != "Target not found.", "the id must have resolved"
        assert "no attribute 'look'" in result["message"]


# ---------------------------------------------------------------------------
# Tile modification round trip
# ---------------------------------------------------------------------------


class TestTileModificationRoundTrip:
    def test_block_exit_survives_a_store_then_apply(self, gs, player):
        tile = player.current_room
        session_data = {}

        gs.store_tile_modification(session_data, tile.x, tile.y, "block_exit",
                                   {"north": True})
        gs.apply_tile_modifications(tile, session_data)

        assert tile.block_exit == {"north": True}

    def test_apply_captures_an_object_baseline_on_first_visit(self, gs, player):
        tile = player.current_room
        tile.objects_here.append(
            objects.Object("Crate", "A crate.", tile=tile, player=player)
        )
        session_data = {}

        gs.apply_tile_modifications(tile, session_data)

        assert session_data["tile_modifications"]["0,0"]["objects_baseline"] == [
            "Crate"
        ]

    def test_removed_objects_stay_removed_across_revisits(self, gs, player):
        tile = player.current_room
        tile.objects_here.append(
            objects.Object("Crate", "A crate.", tile=tile, player=player)
        )
        session_data = {}
        gs.apply_tile_modifications(tile, session_data)  # baseline

        gs.store_tile_modification(session_data, 0, 0, "objects_removed", ["Crate"])
        gs.apply_tile_modifications(tile, session_data)
        assert tile.objects_here == []

        # Re-applying must be a no-op, not remove another one (issue #328).
        gs.apply_tile_modifications(tile, session_data)
        assert tile.objects_here == []

    def test_a_second_crate_spawned_at_runtime_is_kept(self, gs, player):
        """The allowance is computed from the baseline, so extras survive."""
        tile = player.current_room
        first = objects.Object("Crate", "A crate.", tile=tile, player=player)
        tile.objects_here.append(first)
        session_data = {}
        gs.apply_tile_modifications(tile, session_data)

        gs.store_tile_modification(session_data, 0, 0, "objects_removed", ["Crate"])
        spawned = objects.Object("Barrel", "A barrel.", tile=tile, player=player)
        tile.objects_here.append(spawned)

        gs.apply_tile_modifications(tile, session_data)

        assert tile.objects_here == [spawned]

    def test_apply_tile_modifications_tolerates_a_missing_tile(self, gs, player):
        """A ``None`` tile returns before anything is read or written.

        The guard has to sit above ``capture_tile_object_baseline`` — the
        comparison below pins that, since a real tile *does* get a baseline
        stamped into the same session_data.
        """
        session_data = {"tile_modifications": {"0,0": {"block_exit": ["north"]}}}
        untouched = copy.deepcopy(session_data)

        gs.apply_tile_modifications(None, session_data)

        assert session_data == untouched

        # Same call with a real tile is *not* inert: it stamps the baseline.
        tile = player.current_room
        tile.objects_here.append(
            objects.Object("Crate", "A crate.", tile=tile, player=player)
        )
        gs.apply_tile_modifications(tile, session_data)
        assert session_data["tile_modifications"]["0,0"]["objects_baseline"] == ["Crate"]
        assert tile.block_exit == ["north"]

    def test_apply_tile_modifications_ignores_another_tiles_entry(self, gs, player):
        tile = player.current_room
        session_data = {}
        gs.store_tile_modification(session_data, 5, 5, "block_exit", {"north": True})

        gs.apply_tile_modifications(tile, session_data)

        assert tile.block_exit == []


# ---------------------------------------------------------------------------
# Degenerate players
# ---------------------------------------------------------------------------


class TestDegenerateInputs:
    def test_get_current_room_with_no_universe(self, gs):
        orphan = Player()
        orphan.universe = None
        assert gs.get_current_room(orphan) == {
            "error": "Player universe not initialized"
        }

    def test_get_current_room_with_no_maps(self, gs):
        orphan = Player()
        orphan.universe = None
        assert "error" in gs.get_current_room(orphan)

    def test_execute_move_outside_combat_never_raises(self, gs, player):
        assert gs.execute_move(player, "move", "InvalidMoveNameXYZ") == {
            "success": False,
            "error": "Not in combat",
        }

    def test_two_execute_move_calls_outside_combat_are_both_refused(self, gs, player):
        """The old "concurrent combat" test asserted nothing at all."""
        first = gs.execute_move(player, "move", "0")
        second = gs.execute_move(player, "move", "1")
        assert first == second == {"success": False, "error": "Not in combat"}

    def test_trigger_tile_events_returns_a_list_not_a_dict(self, gs, player):
        """The old test allowed ``None`` or a dict; the contract is a list."""
        result = gs.trigger_tile_events(player, player.current_room)
        assert result == []


# ---------------------------------------------------------------------------
# Real app factory / route wiring
# ---------------------------------------------------------------------------


class TestAPIRouteWiring:
    """Route wiring facts, checked against the *real* application factory.

    Deliberately no ``/api/test/session`` calls: creating a session builds a
    full ``Universe`` and mutates module-level item/merchant registries, which
    CLAUDE.md reserves for ``tests/api/``. Everything here is session-free.
    """

    def test_create_app_returns_an_app_and_a_socketio(self, make_api_app):
        app, socketio = make_api_app(with_socketio=True)
        assert app.config["TESTING"] is True
        assert socketio is not None
        assert hasattr(socketio, "emit")

    @pytest.mark.parametrize(
        "method, path",
        [
            ("post", "/api/world/move"),
            ("get", "/api/inventory"),
            ("get", "/api/combat/status"),
            ("post", "/api/combat/start"),
        ],
    )
    def test_protected_routes_401_without_an_authorization_header(
        self, make_api_app, method, path
    ):
        client = make_api_app().test_client()

        response = getattr(client, method)(path, json={"direction": "north"})

        assert response.status_code == 401
        assert response.get_json() == {
            "success": False,
            "error": "Missing or invalid Authorization header",
        }

    def test_debug_blueprint_is_registered_only_in_testing(self, make_api_app):
        """``/api/debug/*`` must never be reachable in production."""
        rules = {r.rule for r in make_api_app().url_map.iter_rules()}
        assert "/api/debug/player" in rules
        assert "/api/test/session" in rules

    def test_core_blueprints_are_all_mounted_under_api(self, make_api_app):
        rules = {r.rule for r in make_api_app().url_map.iter_rules()}
        for expected in (
            "/api/auth/login",
            "/api/world/move",
            "/api/combat/move",
            "/api/inventory",
        ):
            assert expected in rules, f"{expected} is not routed"

    def test_unknown_path_returns_json_not_an_html_error_page(self, make_api_app):
        response = make_api_app().test_client().get("/api/definitely-not-a-route")

        assert response.status_code == 404
