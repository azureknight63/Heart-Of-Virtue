"""``NPCLootMixin`` — what a corpse actually leaves on the floor.

Rewritten to drop onto a **real ``MapTile``** instead of a ``MagicMock`` room.
The mocked version could not see what it was asserting: its headline test did
``room.spawn_item.assert_any_call("FireArrow")`` and passed, even though
``FireArrow`` is not a class in ``src.items`` at all — on a real tile that call
prints ``### ERR: Unknown item type 'FireArrow'`` and spawns a stub. A mock
room accepts any item name you invent, which is exactly the failure mode
CLAUDE.md warns about.

Quantities are pinned under a seeded RNG rather than asserted to be "non-empty",
since the drop count is the whole point of ``drop_inventory``'s survival roll.
"""

import random
from unittest.mock import patch

import pytest

import src.items as items
from src.npc._loot import NPCLootMixin

from tests._gs_fixtures import live_world


class LootableNPC(NPCLootMixin):
    """Minimal host carrying the attribute contract ``NPCLootMixin`` documents."""

    def __init__(self, room=None, player=None, loot=None, name="Bandit"):
        self.name = name
        self.inventory = []
        self.loot = loot
        self.current_room = room
        self.player_ref = player
        self.embedded_arrows = []


@pytest.fixture
def world():
    """A real player on a real tile. ``_combat_adapter`` marks API combat mode,
    which is what makes the mixin record ``player.combat_drops``."""
    player, game_map = live_world()
    player._combat_adapter = object()
    return player, game_map[(0, 0)]


def _floor(tile):
    return [(type(i).__name__, i.count) for i in tile.items_here]


def patch_random_above_threshold():
    """Force every survival roll to fail (``random.random() > 0.6``)."""
    return patch("random.random", return_value=0.99)


class TestDropEmbeddedArrows:
    """Issue #418: arrows that stuck are 100% recoverable — no survival roll."""

    def test_every_embedded_arrow_spawns_as_a_real_item(self, world):
        player, tile = world
        npc = LootableNPC(tile, player)
        npc.embedded_arrows = ["WoodenArrow", "WoodenArrow", "IronArrow"]

        npc.drop_embedded_arrows()

        assert _floor(tile) == [
            ("WoodenArrow", 1),
            ("WoodenArrow", 1),
            ("IronArrow", 1),
        ]
        assert npc.embedded_arrows == []

    def test_embedded_arrows_are_visible_not_hidden(self, world):
        """Unlike scattered inventory, an arrow in a corpse is not concealed."""
        player, tile = world
        npc = LootableNPC(tile, player)
        npc.embedded_arrows = ["WoodenArrow"]

        npc.drop_embedded_arrows()

        assert tile.items_here[0].hidden is False

    def test_no_survival_roll_is_applied(self, world):
        """Ten arrows in, ten arrows out, whatever the RNG says."""
        player, tile = world
        npc = LootableNPC(tile, player)
        npc.embedded_arrows = ["WoodenArrow"] * 10

        random.seed(1)
        npc.drop_embedded_arrows()

        assert len(tile.items_here) == 10

    def test_noop_when_empty(self, world):
        player, tile = world
        npc = LootableNPC(tile, player)
        npc.embedded_arrows = []

        npc.drop_embedded_arrows()

        assert tile.items_here == []

    def test_noop_without_a_room_and_the_arrows_are_kept(self, world):
        """No room means nowhere to drop; the list must not be cleared, or the
        arrows would vanish from the world entirely."""
        player, _ = world
        npc = LootableNPC(None, player)
        npc.embedded_arrows = ["WoodenArrow"]

        npc.drop_embedded_arrows()

        assert npc.embedded_arrows == ["WoodenArrow"]


class TestDropInventory:
    def test_a_stack_survives_partially_under_a_seeded_roll(self, world):
        """Each unit independently survives with p=0.6. Seeded, so the exact
        surviving count is pinned rather than merely "some items dropped"."""
        player, tile = world
        npc = LootableNPC(tile, player)
        arrows = items.WoodenArrow()
        arrows.count = 10
        npc.inventory = [arrows]

        random.seed(0)
        npc.drop_inventory()

        assert _floor(tile) == [("WoodenArrow", 7)]
        assert npc.inventory == []

    @pytest.mark.parametrize("seed, expected", [(0, 7), (1, 6), (2, 3), (5, 2)])
    def test_the_surviving_count_tracks_the_rng(self, world, seed, expected):
        """Different seeds must give different counts — proof the roll is real
        and not, say, always dropping the whole stack."""
        player, tile = world
        npc = LootableNPC(tile, player)
        arrows = items.WoodenArrow()
        arrows.count = 10
        npc.inventory = [arrows]

        random.seed(seed)
        npc.drop_inventory()

        assert _floor(tile) == [("WoodenArrow", expected)]

    def test_dropped_inventory_is_hidden(self, world):
        """Scattered contents are concealed (hfactor 20-60), unlike arrows."""
        player, tile = world
        npc = LootableNPC(tile, player)
        arrows = items.WoodenArrow()
        arrows.count = 10
        npc.inventory = [arrows]

        random.seed(0)
        npc.drop_inventory()

        assert tile.items_here[0].hidden is True

    def test_a_wiped_out_stack_spawns_nothing(self, world):
        player, tile = world
        npc = LootableNPC(tile, player)
        arrows = items.WoodenArrow()
        arrows.count = 1
        npc.inventory = [arrows]

        with patch_random_above_threshold():
            npc.drop_inventory()

        assert tile.items_here == []
        assert not hasattr(player, "combat_drops")
        assert npc.inventory == []

    def test_the_drop_is_recorded_for_the_victory_summary(self, world):
        player, tile = world
        npc = LootableNPC(tile, player)
        arrows = items.WoodenArrow()
        arrows.count = 10
        npc.inventory = [arrows]

        random.seed(0)
        npc.drop_inventory()

        assert player.combat_drops == [
            {
                "name": "Wooden Arrow",
                "quantity": 7,
                "source": "Bandit",
                "kind": "inventory",
            }
        ]

    def test_no_combat_drops_are_recorded_outside_api_combat(self, world):
        """``combat_drops`` is only for the API victory summary."""
        player, tile = world
        del player._combat_adapter
        npc = LootableNPC(tile, player)
        arrows = items.WoodenArrow()
        arrows.count = 10
        npc.inventory = [arrows]

        random.seed(0)
        npc.drop_inventory()

        assert _floor(tile) == [("WoodenArrow", 7)]
        assert not hasattr(player, "combat_drops")

    def test_a_missing_room_aborts_without_losing_the_inventory(self, world):
        player, _ = world
        npc = LootableNPC(None, player)
        arrows = items.WoodenArrow()
        arrows.count = 3
        npc.inventory = [arrows]

        npc.drop_inventory()

        assert npc.inventory == [arrows]

    def test_an_empty_inventory_is_a_noop(self, world):
        player, tile = world
        npc = LootableNPC(tile, player)

        npc.drop_inventory()

        assert tile.items_here == []


class TestRollLoot:
    def test_a_guaranteed_entry_drops_the_named_item(self, world):
        player, tile = world
        npc = LootableNPC(tile, player, loot={"WoodenArrow": {"chance": 100, "qty": 3}})

        random.seed(7)
        npc.roll_loot()

        assert _floor(tile) == [("WoodenArrow", 3)]
        assert player.combat_drops == [
            {
                "name": "Wooden Arrow",
                "quantity": 3,
                "source": "Bandit",
                "kind": "loot",
            }
        ]

    def test_an_impossible_entry_drops_nothing(self, world):
        player, tile = world
        npc = LootableNPC(tile, player, loot={"WoodenArrow": {"chance": 0, "qty": 3}})

        random.seed(7)
        npc.roll_loot()

        assert tile.items_here == []
        assert not hasattr(player, "combat_drops")

    def test_at_most_one_entry_drops_per_death(self, world):
        """The loop breaks on the first success — a two-entry table with two
        guaranteed items must still yield exactly one."""
        player, tile = world
        npc = LootableNPC(
            tile,
            player,
            loot={
                "WoodenArrow": {"chance": 100, "qty": 2},
                "IronArrow": {"chance": 100, "qty": 2},
            },
        )

        random.seed(2)
        npc.roll_loot()

        assert len(tile.items_here) == 1
        assert len(player.combat_drops) == 1

    def test_the_equipment_branch_spawns_a_real_generated_item(self, world):
        """``Equipment_<level>_<enchantments>`` routes through the loot tables'
        random-equipment generator rather than a named item class."""
        player, tile = world
        npc = LootableNPC(tile, player, loot={"Equipment_1_0": {"chance": 100, "qty": 1}})

        random.seed(3)
        npc.roll_loot()

        assert len(tile.items_here) == 1
        spawned = tile.items_here[0]
        assert isinstance(spawned, items.Item)
        # The victory summary must name the item that actually spawned.
        assert player.combat_drops == [
            {
                "name": spawned.name,
                "quantity": 1,
                "source": "Bandit",
                "kind": "loot",
            }
        ]

    def test_a_missing_room_aborts_the_roll(self, world):
        player, _ = world
        npc = LootableNPC(None, player, loot={"WoodenArrow": {"chance": 100, "qty": 1}})

        npc.roll_loot()

        assert not hasattr(player, "combat_drops")


class TestBeforeDeath:
    def test_the_full_death_sequence_leaves_one_stacked_pile(self, world):
        """``before_death`` rolls loot, scatters inventory, drops arrows, then
        stacks the floor so duplicates merge into one entry."""
        player, tile = world
        npc = LootableNPC(tile, player, loot={"WoodenArrow": {"chance": 100, "qty": 2}})
        carried = items.WoodenArrow()
        carried.count = 10
        npc.inventory = [carried]
        npc.embedded_arrows = ["WoodenArrow", "WoodenArrow"]

        random.seed(0)
        assert npc.before_death() is True

        # 2 (loot roll) + 7 (inventory survivors at this seed, the loot roll
        # having consumed the first draws) + 2 (embedded), stacked into a
        # single WoodenArrow entry rather than three separate piles.
        assert len(tile.items_here) == 1
        assert type(tile.items_here[0]).__name__ == "WoodenArrow"
        assert tile.items_here[0].count == 11

    def test_no_loot_table_means_no_loot_roll(self, world):
        player, tile = world
        npc = LootableNPC(tile, player, loot=None)
        npc.embedded_arrows = ["IronArrow"]

        assert npc.before_death() is True

        assert _floor(tile) == [("IronArrow", 1)]

    def test_a_bare_corpse_leaves_nothing(self, world):
        player, tile = world
        npc = LootableNPC(tile, player)

        assert npc.before_death() is True

        assert tile.items_here == []
