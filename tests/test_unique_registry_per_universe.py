"""Unique-item claims belong to one universe, not the process (issue #727).

Each unique item (``items.unique_item_factories``) may exist once per game
world. The claim registry used to be a module-level set shared by every
session in the worker, so one player's merchant rolling a unique removed it
from every other player's world -- and since #727 stocks every merchant at
world build, merely creating a session could use them up.
"""

import io
import random
from unittest.mock import Mock, patch

from src.npc._shop import MerchantShopMixin
from src.secure_pickle import safe_pickle_load, serialize_for_save
from src.player import Player
from src.shop_conditions import UniqueItemInjectionCondition, iter_merchants
from src.universe import Universe


def _no_unique_rolls(self):
    self.shop_conditions = {"value": [], "availability": [], "unique": []}


def _always_roll_a_unique(self):
    self.shop_conditions = {
        "value": [], "availability": [], "unique": [UniqueItemInjectionCondition()],
    }


def _world(roll=_no_unique_rolls, seed=727):
    random.seed(seed)
    player = Player()
    player.universe = Universe(player)
    with patch.object(MerchantShopMixin, "_update_shop_conditions", roll):
        player.universe.build(player)
    return player.universe


def _save_and_load(universe):
    """Round-trip through the real save path (strict ``SafeUnpickler``)."""
    return safe_pickle_load(io.BytesIO(serialize_for_save(universe)), strict=True)


def _jambo(universe):
    game_map = next(m for m in universe.maps if m.get("name") == "grondia-jambos_shop")
    return next(iter_merchants([game_map]))


def _inject(merchant):
    return UniqueItemInjectionCondition().inject_unique_items(merchant)


def test_claiming_every_unique_in_one_world_leaves_another_worlds_pool_whole():
    world_a, world_b = _world(), _world()
    from src.items import unique_item_factories

    for _ in unique_item_factories:
        assert _inject(_jambo(world_a)), "world A could not claim its own unique"
    assert _inject(_jambo(world_a)) == []  # A's pool is now spent...
    assert _inject(_jambo(world_b)), "...and B's went with it"


def test_building_a_new_session_does_not_deplete_an_existing_ones_uniques():
    existing = _world()
    _world(roll=_always_roll_a_unique)  # a new session whose merchants all roll uniques
    assert _inject(_jambo(existing)), "the new session's build used up this world's uniques"


def test_the_claim_is_recorded_on_the_merchants_universe():
    world = _world()
    item = _inject(_jambo(world))[0]
    assert world.unique_items_spawned == {type(item).__name__}


def test_restock_releases_the_claim_back_to_that_universe_only():
    world_a, world_b = _world(), _world()
    jambo_a = _jambo(world_a)
    item = _inject(jambo_a)[0]
    world_b.unique_items_spawned.add(type(item).__name__)
    with patch.object(MerchantShopMixin, "_update_shop_conditions", _no_unique_rolls):
        jambo_a.update_goods()
    assert world_a.unique_items_spawned == set()
    assert world_b.unique_items_spawned == {type(item).__name__}


def test_a_merchant_with_no_universe_injects_nothing():
    """No world, no way to keep the item unique: skip rather than claim it
    in some registry nobody else can see."""
    merchant = Mock(spec=["name", "inventory", "current_room"])
    merchant.name = "Loose"
    merchant.inventory = []
    merchant.current_room = None
    assert _inject(merchant) == []
    assert merchant.inventory == []


def test_a_universe_saved_before_the_registry_existed_loads_with_an_empty_one():
    world = Universe()
    world.__dict__.pop("_unique_items_spawned", None)
    restored = _save_and_load(world)
    assert restored.unique_items_spawned == set()
    restored.unique_items_spawned.add("AncientRelic")
    assert restored.unique_items_spawned == {"AncientRelic"}


def test_the_registry_survives_a_save_round_trip():
    world = Universe()
    world.unique_items_spawned.add("CrystalTear")
    assert _save_and_load(world).unique_items_spawned == {"CrystalTear"}


def test_the_process_global_registry_is_gone():
    import src.items as items_module

    assert not hasattr(items_module, "unique_items_spawned")
