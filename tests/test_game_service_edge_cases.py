"""Boundary-condition tests for GameService, driven through the real service.

History
-------
This file previously held 104 tests, **none** of which called ``game_service``
at all. Every one assigned a value to a ``MagicMock`` attribute and then asserted
that the attribute held the value just assigned::

    def test_cooldown_max_beats(self, game_service, mock_player):
        cooldown = {"test_move": 100}
        assert cooldown["test_move"] == 100

Those tests could not fail for any change to ``src/`` — they asserted Python's
assignment semantics, not the game's. The ``game_service`` fixture was requested
by all 104 and used by none.

The *boundary intents* were legitimate (HP at 0, weight at/over tolerance, unicode
names, negative coordinates, empty vs. full collections), so they are preserved
here — but each is now pushed through the real ``GameService`` against a real
``Player``/``Universe``/``MapTile`` graph, so the assertion is on what the service
*returns* at that boundary. Building the real graph costs ~0.7 ms, so the mock
bought nothing.
"""

import pytest

from src.items import Gold, Item, Restorative
from src.npc import NPC
from tests._gs_fixtures import GRID_3X3, get_player_gold, live_world, set_player_gold


@pytest.fixture
def world():
    """A real player standing at the centre of a real 3x3 map."""
    return live_world(GRID_3X3)


@pytest.fixture
def player(world):
    return world[0]


def _ballast(weight, name="Anvil"):
    """A real ``Item`` with a controlled weight, for carry-capacity boundaries.

    ``Item.__init__`` takes no ``weight``; subclasses set it as a class attribute
    and ``Player.refresh_weight`` multiplies it by ``count`` when present. Both are
    set explicitly here so the arithmetic under test is unambiguous.
    """
    item = Item(
        name=name,
        description="Test ballast.",
        value=1,
        maintype="Misc",
        subtype="Misc",
        discovery_message="a lump of test ballast.",
    )
    item.weight = weight
    item.count = 1
    return item


# ========================= HP BOUNDARIES =========================


class TestHPBoundaries:
    """HP boundaries as the service reports them, not as the fixture sets them."""

    @pytest.mark.parametrize(
        "hp,expect_dead",
        [(-50, True), (0, True), (1, False), (100, False), (150, False)],
    )
    def test_is_player_dead_at_hp_boundary(self, game_service, player, hp, expect_dead):
        """``is_player_dead`` is the single derivation routes use; 0 counts as dead."""
        player.hp = hp
        assert game_service.is_player_dead(player) is expect_dead

    def test_status_reports_hp_verbatim_without_clamping(self, game_service, player):
        """The status payload must not silently clamp HP — the client renders
        overheal and death states from these raw numbers."""
        player.hp = player.maxhp + 50

        status = game_service.get_player_status(player)

        assert status["hp"] == 150
        assert status["max_hp"] == 100

    def test_maxhp_of_one_does_not_break_status(self, game_service, player):
        player.maxhp = 1
        player.hp = 1

        status = game_service.get_player_status(player)

        assert (status["hp"], status["max_hp"]) == (1, 1)


# ========================= FATIGUE BOUNDARIES =========================


class TestFatigueBoundaries:
    """``fatigue`` is the engine's stamina analogue; ``player.stamina`` does not exist."""

    @pytest.mark.parametrize("fatigue", [0, 1, 150, 200])
    def test_status_surfaces_fatigue_at_boundaries(self, game_service, player, fatigue):
        player.fatigue = fatigue

        status = game_service.get_player_status(player)

        assert status["fatigue"] == fatigue
        assert status["max_fatigue"] == player.maxfatigue

    def test_player_has_no_stamina_attribute(self, player):
        """Guards the CLAUDE.md invariant: a test or route reaching for
        ``player.stamina`` is reading a field the engine never sets."""
        assert not hasattr(player, "stamina")


# ========================= LEVEL / EXPERIENCE BOUNDARIES =========================


class TestLevelAndExperienceBoundaries:
    @pytest.mark.parametrize("level", [1, 99, 999])
    def test_status_reports_level(self, game_service, player, level):
        player.level = level
        assert game_service.get_player_status(player)["level"] == level

    @pytest.mark.parametrize(
        "exp,exp_to_level,expected_remaining",
        [
            (0, 100, 100),
            (99, 100, 1),
            (100, 100, 0),
            (150, 100, 0),  # over-threshold must floor at 0, never go negative
        ],
    )
    def test_exp_to_next_level_floors_at_zero(
        self, game_service, player, exp, exp_to_level, expected_remaining
    ):
        """``exp_to_next_level`` drives a progress bar; a negative would render
        the bar inverted, so the service floors it."""
        player.exp = exp
        player.exp_to_level = exp_to_level

        status = game_service.get_player_status(player)

        assert status["exp_to_next_level"] == expected_remaining
        assert status["exp"] == exp
        assert status["max_exp"] == exp_to_level


# ========================= WEIGHT / CARRY-CAPACITY BOUNDARIES =========================


class TestWeightBoundaries:
    """Carry weight is derived by ``player.refresh_weight()`` inside the service.

    The old tests asserted arithmetic they performed themselves in the test body.
    These add real items to a real inventory and assert the service's derived
    totals, so a change to weight accumulation or to the percentage formula fails.
    """

    def test_weight_reflects_real_inventory_contents(self, game_service, player):
        baseline = game_service.get_player_status(player)["weight"]
        player.inventory.append(_ballast(5.0))

        after = game_service.get_player_status(player)

        assert after["weight"] == pytest.approx(baseline + 5.0)

    def test_weight_pct_is_a_percentage_not_a_fraction(self, game_service, player):
        """Wire-format guard: the client renders this straight into a width style.
        Emitting 0.5 instead of 50 silently collapses the bar (CLAUDE.md's
        `hit_chance` drift bug was exactly this mistake)."""
        player.inventory.clear()
        player.inventory.append(_ballast(player.weight_tolerance / 2))

        status = game_service.get_player_status(player)

        assert status["weight_pct"] == pytest.approx(50.0)

    def test_weight_pct_at_exact_tolerance_is_one_hundred(self, game_service, player):
        player.inventory.clear()
        player.inventory.append(_ballast(player.weight_tolerance))

        assert game_service.get_player_status(player)["weight_pct"] == pytest.approx(
            100.0
        )

    def test_overloaded_player_reports_over_one_hundred_percent(
        self, game_service, player
    ):
        """Overload is a real state the HUD must show; it is not clamped away."""
        player.inventory.clear()
        player.inventory.append(_ballast(player.weight_tolerance * 2))

        status = game_service.get_player_status(player)

        assert status["weight"] > status["max_weight"]
        assert status["weight_pct"] > 100.0

    def test_zero_tolerance_does_not_divide_by_zero(self, game_service, player):
        """A stat debuff could in principle drive tolerance to 0; the guard in
        get_player_status must hold rather than raising ZeroDivisionError."""
        player.weight_tolerance = 0
        player.weight_tolerance_base = 0

        status = game_service.get_player_status(player)

        assert status["weight_pct"] == 0

    def test_inventory_weight_matches_status_weight(self, game_service, player):
        """Two endpoints derive carry weight; they must not disagree."""
        player.inventory.append(_ballast(3.25))

        inventory = game_service.get_inventory(player)
        status = game_service.get_player_status(player)

        assert inventory["total_weight"] == pytest.approx(status["weight"])
        assert inventory["weight_limit"] == pytest.approx(status["max_weight"])


# ========================= INVENTORY EDGE CASES =========================


class TestInventoryEdgeCases:
    def test_empty_inventory_serializes_to_empty_item_list(self, game_service, player):
        player.inventory.clear()

        inventory = game_service.get_inventory(player)

        assert inventory["items"] == []
        assert inventory["item_count"] == 0
        assert inventory["total_weight"] == 0

    def test_item_count_tracks_real_additions(self, game_service, player):
        player.inventory.clear()
        for i in range(50):
            player.inventory.append(_ballast(0.0, name=f"Trinket{i}"))

        inventory = game_service.get_inventory(player)

        assert inventory["item_count"] == 50
        assert len(inventory["items"]) == 50
        assert inventory["total_weight"] == 0

    def test_zero_weight_items_do_not_move_the_total(self, game_service, player):
        before = game_service.get_inventory(player)["total_weight"]
        player.inventory.append(_ballast(0.0, name="Feather"))

        assert game_service.get_inventory(player)["total_weight"] == pytest.approx(
            before
        )

    def test_drop_item_moves_it_from_inventory_to_the_tile(
        self, game_service, world
    ):
        """The old suite asserted only that ``drop_item`` returned non-None. The
        observable effect is the transfer, so assert both ends of it."""
        player, game_map = world
        potion = Restorative(count=1)
        player.inventory.append(potion)

        result = game_service.drop_item(player, potion)

        assert result["success"] is True
        assert potion not in player.inventory
        assert potion in game_map[(0, 0)].items_here


# ========================= ATTRIBUTE BOUNDARIES =========================


class TestAttributeBoundaries:
    """Attribute extremes must survive the stats derivation, which divides and
    rounds; the old tests never called it."""

    @pytest.mark.parametrize("value", [-5, 0, 1, 10, 9999])
    def test_stats_round_trip_extreme_strength(self, game_service, player, value):
        player.strength = value
        player.strength_base = value

        stats = game_service.get_player_stats(player)

        assert stats["strength"] == value
        assert stats["strength_base"] == value

    def test_evasion_is_an_integer_even_for_fractional_finesse(
        self, game_service, player
    ):
        """A float finesse must render identically on the character sheet and on
        the battlefield card. Both apply `int(round(...))`, so the sheet's
        `evasion_chance` and the combat serializer's `evasion` must never
        disagree -- that divergence is the regression this guards.

        Note 12.5 -> 12, not 13: `round` is banker's rounding. Pinning the
        agreement rather than a hand-computed literal is what keeps this honest
        if either side's rounding policy is ever changed.
        """
        from src.api.serializers.combat import CombatantSerializer

        player.finesse = 12.5

        stats = game_service.get_player_stats(player)
        card = CombatantSerializer._serialize_combat_stats(player)

        assert stats["evasion_chance"] == 12
        assert isinstance(stats["evasion_chance"], int)
        # The real contract: sheet and battlefield card agree on one finesse.
        assert stats["evasion_chance"] == card["evasion"]

    def test_hit_accuracy_weights_finesse_and_intelligence(
        self, game_service, player
    ):
        """Accuracy must use the combat weighting (finesse 0.7 / intelligence 0.3),
        not finesse alone — otherwise the character sheet disagrees with the dice."""
        player.finesse = 20
        player.intelligence = 10
        accuracy_high_finesse = game_service.get_player_stats(player)["hit_accuracy"]

        player.finesse = 10
        player.intelligence = 20
        accuracy_high_intelligence = game_service.get_player_stats(player)[
            "hit_accuracy"
        ]

        # Finesse is weighted more heavily, so swapping the two must not be a no-op.
        assert accuracy_high_finesse > accuracy_high_intelligence

    def test_unarmed_player_reports_zero_attack_damage(self, game_service, player):
        player.eq_weapon = None

        stats = game_service.get_player_stats(player)

        assert stats["attack_damage_min"] == 0
        assert stats["attack_damage_max"] == 0

    def test_player_has_no_defense_accuracy_or_evasion_attributes(self, player):
        """CLAUDE.md invariant: these are derived stats in the payload, never
        attributes on ``Player``. A test reading them off the player is wrong."""
        for missing in ("defense", "accuracy", "evasion", "health"):
            assert not hasattr(player, missing)


# ========================= GOLD BOUNDARIES =========================


class TestGoldBoundaries:
    """Gold is derived from the inventory by ``get_gold``, never stored as a scalar."""

    @pytest.mark.parametrize("amount", [0, 1, 1_000_000])
    def test_status_gold_matches_the_purse(self, game_service, player, amount):
        set_player_gold(player, amount)

        assert game_service.get_player_status(player)["gold"] == amount
        assert game_service.get_player_stats(player)["gold"] == amount

    def test_gold_is_consolidated_into_a_single_stack(self, game_service, player):
        """``get_player_status`` calls ``stack_gold()`` first; two purses must
        report as one total rather than the service reading only the first."""
        set_player_gold(player, 100)
        player.inventory.append(Gold(amt=250))

        status = game_service.get_player_status(player)

        assert status["gold"] == 350
        assert get_player_gold(player) == 350


# ========================= SPECIAL DATA CASES =========================


class TestSpecialDataCases:
    """Non-ASCII and empty strings must survive serialization unmangled."""

    @pytest.mark.parametrize(
        "name", ["Jean", "François", "Ζαν", "ジャン", "Jean" * 100, ""]
    )
    def test_player_name_round_trips_through_status(self, game_service, player, name):
        player.name = name
        assert game_service.get_player_status(player)["name"] == name

    def test_unicode_npc_names_survive_tile_serialization(self, game_service, world):
        player, game_map = world
        npc = NPC(
            name="Gorran the Ẑealous",
            description="A Golemite with a diacritic.",
            damage=1,
            aggro=False,
            exp_award=0,
        )
        game_map[(0, 0)].npcs_here.append(npc)

        result = game_service.interact_with_tile(player, "look")

        assert [entry["name"] for entry in result["npcs"]] == ["Gorran the Ẑealous"]

    def test_empty_tile_description_serializes_as_empty_string(
        self, game_service, world
    ):
        player, game_map = world
        game_map[(0, 0)].description = ""

        assert game_service.interact_with_tile(player, "look")["description"] == ""


# ========================= COLLECTION BOUNDARIES =========================


class TestCollectionBoundaries:
    """Empty vs. populated tile collections, asserted on the serialized payload."""

    def test_empty_tile_serializes_empty_collections(self, game_service, player):
        result = game_service.interact_with_tile(player, "look")

        assert result["items"] == []
        assert result["npcs"] == []
        assert result["objects"] == []

    def test_tile_items_appear_in_the_payload(self, game_service, world):
        player, game_map = world
        game_map[(0, 0)].items_here.extend(
            [Restorative(count=1), _ballast(1.0, name="Rubble")]
        )

        result = game_service.interact_with_tile(player, "look")

        assert sorted(entry["name"] for entry in result["items"]) == [
            "Restorative",
            "Rubble",
        ]

    def test_interact_reports_error_when_no_tile_at_location(
        self, game_service, player
    ):
        """Off-map coordinates must return the error contract, not raise."""
        player.location_x, player.location_y = 99, 99

        assert game_service.interact_with_tile(player, "look") == {
            "error": "No tile at this location"
        }


# ========================= COORDINATE BOUNDARIES =========================


class TestCoordinateBoundaries:
    def test_exits_at_map_corner_omit_missing_neighbours(self, game_service, world):
        """A player in the corner of the 3x3 grid has exactly three neighbours."""
        player, game_map = world
        player.location_x, player.location_y = -1, -1

        exits = game_service._calculate_exits(
            player.universe, game_map[(-1, -1)], -1, -1
        )

        assert sorted(exits) == ["east", "south", "southeast"]

    def test_blocked_exit_is_removed_even_when_the_neighbour_exists(
        self, game_service, world
    ):
        player, game_map = world
        game_map[(0, 0)].block_exit = ["north"]

        exits = game_service._calculate_exits(player.universe, game_map[(0, 0)], 0, 0)

        assert "north" not in exits
        assert "south" in exits

    def test_negative_coordinates_are_valid_positions(self, game_service, world):
        """Maps are authored around the origin, so negative coords are normal."""
        player, _ = world
        player.location_x, player.location_y = -1, -1

        world_info = game_service.get_world_info(player)

        assert world_info["current_position"] == {"x": -1, "y": -1}


# ========================= UNIVERSE-HELPER BOUNDARIES =========================


class TestUniverseHelperBoundaries:
    """``GameService`` has no ``self.universe``; these static helpers are the
    only sanctioned way into universe state (CLAUDE.md)."""

    def test_game_service_holds_no_universe_reference(self, game_service):
        assert not hasattr(game_service, "universe")

    @pytest.mark.parametrize("tick", [0, 1, 999_999])
    def test_game_tick_helper_reads_through_the_player(
        self, game_service, player, tick
    ):
        player.universe.game_tick = tick
        assert game_service._game_tick(player) == tick

    def test_game_tick_helper_defaults_to_zero_without_a_universe(
        self, game_service, player
    ):
        player.universe = None
        assert game_service._game_tick(player) == 0

    def test_story_helper_returns_the_live_story_dict(self, game_service, player):
        player.universe.story["ch01_met_gorran"] = True

        assert game_service._story(player)["ch01_met_gorran"] is True

    def test_story_helper_defaults_to_empty_dict_without_a_universe(
        self, game_service, player
    ):
        player.universe = None
        assert game_service._story(player) == {}

    def test_world_info_is_empty_without_a_universe(self, game_service, player):
        player.universe = None
        assert game_service.get_world_info(player) == {}
