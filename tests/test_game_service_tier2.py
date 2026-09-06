"""GameService's non-combat public surface: chat, loot, world info, commands.

History
-------
"Tier 2" was a coverage-chasing file: 28 tests, 22 of which asserted only
``assert result is not None`` against a ``MagicMock`` player whose universe
answered every attribute — so *every* method returned a truthy dict no matter
what it did. Three more tests ("test_get_current_tile", "test_search_tile",
"test_get_current_room") had a docstring, a comment, and a bare ``pass``: they
collected and passed while testing nothing at all.

The method list it named was worth keeping, so each entry is now driven through a
real ``Player``/``Universe``/``MapTile`` graph and asserts the payload the service
actually produces. NPC chat is the one area that still uses a hand-written double,
because the real mixin calls an LLM — but the double is a real class with real
``chat_open``/``chat_respond`` methods, so the lookup-by-class-name, the
``_active_chat_npc_id`` bookkeeping (#336) and the relationship enrichment are all
exercised for real.

Tile-modification and exploration tests that lived here are covered far more
thoroughly in ``test_game_service_world.py`` and are not duplicated.
"""

import pytest

from src.items import Gold, RustedDagger, Restorative
from src.npc import NPC
from tests._gs_fixtures import GRID_3X3, live_world


@pytest.fixture
def world():
    return live_world(GRID_3X3)


@pytest.fixture
def player(world):
    return world[0]


@pytest.fixture
def tile(world):
    return world[1][(0, 0)]


class ChattyNPC(NPC):
    """A real NPC subclass exposing the chat protocol without touching an LLM.

    ``npc_chat_open`` looks NPCs up by ``type(npc).__name__`` *or* ``npc.name``,
    so the class name here is load-bearing for the lookup tests.
    """

    def __init__(self, name="Talky", open_result=None, respond_result=None):
        super().__init__(
            name=name,
            description="Someone worth talking to.",
            damage=1,
            aggro=False,
            exp_award=0,
            friend=True,
        )
        self.open_result = open_result or {"success": True, "reputation": 40}
        self.respond_result = respond_result or {"success": True, "reputation": 40}
        self.opened_with = None
        self.responded_with = None

    def chat_open(self, player):
        self.opened_with = player
        return dict(self.open_result)

    def chat_respond(self, player, jean_text, jean_tone="direct"):
        self.responded_with = (player, jean_text, jean_tone)
        return dict(self.respond_result)


class MuteNPC(NPC):
    """An NPC with no chat protocol at all — the 'does not support chat' branch."""

    def __init__(self):
        super().__init__(
            name="Mute",
            description="Says nothing.",
            damage=1,
            aggro=False,
            exp_award=0,
        )


class TestNpcChatOpen:
    """``npc_chat_open`` finds the NPC, records the active chat, enriches the result."""

    def test_opens_chat_and_marks_the_npc_active(self, game_service, player, tile):
        npc = ChattyNPC()
        tile.npcs_here = [npc]

        result = game_service.npc_chat_open(player, "ChattyNPC")

        assert result["success"] is True
        assert npc.opened_with is player
        assert player.__dict__["_active_chat_npc_id"] == "ChattyNPC"

    def test_matches_by_display_name_too(self, game_service, player, tile):
        npc = ChattyNPC(name="Gorran")
        tile.npcs_here = [npc]
        assert game_service.npc_chat_open(player, "Gorran")["success"] is True
        assert npc.opened_with is player

    def test_relationship_badge_is_derived_from_reputation(
        self, game_service, player, tile
    ):
        """The chat mixin only returns a raw int; the badge is built API-side."""
        tile.npcs_here = [ChattyNPC(name="Gorran", open_result={"success": True, "reputation": 40})]

        relationship = game_service.npc_chat_open(player, "Gorran")["relationship"]

        assert relationship["npc_name"] == "Gorran"
        assert relationship["reputation"] == 40
        assert relationship["attitude"] == "favorable"

    def test_npc_not_on_tile_is_an_error(self, game_service, player, tile):
        tile.npcs_here = []
        result = game_service.npc_chat_open(player, "Gorran")
        assert result == {"success": False, "error": "NPC 'Gorran' not found"}
        assert "_active_chat_npc_id" not in player.__dict__

    def test_npc_without_chat_support_is_an_error(self, game_service, player, tile):
        tile.npcs_here = [MuteNPC()]
        result = game_service.npc_chat_open(player, "Mute")
        assert result == {"success": False, "error": "NPC does not support chat"}

    def test_raising_chat_open_clears_the_active_marker(self, game_service, player, tile):
        """#336: a failed open must not permanently suppress loquacity recovery."""

        class ExplodingNPC(ChattyNPC):
            def chat_open(self, player):
                raise RuntimeError("llm down")

        tile.npcs_here = [ExplodingNPC(name="Gorran")]

        result = game_service.npc_chat_open(player, "Gorran")

        assert result["success"] is False
        # The exception string used to be interpolated into the
        # client-facing error and rendered verbatim in the player's panel.
        # A provider SDK exception stringifies to endpoint URL, model id,
        # status body and request id; the detail belongs in the server log.
        assert result["error"] == "Could not start that conversation."
        assert "llm down" not in result["error"]
        assert "_active_chat_npc_id" not in player.__dict__

    def test_immediate_brush_off_clears_the_active_marker(self, game_service, player, tile):
        """Loquacity exhausted: the conversation ends before it begins (#336)."""
        tile.npcs_here = [
            ChattyNPC(name="Gorran", open_result={"success": True, "conversation_ended": True})
        ]

        game_service.npc_chat_open(player, "Gorran")

        assert "_active_chat_npc_id" not in player.__dict__


class TestNpcChatRespond:
    """``npc_chat_respond`` forwards Jean's line and tears down on exhaustion."""

    def test_forwards_text_and_tone_to_the_npc(self, game_service, player, tile):
        npc = ChattyNPC(name="Gorran")
        tile.npcs_here = [npc]

        result = game_service.npc_chat_respond(player, "Gorran", "Well met.", "open")

        assert result["success"] is True
        assert npc.responded_with == (player, "Well met.", "open")

    def test_default_tone_is_direct(self, game_service, player, tile):
        npc = ChattyNPC(name="Gorran")
        tile.npcs_here = [npc]
        game_service.npc_chat_respond(player, "Gorran", "Hello")
        assert npc.responded_with[2] == "direct"

    def test_conversation_ended_clears_the_active_marker(self, game_service, player, tile):
        tile.npcs_here = [
            ChattyNPC(
                name="Gorran",
                respond_result={"success": True, "conversation_ended": True},
            )
        ]
        player.__dict__["_active_chat_npc_id"] = "Gorran"

        game_service.npc_chat_respond(player, "Gorran", "Farewell.")

        assert "_active_chat_npc_id" not in player.__dict__

    def test_missing_npc_is_an_error(self, game_service, player, tile):
        tile.npcs_here = []
        assert game_service.npc_chat_respond(player, "Gorran", "Hi") == {
            "success": False,
            "error": "Active chat NPC not found",
        }

    def test_npc_raising_is_reported_not_propagated(self, game_service, player, tile):
        class ExplodingNPC(ChattyNPC):
            def chat_respond(self, player, jean_text, jean_tone="direct"):
                raise RuntimeError("llm down")

        tile.npcs_here = [ExplodingNPC(name="Gorran")]
        result = game_service.npc_chat_respond(player, "Gorran", "Hi")
        assert result["success"] is False
        assert result["error"] == "Could not deliver that reply."
        assert "llm down" not in result["error"]


class TestNpcChatEndAndHistory:
    """Teardown and history read-back."""

    def test_end_clears_the_active_marker_and_reports_the_count(
        self, game_service, player
    ):
        player.__dict__["_active_chat_npc_id"] = "Gorran"
        player.npc_chat_histories = {"Gorran": {"conversation_count": 3}}

        result = game_service.npc_chat_end(player, "Gorran")

        assert result == {"success": True, "data": {"conversation_count": 3}}
        assert "_active_chat_npc_id" not in player.__dict__

    def test_end_on_an_unknown_npc_reports_zero(self, game_service, player):
        player.npc_chat_histories = {}
        assert game_service.npc_chat_end(player, "Nobody") == {
            "success": True,
            "data": {"conversation_count": 0},
        }

    def test_history_returns_stored_exchanges(self, game_service, player):
        player.npc_chat_histories = {
            "NomadCamper_0": {
                "exchanges": [{"jean": "Hello", "npc": "Mm."}],
                "conversation_count": 2,
                "last_talked_tick": 41,
                "loquacity_current": 3,
                "loquacity_max": 5,
            }
        }

        data = game_service.npc_chat_history(player, "NomadCamper_0")["data"]

        assert data["npc_key"] == "NomadCamper_0"
        # No given_name in the personality, so the suffix is stripped for display.
        assert data["npc_name"] == "NomadCamper"
        assert data["exchanges"] == [{"jean": "Hello", "npc": "Mm."}]
        assert data["conversation_count"] == 2
        assert data["loquacity_current"] == 3

    def test_history_prefers_the_personality_given_name(self, game_service, player):
        player.npc_chat_histories = {
            "NomadCamper_0": {"personality": {"given_name": "Adrienne"}}
        }
        data = game_service.npc_chat_history(player, "NomadCamper_0")["data"]
        assert data["npc_name"] == "Adrienne"

    def test_history_for_unknown_npc_is_an_error(self, game_service, player):
        player.npc_chat_histories = {}
        assert game_service.npc_chat_history(player, "Gorran") == {
            "success": False,
            "error": "No history for 'Gorran'",
        }

    def test_no_histories_attribute_at_all(self, game_service, player):
        assert not hasattr(player, "npc_chat_histories")
        assert game_service.npc_chat_history(player, "Gorran") == {
            "success": False,
            "error": "No chat history available",
        }


class TestDropItem:
    """``drop_item`` moves an item from inventory onto the tile."""

    def test_moves_the_item_onto_the_tile(self, game_service, player, tile):
        dagger = RustedDagger()
        player.inventory.append(dagger)

        result = game_service.drop_item(player, dagger)

        assert result["success"] is True
        assert result["item_name"] == "Rusted Dagger"
        assert dagger not in player.inventory
        assert dagger in tile.items_here

    def test_narrates_the_drop(self, game_service, player, tile):
        """``messages`` is the single source of truth for the client dialog."""
        dagger = RustedDagger()
        player.inventory.append(dagger)
        result = game_service.drop_item(player, dagger)
        assert result["messages"] == ["Jean drops Rusted Dagger."]

    def test_equipped_item_is_unequipped_first(self, game_service, player, tile):
        dagger = RustedDagger()
        player.inventory.append(dagger)
        player.equip_item(item_object=dagger)
        assert dagger.isequipped is True

        game_service.drop_item(player, dagger)

        assert dagger.isequipped is False
        assert player.eq_weapon is not dagger
        assert dagger in tile.items_here

    def test_item_not_in_inventory_is_an_error(self, game_service, player, tile):
        stray = RustedDagger()
        result = game_service.drop_item(player, stray)
        assert result == {"error": "Item not found in inventory"}
        assert stray not in tile.items_here


class TestCollectCombatLoot:
    """``collect_combat_loot`` moves chosen post-combat drops into the inventory."""

    def test_collects_named_items_and_leaves_the_rest(self, game_service, player, tile):
        dagger, potion = RustedDagger(), Restorative()
        tile.items_here = [dagger, potion]
        player.combat_drops = [dagger, potion]

        result = game_service.collect_combat_loot(player, ["Rusted Dagger"])

        assert result["collected"] == ["Rusted Dagger"]
        assert dagger in player.inventory
        assert tile.items_here == [potion]

    def test_clears_combat_drops_so_looting_cannot_repeat(self, game_service, player, tile):
        dagger = RustedDagger()
        tile.items_here = [dagger]
        player.combat_drops = [dagger]

        game_service.collect_combat_loot(player, ["Rusted Dagger"])

        assert player.combat_drops == []

    def test_unknown_name_is_skipped_with_a_reason(self, game_service, player, tile):
        tile.items_here = []
        result = game_service.collect_combat_loot(player, ["Excalibur"])
        assert result["collected"] == []
        assert result["skipped"] == [{"name": "Excalibur", "reason": "not_found"}]

    def test_over_capacity_items_are_skipped(self, game_service, player, tile):
        """weight_tolerance is the cap; an item that would breach it stays put."""
        anvil = RustedDagger()
        anvil.name = "Anvil"
        anvil.weight = player.weight_tolerance + 1
        tile.items_here = [anvil]

        result = game_service.collect_combat_loot(player, ["Anvil"])

        assert result["skipped"] == [{"name": "Anvil", "reason": "over_capacity"}]
        assert anvil in tile.items_here
        assert anvil not in player.inventory

    def test_empty_selection_collects_nothing(self, game_service, player, tile):
        dagger = RustedDagger()
        tile.items_here = [dagger]
        result = game_service.collect_combat_loot(player, [])
        assert result == {"success": True, "collected": [], "skipped": []}
        assert tile.items_here == [dagger]

    def test_none_selection_is_treated_as_empty(self, game_service, player, tile):
        assert game_service.collect_combat_loot(player, None)["collected"] == []

    @pytest.mark.parametrize(
        "bad,message",
        [
            ("Rusted Dagger", "Invalid item_names parameter: expected list, got str"),
            (7, "Invalid item_names parameter: expected list, got int"),
        ],
    )
    def test_non_list_selection_is_rejected(self, game_service, player, bad, message):
        assert game_service.collect_combat_loot(player, bad) == {
            "success": False,
            "error": message,
        }

    def test_non_string_entry_is_rejected(self, game_service, player):
        result = game_service.collect_combat_loot(player, ["Gold", 7])
        assert result["success"] is False
        assert result["error"] == "Invalid item name in list: expected string, got int"


class TestWorldInfo:
    """``get_world_info`` is the world-state summary the client polls."""

    def test_reports_position_story_flags_and_tick(self, game_service, player):
        player.universe.story["ch1_complete"] = True
        player.universe.game_tick = 100

        info = game_service.get_world_info(player)

        assert info["current_position"] == {"x": 0, "y": 0}
        assert info["story_flags"]["ch1_complete"] is True
        assert info["game_tick"] == 100

    def test_explored_tiles_track_the_rooms_visited(self, game_service, player):
        game_service.get_current_room(player)
        assert list(game_service.get_world_info(player)["explored_tiles"]) == [
            "gs-test-map:0,0"
        ]

    def test_no_universe_yields_an_empty_summary(self, game_service, player):
        player.universe = None
        assert game_service.get_world_info(player) == {}

    def test_get_current_tile_delegates_to_get_current_room(self, game_service, player):
        assert game_service.get_current_tile(player) == game_service.get_current_room(player)

    def test_get_current_tile_object_returns_the_live_tile(
        self, game_service, player, tile
    ):
        assert game_service.get_current_tile_object(player) is tile

    def test_get_current_tile_object_without_universe_is_none(self, game_service, player):
        player.universe = None
        assert game_service.get_current_tile_object(player) is None


class TestInteractWithTile:
    """``interact_with_tile`` echoes the action and the tile's contents."""

    def test_echoes_action_and_describes_contents(self, game_service, player, tile):
        tile.description = "A grassy meadow."
        tile.items_here = [Gold(amt=12)]

        result = game_service.interact_with_tile(player, "examine")

        assert result["action"] == "examine"
        assert result["description"] == "A grassy meadow."
        assert [i["name"] for i in result["items"]] == ["Gold"]

    def test_unknown_position_is_an_error(self, game_service, player):
        player.location_x, player.location_y = 42, 42
        assert game_service.interact_with_tile(player, "look") == {
            "error": "No tile at this location"
        }


class TestAvailableCommands:
    """``get_available_commands`` merges tile actions with the system commands."""

    def test_includes_the_tiles_own_actions(self, game_service, player):
        result = game_service.get_available_commands(player)
        names = [c["name"] for c in result["commands"]]
        assert "Search" in names
        assert result["count"] == len(result["commands"])

    def test_always_offers_save_and_menu(self, game_service, player):
        names = [c["name"] for c in game_service.get_available_commands(player)["commands"]]
        assert "Save" in names and "Menu" in names

    def test_system_commands_are_not_duplicated(self, game_service, player):
        names = [c["name"] for c in game_service.get_available_commands(player)["commands"]]
        assert names.count("Save") == 1
        assert names.count("Menu") == 1

    def test_hotkeys_are_carried_through(self, game_service, player):
        commands = game_service.get_available_commands(player)["commands"]
        search = next(c for c in commands if c["name"] == "Search")
        assert "search" in search["hotkey"]

    def test_failing_tile_actions_still_yield_system_commands(
        self, game_service, player, tile
    ):
        def boom(**kwargs):
            raise RuntimeError("tile broken")

        tile.available_actions = boom

        result = game_service.get_available_commands(player)

        assert [c["name"] for c in result["commands"]] == ["Save", "Menu"]


class TestCombatStateOutsideCombat:
    """``get_combat_state`` short-circuits when there is no fight."""

    def test_reports_not_in_combat(self, game_service, player):
        assert game_service.get_combat_state(player) == {
            "in_combat": False,
            "message": "Not in combat",
        }

    def test_no_adapter_means_no_moves(self, game_service, player):
        assert not hasattr(player, "_combat_adapter")
        assert game_service.get_available_moves(player) == {"moves": []}

    def test_is_player_dead_tracks_hp(self, game_service, player):
        assert game_service.is_player_dead(player) is False
        player.hp = 0
        assert game_service.is_player_dead(player) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
