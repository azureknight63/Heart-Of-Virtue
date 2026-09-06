"""Game service tests for extended method coverage.

Tests for high-impact, previously untested methods:
- Shop system: shop_buy, shop_sell, shop_buyback, get_shop_state
- Skills/abilities: learn_skill, get_player_skills, get_available_moves
- Awards: award_gold, award_experience, award_item, award_reputation
- Combat: flee_combat, get_combat_status
- Quests: update_quest_progress, get_quest_status, get_active_quests, complete_quest
- NPC systems: get_npc_state
- World: collect_combat_loot, get_player_progression, get_npcs_at_location

Target: Increase game_service.py coverage from 27% → 60%+ with 35-40 tests.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.items import Consumable, Gold
from src.npc._merchants import Merchant
from src.combatant import wire_handle


@pytest.fixture
def _cached_mock_universe():
    """A stub universe for the skill-tree tests.

    Deliberately **not** session-scoped despite the old name: ``story`` and
    ``game_tick`` are mutable, so a session-wide instance leaks whatever one
    test writes into every later test — and under ``-n auto`` that ordering is
    not even reproducible.
    """
    universe = MagicMock()
    universe.story = {}
    universe.game_tick = 100

    # Mock get_tile to return a test tile
    test_tile = MagicMock()
    test_tile.name = "TestArea"
    test_tile.description = "Test area description"
    test_tile.events_here = []
    test_tile.items_here = []
    test_tile.npcs_here = []
    test_tile.objects_here = []
    test_tile.location_x = 5
    test_tile.location_y = 5

    universe.get_tile = MagicMock(return_value=test_tile)
    return universe


@pytest.fixture
def realistic_mock_universe(_cached_mock_universe):
    """Return cached universe (used as dependency for player fixture)."""
    return _cached_mock_universe


@pytest.fixture
def extended_mock_player(realistic_mock_universe):
    """Create a realistic mock player with rich state for extended tests."""
    player = MagicMock()

    # Basic attributes
    player.name = "Jean"
    player.location_x = 5
    player.location_y = 5
    player.level = 5
    player.exp = 100
    player.exp_to_level = 500
    player.hp = 80
    player.maxhp = 100
    player.fatigue = 70
    player.maxfatigue = 100
    player.strength = 12
    player.finesse = 11
    player.speed = 10
    player.wisdom = 10
    player.constitution = 12
    player.heat = 0

    # Universe and location
    player.universe = realistic_mock_universe
    player.current_room = realistic_mock_universe.get_tile(5, 5)
    player.map = {}

    # Inventory and equipment
    player.inventory = []
    player.eq_weapon = None
    player.eq_armor = None
    player.eq_helmet = None
    player.eq_gauntlets = None
    player.eq_leggings = None
    player.eq_boots = None
    player.eq_offhand = None
    player.weight_current = 0
    player.weight_tolerance = 100

    # Combat state
    player.in_combat = False
    player.enemies = []
    player.combat_drops = []

    # Skill system
    player.skill_exp = {"Basic": 100, "Dagger": 50}
    player.known_moves = []
    player.skilltree = MagicMock()
    player.skilltree.subtypes = {
        "Basic": {},
        "Dagger": {},
    }

    # Quest system
    player.quest_chains = {
        "main_story_1": {"stage": 1, "complete": False, "started": True},
        "side_quest_1": {"stage": 0, "complete": False, "started": False},
    }
    player.active_quests = {}
    player.completed_quests = []

    # Reputation
    player.reputation = {"merchant_npc": 10, "noble_npc": 5}

    # Story/flags
    player.visited_tiles = set()
    player.pending_level_ups = []
    player.pending_attribute_points = 0

    # Dialogue state
    player.dialogue_state = {}
    player.conversation_history = {}

    # Methods to mock
    player.gain_exp = MagicMock(return_value=[])
    player.learn_skill = MagicMock()
    player.stack_gold = MagicMock()
    player.stack_inv_items = MagicMock()
    player.refresh_weight = MagicMock()

    return player


@pytest.fixture
def mock_merchant():
    """Create a mock merchant NPC with shop."""
    merchant = MagicMock()
    merchant.name = "Shopkeeper"
    # Price modifiers live on the merchant itself (ShopInterface removed).
    merchant.buy_modifier = 1.0
    merchant.sell_modifier = 0.5
    merchant.shop_name = "Shopkeeper's Shop"
    merchant.inventory = []
    merchant._buyback_ledger = []

    def initialize_shop():
        merchant.buy_modifier = 1.0
        merchant.sell_modifier = 0.5
        merchant.shop_name = "Shopkeeper's Shop"

    merchant.initialize_shop = initialize_shop
    merchant.update_goods = MagicMock()

    return merchant


@pytest.fixture
def mock_item():
    """Create a mock item for trading."""
    item = MagicMock()
    item.name = "Iron Sword"
    item.value = 50
    item.weight = 5.0
    item.count = 1
    item.is_equipped = False
    item.isequipped = False
    item.description = "A sturdy iron sword"
    item.power = 10
    item.subtype = "Sword"
    return item


# ============================================================================
# SHOP SYSTEM TESTS
# ============================================================================


class _ShopWorld:
    """A real merchant on Jean's tile — no serializer is stubbed.

    The previous shop tests here wrapped every call in five nested
    ``patch(...ShopSerializer...)`` blocks and then asserted
    ``isinstance(result, dict)``. With the serializers stubbed out there was no
    price, no ledger and no gold movement left to check, so the assertions could
    not have failed. The pricing/gold/round-trip surface is now covered against
    real objects in ``tests/test_game_service_advanced.py``; what remains here
    are the ``shop_buyback`` refusal branches that file does not reach.
    """

    def __init__(self, game_service, player, merchant):
        self.gs, self.player, self.merchant = game_service, player, merchant
        self.npc_id = wire_handle(merchant)

    def sell(self, item, quantity=1):
        return self.gs.shop_sell(self.player, self.npc_id, wire_handle(item), quantity)

    def buyback(self, item_id):
        return self.gs.shop_buyback(self.player, self.npc_id, item_id)

    def offer_id(self):
        """The wire id of the single outstanding buyback offer.

        The ENTRY's handle, which is what ``_serialize_buyback_item``
        publishes as the row id and therefore the only id a client can
        send back. The entry's ``item_id`` is an internal pointer at the
        stock the entry draws from, and two entries may share one.
        """
        (entry,) = self.merchant._buyback_ledger
        return wire_handle(entry)


def _tradeable(name="Tonic", value=100, weight=0.1, count=1):
    return Consumable(
        name=name,
        description=f"A {name.lower()}.",
        value=value,
        weight=weight,
        maintype="consumable",
        subtype="healing",
        count=count,
    )


@pytest.fixture
def shop_world(game_service, make_world, grid_3x3, set_player_gold):
    jean, game_map = make_world(grid_3x3)
    set_player_gold(jean, 1000)
    trader = Merchant(
        name="Milo",
        description="A trader.",
        damage=1,
        aggro=False,
        exp_award=0,
        stock_count=0,
        inventory=[Gold(2000)],
    )
    # A non-gold item keeps get_shop_state from firing the update_goods restock,
    # which would clear the inventory and reroll the purse.
    shelf_filler = _tradeable(name="Stall Ledger", value=0, weight=0.0)
    shelf_filler.merchandise = False
    trader.inventory.append(shelf_filler)
    game_map[(0, 0)].npcs_here = [trader]
    return _ShopWorld(game_service, jean, trader)


class TestMerchantDiscovery:
    """``_find_merchant`` gates on ``buy_modifier``, and nothing else does."""

    def test_a_merchant_without_pricing_is_not_found_at_all(
        self, game_service, shop_world
    ):
        """``get_shop_state`` contains a lazy ``initialize_shop()`` fallback for
        an uninitialised merchant — but it is unreachable through the real
        lookup, because ``_find_merchant`` itself requires ``buy_modifier`` to
        be present. Deleting the attribute makes the merchant invisible rather
        than triggering the fallback.

        The old test for this patched ``_find_merchant`` to hand back the mock
        directly, which is precisely what hid the contradiction.
        """
        del shop_world.merchant.buy_modifier

        result = game_service.get_shop_state(shop_world.player, shop_world.npc_id)

        assert result == {
            "success": False,
            "error": "Merchant not found at this location",
        }

    def test_a_merchant_on_another_tile_is_not_found(self, game_service, shop_world):
        game_service.move_player(shop_world.player, "east")

        result = game_service.get_shop_state(shop_world.player, shop_world.npc_id)

        assert result["success"] is False


class TestShopBuybackRefusals:
    """Every way ``shop_buyback`` declines, asserted on real state."""

    def test_an_unknown_merchant_is_refused(self, game_service, shop_world):
        result = game_service.shop_buyback(shop_world.player, "no-such-npc", "x")

        assert result == {
            "success": False,
            "error": "Merchant not found at this location",
        }

    def test_an_unknown_offer_is_refused(self, shop_world):
        """The ledger attribute is created lazily on the first sale, so a
        merchant nobody has sold to has none at all."""
        assert not hasattr(shop_world.merchant, "_buyback_ledger")

        result = shop_world.buyback("never-sold-this")

        assert result["error"] == "Buyback offer has expired or was not found"

    def test_buying_back_beyond_the_purse_is_refused_with_the_shortfall(
        self, shop_world, set_player_gold, get_player_gold
    ):
        item = _tradeable(value=800)
        shop_world.player.inventory.append(item)
        assert shop_world.sell(item)["gold_gained"] == 400

        set_player_gold(shop_world.player, 100)
        result = shop_world.buyback(shop_world.offer_id())

        assert result == {"success": False, "error": "Not enough gold — need 300 more"}
        assert get_player_gold(shop_world.player) == 100
        assert len(shop_world.merchant._buyback_ledger) == 1, "offer was consumed"

    def test_buying_back_something_too_heavy_is_refused(self, shop_world):
        """Jean sold it while over-strong; the carry check runs again on the way
        back in, after the gold check has already passed."""
        shop_world.player.weight_tolerance = 10_000
        anvil = _tradeable(name="Anvil", value=200, weight=999)
        shop_world.player.inventory.append(anvil)
        shop_world.sell(anvil)

        shop_world.player.weight_tolerance = 30
        result = shop_world.buyback(shop_world.offer_id())

        assert result == {"success": False, "error": "Exceeds carry limit"}

    def test_an_offer_whose_item_vanished_is_dropped_from_the_ledger(
        self, shop_world
    ):
        """A stale ledger row must not survive a failed lookup, or the shop
        would keep advertising an item the merchant cannot hand over."""
        item = _tradeable(value=100)
        shop_world.player.inventory.append(item)
        shop_world.sell(item)
        offer_id = shop_world.offer_id()
        shop_world.merchant.inventory = [
            i for i in shop_world.merchant.inventory if i.name != "Tonic"
        ]

        result = shop_world.buyback(offer_id)

        assert result["error"] == "Buyback item no longer in merchant stock"
        assert shop_world.merchant._buyback_ledger == []


class TestLearnSkill:
    """Tests for learn_skill() - learn skills from skill tree."""

    def test_learning_spends_the_skill_experience(self, game_service, extended_mock_player):
        """The cost is deducted from the category's exp pool, not just checked."""
        mock_skill = MagicMock()
        mock_skill.name = "Power Strike"
        mock_skill.description = "A powerful attack"
        extended_mock_player.skilltree.subtypes["Basic"][mock_skill] = 50
        extended_mock_player.skill_exp["Basic"] = 100

        result = game_service.learn_skill(extended_mock_player, "Power Strike", "Basic")

        assert result["success"] is True
        assert extended_mock_player.skill_exp["Basic"] == 50
        extended_mock_player.learn_skill.assert_called_once_with(mock_skill)

    def test_a_refused_purchase_spends_nothing(self, game_service, extended_mock_player):
        """The mirror image: an unaffordable skill must leave the pool intact."""
        mock_skill = MagicMock()
        mock_skill.name = "Power Strike"
        extended_mock_player.skilltree.subtypes["Basic"][mock_skill] = 200
        extended_mock_player.skill_exp["Basic"] = 50

        game_service.learn_skill(extended_mock_player, "Power Strike", "Basic")

        assert extended_mock_player.skill_exp["Basic"] == 50
        extended_mock_player.learn_skill.assert_not_called()

    def test_learn_skill_no_skill_tree(self, game_service, extended_mock_player):
        """Test learn_skill when player has no skill tree."""
        extended_mock_player.skilltree = None
        result = game_service.learn_skill(extended_mock_player, "Power Strike", "Basic")
        assert result["success"] is False
        assert "not initialized" in result["error"].lower()

    def test_learn_skill_invalid_category(self, game_service, extended_mock_player):
        """Test learn_skill with invalid category."""
        result = game_service.learn_skill(extended_mock_player, "Power Strike", "InvalidCategory")
        assert result["success"] is False
        assert "invalid category" in result["error"].lower()

    def test_learn_skill_not_found(self, game_service, extended_mock_player):
        """Test learn_skill when skill is not in category."""
        result = game_service.learn_skill(extended_mock_player, "NonExistent", "Basic")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_learn_skill_already_known(self, game_service, extended_mock_player):
        """Test learn_skill when skill is already learned."""
        mock_skill = MagicMock()
        mock_skill.name = "Power Strike"
        extended_mock_player.skilltree.subtypes["Basic"][mock_skill] = 50
        extended_mock_player.known_moves = [mock_skill]
        extended_mock_player.skill_exp["Basic"] = 100

        result = game_service.learn_skill(extended_mock_player, "Power Strike", "Basic")
        assert result["success"] is False
        assert "already learned" in result["error"].lower()

    def test_learn_skill_insufficient_experience(self, game_service, extended_mock_player):
        """Test learn_skill with insufficient experience."""
        mock_skill = MagicMock()
        mock_skill.name = "Power Strike"
        extended_mock_player.skilltree.subtypes["Basic"][mock_skill] = 200
        extended_mock_player.skill_exp["Basic"] = 50  # Not enough

        result = game_service.learn_skill(extended_mock_player, "Power Strike", "Basic")
        assert result["success"] is False
        assert "not enough experience" in result["error"].lower()

    def test_learn_skill_success(self, game_service, extended_mock_player):
        """Test successfully learning a skill."""
        mock_skill = MagicMock()
        mock_skill.name = "Power Strike"
        extended_mock_player.skilltree.subtypes["Basic"][mock_skill] = 50
        extended_mock_player.skill_exp["Basic"] = 100
        extended_mock_player.known_moves = []

        with patch.object(game_service, "get_player_skills", return_value={"known_moves": []}):
            result = game_service.learn_skill(extended_mock_player, "Power Strike", "Basic")
            assert result["success"] is True
            assert "learned" in result["message"].lower()
            extended_mock_player.learn_skill.assert_called_with(mock_skill)


class TestGetPlayerSkills:
    """Tests for get_player_skills() - retrieve skill tree state."""

    def test_the_payload_reports_the_players_own_moves_and_exp(
        self, game_service, extended_mock_player
    ):
        """Values, not just keys — the three sections used to be checked with
        ``isinstance(..., list/dict)``, which an empty stub satisfies."""
        known = MagicMock()
        known.name = "Jab"
        extended_mock_player.known_moves = [known]
        extended_mock_player.skill_exp = {"Basic": 100, "Dagger": 50}

        result = game_service.get_player_skills(extended_mock_player)

        assert [m["name"] for m in result["known_moves"]] == ["Jab"]
        assert result["skill_exp"] == {"Basic": 100, "Dagger": 50}
        assert set(result["skill_tree"]) == {"Basic", "Dagger"}

    def test_get_player_skills_no_skill_tree(self, game_service, extended_mock_player):
        """Test get_player_skills when player has no skill tree."""
        extended_mock_player.skilltree = None
        result = game_service.get_player_skills(extended_mock_player)
        assert "known_moves" in result
        assert "skill_tree" in result

    def test_get_player_skills_hides_unmet_mastery_skill(
        self, game_service, extended_mock_player
    ):
        """A stat-gated mastery skill whose learnable_when() is False and that
        isn't known yet should be omitted entirely, not listed as disabled."""
        mastery_skill = MagicMock()
        mastery_skill.name = "Lightning Assault"
        mastery_skill.learnable_when.return_value = False
        extended_mock_player.skilltree.subtypes["Basic"][mastery_skill] = 2500
        extended_mock_player.skill_exp["Basic"] = 3300
        extended_mock_player.known_moves = []

        result = game_service.get_player_skills(extended_mock_player)
        names = [s["name"] for s in result["skill_tree"]["Basic"]]
        assert "Lightning Assault" not in names

    def test_get_player_skills_shows_mastery_skill_when_dominant(
        self, game_service, extended_mock_player
    ):
        """Once learnable_when() is True, the mastery skill appears and is
        flagged can_learn given sufficient exp and not already known."""
        mastery_skill = MagicMock()
        mastery_skill.name = "Lightning Assault"
        mastery_skill.learnable_when.return_value = True
        extended_mock_player.skilltree.subtypes["Basic"][mastery_skill] = 2500
        extended_mock_player.skill_exp["Basic"] = 3300
        extended_mock_player.known_moves = []

        result = game_service.get_player_skills(extended_mock_player)
        entries = [s for s in result["skill_tree"]["Basic"] if s["name"] == "Lightning Assault"]
        assert len(entries) == 1
        assert entries[0]["can_learn"] is True
        assert entries[0]["is_known"] is False

    def test_get_player_skills_keeps_known_mastery_skill_even_if_unmet(
        self, game_service, extended_mock_player
    ):
        """A mastery skill the player already knows must stay listed (as
        known) even if the dominant-stat condition no longer holds — only
        not-yet-learned skills are hidden by the gate."""
        mastery_skill = MagicMock()
        mastery_skill.name = "Lightning Assault"
        mastery_skill.learnable_when.return_value = False
        extended_mock_player.skilltree.subtypes["Basic"][mastery_skill] = 2500

        known_move = MagicMock()
        known_move.name = "Lightning Assault"
        extended_mock_player.known_moves = [known_move]

        result = game_service.get_player_skills(extended_mock_player)
        entries = [s for s in result["skill_tree"]["Basic"] if s["name"] == "Lightning Assault"]
        assert len(entries) == 1
        assert entries[0]["is_known"] is True
        assert entries[0]["can_learn"] is False

    def test_get_player_skills_non_gated_skill_unaffected(
        self, game_service, extended_mock_player
    ):
        """A skill without learnable_when (or one that always returns True)
        is never hidden by the new gate, regardless of exp."""
        plain_skill = MagicMock(spec=["name"])
        plain_skill.name = "Dodge"
        extended_mock_player.skilltree.subtypes["Basic"][plain_skill] = 100
        extended_mock_player.skill_exp["Basic"] = 0
        extended_mock_player.known_moves = []

        result = game_service.get_player_skills(extended_mock_player)
        names = [s["name"] for s in result["skill_tree"]["Basic"]]
        assert "Dodge" in names


# ============================================================================
# LOOT AND WORLD TESTS
# ============================================================================


class TestCollectCombatLoot:
    """``collect_combat_loot`` moves named drops into the pack, or explains why not.

    Driven with a real ``Player`` so the weight arithmetic is the engine's own.
    The previous versions asserted ``isinstance(result, dict)`` and then wrapped
    the interesting assertion in ``if result.get("collected"):``, so an empty
    result satisfied them.
    """

    @pytest.fixture
    def looter(self, make_world, grid_3x3):
        jean, _game_map = make_world(grid_3x3)
        return jean

    def test_collecting_nothing_still_succeeds(self, game_service, looter):
        result = game_service.collect_combat_loot(looter, [])

        assert result == {"success": True, "collected": [], "skipped": []}

    def test_a_named_drop_moves_into_the_pack(self, game_service, looter):
        tonic = _tradeable(name="Tonic", value=10, weight=0.5)
        looter.current_room.items_here = [tonic]

        result = game_service.collect_combat_loot(looter, ["Tonic"])

        assert result["collected"] == ["Tonic"]
        assert result["skipped"] == []
        assert tonic not in looter.current_room.items_here
        assert [i for i in looter.inventory if i.name == "Tonic"]

    def test_an_unnamed_drop_is_left_on_the_floor(self, game_service, looter):
        wanted = _tradeable(name="Tonic", value=10, weight=0.5)
        ignored = _tradeable(name="Salve", value=10, weight=0.5)
        looter.current_room.items_here = [wanted, ignored]

        game_service.collect_combat_loot(looter, ["Tonic"])

        assert looter.current_room.items_here == [ignored]

    def test_the_drop_list_is_cleared_afterwards(self, game_service, looter):
        """``combat_drops`` is the post-victory prompt; leaving it populated
        would re-offer the same loot on the next fight."""
        looter.combat_drops = [_tradeable(name="Tonic")]

        game_service.collect_combat_loot(looter, [])

        assert looter.combat_drops == []

    def test_something_too_heavy_is_reported_as_skipped_not_dropped(
        self, game_service, looter
    ):
        anvil = _tradeable(name="Anvil", value=1, weight=999)
        looter.current_room.items_here = [anvil]

        result = game_service.collect_combat_loot(looter, ["Anvil"])

        assert result["collected"] == []
        assert [s["name"] for s in result["skipped"]] == ["Anvil"]
        assert anvil in looter.current_room.items_here, "skipped loot must stay behind"


# ============================================================================
# COMBAT UTILITY TESTS
# ============================================================================


class TestFleeCombat:
    """``flee_combat`` tears the encounter down, or refuses for a stated reason."""

    @pytest.fixture
    def fighter(self, game_service, make_world, grid_3x3):
        from src.npc._enemies import Slime

        jean, game_map = make_world(grid_3x3)
        slime = Slime()
        game_map[(0, 0)].npcs_here = [slime]
        game_service.start_combat(jean, wire_handle(slime))
        return jean, slime

    def test_fleeing_a_distant_enemy_ends_the_fight(self, game_service, fighter):
        jean, slime = fighter
        slime.combat_proximity = {jean: 40}

        result = game_service.flee_combat(jean)

        assert result["fled"] is True
        assert jean.in_combat is False
        assert jean.combat_list == []
        assert jean.current_move is None

    def test_fleeing_strips_combat_only_status_effects(self, game_service, fighter):
        """World-persistent states (Poisoned, Slimed) survive the escape; a
        combat-scoped one must not follow Jean out of the room."""
        jean, slime = fighter
        slime.combat_proximity = {jean: 40}
        transient = MagicMock(persistent=False)
        lasting = MagicMock(persistent=True)
        jean.states = [transient, lasting]

        game_service.flee_combat(jean)

        assert jean.states == [lasting]

    def test_fleeing_outside_combat_is_refused(self, game_service, make_world, grid_3x3):
        jean, _ = make_world(grid_3x3)

        assert game_service.flee_combat(jean) == {"error": "Not in combat"}


# ============================================================================
# STATS AND STATUS TESTS
# ============================================================================


class TestGetPlayerStats:
    """The character sheet reports live, derived values — not raw attributes."""

    @pytest.fixture
    def sheet(self, game_service, make_world, grid_3x3, set_player_gold):
        jean, _ = make_world(grid_3x3)
        set_player_gold(jean, 250)
        return game_service.get_player_stats(jean), jean

    def test_hp_and_fatigue_come_from_the_player(self, sheet):
        stats, jean = sheet

        assert (stats["hp"], stats["max_hp"]) == (jean.hp, jean.maxhp)
        assert (stats["fatigue"], stats["max_fatigue"]) == (jean.fatigue, jean.maxfatigue)

    def test_every_attribute_is_reported_with_its_unmodified_base(self, sheet):
        """Equipment shifts the effective value; the sheet shows both so the UI
        can render the delta."""
        stats, _jean = sheet

        for attribute in (
            "strength",
            "finesse",
            "speed",
            "endurance",
            "charisma",
            "intelligence",
            "faith",
        ):
            assert attribute in stats
            assert f"{attribute}_base" in stats

    def test_jeans_starting_gear_shifts_three_attributes_off_base(self, sheet):
        """Not a tautology: the Tattered Cloth / Cloth Hood / Wedding Band Jean
        starts in are what make effective != base here."""
        stats, _jean = sheet

        assert (stats["finesse"], stats["finesse_base"]) == (11, 10)
        assert (stats["endurance"], stats["endurance_base"]) == (11, 10)
        assert (stats["charisma"], stats["charisma_base"]) == (9, 10)

    def test_the_purse_is_reported_as_a_number(self, sheet, get_player_gold):
        stats, jean = sheet

        assert stats["gold"] == get_player_gold(jean) == 250


class TestGetAvailableMoves:
    """``get_available_moves`` mirrors the adapter's move-selection options."""

    def test_outside_combat_there_are_no_moves(self, game_service, make_world, grid_3x3):
        jean, _ = make_world(grid_3x3)
        assert not hasattr(jean, "_combat_adapter")

        assert game_service.get_available_moves(jean) == {"moves": []}

    def test_in_combat_the_adapters_options_are_serialized(
        self, game_service, make_player, make_npc, make_adapter
    ):
        from src.npc import Slime

        jean = make_player(weapon="Sword")
        # GameService._initialize_combat is what binds the adapter to the
        # player in production; make_adapter only builds it.
        jean._combat_adapter = make_adapter(jean, enemies=[make_npc(cls=Slime, hp=40)])

        moves = game_service.get_available_moves(jean)["moves"]

        assert moves, "a live fight must offer at least one move"
        assert [m["name"] for m in moves] == [
            option["name"] for option in jean._combat_adapter.available_options
        ]
        assert [m["id"] for m in moves] == [str(i) for i in range(len(moves))]
        assert all(
            {"name", "description", "fatigue_cost", "category", "beats_left"} <= set(m)
            for m in moves
        )

    def test_a_non_move_prompt_offers_nothing(
        self, game_service, make_player, make_npc, make_adapter
    ):
        """While the adapter is waiting for a target or a direction its
        ``available_options`` are not moves, so none are advertised."""
        from src.npc import Slime

        jean = make_player(weapon="Sword")
        adapter = make_adapter(jean, enemies=[make_npc(cls=Slime, hp=40)])
        jean._combat_adapter = adapter
        adapter.input_type = "target_selection"

        assert game_service.get_available_moves(jean) == {"moves": []}


class TestGetCombatStatus:
    """``get_combat_status`` is the poll the client runs every beat."""

    def test_outside_combat_there_is_no_battle_state(
        self, game_service, make_world, grid_3x3
    ):
        jean, _ = make_world(grid_3x3)

        status = game_service.get_combat_status(jean)

        assert status == {"combat_active": False, "log": [], "battle_state": None}

    def test_in_combat_the_battle_state_names_the_enemy(
        self, game_service, make_world, grid_3x3
    ):
        from src.npc._enemies import Slime

        jean, game_map = make_world(grid_3x3)
        slime = Slime()
        game_map[(0, 0)].npcs_here = [slime]
        game_service.start_combat(jean, wire_handle(slime))

        status = game_service.get_combat_status(jean)

        assert status["combat_active"] is True
        assert [e["name"] for e in status["battle_state"]["enemies"]] == [slime.name]
