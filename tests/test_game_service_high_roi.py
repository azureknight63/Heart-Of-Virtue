"""Progression: stats, skill tree, skill learning, level-up point allocation.

History
-------
"High ROI" was named for a coverage target ("51% -> 60%+") and delivered none of
it. 18 of its 43 tests were ineffective and several were self-defeating:

* ``test_get_combat_status_not_in_combat`` wrapped its call in
  ``except Exception: assert hasattr(game_service, 'get_combat_status')`` — the
  method could raise on every input and the test would still pass.
* ``test_execute_move_valid_move`` patched ``get_available_moves``, then asserted
  ``hasattr(game_service, 'execute_move')`` without ever calling it.
* ``test_attributes_properly_set`` / ``test_player_name_attribute`` asserted the
  fixture's own literals (``mock_player.name == "Jean"``) with no service call.
* ``test_search_with_current_room`` asserted ``current_room is not None`` — set
  three lines earlier by the fixture.
* ``test_very_large_coordinates`` asserted ``result is None or isinstance(result,
  dict)``, which no return value can violate.

The fixture also invented ``player.equipment``/``player.equipped``/
``player.inventory.items``, none of which exist on the real ``Player`` — so the
"equipment change" tests changed nothing the service could see.

Exits, movement, rooms, inventory, equipment and search are now covered for real
in ``test_game_service_world.py``, ``test_game_service_critical_methods.py`` and
``test_game_service_methods.py``. This file keeps the one area that was uniquely
its own and now tests it properly: **character progression**.
"""

import pytest

from src.items import RustedDagger
from tests._gs_fixtures import GRID_3X3, live_world, set_player_gold

ATTRIBUTES = [
    "strength_base",
    "finesse_base",
    "speed_base",
    "endurance_base",
    "charisma_base",
    "intelligence_base",
    "faith_base",
]


@pytest.fixture
def world():
    return live_world(GRID_3X3)


@pytest.fixture
def player(world):
    return world[0]


class TestGetPlayerStats:
    """The character sheet: attributes, derived combat ratings, encumbrance."""

    @pytest.mark.parametrize(
        "attribute",
        ["strength", "finesse", "speed", "endurance", "charisma", "intelligence", "faith"],
    )
    def test_every_attribute_ships_with_its_base(self, game_service, player, attribute):
        stats = game_service.get_player_stats(player)
        assert stats[attribute] == getattr(player, attribute)
        assert stats[attribute + "_base"] == getattr(player, attribute + "_base")

    def test_vitals_and_purse_are_included(self, game_service, player):
        player.hp = 71
        set_player_gold(player, 88)
        stats = game_service.get_player_stats(player)
        assert stats["hp"] == 71
        assert stats["max_hp"] == player.maxhp
        assert stats["gold"] == 88

    def test_hit_accuracy_uses_the_engines_own_weighting(self, game_service, player):
        """The sheet must agree with the dice — see ``derive_hit_accuracy``."""
        from src.api.services.game_service import derive_hit_accuracy

        assert game_service.get_player_stats(player)["hit_accuracy"] == derive_hit_accuracy(
            player
        )

    def test_evasion_is_the_rounded_finesse(self, game_service, player):
        """A float finesse otherwise renders 12.5 on the sheet and 13 on the card."""
        player.finesse = 12.5
        # Python rounds half to even, so 12.5 -> 12.
        assert game_service.get_player_stats(player)["evasion_chance"] == 12

    def test_attack_damage_band_brackets_weapon_power(self, game_service, player):
        stats = game_service.get_player_stats(player)
        assert stats["attack_damage_min"] < stats["attack_damage_max"]

    def test_a_stronger_weapon_raises_the_damage_band(self, game_service, player):
        before = game_service.get_player_stats(player)["attack_damage_max"]
        dagger = RustedDagger()
        player.inventory.append(dagger)
        player.equip_item(item_object=dagger)

        after = game_service.get_player_stats(player)["attack_damage_max"]

        assert after != before

    def test_carrying_capacity_mirrors_weight_tolerance(self, game_service, player):
        stats = game_service.get_player_stats(player)
        assert stats["carrying_capacity"] == player.weight_tolerance
        assert stats["max_weight"] == player.weight_tolerance

    def test_states_are_listed_with_their_remaining_steps(self, game_service, player):
        class _Poisoned:
            name = "Poisoned"
            steps_left = 4

        player.states = [_Poisoned()]
        assert game_service.get_player_stats(player)["states"] == [
            {"name": "Poisoned", "steps_left": 4}
        ]


class TestGetPlayerSkills:
    """The skill screen: known moves, per-category XP, and what is learnable."""

    def test_known_moves_are_serialized(self, game_service, player):
        known = game_service.get_player_skills(player)["known_moves"]
        names = [m["name"] for m in known]
        assert names == [m.name for m in player.known_moves]
        assert "Attack" in names

    def test_each_known_move_carries_its_ui_fields(self, game_service, player):
        entry = game_service.get_player_skills(player)["known_moves"][0]
        assert set(entry) == {
            "name",
            "display_name",
            "category",
            "description",
            "fatigue_cost",
            "beats_left",
            "xp_gain",
        }

    def test_skill_exp_is_reported_per_category(self, game_service, player):
        skills = game_service.get_player_skills(player)
        assert skills["skill_exp"] is player.skill_exp
        assert "Dagger" in skills["skill_exp"]

    def test_an_already_known_skill_is_flagged_and_not_learnable(
        self, game_service, player
    ):
        basic = game_service.get_player_skills(player)["skill_tree"]["Basic"]
        dodge = next(s for s in basic if s["name"] == "Dodge")
        assert dodge["is_known"] is True
        assert dodge["can_learn"] is False

    def test_can_learn_flips_once_the_category_xp_is_earned(self, game_service, player):
        def entry_for(name):
            tree = game_service.get_player_skills(player)["skill_tree"]["Basic"]
            return next(s for s in tree if s["name"] == name)

        target = entry_for("Tactical Positioning")
        assert target["can_learn"] is False

        player.skill_exp["Basic"] = target["required_exp"]

        assert entry_for("Tactical Positioning")["can_learn"] is True

    def test_no_skill_tree_yields_an_empty_tree(self, game_service, player):
        del player.skilltree
        assert game_service.get_player_skills(player)["skill_tree"] == {}


class TestLearnSkill:
    """``learn_skill`` spends category XP to add a move."""

    @staticmethod
    def _affordable(game_service, player, category="Basic"):
        """Name and cost of a skill in ``category`` the player does not yet know."""
        tree = game_service.get_player_skills(player)["skill_tree"][category]
        entry = next(s for s in tree if not s["is_known"])
        return entry["name"], entry["required_exp"]

    def test_learning_adds_the_move_and_deducts_the_exp(self, game_service, player):
        name, cost = self._affordable(game_service, player)
        player.skill_exp["Basic"] = cost + 25

        result = game_service.learn_skill(player, name, "Basic")

        assert result["success"] is True
        assert result["message"] == f"Learned {name}!"
        assert result["remaining_exp"] == 25
        assert player.skill_exp["Basic"] == 25
        assert name in [m.name for m in player.known_moves]

    def test_the_response_carries_the_refreshed_skill_screen(self, game_service, player):
        name, cost = self._affordable(game_service, player)
        player.skill_exp["Basic"] = cost

        result = game_service.learn_skill(player, name, "Basic")

        assert name in [m["name"] for m in result["skills"]["known_moves"]]

    def test_insufficient_exp_is_refused(self, game_service, player):
        name, cost = self._affordable(game_service, player)
        player.skill_exp["Basic"] = cost - 1

        result = game_service.learn_skill(player, name, "Basic")

        assert result["success"] is False
        assert result["error"] == (
            f"Not enough experience. Required: {cost}, Available: {cost - 1}"
        )
        assert name not in [m.name for m in player.known_moves]

    def test_relearning_a_known_skill_is_refused(self, game_service, player):
        player.skill_exp["Basic"] = 100_000
        assert game_service.learn_skill(player, "Dodge", "Basic") == {
            "success": False,
            "error": "Skill already learned",
        }

    def test_unknown_skill_name_is_refused(self, game_service, player):
        assert game_service.learn_skill(player, "Fireball", "Basic") == {
            "success": False,
            "error": "Skill 'Fireball' not found in category 'Basic'",
        }

    def test_unknown_category_is_refused(self, game_service, player):
        assert game_service.learn_skill(player, "Dodge", "Necromancy") == {
            "success": False,
            "error": "Invalid category: Necromancy",
        }

    def test_missing_skill_tree_is_refused(self, game_service, player):
        del player.skilltree
        assert game_service.learn_skill(player, "Dodge", "Basic") == {
            "success": False,
            "error": "Skill tree not initialized",
        }

    def test_a_failed_learn_never_spends_exp(self, game_service, player):
        player.skill_exp["Basic"] = 500
        game_service.learn_skill(player, "Fireball", "Basic")
        assert player.skill_exp["Basic"] == 500


class TestAllocateLevelUpPoints:
    """``allocate_level_up_points`` spends the points a level-up granted."""

    def test_allocating_raises_the_base_stat(self, game_service, player):
        player.pending_attribute_points = 5
        before = player.strength_base

        result = game_service.allocate_level_up_points(player, "strength_base", 3)

        assert result["success"] is True
        assert result["remaining_points"] == 2
        assert player.strength_base == before + 3
        assert player.pending_attribute_points == 2

    def test_the_response_carries_refreshed_stats(self, game_service, player):
        player.pending_attribute_points = 2
        result = game_service.allocate_level_up_points(player, "faith_base", 2)
        assert result["stats"]["faith_base"] == player.faith_base

    @pytest.mark.parametrize("attribute", ATTRIBUTES)
    def test_every_allowed_attribute_can_be_raised(self, game_service, player, attribute):
        player.pending_attribute_points = 1
        before = getattr(player, attribute)
        assert game_service.allocate_level_up_points(player, attribute, 1)["success"]
        assert getattr(player, attribute) == before + 1

    def test_an_unknown_attribute_is_refused(self, game_service, player):
        player.pending_attribute_points = 5
        assert game_service.allocate_level_up_points(player, "luck_base", 1) == {
            "success": False,
            "error": "Invalid attribute",
        }
        assert player.pending_attribute_points == 5

    def test_spending_more_than_is_pending_is_refused(self, game_service, player):
        player.pending_attribute_points = 2
        before = player.speed_base

        result = game_service.allocate_level_up_points(player, "speed_base", 3)

        assert result == {"success": False, "error": "Not enough points"}
        assert player.speed_base == before

    @pytest.mark.parametrize("amount", [0, -1])
    def test_non_positive_amounts_are_refused(self, game_service, player, amount):
        player.pending_attribute_points = 5
        assert game_service.allocate_level_up_points(player, "speed_base", amount) == {
            "success": False,
            "error": "Amount must be positive",
        }

    def test_a_non_numeric_amount_is_refused(self, game_service, player):
        player.pending_attribute_points = 5
        assert game_service.allocate_level_up_points(player, "speed_base", "lots") == {
            "success": False,
            "error": "Invalid amount",
        }

    def test_randomize_distributes_every_pending_point(self, game_service, player):
        player.pending_attribute_points = 12
        before = {a: getattr(player, a) for a in ATTRIBUTES}

        result = game_service.allocate_level_up_points(player, "randomize", None)

        assert result["success"] is True
        assert result["remaining_points"] == 0
        spent = sum(getattr(player, a) - before[a] for a in ATTRIBUTES)
        assert spent == 12

    def test_randomize_with_nothing_pending_is_refused(self, game_service, player):
        player.pending_attribute_points = 0
        assert game_service.allocate_level_up_points(player, "randomize", None) == {
            "success": False,
            "error": "No pending points to randomize",
        }

    def test_spending_the_last_point_clears_the_level_up_queue(
        self, game_service, player
    ):
        """Stale level-up events re-trigger the SFX on every later status poll."""
        player.pending_attribute_points = 1
        player.pending_level_ups = [2]

        game_service.allocate_level_up_points(player, "faith_base", 1)

        assert player.pending_level_ups == []

    def test_a_partial_spend_leaves_the_queue_alone(self, game_service, player):
        player.pending_attribute_points = 3
        player.pending_level_ups = [2]

        game_service.allocate_level_up_points(player, "faith_base", 1)

        assert player.pending_level_ups == [2]

    def test_derived_stats_are_refreshed_after_allocation(self, game_service, player):
        """``refresh_stat_bonuses`` propagates ``*_base`` into the live stat."""
        player.pending_attribute_points = 5
        before = player.finesse

        game_service.allocate_level_up_points(player, "finesse_base", 5)

        assert player.finesse == before + 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
