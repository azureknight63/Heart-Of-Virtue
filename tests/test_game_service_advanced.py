"""Cross-system integration tests for ``GameService``, on real engine objects.

History
-------
Every one of this file's previous 54 tests was a mock diary. Not one of them
called a single ``GameService`` method — an AST scan for ``game_service.`` over
the old file matched zero test bodies. They set a value on a ``MagicMock`` and
then asserted the value was there::

    def test_shop_buy_deducts_gold(self, game_service, complete_mock_player):
        gold_item = MagicMock(); gold_item.name = "Gold"; gold_item.count = 100
        complete_mock_player.inventory = [gold_item]
        gold_item.count -= 50            # the test performs the "purchase"
        assert gold_item.count == 50     # ...and asserts its own subtraction

    def test_shop_buyback_restores_exact_price(self, ...):
        sold_price = 45
        buyback_price = 45
        assert buyback_price == sold_price

Eight of them asserted a bare ``True``. Deleting ``src/api/services/game_service.py``
outright would not have failed any of them.

Three of the old sections were also aimed at code that does not exist:
``TestQuestChainSystem`` (8 tests) tested a quest-chain engine — there is no
``quest_chain`` symbol anywhere under ``src/`` — and the save-system section
duplicated ``tests/test_game_service_expanded.py``, which drives real saves
against a stubbed Turso client and asserts the ``HOVS`` header bytes.

What this file covers now is the thing its docstring always claimed and nothing
else in the suite does: **multi-system interactions on real objects**. The shop
sections in particular assert that gold is *moved, not minted* (the merchant's
purse falls by exactly what the player gains) and that a reputation discount
reaches the amount actually charged, not merely the price the client displays —
CLAUDE.md names displayed-vs-charged drift as this codebase's dominant bug class.

Nothing here is mocked. A real ``Player``/``Universe``/``MapTile`` graph costs
under a millisecond (``tests/_gs_fixtures.live_world``), and a real ``Merchant``
brings the actual ``buy_modifier``/``sell_modifier``/``shop_name`` pricing
surface that ``GameService.shop_buy``/``shop_sell`` read.
"""

import pytest

from src.items import Consumable, Gold
from src.npc._enemies import Slime
from src.npc._merchants import Merchant


# ========================= HELPERS =========================


def gold_in(inventory):
    """Total gold in any inventory — the merchant's purse as well as Jean's."""
    return sum(
        getattr(item, "amt", 0)
        for item in inventory
        if getattr(item, "name", None) == "Gold"
    )


def make_consumable(name="Tonic", value=100, weight=0.1, count=1):
    """A real ``Consumable`` — the simplest item with a settable value/weight/count."""
    return Consumable(
        name=name,
        description=f"A {name.lower()}.",
        value=value,
        weight=weight,
        maintype="consumable",
        subtype="healing",
        count=count,
    )


def stock(merchant, item):
    """Put ``item`` on the merchant's shelf (``merchandise`` gates the BUY tab)."""
    item.merchandise = True
    merchant.inventory.append(item)
    return item


# ========================= FIXTURES =========================


@pytest.fixture
def world(make_world, grid_3x3):
    """A real 3x3 world with Jean at the origin."""
    return make_world(grid_3x3)


@pytest.fixture
def player(world, set_player_gold):
    """Jean, standing on the origin tile with 1000 gold."""
    jean = world[0]
    set_player_gold(jean, 1000)
    return jean


@pytest.fixture
def merchant(world):
    """A real ``Merchant`` on Jean's tile, carrying a 1000-gold purse.

    A merchant pays for purchases out of this purse. Funding it is not
    incidental: an unfunded merchant refuses every sale with "Merchant has
    insufficient funds", which is its own test below.
    """
    trader = Merchant(
        name="Milo",
        description="A trader with a cluttered stall.",
        damage=1,
        aggro=False,
        exp_award=0,
        stock_count=0,
        inventory=[Gold(1000)],
    )
    # One non-gold item so ``get_shop_state`` does not fire ``update_goods()``.
    # That auto-restock is real behaviour (see TestMerchantRestock below) but it
    # spends the purse, which would make every gold assertion here depend on a
    # random stock roll. ``merchandise`` is False, so it never reaches the BUY tab.
    ledger = make_consumable(name="Stall Ledger", value=0, weight=0.0)
    ledger.merchandise = False
    trader.inventory.append(ledger)
    world[1][(0, 0)].npcs_here = [trader]
    return trader


@pytest.fixture
def shop(game_service, player, merchant):
    """Bound helpers for the shop surface, so tests read as transactions.

    Returns an object with ``buy``/``sell``/``buyback``/``state`` bound to this
    player and merchant, plus ``id_of(item)`` for the wire identifier.
    """

    class _Shop:
        npc_id = str(id(merchant))

        @staticmethod
        def id_of(item):
            return str(id(item))

        def buy(self, item, quantity=1):
            return game_service.shop_buy(player, self.npc_id, self.id_of(item), quantity)

        def sell(self, item, quantity=1):
            return game_service.shop_sell(
                player, self.npc_id, self.id_of(item), quantity
            )

        def buyback(self, item_id):
            return game_service.shop_buyback(player, self.npc_id, item_id)

        def state(self):
            return game_service.get_shop_state(player, self.npc_id)["shop_state"]

        def sell_tab(self):
            """What the SELL tab offers: Jean's inventory minus gold and gear."""
            return game_service.get_shop_state(player, self.npc_id)["sell_inventory"]

    return _Shop()


# ========================= SHOP PRICING =========================


class TestShopPricingArithmetic:
    """``shop_buy``/``shop_sell`` compute the price and move the gold.

    Every assertion here is on real gold totals before and after, because the
    bug class these guard against is a price that is displayed correctly and
    charged incorrectly.
    """

    def test_purchase_charges_value_times_the_buy_modifier(
        self, shop, merchant, player, get_player_gold
    ):
        """Default ``buy_modifier`` is 1.0, so a 100-gold item costs 100."""
        assert merchant.buy_modifier == 1.0
        item = stock(merchant, make_consumable(value=100))

        result = shop.buy(item)

        assert result["success"] is True
        assert result["gold_spent"] == 100
        assert get_player_gold(player) == 900

    def test_purchase_gold_moves_into_the_merchants_purse(
        self, shop, merchant, player, get_player_gold
    ):
        """Gold is transferred, never minted: the merchant is up exactly 100."""
        item = stock(merchant, make_consumable(value=100))
        merchant_before = gold_in(merchant.inventory)

        shop.buy(item)

        assert gold_in(merchant.inventory) - merchant_before == 100
        assert get_player_gold(player) == 900

    def test_purchase_multiplies_by_quantity(self, shop, merchant, get_player_gold, player):
        item = stock(merchant, make_consumable(value=40, count=3))

        result = shop.buy(item, quantity=2)

        assert result["gold_spent"] == 80
        assert get_player_gold(player) == 920

    def test_purchased_units_land_in_the_players_inventory(self, shop, merchant, player):
        stock(merchant, make_consumable(name="Tonic", value=40, count=3))
        item = merchant.inventory[-1]

        shop.buy(item, quantity=2)

        carried = [i for i in player.inventory if i.name == "Tonic"]
        assert len(carried) == 1
        assert carried[0].count == 2

    def test_sale_pays_value_times_the_sell_modifier(
        self, shop, merchant, player, get_player_gold
    ):
        """Default ``sell_modifier`` is 0.5 — the merchant's margin."""
        assert merchant.sell_modifier == 0.5
        item = make_consumable(value=100)
        player.inventory.append(item)

        result = shop.sell(item)

        assert result["success"] is True
        assert result["gold_gained"] == 50
        assert get_player_gold(player) == 1050

    def test_sale_gold_comes_out_of_the_merchants_purse(
        self, shop, merchant, player, get_player_gold
    ):
        """The payout is moved, not minted — the merchant is down exactly 50."""
        item = make_consumable(value=100)
        player.inventory.append(item)
        merchant_before = gold_in(merchant.inventory)

        shop.sell(item)

        assert merchant_before - gold_in(merchant.inventory) == 50
        assert get_player_gold(player) == 1050

    def test_a_merchant_who_cannot_pay_refuses_the_sale(
        self, shop, merchant, player, get_player_gold
    ):
        """The refusal path. A broke merchant must not buy on credit."""
        merchant.inventory = [Gold(5)]
        item = make_consumable(value=100)
        player.inventory.append(item)
        player_before = get_player_gold(player)

        result = shop.sell(item)

        assert result == {"success": False, "error": "Merchant has insufficient funds"}
        assert item in player.inventory, "item left the player despite the refusal"
        assert get_player_gold(player) == player_before
        assert gold_in(merchant.inventory) == 5

    def test_the_purse_check_covers_the_whole_stack_not_one_unit(
        self, shop, merchant, player
    ):
        """A merchant able to afford one unit but not three buys none of them."""
        merchant.inventory = [Gold(60)]
        item = make_consumable(value=100, count=3)
        player.inventory.append(item)

        result = shop.sell(item, quantity=3)

        assert result["error"] == "Merchant has insufficient funds"
        assert item.count == 3

    def test_a_near_worthless_item_still_costs_one_gold(
        self, shop, merchant, get_player_gold, player
    ):
        """The unit price floors at 1 so nothing is ever free."""
        item = stock(merchant, make_consumable(name="Pebble", value=0))

        result = shop.buy(item)

        assert result["gold_spent"] == 1
        assert get_player_gold(player) == 999

    def test_an_unaffordable_purchase_names_the_shortfall_and_moves_nothing(
        self, shop, merchant, player, set_player_gold, get_player_gold
    ):
        set_player_gold(player, 10)
        item = stock(merchant, make_consumable(value=100))

        result = shop.buy(item)

        assert result == {"success": False, "error": "Not enough gold — need 90 more"}
        assert get_player_gold(player) == 10
        assert item in merchant.inventory

    def test_buy_quantity_is_clamped_to_the_stock_on_hand(
        self, shop, merchant, get_player_gold, player
    ):
        """Asking for nine of a two-item stack buys two and charges for two."""
        item = stock(merchant, make_consumable(value=10, count=2))

        result = shop.buy(item, quantity=9)

        assert result["gold_spent"] == 20
        assert get_player_gold(player) == 980

    def test_sell_quantity_is_clamped_to_the_stack_the_player_holds(
        self, shop, player, get_player_gold
    ):
        item = make_consumable(value=100, count=2)
        player.inventory.append(item)

        result = shop.sell(item, quantity=9)

        assert result["gold_gained"] == 100  # 2 x 50, not 9 x 50
        assert get_player_gold(player) == 1100


# ========================= REPUTATION =========================


class TestReputationReachesTheCharge:
    """A reputation discount must alter the gold actually taken, not just the
    number the client renders.

    ``ShopSerializer.get_effective_buy_modifier`` is deliberately shared between
    ``serialize_state`` (display) and ``shop_buy`` (charge); these tests pin
    both ends so the two cannot drift apart.
    """

    def test_neutral_reputation_is_the_baseline(self, shop, merchant, get_player_gold, player):
        """A fresh ``Player`` has no ``reputation`` attribute at all."""
        assert not hasattr(player, "reputation")
        item = stock(merchant, make_consumable(value=100))

        assert shop.buy(item)["gold_spent"] == 100
        assert get_player_gold(player) == 900

    def test_maximum_goodwill_takes_fifteen_percent_off_the_charge(
        self, shop, merchant, player, get_player_gold
    ):
        """+100 reputation is the +/-15% extreme: 1.0 * 0.85 * 100 = 85."""
        player.reputation = {"Milo": 100}
        item = stock(merchant, make_consumable(value=100))

        result = shop.buy(item)

        assert result["gold_spent"] == 85
        assert get_player_gold(player) == 915
        assert result["shop_state"]["buy_modifier"] == pytest.approx(0.85)

    def test_hostility_marks_the_price_up(self, shop, merchant, player, get_player_gold):
        """-100 reputation gives modifier 1.15; the price truncates (not rounds)
        to 114, because ``int(100 * 1.1499999999999999)`` is 114."""
        player.reputation = {"Milo": -100}
        item = stock(merchant, make_consumable(value=100))

        assert shop.buy(item)["gold_spent"] == 114
        assert get_player_gold(player) == 886

    def test_the_displayed_price_equals_the_charged_price(self, shop, merchant, player):
        """The drift guard. A partial reputation makes the two calculations
        diverge if they are ever implemented separately."""
        player.reputation = {"Milo": 60}
        item = stock(merchant, make_consumable(value=100))

        displayed = {row["name"]: row["price"] for row in shop.state()["stock"]}

        assert shop.buy(item)["gold_spent"] == displayed["Tonic"] == 91

    def test_goodwill_raises_the_sale_payout(self, shop, merchant, player, get_player_gold):
        """0.5 * 1.15 = 0.575, so a 100-gold item fetches 57."""
        player.reputation = {"Milo": 100}
        item = make_consumable(value=100)
        player.inventory.append(item)

        result = shop.sell(item)

        assert result["gold_gained"] == 57
        assert get_player_gold(player) == 1057

    def test_the_bonus_payout_still_comes_out_of_the_merchants_purse(
        self, shop, merchant, player
    ):
        """A discount is not a subsidy — the merchant funds every extra gold."""
        player.reputation = {"Milo": 100}
        item = make_consumable(value=100)
        player.inventory.append(item)
        merchant_before = gold_in(merchant.inventory)

        shop.sell(item)

        assert merchant_before - gold_in(merchant.inventory) == 57

    def test_reputation_with_someone_else_does_not_discount_this_shop(
        self, shop, merchant, player
    ):
        """The lookup is keyed on the merchant's own name."""
        player.reputation = {"Gorran": 100, "Vespera": -100}
        item = stock(merchant, make_consumable(value=100))

        assert shop.buy(item)["gold_spent"] == 100


# ========================= BUYBACK =========================


class TestBuybackLedger:
    """Selling opens a same-tick buyback offer at exactly the price paid."""

    def test_a_sale_records_the_price_paid_and_the_tick(self, shop, merchant, player):
        item = make_consumable(name="Tonic", value=100, count=2)
        player.inventory.append(item)

        shop.sell(item, quantity=2)

        (entry,) = merchant._buyback_ledger
        assert entry["item_name"] == "Tonic"
        assert entry["buyback_price"] == 50  # the *unit* price, not the total
        assert entry["count"] == 2
        assert entry["beat_acquired"] == player.universe.game_tick == 0

    def test_buying_back_costs_exactly_what_the_merchant_paid(
        self, shop, player, merchant, get_player_gold
    ):
        """A sell-then-regret round trip must be gold-neutral — no spread."""
        item = make_consumable(value=100)
        player.inventory.append(item)
        before = get_player_gold(player)

        shop.sell(item)
        assert get_player_gold(player) == before + 50

        result = shop.buyback(merchant._buyback_ledger[0]["item_id"])

        assert result["success"] is True
        assert get_player_gold(player) == before

    def test_the_item_comes_home(self, shop, player, merchant):
        item = make_consumable(name="Tonic", value=100)
        player.inventory.append(item)

        shop.sell(item)
        assert not [i for i in player.inventory if i.name == "Tonic"]

        shop.buyback(merchant._buyback_ledger[0]["item_id"])

        assert [i for i in player.inventory if i.name == "Tonic"]

    def test_a_consumed_offer_is_removed_from_the_ledger(self, shop, player, merchant):
        item = make_consumable(value=100)
        player.inventory.append(item)
        shop.sell(item)
        item_id = merchant._buyback_ledger[0]["item_id"]

        shop.buyback(item_id)

        assert merchant._buyback_ledger == []
        assert shop.buyback(item_id)["success"] is False

    def test_the_offer_expires_when_the_world_clock_advances(
        self, game_service, shop, player, merchant
    ):
        """The ledger is scoped to the tick it was created on. Walking away and
        back is two ``move_player`` calls, hence two ticks."""
        item = make_consumable(value=100)
        player.inventory.append(item)
        shop.sell(item)
        assert len(merchant._buyback_ledger) == 1

        game_service.move_player(player, "east")
        game_service.move_player(player, "west")
        assert player.universe.game_tick == 2

        assert shop.state()["buyback_items"] == []
        assert merchant._buyback_ledger == []

    def test_an_expired_offer_is_refused_by_name(
        self, game_service, shop, player, merchant
    ):
        item = make_consumable(value=100)
        player.inventory.append(item)
        shop.sell(item)
        item_id = merchant._buyback_ledger[0]["item_id"]

        game_service.move_player(player, "east")
        game_service.move_player(player, "west")

        result = shop.buyback(item_id)
        assert result["success"] is False
        assert "expired" in result["error"]


# ========================= CARRY LIMIT =========================


class TestShopRespectsTheCarryLimit:
    """Weight is checked before gold changes hands."""

    def test_an_overweight_purchase_is_refused_and_costs_nothing(
        self, shop, merchant, player, get_player_gold
    ):
        anvil = stock(merchant, make_consumable(name="Anvil", value=1, weight=999))
        before = get_player_gold(player)

        result = shop.buy(anvil)

        assert result == {"success": False, "error": "Exceeds carry limit"}
        assert get_player_gold(player) == before
        assert anvil in merchant.inventory

    def test_the_limit_counts_every_unit_in_the_order(
        self, shop, merchant, player, get_player_gold
    ):
        """One brick fits; the same purchase scaled up does not."""
        player.refresh_weight()
        headroom = player.weight_tolerance - player.weight_current
        brick = stock(
            merchant, make_consumable(name="Brick", value=1, weight=headroom / 2, count=9)
        )
        before = get_player_gold(player)

        assert shop.buy(brick, quantity=9)["success"] is False
        assert get_player_gold(player) == before

        assert shop.buy(brick, quantity=1)["success"] is True

    def test_a_purchase_inside_the_limit_goes_through(self, shop, merchant, player):
        feather = stock(merchant, make_consumable(name="Feather", value=1, weight=0.01))

        assert shop.buy(feather)["success"] is True
        assert [i for i in player.inventory if i.name == "Feather"]


# ========================= VALIDATION =========================


class TestShopTransactionValidation:
    """Bad identifiers and quantities are rejected with a specific message."""

    @pytest.mark.parametrize(
        "quantity", [0, -1, -100], ids=["zero", "negative", "very-negative"]
    )
    def test_a_non_positive_quantity_is_rejected(self, shop, merchant, quantity):
        item = stock(merchant, make_consumable(value=10))

        assert shop.buy(item, quantity=quantity)["error"] == "Invalid quantity"
        assert item in merchant.inventory

    def test_an_unknown_merchant_id_is_rejected(self, game_service, player):
        result = game_service.shop_buy(player, "no-such-npc", "no-such-item", 1)

        assert result == {
            "success": False,
            "error": "Merchant not found at this location",
        }

    def test_a_non_merchant_npc_cannot_be_shopped_at(self, game_service, player, world):
        """``_find_merchant`` gates on ``buy_modifier``, which only merchants have."""
        slime = Slime()
        world[1][(0, 0)].npcs_here.append(slime)

        result = game_service.shop_buy(player, str(id(slime)), "x", 1)

        assert result["error"] == "Merchant not found at this location"

    def test_an_item_the_merchant_does_not_have_is_rejected(self, game_service, player, merchant):
        elsewhere = make_consumable(value=10)

        result = game_service.shop_buy(player, str(id(merchant)), str(id(elsewhere)), 1)

        assert result["error"] == "Item not found in merchant inventory"

    def test_equipped_gear_cannot_be_sold(self, shop, player, get_player_gold):
        """Jean starts wearing his own clothes; selling them out from under him
        would leave the equipment slots pointing at the merchant's stock."""
        worn = next(i for i in player.inventory if getattr(i, "isequipped", False))
        before = get_player_gold(player)

        result = shop.sell(worn)

        assert result == {"success": False, "error": "Cannot sell equipped items"}
        assert worn in player.inventory
        assert get_player_gold(player) == before

    def test_a_worthless_item_has_nothing_to_sell(self, shop, player):
        junk = make_consumable(name="Lint", value=0)
        player.inventory.append(junk)

        assert shop.sell(junk)["error"] == "This item has no sell value"
        assert junk in player.inventory

    def test_gold_itself_is_not_merchandise(self, shop, player, merchant):
        """Both sides skip ``Gold`` when resolving an item id, so a purse can
        never be sold or bought as an object."""
        purse = next(i for i in player.inventory if i.name == "Gold")

        assert shop.sell(purse)["error"] == "Item not found in inventory"

        merchant_purse = next(i for i in merchant.inventory if i.name == "Gold")
        assert shop.buy(merchant_purse)["error"] == "Item not found in merchant inventory"


# ========================= ROUND TRIPS =========================


class TestShopRoundTrips:
    """Multi-transaction sequences — the margin has to accumulate correctly."""

    def test_buying_then_selling_back_loses_the_merchants_margin(
        self, shop, merchant, player, get_player_gold
    ):
        """Buy at 1.0x, sell at 0.5x: a 100-gold item costs Jean 50 to churn."""
        item = stock(merchant, make_consumable(value=100))
        before = get_player_gold(player)

        shop.buy(item)
        bought = next(i for i in player.inventory if i.name == "Tonic")
        shop.sell(bought)

        assert get_player_gold(player) == before - 50

    def test_the_merchants_purse_absorbs_exactly_that_margin(
        self, shop, merchant, player
    ):
        item = stock(merchant, make_consumable(value=100))
        merchant_before = gold_in(merchant.inventory)

        shop.buy(item)
        shop.sell(next(i for i in player.inventory if i.name == "Tonic"))

        assert gold_in(merchant.inventory) - merchant_before == 50

    def test_a_merchant_can_be_bought_out_of_gold(self, shop, merchant, player):
        """Repeated sales drain the purse until the next one is refused."""
        merchant.inventory = [Gold(120)]
        for _ in range(3):
            player.inventory.append(make_consumable(name="Tonic", value=100))

        tonics = [i for i in player.inventory if i.name == "Tonic"]
        assert shop.sell(tonics[0])["success"] is True   # purse 120 -> 70
        assert shop.sell(tonics[1])["success"] is True   # purse  70 -> 20
        third = shop.sell(tonics[2])

        assert third["error"] == "Merchant has insufficient funds"
        assert gold_in(merchant.inventory) == 20


# ========================= COMBAT LIFECYCLE =========================


class TestCombatLifecycleAcrossSystems:
    """Starting, polling and leaving a fight, driven through ``GameService``."""

    @pytest.fixture
    def slime(self, world):
        enemy = Slime()
        world[1][(0, 0)].npcs_here = [enemy]
        return enemy

    def test_start_combat_engages_both_sides(self, game_service, player, slime):
        result = game_service.start_combat(player, str(id(slime)))

        assert "error" not in result
        assert player.in_combat is True
        assert slime.in_combat is True
        assert slime.aggro is True
        assert slime in player.combat_list

    def test_start_combat_installs_the_adapter(self, game_service, player, slime):
        game_service.start_combat(player, str(id(slime)))

        assert hasattr(player, "_combat_adapter")
        assert game_service.get_combat_status(player)["combat_active"] is True

    def test_an_unknown_enemy_id_starts_no_fight(self, game_service, player, slime):
        result = game_service.start_combat(player, "not-an-npc")

        assert result == {"error": "Enemy not found"}
        assert player.in_combat is False

    def test_combat_id_identifies_the_fight_not_the_poll(
        self, game_service, player, slime
    ):
        """CLAUDE.md: the client uses ``combat_id`` to tell "new fight" from
        "same fight, next beat", so repeated polls must return one value."""
        game_service.start_combat(player, str(id(slime)))

        first = game_service.get_combat_status(player)["battle_state"]["combat_id"]
        second = game_service.get_combat_status(player)["battle_state"]["combat_id"]

        assert first == second
        assert first

    def test_the_enemy_roster_reaches_the_battle_state(self, game_service, player, slime):
        game_service.start_combat(player, str(id(slime)))

        enemies = game_service.get_combat_status(player)["battle_state"]["enemies"]

        assert [e["name"] for e in enemies] == [slime.name]
        assert enemies[0]["hp"] == slime.hp

    def test_fleeing_is_refused_while_the_enemy_is_close(
        self, game_service, player, slime
    ):
        """``flee_combat`` reads each enemy's own distance to Jean; under 20 ft
        it refuses. ``initialize_combat_positions`` randomises spawn points, so
        the distance is set explicitly rather than hoped for."""
        game_service.start_combat(player, str(id(slime)))
        slime.combat_proximity = {player: 5}

        result = game_service.flee_combat(player)

        assert result["fled"] is False
        assert "too close" in result["error"]
        assert player.in_combat is True

    def test_fleeing_from_a_distance_tears_the_fight_down(
        self, game_service, player, slime
    ):
        game_service.start_combat(player, str(id(slime)))
        slime.combat_proximity = {player: 40}

        result = game_service.flee_combat(player)

        assert result["fled"] is True
        assert player.in_combat is False
        assert player.combat_list == []
        assert slime.in_combat is False and slime.aggro is False
        assert not hasattr(player, "_combat_adapter")

    def test_fleeing_outside_combat_is_an_error(self, game_service, player):
        assert game_service.flee_combat(player) == {"error": "Not in combat"}


# ========================= WORLD STATE =========================


class TestWorldStateAcrossMoves:
    """Walking the map updates exploration, position and the world clock together."""

    def test_a_move_updates_position_room_and_clock_together(
        self, game_service, player, world
    ):
        result = game_service.move_player(player, "east")

        assert result["new_position"] == {"x": 1, "y": 0}
        assert (player.location_x, player.location_y) == (1, 0)
        assert player.current_room is world[1][(1, 0)]
        assert player.universe.game_tick == 1

    def test_the_tile_left_behind_is_remembered(self, game_service, player, world):
        """``previous_tile`` exists so story events can detect an arrival."""
        origin = world[1][(0, 0)]

        game_service.move_player(player, "east")

        assert player.previous_tile is origin

    def test_visited_tiles_accumulate_in_the_exploration_record(
        self, game_service, player
    ):
        for direction in ("east", "north", "west"):
            game_service.move_player(player, direction)

        explored = game_service.get_explored_tiles(player)

        assert {"gs-test-map:1,0", "gs-test-map:1,-1", "gs-test-map:0,-1"} <= set(explored)
        # The record is keyed per map, and carries each tile's exits so the
        # client can draw the discovered graph without re-walking it.
        assert explored["gs-test-map:1,-1"]["exits"]["south"] == {"x": 1, "y": 0}

    def test_tile_modifications_survive_a_return_visit(self, game_service, player, world):
        """Session-scoped tile state is re-applied when Jean walks back in."""
        session_data = {}
        world[1][(1, 0)].block_exit = ["north"]

        game_service.move_player(player, "east", session_data)
        world[1][(1, 0)].block_exit = []
        game_service.move_player(player, "west", session_data)
        game_service.move_player(player, "east", session_data)

        assert world[1][(1, 0)].block_exit == ["north"]

    def test_a_blocked_direction_changes_nothing_at_all(self, game_service, player):
        """The origin has no tile above the top row on a 3x3 grid edge."""
        game_service.move_player(player, "north")
        game_service.move_player(player, "north")  # now at (0, -1), the edge
        tick_at_edge = player.universe.game_tick

        result = game_service.move_player(player, "north")

        assert result == {"error": "Cannot go north from here"}
        assert (player.location_x, player.location_y) == (0, -1)
        assert player.universe.game_tick == tick_at_edge

    def test_story_and_tick_are_read_off_the_player_not_the_service(
        self, game_service, player
    ):
        """``GameService.__init__`` is ``pass`` — there is no ``self.universe``."""
        assert not hasattr(game_service, "universe")

        player.universe.story["ch01_started"] = True
        game_service.move_player(player, "east")

        assert game_service._story(player)["ch01_started"] is True
        assert game_service._game_tick(player) == player.universe.game_tick == 1


# ========================= INVENTORY x SHOP =========================


class TestInventoryAndShopInterplay:
    """Equipment state and the shop's sell tab have to agree."""

    def test_the_sell_tab_hides_what_jean_is_wearing(self, shop, player):
        """The Wedding Band is worth 900 gold and worn — it must not be offered
        for sale while equipped, or the slot would point at merchant stock."""
        band = next(i for i in player.inventory if i.name == "Wedding Band")
        assert band.isequipped is True

        offered = {row["name"] for row in shop.sell_tab()}

        assert "Wedding Band" not in offered

    def test_unequipping_makes_an_item_sellable(self, game_service, shop, player):
        band = next(i for i in player.inventory if i.name == "Wedding Band")
        assert shop.sell(band)["error"] == "Cannot sell equipped items"

        game_service.unequip_item(player, band)

        assert "Wedding Band" in {row["name"] for row in shop.sell_tab()}
        assert shop.sell(band)["gold_gained"] == 450  # 900 x the 0.5 sell modifier

    def test_selling_removes_the_item_from_the_carried_weight(
        self, game_service, shop, player
    ):
        brick = make_consumable(name="Brick", value=100, weight=5.0)
        player.inventory.append(brick)
        player.refresh_weight()
        heavy = player.weight_current

        shop.sell(brick)
        player.refresh_weight()

        assert heavy - player.weight_current == pytest.approx(5.0)

    def test_buying_adds_to_the_carried_weight(self, shop, merchant, player):
        player.refresh_weight()
        before = player.weight_current
        brick = stock(merchant, make_consumable(name="Brick", value=1, weight=2.0, count=2))

        shop.buy(brick, quantity=2)
        player.refresh_weight()

        assert player.weight_current - before == pytest.approx(4.0)

    def test_dropping_an_item_takes_it_out_of_the_sell_tab(
        self, game_service, shop, player
    ):
        tonic = make_consumable(name="Tonic", value=100)
        player.inventory.append(tonic)
        assert "Tonic" in {row["name"] for row in shop.sell_tab()}

        game_service.drop_item(player, tonic)

        assert "Tonic" not in {row["name"] for row in shop.sell_tab()}


# ========================= RESTOCK =========================


class TestMerchantRestock:
    """An empty merchant restocks the first time the shop is opened.

    ``update_goods()`` is normally driven by the terminal game loop's 1000-tick
    merchant refresh, which the API never runs — so ``get_shop_state`` triggers
    it on demand when the merchant holds nothing but gold. Note what that does
    to the purse: ``update_goods`` **clears the whole inventory** and appends a
    fresh ``Gold(base_gold * uniform(0.75, 1.25))`` pouch, so a hand-authored
    purse is replaced rather than added to. That is easy to mistake for "the
    merchant paid for the stock"; it is not, and a test asserting a *decrease*
    would pass by accident on any purse above ``base_gold``.
    """

    @pytest.fixture
    def bare_merchant(self, world):
        trader = Merchant(
            name="Vespera",
            description="A trader who has just sold out.",
            damage=1,
            aggro=False,
            exp_award=0,
            stock_count=3,
            base_gold=400,
            inventory=[Gold(1000)],
        )
        world[1][(0, 0)].npcs_here = [trader]
        return trader

    def test_opening_an_empty_shop_rerolls_the_purse(
        self, game_service, player, bare_merchant
    ):
        assert [i.name for i in bare_merchant.inventory] == ["Gold"]
        assert gold_in(bare_merchant.inventory) == 1000

        purse = game_service.get_shop_state(player, str(id(bare_merchant)))[
            "shop_state"
        ]["merchant_gold"]

        # base_gold 400 scaled by uniform(0.75, 1.25)
        assert 300 <= purse <= 500
        assert gold_in(bare_merchant.inventory) == purse

    def test_a_shop_that_already_has_stock_is_left_alone(
        self, game_service, player, merchant
    ):
        """The main ``merchant`` fixture carries one non-gold item, so the
        restock branch is skipped and the purse survives two openings."""
        first = game_service.get_shop_state(player, str(id(merchant)))["shop_state"]
        second = game_service.get_shop_state(player, str(id(merchant)))["shop_state"]

        assert first["merchant_gold"] == second["merchant_gold"] == 1000
        assert [i.name for i in merchant.inventory] == ["Gold", "Stall Ledger"]
