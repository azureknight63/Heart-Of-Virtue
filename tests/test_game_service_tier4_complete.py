"""GameService: end-to-end behaviour on a real ``Player``/``Universe``/``MapTile`` graph.

Rewritten from the ground up. Every one of the 45 tests that used to live here
was blanket-skipped ("Tier 4 advanced tests - coverage requirements already
met") *and* vacuous: the body was a call wrapped in ``try: ... except
Exception: pass`` followed by ``assert isinstance(result, dict)``. Not one of
them could fail if ``GameService`` returned the wrong dict, the wrong values,
or mutated the wrong player -- and several called methods with the wrong
arity, which the bare ``except`` then swallowed.

Two structural changes:

* **Real objects, real assertions.** Every test drives ``live_world()`` from
  ``tests/_gs_fixtures.py`` and asserts on concrete return values and state
  transitions.
* **No ``Universe.build()``.** The old fixtures called it 14 times. It costs
  ~45 ms a call and mutates module-level item/merchant registries (CLAUDE.md,
  "Running Tests"), which is both slow and a parallelism hazard. ``live_world``
  assembles the same graph by hand in well under a millisecond.

Deliberately dropped (covered elsewhere, with real assertions):
``save_game`` / ``load_game`` / ``list_saves`` / ``delete_save`` -- the four
async tests here patched the coroutine under test out with an ``AsyncMock`` and
then awaited the mock, so they exercised zero production statements.
``tests/test_game_service_tier5_coverage.py`` covers all four for real
(autosave gating, the 20-save cap, deserialization failure, timezone
fallback).
"""

import pytest

from src.api.services.game_service import GameService
from src.player import Player
from src.universe import Universe
from tests._gs_fixtures import GRID_3X3, live_world


@pytest.fixture
def gs():
    return GameService()


@pytest.fixture
def world():
    """Real player on a 3x3 grid centred on the origin (all eight exits open)."""
    player, game_map = live_world(GRID_3X3)
    return player, game_map


@pytest.fixture
def player(world):
    return world[0]


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------


class TestGameServiceCoreInitialization:
    def test_game_service_holds_no_instance_state(self):
        """``__init__`` is ``pass``; two instances must be indistinguishable."""
        assert GameService().__dict__ == {}
        assert not hasattr(GameService(), "universe")

    def test_story_helper_returns_the_universes_story_dict(self, player):
        player.universe.story = {"met_gorran": True}
        assert GameService._story(player) is player.universe.story
        assert GameService._story(player)["met_gorran"] is True

    def test_story_helper_returns_empty_dict_without_a_universe(self):
        orphan = Player()
        orphan.universe = None
        assert GameService._story(orphan) == {}

    def test_game_tick_helper_reads_the_live_tick(self, player):
        player.universe.game_tick = 42
        assert GameService._game_tick(player) == 42

    def test_game_tick_helper_defaults_to_zero_without_a_universe(self):
        orphan = Player()
        orphan.universe = None
        assert GameService._game_tick(orphan) == 0


# ---------------------------------------------------------------------------
# Rooms, tiles, movement
# ---------------------------------------------------------------------------


class TestGameServiceWorldMethods:
    def test_get_current_room_describes_the_tile_under_the_player(self, gs, player):
        room = gs.get_current_room(player)

        assert (room["x"], room["y"]) == (player.location_x, player.location_y)
        assert room["description"] == "Test room at (0, 0)."
        assert room["map_name"] == "gs-test-map"
        assert room["is_passable"] is True
        assert room["items"] == [] and room["npcs"] == [] and room["objects"] == []

    def test_get_current_room_lists_all_eight_exits_on_a_full_grid(self, gs, player):
        exits = gs.get_current_room(player)["exits"]

        assert set(exits) == {
            "north", "south", "east", "west",
            "northeast", "northwest", "southeast", "southwest",
        }
        assert exits["north"] == {"x": 0, "y": -1}
        assert exits["southwest"] == {"x": -1, "y": 1}

    def test_exits_omit_directions_with_no_tile(self, gs, world):
        """A 1x1 map has no neighbours, so the exit set must be empty."""
        lone_player, _ = live_world([(0, 0)])
        assert gs.get_current_room(lone_player)["exits"] == {}

    def test_get_tile_reads_an_arbitrary_coordinate(self, gs, player):
        tile = gs.get_tile(player, 1, -1)

        assert (tile["x"], tile["y"]) == (1, -1)
        assert tile["description"] == "Test room at (1, -1)."
        assert tile["is_passable"] is True

    def test_calculate_exits_matches_the_serialized_room(self, gs, player):
        direct = gs._calculate_exits(player.universe, player.current_room, 0, 0)
        assert direct == gs.get_current_room(player)["exits"]

    def test_resolve_bgm_is_none_for_a_tile_with_no_track(self, gs, player):
        assert gs._resolve_bgm(player.current_room, player) is None

    def test_resolve_bgm_returns_the_tiles_track(self, gs, player):
        player.current_room.bgm = "mineral-pools"
        assert gs._resolve_bgm(player.current_room, player) == "mineral-pools"

    @pytest.mark.parametrize(
        "direction, expected",
        [
            ("north", (0, -1)),
            ("south", (0, 1)),
            ("east", (1, 0)),
            ("west", (-1, 0)),
            ("northeast", (1, -1)),
            ("southwest", (-1, 1)),
        ],
    )
    def test_move_player_moves_jean_and_reports_the_new_position(
        self, gs, player, direction, expected
    ):
        result = gs.move_player(player, direction)

        assert result["success"] is True
        assert result["new_position"] == {"x": expected[0], "y": expected[1]}
        assert (player.location_x, player.location_y) == expected
        assert player.current_room is player.map[expected]
        assert result["combat_started"] is False

    def test_move_player_rejects_an_unknown_direction_without_moving(self, gs, player):
        before = (player.location_x, player.location_y)

        result = gs.move_player(player, "invalid")

        assert result == {"error": "Invalid direction: invalid"}
        assert (player.location_x, player.location_y) == before

    def test_move_player_refuses_to_leave_the_map(self, gs):
        lone_player, _ = live_world([(0, 0)])
        result = gs.move_player(lone_player, "north")

        assert result.get("success") is not True
        assert (lone_player.location_x, lone_player.location_y) == (0, 0)

    def test_move_player_advances_the_game_tick(self, gs, player):
        """Map-entry spawners depend on this; see CLAUDE.md's completed milestones."""
        before = player.universe.game_tick
        gs.move_player(player, "north")
        assert player.universe.game_tick > before

    def test_explored_tiles_accumulate_as_jean_walks(self, gs, player):
        assert gs.get_explored_tiles(player) == {}

        gs.move_player(player, "north")
        gs.move_player(player, "east")

        explored = gs.get_explored_tiles(player)
        assert set(explored) == {"gs-test-map:0,-1", "gs-test-map:1,-1"}
        assert "south" in explored["gs-test-map:0,-1"]["exits"]

    def test_record_exploration_is_idempotent(self, gs, player):
        gs._record_exploration(player, player.current_room)
        gs._record_exploration(player, player.current_room)

        assert len(gs.get_explored_tiles(player)) == 1

    def test_search_reports_an_empty_room_honestly(self, gs, player):
        result = gs.search(player)

        assert result["success"] is True
        assert result["found"] == []
        assert "couldn't find anything" in result["messages"][0]
        assert result["room"]["x"] == 0


# ---------------------------------------------------------------------------
# Inventory / equipment
# ---------------------------------------------------------------------------


class TestGameServiceInventoryMethods:
    def test_get_inventory_summarises_the_real_pack(self, gs, player):
        result = gs.get_inventory(player)

        assert result["item_count"] == len(player.inventory)
        assert [i["name"] for i in result["items"]] == [
            i.name for i in player.inventory
        ]
        assert result["weight_limit"] > 0
        assert 0 <= result["weight_percentage"] <= 100

    def test_get_inventory_tracks_an_added_item(self, gs, player, make_weapon):
        before = gs.get_inventory(player)
        dagger = make_weapon("Dagger")
        player.inventory.append(dagger)

        after = gs.get_inventory(player)

        assert after["item_count"] == before["item_count"] + 1
        assert after["total_weight"] == pytest.approx(
            before["total_weight"] + dagger.weight
        )

    def test_get_equipment_reports_the_equipped_weapon(self, gs, player, make_weapon):
        player.eq_weapon = make_weapon("Sword")

        result = gs.get_equipment(player)

        weapon = result["equipped"]["weapon"]
        assert weapon["item_name"] == player.eq_weapon.name
        assert weapon["slot"] == "weapon"
        assert weapon["equipped"] is True
        assert weapon["damage"] == player.eq_weapon.damage
        assert result["equipment_value"] >= player.eq_weapon.value

    def test_equip_item_rejects_an_unknown_reference(self, gs, player):
        assert gs.equip_item(player, "nonexistent_item_xyz") == {
            "error": "Item cannot be equipped"
        }


# ---------------------------------------------------------------------------
# Player status / skills
# ---------------------------------------------------------------------------


class TestGameServicePlayerStatusMethods:
    def test_get_player_status_mirrors_live_player_state(self, gs, player):
        player.hp = 37

        status = gs.get_player_status(player)

        assert status["name"] == player.name
        assert status["hp"] == 37
        assert status["max_hp"] == player.maxhp
        assert status["level"] == player.level
        assert status["fatigue"] == player.fatigue
        # Attributes the engine does not have must not appear on the wire.
        assert "health" not in status and "stamina" not in status

    def test_get_player_stats_exposes_base_and_effective_attributes(self, gs, player):
        player.strength = 25

        stats = gs.get_player_stats(player)

        assert stats["strength"] == 25
        assert stats["strength_base"] == player.strength_base
        assert stats["max_hp"] == player.maxhp
        assert stats["attack_damage_min"] <= stats["attack_damage_max"]

    def test_get_player_skills_lists_known_moves_and_the_tree(self, gs, player):
        skills = gs.get_player_skills(player)

        assert [m["name"] for m in skills["known_moves"]] == [
            m.name for m in player.known_moves
        ]
        assert skills["skill_exp"] == player.skill_exp
        assert "Basic" in skills["skill_tree"]

    def test_learn_skill_rejects_an_unknown_category(self, gs, player):
        result = gs.learn_skill(player, "Dodge", "Offensive")
        assert result == {"success": False, "error": "Invalid category: Offensive"}

    def test_learn_skill_rejects_an_unknown_skill(self, gs, player):
        result = gs.learn_skill(player, "NoSuchSkill", "Basic")
        assert result["success"] is False
        assert "not found in category" in result["error"]

    def test_learn_skill_refuses_a_skill_jean_already_knows(self, gs, player):
        assert "Dodge" in [m.name for m in player.known_moves]
        assert gs.learn_skill(player, "Dodge", "Basic") == {
            "success": False,
            "error": "Skill already learned",
        }

    def test_learn_skill_enforces_the_experience_requirement(self, gs, player):
        player.skill_exp["Basic"] = 0

        result = gs.learn_skill(player, "Strategic Insight", "Basic")

        assert result["success"] is False
        assert result["error"] == (
            "Not enough experience. Required: 500, Available: 0"
        )
        assert "Strategic Insight" not in [m.name for m in player.known_moves]

    def test_learn_skill_spends_experience_and_grants_the_move(self, gs, player):
        player.skill_exp["Basic"] = 500

        result = gs.learn_skill(player, "Strategic Insight", "Basic")

        assert result["success"] is True
        assert result["message"] == "Learned Strategic Insight!"
        assert result["remaining_exp"] == 0
        assert player.skill_exp["Basic"] == 0
        assert "Strategic Insight" in [m.name for m in player.known_moves]

    def test_get_available_commands_out_of_combat(self, gs, player):
        result = gs.get_available_commands(player)

        names = [c["name"] for c in result["commands"]]
        assert names == ["Search", "Menu", "Save"]
        assert result["count"] == len(result["commands"])


# ---------------------------------------------------------------------------
# Combat entry points (out of combat)
# ---------------------------------------------------------------------------


class TestGameServiceCombatMethods:
    def test_start_combat_rejects_an_enemy_that_is_not_here(self, gs, player):
        assert gs.start_combat(player, "enemy_999") == {"error": "Enemy not found"}
        assert getattr(player, "in_combat", False) is False

    def test_execute_move_outside_combat_is_refused(self, gs, player):
        result = gs.execute_move(player, "move", "0")
        assert result == {"success": False, "error": "Not in combat"}

    def test_get_combat_status_reports_no_active_combat(self, gs, player):
        assert gs.get_combat_status(player) == {
            "combat_active": False,
            "log": [],
            "battle_state": None,
        }

    def test_get_available_moves_is_empty_without_a_combat_adapter(self, gs, player):
        """It reads the *adapter's* pending options, not ``player.known_moves``."""
        assert not hasattr(player, "_combat_adapter")
        assert gs.get_available_moves(player) == {"moves": []}

    def test_get_available_moves_serialises_the_adapters_pending_options(
        self, gs, player, make_npc, make_adapter
    ):
        adapter = make_adapter(player, [make_npc()])
        adapter.input_type = "move_selection"
        adapter.available_options = [
            {
                "name": "Attack",
                "description": "Strike.",
                "fatigue_cost": 74,
                "category": "Offensive",
                "beats_left": 1,
            }
        ]
        player._combat_adapter = adapter

        result = gs.get_available_moves(player)

        assert result["moves"] == [
            {
                "id": "0",
                "name": "Attack",
                "description": "Strike.",
                "fatigue_cost": 74,
                "category": "Offensive",
                "beats_left": 1,
            }
        ]

    def test_get_available_moves_is_empty_while_awaiting_a_target(
        self, gs, player, make_npc, make_adapter
    ):
        """Target/direction prompts must not leak into the move list."""
        adapter = make_adapter(player, [make_npc()])
        adapter.input_type = "target_selection"
        adapter.available_options = [{"name": "Slime"}]
        player._combat_adapter = adapter

        assert gs.get_available_moves(player) == {"moves": []}

    def test_trigger_combat_events_returns_nothing_out_of_combat(self, gs, player):
        assert gs.trigger_combat_events(player) == []

    def test_is_player_dead_tracks_hp(self, gs, player):
        assert gs.is_player_dead(player) is False
        player.hp = 0
        assert gs.is_player_dead(player) is True


# ---------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------


class TestGameServiceInteractionMethods:
    def test_interact_with_target_reports_a_missing_target(self, gs, player):
        assert gs.interact_with_target(player, "invalid_target", "action") == {
            "success": False,
            "message": "Target not found.",
        }

    def test_interact_with_target_finds_an_item_on_the_floor(
        self, gs, player, make_weapon
    ):
        dagger = make_weapon("Dagger")
        player.current_room.items_here.append(dagger)

        room = gs.get_current_room(player)
        (entry,) = room["items"]
        result = gs.interact_with_target(player, entry["id"], "take")

        assert result["success"] is True
        assert dagger in player.inventory
        assert dagger not in player.current_room.items_here


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class TestGameServiceEventProcessing:
    def test_trigger_tile_events_on_an_eventless_tile(self, gs, player):
        assert gs.trigger_tile_events(player, player.current_room) == []

    def test_clean_event_output_strips_ansi_escape_codes(self, gs):
        raw = "\x1b[32mJean\x1b[0m steps forward."

        cleaned = gs._clean_event_output(raw)

        assert cleaned == "Jean steps forward."

    def test_clean_event_output_leaves_plain_text_untouched(self, gs):
        text = "Test output with **bold** and formatting"
        assert gs._clean_event_output(text) == text


# ---------------------------------------------------------------------------
# Tile modification persistence
# ---------------------------------------------------------------------------


class TestGameServiceDataPersistence:
    def test_store_tile_modification_keys_by_coordinate(self, gs):
        session_data = {}

        gs.store_tile_modification(session_data, 1, 2, "opened_chest", {"gold": 5})

        assert session_data == {
            "tile_modifications": {"1,2": {"opened_chest": {"gold": 5}}}
        }

    def test_store_tile_modification_merges_into_the_same_tile(self, gs):
        session_data = {}

        gs.store_tile_modification(session_data, 1, 2, "opened_chest", {"gold": 5})
        gs.store_tile_modification(session_data, 1, 2, "looted", ["Dagger"])

        assert session_data["tile_modifications"]["1,2"] == {
            "opened_chest": {"gold": 5},
            "looted": ["Dagger"],
        }

    def test_store_tile_modification_keeps_tiles_separate(self, gs):
        session_data = {}

        gs.store_tile_modification(session_data, 1, 2, "looted", ["A"])
        gs.store_tile_modification(session_data, 3, 4, "looted", ["B"])

        assert set(session_data["tile_modifications"]) == {"1,2", "3,4"}

    def test_apply_tile_modifications_with_no_stored_state_is_a_no_op(self, gs, player):
        tile = player.current_room
        before = list(tile.items_here)

        gs.apply_tile_modifications(tile, {})

        assert tile.items_here == before


# ---------------------------------------------------------------------------
# Degenerate inputs
# ---------------------------------------------------------------------------


class TestGameServiceErrorHandling:
    def test_get_current_room_without_a_universe_returns_a_structured_error(self, gs):
        """A player with no universe yields a 4xx-shaped payload, never a crash."""
        orphan = Player()
        orphan.universe = None

        assert gs.get_current_room(orphan) == {
            "error": "Player universe not initialized"
        }

    def test_get_tile_off_the_map_returns_a_structured_error(self, gs, player):
        result = gs.get_tile(player, 99, 99)
        assert result.get("error")

    def test_get_player_status_on_a_bare_player_still_serialises(self, gs):
        """A Player with no universe is still a valid subject for status."""
        lone = Player()

        status = gs.get_player_status(lone)

        assert status["name"] == lone.name
        assert status["hp"] == lone.hp


# ---------------------------------------------------------------------------
# Multi-step flows
# ---------------------------------------------------------------------------


class TestGameServiceIntegration:
    def test_walk_search_and_come_back(self, gs, player):
        """Exploration state, position and room payload stay consistent."""
        assert gs.move_player(player, "north")["success"] is True
        assert gs.get_current_room(player)["y"] == -1
        assert gs.search(player)["room"]["y"] == -1

        assert gs.move_player(player, "south")["success"] is True
        assert (player.location_x, player.location_y) == (0, 0)

        # Both tiles are remembered, not just the current one.
        assert set(gs.get_explored_tiles(player)) == {
            "gs-test-map:0,-1",
            "gs-test-map:0,0",
        }

    def test_universe_is_reachable_only_through_the_player(self, gs, player):
        """Regression guard for the ``self.universe`` bug CLAUDE.md documents."""
        assert isinstance(player.universe, Universe)
        assert gs._story(player) is player.universe.story
