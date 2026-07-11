"""tests/test_items_coverage.py

Coverage tests for src/items.py targeting the assigned missing-line ranges:
  185-188, 191-194, 198-200   Item.on_equip merchandise guard
  212-252                     Item.drop stackable branch
  273, 280-363                Item.take (shop detection + stackable + weight checks)
  2176-2198, 2203-2225        DullMedallion.on_equip / on_unequip
  2277-2279, 2285-2286        JeanWeddingBand.on_equip / on_unequip
  2482, 2485-2512             Restorative.drink / use
  2557, 2560-2587             Draught.drink / use
  2635, 2638-2676             Antidote.drink / use
  2710, 2713-2735             SlimeFlask.drink / use
  2765, 2768-2790             MineralSolvent.drink / use
  2817, 2820-2846             Respite.drink / use
  2877, 2880-2896             Relic.hold / use
  2961-2962, 2965             Arrow.stack_grammar (count==1) / prefer
  3243-3244                   Book._paginate_text force-split with existing page
  3309                        Book.read() blank-text fallback
  3320-3328                   Book.use()
  3559-3560, 3566-3584, 3587  DriedCrystalSap.stack_grammar / use / drink
  3615-3616                   FabricariumRejectionShard.examine
  3854                        ConclaveSignalStone.examine
  3879                        FabricariumCompactSeal.examine
  3940-3945, 3955-3981,
  3984, 3987                  IronRation.stack_grammar / use / eat / consume
  4017-4022, 4035-4060,
  4063, 4066, 4069            Bitterroot.stack_grammar / use / eat / chew / consume

Also covers a real bug found during this pass: DriedCrystalSap never set
self.power in __init__, so calling .use() raised AttributeError. Fixed by
adding `self.power = 25` (see src/items.py).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.items as items  # noqa: E402
from src.player import Player  # noqa: E402


def _fresh_player():
    """Return a real Player with a mocked tile so item methods can run."""
    p = Player()
    tile = MagicMock()
    tile.items_here = []
    p.current_room = tile
    p.tile = tile
    return p


# ---------------------------------------------------------------------------
# Item.on_equip — merchandise guard
# ---------------------------------------------------------------------------


class TestItemOnEquipMerchandiseGuard:
    def test_merchandise_weapon_blocks_equip_and_resets_to_fists(self):
        player = _fresh_player()
        weapon = items.Rock(merchandise=True)
        weapon.isequipped = True
        if "unequip" not in weapon.interactions:
            weapon.interactions.append("unequip")
        player.eq_weapon = weapon

        weapon.on_equip(player)

        assert weapon.isequipped is False
        assert player.eq_weapon is player.fists
        assert "unequip" not in weapon.interactions
        assert "equip" in weapon.interactions

    def test_merchandise_non_weapon_blocks_equip(self):
        player = _fresh_player()
        armor = items.TatteredCloth(merchandise=True)
        armor.isequipped = True
        armor.interactions = ["unequip"]

        armor.on_equip(player)

        assert armor.isequipped is False
        assert "equip" in armor.interactions
        assert "unequip" not in armor.interactions

    def test_merchandise_item_without_isequipped_attr_does_not_raise(self):
        player = _fresh_player()
        item = items.Item(
            name="Trinket",
            description="A trinket.",
            value=1,
            maintype="Special",
            subtype="Curio",
            discovery_message="a trinket!",
        )
        item.merchandise = True
        # Should not raise despite no isequipped attribute ever being set
        item.on_equip(player)

    def test_on_equip_exception_is_swallowed(self):
        player = _fresh_player()
        weapon = items.Rock(merchandise=True)
        weapon.isequipped = True

        with patch.object(
            items.functions, "refresh_stat_bonuses", side_effect=RuntimeError("boom")
        ):
            # Should not propagate — caught by the broad except in on_equip
            weapon.on_equip(player)

    def test_non_merchandise_equip_states_applied(self):
        player = _fresh_player()
        item = items.Item(
            name="Charm",
            description="A charm.",
            value=1,
            maintype="Special",
            subtype="Curio",
            discovery_message="a charm!",
        )
        item.equip_states = [MagicMock()]
        player.apply_equip_states = MagicMock()
        item.on_equip(player)
        player.apply_equip_states.assert_called_once_with(item)


# ---------------------------------------------------------------------------
# Item.drop — stackable branch
# ---------------------------------------------------------------------------


class TestItemDropStackable:
    def test_drop_whole_stack_default_quantity(self):
        player = _fresh_player()
        item = items.Restorative(count=3)
        player.inventory = [item]

        item.drop(player)  # quantity=None -> drop whole stack

        assert item.count == 0
        assert player.current_room.spawn_item.call_count == 3
        player.current_room.stack_duplicate_items.assert_called()

    def test_drop_partial_quantity(self):
        player = _fresh_player()
        item = items.Restorative(count=5)
        player.inventory = [item]

        item.drop(player, quantity=2)

        assert item.count == 3
        assert player.current_room.spawn_item.call_count == 2

    def test_drop_zero_quantity_changes_mind(self):
        player = _fresh_player()
        item = items.Restorative(count=4)
        player.inventory = [item]

        item.drop(player, quantity=0)

        assert item.count == 4
        player.current_room.spawn_item.assert_not_called()

    def test_drop_quantity_out_of_range_invalid_amount(self):
        player = _fresh_player()
        item = items.Restorative(count=3)
        player.inventory = [item]

        item.drop(player, quantity=999)

        # Invalid amount — nothing dropped, loop breaks because quantity was given
        assert item.count == 3
        player.current_room.spawn_item.assert_not_called()

    def test_drop_non_integer_quantity_invalid_amount(self):
        player = _fresh_player()
        item = items.Restorative(count=3)
        player.inventory = [item]

        item.drop(player, quantity="abc")

        assert item.count == 3
        player.current_room.spawn_item.assert_not_called()

    def test_drop_single_count_stackable_item(self):
        """A stackable item with count==1 takes the simple 'else' drop path."""
        player = _fresh_player()
        item = items.Restorative(count=1)
        player.inventory = [item]

        item.drop(player)

        assert item in player.current_room.items_here
        assert item not in player.inventory

    def test_drop_non_stackable_equipped_item_unequips_first(self):
        player = _fresh_player()
        weapon = items.Rock()
        weapon.isequipped = True
        weapon.interactions.append("unequip")
        player.inventory = [weapon]
        player.eq_weapon = weapon

        weapon.drop(player)

        assert weapon in player.current_room.items_here
        assert weapon not in player.inventory
        assert weapon.isequipped is False
        assert player.eq_weapon is player.fists


# ---------------------------------------------------------------------------
# Item.take — shop detection, stackable, and weight-limit branches
# ---------------------------------------------------------------------------


class TestItemTake:
    def test_take_whole_stack(self):
        player = _fresh_player()
        item = items.Restorative(count=5)
        player.current_room.items_here = [item]

        item.take(player)

        assert item in player.inventory
        assert item not in player.current_room.items_here
        assert item.merchandise is False

    def test_take_partial_creates_new_item(self):
        player = _fresh_player()
        item = items.Restorative(count=5)
        player.current_room.items_here = [item]

        item.take(player, quantity=2)

        assert item.count == 3
        new_items = [
            i for i in player.inventory if isinstance(i, items.Restorative)
        ]
        assert len(new_items) == 1
        assert new_items[0].count == 2
        assert new_items[0] is not item

    def test_take_zero_quantity_changes_mind(self):
        player = _fresh_player()
        item = items.Restorative(count=5)
        player.current_room.items_here = [item]

        item.take(player, quantity=0)

        assert item.count == 5
        assert item not in player.inventory

    def test_take_invalid_amount_out_of_range(self):
        player = _fresh_player()
        item = items.Restorative(count=5)
        player.current_room.items_here = [item]

        item.take(player, quantity=999)

        assert item.count == 5
        assert item not in player.inventory

    def test_take_stackable_too_heavy_with_quantity_breaks(self):
        player = _fresh_player()
        item = items.Restorative(count=5)
        item.weight = 1000  # guarantee over capacity
        player.current_room.items_here = [item]

        item.take(player, quantity=1)

        assert item not in player.inventory
        assert item.count == 5

    def test_take_stack_in_shop_map_sets_merchandise_true(self):
        player = _fresh_player()
        player.map = {"name": "grondia-jambos_shop"}
        item = items.Restorative(count=1, merchandise=False)
        player.current_room.items_here = [item]

        item.take(player)

        assert item in player.inventory
        assert item.merchandise is True

    def test_take_non_stackable_too_heavy_returns_early(self):
        player = _fresh_player()
        weapon = items.Rock()
        weapon.weight = 1000
        player.current_room.items_here = [weapon]

        weapon.take(player)

        assert weapon not in player.inventory
        assert weapon in player.current_room.items_here

    def test_take_non_stackable_success(self):
        player = _fresh_player()
        weapon = items.Rock()
        player.current_room.items_here = [weapon]

        weapon.take(player)

        assert weapon in player.inventory
        assert weapon not in player.current_room.items_here

    def test_take_non_integer_quantity_invalid_amount(self):
        """Covers the is_input_integer() False branch (a non-numeric explicit
        quantity)."""
        player = _fresh_player()
        item = items.Restorative(count=5)
        player.current_room.items_here = [item]

        item.take(player, quantity="xyz")

        assert item.count == 5
        assert item not in player.inventory

    def test_take_no_current_room_map_attr_falls_back(self):
        """Player has no .map but does have a current_room — covers line 273."""
        player = _fresh_player()
        assert player.map is None
        item = items.Restorative(count=1)
        player.current_room.items_here = [item]

        item.take(player)

        assert item in player.inventory


# ---------------------------------------------------------------------------
# DullMedallion / JeanWeddingBand — on_equip / on_unequip
# ---------------------------------------------------------------------------


class TestDullMedallion:
    def test_on_equip_adds_idle_messages(self):
        player = _fresh_player()
        medallion = items.DullMedallion()
        before = len(player.combat_idle_msg)

        medallion.on_equip(player)

        assert len(player.combat_idle_msg) == before + 7
        assert "The words, 'Cherub Root,' flash across Jean's mind." in player.combat_idle_msg

    def test_on_unequip_removes_idle_messages(self):
        player = _fresh_player()
        medallion = items.DullMedallion()
        medallion.on_equip(player)
        before = len(player.combat_idle_msg)

        medallion.on_unequip(player)

        assert len(player.combat_idle_msg) == before - 7


class TestJeanWeddingBand:
    def test_on_equip_applies_states_and_narrates(self):
        player = _fresh_player()
        band = items.JeanWeddingBand()
        band.equip_states = [MagicMock()]
        player.apply_equip_states = MagicMock()

        band.on_equip(player)

        player.apply_equip_states.assert_called_once_with(band)

    def test_on_unequip_removes_states_and_narrates(self):
        player = _fresh_player()
        band = items.JeanWeddingBand()
        player.remove_equip_states = MagicMock()

        band.on_unequip(player)

        player.remove_equip_states.assert_called_once_with(band)

    def test_drop_interaction_removed_at_construction(self):
        band = items.JeanWeddingBand()
        assert "drop" not in band.interactions


# ---------------------------------------------------------------------------
# Consumables — drink()/use() delegation and effects
# ---------------------------------------------------------------------------


class TestRestorative:
    def test_use_merchandise_blocks(self):
        player = _fresh_player()
        item = items.Restorative(count=1, merchandise=True)
        player.inventory = [item]
        item.use(player)
        assert item.count == 1

    def test_use_heals_and_decrements_count(self):
        player = _fresh_player()
        player.hp = 50
        player.maxhp = 100
        item = items.Restorative(count=1)
        player.inventory = [item]

        item.drink(player)

        assert player.hp > 50
        assert item not in player.inventory  # count hit 0 -> removed

    def test_use_already_full_health_noop(self):
        player = _fresh_player()
        player.hp = player.maxhp
        item = items.Restorative(count=1)
        player.inventory = [item]

        item.use(player)

        assert item.count == 1
        assert item in player.inventory


class TestDraught:
    def test_use_merchandise_blocks(self):
        player = _fresh_player()
        item = items.Draught(count=1, merchandise=True)
        player.inventory = [item]
        item.use(player)
        assert item.count == 1

    def test_use_restores_fatigue_and_decrements_count(self):
        player = _fresh_player()
        player.fatigue = 10
        player.maxfatigue = 150
        item = items.Draught(count=1)
        player.inventory = [item]

        item.drink(player)

        assert player.fatigue > 10
        assert item not in player.inventory

    def test_use_already_rested_noop(self):
        player = _fresh_player()
        player.fatigue = player.maxfatigue
        item = items.Draught(count=1)
        player.inventory = [item]

        item.use(player)

        assert item.count == 1


class TestAntidote:
    def test_use_merchandise_blocks(self):
        player = _fresh_player()
        item = items.Antidote(count=1, merchandise=True)
        player.inventory = [item]
        item.use(player)
        assert item.count == 1

    def test_use_cures_poison_and_heals(self):
        player = _fresh_player()
        player.hp = 50
        player.maxhp = 100
        poison = MagicMock()
        poison.statustype = "poison"
        poison.on_removal = MagicMock()
        poison.target = player
        player.states = [poison]
        item = items.Antidote(count=1)
        player.inventory = [item]

        item.drink(player)

        assert poison not in player.states
        poison.on_removal.assert_called_once_with(player)
        assert item not in player.inventory

    def test_use_no_poison_noop(self):
        player = _fresh_player()
        player.states = []
        item = items.Antidote(count=1)
        player.inventory = [item]

        item.use(player)

        assert item.count == 1


class TestSlimeFlask:
    def test_use_merchandise_blocks(self):
        player = _fresh_player()
        item = items.SlimeFlask(count=1, merchandise=True)
        player.inventory = [item]
        item.use(player)
        assert item.count == 1

    def test_use_removes_slimed_state(self):
        player = _fresh_player()
        slimed = MagicMock()
        slimed.name = "Slimed"
        slimed.on_removal = MagicMock()
        slimed.target = player
        player.states = [slimed]
        item = items.SlimeFlask(count=1)
        player.inventory = [item]

        item.drink(player)

        assert slimed not in player.states
        assert item not in player.inventory

    def test_use_no_slime_noop(self):
        player = _fresh_player()
        player.states = []
        item = items.SlimeFlask(count=1)
        player.inventory = [item]

        item.use(player)

        assert item.count == 1


class TestMineralSolvent:
    def test_use_merchandise_blocks(self):
        player = _fresh_player()
        item = items.MineralSolvent(count=1, merchandise=True)
        player.inventory = [item]
        item.use(player)
        assert item.count == 1

    def test_use_removes_stone_state(self):
        player = _fresh_player()
        stoned = MagicMock()
        stoned.statustype = "stone"
        stoned.on_removal = MagicMock()
        stoned.target = player
        player.states = [stoned]
        item = items.MineralSolvent(count=1)
        player.inventory = [item]

        item.drink(player)

        assert stoned not in player.states
        assert item not in player.inventory

    def test_use_no_crust_noop(self):
        player = _fresh_player()
        player.states = []
        item = items.MineralSolvent(count=1)
        player.inventory = [item]

        item.use(player)

        assert item.count == 1


class TestRespite:
    def test_use_merchandise_blocks(self):
        player = _fresh_player()
        item = items.Respite(count=1, merchandise=True)
        player.inventory = [item]
        item.use(player)
        assert item.count == 1

    def test_use_removes_enraged_state_and_restores_fatigue(self):
        player = _fresh_player()
        player.fatigue = 0
        player.maxfatigue = 100
        enraged = MagicMock()
        enraged.statustype = "enraged"
        enraged.on_removal = MagicMock()
        enraged.target = player
        player.states = [enraged]
        item = items.Respite(count=1)
        player.inventory = [item]

        item.drink(player)

        assert enraged not in player.states
        assert player.fatigue == 10
        assert item not in player.inventory

    def test_use_not_burning_noop(self):
        player = _fresh_player()
        player.states = []
        item = items.Respite(count=1)
        player.inventory = [item]

        item.use(player)

        assert item.count == 1


class TestRelic:
    def test_hold_delegates_to_use(self):
        player = _fresh_player()
        apathy = MagicMock()
        apathy.statustype = "apathy"
        apathy.on_removal = MagicMock()
        apathy.target = player
        player.states = [apathy]
        item = items.Relic(count=1)
        player.inventory = [item]

        item.hold(player)

        assert apathy not in player.states
        assert item not in player.inventory

    def test_use_no_apathy_noop(self):
        player = _fresh_player()
        player.states = []
        item = items.Relic(count=1)
        player.inventory = [item]

        item.use(player)

        assert item.count == 1


# ---------------------------------------------------------------------------
# Arrow — stack_grammar (singular) and prefer()
# ---------------------------------------------------------------------------


class TestArrow:
    def test_stack_grammar_singular(self):
        arrow = items.WoodenArrow(count=1)
        arrow.stack_grammar()
        assert arrow.description == "A standard arrow, to be fired with a bow."
        assert arrow.announce == "Jean notices an arrow on the ground."

    def test_prefer_sets_player_preference(self):
        player = _fresh_player()
        arrow = items.IronArrow(count=1)
        arrow.prefer(player)
        assert player.preferences["arrow"] == "Iron Arrow"


# ---------------------------------------------------------------------------
# Book — pagination and read()/use()
# ---------------------------------------------------------------------------


class TestBookPagination:
    def test_force_split_long_sentence_after_existing_page_content(self):
        book = items.Book(name="Long Book", chars_per_page=50)
        # First a short sentence accumulates into current_page, then a very
        # long "sentence" (no delimiters) forces the split-with-existing-page
        # branch (lines 3243-3244).
        long_run = "A" * 200
        text = "Hi there. " + long_run
        pages = book._paginate_text(text)
        assert len(pages) > 1
        assert pages[0] == "Hi there."

    def test_read_blank_text_uses_description_fallback(self):
        book = items.Book(name="Blank Book", description="An empty tome.")
        book.text = ""  # force falsy text via setter
        book.read()  # should not raise; hits the else: narrate(self.description) branch

    def test_read_short_text_uses_print_slow(self):
        book = items.Book(name="Short Book", text="Just a short note.")
        book.read()

    def test_read_long_text_paginates(self):
        long_text = "Sentence number {}. ".format("x") * 100
        book = items.Book(name="Epic Tome", text=long_text, chars_per_page=200)
        book.read()

    def test_read_processes_event_and_clears_if_not_repeat(self):
        book = items.Book(name="Quest Book", text="Some lore.")
        event = MagicMock()
        event.repeat = False
        book.event = event
        book.read()
        event.process.assert_called_once()
        assert book.event is None

    def test_read_keeps_repeating_event(self):
        book = items.Book(name="Quest Book", text="Some lore.")
        event = MagicMock()
        event.repeat = True
        book.event = event
        book.read()
        assert book.event is event

    def test_use_with_text(self):
        book = items.Book(name="API Book", text="Readable via API.")
        book.use(player=None)

    def test_use_without_text_falls_back_to_description(self):
        book = items.Book(name="API Book", description="Fallback description.")
        book.text = ""
        book.use(player=None)


# ---------------------------------------------------------------------------
# DriedCrystalSap — use()/drink() (and the self.power bug fix)
# ---------------------------------------------------------------------------


class TestDriedCrystalSap:
    def test_power_attribute_is_set(self):
        """Regression test for a bug: __init__ never set self.power, so
        use() raised AttributeError as soon as it was called."""
        item = items.DriedCrystalSap()
        assert hasattr(item, "power")
        assert item.power > 0

    def test_stack_grammar_plural(self):
        item = items.DriedCrystalSap()
        item.count = 3
        item.stack_grammar()
        assert "3" in item.name

    def test_stack_grammar_singular(self):
        item = items.DriedCrystalSap()
        item.count = 2
        item.stack_grammar()  # plural first
        item.count = 1
        item.stack_grammar()  # back to singular
        assert item.name == "Dried Crystal Sap"

    def test_use_heals_and_decrements_count(self):
        player = _fresh_player()
        player.hp = 50
        player.maxhp = 100
        item = items.DriedCrystalSap()
        player.inventory = [item]

        item.drink(player)

        assert player.hp > 50
        assert item not in player.inventory

    def test_use_already_healthy_noop(self):
        player = _fresh_player()
        player.hp = player.maxhp
        item = items.DriedCrystalSap()
        player.inventory = [item]

        item.use(player)

        assert item.count == 1


# ---------------------------------------------------------------------------
# Fabricarium / Conclave lore items — examine()
# ---------------------------------------------------------------------------


class TestLoreExamineItems:
    def test_fabricarium_rejection_shard_examine(self):
        shard = items.FabricariumRejectionShard()
        shard.examine()  # should not raise

    def test_conclave_signal_stone_examine(self):
        stone = items.ConclaveSignalStone()
        stone.examine()

    def test_fabricarium_compact_seal_examine(self):
        seal = items.FabricariumCompactSeal()
        seal.examine()


# ---------------------------------------------------------------------------
# IronRation — stack_grammar / use / eat / consume
# ---------------------------------------------------------------------------


class TestIronRation:
    def test_stack_grammar_plural(self):
        item = items.IronRation(count=2)
        item.stack_grammar()
        assert "portions" in item.description

    def test_use_merchandise_blocks(self):
        player = _fresh_player()
        item = items.IronRation(count=1, merchandise=True)
        player.inventory = [item]
        item.use(player)
        assert item.count == 1

    def test_use_heals_and_decrements(self):
        player = _fresh_player()
        player.hp = 50
        player.maxhp = 100
        item = items.IronRation(count=1)
        player.inventory = [item]

        item.eat(player)

        assert player.hp > 50
        assert item not in player.inventory

    def test_use_already_healthy_noop(self):
        player = _fresh_player()
        player.hp = player.maxhp
        item = items.IronRation(count=1)
        player.inventory = [item]

        item.consume(player)

        assert item.count == 1

    def test_use_clamps_heal_to_missing_hp(self):
        """When the rolled heal amount exceeds missing HP, it's clamped."""
        player = _fresh_player()
        player.hp = 95
        player.maxhp = 100  # only 5 missing, well under the ~27-33 roll
        item = items.IronRation(count=1)
        player.inventory = [item]

        item.use(player)

        assert player.hp == 100


# ---------------------------------------------------------------------------
# Bitterroot — stack_grammar / use / eat / chew / consume
# ---------------------------------------------------------------------------


class TestBitterroot:
    def test_stack_grammar_plural(self):
        item = items.Bitterroot(count=2)
        item.stack_grammar()
        assert "roots" in item.description

    def test_use_merchandise_blocks(self):
        player = _fresh_player()
        item = items.Bitterroot(count=1, merchandise=True)
        player.inventory = [item]
        item.use(player)
        assert item.count == 1

    def test_use_heals_and_decrements(self):
        player = _fresh_player()
        player.hp = 50
        player.maxhp = 100
        item = items.Bitterroot(count=1)
        player.inventory = [item]

        item.eat(player)

        assert player.hp > 50
        assert item not in player.inventory

    def test_chew_delegates_to_use(self):
        player = _fresh_player()
        player.hp = 50
        player.maxhp = 100
        item = items.Bitterroot(count=1)
        player.inventory = [item]

        item.chew(player)

        assert player.hp > 50

    def test_use_already_healthy_noop(self):
        player = _fresh_player()
        player.hp = player.maxhp
        item = items.Bitterroot(count=1)
        player.inventory = [item]

        item.consume(player)

        assert item.count == 1
