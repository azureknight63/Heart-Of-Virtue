"""Player status readout and item use, against a real Player.

History
-------
This file was named for a coverage number ("8% to 80%+") rather than a
behaviour, and it showed: 14 of 19 tests asserted only ``result is not None``.
Two were worse than useless —

* ``test_engage_combat`` wrapped its assertion in
  ``except (NotImplementedError, AttributeError): pass``. ``engage_combat``
  does not exist on ``GameService``, so the test passed by swallowing the
  ``AttributeError`` it provoked. Deleted: there is no such method to test.
* ``test_get_inventory_with_items`` asserted ``len(result) >= 0`` — true of
  every collection in Python.

Its ``move_player`` / ``_story`` / ``_game_tick`` / ``get_inventory`` /
``drop_item`` / ``interact_with_tile`` tests were the weakest of several copies;
the strong versions now live in ``test_game_service_critical_methods.py``,
``test_game_service_methods.py`` and ``test_game_service_tier2.py``. The
``#377 previous_tile`` regression test is kept (it is the only one here that was
already real) and re-expressed on a real map instead of a patched
``_calculate_exits``.

What is left is what nothing else owned: the **player status readout** the HUD
polls every beat, and **item use**.
"""

import pytest

from src.api.services.game_service import GameService
from src.items import Gold, Restorative, RustedDagger
from src.npc import NPC
from tests._gs_fixtures import GRID_3X3, live_world, set_player_gold


@pytest.fixture(scope="session")
def game_service():
    """``GameService.__init__`` is ``pass`` — the service is stateless."""
    return GameService()


@pytest.fixture
def world():
    return live_world(GRID_3X3)


@pytest.fixture
def player(world):
    return world[0]


class _Fatigued:
    """A minimal status effect matching what ``_serialize_active_states`` reads."""

    def __init__(self, name="Fatigued", steps_left=3):
        self.name = name
        self.steps_left = steps_left
        self.beats_left = 2
        self.persistent = True
        self.description = "Worn down."


class TestGetPlayerStatus:
    """The HUD payload: identity, vitals, purse, encumbrance, party."""

    def test_reports_identity_and_vitals(self, game_service, player):
        player.hp = 60
        status = game_service.get_player_status(player)
        assert status["name"] == "Jean"
        assert status["level"] == player.level
        assert status["hp"] == 60
        assert status["max_hp"] == player.maxhp
        assert status["fatigue"] == player.fatigue
        assert status["max_fatigue"] == player.maxfatigue

    def test_experience_gap_is_precomputed(self, game_service, player):
        player.exp = 40
        player.exp_to_level = 150
        status = game_service.get_player_status(player)
        assert status["exp"] == 40
        assert status["max_exp"] == 150
        assert status["exp_to_next_level"] == 110

    def test_experience_gap_never_goes_negative(self, game_service, player):
        player.exp = 500
        player.exp_to_level = 150
        assert game_service.get_player_status(player)["exp_to_next_level"] == 0

    def test_gold_is_read_from_the_purse(self, game_service, player):
        set_player_gold(player, 321)
        assert game_service.get_player_status(player)["gold"] == 321

    def test_gold_stacks_are_consolidated_before_reporting(self, game_service, player):
        """``get_player_status`` calls ``stack_gold`` first, so split purses merge."""
        player.inventory = [Gold(amt=10), Gold(amt=5)]
        assert game_service.get_player_status(player)["gold"] == 15
        assert len([i for i in player.inventory if i.name == "Gold"]) == 1

    def test_weight_is_refreshed_from_the_real_inventory(self, game_service, player):
        before = game_service.get_player_status(player)["weight"]
        player.inventory.append(RustedDagger())

        status = game_service.get_player_status(player)

        assert status["weight"] == pytest.approx(before + RustedDagger().weight)
        assert status["max_weight"] == player.weight_tolerance
        assert status["weight_pct"] == pytest.approx(
            status["weight"] / status["max_weight"] * 100
        )

    def test_no_states_reads_as_normal(self, game_service, player):
        player.states = []
        status = game_service.get_player_status(player)
        assert status["state"] == "normal"
        assert status["states"] == []

    def test_the_first_state_names_the_summary_field(self, game_service, player):
        player.states = [_Fatigued("Poisoned"), _Fatigued("Slimed")]
        status = game_service.get_player_status(player)
        assert status["state"] == "Poisoned"
        assert [s["name"] for s in status["states"]] == ["Poisoned", "Slimed"]

    def test_pending_level_up_points_are_surfaced(self, game_service, player):
        player.pending_attribute_points = 4
        player.pending_level_ups = [2, 3]
        status = game_service.get_player_status(player)
        assert status["pending_attribute_points"] == 4
        assert status["pending_level_ups"] == [2, 3]

    def test_party_members_exclude_the_player_himself(self, game_service, player):
        """``combat_list_allies[0]`` is always Jean; the HUD lists only the rest."""
        gorran = NPC(
            name="Gorran",
            description="  A golemite.  ",
            damage=1,
            aggro=False,
            exp_award=0,
            friend=True,
        )
        player.combat_list_allies = [player, gorran]

        party = game_service.get_player_status(player)["party_members"]

        assert [p["name"] for p in party] == ["Gorran"]
        assert party[0]["id"] == f"ally_{id(gorran)}"
        assert party[0]["description"] == "A golemite."
        assert party[0]["hp"] == gorran.hp

    def test_allies_are_in_range_outside_combat(self, game_service, player):
        gorran = NPC(
            name="Gorran", description="", damage=1, aggro=False, exp_award=0, friend=True
        )
        player.combat_list_allies = [player, gorran]
        player.in_combat = False
        assert game_service.get_player_status(player)["party_members"][0]["in_range"] is True

    def test_a_distant_ally_is_out_of_range_in_combat(self, game_service, player):
        gorran = NPC(
            name="Gorran", description="", damage=1, aggro=False, exp_award=0, friend=True
        )
        player.combat_list_allies = [player, gorran]
        player.in_combat = True
        player.combat_proximity = {gorran: 500}
        assert game_service.get_player_status(player)["party_members"][0]["in_range"] is False


class TestUseItem:
    """``use_item`` delegates the effect to the engine and reports the narration."""

    def test_a_restorative_actually_heals(self, game_service, player):
        player.hp = 40
        potion = Restorative()
        player.inventory.append(potion)

        result = game_service.use_item(player, potion)

        assert result["success"] is True
        assert player.hp > 40
        assert any("recovered" in m for m in result["messages"])

    def test_message_joins_the_narration_lines(self, game_service, player):
        player.hp = 40
        potion = Restorative()
        player.inventory.append(potion)
        result = game_service.use_item(player, potion)
        assert result["message"] == "\n".join(result["messages"]).strip()

    def test_self_use_reports_no_target_name(self, game_service, player):
        player.hp = 40
        potion = Restorative()
        player.inventory.append(potion)
        assert game_service.use_item(player, potion)["target_name"] is None

    def test_unpaid_merchandise_cannot_be_used(self, game_service, player):
        potion = Restorative()
        potion.merchandise = True
        assert game_service.use_item(player, potion) == {
            "error": "You must purchase Restorative before using it"
        }

    def test_an_unusable_item_is_refused(self, game_service, player):
        dagger = RustedDagger()
        assert not hasattr(dagger, "use")
        assert game_service.use_item(player, dagger) == {
            "error": "Rusted Dagger cannot be used"
        }

    def test_an_out_of_reach_ally_cannot_be_targeted_in_combat(
        self, game_service, player
    ):
        gorran = NPC(
            name="Gorran", description="", damage=1, aggro=False, exp_award=0, friend=True
        )
        player.in_combat = True
        player.combat_proximity = {gorran: 500}

        result = game_service.use_item(player, Restorative(), target=gorran)

        assert "too far away" in result["error"]
        assert "Advance" in result["error"]

    def test_an_ally_in_reach_can_be_healed(self, game_service, player):
        gorran = NPC(
            name="Gorran", description="", damage=1, aggro=False, exp_award=0, friend=True
        )
        gorran.hp = 10
        player.in_combat = True
        player.combat_proximity = {gorran: 1}
        potion = Restorative()
        player.inventory.append(potion)

        result = game_service.use_item(player, potion, target=gorran)

        assert result["success"] is True
        assert result["target_name"] == "Gorran"
        assert gorran.hp > 10

    def test_ally_targeting_is_unrestricted_outside_combat(self, game_service, player):
        gorran = NPC(
            name="Gorran", description="", damage=1, aggro=False, exp_award=0, friend=True
        )
        gorran.hp = 10
        player.in_combat = False
        player.combat_proximity = {gorran: 9999}
        potion = Restorative()
        player.inventory.append(potion)

        assert game_service.use_item(player, potion, target=gorran)["success"] is True
        assert gorran.hp > 10


class TestMovePreviousTile:
    """#377 regression, re-expressed on a real map.

    The original used ``patch.object(game_service, "_calculate_exits")`` and a
    ``side_effect`` lambda for ``get_tile``; on a real 3x3 grid neither prop is
    needed, so the test exercises the production exit calculation too.
    """

    def test_successful_move_records_the_outgoing_tile(self, game_service, world):
        player, game_map = world
        origin = game_map[(0, 0)]

        result = game_service.move_player(player, "north")

        assert result["success"] is True
        assert player.previous_tile is origin
        assert player.current_room is game_map[(0, -1)]

    def test_a_refused_move_leaves_previous_tile_alone(self, game_service, player):
        assert not hasattr(player, "previous_tile")
        game_service.move_player(player, "sideways")
        assert not hasattr(player, "previous_tile")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
